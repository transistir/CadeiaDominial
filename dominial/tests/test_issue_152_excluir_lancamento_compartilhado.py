"""
Issue #152 — excluir lançamento de documento compartilhado retornava 404 pela
URL do imóvel importador.

`excluir_lancamento` (lancamento_views.py) filtrava o lançamento por
`documento__imovel=imovel`: um lançamento de documento compartilhado (importado
por outra cadeia) não casava o filtro e o `get_object_or_404` levantava Http404
antes mesmo da tela de confirmação. A correção reaproveita o fallback que o
`editar_lancamento` já tinha, extraído para
`_resolver_lancamento_no_contexto_do_imovel`.

Cenário espelha produção: doc 3168 do imóvel 494, acessado pela URL do imóvel
491 (importador).

O caso mais importante é o `test_lancamento_de_documento_nao_referenciado_...`:
provar que a regra de autorização continua recusando lançamentos que NÃO são
referenciados nesta cadeia (homônimo em outro cartório) — molde em
test_divida_edicao_lancamento_homonimo.py.

Nenhuma migração é aplicada; os testes rodam no banco de testes.
"""

from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from dominial.models import DocumentoImportado, Lancamento, LancamentoTipo
from dominial.tests.test_identidade_documento import IdentidadeDocumentoFixture


