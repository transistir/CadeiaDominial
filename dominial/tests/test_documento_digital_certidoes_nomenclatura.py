"""Nomenclatura dos arquivos dentro do ZIP (#334 — dono, 21/11/2026).

Formato `<numero>_<CRI|OUTRO>-<Cidade>-<UF>.<ext>` — sem NN e sem o tipo
do documento. Desambiguação quando há mais de um cartório do mesmo tipo
na cidade/UF: ordinal do `nome` (`1º` → `CRI1`), senão cns no fim; sem
cartório → `SEM_CARTORIO`; cidade/UF nulos são omitidos (nunca `--`).
Marcadores usam a mesma raiz; colisão de raiz ganha `_2`, `_3`. Módulo
próprio: os dois testes irmãos já roçam o teto de 400 linhas.
"""

from unittest import mock

from django.db import connection
from django.test.utils import CaptureQueriesContext

from dominial.models import Cartorios, Documento, Lancamento
from dominial.tests.test_documento_digital_certidoes import (
    RAIZ_M12345,
    RAIZ_T50,
    _BaseCadeiaCertidoes,
)


class NomenclaturaSimplesTest(_BaseCadeiaCertidoes):
    """(a) caso simples: `<numero>_<tipo>-<cidade>-<uf>.<ext original>`."""

    def _mover_cartorio(self, **campos):
        """Ajusta o cartório da base via `.update()` (revertido no fim)."""
        Cartorios.objects.filter(pk=self.cartorio.pk).update(**campos)

    def test_caso_simples_com_a_extensao_do_original(self):
        """PDF `Scan.PDF` → `M12345_CRI-Cuiaba-MT.PDF`; marcador na origem."""
        self._mover_cartorio(cidade='Cuiaba', estado='MT')
        self._criar_pdf(self.doc_matricula, 'Scan.PDF', b'%PDF-1.4 m')

        response = self.client.get(self._url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._nomes_do_zip(response), [
            'M12345_CRI-Cuiaba-MT.PDF',
            'T50_CRI-Cuiaba-MT_SEM_PDF.txt',
        ])

    def test_tipo_outro_e_original_sem_extensao(self):
        """Cartório OUTRO → `OUTRO-...`; original sem extensão, sem `.`."""
        self._mover_cartorio(tipo='OUTRO', cidade='Cuiaba', estado='MT')
        self._criar_pdf(self.doc_matricula, 'sem-extensao', b'%PDF-1.4 m')

        response = self.client.get(self._url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._nomes_do_zip(response), [
            'M12345_OUTRO-Cuiaba-MT',
            'T50_OUTRO-Cuiaba-MT_SEM_PDF.txt',
        ])

    def test_cidade_e_uf_nulos_sao_omitidos(self):
        """Sem cidade/UF não sobra traço nenhum: `M12345_CRI.pdf`."""
        self._mover_cartorio(cidade=None, estado=None)
        self._criar_pdf(self.doc_matricula, 'm.pdf', b'%PDF-1.4 m')

        response = self.client.get(self._url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._nomes_do_zip(response), [
            'M12345_CRI.pdf',
            'T50_CRI_SEM_PDF.txt',
        ])


class DesambiguacaoCartorioTest(_BaseCadeiaCertidoes):
    """(b)/(c) mais de um cartório do mesmo tipo na mesma cidade/UF."""

    def _criar_par(self, meu_nome, outro_nome, **campos):
        """Cartório da base + um concorrente; a T50 aponta pro concorrente.

        `campos` (cidade, estado...) vale para os DOIS — quem não os
        herdar fica com os valores da base. O lançamento da matrícula
        também passa a citar o concorrente: a origem T50 só resolve pela
        identidade completa (tipo, número, cartório do lançamento).
        `.update()` não dispara signal e o TestCase reverte tudo.
        """
        Cartorios.objects.filter(pk=self.cartorio.pk).update(
            nome=meu_nome, **campos
        )
        outro = Cartorios.objects.create(
            nome=outro_nome, cns='222222', **campos
        )
        Documento.objects.filter(pk=self.doc_origem.pk).update(cartorio=outro)
        Lancamento.objects.filter(documento=self.doc_matricula).update(
            cartorio_origem=outro
        )

    def test_dois_cartorios_do_mesmo_tipo_usam_ordinal_do_nome(self):
        """(b) `1ª`/`2º` no nome → `CRI1`/`CRI2` na sigla."""
        self._criar_par(
            '1ª Serventia de Registro de Imóveis',
            '2º Ofício de Registro de Imóveis',
            cidade='Cuiaba', estado='MT',
        )
        self._criar_pdf(self.doc_matricula, 'm.pdf', b'%PDF-1.4 m')
        self._criar_pdf(self.doc_origem, 't.pdf', b'%PDF-1.4 t')

        response = self.client.get(self._url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._nomes_do_zip(response), [
            'M12345_CRI1-Cuiaba-MT.pdf',
            'T50_CRI2-Cuiaba-MT.pdf',
        ])

    def test_sem_ordinal_no_nome_usa_o_cns(self):
        """(c) nomes sem ordinal → cns desambigua no fim: `...-MT-<cns>`."""
        self._criar_par(
            'Registro de Imóveis Sudoeste',
            'Registro de Imóveis Paralelo',
            cidade='Cuiaba', estado='MT',
        )
        self._criar_pdf(self.doc_matricula, 'm.pdf', b'%PDF-1.4 m')
        self._criar_pdf(self.doc_origem, 't.pdf', b'%PDF-1.4 t')

        response = self.client.get(self._url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._nomes_do_zip(response), [
            'M12345_CRI-Cuiaba-MT-334334.pdf',
            'T50_CRI-Cuiaba-MT-222222.pdf',
        ])

    def test_sem_cidade_a_desambiguacao_vai_direto_no_tipo(self):
        """Sem cidade/UF o cns cola no tipo: `CRI-<cns>` (nunca `CRI--`)."""
        self._criar_par(
            'Registro de Imóveis Sudoeste',
            'Registro de Imóveis Paralelo',
            cidade=None, estado=None,
        )
        self._criar_pdf(self.doc_matricula, 'm.pdf', b'%PDF-1.4 m')
        self._criar_pdf(self.doc_origem, 't.pdf', b'%PDF-1.4 t')

        response = self.client.get(self._url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._nomes_do_zip(response), [
            'M12345_CRI-334334.pdf',
            'T50_CRI-222222.pdf',
        ])


