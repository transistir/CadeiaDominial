"""
Issue #202 (Fase 1) — ordem de exportação (XLS/PDF) agrupada por galho.

Regra definida pelo dono do produto:

1. travessia em pré-ordem a partir da ponta (o primeiro documento do tronco
   principal): ao alcançar um documento, emita-o e desça pelos seus galhos;
2. a ordem dos galhos de cada documento é a chave canônica já existente
   (`dominial.utils.ordenacao_cadeia`): matrícula antes de transcrição,
   número inteiro decrescente, comparando só irmãos do mesmo nível;
3. um documento alcançado por vários galhos é emitido uma única vez, na
   primeira vez;
4. o conjunto de documentos exportados não muda: é o mesmo componente
   alcançável de hoje;
5. a tela (uma linha por nível, só o galho escolhido) não muda — esta issue
   mexe apenas na exportação.

As duas fixtures abaixo (`_Forma114`, `_Forma384`) reproduzem, com os mesmos
números de documento, a forma real dos imóveis 114 e 384 medida no banco do
serviço de teste (issue #201/#202): bifurcação com irmãos matrícula e
transcrição, cadeia atravessando tipo (matrícula -> transcrição) e documentos
alcançados por mais de um galho (M7842/T7890 no 114; T2391 no 384).
"""

from datetime import date

from django.core.cache import cache
from django.test import TestCase

from dominial.models import (
    Cartorios,
    Documento,
    DocumentoTipo,
    Imovel,
    Lancamento,
    LancamentoTipo,
    Pessoas,
    TIs,
)
from dominial.services.cadeia_completa_service import CadeiaCompletaService
from dominial.services.cadeia_dominial_tabela_service import CadeiaDominialTabelaService


class _OrigensFixture:
    """Mixin de fixture: o imóvel analisado e um outro imóvel, com documentos
    descritos por mapas {número: origem textual do lançamento de início de
    matrícula}. O tipo vem do prefixo do número. O primeiro documento de
    `ORIGENS_IMOVEL` é a identidade registral do imóvel.

    Não herda de TestCase para não ser coletado como um caso de teste vazio.
    """

    ORIGENS_IMOVEL = {}
    ORIGENS_OUTRO_IMOVEL = {}

    def setUp(self):
        super().setUp()
        # O tronco principal é cacheado por id de imóvel, e os ids se repetem
        # entre testes (rollback de transação).
        cache.clear()

        self.tis = TIs.objects.create(nome='TI 202', codigo='TI-202', etnia='Teste')
        self.cartorio = Cartorios.objects.create(
            nome='CRI 202', cns='CNS-202', cidade='Cidade 202', estado='TS',
        )
        self.proprietario = Pessoas.objects.create(nome='Proprietario 202')
        self.tipos_documento = {
            'M': DocumentoTipo.objects.create(tipo='matricula'),
            'T': DocumentoTipo.objects.create(tipo='transcricao'),
        }
        self.tipo_inicio = LancamentoTipo.objects.create(tipo='inicio_matricula')

        self.docs = {}
        matricula_imovel = next(iter(self.ORIGENS_IMOVEL))
        self.imovel = Imovel.objects.create(
            terra_indigena_id=self.tis,
            nome=f'Imóvel {matricula_imovel}',
            proprietario=self.proprietario,
            matricula=matricula_imovel,
            tipo_documento_principal='matricula',
            cartorio=self.cartorio,
        )
        self.outro_imovel = Imovel.objects.create(
            terra_indigena_id=self.tis,
            nome='Outro imóvel 202',
            proprietario=self.proprietario,
            matricula='M999999',
            tipo_documento_principal='matricula',
            cartorio=self.cartorio,
        )
        self._criar_documentos(self.imovel, self.ORIGENS_IMOVEL)
        self._criar_documentos(self.outro_imovel, self.ORIGENS_OUTRO_IMOVEL)

    def _criar_documentos(self, imovel, origens_por_numero):
        for numero in origens_por_numero:
            self.docs[numero] = Documento.objects.create(
                imovel=imovel,
                tipo=self.tipos_documento[numero[0]],
                numero=numero,
                data=date(2025, 7, 7),
                cartorio=self.cartorio,
                livro='1',
                folha='1',
            )
        # bulk_create para não disparar o signal `processar_origens_automaticas_signal`
        # (dominial/signals.py), que criaria documentos automáticos a partir
        # da string de origem e poluiria a fixture.
        Lancamento.objects.bulk_create([
            Lancamento(
                documento=self.docs[numero],
                tipo=self.tipo_inicio,
                data=self.docs[numero].data,
                cartorio_origem=self.cartorio,
                origem=origem,
            )
            for numero, origem in origens_por_numero.items()
        ])

    def _numeros_exportados(self):
        resultado = CadeiaCompletaService().get_cadeia_completa(self.tis.id, self.imovel.id)
        documentos = resultado['cadeia_completa'][0]['documentos']
        return [item['documento'].numero for item in documentos]


