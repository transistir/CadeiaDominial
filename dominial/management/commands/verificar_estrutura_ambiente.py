"""Verifica migrações e constraints sem alterar o ambiente."""

import json

from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.db.migrations.executor import MigrationExecutor

from dominial.models import Documento, Imovel


class Command(BaseCommand):
    help = 'Verifica migrações e constraints do banco sem executar alterações.'

    EXPECTATIVAS_FINAIS = {
        'documento_identidade': {
            'tabela': Documento._meta.db_table,
            'colunas': {'tipo_id', 'numero', 'cartorio_id'},
        },
        'imovel_identidade': {
            'tabela': Imovel._meta.db_table,
            'colunas': {'tipo_documento_principal', 'matricula', 'cartorio_id'},
        },
    }

    def add_arguments(self, parser):
        parser.add_argument('--database', default='default')
        parser.add_argument('--json', action='store_true', dest='usar_json')
        parser.add_argument(
            '--expect-final',
            action='store_true',
            help='Exige as constraints finais planejadas para Documento e Imovel.',
        )
        parser.add_argument(
            '--fail-on-problem',
            action='store_true',
            help='Encerra com erro diante de migração pendente ou estado inconsistente.',
        )

    def handle(self, *args, **options):
        alias = options['database']
        if alias not in connections:
            raise CommandError(f'Banco desconhecido: {alias}.')

        conexao = connections[alias]
        executor = MigrationExecutor(conexao)
        folhas = executor.loader.graph.leaf_nodes()
        plano = executor.migration_plan(folhas)
        pendentes = [
            f'{migracao.app_label}.{migracao.name}'
            for migracao, retroceder in plano
            if not retroceder
        ]

        aplicadas = set(executor.loader.applied_migrations)
        conhecidas = set(executor.loader.disk_migrations)
        aplicadas_desconhecidas = sorted(
            f'{app}.{nome}' for app, nome in aplicadas - conhecidas
        )

        constraints = {}
        for model in (Documento, Imovel):
            tabela = model._meta.db_table
            with conexao.cursor() as cursor:
                constraints[tabela] = conexao.introspection.get_constraints(
                    cursor,
                    tabela,
                )

        expectativas = {}
        for nome, expectativa in self.EXPECTATIVAS_FINAIS.items():
            constraints_tabela = constraints[expectativa['tabela']]
            correspondencias = [
                nome_constraint
                for nome_constraint, dados in constraints_tabela.items()
                if dados.get('unique')
                and set(dados.get('columns') or ()) == expectativa['colunas']
            ]
            expectativas[nome] = {
                'atendida': bool(correspondencias),
                'constraints': sorted(correspondencias),
                'colunas_esperadas': sorted(expectativa['colunas']),
            }

        relatorio = {
            'somente_leitura': True,
            'database': alias,
            'vendor': conexao.vendor,
            'migracoes_pendentes': pendentes,
            'migracoes_aplicadas_desconhecidas': aplicadas_desconhecidas,
            'constraints_unicas': {
                tabela: sorted([
                    {
                        'nome': nome,
                        'colunas': list(dados.get('columns') or ()),
                    }
                    for nome, dados in itens.items()
                    if dados.get('unique') and not dados.get('primary_key')
                ], key=lambda item: item['nome'])
                for tabela, itens in constraints.items()
            },
            'expectativas_finais': expectativas,
        }

        if options['usar_json']:
            self.stdout.write(json.dumps(relatorio, ensure_ascii=False, sort_keys=True))
        else:
            self._escrever_relatorio(relatorio)

        problemas = list(pendentes) + list(aplicadas_desconhecidas)
        if options['expect_final']:
            problemas.extend(
                nome for nome, estado in expectativas.items()
                if not estado['atendida']
            )
        if (options['fail_on_problem'] or options['expect_final']) and problemas:
            raise CommandError(
                'Estrutura do ambiente não atende às expectativas: '
                + ', '.join(problemas)
            )

    def _escrever_relatorio(self, relatorio):
        self.stdout.write('VERIFICACAO ESTRUTURAL DO AMBIENTE (SOMENTE LEITURA)')
        self.stdout.write(
            f"Banco: {relatorio['database']} ({relatorio['vendor']})"
        )
        self.stdout.write(
            f"Migrações pendentes: {len(relatorio['migracoes_pendentes'])}"
        )
        self.stdout.write(
            'Migrações aplicadas sem arquivo: '
            f"{len(relatorio['migracoes_aplicadas_desconhecidas'])}"
        )
        for nome, estado in relatorio['expectativas_finais'].items():
            texto = 'OK' if estado['atendida'] else 'AUSENTE'
            self.stdout.write(f'Constraint final {nome}: {texto}')
