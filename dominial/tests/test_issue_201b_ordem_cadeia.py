"""
Issue #201 (follow-up) — ordem canônica da tabela da cadeia dominial.

Regra jurídica definida pelo dono do produto, nesta precedência:

1. documento do imóvel (identidade registral) sempre primeiro;
2. matrícula antes de transcrição — absoluto, não é desempate;
3. número maior antes de menor, comparado como inteiro (nunca como texto).

A mesma chave ordena as linhas da tabela (rota `ver-cadeia-dominial`, nas duas
trilhas da view `tronco_principal`), os botões de origem e a origem seguida por
padrão — sempre a primeira da lista, para que o botão destacado seja a cadeia
exibida. Ela vive num único lugar: `dominial/utils/ordenacao_cadeia.py`.

Antes desta correção conviviam ordenações divergentes: linhas por data
(`obter_cadeia_tabela`), linhas na ordem de expansão
(`get_cadeia_dominial_tabela`), botões por número ignorando o tipo ou por texto
(`'M717' > 'M1612'`) e a caminhada do tronco por número ignorando o tipo
(`identificar_tronco_principal`). No imóvel 4, a tabela destacava M717 e
exibia a cadeia de M1612.

A exportação PDF/XLS (`CadeiaCompletaService`) é agrupada por troncos e não
segue esta regra (decisão explícita do dono do produto).
"""

import random
import re
from datetime import date
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

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
from dominial.services.cache_service import CacheService
from dominial.services.cadeia_dominial_tabela_service import CadeiaDominialTabelaService
from dominial.utils.hierarquia_utils import identificar_tronco_principal
from dominial.utils.ordenacao_cadeia import (
    chave_ordem_cadeia,
    chave_ordem_origem,
    eh_documento_do_imovel,
    numero_para_ordenacao,
    ordenar_cadeia,
)


# Data fictícia/presumida, repetida em vários documentos como no banco.
DATA_PRESUMIDA = date(2025, 7, 7)


def _numeros(cadeia):
    """Números dos documentos, na ordem, a partir do retorno do service."""
    return [item['documento'].numero for item in cadeia]


def _por_numero(cadeia):
    return {item['documento'].numero: item for item in cadeia}


def _opcoes(item):
    """Números dos botões de origem de um documento, na ordem."""
    return [origem['numero'] for origem in item['origens_disponiveis']]