class ExcluirLancamentoCompartilhadoTest(IdentidadeDocumentoFixture):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.user = User.objects.create_user(username="excluilanc", password="excluilancpass")
        cls.tipo_inicio = LancamentoTipo.objects.create(tipo="inicio_matricula")

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.login(username="excluilanc", password="excluilancpass")

        # Documento "dono" (imóvel 494) e o lançamento que a issue tentava excluir.
        self.imovel_dono = self.criar_imovel("494", self.cartorio_a, nome="Dono")
        self.documento_dono = self.criar_documento(
            self.imovel_dono, self.tipo_matricula, "M494", self.cartorio_a
        )
        self.lancamento_alvo = Lancamento.objects.create(
            documento=self.documento_dono,
            tipo=self.tipo_inicio,
            data="2026-01-01",
            numero_lancamento="AV1",
            origem="",
        )

        # Imóvel importador (491): referencia documento_dono diretamente via origem.
        self.imovel_importador = self.criar_imovel("491", self.cartorio_a, nome="Importador")
        self.documento_importador = self.criar_documento(
            self.imovel_importador, self.tipo_matricula, "M491", self.cartorio_a
        )
        # bulk_create: evita o signal criar automaticamente o documento da origem.
        Lancamento.objects.bulk_create([
            Lancamento(
                documento=self.documento_importador,
                tipo=self.tipo_inicio,
                data="2026-01-02",
                origem="M494",
                cartorio_origem=self.cartorio_a,
            ),
        ])

    def _url_excluir(self, imovel, lancamento_id):
        return reverse('excluir_lancamento', kwargs={
            'tis_id': self.ti.id,
            'imovel_id': imovel.id,
            'lancamento_id': lancamento_id,
        })

    # AC#1 -------------------------------------------------------------------
    def test_get_excluir_lancamento_compartilhado_renderiza_confirmacao(self):
        """A requisição que dava 404: GET da exclusão pela URL do importador."""
        response = self.client.get(
            self._url_excluir(self.imovel_importador, self.lancamento_alvo.id)
        )
        self.assertEqual(response.status_code, 200)

    def test_post_excluir_lancamento_compartilhado_via_imovel_importador(self):
        response = self.client.post(
            self._url_excluir(self.imovel_importador, self.lancamento_alvo.id)
        )
        self.assertRedirects(response, reverse('documento_detalhado', kwargs={
            'tis_id': self.ti.id,
            'imovel_id': self.imovel_importador.id,
            'documento_id': self.documento_dono.id,
        }))
        self.assertFalse(
            Lancamento.objects.filter(id=self.lancamento_alvo.id).exists()
        )

    # AC#2 (regressão) -----------------------------------------------------
    def test_excluir_lancamento_via_imovel_dono_continua_funcionando(self):
        response = self.client.post(
            self._url_excluir(self.imovel_dono, self.lancamento_alvo.id)
        )
        self.assertRedirects(response, reverse('documento_detalhado', kwargs={
            'tis_id': self.ti.id,
            'imovel_id': self.imovel_dono.id,
            'documento_id': self.documento_dono.id,
        }))
        self.assertFalse(
            Lancamento.objects.filter(id=self.lancamento_alvo.id).exists()
        )

    # Segurança ----------------------------------------------------------
    def test_lancamento_de_documento_nao_referenciado_nao_pode_ser_excluido(self):
        """Homônimo M-em-outro-cartório, não referenciado por esta cadeia:
        excluí-lo pela URL do importador deve ser recusado (redirect para
        cadeia_dominial) e o lançamento deve continuar existindo.

        O homônimo tem o MESMO número (M494) do documento referenciado pela
        cadeia do importador, mas em CARTÓRIO DIFERENTE — a autorização só pode
        aceitar se exigir a identidade completa (número + cartório), não apenas
        o número normalizado."""
        imovel_homonimo = self.criar_imovel("494b", self.cartorio_b, nome="Homônimo B")
        documento_homonimo = self.criar_documento(
            imovel_homonimo, self.tipo_matricula, "M494", self.cartorio_b
        )
        lancamento_homonimo = Lancamento.objects.create(
            documento=documento_homonimo,
            tipo=self.tipo_inicio,
            data="2026-01-01",
            origem="",
        )

        response = self.client.post(
            self._url_excluir(self.imovel_importador, lancamento_homonimo.id)
        )
        self.assertRedirects(response, reverse('cadeia_dominial', kwargs={
            'tis_id': self.ti.id,
            'imovel_id': self.imovel_importador.id,
        }))
        self.assertTrue(
            Lancamento.objects.filter(id=lancamento_homonimo.id).exists()
        )

    # Ramo da árvore (indireção) ----------------------------------------
    def test_excluir_lancamento_compartilhado_com_indirecao_de_dois_niveis(self):
        """Cadeia M491 -> M494 -> M900. O lançamento de M900 (terceiro imóvel)
        deve poder ser excluído pela URL do importador via o fallback da
        árvore."""
        imovel_neto = self.criar_imovel("900", self.cartorio_a, nome="Neto")
        documento_neto = self.criar_documento(
            imovel_neto, self.tipo_matricula, "M900", self.cartorio_a
        )
        lancamento_neto = Lancamento.objects.create(
            documento=documento_neto,
            tipo=self.tipo_inicio,
            data="2026-01-01",
            numero_lancamento="AV1",
            origem="",
        )
        # documento_dono passa a referenciar M900 como origem.
        Lancamento.objects.bulk_create([
            Lancamento(
                documento=self.documento_dono,
                tipo=self.tipo_inicio,
                data="2026-01-03",
                origem="M900",
                cartorio_origem=self.cartorio_a,
            ),
        ])

        response = self.client.post(
            self._url_excluir(self.imovel_importador, lancamento_neto.id)
        )
        self.assertRedirects(response, reverse('documento_detalhado', kwargs={
            'tis_id': self.ti.id,
            'imovel_id': self.imovel_importador.id,
            'documento_id': documento_neto.id,
        }))
        self.assertFalse(
            Lancamento.objects.filter(id=lancamento_neto.id).exists()
        )

    # AC#3 -------------------------------------------------------------------
    def test_confirm_delete_avisa_que_exclusao_afeta_todas_as_cadeias(self):
        response = self.client.get(
            self._url_excluir(self.imovel_importador, self.lancamento_alvo.id)
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Documento compartilhado")
        self.assertContains(response, "todas")

    def test_documento_detalhado_injeta_flag_de_compartilhamento_no_confirm(self):
        url = reverse('documento_detalhado', kwargs={
            'tis_id': self.ti.id,
            'imovel_id': self.imovel_importador.id,
            'documento_id': self.documento_dono.id,
        })
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "compartilhado entre várias cadeias")

    def test_confirm_delete_avisa_compartilhado_pela_url_do_imovel_dono(self):
        """Excluindo pela URL do imóvel DONO de um documento que outra cadeia
        importou, a tela de confirmação também precisa avisar (AC#3)."""
        DocumentoImportado.objects.create(
            documento=self.documento_dono,
            imovel_origem=self.imovel_importador,
            importado_por=self.user,
        )
        response = self.client.get(
            self._url_excluir(self.imovel_dono, self.lancamento_alvo.id)
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Documento compartilhado")
        self.assertContains(response, "todas")

    # Regressão do helper ---------------------------------------------------
    def test_lancamento_inexistente_continua_retornando_404(self):
        response = self.client.get(
            self._url_excluir(self.imovel_importador, 999999)
        )
        self.assertEqual(response.status_code, 404)
