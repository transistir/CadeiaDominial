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

import zipfile
from datetime import date, timedelta
from unittest import mock

from django.db.models.fields.files import FieldFile
from django.urls import reverse
from django.utils import timezone

from dominial.models import Documento, DocumentoDigital, Imovel, UserImovel
from dominial.tests.test_documento_digital_certidoes import (
    RAIZ_M12345,
    RAIZ_T50,
    _BaseCadeiaCertidoes,
)


def _fixar_ordem_de_upload(mais_recente, *anteriores):
    """Distância determinística entre `data_upload` de uploads em teste.

    `auto_now_add` ignora o `data_upload` passado ao create: dois uploads
    criados no mesmo instante EMPATAM em `ordering = ['-data_upload']` e
    a ordem de iteração vira indefinida — quem fica com o nome limpo e
    quem fica com `_2` poderia trocar entre execuções. `update()` bypassa
    o `pre_save` e fixa a ordem: `mais_recente` itera primeiro.
    """
    hora = timezone.now()
    for registro in anteriores:
        DocumentoDigital.objects.filter(pk=registro.pk).update(
            data_upload=hora - timedelta(hours=1)
        )
    DocumentoDigital.objects.filter(pk=mais_recente.pk).update(
        data_upload=hora
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

    def _ilegivel_apenas(self, nome_alvo):
        """`PermissionError` só para `nome_alvo`; todo o resto abre normal.

        Patch com função comum em vez de MagicMock: função é descritor,
        então o FieldFile chega como `self` e o `name` dele distingue o
        alvo — indispensable no caso misto, em que o irmão do mesmo
        documento tem que abrir de verdade. O destino segue sendo a
        CLASSE: a view recarrega os registros com FieldFile próprio.
        """
        original = FieldFile.open

        def abrir_se_legivel(fieldfile, modo='rb'):
            if fieldfile.name == nome_alvo:
                raise PermissionError(f'dono errado: {nome_alvo}')
            return original(fieldfile, modo)

        return mock.patch.object(FieldFile, 'open', new=abrir_se_legivel)

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

    def test_misto_um_legivel_e_um_ilegivel_dividem_a_mesma_posicao(self):
        """Caso misto: o documento entrega o PDF E o marcador, juntos.

        O legível não é refém do ilegível: PDF e `_INDISPONIVEL.txt`
        dividem a mesma posição (a da matrícula), o PDF com o conteúdo
        dele intacto. O ilegível fica com o upload mais recente para
        iterar primeiro (`-data_upload`, fixado pelo helper).
        """
        bom = self._criar_pdf(self.doc_matricula, 'bom.pdf', b'%PDF-1.4 bom')
        ruim = self._criar_pdf(self.doc_matricula, 'ruim.pdf', b'%PDF-1.4 ruim')
        _fixar_ordem_de_upload(ruim, bom)

        with self._ilegivel_apenas(ruim.arquivo.name), self.assertLogs(
            'dominial.views.certidoes_views', level='WARNING'
        ):
            response = self.client.get(self._url())

        self.assertEqual(response.status_code, 200)
        with zipfile.ZipFile(self._zip_bytes(response)) as zipf:
            self.assertEqual(zipf.namelist(), [
                f'{RAIZ_M12345}_INDISPONIVEL.txt',
                f'{RAIZ_M12345}.pdf',
                f'{RAIZ_T50}_SEM_PDF.txt',
            ])
            self.assertEqual(zipf.read(f'{RAIZ_M12345}.pdf'), b'%PDF-1.4 bom')

    def test_verificacao_misto_conta_com_pdf_e_lista_indisponivel(self):
        """O documento misto conta em `com_pdf` E lista o arquivo em
        `indisponiveis` — o modal não esconde nem promete o que falta."""
        bom = self._criar_pdf(self.doc_matricula, 'bom.pdf', b'%PDF-1.4 bom')
        ruim = self._criar_pdf(self.doc_matricula, 'ruim.pdf', b'%PDF-1.4 ruim')
        _fixar_ordem_de_upload(ruim, bom)

        with self._ilegivel_apenas(ruim.arquivo.name):
            response = self.client.get(self._url_verificar())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            'total': 2,
            'com_pdf': 1,
            'sem_pdf': 1,
            'indisponiveis': [{
                'ordem': 1,
                'tipo': 'Matrícula',
                'numero': 'M12345',
                'nome_original': 'ruim.pdf',
            }],
        })


class ColisaoCasefoldTest(_BaseCadeiaCertidoes):
    """MF2: `.pdf` × `.PDF` não podem se sobrescrever na extração."""

    def test_extensoes_que_diferem_somente_na_caixa_ganham_sufixo(self):
        """Segunda entrada no mesmo raiz vira `_2` — caixa não distingue.

        A reserva no `usados` é por ``casefold()``: os dois nomes
        dobrados divergem, então ambos sobrevivem à extração em FS
        case-insensitive (Windows/macOS), e exatamente um termina em
        `_2.pdf`. A ordem entre os dois uploads é fixada pelo helper:
        sem ele, `auto_now_add` pode gravar os dois no mesmo instante e
        o empate em `-data_upload` trocaria quem leva `_2`.
        """
        scan_pdf = self._criar_pdf(
            self.doc_matricula, 'scan.pdf', b'%PDF-1.4 um'
        )
        scan_pdf_maiusculo = self._criar_pdf(
            self.doc_matricula, 'scan.PDF', b'%PDF-1.4 dois'
        )
        _fixar_ordem_de_upload(scan_pdf_maiusculo, scan_pdf)

        response = self.client.get(self._url())

        self.assertEqual(response.status_code, 200)
        nomes = self._nomes_do_zip(response)
        proprios = [
            nome for nome in nomes if nome.startswith(RAIZ_M12345)
        ]
        self.assertIn(f'{RAIZ_T50}_SEM_PDF.txt', nomes)
        self.assertEqual(len(proprios), 2)
        dobrados = {nome.casefold() for nome in proprios}
        self.assertEqual(len(dobrados), 2)
        self.assertEqual(
            dobrados,
            {
                f'{RAIZ_M12345}.pdf'.casefold(),
                f'{RAIZ_M12345}_2.pdf'.casefold(),
            },
        )
        self.assertEqual(
            sum(nome.endswith('_2.pdf') for nome in proprios), 1
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
