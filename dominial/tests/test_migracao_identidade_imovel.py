from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class ImovelIdentidadeMigrationTest(TransactionTestCase):
    migrate_from = [('dominial', '0043_documento_identidade_constraint')]
    migrate_to = [('dominial', '0044_imovel_identidade_constraint')]

    def setUp(self):
        super().setUp()
        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.migrate_from)
        self.apps_antes = self.executor.loader.project_state(
            self.migrate_from
        ).apps
        self.cartorio, self.tis, self.pessoa = self.criar_base()

    def tearDown(self):
        executor = MigrationExecutor(connection)
        estado_atual = executor.loader.project_state().apps
        estado_atual.get_model('dominial', 'Imovel').objects.all().delete()
        executor.migrate(self.migrate_to)
        super().tearDown()

    def criar_base(self):
        Cartorio = self.apps_antes.get_model('dominial', 'Cartorios')
        TIs = self.apps_antes.get_model('dominial', 'TIs')
        Pessoas = self.apps_antes.get_model('dominial', 'Pessoas')
        cartorio = Cartorio.objects.create(
            nome='Cartório Migração Imóvel',
            cns='888888',
            cidade='Teste',
            estado='TS',
        )
        tis = TIs.objects.create(
            nome='TI Migração Imóvel',
            codigo='TI-MIG-IMOVEL',
            etnia='Teste',
        )
        pessoa = Pessoas.objects.create(nome='Pessoa Migração Imóvel')
        return cartorio, tis, pessoa

    def criar_imovel(self, apps, matricula, tipo, nome):
        Imovel = apps.get_model('dominial', 'Imovel')
        return Imovel.objects.create(
            terra_indigena_id_id=self.tis.pk,
            proprietario_id=self.pessoa.pk,
            nome=nome,
            matricula=matricula,
            tipo_documento_principal=tipo,
            cartorio_id=self.cartorio.pk,
        )

    def migrar_para_destino(self):
        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.migrate_to)
        return self.executor.loader.project_state(self.migrate_to).apps

    def test_avanco_limpo_permite_tipos_homonimos_e_bloqueia_identidade_igual(self):
        self.criar_imovel(
            self.apps_antes,
            matricula='123',
            tipo='matricula',
            nome='Matrícula',
        )

        apps_depois = self.migrar_para_destino()
        self.criar_imovel(
            apps_depois,
            matricula='123',
            tipo='transcricao',
            nome='Transcrição',
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.criar_imovel(
                apps_depois,
                matricula='123',
                tipo='transcricao',
                nome='Transcrição duplicada',
            )

    def test_avanco_com_conflito_canonico_e_interrompido(self):
        self.criar_imovel(
            self.apps_antes,
            matricula='M123',
            tipo='matricula',
            nome='Prefixada',
        )
        self.criar_imovel(
            self.apps_antes,
            matricula='123',
            tipo='matricula',
            nome='Canônica',
        )

        with self.assertRaisesMessage(RuntimeError, 'auditoria de identidade'):
            self.migrar_para_destino()

    def test_reversao_e_interrompida_quando_tipos_homonimos_existirem(self):
        self.criar_imovel(
            self.apps_antes,
            matricula='123',
            tipo='matricula',
            nome='Matrícula',
        )
        apps_depois = self.migrar_para_destino()
        self.criar_imovel(
            apps_depois,
            matricula='123',
            tipo='transcricao',
            nome='Transcrição',
        )

        executor = MigrationExecutor(connection)
        with self.assertRaisesMessage(RuntimeError, 'Reversão de Imovel'):
            executor.migrate(self.migrate_from)
