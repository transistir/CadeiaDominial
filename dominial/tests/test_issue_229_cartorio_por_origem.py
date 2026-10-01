"""
Issue #229 — cartório por origem na tabela/API/XLSX.

Bug: `formatar_origem_completa` anexava o cartório único legado
(`lancamento.cartorio_origem`) a TODAS as partes do texto `lancamento.origem`,
ignorando as linhas `LancamentoOrigem` que guardam cartório por posição desde
o #144 fase 2. Caso real: lançamento 8374 — T100 Iguatemi, T99 Navirai; antes
da correção ambas saíam "Iguatemi".
"""

from types import SimpleNamespace

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape

from dominial.models import (
    Cartorios,
    Documento,
    DocumentoTipo,
    Imovel,
    Lancamento,
    LancamentoOrigem,
    LancamentoTipo,
    Pessoas,
    TIs,
)
from openpyxl import Workbook

from dominial.services.cadeia_completa_service import CadeiaCompletaService
from dominial.services.exportacao_excel_service import escrever_secao_documentos
from dominial.services.cadeia_dominial_tabela_service import CadeiaDominialTabelaService
from dominial.services.lancamento_origem_leitura_service import (
    LancamentoOrigemLeituraService,
)
from dominial.services.lancamento_origem_service import LancamentoOrigemService
from dominial.templatetags.dominial_extras import origem_formatada_completa
from dominial.utils.formatacao_utils import formatar_origem_completa


class _Fixture229:
    """Mixin de fixture para os testes da issue #229.

    Não herda de TestCase para não ser coletado como um caso de teste vazio.
    Classes filhas devem herdar de (_Fixture229, TestCase).
    """

    def setUp(self):
        super().setUp()
        self.tis = TIs.objects.create(nome='TI 229', codigo='TI-229', etnia='Teste')
        self.proprietario = Pessoas.objects.create(nome='Proprietario 229')
        self.cartorio_iguatemi = Cartorios.objects.create(
            nome='Registro de Imóveis de Iguatemi',
            cns='229001', cidade='Iguatemi', estado='MS',
        )
        self.cartorio_navirai = Cartorios.objects.create(
            nome='Registro de Imóveis de Navirai',
            cns='229002', cidade='Navirai', estado='MS',
        )
        self.tipo_matricula = DocumentoTipo.objects.create(tipo='matricula')
        self.tipo_transcricao = DocumentoTipo.objects.create(tipo='transcricao')
        self.tipo_inicio = LancamentoTipo.objects.create(tipo='inicio_matricula')

        self.imovel = Imovel.objects.create(
            terra_indigena_id=self.tis,
            nome='Imóvel 229',
            proprietario=self.proprietario,
            matricula='M8374',
            tipo_documento_principal='matricula',
            cartorio=self.cartorio_iguatemi,
        )
        self.documento = Documento.objects.create(
            imovel=self.imovel,
            tipo=self.tipo_matricula,
            numero='M8374',
            data=timezone.now().date(),
            cartorio=self.cartorio_iguatemi,
        )

    def _criar_lancamento(self, origem, cartorio_origem=None):
        lancamento = Lancamento(
            documento=self.documento,
            tipo=self.tipo_inicio,
            data=timezone.now().date(),
            origem=origem,
            cartorio_origem=cartorio_origem,
        )
        Lancamento.objects.bulk_create([lancamento])
        return Lancamento.objects.get(pk=lancamento.pk)

    @staticmethod
    def _criar_linha(lancamento, indice_origem, tipo_documento, numero, cartorio):
        return LancamentoOrigem.objects.create(
            lancamento=lancamento,
            indice_origem=indice_origem,
            tipo_documento=tipo_documento,
            numero=numero,
            cartorio=cartorio,
        )


