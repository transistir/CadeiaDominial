"""PII: nem __str__ dos models de OCR nem as views de exclusão de
documento/TI/imóvel vazam o nome original do arquivo (identificável, dado
de terceiro) para logs.
"""

import io
import logging
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.management import call_command
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from dominial.models import Documento, Imovel, TIs
from dominial.views.documento_views import excluir_documento
from ia_ocr.backends import OcrBackend, OcrBackendError, ResultadoOcr
from ia_ocr.models import (
    ExtracaoSugerida, OcrJob, OcrJobTransicao, PaginaOcr,
)
from ia_ocr.services import criar_job

from .factories import criar_documento_digital

NOME_SENSIVEL = 'matricula-sensivel-999.pdf'
MARCADOR_PII = 'CPF-SINTETICO-999.888.777-66'
MARCADOR_CODIGO = 'CPF_SINTETICO_99988877766'


class BackendTimingComChavePii(OcrBackend):
    def processar(self, job):
        return ResultadoOcr(
            paginas=[{'numero_pagina': 1, 'texto': 'sintético', 'blocos': None}],
            sha256_pdf='1' * 64,
            page_count=1,
            timings_ms={MARCADOR_PII: 42, 'total_ms': 10},
            origem='ocr',
        )


class BackendMensagemComPii(OcrBackend):
    def processar(self, job):
        raise OcrBackendError('SERVICE_UNAVAILABLE', MARCADOR_PII)


class BackendCodigoForjadoComPii(OcrBackend):
    def processar(self, job):
        raise OcrBackendError(MARCADOR_CODIGO, MARCADOR_PII)


class BackendCodigoContratual(OcrBackend):
    def processar(self, job):
        raise OcrBackendError('TOO_MANY_PAGES', MARCADOR_PII)


