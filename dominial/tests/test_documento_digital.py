import io
import re
import tempfile
from datetime import date

from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone

from dominial.models import (
    TIs, Imovel, DocumentoTipo, Documento, Cartorios, DocumentoDigital, Pessoas, UserImovel
)
from ia_ocr import estados, services
from ia_ocr.models import (
    CampoSugerido,
    ExtracaoSugerida,
    OcrJob,
    OcrJobTransicao,
    PaginaOcr,
    PendenciaLimpezaArquivo,
)


class DocumentoDigitalTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='testuser', password='testpass123')
        cls.ti = TIs.objects.create(nome='TI Teste')
        cls.cartorio = Cartorios.objects.create(nome='CRI Teste', estado='SP')
        from dominial.models import Pessoas
        cls.proprietario = Pessoas.objects.create(nome='Proprietario Teste')
        cls.tipo = DocumentoTipo.objects.create(tipo='transcricao')
        cls.imovel = Imovel.objects.create(
            nome='Imovel Teste', matricula='12345',
            terra_indigena_id=cls.ti, proprietario=cls.proprietario,
            cartorio=cls.cartorio
        )
        from datetime import date
        cls.documento = Documento.objects.create(
            imovel=cls.imovel, tipo=cls.tipo, numero='R1',
            data=date(2024, 1, 1), cartorio=cls.cartorio,
            livro='1', folha='1'
        )
        # Segregação (#132): o usuário comum só enxerga imóveis atribuídos a ele.
        UserImovel.objects.create(user=cls.user, imovel=cls.imovel)

    def setUp(self):
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

    def test_upload_pdf(self):
        """Usuário autenticado consegue fazer upload de PDF."""
        pdf_content = b'%PDF-1.4 test content'
        pdf_file = SimpleUploadedFile(
            'test.pdf', pdf_content, content_type='application/pdf'
        )
        url = reverse('upload_documento_digital', kwargs={
            'tis_id': self.ti.id, 'imovel_id': self.imovel.id,
            'documento_id': self.documento.id
        })
        response = self.client.post(url, {'arquivo': pdf_file})
        self.assertEqual(response.status_code, 302)
        # PDF volta para a própria página de upload, onde fica o card
        # "Extrair texto com IA" (fluxo tela 1 do protótipo, issue #260).
        self.assertEqual(response.url, reverse('upload_documento_digital', kwargs={
            'tis_id': self.ti.id, 'imovel_id': self.imovel.id,
            'documento_id': self.documento.id
        }))
        self.assertTrue(DocumentoDigital.objects.filter(
            documento=self.documento, nome_original='test.pdf'
        ).exists())

    def test_upload_pdf_fluxo_termina_no_card_ocr(self):
        """Fluxo tela 1 (#260): upload de PDF → card de OCR com o arquivo.

        Seguindo os redirects do POST, a página final é o próprio upload e
        traz o card "Extrair texto com IA" listando o PDF recém-anexado,
        além da mensagem de sucesso preservada.
        """
        pdf_content = b'%PDF-1.4 fluxo card'
        pdf_file = SimpleUploadedFile(
            'fluxo-card.pdf', pdf_content, content_type='application/pdf'
        )
        url = reverse('upload_documento_digital', kwargs={
            'tis_id': self.ti.id, 'imovel_id': self.imovel.id,
            'documento_id': self.documento.id
        })
        response = self.client.post(url, {'arquivo': pdf_file}, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Extrair texto com IA')
        self.assertContains(response, 'fluxo-card.pdf')
        self.assertContains(response, 'anexado com sucesso')

    def test_upload_imagem(self):
        """Usuário autenticado consegue fazer upload de imagem PNG."""
        png_content = b'\x89PNG\r\n\x1a\n' + b'\x00' * 50
        png_file = SimpleUploadedFile(
            'test.png', png_content, content_type='image/png'
        )
        url = reverse('upload_documento_digital', kwargs={
            'tis_id': self.ti.id, 'imovel_id': self.imovel.id,
            'documento_id': self.documento.id
        })
        response = self.client.post(url, {'arquivo': png_file})
        self.assertEqual(response.status_code, 302)
        # Imagem não tem card de OCR: segue para o detalhado como antes.
        self.assertEqual(response.url, reverse('documento_detalhado', kwargs={
            'tis_id': self.ti.id, 'imovel_id': self.imovel.id,
            'documento_id': self.documento.id
        }))
        self.assertTrue(DocumentoDigital.objects.filter(
            documento=self.documento
        ).exists())

    def test_upload_tipo_invalido(self):
        """Tipo de arquivo inválido é rejeitado."""
        exe_file = SimpleUploadedFile(
            'malware.exe', b'MZ' + b'\x00' * 50, content_type='application/x-msdownload'
        )
        url = reverse('upload_documento_digital', kwargs={
            'tis_id': self.ti.id, 'imovel_id': self.imovel.id,
            'documento_id': self.documento.id
        })
        response = self.client.post(url, {'arquivo': exe_file})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(DocumentoDigital.objects.filter(documento=self.documento).exists())

    def test_upload_sem_autenticacao(self):
        """Usuário não autenticado é redirecionado para login."""
        self.client.logout()
        url = reverse('upload_documento_digital', kwargs={
            'tis_id': self.ti.id, 'imovel_id': self.imovel.id,
            'documento_id': self.documento.id
        })
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_servir_documento(self):
        """Arquivo é servido corretamente via FileResponse."""
        pdf_content = b'%PDF-1.4 test content'
        pdf_file = SimpleUploadedFile(
            'read_test.pdf', pdf_content, content_type='application/pdf'
        )
        dd = DocumentoDigital.objects.create(
            documento=self.documento,
            arquivo=pdf_file,
            nome_original='read_test.pdf',
            tipo_mime='application/pdf',
            tamanho_bytes=len(pdf_content),
            upload_por=self.user,
        )
        url = reverse('servir_documento_digital', kwargs={
            'tis_id': self.ti.id, 'imovel_id': self.imovel.id,
            'documento_id': self.documento.id, 'arquivo_id': dd.id
        })
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_servir_documento_permite_embutir_no_proprio_site(self):
        """I-4 (#261): a tela de confirmação do texto exibe o PDF num iframe da
        própria origem; o padrão do Django (X-Frame-Options: DENY) o bloquearia."""
        pdf_content = b'%PDF-1.4 test content'
        with tempfile.TemporaryDirectory() as midia:
            with override_settings(MEDIA_ROOT=midia):
                dd = DocumentoDigital.objects.create(
                    documento=self.documento,
                    arquivo=SimpleUploadedFile(
                        'embed_test.pdf', pdf_content, content_type='application/pdf'
                    ),
                    nome_original='embed_test.pdf',
                    tipo_mime='application/pdf',
                    tamanho_bytes=len(pdf_content),
                    upload_por=self.user,
                )
                url = reverse('servir_documento_digital', kwargs={
                    'tis_id': self.ti.id, 'imovel_id': self.imovel.id,
                    'documento_id': self.documento.id, 'arquivo_id': dd.id
                })

                response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['X-Frame-Options'], 'SAMEORIGIN')
        # O restante do contrato do arquivo servido não muda.
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertIn('X-Accel-Redirect', response)

    def test_excluir_documento(self):
        """Exclusão via POST funciona."""
        pdf_file = SimpleUploadedFile(
            'delete_test.pdf', b'%PDF-1.4', content_type='application/pdf'
        )
        dd = DocumentoDigital.objects.create(
            documento=self.documento,
            arquivo=pdf_file,
            nome_original='delete_test.pdf',
            tipo_mime='application/pdf',
            tamanho_bytes=8,
            upload_por=self.user,
        )
        url = reverse('excluir_documento_digital', kwargs={
            'tis_id': self.ti.id, 'imovel_id': self.imovel.id,
            'documento_id': self.documento.id, 'arquivo_id': dd.id
        })
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(DocumentoDigital.objects.filter(id=dd.id).exists())

    def test_excluir_get_rejeitado(self):
        """Exclusão via GET é rejeitada (405)."""
        pdf_file = SimpleUploadedFile(
            'no_delete.pdf', b'%PDF-1.4', content_type='application/pdf'
        )
        dd = DocumentoDigital.objects.create(
            documento=self.documento,
            arquivo=pdf_file,
            nome_original='no_delete.pdf',
            tipo_mime='application/pdf',
            tamanho_bytes=8,
            upload_por=self.user,
        )
        url = reverse('excluir_documento_digital', kwargs={
            'tis_id': self.ti.id, 'imovel_id': self.imovel.id,
            'documento_id': self.documento.id, 'arquivo_id': dd.id
        })
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)
        # O arquivo ainda existe
        self.assertTrue(DocumentoDigital.objects.filter(id=dd.id).exists())

    def test_tamanho_formatado(self):
        """Property tamanho_formatado retorna string correta."""
        dd = DocumentoDigital(tamanho_bytes=500)
        self.assertEqual(dd.tamanho_formatado, '500 B')
        dd.tamanho_bytes = 2048
        self.assertEqual(dd.tamanho_formatado, '2.0 KB')
        dd.tamanho_bytes = 5 * 1024 * 1024
        self.assertEqual(dd.tamanho_formatado, '5.0 MB')

    def test_upload_magic_bytes_invalido(self):
        """Arquivo com extensão .pdf mas conteúdo inválido é rejeitado."""
        fake_pdf = SimpleUploadedFile(
            'fake.pdf', b'not a real pdf content at all', content_type='application/pdf'
        )
        url = reverse('upload_documento_digital', kwargs={
            'tis_id': self.ti.id, 'imovel_id': self.imovel.id,
            'documento_id': self.documento.id
        })
        response = self.client.post(url, {'arquivo': fake_pdf})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(DocumentoDigital.objects.filter(
            documento=self.documento, nome_original='fake.pdf'
        ).exists())