class ResolverLinhaPorPosicaoTest(SimpleTestCase):
    """Lógica pura de `resolver_linha_por_posicao`, sem tocar o banco."""

    @staticmethod
    def _linha(indice_origem, tipo_documento, numero_normalizado, cartorio=None):
        return SimpleNamespace(
            indice_origem=indice_origem,
            tipo_documento=tipo_documento,
            numero_normalizado=numero_normalizado,
            cartorio=cartorio,
        )

    def test_posicao_e_identidade_casam(self):
        linha_t100 = self._linha(0, 'transcricao', '100')
        linha_t99 = self._linha(1, 'transcricao', '99')
        linhas = [linha_t100, linha_t99]

        resultado = LancamentoOrigemService.resolver_linha_por_posicao(
            linhas, 'T99', 1, ['T100', 'T99']
        )

        self.assertEqual(resultado, (linha_t99, False, False))

    def test_homonimo_no_texto_sem_linha_na_posicao_e_ambiguo(self):
        linha_t366_pos1 = self._linha(1, 'transcricao', '366')
        linhas = [linha_t366_pos1]

        resultado = LancamentoOrigemService.resolver_linha_por_posicao(
            linhas, 'T366', 0, ['T366', 'T366']
        )

        self.assertEqual(resultado, (None, True, False))

    def test_duas_linhas_mesma_chave_texto_nao_homonimo_e_ambiguo_registrada(self):
        # F2-21: o texto não é homônimo (só uma origem "T366" no conjunto
        # atual), mas o banco tem 2 linhas com a mesma chave — ambiguidade
        # registrada, não a mesma coisa que homônimo no texto.
        linha_a = self._linha(5, 'transcricao', '366')
        linha_b = self._linha(6, 'transcricao', '366')
        linhas = [linha_a, linha_b]

        resultado = LancamentoOrigemService.resolver_linha_por_posicao(
            linhas, 'T366', 0, ['T366']
        )

        self.assertEqual(resultado, (None, True, True))

    def test_texto_sem_chave_nao_resolve(self):
        linhas = [self._linha(0, 'transcricao', '100')]

        resultado = LancamentoOrigemService.resolver_linha_por_posicao(
            linhas, 'Escritura particular', 0, ['Escritura particular']
        )

        self.assertEqual(resultado, (None, False, False))

    def test_fallback_por_identidade_com_candidato_unico(self):
        # Índices reordenados: a linha está na posição 3, mas o texto está na
        # posição 0 do conjunto atual. Regra 3 positiva: exatamente 1
        # candidato por identidade resolve, mesmo sem casar a posição.
        linha_t100 = self._linha(3, 'transcricao', '100')
        linhas = [linha_t100]

        resultado = LancamentoOrigemService.resolver_linha_por_posicao(
            linhas, 'T100', 0, ['T100']
        )

        self.assertEqual(resultado, (linha_t100, False, False))


