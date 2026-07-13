from datetime import date

from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class DocumentoIdentidadeMigrationTest(TransactionTestCase):
    migrate_from = [('dominial', '0042_fix_matricula_unique_constraint')]
    migrate_to = [('dominial', '0043_documento_identidade_constraint')]

    def setUp(self):
        super().setUp()
        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.migrate_from)
        self.apps_antes = self.executor.loader.project_state(
            self.migrate_from
        ).apps

    def tearDown(self):
        # Remover dados de cada cenário antes de restaurar o schema mais novo.
        executor = MigrationExecutor(connection)
        estado_atual = executor.loader.project_state().apps
        estado_atual.get_model('dominial', 'Documento').objects.all().delete()
        executor.migrate(self.migrate_to)
        super().tearDown()

    def criar_base(self):
        Cartorio = self.apps_antes.get_model('dominial', 'Cartorios')
        TIs = self.apps_antes.get_model('dominial', 'TIs')
        Pessoas = self.apps_antes.get_model('dominial', 'Pessoas')
        Imovel = self.apps_antes.get_model('dominial', 'Imovel')
        DocumentoTipo = self.apps_antes.get_model('dominial', 'DocumentoTipo')

        cartorio = Cartorio.objects.create(
            nome='Cartório Migração',
            cns='999999',
            cidade='Teste',
            estado='TS',
        )
        tis = TIs.objects.create(
            nome='TI Migração',
            codigo='TI-MIG',
            etnia='Teste',
        )
        pessoa = Pessoas.objects.create(nome='Pessoa Migração')
        imovel_a = Imovel.objects.create(
            terra_indigena_id=tis,
            proprietario=pessoa,
            nome='Imóvel A',
            matricula='9001',
            tipo_documento_principal='matricula',
            cartorio=cartorio,
        )
        imovel_b = Imovel.objects.create(
            terra_indigena_id=tis,
            proprietario=pessoa,
            nome='Imóvel B',
            matricula='9002',
            tipo_documento_principal='transcricao',
            cartorio=cartorio,
        )
        matricula = DocumentoTipo.objects.create(tipo='matricula')
        transcricao = DocumentoTipo.objects.create(tipo='transcricao')
        return cartorio, imovel_a, imovel_b, matricula, transcricao

    def criar_documento(self, apps, imovel, tipo, numero, cartorio):
        Documento = apps.get_model('dominial', 'Documento')
        return Documento.objects.create(
            imovel=imovel,
            tipo=tipo,
            numero=numero,
            data=date(2026, 1, 1),
            cartorio=cartorio,
            livro='1',
            folha='1',
        )

    def migrar_para_destino(self):
        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.migrate_to)
        return self.executor.loader.project_state(self.migrate_to).apps

    def test_avanco_limpo_aplica_identidade_completa(self):
        cartorio, imovel_a, imovel_b, matricula, _ = self.criar_base()
        self.criar_documento(
            self.apps_antes,
            imovel_a,
            matricula,
            '123',
            cartorio,
        )

        apps_depois = self.migrar_para_destino()
        DocumentoTipo = apps_depois.get_model('dominial', 'DocumentoTipo')
        Documento = apps_depois.get_model('dominial', 'Documento')
        transcricao = DocumentoTipo.objects.get(tipo='transcricao')
        imovel_b = apps_depois.get_model('dominial', 'Imovel').objects.get(
            pk=imovel_b.pk
        )
        cartorio = apps_depois.get_model('dominial', 'Cartorios').objects.get(
            pk=cartorio.pk
        )

        self.criar_documento(
            apps_depois,
            imovel_b,
            transcricao,
            '123',
            cartorio,
        )
        self.assertEqual(Documento.objects.filter(numero='123').count(), 2)

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.criar_documento(
                apps_depois,
                imovel_b,
                transcricao,
                '123',
                cartorio,
            )

    def test_avanco_com_conflito_canonico_e_interrompido(self):
        cartorio, imovel_a, imovel_b, matricula, _ = self.criar_base()
        self.criar_documento(
            self.apps_antes,
            imovel_a,
            matricula,
            'M123',
            cartorio,
        )
        self.criar_documento(
            self.apps_antes,
            imovel_b,
            matricula,
            '123',
            cartorio,
        )

        with self.assertRaisesMessage(RuntimeError, 'auditoria de identidade'):
            self.migrar_para_destino()

    def test_reversao_e_interrompida_quando_constraint_antiga_nao_comporta(self):
        cartorio, imovel_a, imovel_b, matricula, _ = self.criar_base()
        self.criar_documento(
            self.apps_antes,
            imovel_a,
            matricula,
            '123',
            cartorio,
        )
        apps_depois = self.migrar_para_destino()
        transcricao = apps_depois.get_model(
            'dominial',
            'DocumentoTipo',
        ).objects.get(tipo='transcricao')
        imovel_b = apps_depois.get_model('dominial', 'Imovel').objects.get(
            pk=imovel_b.pk
        )
        cartorio = apps_depois.get_model('dominial', 'Cartorios').objects.get(
            pk=cartorio.pk
        )
        self.criar_documento(
            apps_depois,
            imovel_b,
            transcricao,
            '123',
            cartorio,
        )

        executor = MigrationExecutor(connection)
        with self.assertRaisesMessage(RuntimeError, 'Reversão de Documento'):
            executor.migrate(self.migrate_from)
