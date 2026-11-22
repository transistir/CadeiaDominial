"""Regressão: ``data_origem`` não pode ser inferida da data do ato.

Bug: ``LancamentoCriacaoService._criar_lancamento_basico`` gravava
``data_origem=dados_lancamento['data']`` — copiando a data do ato para a data
do documento de origem. Nenhum formulário envia ``data_origem``, então o campo
era sempre inventado.

Regra de produto (Hiure, 22/11): ``data_origem`` só pode ser gravada quando
estiver efetivamente presente na referência documental ou tiver sido informada
explicitamente pelo usuário. Ausente ⇒ ``None``.
"""

from datetime import date

from django.test import RequestFactory

from dominial.models import LancamentoTipo
from dominial.services.lancamento_criacao_service import LancamentoCriacaoService
from dominial.tests.segregacao_fixtures import usuario_com_tis
from dominial.tests.test_identidade_documento import IdentidadeDocumentoFixture


class DataOrigemSemInferenciaTest(IdentidadeDocumentoFixture):
    """``data_origem`` na criação via ``criar_lancamento_completo``."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.tipo_inicio, _ = LancamentoTipo.objects.get_or_create(
            tipo="inicio_matricula"
        )

    def _cenario(self, matricula):
        imovel = self.criar_imovel(
            matricula, self.cartorio_a, nome=f"Imóvel #{matricula}"
        )
        documento = self.criar_documento(
            imovel, self.tipo_matricula, f"M{matricula}", self.cartorio_a
        )
        return imovel, documento

    def _post(self, sigla, *, data_origem=None, origens=None,
              cartorios_ids=None, cartorios_nomes=None):
        """Monta POST de início de matrícula para ``criar_lancamento_completo``."""
        origens = origens or []
        total = len(origens)
        post = {
            "tipo_lancamento": str(self.tipo_inicio.pk),
            "sigla_matricula": sigla,
            "numero_lancamento_simples": "1",
            "numero_lancamento": "",
            "data": "2026-01-02",
            "observacoes": "",
            "origem_completa[]": list(origens),
            "cartorio_origem[]": [
                str(c) if c else "" for c in (cartorios_ids or [])
            ],
            "cartorio_origem_nome[]": list(cartorios_nomes or []),
            "livro_origem[]": [""] * total,
            "folha_origem[]": [""] * total,
            "transmitente_nome[]": [],
            "transmitente[]": [],
            "adquirente_nome[]": [],
            "adquirente[]": [],
        }
        if data_origem is not None:
            post["data_origem"] = data_origem
        return post

    def _criar(self, post, imovel, documento, *, apos_importacao=False):
        request = RequestFactory().post("/x/", post)
        request.user = usuario_com_tis(f"u-{post['sigla_matricula']}", self.ti)
        lancamento, mensagem = LancamentoCriacaoService.criar_lancamento_completo(
            request, self.ti, imovel, documento, apos_importacao=apos_importacao
        )
        return lancamento, mensagem

    def test_sem_data_origem_no_post_grava_none(self):
        """Criação sem ``data_origem`` no POST → ``None`` (não a data do ato)."""
        imovel, documento = self._cenario("701")
        lancamento, mensagem = self._criar(
            self._post("M701"), imovel, documento
        )

        self.assertIsNotNone(lancamento, mensagem)
        lancamento.refresh_from_db()
        self.assertIsNone(lancamento.data_origem)
        self.assertEqual(lancamento.data, date(2026, 1, 2))

    def test_data_origem_explicita_e_persistida(self):
        """``data_origem`` explícito no POST vence e é persistido."""
        imovel, documento = self._cenario("702")
        lancamento, mensagem = self._criar(
            self._post("M702", data_origem="2025-05-05"), imovel, documento
        )

        self.assertIsNotNone(lancamento, mensagem)
        lancamento.refresh_from_db()
        self.assertEqual(lancamento.data_origem, date(2025, 5, 5))
        self.assertEqual(lancamento.data, date(2026, 1, 2))

    def test_inicio_matricula_com_origem_sem_data_fica_none(self):
        """Início de matrícula com origem (sem data na origem) → ``None``."""
        imovel, documento = self._cenario("703")
        self.criar_documento(
            self.criar_imovel("500", self.cartorio_a, nome="Origem M500"),
            self.tipo_matricula, "M500", self.cartorio_a,
        )
        lancamento, mensagem = self._criar(
            self._post(
                "M703",
                origens=["M500"],
                cartorios_ids=[self.cartorio_a.pk],
                cartorios_nomes=[self.cartorio_a.nome],
            ),
            imovel,
            documento,
            apos_importacao=True,
        )

        self.assertIsNotNone(lancamento, mensagem)
        lancamento.refresh_from_db()
        self.assertIsNone(lancamento.data_origem)