class FormatarOrigemCompletaPorOrigemTest(_Fixture229, TestCase):
    def test_multiplas_origens_exibem_cartorio_de_cada_linha(self):
        lancamento = self._criar_lancamento('T100; T99', self.cartorio_iguatemi)
        self._criar_linha(lancamento, 0, 'transcricao', 'T100', self.cartorio_iguatemi)
        self._criar_linha(lancamento, 1, 'transcricao', 'T99', self.cartorio_navirai)

        resultado = formatar_origem_completa(lancamento)

        self.assertEqual(
            resultado,
            'T100 (Registro de Imóveis de Iguatemi)\n'
            'T99 (Registro de Imóveis de Navirai)',
        )

    def test_filtro_template_usa_br_escapa_e_cartorio_por_origem(self):
        lancamento = self._criar_lancamento('T100; T99', self.cartorio_iguatemi)
        self._criar_linha(lancamento, 0, 'transcricao', 'T100', self.cartorio_iguatemi)
        self._criar_linha(lancamento, 1, 'transcricao', 'T99', self.cartorio_navirai)

        resultado = origem_formatada_completa(lancamento)

        self.assertEqual(
            str(resultado),
            'T100 (Registro de Imóveis de Iguatemi)<br>'
            'T99 (Registro de Imóveis de Navirai)',
        )

    def test_fim_de_cadeia_antes_desloca_indice(self):
        lancamento = self._criar_lancamento(
            'Destacamento Público:INCRA:Origem Lídima; T100; T99',
            self.cartorio_iguatemi,
        )
        self._criar_linha(lancamento, 1, 'transcricao', 'T100', self.cartorio_iguatemi)
        self._criar_linha(lancamento, 2, 'transcricao', 'T99', self.cartorio_navirai)

        resultado = formatar_origem_completa(lancamento)

        self.assertEqual(
            resultado,
            'Destacamento Público : INCRA (Origem Lídima)\n'
            'T100 (Registro de Imóveis de Iguatemi)\n'
            'T99 (Registro de Imóveis de Navirai)',
        )

    def test_fim_de_cadeia_no_meio(self):
        lancamento = self._criar_lancamento(
            'T100; Sem Origem::sem_origem; T99', self.cartorio_iguatemi
        )
        self._criar_linha(lancamento, 0, 'transcricao', 'T100', self.cartorio_iguatemi)
        self._criar_linha(lancamento, 2, 'transcricao', 'T99', self.cartorio_navirai)

        resultado = formatar_origem_completa(lancamento)

        self.assertEqual(
            resultado,
            'T100 (Registro de Imóveis de Iguatemi)\n'
            'Sem Origem (Sem Origem)\n'
            'T99 (Registro de Imóveis de Navirai)',
        )

    def test_homonimos_distinguidos_pela_posicao(self):
        lancamento = self._criar_lancamento('T366; T366', self.cartorio_iguatemi)
        self._criar_linha(lancamento, 0, 'transcricao', 'T366', self.cartorio_iguatemi)
        self._criar_linha(lancamento, 1, 'transcricao', 'T366', self.cartorio_navirai)

        resultado = formatar_origem_completa(lancamento)

        self.assertEqual(
            resultado,
            'T366 (Registro de Imóveis de Iguatemi)\n'
            'T366 (Registro de Imóveis de Navirai)',
        )

    def test_homonimo_sem_linha_na_posicao_fica_sem_cartorio(self):
        lancamento = self._criar_lancamento('T366; T366', self.cartorio_iguatemi)
        self._criar_linha(lancamento, 0, 'transcricao', 'T366', self.cartorio_iguatemi)

        resultado = formatar_origem_completa(lancamento)

        self.assertEqual(resultado, 'T366 (Registro de Imóveis de Iguatemi)\nT366')

    def test_fim_cadeia_desloca_indice_homonimos(self):
        """Fim de cadeia na posição 0 desloca índices dos homônimos seguintes.

        Se o formatador contasse só origens normais (ignorando o fim de cadeia
        no split), os T366 receberiam cartórios trocados ou o mesmo cartório.
        """
        lancamento = self._criar_lancamento(
            'Sem Origem::sem_origem; T366; T366', self.cartorio_iguatemi
        )
        self._criar_linha(lancamento, 1, 'transcricao', 'T366', self.cartorio_iguatemi)
        self._criar_linha(lancamento, 2, 'transcricao', 'T366', self.cartorio_navirai)

        resultado = formatar_origem_completa(lancamento)

        self.assertEqual(
            resultado,
            'Sem Origem (Sem Origem)\n'
            'T366 (Registro de Imóveis de Iguatemi)\n'
            'T366 (Registro de Imóveis de Navirai)',
        )

    def test_fim_cadeia_com_texto_livre_posicao(self):
        """Fim de cadeia desloca índice de texto livre posterior.

        'Transcrição nº 55' está na posição 1 do split e a linha estruturada
        tem indice_origem=1 — o casamento por posição deve funcionar mesmo
        com um fim de cadeia na posição 0.
        """
        lancamento = self._criar_lancamento(
            'Destacamento Público:INCRA:origem_lidima; Transcrição nº 55',
            self.cartorio_iguatemi,
        )
        self._criar_linha(
            lancamento, 1, 'transcricao', 'T55', self.cartorio_iguatemi
        )

        resultado = formatar_origem_completa(lancamento)

        self.assertEqual(
            resultado,
            'Destacamento Público : INCRA (Origem Lídima)\n'
            'Transcrição nº 55 (Registro de Imóveis de Iguatemi)',
        )

    def test_identidade_divergente_nao_empresta_cartorio(self):
        lancamento = self._criar_lancamento('T100; M99', self.cartorio_iguatemi)
        self._criar_linha(lancamento, 0, 'transcricao', 'T100', self.cartorio_iguatemi)
        self._criar_linha(lancamento, 1, 'transcricao', 'T99', self.cartorio_navirai)

        resultado = formatar_origem_completa(lancamento)

        self.assertEqual(
            resultado, 'T100 (Registro de Imóveis de Iguatemi)\nM99'
        )

    def test_posicao_posterior_sem_linha_fica_sem_cartorio(self):
        lancamento = self._criar_lancamento('T100; T77', self.cartorio_iguatemi)
        self._criar_linha(lancamento, 0, 'transcricao', 'T100', self.cartorio_iguatemi)

        resultado = formatar_origem_completa(lancamento)

        self.assertEqual(
            resultado, 'T100 (Registro de Imóveis de Iguatemi)\nT77'
        )

    def test_primeira_posicao_sem_linha_nao_herda_com_linhas(self):
        lancamento = self._criar_lancamento('T100; T99', self.cartorio_navirai)
        self._criar_linha(lancamento, 1, 'transcricao', 'T99', self.cartorio_navirai)

        resultado = formatar_origem_completa(lancamento)

        self.assertEqual(
            resultado, 'T100\nT99 (Registro de Imóveis de Navirai)'
        )

    def test_primeira_posicao_contraditoria_nao_herda(self):
        lancamento = self._criar_lancamento('M100; T99', self.cartorio_iguatemi)
        self._criar_linha(lancamento, 0, 'transcricao', 'T100', self.cartorio_iguatemi)
        self._criar_linha(lancamento, 1, 'transcricao', 'T99', self.cartorio_navirai)

        resultado = formatar_origem_completa(lancamento)

        self.assertEqual(
            resultado, 'M100\nT99 (Registro de Imóveis de Navirai)'
        )

    def test_texto_sem_identidade_nao_recebe_cartorio_de_outra_origem(self):
        lancamento = self._criar_lancamento(
            'Escritura particular; T99', self.cartorio_navirai
        )
        self._criar_linha(lancamento, 1, 'transcricao', 'T99', self.cartorio_navirai)

        resultado = formatar_origem_completa(lancamento)

        self.assertEqual(
            resultado, 'Escritura particular\nT99 (Registro de Imóveis de Navirai)'
        )

    def test_nome_do_cartorio_da_linha_e_escapado(self):
        cartorio_perigoso = Cartorios.objects.create(
            nome='<b>Navirai</b>', cns='229003', cidade='Navirai', estado='MS'
        )
        lancamento = self._criar_lancamento('T100; T99', self.cartorio_iguatemi)
        self._criar_linha(lancamento, 0, 'transcricao', 'T100', self.cartorio_iguatemi)
        self._criar_linha(lancamento, 1, 'transcricao', 'T99', cartorio_perigoso)

        resultado = origem_formatada_completa(lancamento)

        self.assertIn(escape('<b>Navirai</b>'), str(resultado))
        self.assertNotIn('<b>Navirai</b>', str(resultado))

    def test_legado_sem_linhas_mantem_cartorio_unico(self):
        lancamento = self._criar_lancamento('T100; T99', self.cartorio_iguatemi)

        resultado = formatar_origem_completa(lancamento)

        self.assertEqual(
            resultado,
            'T100 (Registro de Imóveis de Iguatemi)\n'
            'T99 (Registro de Imóveis de Iguatemi)',
        )

    def test_legado_sem_cartorio_origem_exibe_so_texto(self):
        lancamento = self._criar_lancamento('T100; T99', None)

        resultado = formatar_origem_completa(lancamento)

        self.assertEqual(resultado, 'T100\nT99')

    def test_origem_unica_com_linha_usa_cartorio_da_linha(self):
        lancamento = self._criar_lancamento('T100', self.cartorio_iguatemi)
        self._criar_linha(lancamento, 0, 'transcricao', 'T100', self.cartorio_navirai)

        resultado = formatar_origem_completa(lancamento)

        self.assertEqual(resultado, 'T100 (Registro de Imóveis de Navirai)')


