import io
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from dominial.models import TIs, Imovel, DocumentoTipo, Documento, Cartorios, DocumentoDigital


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
        self.assertTrue(DocumentoDigital.objects.filter(
            documento=self.documento, nome_original='test.pdf'
        ).exists())

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
