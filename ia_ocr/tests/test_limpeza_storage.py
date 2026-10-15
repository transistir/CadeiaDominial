import tempfile
from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import TestCase, override_settings
from django.urls import reverse

from dominial.models import DocumentoDigital
from ia_ocr.models import OcrJob, PendenciaLimpezaArquivo

from .factories import criar_documento_digital


class ExclusaoDocumentoDigitalComPendenciaTest(TestCase):
    NOME_SENSIVEL = 'matricula-pessoa-sensivel.pdf'

    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_superuser(
            username='admin-limpeza-storage',
            password='senha-sintetica-123',
        )

    def setUp(self):
        self.client.login(
            username='admin-limpeza-storage',
            password='senha-sintetica-123',
        )

    def _criar_arquivo(self):
        documento_digital = criar_documento_digital(
            upload_por=self.usuario,
            nome=self.NOME_SENSIVEL,
        )
        documento_digital.arquivo.save(
            self.NOME_SENSIVEL,
            ContentFile(b'%PDF-1.4 conteudo sintetico'),
        )
        return documento_digital

    def _url(self, documento_digital):
        documento = documento_digital.documento
        return reverse('excluir_documento_digital', kwargs={
            'tis_id': documento.imovel.terra_indigena_id_id,
            'imovel_id': documento.imovel_id,
            'documento_id': documento.id,
            'arquivo_id': documento_digital.id,
        })

    @staticmethod
    def _mensagens(response):
        return [
            (mensagem.tags, str(mensagem))
            for mensagem in get_messages(response.wsgi_request)
        ]

    def test_falha_no_storage_cria_pendencia_que_localiza_arquivo_orfao(self):
        with tempfile.TemporaryDirectory() as midia, override_settings(MEDIA_ROOT=midia):
            documento_digital = self._criar_arquivo()
            arquivo_id = documento_digital.id
            documento_id = documento_digital.documento_id
            caminho = documento_digital.arquivo.name
            self.assertTrue(default_storage.exists(caminho))
            self.client.raise_request_exception = False

            with patch(
                'django.db.models.fields.files.FieldFile.delete',
                side_effect=OSError('falha sintética de storage'),
            ):
                response = self.client.post(self._url(documento_digital))

            self.assertEqual(response.status_code, 302)
            self.assertFalse(DocumentoDigital.objects.filter(id=arquivo_id).exists())
            pendencia = PendenciaLimpezaArquivo.objects.get()
            self.assertEqual(pendencia.documento_digital_id, arquivo_id)
            self.assertEqual(pendencia.documento_id, documento_id)
            self.assertEqual(pendencia.caminho_storage, caminho)
            self.assertTrue(
                default_storage.exists(pendencia.caminho_storage),
                'A pendência não localiza o objeto órfão no storage.',
            )
            mensagens = self._mensagens(response)
            self.assertTrue(
                any(tags == 'warning' and 'suporte' in texto for tags, texto in mensagens),
                mensagens,
            )

    def test_log_e_str_da_pendencia_nao_expoem_caminho_ou_nome(self):
        detalhe_erro = 'permissão negada em /storage/dado-pessoal.pdf'
        with tempfile.TemporaryDirectory() as midia, override_settings(MEDIA_ROOT=midia):
            documento_digital = self._criar_arquivo()
            arquivo_id = documento_digital.id
            caminho = documento_digital.arquivo.name
            self.client.raise_request_exception = False

            with patch(
                'django.db.models.fields.files.FieldFile.delete',
                side_effect=OSError(detalhe_erro),
            ), self.assertLogs(
                'dominial.views.documento_digital_views', level='WARNING'
            ) as logs:
                response = self.client.post(self._url(documento_digital))

            self.assertEqual(response.status_code, 302)
            pendencia = PendenciaLimpezaArquivo.objects.get()
            log = '\n'.join(logs.output)
            self.assertIn(f'arquivo_id={arquivo_id}', log)
            self.assertNotIn(caminho, log)
            self.assertNotIn(self.NOME_SENSIVEL, log)
            self.assertNotIn(detalhe_erro, log)

            representacao = str(pendencia)
            self.assertIn(str(arquivo_id), representacao)
            self.assertNotIn(caminho, representacao)
            self.assertNotIn(self.NOME_SENSIVEL, representacao)

    def test_storage_ok_nao_cria_pendencia_e_apaga_arquivo_e_registro(self):
        with tempfile.TemporaryDirectory() as midia, override_settings(MEDIA_ROOT=midia):
            documento_digital = self._criar_arquivo()
            arquivo_id = documento_digital.id
            caminho = documento_digital.arquivo.name

            response = self.client.post(self._url(documento_digital))

            self.assertEqual(response.status_code, 302)
            self.assertFalse(DocumentoDigital.objects.filter(id=arquivo_id).exists())
            self.assertFalse(default_storage.exists(caminho))
            self.assertFalse(PendenciaLimpezaArquivo.objects.exists())

    def test_job_ocr_bloqueia_exclusao_sem_criar_pendencia(self):
        with tempfile.TemporaryDirectory() as midia, override_settings(MEDIA_ROOT=midia):
            documento_digital = self._criar_arquivo()
            arquivo_id = documento_digital.id
            caminho = documento_digital.arquivo.name
            OcrJob.objects.create(documento_digital=documento_digital)

            response = self.client.post(self._url(documento_digital))

            self.assertEqual(response.status_code, 302)
            self.assertTrue(DocumentoDigital.objects.filter(id=arquivo_id).exists())
            self.assertTrue(default_storage.exists(caminho))
            self.assertFalse(PendenciaLimpezaArquivo.objects.exists())
            mensagens = self._mensagens(response)
            self.assertTrue(
                any(tags == 'error' and 'OCR' in texto for tags, texto in mensagens),
                mensagens,
            )
