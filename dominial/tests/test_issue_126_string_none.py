import json
from datetime import date
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth.models import User
from django.template import Context, Template
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from dominial.models import (
    Cartorios, Documento, DocumentoTipo, Imovel, Lancamento, LancamentoTipo,
    Pessoas, TIs, UserImovel,
)
from dominial.utils.formatacao_utils import normalizar_texto_opcional
from dominial.views.cadeia_dominial_views import cadeia_dominial_dados


class LimparNoneFilterTest(SimpleTestCase):
    def _renderizar_titulo(self, titulo):
        template = Template(
            "{% load dominial_extras %}"
            "{% with titulo_limpo=lancamento.titulo|limpar_none:'' %}"
            "{% if titulo_limpo %}TITULO:{{ titulo_limpo }}{% else %}SEM_TITULO{% endif %}"
            "{% endwith %}"
        )
        contexto = Context({'lancamento': SimpleNamespace(titulo=titulo)})
        return template.render(contexto)

    def test_limpar_none_converte_none_real_em_hifen(self):
        template = Template("{% load dominial_extras %}{{ valor|limpar_none }}")
        self.assertEqual(template.render(Context({'valor': None})), '-')

    def test_limpar_none_converte_string_none_em_hifen(self):
        template = Template("{% load dominial_extras %}{{ valor|limpar_none }}")
        self.assertEqual(template.render(Context({'valor': 'None'})), '-')

    def test_limpar_none_aceita_padrao_personalizado(self):
        template = Template("{% load dominial_extras %}{{ valor|limpar_none:'N/D' }}")
        self.assertEqual(template.render(Context({'valor': 'None'})), 'N/D')

    def test_limpar_none_trata_string_vazia_e_espacos_como_ausente(self):
        template = Template("{% load dominial_extras %}{{ valor|limpar_none }}")
        self.assertEqual(template.render(Context({'valor': ''})), '-')
        self.assertEqual(template.render(Context({'valor': '   '})), '-')

    def test_limpar_none_preserva_texto_valido(self):
        template = Template("{% load dominial_extras %}{{ valor|limpar_none }}")
        self.assertEqual(template.render(Context({'valor': 'Compra e Venda'})), 'Compra e Venda')

    def test_limpar_none_preserva_zero_e_false(self):
        self.assertEqual(normalizar_texto_opcional(0), 0)
        self.assertEqual(normalizar_texto_opcional(False), False)

    def test_normalizador_pode_retornar_none_para_json(self):
        self.assertIsNone(normalizar_texto_opcional(None))
        self.assertIsNone(normalizar_texto_opcional('None'))
        self.assertIsNone(normalizar_texto_opcional(''))
        self.assertEqual(normalizar_texto_opcional('Titulo valido'), 'Titulo valido')

    def test_condicional_de_titulo_nao_renderiza_string_none(self):
        self.assertEqual(self._renderizar_titulo('None'), 'SEM_TITULO')
        self.assertEqual(self._renderizar_titulo(None), 'SEM_TITULO')
        self.assertEqual(self._renderizar_titulo('Título Real'), 'TITULO:Título Real')


class _Issue126EndpointFixture:
    """Mixin de fixtures para os testes de endpoint da issue #126.

    Não herda de TestCase para não ser coletado como um caso de teste
    vazio. Classes filhas devem herdar de (_Issue126EndpointFixture, TestCase).
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='issue126ep', password='issue126pass')
        cls.tis = TIs.objects.create(nome='TI 126 Endpoint', codigo='TI-126-EP', etnia='Teste')
        cls.pessoa = Pessoas.objects.create(nome='Pessoa 126 Endpoint')
        cls.cartorio = Cartorios.objects.create(
            nome='Cartório 126 Endpoint', cns='CNS-126-EP', cidade='Cidade Teste', estado='TS',
        )
        cls.imovel = Imovel.objects.create(
            terra_indigena_id=cls.tis,
            nome='Imóvel 126 Endpoint',
            proprietario=cls.pessoa,
            matricula='126-EP',
            tipo_documento_principal='matricula',
            cartorio=cls.cartorio,
        )
        cls.doc_tipo = DocumentoTipo.objects.create(tipo='matricula')
        cls.lanc_tipo = LancamentoTipo.objects.create(tipo='averbacao')
        cls.documento = Documento.objects.create(
            imovel=cls.imovel,
            tipo=cls.doc_tipo,
            numero='M-126-EP',
            data=date(2026, 1, 1),
            cartorio=cls.cartorio,
            livro='1',
            folha='1',
        )
        # Segregação (#132): o usuário comum só enxerga imóveis atribuídos a ele.
        UserImovel.objects.create(user=cls.user, imovel=cls.imovel)

    def _criar_lancamento(self, **kwargs):
        dados = dict(documento=self.documento, tipo=self.lanc_tipo, data=date(2026, 1, 1))
        dados.update(kwargs)
        return Lancamento.objects.create(**dados)

    def _mock_tronco_principal(self):
        return mock.patch(
            'dominial.services.hierarquia_service.HierarquiaService.obter_tronco_principal',
            return_value=[self.documento],
        )


class CadeiaDominialDadosSerializaTituloTest(_Issue126EndpointFixture, TestCase):
    """Cobre `cadeia_dominial_views.cadeia_dominial_dados` (JSON da árvore)."""

    def test_cadeia_dominial_dados_serializa_titulo_none_textual_como_vazio(self):
        lancamento = self._criar_lancamento(titulo='None')

        request = RequestFactory().get('/fake-cadeia-dominial-dados/')
        request.user = self.user

        with self._mock_tronco_principal():
            response = cadeia_dominial_dados(request, tis_id=self.tis.id, imovel_id=self.imovel.id)

        payload = json.loads(response.content)
        lancamentos_serializados = payload['children'][0]['children']
        alvo = next(l for l in lancamentos_serializados if l['data']['id'] == lancamento.id)

        self.assertEqual(alvo['data']['titulo'], '')


class ApiCadeiaAtualizadaSerializaCamposTest(_Issue126EndpointFixture, TestCase):
    """Cobre `api_views.get_cadeia_dominial_atualizada` (JSON consumido pelo front)."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        self.url = reverse(
            'get_cadeia_dominial_atualizada',
            kwargs={'tis_id': self.tis.id, 'imovel_id': self.imovel.id},
        )

    def test_api_cadeia_atualizada_serializa_titulo_none_textual_como_null(self):
        lancamento = self._criar_lancamento(titulo='None')

        with self._mock_tronco_principal():
            response = self.client.get(self.url)

        payload = response.json()
        self.assertTrue(payload['success'])
        lancamentos_serializados = payload['cadeia'][0]['lancamentos']
        alvo = next(l for l in lancamentos_serializados if l['id'] == lancamento.id)

        self.assertIsNone(alvo['titulo'])

    def test_api_normaliza_demais_campos_textuais_suscetiveis(self):
        campos_normalizados = (
            'numero_lancamento', 'forma', 'titulo', 'descricao',
            'origem', 'observacoes', 'livro_transacao', 'folha_transacao',
        )
        lancamento = self._criar_lancamento(**{campo: 'None' for campo in campos_normalizados})

        with self._mock_tronco_principal():
            response = self.client.get(self.url)

        payload = response.json()
        lancamentos_serializados = payload['cadeia'][0]['lancamentos']
        alvo = next(l for l in lancamentos_serializados if l['id'] == lancamento.id)

        for campo in campos_normalizados:
            self.assertIsNone(alvo[campo], f'{campo} deveria ser null, veio {alvo[campo]!r}')
