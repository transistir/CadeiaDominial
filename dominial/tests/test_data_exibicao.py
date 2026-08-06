"""Testes para a property `Documento.data_exibicao`.

Contexto: documentos de matrícula criados automaticamente antes da correção
da issue #120 gravaram `data='2024-01-01'` fixo — uma data fictícia, sem
valor jurídico. A correção da issue #120 passou a gravar a data real
(`timezone.localdate()`) e marcar `data_presumida=True` nesses casos.

`data_exibicao` cobre os dois cenários (o legado com a data fictícia de
2024-01-01, e os novos documentos com `data_presumida=True`) e sempre
exibe `data_cadastro` — a data real de criação no sistema — em vez da data
sem valor jurídico. Para documentos com data jurídica real, `data_exibicao`
retorna a própria `data`.
"""
from datetime import date

from django.test import TestCase

from dominial.models import Cartorios, Documento, DocumentoTipo, Imovel, Pessoas, TIs
from dominial.models.documento_models import DATA_FICTICIA_LEGADO


class DataExibicaoFixture:
    """Mixin de fixtures — não herda de TestCase para não ser coletado como
    um caso de teste vazio. Classes filhas devem herdar de
    (DataExibicaoFixture, TestCase)."""

    @classmethod
    def setUpTestData(cls):
        cls.tis = TIs.objects.create(nome="TI Data Exibicao", codigo="TI-DATAEXIB", etnia="Teste")
        cls.pessoa = Pessoas.objects.create(nome="Pessoa Data Exibicao")
        cls.cartorio = Cartorios.objects.create(
            nome="Cartório Data Exibicao",
            cns="CNS-DATAEXIB",
            cidade="Cidade Data Exibicao",
            estado="MS",
        )
        cls.tipo_matricula, _ = DocumentoTipo.objects.get_or_create(tipo='matricula')

    def criar_imovel(self, matricula):
        return Imovel.objects.create(
            terra_indigena_id=self.tis,
            nome="Imóvel Data Exibicao",
            proprietario=self.pessoa,
            matricula=matricula,
            tipo_documento_principal="matricula",
            cartorio=self.cartorio,
        )

    def criar_documento(self, imovel, numero, data, data_presumida=False):
        return Documento.objects.create(
            imovel=imovel,
            tipo=self.tipo_matricula,
            numero=numero,
            data=data,
            data_presumida=data_presumida,
            cartorio=self.cartorio,
            livro="1",
            folha="1",
        )


class DataExibicaoTest(DataExibicaoFixture, TestCase):
    """Cobre a property `Documento.data_exibicao`."""

    def test_data_ficticia_legado_exibe_data_cadastro(self):
        """Documento com a data fictícia de legado (2024-01-01) e
        `data_presumida=False` (registros antigos, anteriores ao campo)
        deve exibir `data_cadastro` — a data real de criação no sistema —
        em vez da data fictícia sem valor jurídico.

        `data_cadastro` é `auto_now_add=True`: só é gravado na criação e
        não pode ser sobrescrito num save() posterior. Por isso o documento
        é criado primeiro (com qualquer data) e só depois tem `data`
        alterada para a data fictícia de legado, simulando um registro
        antigo cuja `data_cadastro` (hoje) é necessariamente diferente de
        2024-01-01.
        """
        imovel = self.criar_imovel("100")
        documento = self.criar_documento(imovel, "100", data=date(1998, 3, 15))

        documento.data = DATA_FICTICIA_LEGADO
        documento.save()
        documento.refresh_from_db()

        hoje = date.today()
        # Pré-condição: garante que a asserção abaixo não é trivialmente
        # verdadeira — data_cadastro (hoje) precisa ser diferente da data
        # fictícia de legado para o teste ser significativo.
        self.assertNotEqual(hoje, DATA_FICTICIA_LEGADO)
        self.assertEqual(documento.data_cadastro, hoje)

        self.assertEqual(documento.data_exibicao, documento.data_cadastro)

    def test_data_presumida_exibe_data_cadastro(self):
        """Documento com `data_presumida=True` deve exibir `data_cadastro`,
        independentemente do valor gravado em `data` — mesmo que `data` não
        seja a data fictícia de legado (ex: um valor qualquer usado como
        placeholder)."""
        imovel = self.criar_imovel("101")
        documento = self.criar_documento(
            imovel, "101", data=date(2015, 6, 20), data_presumida=True,
        )

        self.assertEqual(documento.data_exibicao, documento.data_cadastro)

    def test_data_real_exibe_data_juridica(self):
        """Documento com data jurídica real e `data_presumida=False` deve
        exibir a própria `data` — não `data_cadastro`, que reflete apenas
        quando o registro foi criado no sistema, sem relação com o dado
        jurídico real (livro/registro)."""
        imovel = self.criar_imovel("102")
        documento = self.criar_documento(imovel, "102", data=date(1998, 3, 15))

        self.assertEqual(documento.data_exibicao, documento.data)
        self.assertNotEqual(documento.data_exibicao, documento.data_cadastro)

    def test_expression_ordena_pela_mesma_data_exibida(self):
        imovel = self.criar_imovel("103")
        legado = self.criar_documento(
            imovel, "103", data=DATA_FICTICIA_LEGADO,
        )
        presumido = self.criar_documento(
            imovel, "104", data=date(1990, 1, 1), data_presumida=True,
        )
        data_real = self.criar_documento(
            imovel, "105", data=date(2022, 1, 1),
        )
        Documento.objects.filter(pk=legado.pk).update(data_cadastro=date(2020, 1, 1))
        Documento.objects.filter(pk=presumido.pk).update(data_cadastro=date(2021, 1, 1))

        documentos = Documento.objects.filter(imovel=imovel).annotate(
            data_exibicao_ordenacao=Documento.data_exibicao_expression(),
        ).order_by('-data_exibicao_ordenacao', '-id')

        self.assertEqual(
            list(documentos.values_list('pk', flat=True)),
            [data_real.pk, presumido.pk, legado.pk],
        )
