"""Testes do select de siglas de destacamento do patrimônio público (issue #104)."""

from importlib import import_module

from django.apps import apps
from django.template.loader import render_to_string
from django.test import TestCase, RequestFactory
from django.utils import timezone

from dominial.models import (
    TIs, Pessoas, Imovel, Cartorios,
    DocumentoTipo, LancamentoTipo,
    Documento, Lancamento, OrigemFimCadeia, FimCadeia,
)
from dominial.services.hierarquia_arvore_service import HierarquiaArvoreService
from dominial.services.lancamento_campos_service import LancamentoCamposService
from dominial.views.lancamento_views import _build_fim_cadeia_opcoes

SEED = import_module('dominial.migrations.0053_seed_fim_cadeia_destacamento_publico')


class SeedFimCadeiaTest(TestCase):
    """A migração de dados semeia os 27 estados + as 2 coroas imperiais."""

    def setUp(self):
        # A própria migração já semeou o banco de teste; partir do zero para
        # exercitar a função de seed em si
        FimCadeia.objects.all().delete()

    def test_semeia_29_destacamentos(self):
        SEED.semear_destacamentos(apps, None)
        self.assertEqual(
            FimCadeia.objects.filter(tipo='destacamento_publico', ativo=True).count(),
            29,
        )

    def test_semeia_estados_e_coroas_com_sigla(self):
        SEED.semear_destacamentos(apps, None)
        self.assertEqual(FimCadeia.objects.get(nome='Estado da Bahia').sigla, 'BA')
        self.assertEqual(FimCadeia.objects.get(nome='Distrito Federal').sigla, 'DF')
        self.assertEqual(
            FimCadeia.objects.get(nome='Coroa do Império Brasileiro').sigla, 'IMP-BR'
        )
        self.assertEqual(
            FimCadeia.objects.get(nome='Coroa do Império Português').sigla, 'IMP-PT'
        )

    def test_semear_duas_vezes_nao_duplica(self):
        SEED.semear_destacamentos(apps, None)
        SEED.semear_destacamentos(apps, None)
        self.assertEqual(FimCadeia.objects.count(), 29)

    def test_semear_nao_sobrescreve_registro_existente(self):
        """get_or_create por nome preserva ajustes feitos no admin."""
        FimCadeia.objects.create(
            nome='Estado da Bahia',
            tipo='destacamento_publico',
            classificacao='inconclusa',
            sigla='BAHIA',
        )
        SEED.semear_destacamentos(apps, None)
        self.assertEqual(FimCadeia.objects.get(nome='Estado da Bahia').sigla, 'BAHIA')
        self.assertEqual(FimCadeia.objects.count(), 29)


class FimCadeiaOpcoesTest(TestCase):
    """Opções oferecidas ao formulário."""

    def setUp(self):
        FimCadeia.objects.all().delete()
        FimCadeia.objects.create(
            nome='Estado da Bahia', tipo='destacamento_publico',
            classificacao='origem_lidima', sigla='BA',
        )
        FimCadeia.objects.create(
            nome='Estado do Acre', tipo='destacamento_publico',
            classificacao='origem_lidima', sigla='AC',
        )

    def test_ordenadas_por_nome(self):
        # 'Estado da Bahia' vem antes de 'Estado do Acre' na ordem por nome
        opcoes = _build_fim_cadeia_opcoes()
        self.assertEqual([o['sigla'] for o in opcoes], ['BA', 'AC'])

    def test_ignora_inativos(self):
        FimCadeia.objects.filter(nome='Estado do Acre').update(ativo=False)
        self.assertEqual([o['sigla'] for o in _build_fim_cadeia_opcoes()], ['BA'])

    def test_ignora_outros_tipos(self):
        FimCadeia.objects.create(
            nome='Outra coisa', tipo='outra',
            classificacao='inconclusa', sigla='XX',
        )
        self.assertEqual([o['sigla'] for o in _build_fim_cadeia_opcoes()], ['BA', 'AC'])

    def test_ignora_cadastro_sem_sigla(self):
        """Sem sigla não há valor para gravar no lançamento."""
        FimCadeia.objects.create(
            nome='Sem sigla', tipo='destacamento_publico',
            classificacao='origem_lidima', sigla='',
        )
        FimCadeia.objects.create(
            nome='Sigla nula', tipo='destacamento_publico',
            classificacao='origem_lidima', sigla=None,
        )
        self.assertEqual([o['sigla'] for o in _build_fim_cadeia_opcoes()], ['BA', 'AC'])


class FimCadeiaDestacamentoTemplateTest(TestCase):
    """Renderização do bloco select + informação adicional."""

    def _renderizar(self, **contexto):
        base = {
            'indice': 0,
            'sigla_selecionada': '',
            'info_adicional': '',
            'visivel': False,
            'fim_cadeia_opcoes': [
                {'nome': 'Estado da Bahia', 'sigla': 'BA'},
                {'nome': 'Coroa do Império Brasileiro', 'sigla': 'IMP-BR'},
            ],
        }
        base.update(contexto)
        return render_to_string(
            'dominial/components/_fim_cadeia_destacamento_fields.html', base
        )

    def test_renderiza_select_com_opcoes(self):
        html = self._renderizar()
        self.assertIn('<select name="sigla_patrimonio_publico[]"', html)
        self.assertIn('<option value="BA">BA — Estado da Bahia</option>', html)
        self.assertIn(
            '<option value="IMP-BR">IMP-BR — Coroa do Império Brasileiro</option>', html
        )

    def test_renderiza_input_de_informacao_adicional(self):
        html = self._renderizar(info_adicional='Secretaria de Terras')
        self.assertIn('name="info_adicional_fim_cadeia[]"', html)
        self.assertIn('Informação adicional', html)
        self.assertIn('value="Secretaria de Terras"', html)

    def test_campos_ficam_no_mesmo_container(self):
        """Select e informação adicional dividem o div sigla-patrimonio-container."""
        html = self._renderizar()
        container = html.split('id="sigla-patrimonio-container_0"', 1)[1]
        self.assertIn('sigla_patrimonio_publico_0', container)
        self.assertIn('info_adicional_fim_cadeia_0', container)

    def test_sigla_gravada_vai_para_data_attribute(self):
        """Valor legado de texto livre é preservado para o JS reinserir no select."""
        html = self._renderizar(sigla_selecionada='INCRA')
        self.assertIn('data-sigla-selecionada="INCRA"', html)

    def test_visivel_controla_display(self):
        self.assertIn('display: none;', self._renderizar())
        self.assertIn('display: block;', self._renderizar(visivel=True))


