"""ZIP "Baixar certidões" — MUST-FIX da revisão do Opus (22/11).

1. MF1: arquivo que existe mas não abre (`PermissionError`, dono errado
   após restore) NÃO pode sumir do ZIP — vira `_INDISPONIVEL.txt` na
   posição dele, e o JSON da verificação o classifica como indisponível,
   para o modal não prometer o que o ZIP não entrega;
2. MF2: nomes que diferem só pela caixa (`.pdf` × `.PDF`) colidem em FS
   case-insensitive (Windows/macOS) — a reserva do `usados` é por
   ``casefold()``; o nome entregue preserva a caixa do original;
3. hardening: `: * ? " < > |` viram `_` — o ZIP é extraído em Windows na
   maioria dos casos.

Em módulo próprio: os irmãos (original e ``correcoes``) já estão no teto
de 400 linhas imposto pelo CI. Cadeia base vem de `_BaseCadeiaCertidoes`.
"""

from datetime import date
from unittest import mock

from django.db.models.fields.files import FieldFile
from django.urls import reverse

from dominial.models import Documento, Imovel, UserImovel
from dominial.tests.test_documento_digital_certidoes import (
    RAIZ_M12345,
    RAIZ_T50,
    _BaseCadeiaCertidoes,
)


class ArquivoIlegivelViraMarcadorTest(_BaseCadeiaCertidoes):
    """MF1: `exists()` true com `open` estourando não pode sumir do ZIP."""

    def _ilegivel(self):
        """Arquivo presente no storage, porém ilegível (dono errado).

        Patch na CLASSE do FieldFile: a view recarrega o registro do
        banco com FieldFile próprio — patch por instância não a alcança.
        """
        return mock.patch.object(
            FieldFile,
            'open',
            side_effect=PermissionError('dono errado após restore'),
        )

    def _url_verificar(self):
        return reverse('baixar_certidoes_cadeia_verificar', kwargs={
            'tis_id': self.tis.id, 'imovel_id': self.imovel.id,
        })

    def test_arquivo_presente_que_nao_abre_vira_marcador_na_posicao(self):
        self._criar_pdf(self.doc_matricula, 'real.pdf', b'%PDF-1.4 real')

        with self._ilegivel(), self.assertLogs(
            'dominial.views.certidoes_views', level='WARNING'
        ):
            response = self.client.get(self._url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._nomes_do_zip(response), [
            f'{RAIZ_M12345}_INDISPONIVEL.txt',
            f'{RAIZ_T50}_SEM_PDF.txt',
        ])

    def test_verificacao_classifica_arquivo_ilegivel_como_indisponivel(self):
        self._criar_pdf(self.doc_matricula, 'real.pdf', b'%PDF-1.4 real')

        with self._ilegivel():
            response = self.client.get(self._url_verificar())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            'total': 2,
            'com_pdf': 0,
            'sem_pdf': 1,
            'indisponiveis': [{
                'ordem': 1,
                'tipo': 'Matrícula',
                'numero': 'M12345',
                'nome_original': 'real.pdf',
            }],
        })


class ColisaoCasefoldTest(_BaseCadeiaCertidoes):
    """MF2: `.pdf` × `.PDF` não podem se sobrescrever na extração."""

    def test_extensoes_que_diferem_somente_na_caixa_ganham_sufixo(self):
        """Segunda entrada no mesmo raiz vira `_2` — caixa não distingue.

        `ordering = ['-data_upload']`: o PDF anexado por último itera
        primeiro e fica com o nome limpo; o `_2` fica no mais antigo.
        """
        self._criar_pdf(self.doc_matricula, 'scan.pdf', b'%PDF-1.4 um')
        self._criar_pdf(self.doc_matricula, 'scan.PDF', b'%PDF-1.4 dois')

        response = self.client.get(self._url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            sorted(self._nomes_do_zip(response)),
            [
                f'{RAIZ_M12345}.PDF',
                f'{RAIZ_M12345}_2.pdf',
                f'{RAIZ_T50}_SEM_PDF.txt',
            ],
        )


class CaracteresProibidosWindowsTest(_BaseCadeiaCertidoes):
    """Hardening: `: * ? " < > |` não sobrevivem em nome dentro do ZIP."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.imovel_windows = Imovel.objects.create(
            terra_indigena_id=cls.tis,
            nome='Imovel Windows 334',
            proprietario=cls.proprietario,
            matricula='M:123/45?',
            cartorio=cls.cartorio,
        )
        cls.doc_windows = Documento.objects.create(
            imovel=cls.imovel_windows,
            tipo=cls.tipo_matricula,
            numero='M:123/45?',
            data=date(2024, 4, 4),
            cartorio=cls.cartorio,
            livro='1',
            folha='4',
        )
        UserImovel.objects.create(user=cls.user, imovel=cls.imovel_windows)

    def _url_de(self, imovel):
        return reverse('baixar_certidoes_cadeia', kwargs={
            'tis_id': self.tis.id, 'imovel_id': imovel.id,
        })

    def test_numero_com_caracteres_proibidos_vira_underline(self):
        """`M:123/45?` → `M_123_45_`: nem `:` nem `?` sobrevivem."""
        self._criar_pdf(self.doc_windows, 'certidao.pdf')

        response = self.client.get(self._url_de(self.imovel_windows))

        self.assertEqual(response.status_code, 200)
        nomes = self._nomes_do_zip(response)
        self.assertEqual(nomes, ['M_123_45__CRI-Cidade-TS.pdf'])
        self.assertFalse(
            any(
                caractere in nome
                for nome in nomes
                for caractere in ':*?"<>|'
            ),
            nomes,
        )
