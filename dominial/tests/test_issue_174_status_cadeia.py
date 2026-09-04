"""Issue #174 — badge de status de cadeia finalizada na relação de imóveis da TI.

A página ``tis_detail`` deve mostrar, por imóvel, se a cadeia dominial está
finalizada (e com qual classificação) sem precisar abrir imóvel por imóvel.
"""

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from ..models import (
    Cartorios,
    Documento,
    DocumentoTipo,
    Imovel,
    Lancamento,
    LancamentoTipo,
    OrigemFimCadeia,
    Pessoas,
    TIs,
)
from ..services.status_cadeia_service import StatusCadeiaService


class StatusCadeiaBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="t174", password="t174pass")
        self.client = Client()
        self.client.login(username="t174", password="t174pass")

        self.tis = TIs.objects.create(nome="TI 174", etnia="Teste", codigo="TI174")
        self.cartorio = Cartorios.objects.create(
            nome="Cartório 174", cns="CNS174174", cidade="Cidade"
        )
        self.pessoa = Pessoas.objects.create(nome="Proprietário 174", cpf="17417417417")
        self.tipo_matricula = DocumentoTipo.objects.create(tipo="matricula")
        self.tipo_registro = LancamentoTipo.objects.create(tipo="registro")

    def _criar_imovel(self, matricula):
        return Imovel.objects.create(
            nome=f"Imóvel {matricula}",
            matricula=matricula,
            terra_indigena_id=self.tis,
            proprietario=self.pessoa,
            cartorio=self.cartorio,
        )

    def _criar_lancamento(self, imovel):
        documento = Documento.objects.create(
            numero=imovel.matricula,
            tipo=self.tipo_matricula,
            imovel=imovel,
            cartorio=self.cartorio,
            data=timezone.now().date(),
            livro="1",
            folha="1",
        )
        return Lancamento.objects.create(
            documento=documento,
            tipo=self.tipo_registro,
            data=timezone.now().date(),
            origem="",
        )

    def _fim_cadeia(self, lancamento, classificacao, indice_origem=0):
        return OrigemFimCadeia.objects.create(
            lancamento=lancamento,
            indice_origem=indice_origem,
            fim_cadeia=True,
            tipo_fim_cadeia="destacamento_publico",
            classificacao_fim_cadeia=classificacao,
        )


class StatusCadeiaServiceTest(StatusCadeiaBase):
    def test_origem_lidima(self):
        imovel = self._criar_imovel("M1")
        self._fim_cadeia(self._criar_lancamento(imovel), "origem_lidima")
        status_map = StatusCadeiaService.status_por_imovel(self.tis.id)
        self.assertEqual(status_map.get(imovel.id), "origem_lidima")

    def test_sem_origem(self):
        imovel = self._criar_imovel("M2")
        self._fim_cadeia(self._criar_lancamento(imovel), "sem_origem")
        status_map = StatusCadeiaService.status_por_imovel(self.tis.id)
        self.assertEqual(status_map.get(imovel.id), "sem_origem")

    def test_imovel_sem_fim_de_cadeia_ausente_do_dict(self):
        imovel = self._criar_imovel("M3")
        self._criar_lancamento(imovel)  # sem OrigemFimCadeia
        status_map = StatusCadeiaService.status_por_imovel(self.tis.id)
        self.assertNotIn(imovel.id, status_map)
        self.assertIsNone(status_map.get(imovel.id))

    def test_origem_fim_cadeia_false_nao_conta(self):
        imovel = self._criar_imovel("M3b")
        lancamento = self._criar_lancamento(imovel)
        OrigemFimCadeia.objects.create(
            lancamento=lancamento,
            indice_origem=0,
            fim_cadeia=False,
            classificacao_fim_cadeia="origem_lidima",
        )
        status_map = StatusCadeiaService.status_por_imovel(self.tis.id)
        self.assertNotIn(imovel.id, status_map)

    def test_prioridade_pior_situacao(self):
        imovel = self._criar_imovel("M4")
        lancamento = self._criar_lancamento(imovel)
        self._fim_cadeia(lancamento, "origem_lidima", indice_origem=0)
        self._fim_cadeia(lancamento, "sem_origem", indice_origem=1)
        status_map = StatusCadeiaService.status_por_imovel(self.tis.id)
        self.assertEqual(status_map.get(imovel.id), "sem_origem")

    def test_inconclusa_reconhecida(self):
        imovel = self._criar_imovel("M5")
        self._fim_cadeia(self._criar_lancamento(imovel), "inconclusa")
        status_map = StatusCadeiaService.status_por_imovel(self.tis.id)
        self.assertEqual(status_map.get(imovel.id), "inconclusa")

    def test_classificacao_desconheca_nao_derruba_e_retorna_none(self):
        imovel = self._criar_imovel("M6")
        lancamento = self._criar_lancamento(imovel)
        OrigemFimCadeia.objects.create(
            lancamento=lancamento,
            indice_origem=0,
            fim_cadeia=True,
            tipo_fim_cadeia="destacamento_publico",
            classificacao_fim_cadeia="foo_bar_baz",
        )
        status_map = StatusCadeiaService.status_por_imovel(self.tis.id)
        self.assertNotIn(imovel.id, status_map)
        self.assertIsNone(status_map.get(imovel.id))

    def test_classificacao_nula_tratada_como_desconhecida(self):
        imovel = self._criar_imovel("M7")
        lancamento = self._criar_lancamento(imovel)
        OrigemFimCadeia.objects.create(
            lancamento=lancamento,
            indice_origem=0,
            fim_cadeia=True,
            tipo_fim_cadeia="destacamento_publico",
            classificacao_fim_cadeia=None,
        )
        status_map = StatusCadeiaService.status_por_imovel(self.tis.id)
        self.assertNotIn(imovel.id, status_map)
        self.assertIsNone(status_map.get(imovel.id))

    def test_nao_vaza_imoveis_de_outra_ti(self):
        outra_tis = TIs.objects.create(nome="Outra TI", etnia="X", codigo="OUT174")
        imovel_outra = Imovel.objects.create(
            nome="Imóvel outra TI",
            matricula="M999",
            terra_indigena_id=outra_tis,
            proprietario=self.pessoa,
            cartorio=self.cartorio,
        )
        self._fim_cadeia(self._criar_lancamento(imovel_outra), "origem_lidima")
        status_map = StatusCadeiaService.status_por_imovel(self.tis.id)
        self.assertNotIn(imovel_outra.id, status_map)


class StatusCadeiaViewTest(StatusCadeiaBase):
    def test_tis_detail_renderiza_badge_e_traco(self):
        imovel_finalizado = self._criar_imovel("MF")
        self._fim_cadeia(self._criar_lancamento(imovel_finalizado), "origem_lidima")
        imovel_andamento = self._criar_imovel("MA")
        self._criar_lancamento(imovel_andamento)

        response = self.client.get(reverse("tis_detail", args=[self.tis.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "cadeia-badge-lidima")
        self.assertContains(response, "Origem Lídima")
        self.assertContains(response, "cadeia-badge-vazio")
