"""
Issue #213 (fase 1) — o service de lançamento não pode mais mutar o
cadastro global de `Pessoas`, nem colapsar múltiplos adquirentes/
transmitentes que chegam com o mesmo `pessoa_id` (registro composto,
ex. "João Rodrigues, José de Arruda e Paulo Santos") em uma única linha
de `LancamentoPessoa`.
"""

from django.test import TestCase

from ..models import (
    Cartorios,
    Documento,
    DocumentoTipo,
    Imovel,
    Lancamento,
    LancamentoPessoa,
    LancamentoTipo,
    Pessoas,
    TIs,
)
from ..services.lancamento_pessoa_service import LancamentoPessoaService
from ..services.lancamento_service import LancamentoService


class PessoaMutacaoTest(TestCase):
    def setUp(self):
        self.tis = TIs.objects.create(nome="TI 213", etnia="Teste", estado="SP")
        self.cartorio = Cartorios.objects.create(
            nome="Cartório 213", cns="CNS213213", cidade="São Paulo"
        )
        self.tipo_matricula = DocumentoTipo.objects.create(tipo="matricula")
        self.tipo_inicio = LancamentoTipo.objects.create(tipo="inicio_matricula")

        self.proprietario = Pessoas.objects.create(nome="Proprietário 213")
        self.imovel = Imovel.objects.create(
            nome="Imóvel 213",
            matricula="21300",
            terra_indigena_id=self.tis,
            proprietario=self.proprietario,
            tipo_documento_principal="matricula",
            cartorio=self.cartorio,
        )
        self.documento = Documento.objects.create(
            numero="21300",
            tipo=self.tipo_matricula,
            imovel=self.imovel,
            cartorio=self.cartorio,
            data="2020-01-01",
            livro="1",
            folha="1",
        )
        self.lancamento = Lancamento.objects.create(
            documento=self.documento,
            tipo=self.tipo_inicio,
            numero_lancamento="1",
            data="2020-01-01",
        )

        self.composto = Pessoas.objects.create(
            nome="João Rodrigues, José de Arruda e Paulo Santos"
        )

    def test_edicao_de_nome_nao_altera_pessoas_compartilhado(self):
        LancamentoPessoaService.processar_pessoas_lancamento(
            self.lancamento,
            ["João Rodrigues"],
            [str(self.composto.id)],
            "adquirente",
        )

        self.composto.refresh_from_db()
        self.assertEqual(
            self.composto.nome, "João Rodrigues, José de Arruda e Paulo Santos"
        )

        self.assertTrue(
            LancamentoPessoa.objects.filter(
                lancamento=self.lancamento,
                pessoa__nome="João Rodrigues",
            ).exists()
        )

    def test_tres_adquirentes_com_mesmo_id_geram_tres_linhas(self):
        nomes = ["João Rodrigues", "José de Arruda", "Paulo Santos"]
        ids = [str(self.composto.id)] * 3

        LancamentoPessoaService.processar_pessoas_lancamento(
            self.lancamento, nomes, ids, "adquirente"
        )

        linhas = LancamentoPessoa.objects.filter(
            lancamento=self.lancamento, tipo="adquirente"
        )
        self.assertEqual(linhas.count(), 3)
        self.assertEqual(
            set(linhas.values_list("nome_digitado", flat=True)), set(nomes)
        )
        self.assertEqual(
            set(linhas.values_list("pessoa__nome", flat=True)), set(nomes)
        )

        self.composto.refresh_from_db()
        self.assertEqual(
            self.composto.nome, "João Rodrigues, José de Arruda e Paulo Santos"
        )

    def test_nome_igual_ao_cadastro_reaproveita_pessoas(self):
        existente = Pessoas.objects.create(nome="Maria Silva")
        total_antes = Pessoas.objects.count()

        LancamentoPessoaService.processar_pessoas_lancamento(
            self.lancamento, ["Maria Silva"], [str(existente.id)], "transmitente"
        )

        self.assertEqual(Pessoas.objects.count(), total_antes)
        linha = LancamentoPessoa.objects.get(
            lancamento=self.lancamento, tipo="transmitente"
        )
        self.assertEqual(linha.pessoa_id, existente.id)
        existente.refresh_from_db()
        self.assertEqual(existente.nome, "Maria Silva")

        # Ramo do .lower(): nome digitado em minúsculas ainda reaproveita o
        # mesmo registro vinculado por id. Usa tipo diferente do caso acima
        # para não colidir com a linha já criada (chave é lancamento+pessoa+tipo).
        LancamentoPessoaService.processar_pessoas_lancamento(
            self.lancamento, ["maria silva"], [str(existente.id)], "adquirente"
        )

        self.assertEqual(Pessoas.objects.count(), total_antes)
        linha_lower = LancamentoPessoa.objects.get(
            lancamento=self.lancamento, tipo="adquirente"
        )
        self.assertEqual(linha_lower.pessoa_id, existente.id)
        existente.refresh_from_db()
        self.assertEqual(existente.nome, "Maria Silva")

    def test_nome_digitado_persistido(self):
        LancamentoPessoaService.processar_pessoas_lancamento(
            self.lancamento, ["Nome Digitado 213"], [""], "adquirente"
        )

        linha = LancamentoPessoa.objects.get(
            lancamento=self.lancamento, tipo="adquirente"
        )
        self.assertEqual(linha.nome_digitado, "Nome Digitado 213")

    def test_pessoa_id_inexistente_cai_para_nome(self):
        total_antes = Pessoas.objects.count()

        LancamentoPessoaService.processar_pessoas_lancamento(
            self.lancamento, ["Fulano Inexistente"], ["999999"], "adquirente"
        )

        self.assertEqual(Pessoas.objects.count(), total_antes + 1)
        linha = LancamentoPessoa.objects.get(
            lancamento=self.lancamento, tipo="adquirente"
        )
        self.assertEqual(linha.pessoa.nome, "Fulano Inexistente")

        # id inválido (não numérico) não pode estourar exceção
        LancamentoPessoaService.processar_pessoas_lancamento(
            self.lancamento, ["Outro Fulano"], ["abc"], "transmitente"
        )
        linha2 = LancamentoPessoa.objects.get(
            lancamento=self.lancamento, tipo="transmitente"
        )
        self.assertEqual(linha2.pessoa.nome, "Outro Fulano")

    def test_sem_pessoa_id_cria_ou_reaproveita(self):
        total_antes = Pessoas.objects.count()

        LancamentoPessoaService.processar_pessoas_lancamento(
            self.lancamento, ["Pessoa Nova 213"], [], "adquirente"
        )
        self.assertEqual(Pessoas.objects.count(), total_antes + 1)

        LancamentoPessoaService.processar_pessoas_lancamento(
            self.lancamento, ["Pessoa Nova 213"], [], "transmitente"
        )
        self.assertEqual(Pessoas.objects.count(), total_antes + 1)

    def test_entrada_lancamento_service_nao_muta_pessoas(self):
        LancamentoService.processar_pessoas_lancamento(
            self.lancamento,
            ["José de Arruda"],
            [str(self.composto.id)],
            "adquirente",
        )

        self.composto.refresh_from_db()
        self.assertEqual(
            self.composto.nome, "João Rodrigues, José de Arruda e Paulo Santos"
        )
        self.assertTrue(
            LancamentoPessoa.objects.filter(
                lancamento=self.lancamento,
                pessoa__nome="José de Arruda",
            ).exists()
        )

    def test_edicao_do_lancamento_nao_duplica_linhas(self):
        nomes = ["João Rodrigues", "José de Arruda", "Paulo Santos"]
        ids = [str(self.composto.id)] * 3

        LancamentoPessoaService.processar_pessoas_lancamento(
            self.lancamento, nomes, ids, "adquirente"
        )

        # Simula a edição do lançamento: a view apaga as linhas existentes
        # antes de reprocessar (dominial/services/lancamento_criacao_service.py:308).
        self.lancamento.pessoas.all().delete()

        LancamentoPessoaService.processar_pessoas_lancamento(
            self.lancamento, nomes, ids, "adquirente"
        )

        linhas = LancamentoPessoa.objects.filter(
            lancamento=self.lancamento, tipo="adquirente"
        )
        self.assertEqual(linhas.count(), 3)
        self.assertEqual(
            set(linhas.values_list("nome_digitado", flat=True)), set(nomes)
        )

        self.composto.refresh_from_db()
        self.assertEqual(
            self.composto.nome, "João Rodrigues, José de Arruda e Paulo Santos"
        )

    def test_nomes_vazios_e_lista_de_ids_mais_curta(self):
        LancamentoPessoaService.processar_pessoas_lancamento(
            self.lancamento,
            ["", "  ", "Só Um Nome"],
            ["", ""],
            "adquirente",
        )

        linhas = LancamentoPessoa.objects.filter(
            lancamento=self.lancamento, tipo="adquirente"
        )
        self.assertEqual(linhas.count(), 1)
        self.assertEqual(linhas.first().pessoa.nome, "Só Um Nome")

        self.assertFalse(
            Pessoas.objects.filter(nome__in=["", "  "]).exists()
        )

    def test_reprocessar_sem_apagar_e_idempotente(self):
        nomes = ["Ana", "Beto"]
        ids = ["", ""]

        LancamentoPessoaService.processar_pessoas_lancamento(
            self.lancamento, nomes, ids, "adquirente"
        )
        total_pessoas_apos_primeira = Pessoas.objects.count()

        # Reprocessa com os mesmos nomes/ids sem apagar as linhas existentes
        # antes (diferente de test_edicao_do_lancamento_nao_duplica_linhas).
        LancamentoPessoaService.processar_pessoas_lancamento(
            self.lancamento, nomes, ids, "adquirente"
        )

        linhas = LancamentoPessoa.objects.filter(
            lancamento=self.lancamento, tipo="adquirente"
        )
        self.assertEqual(linhas.count(), 2)
        self.assertEqual(
            set(linhas.values_list("nome_digitado", flat=True)), set(nomes)
        )
        self.assertEqual(Pessoas.objects.count(), total_pessoas_apos_primeira)
