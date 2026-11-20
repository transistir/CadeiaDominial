"""Representações e exclusões protegidas por OCR, migradas verbatim."""

import logging
from unittest import mock

from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.http import HttpResponse
from django.test import RequestFactory
from django.urls import reverse

from dominial.models import Documento, Imovel, TIs
from dominial.views.documento_views import excluir_documento
from ia_ocr.models import ExtracaoSugerida, OcrJob, OcrJobTransicao, PaginaOcr

from .factories import criar_documento_digital
from .test_pii_base import NOME_SENSIVEL


class StrSemNomeDoArquivoTestParte:
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
            ocr_job=job, schema_version='v1', payload={},
            payload_servico={}, provider='sintetico',  # I-5: payload_servico NOT NULL
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


class ExclusoesComOcrTestParte:
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


class ExclusoesSemOcrTestParte:
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
