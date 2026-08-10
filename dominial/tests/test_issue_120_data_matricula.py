"""Testes de regressão para issue #120.

BUG: `LancamentoDocumentoService.criar_documento_matricula_automatico`
gravava `data='2024-01-01'` fixo no documento de matrícula criado
automaticamente ao cadastrar um imóvel — uma data fictícia, sem qualquer
valor jurídico, inaceitável em um sistema de cadeia dominial.

Correção: a data gravada passa a ser `timezone.localdate()` (a data local
"de hoje", respeitando o `TIME_ZONE` das settings — atualmente 'UTC'; este
PR não altera essa configuração) e o novo campo `Documento.data_presumida`
marca explicitamente que essa data não é um dado jurídico real (livro/
registro), e sim a data em que o cadastro foi iniciado no sistema.
"""
from datetime import date, datetime, timezone as dt_timezone
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from dominial.models import Cartorios, Documento, Imovel, Pessoas, TIs
from dominial.services.lancamento_documento_service import LancamentoDocumentoService


class Issue120Fixture:
    """Mixin de fixtures — não herda de TestCase para não ser coletado como
    um caso de teste vazio. Classes filhas devem herdar de
    (Issue120Fixture, TestCase)."""

    @classmethod
    def setUpTestData(cls):
        cls.tis = TIs.objects.create(nome="TI Issue 120", codigo="TI-120", etnia="Teste")
        cls.pessoa = Pessoas.objects.create(nome="Pessoa Issue 120")
        cls.cartorio = Cartorios.objects.create(
            nome="Cartório Issue 120",
            cns="CNS-ISSUE-120",
            cidade="Cidade Issue 120",
            estado="MS",
        )

    def criar_imovel(self, matricula):
        return Imovel.objects.create(
            terra_indigena_id=self.tis,
            nome="Imóvel Issue 120",
            proprietario=self.pessoa,
            matricula=matricula,
            tipo_documento_principal="matricula",
            cartorio=self.cartorio,
        )


class CriarDocumentoMatriculaAutomaticoTest(Issue120Fixture, TestCase):
    """Cobre `LancamentoDocumentoService.criar_documento_matricula_automatico`
    diretamente."""

    @override_settings(TIME_ZONE='America/Sao_Paulo')
    def test_usa_data_local_e_nao_data_utc(self):
        """Com TIME_ZONE='America/Sao_Paulo', 2026-03-10 02:00 UTC == 23:00
        do dia anterior em SP. localdate() retorna 09/03; now().date()
        retornaria 10/03. O teste falha se alguém regredir para now().date()."""
        # 2026-03-10 02:00 UTC == 2026-03-09 23:00 em São Paulo
        instante = datetime(2026, 3, 10, 2, 0, tzinfo=dt_timezone.utc)
        imovel = self.criar_imovel("125")

        with mock.patch("django.utils.timezone.now", return_value=instante):
            documento = LancamentoDocumentoService.criar_documento_matricula_automatico(imovel)

        self.assertEqual(documento.data, date(2026, 3, 9))    # localdate()
        self.assertNotEqual(documento.data, instante.date())  # now().date() falharia

    def test_define_data_presumida_true(self):
        """O documento criado automaticamente marca `data_presumida=True`:
        a data gravada não é um dado jurídico real, é a data de cadastro."""
        imovel = self.criar_imovel("121")

        documento = LancamentoDocumentoService.criar_documento_matricula_automatico(imovel)

        self.assertTrue(documento.data_presumida)

    def test_data_nunca_e_futura(self):
        """Nenhum documento criado pelo service deve ter data posterior à
        data local atual — a correção não deve trocar uma data fictícia do
        passado por uma data fictícia no futuro."""
        imovel = self.criar_imovel("122")

        documento = LancamentoDocumentoService.criar_documento_matricula_automatico(imovel)

        self.assertLessEqual(documento.data, timezone.localdate())


class DocumentoLabelDataTest(TestCase):
    """Cobre a property `Documento.label_data`, que depende só de
    `data_presumida` — sem precisar de um documento persistido no banco."""

    def test_label_data_quando_presumida(self):
        documento = Documento(data_presumida=True)

        self.assertEqual(documento.label_data, "Análise iniciada em")

    def test_label_data_quando_nao_presumida(self):
        documento = Documento(data_presumida=False)

        self.assertEqual(documento.label_data, "Data")


class ImovelFormCriaMatriculaComDataRealTest(Issue120Fixture, TestCase):
    """Integração via `imovel_form` (form → view → service): a correção
    também precisa valer no fluxo real de cadastro de imóvel, não só quando
    o service é chamado diretamente. View em
    `dominial/views/imovel_views.py` (criação automática de matrícula em
    `imovel_form`, ~linhas 70-74)."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.user = User.objects.create_user(username="issue120", password="issue120pass")

    def setUp(self):
        self.client.force_login(self.user)

    def test_cadastro_de_imovel_cria_matricula_com_data_real_e_presumida(self):
        url = reverse("imovel_cadastro", kwargs={"tis_id": self.tis.id})

        response = self.client.post(url, {
            "nome": "Imóvel via View Issue 120",
            "matricula": "999120",
            "tipo_documento_principal": "matricula",
            "cartorio": self.cartorio.id,
            "proprietario_nome": "Proprietário Issue 120",
            "estado": self.cartorio.estado,
            "cidade": self.cartorio.cidade,
        })

        self.assertEqual(response.status_code, 302)

        imovel = Imovel.objects.get(matricula="999120")
        documento = Documento.objects.get(imovel=imovel, tipo__tipo="matricula")

        self.assertEqual(documento.data, timezone.localdate())
        self.assertTrue(documento.data_presumida)