class FormatarOrigemTextoLivreTest(_Fixture229, TestCase):
    def test_texto_livre_posicao_0_casa_linha_da_posicao(self):
        lancamento = self._criar_lancamento(
            'Transcrição nº 55; T99', self.cartorio_navirai
        )
        self._criar_linha(lancamento, 0, 'transcricao', 'T55', self.cartorio_iguatemi)
        self._criar_linha(lancamento, 1, 'transcricao', 'T99', self.cartorio_navirai)

        resultado = formatar_origem_completa(lancamento)

        self.assertEqual(
            resultado,
            'Transcrição nº 55 (Registro de Imóveis de Iguatemi)\n'
            'T99 (Registro de Imóveis de Navirai)',
        )

    def test_texto_livre_posicao_posterior_casa_linha_da_posicao(self):
        lancamento = self._criar_lancamento(
            'T100; Transcrição nº 55', self.cartorio_iguatemi
        )
        self._criar_linha(lancamento, 0, 'transcricao', 'T100', self.cartorio_iguatemi)
        self._criar_linha(lancamento, 1, 'transcricao', 'T55', self.cartorio_navirai)

        resultado = formatar_origem_completa(lancamento)

        self.assertEqual(
            resultado,
            'T100 (Registro de Imóveis de Iguatemi)\n'
            'Transcrição nº 55 (Registro de Imóveis de Navirai)',
        )

    def test_texto_livre_tipo_divergente_nao_casa(self):
        lancamento = self._criar_lancamento('Matrícula 55; T100', self.cartorio_iguatemi)
        self._criar_linha(lancamento, 0, 'transcricao', 'T55', self.cartorio_iguatemi)
        self._criar_linha(lancamento, 1, 'transcricao', 'T100', self.cartorio_navirai)

        resultado = formatar_origem_completa(lancamento)

        self.assertEqual(
            resultado, 'Matrícula 55\nT100 (Registro de Imóveis de Navirai)'
        )

    def test_texto_livre_numero_divergente_nao_casa(self):
        lancamento = self._criar_lancamento(
            'Transcrição nº 56; T100', self.cartorio_iguatemi
        )
        self._criar_linha(lancamento, 0, 'transcricao', 'T55', self.cartorio_iguatemi)
        self._criar_linha(lancamento, 1, 'transcricao', 'T100', self.cartorio_navirai)

        resultado = formatar_origem_completa(lancamento)

        self.assertEqual(
            resultado, 'Transcrição nº 56\nT100 (Registro de Imóveis de Navirai)'
        )

    def test_texto_livre_nao_usa_linha_de_outra_posicao(self):
        lancamento = self._criar_lancamento(
            'T100; Transcrição nº 55', self.cartorio_iguatemi
        )
        self._criar_linha(lancamento, 0, 'transcricao', 'T100', self.cartorio_iguatemi)
        self._criar_linha(lancamento, 2, 'transcricao', 'T55', self.cartorio_navirai)

        resultado = formatar_origem_completa(lancamento)

        self.assertEqual(
            resultado, 'T100 (Registro de Imóveis de Iguatemi)\nTranscrição nº 55'
        )

    def test_texto_livre_origem_unica_usa_linha(self):
        lancamento = self._criar_lancamento('Transcrição nº 55', self.cartorio_iguatemi)
        self._criar_linha(lancamento, 0, 'transcricao', 'T55', self.cartorio_navirai)

        resultado = formatar_origem_completa(lancamento)

        self.assertEqual(
            resultado, 'Transcrição nº 55 (Registro de Imóveis de Navirai)'
        )


