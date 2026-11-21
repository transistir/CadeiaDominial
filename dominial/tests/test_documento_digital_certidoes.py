"""Testes do botão "Baixar certidões" — ZIP com os PDFs da cadeia (#334).

Em arquivo próprio porque o legado ``test_documento_digital.py`` está
congelado no baseline de 400 linhas (nenhum arquivo em baseline pode crescer).
"""

import io
import zipfile
from datetime import date

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

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
    UserImovel,
)


class _BaseCadeiaCertidoes(TestCase):
    """Cadeia real: M12345 (imóvel principal) <- T50 (imóvel de origem).

    Mesma receita de ``test_issue_172_suprimir_troncos``: lançamentos
    ``inicio_matricula`` via ``bulk_create`` (sem o signal de origens
    automáticas) fazem a origem T50 entrar no tronco principal do imóvel
    principal, como documento importado.
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='user_certidoes', password='testpass123'
        )
        cls.outro_user = User.objects.create_user(
            username='outro_certidoes', password='testpass123'
        )
        cls.tis = TIs.objects.create(nome='TI 334', codigo='TI334', etnia='X')
        cls.cartorio = Cartorios.objects.create(
            nome='Cartorio 334', cns='334334', cidade='Cidade', estado='TS'
        )
        cls.proprietario = Pessoas.objects.create(nome='Proprietario 334')
        cls.tipo_matricula = DocumentoTipo.objects.create(tipo='matricula')
        cls.tipo_transcricao = DocumentoTipo.objects.create(tipo='transcricao')
        cls.tipo_inicio = LancamentoTipo.objects.create(tipo='inicio_matricula')

        # Imóvel de origem: T50 vive aqui; o PDF do importado fica neste
        # Documento (#297), mesmo o download partindo da cadeia de outro imóvel.
        cls.imovel_origem = Imovel.objects.create(
            terra_indigena_id=cls.tis,
            nome='Fazenda Origem 334',
            proprietario=cls.proprietario,
            matricula='M900',
            cartorio=cls.cartorio,
        )
        cls.doc_origem = Documento.objects.create(
            imovel=cls.imovel_origem,
            tipo=cls.tipo_transcricao,
            numero='T50',
            data=date(2020, 5, 10),
            cartorio=cls.cartorio,
            livro='2',
            folha='5',
        )
        Lancamento.objects.bulk_create([
            Lancamento(
                documento=cls.doc_origem,
                tipo=cls.tipo_inicio,
                data=date(2020, 5, 10),
                cartorio_origem=cls.cartorio,
                origem='',
            ),
        ])

        # Imóvel principal: a matrícula cujo lançamento aponta para T50.
        cls.imovel = Imovel.objects.create(
            terra_indigena_id=cls.tis,
            nome='Fazenda Principal 334',
            proprietario=cls.proprietario,
            matricula='M12345',
            cartorio=cls.cartorio,
        )
        cls.doc_matricula = Documento.objects.create(
            imovel=cls.imovel,
            tipo=cls.tipo_matricula,
            numero='M12345',
            data=date(2024, 1, 1),
            cartorio=cls.cartorio,
            livro='1',
            folha='1',
        )
        Lancamento.objects.bulk_create([
            Lancamento(
                documento=cls.doc_matricula,
                tipo=cls.tipo_inicio,
                data=date(2024, 1, 1),
                cartorio_origem=cls.cartorio,
                origem='T50',
            ),
        ])

        # Segregação (#132): o usuário enxerga os dois imóveis da cadeia.
        UserImovel.objects.create(user=cls.user, imovel=cls.imovel)
        UserImovel.objects.create(user=cls.user, imovel=cls.imovel_origem)

    def setUp(self):
        cache.clear()
        self.client = Client()
        self.client.login(username='user_certidoes', password='testpass123')

    def _url(self):
        return reverse('baixar_certidoes_cadeia', kwargs={
            'tis_id': self.tis.id, 'imovel_id': self.imovel.id,
        })

    def _criar_pdf(self, documento, nome, conteudo=b'%PDF-1.4 conteudo'):
        return DocumentoDigital.objects.create(
            documento=documento,
            arquivo=SimpleUploadedFile(
                nome, conteudo, content_type='application/pdf'
            ),
            nome_original=nome,
            tipo_mime='application/pdf',
            tamanho_bytes=len(conteudo),
            upload_por=self.user,
        )

    def _criar_imagem(self, documento, nome):
        conteudo = b'\x89PNG\r\n\x1a\n' + b'\x00' * 50
        return DocumentoDigital.objects.create(
            documento=documento,
            arquivo=SimpleUploadedFile(
                nome, conteudo, content_type='image/png'
            ),
            nome_original=nome,
            tipo_mime='image/png',
            tamanho_bytes=len(conteudo),
            upload_por=self.user,
        )

    def _criar_registro_fantasma(self, documento, nome, caminho):
        """Registro cujo arquivo não existe no storage (nome fixo no FileField)."""
        return DocumentoDigital.objects.create(
            documento=documento,
            arquivo=caminho,
            nome_original=nome,
            tipo_mime='application/pdf',
            tamanho_bytes=100,
            upload_por=self.user,
        )

    def _zip_bytes(self, response):
        """FileResponse é streaming: junta o conteúdo antes de abrir o ZIP."""
        return io.BytesIO(b''.join(response.streaming_content))

    def _nomes_do_zip(self, response):
        with zipfile.ZipFile(self._zip_bytes(response)) as zipf:
            return zipf.namelist()


class BaixarCertidoesCadeiaTest(_BaseCadeiaCertidoes):
    def test_zip_com_dois_pdfs_na_ordem_da_tela(self):
        """2 PDFs → ZIP com os dois, ordem da cadeia e conteúdo originais."""
        self._criar_pdf(
            self.doc_matricula, 'certidao-matricula.pdf', b'%PDF-1.4 matricula'
        )
        self._criar_pdf(
            self.doc_origem, 'certidao-transcricao.pdf', b'%PDF-1.4 transcricao'
        )

        response = self.client.get(self._url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/zip')
        nome_esperado = (
            f'certidoes_m12345_{timezone.localdate().strftime("%Y%m%d")}.zip'
        )
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn(nome_esperado, response['Content-Disposition'])
        # NN = posição na cadeia: 01 é a matrícula do imóvel, 02 a origem.
        # Resposta streaming: o conteúdo é consumido uma única vez.
        with zipfile.ZipFile(self._zip_bytes(response)) as zipf:
            nomes = zipf.namelist()
            self.assertEqual(nomes, [
                '01_Matricula_M12345_certidao-matricula.pdf',
                '02_Transcricao_T50_certidao-transcricao.pdf',
            ])
            self.assertEqual(
                zipf.read('01_Matricula_M12345_certidao-matricula.pdf'),
                b'%PDF-1.4 matricula',
            )
            self.assertEqual(
                zipf.read('02_Transcricao_T50_certidao-transcricao.pdf'),
                b'%PDF-1.4 transcricao',
            )

    def test_imagem_nao_entra_no_zip(self):
        """Imagens (PNG/JPEG/WebP) ficam fora do ZIP nesta v1."""
        self._criar_imagem(self.doc_matricula, 'scan.png')
        self._criar_pdf(self.doc_matricula, 'certidao.pdf')

        response = self.client.get(self._url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self._nomes_do_zip(response),
            [
                '01_Matricula_M12345_certidao.pdf',
                '02_Transcricao_T50_SEM_PDF.txt',
            ],
        )

    def test_documento_importado_inclui_pdf_do_imovel_de_origem(self):
        """PDF do importado vive no Documento do imóvel de origem (#297)."""
        self._criar_pdf(self.doc_origem, 'certidao-origem.pdf')

        response = self.client.get(self._url())

        self.assertEqual(response.status_code, 200)
        # Só a origem tem PDF, mas cada NN continua sendo a posição do
        # documento na cadeia, não a ordem dos itens coletados.
        self.assertEqual(
            self._nomes_do_zip(response),
            [
                '01_Matricula_M12345_SEM_PDF.txt',
                '02_Transcricao_T50_certidao-origem.pdf',
            ],
        )

    def test_colisao_de_nome_ganha_sufixo(self):
        """Dois PDFs com o mesmo nome no mesmo documento → sufixo _2."""
        self._criar_pdf(self.doc_matricula, 'igual.pdf', b'%PDF-1.4 um')
        self._criar_pdf(self.doc_matricula, 'igual.pdf', b'%PDF-1.4 dois')

        response = self.client.get(self._url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            sorted(self._nomes_do_zip(response)),
            [
                '01_Matricula_M12345_igual.pdf',
                '01_Matricula_M12345_igual_2.pdf',
                '02_Transcricao_T50_SEM_PDF.txt',
            ],
        )

    def test_sem_pdf_em_toda_a_cadeia_vira_marcadores(self):
        """Decisão do dono (21/11): sem PDF em documento nenhum, o ZIP
        traz um marcador `_SEM_PDF.txt` por documento, na ordem da lista."""
        response = self.client.get(self._url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._nomes_do_zip(response), [
            '01_Matricula_M12345_SEM_PDF.txt',
            '02_Transcricao_T50_SEM_PDF.txt',
        ])

    def test_cadeia_sem_documento_redireciona_com_mensagem(self):
        """Só cadeia sem documento nenhum volta com MENSAGEM_SEM_PDF."""
        imovel_vazio = Imovel.objects.create(
            terra_indigena_id=self.tis,
            nome='Fazenda Vazia 334',
            proprietario=self.proprietario,
            matricula='M777',
            cartorio=self.cartorio,
        )
        UserImovel.objects.create(user=self.user, imovel=imovel_vazio)
        url = reverse('baixar_certidoes_cadeia', kwargs={
            'tis_id': self.tis.id, 'imovel_id': imovel_vazio.id,
        })

        response = self.client.get(url)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse('tronco_principal', kwargs={
                'tis_id': self.tis.id, 'imovel_id': imovel_vazio.id,
            }),
        )
        seguida = self.client.get(response.url)
        self.assertContains(
            seguida, 'Nenhum PDF anexado aos documentos desta cadeia.'
        )

    def test_arquivo_ausente_no_storage_vira_marcador_e_conclui(self):
        """Registro sem arquivo físico: marcador no lugar + warning no log."""
        self._criar_pdf(self.doc_matricula, 'real.pdf', b'%PDF-1.4 real')
        fantasma = self._criar_registro_fantasma(
            self.doc_matricula,
            'fantasma.pdf',
            'documentos_digitais/2024/01/fantasma.pdf',
        )

        with self.assertLogs(
            'dominial.views.certidoes_views', level='WARNING'
        ) as logs:
            response = self.client.get(self._url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._nomes_do_zip(response), [
            '01_Matricula_M12345_fantasma.pdf_INDISPONIVEL.txt',
            '01_Matricula_M12345_real.pdf',
            '02_Transcricao_T50_SEM_PDF.txt',
        ])
        self.assertTrue(
            any(str(fantasma.id) in log for log in logs.output),
            logs.output,
        )

    def test_documento_fora_do_escopo_nao_entra_no_zip(self):
        """Documento fora do escopo do usuário (#132) não entra no ZIP.

        Com atribuição só ao imóvel principal, o escopo do usuário não
        alcança a origem T50 — o ZIP só tem a matrícula (como marcador,
        pois ela não tem PDF visível).
        """
        self._criar_pdf(self.doc_origem, 'certidao-origem.pdf')
        UserImovel.objects.create(
            user=self.outro_user, imovel=self.imovel
        )
        self.client.login(username='outro_certidoes', password='testpass123')

        response = self.client.get(self._url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self._nomes_do_zip(response),
            ['01_Matricula_M12345_SEM_PDF.txt'],
        )

    def test_usuario_sem_acesso_recebe_404(self):
        """Segregação: usuário sem o imóvel atribuído recebe 404."""
        self._criar_pdf(self.doc_matricula, 'certidao.pdf')
        self.client.login(username='outro_certidoes', password='testpass123')

        response = self.client.get(self._url())

        self.assertEqual(response.status_code, 404)


class BotaoBaixarCertidoesTest(_BaseCadeiaCertidoes):
    """O botão não depende de PDF (dono 21/11); href não leva ``?escolhas``."""

    def _url_cadeia(self):
        return reverse('tronco_principal', kwargs={
            'tis_id': self.tis.id, 'imovel_id': self.imovel.id,
        })

    def test_botao_aparece_quando_ha_pdf(self):
        self._criar_pdf(self.doc_matricula, 'certidao.pdf')

        response = self.client.get(self._url_cadeia())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Baixar certidões')
        self.assertContains(response, self._url())

    def test_botao_fica_mesmo_sem_pdf_e_href_sem_escolhas(self):
        """(g) sempre visível com lançamentos; ZIP não segue ``?escolhas``."""
        response = self.client.get(self._url_cadeia())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Baixar certidões')
        self.assertContains(response, 'certidoes.zip/')
        self.assertNotContains(response, 'certidoes.zip/?escolhas')