class CasosEspeciaisDaRaizTest(_BaseCadeiaCertidoes):
    """(d) sem cartório; (e)/(f) marcadores e colisão na nova raiz."""

    def test_documento_sem_cartorio_vira_sem_cartorio(self):
        """(d) documento sem cartório → `M12345_SEM_CARTORIO.pdf`.

        A FK `cartorio` é NOT NULL desde a 0004: linha sem cartório não
        nasce hoje, então o teste substitui o descritor por um cartório
        sem segmento nenhum (tipo/cns vazios — os defaults viriam 'CRI').
        Ramo defensivo para dado legado; a árvore lê `nome=''` sem estourar.
        """
        self._criar_pdf(self.doc_matricula, 'm.pdf', b'%PDF-1.4 m')
        vazio = Cartorios(tipo='', nome='', cns='')
        with mock.patch.object(
            Documento, 'cartorio', property(lambda self: vazio)
        ):
            response = self.client.get(self._url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._nomes_do_zip(response), [
            'M12345_SEM_CARTORIO.pdf',
            'T50_SEM_CARTORIO_SEM_PDF.txt',
        ])

    def test_dois_fantasmas_da_mesma_raiz_ganham_sufixo(self):
        """(e) marcador INDISPONIVEL na nova raiz; segundo vira `_2`."""
        self._criar_registro_fantasma(
            self.doc_matricula, 'a.pdf', 'documentos_digitais/2024/01/a.pdf',
        )
        self._criar_registro_fantasma(
            self.doc_matricula, 'b.pdf', 'documentos_digitais/2024/01/b.pdf',
        )

        with self.assertLogs(
            'dominial.views.certidoes_views', level='WARNING'
        ):
            response = self.client.get(self._url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._nomes_do_zip(response), [
            f'{RAIZ_M12345}_INDISPONIVEL.txt',
            f'{RAIZ_M12345}_INDISPONIVEL_2.txt',
            f'{RAIZ_T50}_SEM_PDF.txt',
        ])

    def test_pdf_e_fantasma_de_mesmo_documento_nao_colidem(self):
        """(f) `usados` é um conjunto só: o PDF fica com o nome limpo e o
        registro sumido vira `_INDISPONIVEL.txt` — nada se sobrescreve."""
        self._criar_pdf(self.doc_matricula, 'm.pdf', b'%PDF-1.4 m')
        self._criar_registro_fantasma(
            self.doc_matricula, 'm.pdf', 'documentos_digitais/2024/01/m.pdf',
        )

        with self.assertLogs(
            'dominial.views.certidoes_views', level='WARNING'
        ):
            response = self.client.get(self._url())

        self.assertEqual(response.status_code, 200)
        # `sorted`: a ordem dos arquivos DENTRO do documento é do modelo,
        # não da nomenclatura — o que importa é o conjunto de nomes.
        self.assertEqual(sorted(self._nomes_do_zip(response)), [
            f'{RAIZ_M12345}.pdf',
            f'{RAIZ_M12345}_INDISPONIVEL.txt',
            f'{RAIZ_T50}_SEM_PDF.txt',
        ])


class CacheDeAmbiguidadeTest(_BaseCadeiaCertidoes):
    """A pergunta "há concorrente?" custa 1 query por combinação."""

    def test_uma_contagem_de_concorrentes_por_combinacao(self):
        """Dois documentos do MESMO cartório → uma única COUNT na tabela."""
        Cartorios.objects.filter(pk=self.cartorio.pk).update(
            cidade='Cuiaba', estado='MT'
        )
        self._criar_pdf(self.doc_matricula, 'm.pdf', b'%PDF-1.4 m')
        self._criar_pdf(self.doc_origem, 't.pdf', b'%PDF-1.4 t')

        with CaptureQueriesContext(connection) as captura:
            response = self.client.get(self._url())

        self.assertEqual(response.status_code, 200)
        contagens = [
            consulta['sql'] for consulta in captura.captured_queries
            if 'dominial_cartorios' in consulta['sql'] and 'COUNT' in consulta['sql']
        ]
        self.assertEqual(len(contagens), 1, contagens)
