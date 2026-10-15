"""Regressões da classificação de bloqueios PROTECT nas exclusões (#258)."""

import logging
from datetime import date
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.db.models import ProtectedError
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from dominial.models import (
    Cartorios,
    Documento,
    DocumentoDigital,
    DocumentoTipo,
    Imovel,
    Lancamento,
    LancamentoTipo,
    Pessoas,
    TIs,
)
from dominial.views.documento_views import excluir_documento
from dominial.views.tis_views import imovel_delete, tis_delete


User = get_user_model()
NOME_ARQUIVO_PII = 'matricula-pessoa-sensivel-12345678900.pdf'


class ExclusoesComVinculoNaoOcrTest(TestCase):
    """Um PROTECT alheio ao OCR deve identificar o tipo bloqueador real."""

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username='admin-protect-nao-ocr', password='senha-sintetica-123'
        )
        cls.cartorio = Cartorios.objects.create(
            nome='CRI Proteção sem OCR', estado='PA'
        )
        cls.proprietario = Pessoas.objects.create(nome='Pessoa Sintética')
        cls.tipo_documento = DocumentoTipo.objects.create(tipo='matricula')
        cls.tipo_lancamento = LancamentoTipo.objects.create(
            tipo='averbacao'
        )

        cls.ti_externa = TIs.objects.create(
            nome='TI externa sintética', codigo='TI-EXT-PROTECT', etnia='Sintética'
        )
        cls.imovel_externo = cls._criar_imovel(cls.ti_externa, 9000)
        cls.documento_externo = cls._criar_documento(cls.imovel_externo, 9000)

        cls.ti_documento = TIs.objects.create(
            nome='TI documento sintética', codigo='TI-DOC-PROTECT', etnia='Sintética'
        )
        cls.imovel_documento = cls._criar_imovel(cls.ti_documento, 9001)
        cls.documento_alvo = cls._criar_documento(cls.imovel_documento, 9001)

        cls.ti_imovel = TIs.objects.create(
            nome='TI imóvel sintética', codigo='TI-IMO-PROTECT', etnia='Sintética'
        )
        cls.imovel_alvo = cls._criar_imovel(cls.ti_imovel, 9002)
        cls.documento_do_imovel = cls._criar_documento(cls.imovel_alvo, 9002)

        cls.ti_alvo = TIs.objects.create(
            nome='TI alvo sintética', codigo='TI-ALVO-PROTECT', etnia='Sintética'
        )
        cls.imovel_da_ti = cls._criar_imovel(cls.ti_alvo, 9003)
        cls.documento_da_ti = cls._criar_documento(cls.imovel_da_ti, 9003)

        for indice, documento_origem in enumerate(
            (cls.documento_alvo, cls.documento_do_imovel, cls.documento_da_ti),
            start=1,
        ):
            Lancamento.objects.create(
                documento=cls.documento_externo,
                tipo=cls.tipo_lancamento,
                numero_lancamento=f'AV{indice}',
                data=date(2026, 1, indice),
                documento_origem=documento_origem,
            )
            DocumentoDigital.objects.create(
                documento=documento_origem,
                arquivo=f'documentos_digitais/{indice}/{NOME_ARQUIVO_PII}',
                nome_original=NOME_ARQUIVO_PII,
                tipo_mime='application/pdf',
                tamanho_bytes=123,
                upload_por=cls.superuser,
            )

    @classmethod
    def _criar_imovel(cls, ti, numero):
        return Imovel.objects.create(
            terra_indigena_id=ti,
            nome=f'Imóvel sintético {numero}',
            proprietario=cls.proprietario,
            matricula=str(numero),
            cartorio=cls.cartorio,
        )

    @classmethod
    def _criar_documento(cls, imovel, numero):
        return Documento.objects.create(
            imovel=imovel,
            tipo=cls.tipo_documento,
            numero=f'M{numero}',
            data=date(2026, 1, 1),
            cartorio=cls.cartorio,
            livro='1',
            folha=str(numero),
        )

    def _request_post(self):
        request = RequestFactory().post('/exclusao-protegida/')
        request.user = self.superuser
        request.session = {}
        request._messages = FallbackStorage(request)
        return request

    def _assert_vinculo_real_sem_pii(self, request, logs, entidade):
        mensagens = [str(mensagem) for mensagem in get_messages(request)]
        self.assertEqual(len(mensagens), 1, mensagens)
        mensagem = mensagens[0]
        self.assertIn(
            f'{entidade} possui vínculos que impedem a exclusão (lançamentos).',
            mensagem,
        )
        self.assertNotIn('OCR', mensagem)

        formatador = logging.Formatter()
        logs_formatados = '\n'.join(
            formatador.format(record) for record in logs.records
        )
        self.assertIn('tipos=Lançamentos', logs_formatados)
        self.assertNotIn('OcrJob', logs_formatados)
        self.assertNotIn(NOME_ARQUIVO_PII, logs_formatados)

    def test_documento_bloqueado_por_job_ocr_informa_processamento_sem_pii(self):
        from ia_ocr.services import criar_job

        documento_digital = DocumentoDigital.objects.create(
            documento=self.documento_alvo,
            arquivo=f'documentos_digitais/ocr/{NOME_ARQUIVO_PII}',
            nome_original=NOME_ARQUIVO_PII,
            tipo_mime='application/pdf',
            tamanho_bytes=456,
            upload_por=self.superuser,
        )
        job, criado = criar_job(
            documento_digital,
            criado_por=self.superuser,
        )
        self.assertTrue(criado)

        request = self._request_post()
        with mock.patch(
            'dominial.views.documento_views.render',
            return_value=HttpResponse('confirmação sintética'),
        ), self.assertLogs(
            'dominial.views.documento_views', level='WARNING'
        ) as logs:
            response = excluir_documento(
                request,
                tis_id=self.ti_documento.id,
                imovel_id=self.imovel_documento.id,
                documento_id=self.documento_alvo.id,
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Documento.objects.filter(pk=self.documento_alvo.pk).exists())
        mensagens = [str(mensagem) for mensagem in get_messages(request)]
        self.assertEqual(len(mensagens), 1, mensagens)
        self.assertIn('processamento de OCR', mensagens[0])

        formatador = logging.Formatter()
        logs_formatados = '\n'.join(
            formatador.format(record) for record in logs.records
        )
        self.assertIn(f'documento id={self.documento_alvo.id}', logs_formatados)
        self.assertIn('Jobs de OCR', logs_formatados)
        self.assertNotIn(NOME_ARQUIVO_PII, logs_formatados)
        self.assertNotIn(str(job), logs_formatados)

    def test_documento_com_protected_objects_vazio_usa_mensagem_generica(self):
        request = self._request_post()
        with mock.patch.object(
            Documento,
            'delete',
            side_effect=ProtectedError('bloqueio', set()),
        ), mock.patch(
            'dominial.views.documento_views.render',
            return_value=HttpResponse('confirmação sintética'),
        ), self.assertLogs(
            'dominial.views.documento_views', level='WARNING'
        ):
            response = excluir_documento(
                request,
                tis_id=self.ti_documento.id,
                imovel_id=self.imovel_documento.id,
                documento_id=self.documento_alvo.id,
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Documento.objects.filter(pk=self.documento_alvo.pk).exists())
        mensagens = [str(mensagem) for mensagem in get_messages(request)]
        self.assertEqual(len(mensagens), 1, mensagens)
        self.assertEqual(
            mensagens[0],
            'Documento possui vínculos que impedem a exclusão. '
            'Remova esses vínculos antes de excluir.',
        )
        self.assertNotIn('OCR', mensagens[0])

    def test_documento_bloqueado_por_lancamento_informa_vinculo_real(self):
        request = self._request_post()
        with mock.patch(
            'dominial.views.documento_views.render',
            return_value=HttpResponse('confirmação sintética'),
        ), self.assertLogs(
            'dominial.views.documento_views', level='WARNING'
        ) as logs:
            response = excluir_documento(
                request,
                tis_id=self.ti_documento.id,
                imovel_id=self.imovel_documento.id,
                documento_id=self.documento_alvo.id,
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Documento.objects.filter(pk=self.documento_alvo.pk).exists())
        self._assert_vinculo_real_sem_pii(request, logs, 'Documento')
        self.assertIn(f'documento id={self.documento_alvo.id}', logs.output[0])

    def test_imovel_bloqueado_por_lancamento_informa_vinculo_real(self):
        request = self._request_post()
        with mock.patch(
            'dominial.views.tis_views.render',
            return_value=HttpResponse('confirmação sintética'),
        ), self.assertLogs('dominial.views.tis_views', level='WARNING') as logs:
            response = imovel_delete(
                request, tis_id=self.ti_imovel.id, imovel_id=self.imovel_alvo.id
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Imovel.objects.filter(pk=self.imovel_alvo.pk).exists())
        self._assert_vinculo_real_sem_pii(request, logs, 'Imóvel')
        self.assertIn(f'imovel id={self.imovel_alvo.id}', logs.output[0])

    def test_ti_bloqueada_por_lancamento_informa_vinculo_real(self):
        request = self._request_post()
        with mock.patch(
            'dominial.views.tis_views.render',
            return_value=HttpResponse('confirmação sintética'),
        ), self.assertLogs('dominial.views.tis_views', level='WARNING') as logs:
            response = tis_delete(request, tis_id=self.ti_alvo.id)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(TIs.objects.filter(pk=self.ti_alvo.pk).exists())
        self._assert_vinculo_real_sem_pii(request, logs, 'Terra Indígena')
        self.assertIn(f'tis id={self.ti_alvo.id}', logs.output[0])
