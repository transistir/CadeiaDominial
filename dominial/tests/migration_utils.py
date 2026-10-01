from django.db.migrations.executor import MigrationExecutor


MIGRACAO_IRREVERSIVEL = (
    'dominial',
    '0058_atribui_imoveis_existentes_superusers',
)
MIGRACAO_ANTERIOR = [('dominial', '0057_userimovel')]


def executor_para_migracao_historica(connection):
    """Permite que testes de schema anteriores à 0058 iniciem pelo estado atual."""
    executor = MigrationExecutor(connection)
    if MIGRACAO_IRREVERSIVEL in executor.loader.applied_migrations:
        # A 0058 altera apenas dados. No banco descartável de testes, marque-a
        # como revertida sem executar um reverse que não existe por design.
        executor.migrate(MIGRACAO_ANTERIOR, fake=True)
        executor = MigrationExecutor(connection)
    return executor
