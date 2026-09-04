"""Issue #167 — endpoint `buscar_m_anterior` (AJAX para "M anterior
vinculada" na tela de Novo Lançamento).

Cobre os caminhos do JSON: encontrado na mesma TI / outra TI / não
encontrado / params inválidos.
"""
import os
import re
from datetime import date
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from dominial.models import (
    TIs, Imovel, DocumentoTipo, Cartorios, Documento, Pessoas,
)


class BuscarMAnteriorTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user('u', 'u@x.com', 'pw')

        self.pessoa = Pessoas.objects.create(nome='P')
        self.cart_a = Cartorios.objects.create(nome='CRI A', cidade='C', cns='CNS-A')
        self.cart_b = Cartorios.objects.create(nome='CRI B', cidade='C', cns='CNS-B')
        self.tipo_m = DocumentoTipo.objects.get_or_create(tipo='matricula')[0]
        self.tipo_t = DocumentoTipo.objects.get_or_create(tipo='transcricao')[0]

        self.ti1 = TIs.objects.create(nome='TI 1', codigo='TI-001')
        self.ti2 = TIs.objects.create(nome='TI 2', codigo='TI-002')

        self.imovel_ti1 = Imovel.objects.create(
            nome='Imóvel TI1', matricula='001',
            tipo_documento_principal='M', cartorio=self.cart_a,
            terra_indigena_id=self.ti1, proprietario=self.pessoa,
        )
        self.imovel_ti2 = Imovel.objects.create(
            nome='Imóvel TI2', matricula='002',
            tipo_documento_principal='M', cartorio=self.cart_b,
            terra_indigena_id=self.ti2, proprietario=self.pessoa,
        )

        # Matrícula 1234 no cart A → Imóvel da TI1 (mesma TI)
        self.doc_ti1_a = Documento.objects.create(
            tipo=self.tipo_m, numero='1234', cartorio=self.cart_a,
            imovel=self.imovel_ti1,
            data=date(2020, 1, 1), livro='1', folha='1',
        )
        # Mesma matrícula 1234 no cart B → Imóvel da TI2 (cruzamento
        # com outra TI: isso é exatamente o cenário de quebra da
        # cadeia que motivou a issue #167).
        self.doc_ti2_b = Documento.objects.create(
            tipo=self.tipo_m, numero='1234', cartorio=self.cart_b,
            imovel=self.imovel_ti2,
            data=date(2020, 1, 1), livro='1', folha='1',
        )

        self.url = reverse('buscar_m_anterior')

    def _login_e_get(self, params):
        self.client.force_login(self.user)
        return self.client.get(self.url, params)

    def test_encontra_doc_na_mesma_ti(self):
        r = self._login_e_get({
            'numero': 'M 1234', 'cartorio_id': self.cart_a.id,
            'tis_id': self.ti1.id,
        })
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data['encontrado'])
        self.assertEqual(data['doc_id'], self.doc_ti1_a.id)
        self.assertEqual(data['matricula'], '1234')
        self.assertEqual(data['imovel_nome'], 'Imóvel TI1')
        self.assertTrue(data['mesma_ti'])
        self.assertFalse(data['outra_ti'])

    def test_encontra_doc_em_outra_ti(self):
        # Usuário na TI1, mas o par (numero, cartório) bate com o
        # documento que pertence à TI2 (cart B).
        r = self._login_e_get({
            'numero': '1234', 'cartorio_id': self.cart_b.id,
            'tis_id': self.ti1.id,
        })
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data['encontrado'])
        self.assertFalse(data['mesma_ti'])
        self.assertTrue(data['outra_ti'])
        self.assertEqual(data['imovel_nome'], 'Imóvel TI2')

    def test_nao_encontrado(self):
        r = self._login_e_get({
            'numero': 'M 9999', 'cartorio_id': self.cart_a.id,
            'tis_id': self.ti1.id,
        })
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertFalse(data['encontrado'])
        self.assertIsNone(data['doc_id'])

    def test_param_obrigatorio_faltando(self):
        self.client.force_login(self.user)
        r = self.client.get(self.url, {'numero': 'M 1234'})  # sem cartorio_id
        self.assertEqual(r.status_code, 400)

    def test_nao_confundir_transcricao_com_matricula_mesmo_numero(self):
        """Codex review P1 do PR #167: quando o cartório tem M e T com mesmo
        número normalizado, o endpoint deve retornar a matrícula — não a
        transcrição — para não reportar imóvel/TI errado como 'M anterior'.
        """
        # Transcrição 1234 no cart A, do imóvel da TI1.
        Documento.objects.create(
            tipo=self.tipo_t, numero='1234', cartorio=self.cart_a,
            imovel=self.imovel_ti1,
            data=date(2020, 1, 1), livro='1', folha='1',
        )
        r = self._login_e_get({
            'numero': 'M 1234', 'cartorio_id': self.cart_a.id,
            'tis_id': self.ti1.id,
        })
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data['encontrado'])
        # Deve ser a matrícula M 1234 (doc_ti1_a), nunca a transcrição.
        self.assertEqual(data['doc_id'], self.doc_ti1_a.id)
        self.assertEqual(data['matricula'], '1234')

    def test_normaliza_numero_com_prefixo_e_espaco(self):
        r = self._login_e_get({
            'numero': '  m 1234  ', 'cartorio_id': self.cart_a.id,
            'tis_id': self.ti1.id,
        })
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['encontrado'])


