"""ZIP "Baixar certidões" — MUST-FIX do review e decisões do dono (21/11).

1. ZIP = a MESMA lista do XLSX (fonte `CadeiaCompletaService`, a mesma de
   `exportar_cadeia_dominial_excel`); a escolha de origem da tela NÃO filtra;
2. todo documento entra na posição dele: PDF, `_INDISPONIVEL.txt` (registro
   sumido do storage) ou `_SEM_PDF.txt` (sem registro de PDF);
3. endpoint de verificação (JSON) alimenta o modal de aviso.

Em módulo próprio: `test_documento_digital_certidoes.py` está perto do teto
de 400 linhas imposto pelo CI. A cadeia base vem de `_BaseCadeiaCertidoes`.
"""

import io
import tempfile
import zipfile
from datetime import date
from unittest import mock

from django.urls import reverse

from dominial.models import Documento, Imovel, Lancamento, UserImovel
from dominial.services.cadeia_completa_service import CadeiaCompletaService
from dominial.services.cadeia_dominial_tabela_service import (
    CadeiaDominialTabelaService,
)
from dominial.tests.test_documento_digital_certidoes import (
    RAIZ_M12345,
    RAIZ_T50,
    _BaseCadeiaCertidoes,
)


def _conteudo_do_zip(response):
    """``{nome: bytes}`` de um FileResponse de ZIP (streaming)."""
    with zipfile.ZipFile(io.BytesIO(b''.join(response.streaming_content))) as zipf:
        return {nome: zipf.read(nome) for nome in zipf.namelist()}


# Cadeia homônima com PDF nos três documentos: é a lista que o XLSX traz.
RAIZ_T40 = 'T40_CRI-Cidade-TS'
_NOMES_CADEIA_INTEIRA = [
    f'{RAIZ_M12345}.pdf',
    f'{RAIZ_T50}.pdf',
    f'{RAIZ_T40}.pdf',
]


def _criar_fantasma_padrao(base, documento):
    """Registro de PDF cujo arquivo sumiu do storage (caminho fixo)."""
    return base._criar_registro_fantasma(
        documento, 'fantasma.pdf', 'documentos_digitais/2024/01/fantasma.pdf',
    )


def _cadeia_com_dois_homonimos(cls):
    """M12345 passa a citar duas origens reais (T50 e T40).

    T40 vive no imóvel de origem, ao lado de T50. Sem escolha, a TABELA
    segue T50 (padrão: maior número) — o ZIP traz os dois.
    """
    cls.doc_t40 = Documento.objects.create(
        imovel=cls.imovel_origem,
        tipo=cls.tipo_transcricao,
        numero='T40',
        data=date(2019, 3, 3),
        cartorio=cls.cartorio,
        livro='2',
        folha='4',
    )
    Lancamento.objects.bulk_create([
        Lancamento(
            documento=cls.doc_t40,
            tipo=cls.tipo_inicio,
            data=date(2019, 3, 3),
            cartorio_origem=cls.cartorio,
            origem='',
        ),
    ])
    # `.update()` não dispara signal de origens estruturadas: a leitura
    # fica no fallback textual, com o cartório do próprio lançamento.
    Lancamento.objects.filter(documento=cls.doc_matricula).update(
        origem='T50; T40'
    )


