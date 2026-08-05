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
from datetime import datetime, timezone as dt_timezone
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from dominial.models import Cartorios, Documento, DocumentoTipo, Imovel, Pessoas, TIs
from dominial.services.lancamento_documento_service import LancamentoDocumentoService


class Issue120Fixture(TestCase):
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
        cls.tipo_matricula = DocumentoTipo.objects.get_or_create(tipo="matricula")[0]

    def criar_imovel(self, matricula):
        return Imovel.objects.create(
            terra_indigena_id=self.tis,
            nome="Imóvel Issue 120",
            proprietario=self.pessoa,
            matricula=matricula,
            tipo_documento_principal="matricula",
            cartorio=self.cartorio,
        )


class CriarDocumentoMatriculaAutomaticoTest(Issue120Fixture):
    """Cobre `LancamentoDocumentoService.criar_documento_matricula_automatico`
    diretamente."""

    def test_usa_data_local_respeitando_time_zone_das_settings(self):
        """BUG #120: a data era hardcoded '2024-01-01'. Com o relógio
        congelado num instante bem distante disso, a data gravada deve
        corresponder a `timezone.localdate()` — que respeita o `TIME_ZONE`
        ativo nas settings (hoje 'UTC'), sem exigir simular meia-noite em
        Brasília nem alterar TIME_ZONE neste PR."""
        instante_congelado = datetime(2026, 3, 10, 8, 0, tzinfo=dt_timezone.utc)
        imovel = self.criar_imovel("120")

        with mock.patch("django.utils.timezone.now", return_value=instante_congelado):
            data_local_esperada = timezone.localdate()
            documento = LancamentoDocumentoService.criar_documento_matricula_automatico(imovel)

        # Confirma que o freeze de fato mudou a data "atual" usada no teste,
        # senão a asserção seguinte poderia passar por coincidência.
        self.assertEqual(data_local_esperada, instante_congelado.date())
        self.assertEqual(documento.data, data_local_esperada)

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


class DocumentoLabelDataTest(Issue120Fixture):
    """Cobre a property `Documento.label_data`."""

    def criar_documento(self, matricula, data_presumida):
        imovel = self.criar_imovel(matricula)
        return Documento.objects.create(
            imovel=imovel,
            tipo=self.tipo_matricula,
            numero=f"M{matricula}",
            data=timezone.localdate(),
            data_presumida=data_presumida,
            cartorio=self.cartorio,
            livro="1",
            folha="1",
        )

    def test_label_data_quando_presumida(self):
        documento = self.criar_documento("123", data_presumida=True)

        self.assertEqual(documento.label_data, "Análise iniciada em")

    def test_label_data_quando_nao_presumida(self):
        documento = self.criar_documento("124", data_presumida=False)

        self.assertEqual(documento.label_data, "Data")


class ImovelFormCriaMatriculaComDataRealTest(Issue120Fixture):
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