class InfoAdicionalPersistenciaTest(TestCase):
    """A informação adicional é gravada em OrigemFimCadeia."""

    def setUp(self):
        self.factory = RequestFactory()
        tis = TIs.objects.create(nome='TI Teste', codigo='T104', etnia='Teste')
        cartorio = Cartorios.objects.create(
            nome='Cartório Teste', cns='104104', cidade='Cidade', estado='TS'
        )
        proprietario = Pessoas.objects.create(nome='Proprietário', cpf='10410410410')
        imovel = Imovel.objects.create(
            terra_indigena_id=tis, nome='Imóvel Teste', proprietario=proprietario,
            matricula='M104', cartorio=cartorio,
        )
        documento = Documento.objects.create(
            imovel=imovel, tipo=DocumentoTipo.objects.create(tipo='matricula'),
            numero='M104', data=timezone.now().date(), cartorio=cartorio,
            livro='1', folha='1',
        )
        self.lancamento = Lancamento.objects.create(
            documento=documento,
            tipo=LancamentoTipo.objects.create(tipo='inicio_matricula'),
            data=timezone.now().date(), origem='',
        )

    def _postar(self, **extra):
        dados = {
            'origem_completa[]': ['Destacamento Público:BA:origem_lidima'],
            'fim_cadeia[]': ['0'],
            'tipo_fim_cadeia[]': ['destacamento_publico'],
            'classificacao_fim_cadeia[]': ['origem_lidima'],
            'sigla_patrimonio_publico[]': ['BA'],
            'especificacao_fim_cadeia[]': [''],
        }
        dados.update(extra)
        request = self.factory.post('/', dados)
        LancamentoCamposService._processar_campos_inicio_matricula(request, self.lancamento)

    def test_grava_info_adicional(self):
        self._postar(**{'info_adicional_fim_cadeia[]': ['Secretaria de Terras']})
        origem_fc = OrigemFimCadeia.objects.get(lancamento=self.lancamento, indice_origem=0)
        self.assertEqual(origem_fc.info_adicional_fim_cadeia, 'Secretaria de Terras')

    def test_info_adicional_vazia_vira_none(self):
        self._postar(**{'info_adicional_fim_cadeia[]': ['   ']})
        origem_fc = OrigemFimCadeia.objects.get(lancamento=self.lancamento, indice_origem=0)
        self.assertIsNone(origem_fc.info_adicional_fim_cadeia)

    def test_post_sem_campo_nao_quebra(self):
        """Posts antigos (sem o campo novo) continuam funcionando."""
        self._postar()
        origem_fc = OrigemFimCadeia.objects.get(lancamento=self.lancamento, indice_origem=0)
        self.assertIsNone(origem_fc.info_adicional_fim_cadeia)
        self.assertEqual(origem_fc.tipo_fim_cadeia, 'destacamento_publico')


class NoFimCadeiaInfoAdicionalTest(TestCase):
    """O nó da árvore D3 carrega a informação adicional para o painel lateral."""

    def setUp(self):
        tis = TIs.objects.create(nome='TI Teste', codigo='T105', etnia='Teste')
        cartorio = Cartorios.objects.create(
            nome='Cartório Teste', cns='105105', cidade='Cidade', estado='TS'
        )
        proprietario = Pessoas.objects.create(nome='Proprietário', cpf='10510510510')
        self.imovel = Imovel.objects.create(
            terra_indigena_id=tis, nome='Imóvel Teste', proprietario=proprietario,
            matricula='M105', cartorio=cartorio,
        )
        documento = Documento.objects.create(
            imovel=self.imovel, tipo=DocumentoTipo.objects.create(tipo='matricula'),
            numero='M105', data=timezone.now().date(), cartorio=cartorio,
            livro='1', folha='1',
        )
        self.lancamento = Lancamento.objects.create(
            documento=documento, tipo=LancamentoTipo.objects.create(tipo='registro'),
            data=timezone.now().date(), origem='Destacamento Público:BA:origem_lidima',
        )
        OrigemFimCadeia.objects.create(
            lancamento=self.lancamento, indice_origem=0, fim_cadeia=True,
            tipo_fim_cadeia='destacamento_publico',
            classificacao_fim_cadeia='origem_lidima',
            info_adicional_fim_cadeia='Secretaria de Terras',
        )

    def test_no_expoe_sigla_e_info_adicional(self):
        arvore = HierarquiaArvoreService.construir_arvore_cadeia_dominial(self.imovel)
        no_fc = next(d for d in arvore['documentos'] if d.get('is_fim_cadeia'))
        self.assertEqual(no_fc['sigla_patrimonio_publico'], 'BA')
        self.assertEqual(no_fc['info_adicional_fim_cadeia'], 'Secretaria de Terras')
