from django.db import migrations
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.loader import MigrationLoader


# Apps cujo rollback histórico (test_migracao_*) cruza migrações de dados
# irreversíveis por design — ex.: 0058 (atribuição de imóveis a superusers)
# e 0060 (seed de perfis), ambas RunPython sem reverse.
APLICACOES_HISTORICAS = ('dominial', 'ia_ocr')

_reversao_noop_aplicada = False


def _permitir_reversao_das_migracoes_de_dados():
    """Dá reverso noop aos RunPython irreversíveis no processo de testes.

    Em produção essas migrações são irreversíveis por design (não há como
    distinguir os dados que elas criaram dos gravados manualmente). Sem
    reverso, voltar o schema além delas exigiria desmarcar registros com
    ``fake`` — e o plano fake inclui tudo que depende delas (dominial 0059+,
    ia_ocr 0007+), deixando as tabelas dessas migrações órfãs no banco
    enquanto o histórico diz que estão des-aplicadas. O reavanço do
    teardown então colide ("table already exists") e o flush do
    TransactionTestCase falha por falta de tabela. Com reverso noop o
    rollback des-aplica tudo de verdade e schema e histórico andam juntos;
    os dados que o avanço porventura criar são rede de rollback num banco
    de testes descartável.
    """
    global _reversao_noop_aplicada
    if _reversao_noop_aplicada:
        return
    loader = MigrationLoader(None, ignore_no_migrations=True)
    for (app, _nome), migration in loader.disk_migrations.items():
        if app not in APLICACOES_HISTORICAS:
            continue
        for operacao in migration.operations:
            if (
                isinstance(operacao, migrations.RunPython)
                and operacao.reverse_code is None
            ):
                operacao.reverse_code = migrations.RunPython.noop
    _reversao_noop_aplicada = True


def executor_para_migracao_historica(connection):
    """Executor para testes de schema anteriores às migrações de dados.

    Em produção as migrações de dados sem reverse são irreversíveis; nos
    testes elas ganham reverso noop (ver
    ``_permitir_reversao_das_migracoes_de_dados``) para que o rollback
    histórico seja executado de verdade.
    """
    _permitir_reversao_das_migracoes_de_dados()
    return MigrationExecutor(connection)


def restaurar_estado_mais_recente(connection):
    """Reaplica o grafo até os leaf nodes no teardown de testes de migração.

    Voltar ``dominial`` a uma migração antiga desfaz em cascata as migrações
    de outros apps que dependem dele (a ``ia_ocr`` depende da dominial). O
    ``flush`` do ``TransactionTestCase`` exige todas as tabelas do estado
    atual dos modelos, então o schema mais novo precisa ser reconstruído
    antes do ``super().tearDown()``.
    """
    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())