class _Forma114(_OrigensFixture):
    """Forma do imóvel 114 (TI Comexatibá, test server): 17 documentos.

    M13826 bifurca em cinco matrículas irmãs (ordem canônica: número
    decrescente). M13320 e M13132 convergem em M7842 (que segue para T7890,
    cadeia atravessando tipo); M7843 cita T7890 diretamente — M7842 e T7890
    são, portanto, alcançados por mais de um galho e devem aparecer uma única
    vez, na primeira vez (via M13320, o galho de maior precedência).
    """

    ORIGENS_IMOVEL = {'M18692': 'M16433; M13826'}
    ORIGENS_OUTRO_IMOVEL = {
        'M16433': '',
        'M13826': 'M13320; M13133; M13132; M7843; M7697',
        'M13320': 'M7842',
        'M7842': 'T7890',
        'T7890': '',
        'M13133': 'M10509',
        'M10509': '',
        'M13132': 'M7842',
        'M7843': 'T7890',
        'M7697': 'T10104; T10102; T8591; T8390; T8389',
        'T10104': '',
        'T10102': '',
        'T8591': 'T7670',
        'T7670': '',
        'T8390': '',
        'T8389': '',
    }

    ORDEM_GALHO = [
        'M18692', 'M16433', 'M13826', 'M13320', 'M7842', 'T7890', 'M13133',
        'M10509', 'M13132', 'M7843', 'M7697', 'T10104', 'T10102', 'T8591',
        'T7670', 'T8390', 'T8389',
    ]


class _Forma384(_OrigensFixture):
    """Forma do imóvel 384 (TI Iguatemipegua I, test server): 30 documentos.

    T2391 é citada por nove documentos diferentes (T3281, T3280, T4558,
    T3446, T4559, T3445, T3444, T3443, T3151) e deve aparecer uma única vez.
    M2622 -> T9231 -> T13963 -> T9001 é uma cadeia contígua que atravessa
    matrícula e transcrição, ao contrário da antiga lista plana.
    """

    ORIGENS_IMOVEL = {'M8272': 'M7775'}
    ORIGENS_OUTRO_IMOVEL = {
        'M7775': 'M2623; M2622; M002621',
        'M2623': 'M2072',
        'M2072': 'T13367; T13366; T3446',
        'T13367': 'T10786; T4558',
        'T10786': 'T3281; T3280',
        'T3281': 'T2391',
        'T3280': 'T2391',
        'T4558': 'T2391',
        'T13366': 'T3281; T3280',
        'T3446': 'T2391',
        'T2391': '',
        'M2622': 'T9231',
        'T9231': 'T13963',
        'T13963': 'T9001; T6903; T6873',
        'T9001': '',
        'T6903': 'T5184',
        'T5184': 'T341',
        'T341': '',
        'T6873': (
            'T4591; T4590; T4589; T4559; T4558; T3446; T3445; T3444; T3443; T3151'
        ),
        'T4591': 'T3281; T3280',
        'T4590': 'T3281; T3280',
        'T4589': 'T3281; T3280',
        'T4559': 'T2391',
        'T3445': 'T2391',
        'T3444': 'T2391',
        'T3443': 'T2391',
        'T3151': 'T2391',
        'M002621': 'T3059',
        'T3059': '',
    }

    ORDEM_GALHO = [
        'M8272', 'M7775', 'M2623', 'M2072', 'T13367', 'T10786', 'T3281',
        'T2391', 'T3280', 'T4558', 'T13366', 'T3446', 'M2622', 'T9231',
        'T13963', 'T9001', 'T6903', 'T5184', 'T341', 'T6873', 'T4591',
        'T4590', 'T4589', 'T4559', 'T3445', 'T3444', 'T3443', 'T3151',
        'M002621', 'T3059',
    ]


