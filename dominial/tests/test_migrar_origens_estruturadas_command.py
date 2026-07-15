import json
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from dominial.models import (
    Cartorios,
    Documento,
    DocumentoTipo,
    Imovel,
    Lancamento,
    LancamentoOrigem,
    LancamentoTipo,
    Pessoas,
    TIs,
)


class MigrarOrigensEstruturadasCommandTest(TestCase):
    def setUp(self):
        tis = TIs.objects.create(nome='TI Teste', codigo='T23', etnia='Teste')
        pessoa = Pessoas.objects.create(nome='Pessoa T23', cpf='98765432100')
        self.cartorio = Cartorios.objects.create(
            nome='Cartório T23',
            cns='333333',
            cidade='Cidade',
            estado='SP',
        )
        imovel = Imovel.objects.create(
            terra_indigena_id=tis,
            nome='Imóvel T23',
            proprietario=pessoa,
            matricula='900',
            tipo_documento_principal='matricula',
            cartorio=self.cartorio,
        )
        documento = Documento.objects.create(
            imovel=imovel,
            tipo=DocumentoTipo.objects.create(tipo='matricula'),
            numero='M900',
            data=timezone.now().date(),
            cartorio=self.cartorio,
        )
        self.tipo_lancamento = LancamentoTipo.objects.create(tipo='inicio_matricula')
        self.documento = documento

    def criar_historico(self, origem, cartorio=True, livro=' 10 ', folha=' 20 '):
        lancamento = Lancamento(
            documento=self.documento,
            tipo=self.tipo_lancamento,
            data=timezone.now().date(),
            origem=origem,
            cartorio_origem=self.cartorio if cartorio else None,
            livro_origem=livro,
            folha_origem=folha,
        )
        Lancamento.objects.bulk_create([lancamento])
        return lancamento

    def executar_json(self, *args):
        saida = StringIO()
        call_command('migrar_origens_estruturadas', *args, '--json', stdout=saida)
        return json.loads(saida.getvalue())

    def test_dry_run_relata_sem_executar_sql_de_escrita(self):
        lancamento = self.criar_historico('M 00123')

        with CaptureQueriesContext(connection) as queries:
            relatorio = self.executar_json('--dry-run')

        escritas = [
            query['sql']
            for query in queries.captured_queries
            if query['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE'))
        ]
        self.assertEqual(escritas, [])
        self.assertEqual(relatorio['convertiveis'], 1)
        self.assertEqual(relatorio['ids']['convertiveis'], [lancamento.pk])
        self.assertFalse(LancamentoOrigem.objects.exists())

    def test_execucao_preserva_legado_e_e_idempotente(self):
        lancamento = self.criar_historico('T456', livro=' 30 ', folha=' 40 ')

        primeira = self.executar_json()
        segunda = self.executar_json()

        lancamento.refresh_from_db()
        origem = LancamentoOrigem.objects.get(lancamento=lancamento)
        self.assertEqual(lancamento.origem, 'T456')
        self.assertEqual(origem.tipo_documento, 'transcricao')
        self.assertEqual(origem.numero, 'T456')
        self.assertEqual(origem.numero_normalizado, '456')
        self.assertEqual(origem.cartorio, self.cartorio)
        self.assertEqual((origem.livro, origem.folha), ('30', '40'))
        self.assertEqual(primeira['convertidos'], 1)
        self.assertEqual(segunda['convertidos'], 0)
        self.assertEqual(segunda['ja_estruturados'], 1)
        self.assertEqual(LancamentoOrigem.objects.count(), 1)

    def test_nao_converte_ambiguos_invalidos_fim_cadeia_ou_sem_cartorio(self):
        ambiguo = self.criar_historico('M123; T456')
        invalido = self.criar_historico('Matrícula descrita 789')
        fim_cadeia = self.criar_historico('Sem Origem: posse tradicional')
        sem_cartorio = self.criar_historico('M999', cartorio=False)

        relatorio = self.executar_json()

        self.assertEqual(relatorio['ids']['ambiguos'], [ambiguo.pk])
        self.assertEqual(relatorio['ids']['invalidos'], [invalido.pk])
        self.assertEqual(relatorio['ids']['fim_cadeia'], [fim_cadeia.pk])
        self.assertEqual(relatorio['ids']['sem_cartorio'], [sem_cartorio.pk])
        self.assertFalse(LancamentoOrigem.objects.exists())

    def test_falha_reverte_todo_o_lote(self):
        self.criar_historico('M111')
        self.criar_historico('T222')
        salvar_original = LancamentoOrigem.save
        chamadas = 0

        def salvar_com_falha(instancia, *args, **kwargs):
            nonlocal chamadas
            chamadas += 1
            if chamadas == 2:
                raise RuntimeError('falha simulada')
            return salvar_original(instancia, *args, **kwargs)

        with patch.object(LancamentoOrigem, 'save', new=salvar_com_falha):
            with self.assertRaisesMessage(RuntimeError, 'falha simulada'):
                call_command('migrar_origens_estruturadas')

        self.assertFalse(LancamentoOrigem.objects.exists())
