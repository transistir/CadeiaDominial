from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from dominial.models import (
    Cartorios,
    Documento,
    DocumentoTipo,
    Imovel,
    Lancamento,
    LancamentoTipo,
    Pessoas,
    TIs,
    UserImovel,
)


class Issue121AreaInicioTranscricaoTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="issue121", password="testpass")
        cls.tis = TIs.objects.create(
            nome="TI Issue 121",
            codigo="TI-121",
            etnia="Teste",
        )
        cls.pessoa = Pessoas.objects.create(nome="Pessoa Issue 121")
        cls.cartorio = Cartorios.objects.create(
            nome="Cartório Issue 121",
            cns="CNS-ISSUE-121",
            cidade="Campo Grande",
            estado="MS",
        )
        cls.tipo_transcricao = DocumentoTipo.objects.create(tipo="transcricao")
        cls.tipo_matricula = DocumentoTipo.objects.create(tipo="matricula")
        cls.tipo_inicio = LancamentoTipo.objects.create(tipo="inicio_matricula")
        cls.tipo_averbacao = LancamentoTipo.objects.create(tipo="averbacao")
        cls.tipo_registro = LancamentoTipo.objects.create(tipo="registro")

        cls.imovel_transcricao = Imovel.objects.create(
            terra_indigena_id=cls.tis,
            nome="Imóvel Transcrição",
            proprietario=cls.pessoa,
            matricula="121",
            tipo_documento_principal="transcricao",
            cartorio=cls.cartorio,
        )
        cls.documento_transcricao = Documento.objects.create(
            imovel=cls.imovel_transcricao,
            tipo=cls.tipo_transcricao,
            numero="T121",
            data="2026-08-05",
            cartorio=cls.cartorio,
            livro="1",
            folha="1",
        )
        cls.imovel_matricula = Imovel.objects.create(
            terra_indigena_id=cls.tis,
            nome="Imóvel Matrícula",
            proprietario=cls.pessoa,
            matricula="T122",
            tipo_documento_principal="matricula",
            cartorio=cls.cartorio,
        )
        cls.documento_matricula = Documento.objects.create(
            imovel=cls.imovel_matricula,
            tipo=cls.tipo_matricula,
            numero="T122",
            data="2026-08-05",
            cartorio=cls.cartorio,
            livro="2",
            folha="2",
        )

        # Segregação (#132): o usuário comum só enxerga imóveis atribuídos a ele.
        UserImovel.objects.create(user=cls.user, imovel=cls.imovel_transcricao)
        UserImovel.objects.create(user=cls.user, imovel=cls.imovel_matricula)

    def setUp(self):
        self.client.force_login(self.user)

    def _novo_lancamento(self, imovel, documento):
        url = reverse(
            "novo_lancamento_documento",
            kwargs={
                "tis_id": self.tis.id,
                "imovel_id": imovel.id,
                "documento_id": documento.id,
            },
        )
        return self.client.get(url)

    def test_nova_transcricao_exibe_apenas_area_da_transmissao(self):
        response = self._novo_lancamento(
            self.imovel_transcricao,
            self.documento_transcricao,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="area_transmissao"', count=1)
        self.assertNotContains(response, 'id="area_inicio_matricula"')

    def test_nova_matricula_mantem_area_de_inicio_matricula(self):
        response = self._novo_lancamento(
            self.imovel_matricula,
            self.documento_matricula,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="area_inicio_matricula"', count=1)
        self.assertContains(response, "window.isTranscricao = false;")

    def test_edicao_de_inicio_em_transcricao_exibe_area_na_transmissao(self):
        lancamento = Lancamento.objects.create(
            documento=self.documento_transcricao,
            tipo=self.tipo_inicio,
            data="2026-08-05",
            area=Decimal("150.5000"),
            cartorio_origem=self.cartorio,
        )
        url = reverse(
            "editar_lancamento",
            kwargs={
                "tis_id": self.tis.id,
                "imovel_id": self.imovel_transcricao.id,
                "lancamento_id": lancamento.id,
            },
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="area_transmissao"')
        self.assertContains(response, 'value="150.5000"')
        self.assertNotContains(response, 'id="area_inicio_matricula"')

    def test_averbacao_em_transcricao_continua_sem_area_propria(self):
        response = self._novo_lancamento(
            self.imovel_transcricao,
            self.documento_transcricao,
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="area_averbacao"')
        self.assertContains(response, 'id="area_transmissao"', count=1)

    def test_registro_em_matricula_continua_com_area_da_transmissao(self):
        response = self._novo_lancamento(
            self.imovel_matricula,
            self.documento_matricula,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="area_transmissao"', count=1)
