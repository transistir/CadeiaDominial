"""
Issue #201 — escolha de origem na tabela da cadeia dominial.

Bug de produção (imóvel 384): ao escolher uma das origens de uma transcrição
compartilhada com origem dupla, os documentos importados abaixo da origem
escolhida sumiam da tabela. O servidor devolvia a cadeia correta; quem os
escondia era o JS (`atualizarTabelaCadeia` em
`static/dominial/js/cadeia_dominial_tabela.js`), que aplicava a escolha do
primeiro documento ambíguo a todos os documentos compartilhados e ocultava os
que não fossem a origem escolhida. Além disso, o re-render via AJAX formatava
área/origem de modo diferente do template server-side (filtros `area_ha` e
`origem_formatada_completa`).

A correção remove o filtro do JS e faz `get_cadeia_dominial_atualizada`
(`dominial/views/api_views.py`) devolver `area_formatada`/`origem_formatada`,
calculados pelas mesmas funções de `dominial/utils/formatacao_utils.py` usadas
pelo template (sem duplicar a regra no JS).

Estes testes fixam o comportamento do servidor definido na continuação da
issue #201: com ou sem escolha, a tabela mostra apenas um tronco, na ordem da
caminhada hierárquica. Entre as origens irmãs de um documento, a chave
canônica decide a origem padrão; os demais galhos não viram linhas.

Fixture (espelha os imóveis de produção 384/358): um imóvel A analisado
(matrícula M100, tronco linear) cuja matrícula tem uma única origem
(T10786, transcrição pertencente a um imóvel B). T10786 tem DUAS origens
(T3280 e T3281) — o ponto de escolha do usuário. T3280 leva a um fim de
cadeia (T2391, "Destacamento Público"); T3281 leva a uma subcadeia mais
longa (T9001 -> T4558, fim de cadeia implícito por origem vazia).
"""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.template import Context, Template
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils.html import escape

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
from dominial.services.cadeia_dominial_tabela_service import CadeiaDominialTabelaService