class FormatarOrigemSemBancoTest(SimpleTestCase):
    """`SimpleTestCase` barra acesso ao banco: cada teste também prova a
    guarda D6 (não tocar na relação `origens_estruturadas` sem isinstance+pk)."""

    def test_duck_typed_com_pk_sem_relacao_usa_legado(self):
        lancamento = SimpleNamespace(
            pk=1,
            origem='T100; T99',
            cartorio_origem=SimpleNamespace(nome='X'),
        )

        resultado = formatar_origem_completa(lancamento)

        self.assertEqual(resultado, 'T100 (X)\nT99 (X)')

    def test_lancamento_nao_salvo_usa_legado(self):
        lancamento = Lancamento(
            origem='T100; T99',
            cartorio_origem=Cartorios(nome='X'),
        )

        resultado = formatar_origem_completa(lancamento)

        self.assertEqual(resultado, 'T100 (X)\nT99 (X)')


class FormatarOrigemCompletaAddendumTest(_Fixture229, TestCase):
    """Addendum v2.1 do co-review (Codex gpt-6-astra, round 2)."""

    def test_ambiguidade_posicao_0_no_formatador(self):
        lancamento = self._criar_lancamento('T366; T366', self.cartorio_iguatemi)
        self._criar_linha(lancamento, 1, 'transcricao', 'T366', self.cartorio_navirai)

        resultado = formatar_origem_completa(lancamento)

        self.assertEqual(
            resultado, 'T366\nT366 (Registro de Imóveis de Navirai)'
        )

    def test_outra_misturado_com_origens_normais(self):
        lancamento = self._criar_lancamento(
            'T100; Outra:Lote 5:origem_identificada; T99', self.cartorio_iguatemi
        )
        self._criar_linha(lancamento, 0, 'transcricao', 'T100', self.cartorio_iguatemi)
        self._criar_linha(lancamento, 2, 'transcricao', 'T99', self.cartorio_navirai)

        resultado = formatar_origem_completa(lancamento)

        self.assertEqual(
            resultado,
            'T100 (Registro de Imóveis de Iguatemi)\n'
            'Outra : Lote 5 (Origem Lídima)\n'
            'T99 (Registro de Imóveis de Navirai)',
        )

    def test_fim_cadeia_legado_misturado(self):
        lancamento = self._criar_lancamento(
            'FIM_CADEIA; T100; T99', self.cartorio_iguatemi
        )
        self._criar_linha(lancamento, 1, 'transcricao', 'T100', self.cartorio_iguatemi)
        self._criar_linha(lancamento, 2, 'transcricao', 'T99', self.cartorio_navirai)

        resultado = formatar_origem_completa(lancamento)

        self.assertEqual(
            resultado,
            'FIM_CADEIA\n'
            'T100 (Registro de Imóveis de Iguatemi)\n'
            'T99 (Registro de Imóveis de Navirai)',
        )