class _CapturadorDeLogs(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.records = []

    def emit(self, record):
        self.records.append(record)


class SanitizacaoDePiiDoBackendTest(TestCase):
    def setUp(self):
        self.documento = criar_documento_digital()

    def _executar_backend(self, backend):
        job, _ = criar_job(self.documento)
        capturador = _CapturadorDeLogs()
        raiz = logging.getLogger()
        raiz.addHandler(capturador)
        stdout, stderr = io.StringIO(), io.StringIO()
        try:
            with override_settings(OCR_BACKEND=backend):
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    call_command('process_ocr_queue', '--once', verbosity=3)
        finally:
            raiz.removeHandler(capturador)

        job.refresh_from_db()
        formatador = logging.Formatter()
        superficies = {
            'erro_codigo': job.erro_codigo,
            'erro_mensagem': job.erro_mensagem,
            'timings_ms': repr(job.timings_ms),
            'auditoria': repr(list(job.transicoes.values_list('motivo', flat=True))),
            'caplog': '\n'.join(formatador.format(record) for record in capturador.records),
            'stdout': stdout.getvalue(),
            'stderr': stderr.getvalue(),
        }
        return job, superficies

    def _assert_marcadores_ausentes(self, superficies, *marcadores):
        for nome, conteudo in superficies.items():
            for marcador in marcadores:
                with self.subTest(superficie=nome, marcador=marcador):
                    self.assertNotIn(marcador, conteudo)

    def test_chave_de_timing_com_pii_e_descartada_de_banco_e_logs(self):
        job, superficies = self._executar_backend(
            'ia_ocr.tests.test_pii.BackendTimingComChavePii'
        )

        self.assertEqual(job.timings_ms, {'total_ms': 10})
        self._assert_marcadores_ausentes(superficies, MARCADOR_PII)

    def test_mensagem_externa_com_pii_nunca_e_persistida_ou_logada(self):
        job, superficies = self._executar_backend(
            'ia_ocr.tests.test_pii.BackendMensagemComPii'
        )

        self.assertEqual(job.erro_codigo, 'SERVICE_UNAVAILABLE')
        self.assertEqual(job.erro_mensagem, 'serviço OCR indisponível')
        self.assertEqual(
            job.transicoes.filter(para_status='falhou').get().motivo,
            'SERVICE_UNAVAILABLE',
        )
        self._assert_marcadores_ausentes(superficies, MARCADOR_PII)

    def test_codigo_forjado_com_pii_vira_erro_interno_sem_vazamento(self):
        job, superficies = self._executar_backend(
            'ia_ocr.tests.test_pii.BackendCodigoForjadoComPii'
        )

        self.assertEqual(job.erro_codigo, 'ERRO_INTERNO')
        self.assertEqual(
            job.erro_mensagem, 'falha interna no processamento do job'
        )
        self.assertEqual(
            job.transicoes.filter(para_status='falhou').get().motivo,
            'ERRO_INTERNO',
        )
        self._assert_marcadores_ausentes(
            superficies, MARCADOR_CODIGO, MARCADOR_PII
        )

    def test_codigo_valido_persiste_com_mensagem_local(self):
        job, superficies = self._executar_backend(
            'ia_ocr.tests.test_pii.BackendCodigoContratual'
        )

        self.assertEqual(job.erro_codigo, 'TOO_MANY_PAGES')
        self.assertEqual(
            job.erro_mensagem,
            'documento excede o limite de páginas do serviço',
        )
        self.assertEqual(
            job.transicoes.filter(para_status='falhou').get().motivo,
            'TOO_MANY_PAGES',
        )
        self._assert_marcadores_ausentes(superficies, MARCADOR_PII)


class StrSemNomeDoArquivoTest(TestCase):
    """__str__ dos models de OCR só expõe job_id/status/número de página.

    O repr de uma instância entra em tracebacks (ProtectedError carrega os
    objetos protegidos); se __str__ incluir o documento, o nome do arquivo
    do PDF vai junto para o log.
    """

    def test_strs_nao_carregam_nome_do_arquivo(self):
        documento = criar_documento_digital(nome=NOME_SENSIVEL)
        job = OcrJob.objects.create(documento_digital=documento)
        PaginaOcr.objects.create(
            ocr_job=job, numero_pagina=3, texto_ocr='texto sintético'
        )
        ExtracaoSugerida.objects.create(
            ocr_job=job, schema_version='v1', payload={}, provider='sintetico'
        )
        OcrJobTransicao.objects.create(
            ocr_job=job,
            de_status='pendente', para_status='em_execucao',
        )

        representacoes = [
            str(job),
            str(job.paginas.first()),
            str(job.extracoes.first()),
            str(job.transicoes.first()),
        ]
        for representacao in representacoes:
            with self.subTest(representacao=representacao):
                self.assertNotIn(NOME_SENSIVEL, representacao)
        # Identificação segue possível: job_id e número da página.
        self.assertIn(str(job.job_id), str(job))
        self.assertIn('3', str(job.paginas.first()))


class ExclusoesComOcrTest(TestCase):
    """#258: a FK PROTECT de OcrJob bloqueia a exclusão de documento/TI/imóvel —
    a resposta explica o bloqueio e o log NÃO carrega o nome do arquivo."""

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username='admin-ocr', password='senha-sintetica-123'
        )
        cls.documento_digital = criar_documento_digital(
            upload_por=cls.superuser, nome=NOME_SENSIVEL
        )
        OcrJob.objects.create(documento_digital=cls.documento_digital)
        cls.documento = cls.documento_digital.documento
        cls.imovel = cls.documento.imovel
        cls.ti = cls.imovel.terra_indigena_id

    def setUp(self):
        self.client.login(username='admin-ocr', password='senha-sintetica-123')
        self.formatador = logging.Formatter()

    def _assert_log_sem_vazamento(self, logs):
        """Confere o record FORMATADO: mensagem + exc_text (traceback)."""
        for record in logs.records:
            formatado = self.formatador.format(record)
            self.assertNotIn(NOME_SENSIVEL, formatado, formatado)

    def _mensagens(self, response):
        return [str(m) for m in get_messages(response.wsgi_request)]

    def test_exclusao_de_documento_bloqueada_por_ocr_sem_vazar_nome(self):
        # `excluir_documento` não tem rota em urls.py: chamada direta da view.
        # O template de confirmação não existe no projeto (caminho de render
        # nunca exercitado); o alvo aqui é o tratamento do ProtectedError.
        request = RequestFactory().post('/excluir-documento/')
        request.user = self.superuser
        request.session = {}
        request._messages = FallbackStorage(request)

        with mock.patch(
            'dominial.views.documento_views.render',
            return_value=HttpResponse('confirmacao sintetica'),
        ), self.assertLogs('dominial.views.documento_views', level='WARNING') as logs:
            response = excluir_documento(
                request, tis_id=self.ti.id, imovel_id=self.imovel.id,
                documento_id=self.documento.id,
            )

        self.assertEqual(response.status_code, 200)  # renderiza a confirmação
        self.assertTrue(Documento.objects.filter(id=self.documento.id).exists())
        mensagens = [str(m) for m in get_messages(request)]
        self.assertTrue(any('OCR' in m for m in mensagens), mensagens)
        self._assert_log_sem_vazamento(logs)

    def test_exclusao_de_imovel_bloqueada_por_ocr_sem_vazar_nome(self):
        with self.assertLogs('dominial.views.tis_views', level='WARNING') as logs:
            response = self.client.post(
                reverse(
                    'imovel_excluir',
                    kwargs={'tis_id': self.ti.id, 'imovel_id': self.imovel.id},
                ),
                follow=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Imovel.objects.filter(id=self.imovel.id).exists())
        mensagens = self._mensagens(response)
        self.assertTrue(any('OCR' in m for m in mensagens), mensagens)
        self._assert_log_sem_vazamento(logs)

    def test_exclusao_de_ti_bloqueada_por_ocr_sem_vazar_nome(self):
        with self.assertLogs('dominial.views.tis_views', level='WARNING') as logs:
            response = self.client.post(
                reverse('tis_delete', kwargs={'tis_id': self.ti.id}),
                follow=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(TIs.objects.filter(id=self.ti.id).exists())
        mensagens = self._mensagens(response)
        self.assertTrue(any('OCR' in m for m in mensagens), mensagens)
        self._assert_log_sem_vazamento(logs)


class ExclusoesSemOcrTest(TestCase):
    """Sem job de OCR vinculado, as três exclusões funcionam como antes."""

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username='admin-ocr-sem-job', password='senha-sintetica-123'
        )
        cls.documento_digital = criar_documento_digital(upload_por=cls.superuser)
        cls.documento = cls.documento_digital.documento
        cls.imovel = cls.documento.imovel
        cls.ti = cls.imovel.terra_indigena_id

    def setUp(self):
        self.client.login(username='admin-ocr-sem-job', password='senha-sintetica-123')

    def test_excluir_documento_sem_job_funciona(self):
        request = RequestFactory().post('/excluir-documento/')
        request.user = self.superuser
        request.session = {}
        request._messages = FallbackStorage(request)

        response = excluir_documento(
            request, tis_id=self.ti.id, imovel_id=self.imovel.id,
            documento_id=self.documento.id,
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Documento.objects.filter(id=self.documento.id).exists())

    def test_excluir_imovel_sem_job_funciona(self):
        response = self.client.post(
            reverse(
                'imovel_excluir',
                kwargs={'tis_id': self.ti.id, 'imovel_id': self.imovel.id},
            )
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Imovel.objects.filter(id=self.imovel.id).exists())

    def test_excluir_ti_sem_job_funciona(self):
        response = self.client.post(
            reverse('tis_delete', kwargs={'tis_id': self.ti.id})
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(TIs.objects.filter(id=self.ti.id).exists())