class Forma114OrdemDeExportacaoTest(_Forma114, TestCase):

    def test_ordem_de_exportacao_segue_a_ordem_ouro(self):
        self.assertEqual(self._numeros_exportados(), self.ORDEM_GALHO)


class Forma384OrdemDeExportacaoTest(_Forma384, TestCase):

    def test_ordem_de_exportacao_segue_a_ordem_ouro(self):
        self.assertEqual(self._numeros_exportados(), self.ORDEM_GALHO)

    def test_documento_alcancado_por_varios_galhos_aparece_uma_unica_vez(self):
        numeros = self._numeros_exportados()
        self.assertEqual(numeros.count('T2391'), 1)

    def test_conjunto_exportado_e_superconjunto_do_antigo(self):
        """
        A travessia em pré-ordem parte do mesmo documento inicial do
        algoritmo antigo (`tronco_principal[0]`) e desce por TODAS as
        origens resolvidas: nunca perde documento que o antigo alcançava —
        o conjunto novo não pode ser subconjunto do antigo, só igual ou
        superconjunto (é o que acontece no imóvel 214, cuja matrícula não
        tem documento próprio: ver `MatriculaSemDocumentoProprioTest`).

        Neste fixture (sem o "gap" do imóvel 214) o conjunto é exatamente o
        mesmo do antigo — só a ordem muda; por isso a comparação abaixo é de
        igualdade, não de superconjunto estrito.
        """
        resultado = CadeiaCompletaService().get_cadeia_completa(self.tis.id, self.imovel.id)
        documentos = resultado['cadeia_completa'][0]['documentos']
        ids_exportados = {item['documento'].id for item in documentos}

        ids_esperados = {
            self.docs[numero].id
            for numero in {**self.ORIGENS_IMOVEL, **self.ORIGENS_OUTRO_IMOVEL}
        }
        self.assertEqual(len(documentos), len(self.ORDEM_GALHO))
        self.assertEqual(ids_exportados, ids_esperados)


class Forma384TabelaContinuaUmaLinhaPorNivelTest(_Forma384, TestCase):
    """A tabela (tela) não muda nesta issue: continua com uma linha por
    nível, seguindo só o galho de maior precedência — nunca as 30 linhas da
    exportação."""

    def test_tabela_segue_so_o_galho_de_maior_precedencia(self):
        cadeia = CadeiaDominialTabelaService().obter_cadeia_tabela(self.imovel)
        numeros = [item['documento'].numero for item in cadeia]

        self.assertEqual(
            numeros,
            ['M8272', 'M7775', 'M2623', 'M2072', 'T13367', 'T10786', 'T3281', 'T2391'],
        )
        self.assertLess(len(numeros), len(self.ORDEM_GALHO))


