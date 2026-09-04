"""Issue #167 — endpoint `buscar_m_anterior` (AJAX para "M anterior
vinculada" na tela de Novo Lançamento).

Cobre os caminhos do JSON: encontrado na mesma TI / outra TI / não
encontrado / params inválidos.
"""
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
        self.tipo_m = DocumentoTipo.objects.create(tipo='M')

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

    def test_normaliza_numero_com_prefixo_e_espaco(self):
        r = self._login_e_get({
            'numero': '  m 1234  ', 'cartorio_id': self.cart_a.id,
            'tis_id': self.ti1.id,
        })
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['encontrado'])