class ChaveCanonicaTest(SimpleTestCase):
    """A chave única, sem banco."""

    IMOVEL = SimpleNamespace(
        id=1, tipo_documento_principal='matricula',
        matricula_normalizada='100', cartorio_id=1,
    )

    def _documento(self, numero, imovel_id=2, cartorio_id=1):
        tipo = {'M': 'matricula', 'T': 'transcricao'}.get(numero[0], 'outro')
        return SimpleNamespace(
            numero=numero, numero_normalizado=numero[1:],
            tipo=SimpleNamespace(tipo=tipo),
            imovel_id=imovel_id, cartorio_id=cartorio_id,
        )

    def test_numero_e_comparado_como_inteiro_sem_zeros_a_esquerda(self):
        self.assertEqual(numero_para_ordenacao('M002621'), 2621)
        self.assertEqual(numero_para_ordenacao('002621'), 2621)
        self.assertEqual(numero_para_ordenacao('sem número'), 0)
        self.assertEqual(numero_para_ordenacao(None), 0)
        # Como texto, 'M717' > 'M1612' e 'M002621' ficaria por último.
        self.assertEqual(
            sorted(['M717', 'M002621', 'M1612', 'M2622'], key=chave_ordem_origem),
            ['M2622', 'M002621', 'M1612', 'M717'],
        )

    def test_matricula_vem_antes_de_transcricao_de_numero_maior(self):
        self.assertEqual(
            sorted(['M6861', 'T17675', 'T21820', 'T3987'], key=chave_ordem_origem),
            ['M6861', 'T21820', 'T17675', 'T3987'],
        )

    def test_tipo_desconhecido_vai_depois_das_transcricoes(self):
        documentos = [
            self._documento('X99999'), self._documento('T1'), self._documento('M1'),
        ]
        self.assertEqual(
            [documento.numero for documento in ordenar_cadeia(documentos)],
            ['M1', 'T1', 'X99999'],
        )

    def test_documento_do_imovel_vem_antes_de_matricula_maior(self):
        documento_do_imovel = self._documento('M100', imovel_id=1)
        documentos = [self._documento('T9000'), self._documento('M5000'), documento_do_imovel]

        self.assertTrue(eh_documento_do_imovel(documento_do_imovel, self.IMOVEL))
        self.assertEqual(
            [documento.numero for documento in ordenar_cadeia(documentos, self.IMOVEL)],
            ['M100', 'M5000', 'T9000'],
        )
        # Sem imóvel (ordem das origens), nenhum documento recebe o rank 0.
        self.assertEqual(
            [documento.numero for documento in ordenar_cadeia(documentos)],
            ['M5000', 'M100', 'T9000'],
        )

    def test_homonimo_de_outro_cartorio_nao_e_o_documento_do_imovel(self):
        homonimo = self._documento('M100', imovel_id=1, cartorio_id=2)
        self.assertFalse(eh_documento_do_imovel(homonimo, self.IMOVEL))

    def test_documento_e_seu_codigo_de_origem_tem_a_mesma_chave(self):
        for numero in ('M002621', 'T3281', 'M8272'):
            with self.subTest(numero=numero):
                self.assertEqual(
                    chave_ordem_cadeia(self._documento(numero)),
                    chave_ordem_origem(numero),
                )

    def test_chaves_identicas_mantem_a_ordem_recebida(self):
        # Mesmo tipo e número em cartórios diferentes: nenhum critério extra.
        cartorio_1 = self._documento('M123', cartorio_id=1)
        cartorio_2 = self._documento('M123', cartorio_id=2)
        for entrada in ([cartorio_1, cartorio_2], [cartorio_2, cartorio_1]):
            self.assertEqual(
                [documento.cartorio_id for documento in ordenar_cadeia(entrada)],
                [documento.cartorio_id for documento in entrada],
            )

    def test_ordenar_cadeia_nao_altera_a_lista_recebida(self):
        documentos = [self._documento('T1'), self._documento('M1')]
        ordenar_cadeia(documentos)
        self.assertEqual([documento.numero for documento in documentos], ['T1', 'M1'])