class FormatarOrigemCompletaQueriesTest(_Fixture229, TestCase):
    def test_exportacao_prefetch_zera_queries_no_formatador(self):
        documento_estruturado = Documento.objects.create(
            imovel=self.imovel, tipo=self.tipo_transcricao, numero='T-QRY-A',
            data=timezone.now().date(), cartorio=self.cartorio_iguatemi,
        )
        lancamento_estruturado = Lancamento(
            documento=documento_estruturado, tipo=self.tipo_inicio,
            data=timezone.now().date(), origem='T100; T99',
            cartorio_origem=self.cartorio_iguatemi,
        )
        Lancamento.objects.bulk_create([lancamento_estruturado])
        self._criar_linha(
            lancamento_estruturado, 0, 'transcricao', 'T100', self.cartorio_iguatemi
        )
        self._criar_linha(
            lancamento_estruturado, 1, 'transcricao', 'T99', self.cartorio_navirai
        )

        documento_legado = Documento.objects.create(
            imovel=self.imovel, tipo=self.tipo_transcricao, numero='T-QRY-B',
            data=timezone.now().date(), cartorio=self.cartorio_iguatemi,
        )
        lancamento_legado = Lancamento(
            documento=documento_legado, tipo=self.tipo_inicio,
            data=timezone.now().date(), origem='T50',
            cartorio_origem=self.cartorio_iguatemi,
        )
        Lancamento.objects.bulk_create([lancamento_legado])

        documentos = list(
            Documento.objects.filter(
                pk__in=[documento_estruturado.pk, documento_legado.pk]
            )
        )
        CadeiaCompletaService._prefetch_dados_exportacao(documentos)

        resultados = {}
        with self.assertNumQueries(0):
            for documento in documentos:
                for lancamento in documento._lancamentos_exportacao:
                    resultados[documento.numero] = formatar_origem_completa(lancamento)

        self.assertEqual(
            resultados['T-QRY-A'],
            'T100 (Registro de Imóveis de Iguatemi)\n'
            'T99 (Registro de Imóveis de Navirai)',
        )
        self.assertEqual(
            resultados['T-QRY-B'], 'T50 (Registro de Imóveis de Iguatemi)'
        )

    def test_tabela_prefetch_zera_queries_no_formatador(self):
        lancamento = self._criar_lancamento('T100; T99', self.cartorio_iguatemi)
        self._criar_linha(lancamento, 0, 'transcricao', 'T100', self.cartorio_iguatemi)
        self._criar_linha(lancamento, 1, 'transcricao', 'T99', self.cartorio_navirai)

        lancamentos = list(
            CadeiaDominialTabelaService._lancamentos_do_documento(self.documento)
        )

        with self.assertNumQueries(0):
            resultado = formatar_origem_completa(lancamentos[0])

        self.assertEqual(
            resultado,
            'T100 (Registro de Imóveis de Iguatemi)\n'
            'T99 (Registro de Imóveis de Navirai)',
        )

    def test_sem_prefetch_uma_query_por_lancamento(self):
        lancamento = self._criar_lancamento('T100; T99', self.cartorio_iguatemi)
        self._criar_linha(lancamento, 0, 'transcricao', 'T100', self.cartorio_iguatemi)
        self._criar_linha(lancamento, 1, 'transcricao', 'T99', self.cartorio_navirai)

        lancamento_recarregado = Lancamento.objects.select_related(
            'cartorio_origem'
        ).get(pk=lancamento.pk)

        with self.assertNumQueries(1):
            formatar_origem_completa(lancamento_recarregado)

    def test_caminho_legado_frio_sem_select_related(self):
        """Caminho frio: Lancamento.objects.get(pk=...) sem select_related.

        Custo real: 2 queries.
        - Query 1: linhas_estruturadas (SELECT em LancamentoOrigem, vazio)
        - Query 2: cartorio_origem lazy load (SELECT em Cartorios)

        Justificativa: sem raw SQL, não há como combinar as duas consultas
        (linhas estruturadas + nome do cartório legado) em uma única query.
        A verificação de linhas é obrigatória para correção (#229), e o nome
        do cartório é necessário para exibição. O custo é aceitável para o
        caminho frio (lançamentos legados sem prefetch), que é minoritário
        no fluxo de exportação (onde o prefetch zera queries).

        Round 2 de review: avaliar se vale a pena adicionar select_related
        no carregamento legado para reduzir para 1 query.
        """
        lancamento = self._criar_lancamento('T100; T99', self.cartorio_iguatemi)
        # Sem linhas estruturadas: caminho legado

        lancamento_frio = Lancamento.objects.get(pk=lancamento.pk)

        with self.assertNumQueries(2):
            resultado = formatar_origem_completa(lancamento_frio)

        self.assertEqual(
            resultado,
            'T100 (Registro de Imóveis de Iguatemi)\n'
            'T99 (Registro de Imóveis de Iguatemi)',
        )

    def test_so_fins_de_cadeia_nao_consulta_linhas(self):
        lancamento = self._criar_lancamento(
            'Destacamento Público:INCRA:Origem Lídima', self.cartorio_iguatemi
        )

        with self.assertNumQueries(0):
            formatar_origem_completa(lancamento)

    def test_obter_origens_com_prefetch_igual_sem_prefetch(self):
        lancamento = self._criar_lancamento('T100; T99', self.cartorio_iguatemi)
        self._criar_linha(lancamento, 0, 'transcricao', 'T100', self.cartorio_iguatemi)
        self._criar_linha(lancamento, 1, 'transcricao', 'T99', self.cartorio_navirai)

        sem_prefetch = LancamentoOrigemLeituraService.obter_origens(
            Lancamento.objects.get(pk=lancamento.pk)
        )

        lancamento_prefetched = Lancamento.objects.prefetch_related(
            LancamentoOrigemLeituraService.prefetch_linhas()
        ).get(pk=lancamento.pk)
        with self.assertNumQueries(0):
            com_prefetch = LancamentoOrigemLeituraService.obter_origens(
                lancamento_prefetched
            )

        self.assertEqual(sem_prefetch, com_prefetch)