class CadeiaInteiraNoZipTest(_BaseCadeiaCertidoes):
    """Decisões do dono 1–2: o ZIP é a mesma lista do XLSX, sem filtro."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        _cadeia_com_dois_homonimos(cls)

    def test_zip_e_a_mesma_lista_do_xlsx(self):
        """(a) PDFs nos três → ZIP com os três, na ordem da lista do XLSX."""
        self._criar_pdf(self.doc_matricula, 'pdf-m.pdf', b'%PDF-1.4 m')
        self._criar_pdf(self.doc_origem, 'pdf-t50.pdf', b'%PDF-1.4 t50')
        self._criar_pdf(self.doc_t40, 'pdf-t40.pdf', b'%PDF-1.4 t40')

        cadeia = CadeiaCompletaService(user=self.user).get_cadeia_completa(
            self.tis.id, self.imovel.id
        )['cadeia_completa']
        ordem_xlsx = [
            item['documento'].numero
            for tronco in cadeia
            for item in tronco['documentos']
        ]

        response = self.client.get(self._url())

        self.assertEqual(response.status_code, 200)
        # NN = posição na MESMA lista que o XLSX renderiza:
        self.assertEqual(ordem_xlsx, ['M12345', 'T50', 'T40'])
        self.assertEqual(self._nomes_do_zip(response), _NOMES_CADEIA_INTEIRA)

    def test_sessao_com_escolha_de_origem_nao_filtra_o_zip(self):
        """(b) sessão presa em T40: a tabela mostra 2; o ZIP traz 3."""
        self._criar_pdf(self.doc_matricula, 'pdf-m.pdf', b'%PDF-1.4 m')
        self._criar_pdf(self.doc_origem, 'pdf-t50.pdf', b'%PDF-1.4 t50')
        self._criar_pdf(self.doc_t40, 'pdf-t40.pdf', b'%PDF-1.4 t40')

        session = self.client.session
        session[f'origem_documento_{self.doc_matricula.id}'] = 'T40'
        session.save()
        tabela = CadeiaDominialTabelaService(user=self.user)
        linhas = tabela.get_cadeia_dominial_tabela(
            self.tis.id, self.imovel.id, self.client.session
        )['cadeia']
        self.assertEqual(
            [item['documento'].numero for item in linhas], ['M12345', 'T40']
        )

        response = self.client.get(self._url())

        # O ZIP não segue a escolha da sessão: lista inteira do XLSX.
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._nomes_do_zip(response), _NOMES_CADEIA_INTEIRA)

    def test_todo_documento_da_cadeia_tem_entrada_no_zip(self):
        """(e) PDF + indisponível + sem PDF: 3 documentos → 3 entradas."""
        self._criar_pdf(self.doc_matricula, 'real.pdf', b'%PDF-1.4 real')
        _criar_fantasma_padrao(self, self.doc_origem)

        with self.assertLogs(
            'dominial.views.certidoes_views', level='WARNING'
        ):
            response = self.client.get(self._url())

        self.assertEqual(self._nomes_do_zip(response), [
            f'{RAIZ_M12345}.pdf',
            f'{RAIZ_T50}_INDISPONIVEL.txt',
            f'{RAIZ_T40}_SEM_PDF.txt',
        ])


class MarcadoresNoZipTest(_BaseCadeiaCertidoes):
    """Decisão do dono 2: marcadores explicam o caso, na posição certa."""

    def test_arquivo_indisponivel_vira_marcador_na_posicao(self):
        """(c) registro sumido do storage → `_INDISPONIVEL.txt` + texto."""
        self._criar_pdf(self.doc_matricula, 'real.pdf', b'%PDF-1.4 real')
        _criar_fantasma_padrao(self, self.doc_origem)

        with self.assertLogs(
            'dominial.views.certidoes_views', level='WARNING'
        ):
            response = self.client.get(self._url())

        self.assertEqual(response.status_code, 200)
        conteudo = _conteudo_do_zip(response)
        nome = f'{RAIZ_T50}_INDISPONIVEL.txt'
        self.assertEqual(list(conteudo), [f'{RAIZ_M12345}.pdf', nome])
        texto = conteudo[nome].decode()
        self.assertIn('Transcrição T50', texto)
        self.assertIn('fantasma.pdf', texto)
        self.assertIn('armazenamento', texto)

    def test_documento_sem_pdf_vira_marcador_na_posicao(self):
        """(d) documento sem registro de PDF → `_SEM_PDF.txt` + texto."""
        self._criar_pdf(self.doc_matricula, 'real.pdf', b'%PDF-1.4 real')

        response = self.client.get(self._url())

        self.assertEqual(response.status_code, 200)
        conteudo = _conteudo_do_zip(response)
        self.assertEqual(list(conteudo), [
            f'{RAIZ_M12345}.pdf',
            f'{RAIZ_T50}_SEM_PDF.txt',
        ])
        texto = conteudo[f'{RAIZ_T50}_SEM_PDF.txt'].decode()
        self.assertIn('Transcrição T50', texto)
        self.assertIn('nenhum PDF', texto)

    def test_somente_fantasma_vira_marcador_e_zip_e_entregue(self):
        """MF4 (dono 21/11): só fantasma não redireciona — vira marcador."""
        _criar_fantasma_padrao(self, self.doc_matricula)

        with self.assertLogs(
            'dominial.views.certidoes_views', level='WARNING'
        ):
            response = self.client.get(self._url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(_conteudo_do_zip(response)), [
            f'{RAIZ_M12345}_INDISPONIVEL.txt',
            f'{RAIZ_T50}_SEM_PDF.txt',
        ])


class VerificacaoAntesDeBaixarTest(_BaseCadeiaCertidoes):
    """Decisão do dono 3: JSON que alimenta o modal de aviso."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        _cadeia_com_dois_homonimos(cls)

    def _url_verificar(self):
        return reverse('baixar_certidoes_cadeia_verificar', kwargs={
            'tis_id': self.tis.id, 'imovel_id': self.imovel.id,
        })

    def test_verificacao_devolve_resumo_com_indisponiveis(self):
        """(f) total, com_pdf, sem_pdf e a lista de indisponíveis."""
        self._criar_pdf(self.doc_matricula, 'real.pdf', b'%PDF-1.4 real')
        _criar_fantasma_padrao(self, self.doc_origem)

        response = self.client.get(self._url_verificar())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            'total': 3,
            'com_pdf': 1,
            'sem_pdf': 1,
            'indisponiveis': [{
                'ordem': 2,
                'tipo': 'Transcrição',
                'numero': 'T50',
                'nome_original': 'fantasma.pdf',
            }],
        })

    def test_verificacao_sem_perdas_nao_lista_nada(self):
        """Tudo disponível: com_pdf = total, sem_pdf 0, lista vazia."""
        self._criar_pdf(self.doc_matricula, 'pdf-m.pdf', b'%PDF-1.4 m')
        self._criar_pdf(self.doc_origem, 'pdf-t50.pdf', b'%PDF-1.4 t50')
        self._criar_pdf(self.doc_t40, 'pdf-t40.pdf', b'%PDF-1.4 t40')

        response = self.client.get(self._url_verificar())

        self.assertEqual(response.json(), {
            'total': 3,
            'com_pdf': 3,
            'sem_pdf': 0,
            'indisponiveis': [],
        })

    def test_usuario_sem_acesso_recebe_404_no_zip_e_na_verificacao(self):
        """(h) segregação (#132) vale para os dois endpoints."""
        self._criar_pdf(self.doc_matricula, 'certidao.pdf')
        self.client.login(username='outro_certidoes', password='testpass123')

        self.assertEqual(self.client.get(self._url()).status_code, 404)
        self.assertEqual(self.client.get(self._url_verificar()).status_code, 404)