class _OrdemCadeiaFixture:
    """Mixin de fixture: o imóvel analisado e um outro imóvel, com documentos
    descritos por mapas {número: origem textual do lançamento de início de
    matrícula}. O tipo vem do prefixo do número; o primeiro documento de
    `ORIGENS_IMOVEL` é a identidade registral do imóvel.

    Não herda de TestCase para não ser coletado como um caso de teste
    vazio. Classes filhas devem herdar de (_Fixture, TestCase).
    """

    ORIGENS_IMOVEL = {}
    ORIGENS_OUTRO_IMOVEL = {}
    DATAS = {}

    def setUp(self):
        super().setUp()
        # O tronco principal é cacheado por id de imóvel, e os ids se repetem
        # entre testes (rollback de transação).
        cache.clear()

        self.tis = TIs.objects.create(nome='TI 201b', codigo='TI-201B', etnia='Teste')
        self.cartorio = Cartorios.objects.create(
            nome='CRI 201b', cns='CNS-201B', cidade='Cidade 201b', estado='TS',
        )
        self.proprietario = Pessoas.objects.create(nome='Proprietario 201b')
        self.tipos_documento = {
            'M': DocumentoTipo.objects.create(tipo='matricula'),
            'T': DocumentoTipo.objects.create(tipo='transcricao'),
        }
        self.tipo_inicio = LancamentoTipo.objects.create(tipo='inicio_matricula')

        self.docs = {}
        self.imovel = self._criar_imovel(next(iter(self.ORIGENS_IMOVEL)))
        self.outro_imovel = self._criar_imovel('M999999')
        self._criar_documentos(self.imovel, self.ORIGENS_IMOVEL)
        self._criar_documentos(self.outro_imovel, self.ORIGENS_OUTRO_IMOVEL)

    def _criar_imovel(self, matricula):
        return Imovel.objects.create(
            terra_indigena_id=self.tis,
            nome=f'Imóvel {matricula}',
            proprietario=self.proprietario,
            matricula=matricula,
            tipo_documento_principal='matricula',
            cartorio=self.cartorio,
        )

    def _criar_documentos(self, imovel, origens_por_numero):
        for numero in origens_por_numero:
            self.docs[numero] = Documento.objects.create(
                imovel=imovel,
                tipo=self.tipos_documento[numero[0]],
                numero=numero,
                data=self.DATAS.get(numero, DATA_PRESUMIDA),
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

    def _logar(self):
        self.client.force_login(
            User.objects.create_user(username='issue201b', password='issue201bpass')
        )


class _Forma384(_OrdemCadeiaFixture):
    """Forma do imóvel 384 (TI 201, test server), com os mesmos números.

    Tronco principal (sem escolha): M8272 -> M7775 -> M2623 -> M2072 ->
    T13367 -> T10786 -> T3281 -> T2391. T10786 tem origem dupla (T3280 e
    T3281), o ponto de escolha do caso real. Os demais documentos são origens
    que o tronco não segue, com as subcadeias abaixo delas: só entram na
    trilha com escolha, que tem 17 documentos.

    As datas imitam as do banco (fictícias, várias idênticas). Ordenada por
    data, como fazia `obter_cadeia_tabela`, a tabela saía
    M8272, M7775, T3281, T2391, M2623, M2072, T13367, T10786.
    """

    ORIGENS_IMOVEL = {'M8272': 'M7775'}
    ORIGENS_OUTRO_IMOVEL = {
        'M7775': 'M2623; M2622',
        'M2623': 'M2072',
        'M2072': 'T13367; T13366',
        'T13367': 'T10786; T9231',
        'T10786': 'T3280; T3281',
        'T3281': 'T2391',
        'T3280': 'T2391',
        'T2391': 'Destacamento Público:INCRA:origem_lidima',
        'M2622': 'M002621',
        'M002621': 'T13963',
        'T13963': '',
        'T13366': 'T3446',
        'T3446': '',
        'T9231': 'T9001',
        'T9001': 'T4558',
        'T4558': '',
    }
    DATAS = {
        'M8272': date(2024, 1, 1),
        'M7775': date(2024, 6, 1),
        'T3281': date(2025, 1, 1),
        'T2391': date(2025, 1, 1),
    }

    ORDEM_SEM_ESCOLHA = [
        'M8272', 'M7775', 'M2623', 'M2072', 'T13367', 'T10786', 'T3281', 'T2391',
    ]
    ORDEM_COM_ESCOLHA = [
        'M8272', 'M7775', 'M2623', 'M2622', 'M002621', 'M2072',
        'T13963', 'T13367', 'T13366', 'T10786', 'T9231', 'T9001', 'T4558',
        'T3446', 'T3281', 'T3280', 'T2391',
    ]

    def _cadeia_com_escolha(self):
        return CadeiaDominialTabelaService().get_cadeia_dominial_tabela(
            self.tis.id, self.imovel.id,
            escolhas_origem_param={str(self.docs['T10786'].id): 'T3281'},
        )['cadeia']


class Forma384SemEscolhaTest(_Forma384, TestCase):
    """Trilha sem escolha (`obter_cadeia_tabela`): o tronco principal."""

    def test_linhas_na_ordem_canonica(self):
        cadeia = CadeiaDominialTabelaService().obter_cadeia_tabela(self.imovel)
        self.assertEqual(_numeros(cadeia), self.ORDEM_SEM_ESCOLHA)

    def test_pagina_renderiza_as_linhas_na_ordem_canonica(self):
        self._logar()
        response = self.client.get(reverse(
            'tronco_principal',
            kwargs={'tis_id': self.tis.id, 'imovel_id': self.imovel.id},
        ))
        self.assertEqual(response.status_code, 200)

        numero_por_id = {str(documento.id): numero for numero, documento in self.docs.items()}
        ids = re.findall(
            r'class="documento-row[^"]*" data-documento-id="(\d+)"',
            response.content.decode(),
        )
        self.assertEqual([numero_por_id[doc_id] for doc_id in ids], self.ORDEM_SEM_ESCOLHA)

    def test_chamadas_repetidas_dao_a_mesma_ordem(self):
        service = CadeiaDominialTabelaService()
        primeira = _numeros(service.obter_cadeia_tabela(self.imovel))
        # A segunda chamada lê o tronco principal do cache.
        segunda = _numeros(service.obter_cadeia_tabela(self.imovel))

        self.assertEqual(primeira, self.ORDEM_SEM_ESCOLHA)
        self.assertEqual(segunda, primeira)


class Forma384ComEscolhaTest(_Forma384, TestCase):
    """Trilha com escolha (`get_cadeia_dominial_tabela`): o tronco expandido.
    A expansão define quais documentos entram; a ordem é a canônica."""

    def test_linhas_na_ordem_canonica(self):
        self.assertEqual(_numeros(self._cadeia_com_escolha()), self.ORDEM_COM_ESCOLHA)

    def test_trilhas_sem_e_com_escolha_tem_a_mesma_ordem_relativa(self):
        sem_escolha = _numeros(CadeiaDominialTabelaService().obter_cadeia_tabela(self.imovel))
        com_escolha = _numeros(self._cadeia_com_escolha())

        self.assertEqual(
            [numero for numero in com_escolha if numero in sem_escolha],
            sem_escolha,
        )

    def test_api_devolve_as_linhas_na_ordem_canonica(self):
        # O JS re-renderiza a tabela exatamente na ordem do JSON da API.
        self._logar()
        url = reverse(
            'get_cadeia_dominial_atualizada',
            kwargs={'tis_id': self.tis.id, 'imovel_id': self.imovel.id},
        )

        payload = self.client.get(url).json()
        self.assertTrue(payload['success'])
        self.assertEqual(
            [item['documento']['numero'] for item in payload['cadeia']],
            self.ORDEM_SEM_ESCOLHA,
        )

        session = self.client.session
        session[f'origem_documento_{self.docs["T10786"].id}'] = 'T3281'
        session.save()

        payload = self.client.get(url).json()
        self.assertTrue(payload['success'])
        self.assertEqual(
            [item['documento']['numero'] for item in payload['cadeia']],
            self.ORDEM_COM_ESCOLHA,
        )

    def test_ordem_nao_depende_da_ordem_de_entrada(self):
        documentos = [item['documento'] for item in self._cadeia_com_escolha()]
        embaralhados = list(documentos)
        random.Random(201).shuffle(embaralhados)

        for entrada in (list(reversed(documentos)), embaralhados):
            self.assertEqual(
                [documento.numero for documento in ordenar_cadeia(entrada, self.imovel)],
                self.ORDEM_COM_ESCOLHA,
            )

    def test_chamadas_repetidas_dao_a_mesma_ordem(self):
        self.assertEqual(
            _numeros(self._cadeia_com_escolha()),
            _numeros(self._cadeia_com_escolha()),
        )


class _FormaTipoAbsoluto(_OrdemCadeiaFixture):
    """Forma do documento M7618 (imóvel 4), com origens
    `M6861; T17675; T21820; T3987`: M6861 é a menor delas em número.

    M6861, por sua vez, tem origens de tipos mistos (`T30000; M500`), para
    verificar a origem padrão de um documento importado na trilha com escolha.
    """

    ORIGENS_IMOVEL = {'M7618': 'M6861; T17675; T21820; T3987'}
    ORIGENS_OUTRO_IMOVEL = {
        'M6861': 'T30000; M500',
        'T17675': '',
        'T21820': '',
        'T3987': '',
        'T30000': '',
        'M500': '',
    }

    def _cadeia_com_escolha_t3987(self):
        return CadeiaDominialTabelaService().get_cadeia_dominial_tabela(
            self.tis.id, self.imovel.id,
            escolhas_origem_param={str(self.docs['M7618'].id): 'T3987'},
        )['cadeia']


class PrioridadeAbsolutaDeTipoTest(_FormaTipoAbsoluto, TestCase):
    """Qualquer matrícula vem antes de qualquer transcrição, mesmo que a
    transcrição tenha número maior."""

    def test_sem_escolha_botoes_padrao_e_tronco_seguem_a_matricula(self):
        cadeia = CadeiaDominialTabelaService().obter_cadeia_tabela(self.imovel)
        item_m7618 = _por_numero(cadeia)['M7618']

        self.assertEqual(_opcoes(item_m7618), ['M6861', 'T21820', 'T17675', 'T3987'])
        self.assertEqual(item_m7618['escolha_atual'], 'M6861')
        # A caminhada do tronco segue M6861 (antes seguia T21820, o maior número).
        self.assertEqual(
            [documento.numero for documento in identificar_tronco_principal(self.imovel)],
            ['M7618', 'M6861', 'M500'],
        )
        self.assertEqual(_numeros(cadeia), ['M7618', 'M6861', 'M500'])

    def test_com_escolha_linhas_poem_matricula_antes_de_transcricao_maior(self):
        cadeia = self._cadeia_com_escolha_t3987()
        item_m7618 = _por_numero(cadeia)['M7618']

        self.assertEqual(
            _numeros(cadeia),
            ['M7618', 'M6861', 'M500', 'T21820', 'T17675', 'T3987'],
        )
        self.assertEqual(_opcoes(item_m7618), ['M6861', 'T21820', 'T17675', 'T3987'])
        self.assertEqual(item_m7618['escolha_atual'], 'T3987')

    def test_com_escolha_origem_padrao_de_documento_importado_e_a_exibida(self):
        cadeia = self._cadeia_com_escolha_t3987()
        # M6861 entra como origem importada de M7618, sem escolha própria.
        item_m6861 = _por_numero(cadeia)['M6861']

        self.assertEqual(_opcoes(item_m6861), ['M500', 'T30000'])
        self.assertEqual(item_m6861['escolha_atual'], 'M500')
        # A subcadeia expandida é a da origem destacada, não a de maior número.
        self.assertIn('M500', _numeros(cadeia))
        self.assertNotIn('T30000', _numeros(cadeia))


class _FormaNumeroInteiro(_OrdemCadeiaFixture):
    """Forma do documento M6726 (imóvel 4), com 6 origens matrícula. Como texto,
    'M717' > 'M1612'; como número, M1612 é a maior. M717 e M1612 são do caso
    real; as outras 4 origens são ilustrativas."""

    ORIGENS_IMOVEL = {'M6726': 'M717; M1612; M1105; M698; M1250; M340'}
    ORIGENS_OUTRO_IMOVEL = dict.fromkeys(
        ['M717', 'M1612', 'M1105', 'M698', 'M1250', 'M340'], ''
    )
    ORDEM_ORIGENS = ['M1612', 'M1250', 'M1105', 'M717', 'M698', 'M340']


class OrigemPadraoEhAPrimeiraDaListaTest(_FormaNumeroInteiro, TestCase):
    """Regressão: a tabela destacava M717 (ordem de texto) enquanto a cadeia
    exibida seguia M1612 (ordem numérica)."""

    def test_sem_escolha_botao_destacado_e_a_origem_seguida(self):
        cadeia = CadeiaDominialTabelaService().obter_cadeia_tabela(self.imovel)
        item_m6726 = _por_numero(cadeia)['M6726']

        self.assertEqual(_opcoes(item_m6726), self.ORDEM_ORIGENS)
        self.assertEqual(
            item_m6726['escolha_atual'],
            item_m6726['origens_disponiveis'][0]['numero'],
        )
        self.assertEqual(
            [
                origem['numero']
                for origem in item_m6726['origens_disponiveis']
                if origem['escolhida']
            ],
            ['M1612'],
        )
        # A cadeia exibida segue a origem destacada.
        self.assertEqual(_numeros(cadeia), ['M6726', 'M1612'])

    def test_botoes_tem_a_mesma_ordem_nas_duas_trilhas(self):
        service = CadeiaDominialTabelaService()
        item_sem_escolha = _por_numero(service.obter_cadeia_tabela(self.imovel))['M6726']
        item_com_escolha = _por_numero(service.get_cadeia_dominial_tabela(
            self.tis.id, self.imovel.id,
            escolhas_origem_param={str(self.docs['M6726'].id): 'M717'},
        )['cadeia'])['M6726']

        self.assertEqual(_opcoes(item_sem_escolha), self.ORDEM_ORIGENS)
        self.assertEqual(_opcoes(item_com_escolha), self.ORDEM_ORIGENS)
        # A escolha explícita continua sendo a destacada.
        self.assertEqual(item_com_escolha['escolha_atual'], 'M717')


class _FormaCaminhadaForaDaOrdem(_OrdemCadeiaFixture):
    """Tronco cuja caminhada não segue a ordem canônica (numerações de
    cartórios diferentes): M100 (documento do imóvel) -> M5000 -> T300 -> T9000.
    As datas também divergem das duas ordens."""

    ORIGENS_IMOVEL = {'M100': 'M5000'}
    ORIGENS_OUTRO_IMOVEL = {'M5000': 'T300', 'T300': 'T9000', 'T9000': ''}
    DATAS = {'M100': date(2024, 1, 1), 'T9000': date(1950, 1, 1)}

    ORDEM_HIERARQUICA = ['M100', 'M5000', 'T300', 'T9000']
    ORDEM_CANONICA = ['M100', 'M5000', 'T9000', 'T300']


class DocumentoDoImovelPrimeiroTest(_FormaCaminhadaForaDaOrdem, TestCase):

    def test_documento_do_imovel_em_primeiro_mesmo_com_matricula_maior(self):
        service = CadeiaDominialTabelaService()
        sem_escolha = service.obter_cadeia_tabela(self.imovel)
        com_escolha = service.get_cadeia_dominial_tabela(
            self.tis.id, self.imovel.id,
            escolhas_origem_param={str(self.docs['M100'].id): 'M5000'},
        )['cadeia']

        self.assertEqual(_numeros(sem_escolha), self.ORDEM_CANONICA)
        self.assertEqual(_numeros(com_escolha), self.ORDEM_CANONICA)


class CacheDoTroncoPrincipalTest(_FormaCaminhadaForaDaOrdem, TestCase):
    """D5: `obter_cadeia_tabela` reordenava no lugar a lista entregue pelo
    cache do tronco principal."""

    def test_obter_cadeia_tabela_nao_reordena_o_tronco_do_cache(self):
        tronco = identificar_tronco_principal(self.imovel)
        self.assertEqual([documento.numero for documento in tronco], self.ORDEM_HIERARQUICA)
        CacheService.set_cached_tronco_principal(self.imovel.id, tronco)

        entregues = []
        ler_cache = CacheService.get_cached_tronco_principal

        def espiar_cache(*args, **kwargs):
            tronco_cacheado = ler_cache(*args, **kwargs)
            entregues.append(tronco_cacheado)
            return tronco_cacheado

        with mock.patch.object(
            CacheService, 'get_cached_tronco_principal', side_effect=espiar_cache
        ):
            cadeia = CadeiaDominialTabelaService().obter_cadeia_tabela(self.imovel)

        self.assertEqual(_numeros(cadeia), self.ORDEM_CANONICA)
        # A lista que o cache entregou continua em ordem hierárquica...
        self.assertEqual(len(entregues), 1)
        self.assertEqual(
            [documento.numero for documento in entregues[0]], self.ORDEM_HIERARQUICA
        )
        # ...assim como o valor armazenado.
        self.assertEqual(
            [
                documento.numero
                for documento in CacheService.get_cached_tronco_principal(self.imovel.id)
            ],
            self.ORDEM_HIERARQUICA,
        )


class OrigensDeChaveIdenticaTest(_OrdemCadeiaFixture, TestCase):
    """Códigos de chave idêntica (M0123 e M123 valem 123) ficam na ordem de
    leitura da origem, sem depender da ordem de iteração de um set."""

    ORIGENS_IMOVEL = {'M1': 'M0123; M123', 'M2': 'M123; M0123'}
    ORIGENS_OUTRO_IMOVEL = {'M0123': '', 'M123': ''}

    def test_botoes_mantem_a_ordem_de_leitura_nas_duas_trilhas(self):
        service = CadeiaDominialTabelaService()
        for numero, esperado in (('M1', ['M0123', 'M123']), ('M2', ['M123', 'M0123'])):
            documento = self.docs[numero]
            lancamentos = list(documento.lancamentos.select_related('tipo'))
            with self.subTest(documento=numero):
                self.assertEqual(
                    service._obter_origens_documento(documento, lancamentos), esperado
                )
                self.assertEqual(
                    [
                        origem['numero']
                        for origem in service._origens_disponiveis_lancamento(lancamentos[0])
                    ],
                    esperado,
                )