class _Issue201Fixture:
    """Mixin de fixture para os testes da issue #201.

    Não herda de TestCase para não ser coletado como um caso de teste
    vazio. Classes filhas devem herdar de (_Issue201Fixture, TestCase).
    """

    def setUp(self):
        super().setUp()
        # O tronco principal é cacheado por id de imóvel (LocMemCache,
        # `CacheService.get/set_cached_tronco_principal`). Como os ids são
        # reaproveitados entre testes (rollback de transação), é preciso
        # limpar o cache a cada teste.
        cache.clear()

        self.user = User.objects.create_user(username='issue201', password='issue201pass')

        self.tis = TIs.objects.create(nome='TI 201', codigo='TI-201', etnia='Teste')

        # Nome com "&" para exercitar a paridade de escape HTML entre a API
        # e o template (issue #201).
        self.cartorio = Cartorios.objects.create(
            nome='Cartório de Registro de Imóveis & Anexos 201',
            cns='CNS-201',
            cidade='Cidade 201',
            estado='TS',
        )
        self.nome_cartorio_escapado = escape(self.cartorio.nome)

        self.proprietario = Pessoas.objects.create(nome='Proprietario 201')

        self.tipo_matricula = DocumentoTipo.objects.create(tipo='matricula')
        self.tipo_transcricao = DocumentoTipo.objects.create(tipo='transcricao')
        self.tipo_inicio = LancamentoTipo.objects.create(tipo='inicio_matricula')

        # Imóvel A: o imóvel analisado. Sua matrícula (M100) tem uma única
        # origem (T10786), que pertence ao imóvel B.
        self.imovel_a = Imovel.objects.create(
            terra_indigena_id=self.tis,
            nome='Imóvel A 201',
            proprietario=self.proprietario,
            matricula='M100',
            tipo_documento_principal='matricula',
            cartorio=self.cartorio,
        )
        # Imóvel B: o outro imóvel, dono de toda a cadeia de transcrições
        # importada por A. Não precisa de documento próprio para M358.
        self.imovel_b = Imovel.objects.create(
            terra_indigena_id=self.tis,
            nome='Imóvel B 201',
            proprietario=self.proprietario,
            matricula='M358',
            tipo_documento_principal='matricula',
            cartorio=self.cartorio,
        )

        self.doc_m100 = Documento.objects.create(
            imovel=self.imovel_a, tipo=self.tipo_matricula, numero='M100',
            data=date(2020, 1, 10), cartorio=self.cartorio, livro='1', folha='1',
        )
        self.doc_t10786 = Documento.objects.create(
            imovel=self.imovel_b, tipo=self.tipo_transcricao, numero='T10786',
            data=date(2015, 6, 1), cartorio=self.cartorio, livro='2', folha='2',
        )
        self.doc_t3280 = Documento.objects.create(
            imovel=self.imovel_b, tipo=self.tipo_transcricao, numero='T3280',
            data=date(2010, 3, 1), cartorio=self.cartorio, livro='3', folha='3',
        )
        self.doc_t3281 = Documento.objects.create(
            imovel=self.imovel_b, tipo=self.tipo_transcricao, numero='T3281',
            data=date(2012, 8, 1), cartorio=self.cartorio, livro='4', folha='4',
        )
        self.doc_t2391 = Documento.objects.create(
            imovel=self.imovel_b, tipo=self.tipo_transcricao, numero='T2391',
            data=date(2005, 1, 1), cartorio=self.cartorio, livro='5', folha='5',
        )
        self.doc_t9001 = Documento.objects.create(
            imovel=self.imovel_b, tipo=self.tipo_transcricao, numero='T9001',
            data=date(2008, 4, 1), cartorio=self.cartorio, livro='6', folha='6',
        )
        self.doc_t4558 = Documento.objects.create(
            imovel=self.imovel_b, tipo=self.tipo_transcricao, numero='T4558',
            data=date(2001, 1, 1), cartorio=self.cartorio, livro='7', folha='7',
        )

        # bulk_create para não disparar o signal `processar_origens_automaticas_signal`
        # (dominial/signals.py), que criaria documentos automáticos a partir
        # da string de origem e poluiria a fixture.
        Lancamento.objects.bulk_create([
            Lancamento(
                documento=self.doc_m100, tipo=self.tipo_inicio,
                data=date(2020, 1, 10), cartorio_origem=self.cartorio,
                origem='T10786', area=Decimal('1234.5678'),
            ),
            Lancamento(
                documento=self.doc_t10786, tipo=self.tipo_inicio,
                data=date(2015, 6, 1), cartorio_origem=self.cartorio,
                origem='T3280; T3281', area=None,
            ),
            Lancamento(
                documento=self.doc_t3280, tipo=self.tipo_inicio,
                data=date(2010, 3, 1), cartorio_origem=self.cartorio,
                origem='T2391', area=Decimal('0'),
            ),
            Lancamento(
                documento=self.doc_t3281, tipo=self.tipo_inicio,
                data=date(2012, 8, 1), cartorio_origem=self.cartorio,
                origem='T9001',
            ),
            Lancamento(
                documento=self.doc_t2391, tipo=self.tipo_inicio,
                data=date(2005, 1, 1), cartorio_origem=self.cartorio,
                origem='Destacamento Público:INCRA:origem_lidima',
            ),
            Lancamento(
                documento=self.doc_t9001, tipo=self.tipo_inicio,
                data=date(2008, 4, 1), cartorio_origem=self.cartorio,
                origem='T4558',
            ),
            Lancamento(
                documento=self.doc_t4558, tipo=self.tipo_inicio,
                data=date(2001, 1, 1), cartorio_origem=self.cartorio,
                origem='',
            ),
        ])

    # -- Helpers ----------------------------------------------------------

    def _numeros_service(self, cadeia):
        """Números de documento, na ordem devolvida pelo service."""
        return [item['documento'].numero for item in cadeia]

    def _numeros_api(self, cadeia_json):
        """Números de documento, na ordem devolvida pela API."""
        return [item['documento']['numero'] for item in cadeia_json]


class ServicoSemEscolhaTest(_Issue201Fixture, TestCase):
    """Comportamento 1: sem escolha, o serviço segue o tronco linear."""

    def test_tronco_sem_escolha_segue_a_origem_de_maior_numero(self):
        cadeia = CadeiaDominialTabelaService().obter_cadeia_tabela(self.imovel_a)
        # Garante a caminhada hierárquica pela origem padrão entre as irmãs.
        self.assertEqual(
            self._numeros_service(cadeia),
            ['M100', 'T10786', 'T3281', 'T9001', 'T4558'],
        )