class ExportacaoXlsxCartorioPorOrigemTest(_Fixture229, TestCase):
    def test_coluna_origem_exibe_cartorio_por_origem(self):
        lancamento = self._criar_lancamento('T100; T99', self.cartorio_iguatemi)
        self._criar_linha(lancamento, 0, 'transcricao', 'T100', self.cartorio_iguatemi)
        self._criar_linha(lancamento, 1, 'transcricao', 'T99', self.cartorio_navirai)

        service = CadeiaCompletaService()
        resultado = service.get_cadeia_completa(self.tis.id, self.imovel.id)

        ws = Workbook().active
        escrever_secao_documentos(ws, resultado['cadeia_completa'], 1)

        valores_coluna_o = [
            cell.value for cell in ws['O'] if cell.value not in (None, 'Origem')
        ]
        self.assertIn(
            'T100 (Registro de Imóveis de Iguatemi)\n'
            'T99 (Registro de Imóveis de Navirai)',
            valores_coluna_o,
        )


class ApiOrigemFormatadaPorOrigemTest(_Fixture229, TestCase):
    def test_origem_formatada_por_origem(self):
        self.imovel.matricula = 'M900'
        self.imovel.save()
        self.documento.numero = 'M900'
        self.documento.save()
        lancamento = self._criar_lancamento('T100; T99', self.cartorio_iguatemi)
        self._criar_linha(lancamento, 0, 'transcricao', 'T100', self.cartorio_iguatemi)
        self._criar_linha(lancamento, 1, 'transcricao', 'T99', self.cartorio_navirai)

        user = User.objects.create_user(username='issue229', password='issue229pass')
        self.client.force_login(user)
        url = reverse(
            'get_cadeia_dominial_atualizada',
            kwargs={'tis_id': self.tis.id, 'imovel_id': self.imovel.id},
        )

        payload = self.client.get(url).json()

        self.assertTrue(payload['success'])
        item = next(
            item for item in payload['cadeia']
            if item['documento']['numero'] == 'M900'
        )
        self.assertEqual(
            item['lancamentos'][0]['origem_formatada'],
            'T100 (Registro de Imóveis de Iguatemi)<br>'
            'T99 (Registro de Imóveis de Navirai)',
        )