class SanitizacaoDoNumeroNoZipTest(_BaseCadeiaCertidoes):
    """MF2: o número do documento não pode virar caminho dentro do ZIP."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.imovel_barra = Imovel.objects.create(
            terra_indigena_id=cls.tis,
            nome='Imovel Barra 334',
            proprietario=cls.proprietario,
            matricula='M123/45',
            cartorio=cls.cartorio,
        )
        cls.doc_barra = Documento.objects.create(
            imovel=cls.imovel_barra,
            tipo=cls.tipo_matricula,
            numero='M123/45',
            data=date(2024, 2, 2),
            cartorio=cls.cartorio,
            livro='1',
            folha='2',
        )
        UserImovel.objects.create(user=cls.user, imovel=cls.imovel_barra)
        cls.imovel_pontos = Imovel.objects.create(
            terra_indigena_id=cls.tis,
            nome='Imovel Pontos 334',
            proprietario=cls.proprietario,
            matricula='../evil',
            cartorio=cls.cartorio,
        )
        cls.doc_pontos = Documento.objects.create(
            imovel=cls.imovel_pontos,
            tipo=cls.tipo_matricula,
            numero='../evil',
            data=date(2024, 3, 3),
            cartorio=cls.cartorio,
            livro='1',
            folha='3',
        )
        UserImovel.objects.create(user=cls.user, imovel=cls.imovel_pontos)

    def _url_de(self, imovel):
        return reverse('baixar_certidoes_cadeia', kwargs={
            'tis_id': self.tis.id, 'imovel_id': imovel.id,
        })

    def test_numero_com_barra_nao_cria_subpasta(self):
        """`M123/45` vira `M123_45`: nome plano, sem separador de caminho."""
        self._criar_pdf(self.doc_barra, 'certidao.pdf')

        response = self.client.get(self._url_de(self.imovel_barra))

        self.assertEqual(response.status_code, 200)
        nomes = self._nomes_do_zip(response)
        self.assertEqual(nomes, ['M123_45_CRI-Cidade-TS.pdf'])

    def test_numero_com_pontos_nao_sobe_de_nivel(self):
        """`../evil` não sobra `..` nem `/` no nome dentro do ZIP."""
        self._criar_pdf(self.doc_pontos, 'certidao.pdf')

        response = self.client.get(self._url_de(self.imovel_pontos))

        self.assertEqual(response.status_code, 200)
        nomes = self._nomes_do_zip(response)
        self.assertEqual(len(nomes), 1, nomes)
        self.assertFalse(
            any('/' in nome or '\\' in nome or '..' in nome for nome in nomes),
            nomes,
        )
        # `../evil` → `__evil`: os dois pontos viram `_` e o `/` também.
        self.assertEqual(nomes, ['__evil_CRI-Cidade-TS.pdf'])


class FalhaDuranteACopiaTest(_BaseCadeiaCertidoes):
    """MF3: OSError na cópia não pode virar ZIP truncado com 200."""

    def test_falha_na_copia_nao_entrega_zip_truncado(self):
        self._criar_pdf(self.doc_matricula, 'quebra.pdf', b'%PDF-1.4 real')

        with (
            mock.patch(
                'dominial.views.certidoes_views.shutil.copyfileobj',
                side_effect=OSError('falha de leitura durante a cópia'),
            ),
            self.assertLogs(
                'dominial.views.certidoes_views', level='ERROR'
            ) as logs,
        ):
            response = self.client.get(self._url())

        self.assertEqual(response.status_code, 302)
        self.assertNotIn('application/zip', response.get('Content-Type', ''))
        self.assertEqual(
            response.url,
            reverse('tronco_principal', kwargs={
                'tis_id': self.tis.id, 'imovel_id': self.imovel.id,
            }),
        )
        self.assertTrue(
            any('certidões' in log for log in logs.output), logs.output
        )
        # A mensagem de erro chega na cadeia — sem JSON/ZIP parcial:
        seguida = self.client.get(response.url)
        self.assertContains(seguida, 'Erro ao gerar o ZIP')


class SpoolFechadoEmErroTest(_BaseCadeiaCertidoes):
    """MF5: o spool fecha em qualquer caminho de exceção."""

    def test_spool_fechado_quando_a_resposta_falha(self):
        self._criar_pdf(self.doc_matricula, 'certidao.pdf')
        criados = []
        spool_real = tempfile.SpooledTemporaryFile

        def _spool_espiao(*args, **kwargs):
            criados.append(spool_real(*args, **kwargs))
            return criados[-1]

        with (
            mock.patch(
                'dominial.views.certidoes_views.tempfile.SpooledTemporaryFile',
                side_effect=_spool_espiao,
            ),
            mock.patch(
                'dominial.views.certidoes_views.FileResponse',
                side_effect=RuntimeError('falha na construção da resposta'),
            ),
            self.assertLogs('dominial.views.certidoes_views', level='ERROR'),
        ):
            response = self.client.get(self._url())

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(criados), 1, criados)
        self.assertTrue(criados[0].closed)
