from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class ImovelCartorioNotNullMigrationTest(TransactionTestCase):
    migrate_from = [('dominial', '0044_imovel_identidade_constraint')]
    migrate_to = [('dominial', '0045_imovel_cartorio_not_null')]

    def setUp(self):
        super().setUp()
        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.migrate_from)
        self.apps_antes = self.executor.loader.project_state(
            self.migrate_from
        ).apps
        self.tis, self.pessoa = self.criar_base()

    def tearDown(self):
        executor = MigrationExecutor(connection)
        self.apps_antes.get_model('dominial', 'Imovel').objects.all().delete()
        executor.migrate(self.migrate_to)
        super().tearDown()

    def criar_base(self):
        TIs = self.apps_antes.get_model('dominial', 'TIs')
        Pessoas = self.apps_antes.get_model('dominial', 'Pessoas')
        tis = TIs.objects.create(
            nome='TI Migração Cartório',
            codigo='TI-MIG-CARTORIO',
            etnia='Teste',
        )
        pessoa = Pessoas.objects.create(nome='Pessoa Migração Cartório')
        return tis, pessoa

    def criar_imovel_sem_cartorio(self, apps, matricula='123'):
        Imovel = apps.get_model('dominial', 'Imovel')
        return Imovel.objects.create(
            terra_indigena_id_id=self.tis.pk,
            proprietario_id=self.pessoa.pk,
            nome='Sem cartório',
            matricula=matricula,
            tipo_documento_principal='matricula',
            cartorio_id=None,
        )

    def migrar(self, destino):
        executor = MigrationExecutor(connection)
        executor.migrate(destino)
        return executor.loader.project_state(destino).apps

    def test_avanco_com_legado_sem_cartorio_e_interrompido(self):
        imovel = self.criar_imovel_sem_cartorio(self.apps_antes)

        with self.assertRaisesMessage(RuntimeError, str(imovel.pk)):
            self.migrar(self.migrate_to)

    def test_avanco_limpo_aplica_not_null_no_banco(self):
        apps_depois = self.migrar(self.migrate_to)

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.criar_imovel_sem_cartorio(apps_depois)

    def test_reversao_restaura_suporte_tecnico_a_null(self):
        self.migrar(self.migrate_to)
        apps_revertidas = self.migrar(self.migrate_from)

        imovel = self.criar_imovel_sem_cartorio(apps_revertidas)

        self.assertIsNone(imovel.cartorio_id)