class ServicoComEscolhaTest(_Issue201Fixture, TestCase):
    """Comportamento 2: com escolha, só o tronco da origem escolhida aparece."""

    def test_escolha_t3280_segue_apenas_o_tronco_ate_t2391(self):
        service = CadeiaDominialTabelaService()
        resultado = service.get_cadeia_dominial_tabela(
            self.tis.id, self.imovel_a.id,
            escolhas_origem_param={str(self.doc_t10786.id): 'T3280'},
        )
        numeros = self._numeros_service(resultado['cadeia'])
        # Garante hierarquia e ausência do galho irmão iniciado por T3281.
        self.assertEqual(
            numeros,
            ['M100', 'T10786', 'T3280', 'T2391'],
        )

    def test_escolha_t3281_segue_apenas_o_tronco_ate_t4558(self):
        service = CadeiaDominialTabelaService()
        resultado = service.get_cadeia_dominial_tabela(
            self.tis.id, self.imovel_a.id,
            escolhas_origem_param={str(self.doc_t10786.id): 'T3281'},
        )
        numeros = self._numeros_service(resultado['cadeia'])
        # Garante hierarquia e ausência do galho irmão iniciado por T3280.
        self.assertEqual(
            numeros,
            ['M100', 'T10786', 'T3281', 'T9001', 'T4558'],
        )


class OrigensDisponiveisTest(_Issue201Fixture, TestCase):
    """Comportamento 3: metadados de múltiplas origens/escolha atual."""

    def test_com_escolha_t3280_marca_origem_e_remove_galho_t3281(self):
        service = CadeiaDominialTabelaService()
        resultado = service.get_cadeia_dominial_tabela(
            self.tis.id, self.imovel_a.id,
            escolhas_origem_param={str(self.doc_t10786.id): 'T3280'},
        )
        por_numero = {
            item['documento'].numero: item for item in resultado['cadeia']
        }

        # Garante que o irmão não escolhido T3281 não aparece na tabela.
        self.assertEqual(list(por_numero), ['M100', 'T10786', 'T3280', 'T2391'])
        self.assertNotIn('T3281', por_numero)

        item_t10786 = por_numero['T10786']
        self.assertTrue(item_t10786['tem_multiplas_origens'])
        self.assertEqual(
            item_t10786['origens_disponiveis'],
            [
                {
                    'numero': 'T3281',
                    'identidade': f'documento:{self.doc_t3281.id}',
                    'escolhida': False,
                },
                {
                    'numero': 'T3280',
                    'identidade': f'documento:{self.doc_t3280.id}',
                    'escolhida': True,
                },
            ],
        )
        self.assertEqual(item_t10786['escolha_atual'], 'T3280')

        for numero in ('M100', 'T3280', 'T2391'):
            self.assertFalse(
                por_numero[numero]['tem_multiplas_origens'],
                f'{numero} não deveria ter múltiplas origens',
            )

    def test_sem_escolha_marca_t3281_como_escolha_padrao(self):
        cadeia = CadeiaDominialTabelaService().obter_cadeia_tabela(self.imovel_a)
        por_numero = {item['documento'].numero: item for item in cadeia}

        item_t10786 = por_numero['T10786']
        self.assertTrue(item_t10786['tem_multiplas_origens'])
        self.assertEqual(item_t10786['escolha_atual'], 'T3281')

        escolhidas = {
            origem['numero']: origem['escolhida']
            for origem in item_t10786['origens_disponiveis']
        }
        self.assertTrue(escolhidas['T3281'])
        self.assertFalse(escolhidas['T3280'])