class ExcluirDocumentoDigitalComOcrTest(TestCase):
    """Regressão #258: FK PROTECT de OcrJob não pode perder o arquivo do storage.

    A ordem correta é excluir o registro primeiro; o arquivo do storage só sai
    se o registro sair. Com job de OCR vinculado, nada é apagado.
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='testuser_ocr', password='testpass123')
        cls.ti = TIs.objects.create(nome='TI Teste OCR')
        cls.cartorio = Cartorios.objects.create(nome='CRI Teste OCR', estado='SP')
        cls.proprietario = Pessoas.objects.create(nome='Proprietario Teste OCR')
        cls.tipo = DocumentoTipo.objects.create(tipo='transcricao_ocr')
        cls.imovel = Imovel.objects.create(
            nome='Imovel Teste OCR', matricula='99001',
            terra_indigena_id=cls.ti, proprietario=cls.proprietario,
            cartorio=cls.cartorio
        )
        cls.documento = Documento.objects.create(
            imovel=cls.imovel, tipo=cls.tipo, numero='R9',
            data=date(2024, 1, 1), cartorio=cls.cartorio,
            livro='9', folha='9'
        )
        UserImovel.objects.create(user=cls.user, imovel=cls.imovel)

    def setUp(self):
        self.client = Client()
        self.client.login(username='testuser_ocr', password='testpass123')

    def _criar_arquivo(self, nome='matricula-sintetica.pdf'):
        conteudo = b'%PDF-1.4 conteudo sintetico'
        pdf_file = SimpleUploadedFile(nome, conteudo, content_type='application/pdf')
        return DocumentoDigital.objects.create(
            documento=self.documento,
            arquivo=pdf_file,
            nome_original=nome,
            tipo_mime='application/pdf',
            tamanho_bytes=len(conteudo),
            upload_por=self.user,
        )

    def _url(self, arquivo_id):
        return reverse('excluir_documento_digital', kwargs={
            'tis_id': self.ti.id, 'imovel_id': self.imovel.id,
            'documento_id': self.documento.id, 'arquivo_id': arquivo_id,
        })

    def _assinatura(self, arquivo_id):
        """Assinatura do estado atual, extraída da confirmação renderizada."""
        response = self.client.post(self._url(arquivo_id))
        self.assertEqual(response.status_code, 200)
        match = re.search(
            r'name="assinatura" value="([^"]+)"', response.content.decode()
        )
        self.assertIsNotNone(match, 'A confirmação não trouxe a assinatura.')
        return match.group(1)

    def test_excluir_com_job_ocr_pede_confirmacao(self):
        with tempfile.TemporaryDirectory() as midia:
            with override_settings(MEDIA_ROOT=midia):
                dd = self._criar_arquivo()
                caminho = dd.arquivo.name
                self.assertTrue(default_storage.exists(caminho))
                job = OcrJob.objects.create(documento_digital=dd)

                response = self.client.post(self._url(dd.id))

                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'Apagar arquivo e OCR')
                self.assertContains(response, dd.nome_original)
                self.assertTrue(
                    DocumentoDigital.objects.filter(id=dd.id).exists(),
                    'O registro foi apagado sem confirmação do OCR.',
                )
                self.assertTrue(
                    OcrJob.objects.filter(id=job.id).exists(),
                    'O job de OCR foi apagado sem confirmação.',
                )
                self.assertTrue(
                    default_storage.exists(caminho),
                    'O arquivo foi apagado do storage antes da confirmação (bug #258).',
                )

    def test_excluir_confirmado_apaga_job_paginas_e_registra_pendencia(self):
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as midia:
            with override_settings(MEDIA_ROOT=midia):
                dd = self._criar_arquivo()
                arquivo_id = dd.id
                caminho = dd.arquivo.name
                job = OcrJob.objects.create(documento_digital=dd)
                PaginaOcr.objects.create(
                    ocr_job=job, numero_pagina=1, texto_ocr='texto sintetico'
                )
                assinatura = self._assinatura(arquivo_id)

                # Falha física deixa a pendência durável para retry (#258).
                with patch(
                    'django.db.models.fields.files.FieldFile.delete',
                    side_effect=OSError('falha simulada'),
                ):
                    response = self.client.post(
                        self._url(arquivo_id),
                        {'confirmar_ocr': '1', 'assinatura': assinatura},
                    )

                self.assertEqual(response.status_code, 302)
                self.assertFalse(
                    DocumentoDigital.objects.filter(id=arquivo_id).exists()
                )
                self.assertFalse(OcrJob.objects.filter(id=job.id).exists())
                self.assertFalse(
                    PaginaOcr.objects.filter(ocr_job_id=job.id).exists()
                )
                pendencia = PendenciaLimpezaArquivo.objects.get(
                    documento_digital_id=arquivo_id
                )
                self.assertEqual(pendencia.caminho_storage, caminho)
                mensagens = [str(m) for m in get_messages(response.wsgi_request)]
                self.assertTrue(
                    any('excluído com sucesso' in mensagem for mensagem in mensagens),
                    mensagens,
                )

    def test_confirmacao_mostra_contagens_de_paginas_e_extracoes(self):
        with tempfile.TemporaryDirectory() as midia:
            with override_settings(MEDIA_ROOT=midia):
                dd = self._criar_arquivo()
                job = OcrJob.objects.create(documento_digital=dd)
                PaginaOcr.objects.create(
                    ocr_job=job, numero_pagina=1, texto_ocr='pagina 1'
                )
                PaginaOcr.objects.create(
                    ocr_job=job, numero_pagina=2, texto_ocr='pagina 2',
                    confirmado_em=timezone.now(),
                )

                response = self.client.post(self._url(dd.id))

                self.assertEqual(response.status_code, 200)
                content = response.content.decode()
                self.assertIn('2 páginas', content)
                self.assertIn('1 confirmada', content)
                self.assertIn('0 extrações', content)
                self.assertIn(
                    'O texto confirmado deste arquivo será perdido. '
                    'Esta ação não pode ser desfeita.',
                    content,
                )

    def test_dois_posts_sem_confirmar_ocr_nao_apagam_nada(self):
        with tempfile.TemporaryDirectory() as midia:
            with override_settings(MEDIA_ROOT=midia):
                dd = self._criar_arquivo()
                caminho = dd.arquivo.name
                job = OcrJob.objects.create(documento_digital=dd)

                for _ in range(2):
                    response = self.client.post(self._url(dd.id))
                    self.assertEqual(response.status_code, 200)
                    self.assertContains(response, 'Apagar arquivo e OCR')

                self.assertTrue(
                    DocumentoDigital.objects.filter(id=dd.id).exists()
                )
                self.assertTrue(
                    OcrJob.objects.filter(id=job.id).exists()
                )
                self.assertTrue(default_storage.exists(caminho))

    def test_confirmar_ocr_zero_renderiza_confirmacao_sem_apagar(self):
        with tempfile.TemporaryDirectory() as midia:
            with override_settings(MEDIA_ROOT=midia):
                dd = self._criar_arquivo()
                job = OcrJob.objects.create(documento_digital=dd)

                response = self.client.post(
                    self._url(dd.id), {'confirmar_ocr': '0'}
                )

                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'Apagar arquivo e OCR')
                self.assertTrue(
                    DocumentoDigital.objects.filter(id=dd.id).exists()
                )
                self.assertTrue(OcrJob.objects.filter(id=job.id).exists())

    def test_confirmacao_divergente_nao_apaga_nada(self):
        """P2: se o OCR mudou desde o render, a confirmação antiga não vale.

        O status escolhido para a divergência é 409 (Conflict): a página é
        re-renderizada com os números atuais e o aviso, sem apagar nada.
        """
        with tempfile.TemporaryDirectory() as midia:
            with override_settings(MEDIA_ROOT=midia):
                dd = self._criar_arquivo()
                caminho = dd.arquivo.name
                job = OcrJob.objects.create(documento_digital=dd)
                pagina = PaginaOcr.objects.create(
                    ocr_job=job, numero_pagina=1, texto_ocr='pagina 1'
                )
                assinatura_velha = self._assinatura(dd.id)

                # Outro usuário confirma a página entre o render e o POST.
                pagina.confirmado_em = timezone.now()
                pagina.save(update_fields=['confirmado_em'])

                response = self.client.post(
                    self._url(dd.id),
                    {'confirmar_ocr': '1', 'assinatura': assinatura_velha},
                )

                self.assertEqual(response.status_code, 409)
                self.assertContains(
                    response,
                    'O processamento mudou desde que você abriu esta página.',
                    status_code=409,
                )
                self.assertContains(response, '1 confirmada', status_code=409)
                self.assertTrue(
                    DocumentoDigital.objects.filter(id=dd.id).exists()
                )
                self.assertTrue(OcrJob.objects.filter(id=job.id).exists())
                self.assertTrue(
                    PaginaOcr.objects.filter(id=pagina.id).exists()
                )
                self.assertTrue(default_storage.exists(caminho))

    def test_pagina_editada_e_reconfirmada_invalida_confirmacao(self):
        """P1: editar/reconfirmar a página muda texto e versão, não as contagens."""
        with tempfile.TemporaryDirectory() as midia:
            with override_settings(MEDIA_ROOT=midia):
                dd = self._criar_arquivo()
                caminho = dd.arquivo.name
                job = OcrJob.objects.create(documento_digital=dd)
                pagina = PaginaOcr.objects.create(
                    ocr_job=job, numero_pagina=1, texto_ocr='ocr original',
                    texto_confirmado='texto confirmado original',
                    confirmado_em=timezone.now(), versao=1,
                )
                assinatura_velha = self._assinatura(dd.id)

                # Outro usuário edita e reconfirma a mesma página: contagem e
                # job continuam iguais, mas texto e versão mudam.
                PaginaOcr.objects.filter(id=pagina.id).update(
                    texto_confirmado='texto novo nunca exibido',
                    versao=2,
                    confirmado_em=timezone.now(),
                )

                response = self.client.post(
                    self._url(dd.id),
                    {'confirmar_ocr': '1', 'assinatura': assinatura_velha},
                )

                self.assertEqual(response.status_code, 409)
                self.assertContains(
                    response,
                    'O processamento mudou desde que você abriu esta página.',
                    status_code=409,
                )
                self.assertTrue(
                    DocumentoDigital.objects.filter(id=dd.id).exists()
                )
                self.assertTrue(OcrJob.objects.filter(id=job.id).exists())
                pagina.refresh_from_db()
                self.assertEqual(pagina.texto_confirmado, 'texto novo nunca exibido')
                self.assertEqual(pagina.versao, 2)
                self.assertTrue(default_storage.exists(caminho))

    def test_extracao_alterada_no_lugar_invalida_confirmacao(self):
        """P1: conteúdo novo de extração invalida a assinatura sem mudar contagem."""
        with tempfile.TemporaryDirectory() as midia:
            with override_settings(MEDIA_ROOT=midia):
                dd = self._criar_arquivo()
                caminho = dd.arquivo.name
                job = OcrJob.objects.create(documento_digital=dd)
                extracao = ExtracaoSugerida.objects.create(
                    ocr_job=job, schema_version='v1',
                    payload={'campo': 'original'},
                    provider='teste', payload_servico={'campo': 'original'},
                )
                assinatura_velha = self._assinatura(dd.id)

                # Outro usuário altera a extração sem criar/remover nenhuma.
                ExtracaoSugerida.objects.filter(id=extracao.id).update(
                    payload={'campo': 'alterado'},
                )

                response = self.client.post(
                    self._url(dd.id),
                    {'confirmar_ocr': '1', 'assinatura': assinatura_velha},
                )

                self.assertEqual(response.status_code, 409)
                self.assertContains(
                    response,
                    'O processamento mudou desde que você abriu esta página.',
                    status_code=409,
                )
                self.assertTrue(
                    DocumentoDigital.objects.filter(id=dd.id).exists()
                )
                self.assertTrue(OcrJob.objects.filter(id=job.id).exists())
                extracao.refresh_from_db()
                self.assertEqual(extracao.payload, {'campo': 'alterado'})
                self.assertTrue(default_storage.exists(caminho))

    def test_campo_revisado_depois_do_render_invalida_confirmacao(self):
        """#303: revisão de campo não toca no job/extração, mas invalida a assinatura.

        Usa `salvar_bloco()` — o serviço chamado pela view de revisão — em vez
        do endpoint, que exigiria montar request/URL de revisão. É o mesmo
        caminho que grava `CampoSugerido` sem tocar em `payload`,
        `payload_servico`, `finalizada_em` ou `job.atualizado_em`.
        """
        with tempfile.TemporaryDirectory() as midia:
            with override_settings(MEDIA_ROOT=midia):
                dd = self._criar_arquivo()
                caminho = dd.arquivo.name
                job = OcrJob.objects.create(
                    documento_digital=dd, status=estados.EXTRAIDO,
                    criado_por=self.user,
                )
                extracao = ExtracaoSugerida.objects.create(
                    ocr_job=job, schema_version='v1', payload={'v': 1},
                    provider='teste', payload_servico={'v': 1},
                    solicitada_por=self.user,
                )
                campo = CampoSugerido.objects.create(
                    extracao=extracao, chave='/document/numero',
                    tipo_valor='texto',
                )
                assinatura_velha = self._assinatura(dd.id)

                # Outro revisor edita o campo depois do render, sem mudar a
                # contagem de jobs/páginas/extrações.
                services.salvar_bloco(
                    extracao,
                    {'/document/numero': {
                        'incluir': True, 'valor': 'valor revisado',
                    }},
                    self.user, services.versao_bloco(extracao),
                )

                response = self.client.post(
                    self._url(dd.id),
                    {'confirmar_ocr': '1', 'assinatura': assinatura_velha},
                )

                self.assertEqual(response.status_code, 409)
                self.assertContains(
                    response,
                    'O processamento mudou desde que você abriu esta página.',
                    status_code=409,
                )
                self.assertTrue(
                    DocumentoDigital.objects.filter(id=dd.id).exists()
                )
                self.assertTrue(OcrJob.objects.filter(id=job.id).exists())
                self.assertTrue(
                    ExtracaoSugerida.objects.filter(id=extracao.id).exists()
                )
                campo.refresh_from_db()
                self.assertEqual(campo.valor_final, 'valor revisado')
                self.assertEqual(campo.status_revisao, 'editado')
                self.assertTrue(default_storage.exists(caminho))

    def test_job_criado_depois_do_render_invalida_confirmacao(self):
        """P3: job novo entre o render e o POST re-renderiza com ele na lista."""
        with tempfile.TemporaryDirectory() as midia:
            with override_settings(MEDIA_ROOT=midia):
                dd = self._criar_arquivo()
                caminho = dd.arquivo.name
                job_antigo = OcrJob.objects.create(documento_digital=dd)
                assinatura_velha = self._assinatura(dd.id)

                # Outro fluxo cria um job entre a confirmação e o POST.
                job_novo = OcrJob.objects.create(documento_digital=dd)
                PaginaOcr.objects.create(
                    ocr_job=job_novo, numero_pagina=1, texto_ocr='nova'
                )

                response = self.client.post(
                    self._url(dd.id),
                    {'confirmar_ocr': '1', 'assinatura': assinatura_velha},
                )

                self.assertEqual(response.status_code, 409)
                self.assertContains(
                    response,
                    'O processamento mudou desde que você abriu esta página.',
                    status_code=409,
                )
                conteudo = response.content.decode()
                self.assertEqual(
                    conteudo.count('1 processamento de OCR'), 2,
                    'A página não exibiu o job criado depois do render.',
                )
                self.assertIn('1 página', conteudo)
                self.assertTrue(
                    DocumentoDigital.objects.filter(id=dd.id).exists()
                )
                self.assertTrue(
                    OcrJob.objects.filter(
                        id__in=[job_antigo.id, job_novo.id]
                    ).count() == 2
                )
                self.assertTrue(default_storage.exists(caminho))

    def test_confirmado_sem_assinatura_nao_apaga_nada(self):
        """Cliente antigo (aba velha) não tem assinatura: trata como divergente."""
        with tempfile.TemporaryDirectory() as midia:
            with override_settings(MEDIA_ROOT=midia):
                dd = self._criar_arquivo()
                caminho = dd.arquivo.name
                job = OcrJob.objects.create(documento_digital=dd)

                response = self.client.post(
                    self._url(dd.id), {'confirmar_ocr': '1'}
                )

                self.assertEqual(response.status_code, 409)
                self.assertTrue(
                    DocumentoDigital.objects.filter(id=dd.id).exists()
                )
                self.assertTrue(OcrJob.objects.filter(id=job.id).exists())
                self.assertTrue(default_storage.exists(caminho))

    def test_aviso_neutro_quando_nao_ha_pagina_confirmada(self):
        with tempfile.TemporaryDirectory() as midia:
            with override_settings(MEDIA_ROOT=midia):
                dd = self._criar_arquivo()
                job = OcrJob.objects.create(documento_digital=dd)
                PaginaOcr.objects.create(
                    ocr_job=job, numero_pagina=1, texto_ocr='pendente'
                )

                response = self.client.post(self._url(dd.id))

                content = response.content.decode()
                self.assertIn(
                    'O processamento de OCR deste arquivo será removido.',
                    content,
                )
                self.assertNotIn(
                    'O texto confirmado deste arquivo será perdido.', content
                )

    def test_confirmado_apaga_cascatas_e_arquivo_fisico_sem_pendencia(self):
        with tempfile.TemporaryDirectory() as midia:
            with override_settings(MEDIA_ROOT=midia):
                dd = self._criar_arquivo('cascata.pdf')
                arquivo_id = dd.id
                caminho = dd.arquivo.name
                job = OcrJob.objects.create(documento_digital=dd)
                pagina = PaginaOcr.objects.create(
                    ocr_job=job, numero_pagina=1, texto_ocr='pagina 1'
                )
                extracao = ExtracaoSugerida.objects.create(
                    ocr_job=job, schema_version='v1', payload={},
                    provider='teste', payload_servico={},
                )
                campo = CampoSugerido.objects.create(
                    extracao=extracao, chave='nome'
                )
                transicao = OcrJobTransicao.objects.create(
                    ocr_job=job, de_status='pendente', para_status='em_execucao'
                )
                assinatura = self._assinatura(arquivo_id)

                with self.assertLogs(
                    'dominial.views.documento_digital_views', level='INFO'
                ) as logs:
                    response = self.client.post(
                        self._url(arquivo_id),
                        {'confirmar_ocr': '1', 'assinatura': assinatura},
                    )

                self.assertEqual(response.status_code, 302)
                self.assertFalse(
                    DocumentoDigital.objects.filter(id=arquivo_id).exists()
                )
                self.assertFalse(OcrJob.objects.filter(id=job.id).exists())
                self.assertFalse(
                    PaginaOcr.objects.filter(id=pagina.id).exists()
                )
                self.assertFalse(
                    ExtracaoSugerida.objects.filter(id=extracao.id).exists()
                )
                self.assertFalse(
                    CampoSugerido.objects.filter(id=campo.id).exists()
                )
                self.assertFalse(
                    OcrJobTransicao.objects.filter(id=transicao.id).exists()
                )
                self.assertFalse(default_storage.exists(caminho))
                self.assertFalse(
                    PendenciaLimpezaArquivo.objects.filter(
                        documento_digital_id=arquivo_id
                    ).exists()
                )
                log = '\n'.join(logs.output)
                self.assertIn(f'arquivo_id={arquivo_id}', log)
                self.assertIn(f'user_id={self.user.id}', log)
                self.assertIn('jobs=1', log)
                self.assertNotIn('cascata.pdf', log)

    def test_dois_jobs_no_mesmo_arquivo_apagam_junto(self):
        with tempfile.TemporaryDirectory() as midia:
            with override_settings(MEDIA_ROOT=midia):
                dd = self._criar_arquivo()
                arquivo_id = dd.id
                job1 = OcrJob.objects.create(documento_digital=dd)
                job2 = OcrJob.objects.create(documento_digital=dd)
                pag1 = PaginaOcr.objects.create(
                    ocr_job=job1, numero_pagina=1, texto_ocr='p1'
                )
                pag2 = PaginaOcr.objects.create(
                    ocr_job=job2, numero_pagina=1, texto_ocr='p2',
                    confirmado_em=timezone.now(),
                )
                assinatura = self._assinatura(arquivo_id)

                response = self.client.post(
                    self._url(arquivo_id),
                    {'confirmar_ocr': '1', 'assinatura': assinatura},
                )

                self.assertEqual(response.status_code, 302)
                self.assertFalse(
                    DocumentoDigital.objects.filter(id=arquivo_id).exists()
                )
                self.assertFalse(
                    OcrJob.objects.filter(id__in=[job1.id, job2.id]).exists()
                )
                self.assertFalse(
                    PaginaOcr.objects.filter(
                        id__in=[pag1.id, pag2.id]
                    ).exists()
                )

    def test_protected_error_orienta_tentar_novamente(self):
        from unittest.mock import patch
        from django.db.models import ProtectedError

        with tempfile.TemporaryDirectory() as midia:
            with override_settings(MEDIA_ROOT=midia):
                dd = self._criar_arquivo()
                job = OcrJob.objects.create(documento_digital=dd)
                assinatura = self._assinatura(dd.id)

                with patch(
                    'django.db.models.query.QuerySet.delete',
                    side_effect=ProtectedError('protegido', []),
                ):
                    response = self.client.post(
                        self._url(dd.id),
                        {'confirmar_ocr': '1', 'assinatura': assinatura},
                    )

                self.assertEqual(response.status_code, 302)
                mensagens = [
                    str(m) for m in get_messages(response.wsgi_request)
                ]
                self.assertIn(
                    'O processamento de OCR mudou enquanto você confirmava. '
                    'Tente novamente.',
                    mensagens,
                )
                self.assertFalse(
                    any('suporte' in mensagem for mensagem in mensagens)
                )
                self.assertTrue(
                    DocumentoDigital.objects.filter(id=dd.id).exists()
                )
                self.assertTrue(OcrJob.objects.filter(id=job.id).exists())

    def test_excluir_sem_job_ocr_apaga_registro_e_arquivo(self):
        with tempfile.TemporaryDirectory() as midia:
            with override_settings(MEDIA_ROOT=midia):
                dd = self._criar_arquivo()
                caminho = dd.arquivo.name
                self.assertTrue(default_storage.exists(caminho))

                response = self.client.post(self._url(dd.id))

                self.assertEqual(response.status_code, 302)
                self.assertFalse(DocumentoDigital.objects.filter(id=dd.id).exists())
                self.assertFalse(
                    default_storage.exists(caminho),
                    'O arquivo permaneceu no storage após excluir o registro.',
                )

    def test_excluir_com_falha_no_storage_remove_registro_e_avisa_sem_pii_no_log(self):
        from unittest.mock import patch

        nome = 'matricula-pessoa-sensivel.pdf'
        detalhe_erro = 'permissão negada em /storage/dado-pessoal.pdf'
        with tempfile.TemporaryDirectory() as midia:
            with override_settings(MEDIA_ROOT=midia):
                dd = self._criar_arquivo(nome)
                arquivo_id = dd.id
                caminho = dd.arquivo.name
                self.assertTrue(default_storage.exists(caminho))
                self.client.raise_request_exception = False

                with patch(
                    'django.db.models.fields.files.FieldFile.delete',
                    side_effect=OSError(detalhe_erro),
                ), self.assertLogs(
                    'dominial.views.documento_digital_views', level='WARNING'
                ) as logs:
                    response = self.client.post(self._url(arquivo_id))
                    self.assertEqual(response.status_code, 302)

                self.assertFalse(DocumentoDigital.objects.filter(id=arquivo_id).exists())
                self.assertTrue(
                    default_storage.exists(caminho),
                    'O mock deveria preservar o arquivo órfão no storage.',
                )
                mensagens = [
                    (mensagem.tags, str(mensagem))
                    for mensagem in get_messages(response.wsgi_request)
                ]
                self.assertTrue(
                    any(tags == 'success' and nome in texto for tags, texto in mensagens),
                    mensagens,
                )
                self.assertTrue(
                    any(
                        tags == 'warning'
                        and 'arquivo físico' in texto
                        and 'suporte' in texto
                        for tags, texto in mensagens
                    ),
                    mensagens,
                )

                log = '\n'.join(logs.output)
                self.assertIn(f'arquivo_id={arquivo_id}', log)
                self.assertIn('limpeza física', log)
                self.assertNotIn(nome, log)
                self.assertNotIn(caminho, log)
                self.assertNotIn(detalhe_erro, log)