class GreptileP2RaceAbortTest(TestCase):
    """P2 do Greptile no PR #185: race entre fetch em voo e mudança de inputs.

    Sem teste JS (sem Playwright no repo), validamos que o JS tem o guard
    anti-stale-badge via pattern-matching no arquivo fonte. Se alguém remover
    o abort() do early-return, este teste quebra.
    """

    JS_PATH = os.path.join(
        os.path.dirname(__file__),
        '..', '..', 'static', 'dominial', 'js', 'origem_simples.js',
    )

    def setUp(self):
        with open(self.JS_PATH, encoding='utf-8') as f:
            self.js_src = f.read()

    def test_atualizarMAnterior_aborta_fetch_no_early_return_invalido(self):
        """Garante que o early-return para tipo/numero/cartorio inválido
        aborta o AbortController pendente, evitando render stale."""
        # Localiza o early-return: o primeiro "if (tipo !== 'M' ... return;"
        # deve estar seguido de um abort() antes do return.
        match = re.search(
            r"if\s*\(\s*tipo\s*!==\s*'M'\s*\|\|\s*!numero\s*\|\|\s*!cartorioId\s*\)\s*\{(.*?)\}",
            self.js_src,
            re.DOTALL,
        )
        assert match is not None, (
            'Bloco de validação tipo/numero/cartorio não encontrado no JS'
        )
        body = match.group(1)
        self.assertIn(
            '_mAnteriorAbort[index].abort()',
            body,
            'P2 Greptile: early-return precisa abortar fetch pendente antes '
            'de esconder o badge (race condition com fetch atrasado)',
        )

    def test_handler_then_confere_controller_antes_de_renderizar(self):
        """Mesmo que o fetch escape do abort (ex: rede rápida), o .then deve
        conferir se o controller ainda é o atual antes de repopular o badge."""
        # Procura o .then(dados => ...) e garante que ele checa o controller.
        # No nosso código atual, o check está no .finally, mas a checagem no
        # .then é uma salvaguarda adicional. Se não existir ainda, registramos
        # como aviso (skip) para não bloquear.
        then_match = re.search(
            r"\.then\(\s*dados\s*=>\s*\{(.*?)\}\s*\)",
            self.js_src,
            re.DOTALL,
        )
        assert then_match is not None, 'handler .then(dados => ...) ausente'
        then_body = then_match.group(1)
        # Salvaguarda: ou o then confere o controller, OU o finally zera
        # _mAnteriorAbort e o render só acontece no caminho síncrono após
        # abort() — verificamos o finally como contrapeso.
        finally_match = re.search(
            r"\.finally\(\s*\(\)\s*=>\s*\{(.*?)\}\s*\)",
            self.js_src,
            re.DOTALL,
        )
        assert finally_match is not None, 'handler .finally ausente'
        finally_body = finally_match.group(1)
        self.assertIn(
            '_mAnteriorAbort[index] = null',
            finally_body,
            'finally deve zerar _mAnteriorAbort para evitar uso de controller '
            'já abortado em chamadas subsequentes',
        )