class EndpointEscolhaOrigemTest(_Issue201Fixture, TestCase):
    """Comportamento 4: fluxo real via endpoints (sessão), sem mocks."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        self.url_api = reverse(
            'get_cadeia_dominial_atualizada',
            kwargs={'tis_id': self.tis.id, 'imovel_id': self.imovel_a.id},
        )
        self.url_escolher = reverse('escolher_origem_documento')

    def test_escolher_origem_via_post_substitui_o_tronco_no_get_seguinte(self):
        payload_inicial = self.client.get(self.url_api).json()
        self.assertTrue(payload_inicial['success'])
        # Garante a ordem literal do tronco padrão antes da escolha via POST.
        self.assertEqual(
            self._numeros_api(payload_inicial['cadeia']),
            ['M100', 'T10786', 'T3281', 'T9001', 'T4558'],
        )

        resposta_post = self.client.post(
            self.url_escolher,
            data=json.dumps({
                'documento_id': self.doc_t10786.id,
                'origem_numero': 'T3280',
                'tis_id': self.tis.id,
                'imovel_id': self.imovel_a.id,
            }),
            content_type='application/json',
        )
        self.assertTrue(resposta_post.json()['success'])

        payload_final = self.client.get(self.url_api).json()
        self.assertTrue(payload_final['success'])
        self.assertEqual(
            self._numeros_api(payload_final['cadeia']),
            ['M100', 'T10786', 'T3280', 'T2391'],
        )

        item_t10786 = next(
            item for item in payload_final['cadeia']
            if item['documento']['numero'] == 'T10786'
        )
        self.assertTrue(item_t10786['tem_multiplas_origens'])
        self.assertEqual(item_t10786['escolha_atual'], 'T3280')
        escolhidas = {
            origem['numero']: origem['escolhida']
            for origem in item_t10786['origens_disponiveis']
        }
        self.assertTrue(escolhidas['T3280'])
        self.assertFalse(escolhidas['T3281'])


class ApiCamposFormatadosTest(_Issue201Fixture, TestCase):
    """Comportamento 5: `area_formatada`/`origem_formatada` na API (#201)."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        url_api = reverse(
            'get_cadeia_dominial_atualizada',
            kwargs={'tis_id': self.tis.id, 'imovel_id': self.imovel_a.id},
        )
        # Escolher T3280 para verificar os campos nas quatro linhas desse tronco.
        session = self.client.session
        session[f'origem_documento_{self.doc_t10786.id}'] = 'T3280'
        session.save()

        payload = self.client.get(url_api).json()
        self.assertTrue(payload['success'])
        self.assertEqual(
            self._numeros_api(payload['cadeia']),
            ['M100', 'T10786', 'T3280', 'T2391'],
        )
        # Cada documento da fixture tem exatamente um lançamento.
        self.lancamento_por_doc = {
            item['documento']['numero']: item['lancamentos'][0]
            for item in payload['cadeia']
        }

    def test_todos_os_lancamentos_tem_campos_formatados_e_brutos(self):
        # Garante o contrato formatado e bruto em todo o tronco escolhido.
        for numero, lancamento in self.lancamento_por_doc.items():
            self.assertIn('area_formatada', lancamento, numero)
            self.assertIn('origem_formatada', lancamento, numero)
            # As chaves brutas continuam presentes (testes existentes contam com elas).
            self.assertIn('area', lancamento, numero)
            self.assertIn('origem', lancamento, numero)

    def test_m100_area_formatada_em_padrao_brasileiro(self):
        # Garante que a raiz do tronco mantém a área no padrão brasileiro.
        self.assertEqual(
            self.lancamento_por_doc['M100']['area_formatada'], '1234,5678'
        )

    def test_t10786_area_e_origem_formatadas_com_dupla_origem(self):
        # Garante que os botões irmãos não alteram a origem formatada da linha.
        lancamento = self.lancamento_por_doc['T10786']
        self.assertEqual(lancamento['area_formatada'], '-')
        esperado = (
            f'T3280 ({self.nome_cartorio_escapado})<br>'
            f'T3281 ({self.nome_cartorio_escapado})'
        )
        self.assertEqual(lancamento['origem_formatada'], esperado)

    def test_t3280_area_zero_formatada_como_traco(self):
        # Garante que a origem escolhida mantém área zero representada por traço.
        self.assertEqual(
            self.lancamento_por_doc['T3280']['area_formatada'], '-'
        )

    def test_t2391_origem_de_fim_de_cadeia_formatada(self):
        # Garante a formatação do fim do tronco escolhido.
        self.assertEqual(
            self.lancamento_por_doc['T2391']['origem_formatada'],
            'Destacamento Público : INCRA (Origem Lídima)',
        )