class OrigemComCartorioDivergenteTest(TestCase):
    """Uma origem cujo código bate com um documento existente, mas informada
    com outro cartório no lançamento, não resolve: mesmo código em cartórios
    diferentes são origens distintas (`obter_origens_resolvidas`), e uma
    origem que não resolve fica de fora do conjunto exportado — em vez de,
    por engano, resolver pelo número isolado.
    """

    def setUp(self):
        cache.clear()
        self.tis = TIs.objects.create(nome='TI Cart', codigo='TI-CART', etnia='Teste')
        self.cartorio = Cartorios.objects.create(
            nome='CRI A', cns='CNS-A', cidade='Cidade A', estado='TS',
        )
        self.outro_cartorio = Cartorios.objects.create(
            nome='CRI B', cns='CNS-B', cidade='Cidade B', estado='TS',
        )
        self.proprietario = Pessoas.objects.create(nome='Proprietario Cart')
        tipo_matricula = DocumentoTipo.objects.create(tipo='matricula')
        tipo_inicio = LancamentoTipo.objects.create(tipo='inicio_matricula')

        self.imovel = Imovel.objects.create(
            terra_indigena_id=self.tis,
            nome='Imóvel Cart',
            proprietario=self.proprietario,
            matricula='M100',
            tipo_documento_principal='matricula',
            cartorio=self.cartorio,
        )
        m100 = Documento.objects.create(
            imovel=self.imovel, tipo=tipo_matricula, numero='M100',
            data=date(2025, 7, 7), cartorio=self.cartorio, livro='1', folha='1',
        )
        # M50 existe, mas só no cartório A. A origem de M100 informa M50 no
        # cartório B — não há M50 nesse cartório, então não resolve.
        Documento.objects.create(
            imovel=self.imovel, tipo=tipo_matricula, numero='M50',
            data=date(2025, 7, 7), cartorio=self.cartorio, livro='1', folha='1',
        )
        # bulk_create para não disparar o signal `processar_origens_automaticas_signal`
        # (dominial/signals.py), que criaria/religaria documentos a partir da
        # string de origem e mascararia o cenário testado.
        Lancamento.objects.bulk_create([
            Lancamento(
                documento=m100, tipo=tipo_inicio, data=m100.data,
                cartorio_origem=self.outro_cartorio, origem='M50',
            ),
        ])

    def test_origem_com_cartorio_divergente_fica_fora_do_conjunto(self):
        resultado = CadeiaCompletaService().get_cadeia_completa(self.tis.id, self.imovel.id)
        documentos = resultado['cadeia_completa'][0]['documentos']
        numeros = [item['documento'].numero for item in documentos]

        self.assertEqual(numeros, ['M100'])


class MatriculaSemDocumentoProprioTest(TestCase):
    """Forma do imóvel 214 (test server): a matrícula do imóvel (M2025) não
    tem Documento próprio — só existe M2024, que ninguém cita como origem e
    por isso vira a raiz do tronco (fallback de `identificar_tronco_principal`
    para documentos-raiz). M2024 tem duas origens (T25891, T25890); a árvore
    antiga (removida nesta issue) só alcançava a primeira. A nova travessia
    desce por todas as origens de cada documento e inclui as duas.
    """

    def setUp(self):
        cache.clear()
        self.tis = TIs.objects.create(nome='TI 214', codigo='TI-214', etnia='Teste')
        self.cartorio = Cartorios.objects.create(
            nome='CRI 214', cns='CNS-214', cidade='Cidade 214', estado='TS',
        )
        self.proprietario = Pessoas.objects.create(nome='Proprietario 214')
        tipo_matricula = DocumentoTipo.objects.create(tipo='matricula')
        tipo_transcricao = DocumentoTipo.objects.create(tipo='transcricao')
        tipo_inicio = LancamentoTipo.objects.create(tipo='inicio_matricula')

        self.imovel = Imovel.objects.create(
            terra_indigena_id=self.tis,
            nome='Imóvel 214',
            proprietario=self.proprietario,
            matricula='M2025',
            tipo_documento_principal='matricula',
            cartorio=self.cartorio,
        )

        m2024 = Documento.objects.create(
            imovel=self.imovel, tipo=tipo_matricula, numero='M2024',
            data=date(2025, 7, 7), cartorio=self.cartorio, livro='1', folha='1',
        )
        for numero in ('T25891', 'T25890'):
            Documento.objects.create(
                imovel=self.imovel, tipo=tipo_transcricao, numero=numero,
                data=date(2025, 7, 7), cartorio=self.cartorio, livro='1', folha='1',
            )

        # bulk_create para não disparar o signal `processar_origens_automaticas_signal`
        # (dominial/signals.py), que criaria documentos automáticos a partir
        # da string de origem e poluiria a fixture.
        Lancamento.objects.bulk_create([
            Lancamento(
                documento=m2024, tipo=tipo_inicio, data=m2024.data,
                cartorio_origem=self.cartorio, origem='T25891; T25890',
            ),
        ])

    def test_conjunto_exportado_inclui_segunda_origem_da_raiz(self):
        resultado = CadeiaCompletaService().get_cadeia_completa(self.tis.id, self.imovel.id)
        documentos = resultado['cadeia_completa'][0]['documentos']
        numeros = [item['documento'].numero for item in documentos]

        self.assertEqual(numeros, ['M2024', 'T25891', 'T25890'])