class ParidadeTemplateTest(_Issue201Fixture, TestCase):
    """Comportamento 6: os campos formatados da API batem exatamente com
    os filtros de template usados na renderização server-side."""

    def test_campos_formatados_da_api_batem_com_os_filtros_do_template(self):
        # Garante paridade de formatação nas quatro linhas do galho escolhido.
        self.client.force_login(self.user)
        url_api = reverse(
            'get_cadeia_dominial_atualizada',
            kwargs={'tis_id': self.tis.id, 'imovel_id': self.imovel_a.id},
        )
        session = self.client.session
        session[f'origem_documento_{self.doc_t10786.id}'] = 'T3280'
        session.save()

        payload = self.client.get(url_api).json()
        self.assertTrue(payload['success'])

        template_area = Template(
            "{% load dominial_extras %}{{ lancamento.area|area_ha }}"
        )
        template_origem = Template(
            "{% load dominial_extras %}"
            "{% if lancamento.origem %}{{ lancamento|origem_formatada_completa|safe }}"
            "{% else %}-{% endif %}"
        )

        total_verificado = 0
        for item in payload['cadeia']:
            for lancamento_serializado in item['lancamentos']:
                lancamento = Lancamento.objects.get(id=lancamento_serializado['id'])
                contexto = Context({'lancamento': lancamento})

                self.assertEqual(
                    template_area.render(contexto),
                    lancamento_serializado['area_formatada'],
                )
                self.assertEqual(
                    template_origem.render(contexto),
                    lancamento_serializado['origem_formatada'],
                )
                total_verificado += 1

        # Os quatro lançamentos do tronco escolhido, um por documento.
        self.assertEqual(total_verificado, 4)


class ParidadePaginaTest(_Issue201Fixture, TestCase):
    """Comportamento 7: a página `tronco_principal` (render server-side)
    mostra os mesmos valores formatados que a API retorna."""

    def test_pagina_tronco_principal_renderiza_valores_formatados(self):
        self.client.force_login(self.user)
        kwargs = {'tis_id': self.tis.id, 'imovel_id': self.imovel_a.id}

        # Sem escolha, a página e a API partem do mesmo conjunto de documentos.
        payload = self.client.get(
            reverse('get_cadeia_dominial_atualizada', kwargs=kwargs)
        ).json()
        self.assertTrue(payload['success'])
        lancamento_por_doc = {
            item['documento']['numero']: item['lancamentos'][0]
            for item in payload['cadeia']
        }
        area_m100 = lancamento_por_doc['M100']['area_formatada']
        origem_t10786 = lancamento_por_doc['T10786']['origem_formatada']
        # Valores concretos, para a comparação abaixo não passar com campos vazios.
        self.assertEqual(area_m100, '1234,5678')
        self.assertIn(self.nome_cartorio_escapado, origem_t10786)

        response = self.client.get(reverse('tronco_principal', kwargs=kwargs))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()

        self.assertIn(f'<td>{area_m100}</td>', html)
        self.assertIn(origem_t10786, html)


class TabelaJsRenderizaOQueOServidorEnviaTest(SimpleTestCase):
    """Comportamento 8: o re-render JS não filtra documentos nem reformata
    área/origem por conta própria.

    O bug de produção do #201 estava no JS: `atualizarTabelaCadeia` ocultava
    (classe `documento-oculto`) documentos que o servidor devolvia. Enquanto
    o repositório não tem testes de JS, esta verificação estática do código
    impede que o filtro e o formatador duplicado voltem.
    """

    DIRETORIO_STATIC = Path(settings.STATICFILES_DIRS[0]) / 'dominial'

    def test_js_nao_filtra_documentos_nem_duplica_formatadores(self):
        codigo = (
            self.DIRETORIO_STATIC / 'js' / 'cadeia_dominial_tabela.js'
        ).read_text(encoding='utf-8')

        for trecho in (
            'deveExibir',
            'origemEscolhidaGlobal',
            'documento-oculto',
            'formatarOrigemCompleta',
        ):
            self.assertNotIn(trecho, codigo)

        self.assertIn('lancamento.area_formatada', codigo)
        self.assertIn('lancamento.origem_formatada', codigo)

    def test_css_nao_define_classe_documento_oculto(self):
        estilos = (
            self.DIRETORIO_STATIC / 'css' / 'cadeia_dominial_tabela.css'
        ).read_text(encoding='utf-8')

        self.assertNotIn('.documento-oculto', estilos)
