from datetime import date

from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class IdentidadeCanonicaMigrationTest(TransactionTestCase):
    migrate_from = [('dominial', '0047_alter_lancamentoorigem_id')]
    migrate_to = [('dominial', '0048_identidade_canonica_gerada')]

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        self.apps_antes = executor.loader.project_state(self.migrate_from).apps
        self.cartorio, self.tis, self.pessoa, self.tipo = self.criar_base()

    def tearDown(self):
        executor = MigrationExecutor(connection)
        self.apps_antes.get_model('dominial', 'Documento').objects.all().delete()
        self.apps_antes.get_model('dominial', 'Imovel').objects.all().delete()
        executor.migrate(self.migrate_to)
        super().tearDown()

    def criar_base(self):
        Cartorio = self.apps_antes.get_model('dominial', 'Cartorios')
        TIs = self.apps_antes.get_model('dominial', 'TIs')
        Pessoas = self.apps_antes.get_model('dominial', 'Pessoas')
        DocumentoTipo = self.apps_antes.get_model('dominial', 'DocumentoTipo')

        cartorio = Cartorio.objects.create(
            nome='Cartório Canônico',
            cns='CANONICO-001',
            cidade='Teste',
            estado='TS',
        )
        tis = TIs.objects.create(
            nome='TI Canônica',
            codigo='TI-CANONICA',
            etnia='Teste',
        )
        pessoa = Pessoas.objects.create(nome='Pessoa Canônica')
        tipo = DocumentoTipo.objects.create(tipo='matricula')
        return cartorio, tis, pessoa, tipo

    def criar_imovel(self, apps, matricula, nome):
        Imovel = apps.get_model('dominial', 'Imovel')
        return Imovel.objects.create(
            terra_indigena_id_id=self.tis.pk,
            proprietario_id=self.pessoa.pk,
            nome=nome,
            matricula=matricula,
            tipo_documento_principal='matricula',
            cartorio_id=self.cartorio.pk,
        )

    def criar_documento(self, apps, imovel_id, numero):
        Documento = apps.get_model('dominial', 'Documento')
        return Documento.objects.create(
            imovel_id=imovel_id,
            tipo_id=self.tipo.pk,
            numero=numero,
            data=date(2026, 1, 1),
            cartorio_id=self.cartorio.pk,
            livro='1',
            folha='1',
        )

    def migrar_para_destino(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        return executor.loader.project_state(self.migrate_to).apps

    def migrar_para_origem(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        return executor.loader.project_state(self.migrate_from).apps

    def test_avanco_limpo_gera_campos_e_protege_novas_gravacoes(self):
        imovel_a = self.criar_imovel(self.apps_antes, '9001', 'Imóvel A')
        imovel_b = self.criar_imovel(self.apps_antes, '9002', 'Imóvel B')
        documento = self.criar_documento(self.apps_antes, imovel_a.pk, 'M 123')

        apps_depois = self.migrar_para_destino()
        Documento = apps_depois.get_model('dominial', 'Documento')
        documento = Documento.objects.get(pk=documento.pk)
        self.assertEqual(documento.numero, 'M 123')
        self.assertEqual(documento.numero_normalizado, '123')

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.criar_documento(apps_depois, imovel_b.pk, '123')

        distinto = self.criar_documento(apps_depois, imovel_b.pk, '00123')
        distinto = Documento.objects.get(pk=distinto.pk)
        self.assertEqual(distinto.numero_normalizado, '00123')

    def test_constraint_canonica_do_imovel_e_aplicada_apos_avanco(self):
        imovel = self.criar_imovel(self.apps_antes, 'M 456', 'Prefixado')

        apps_depois = self.migrar_para_destino()
        Imovel = apps_depois.get_model('dominial', 'Imovel')
        imovel = Imovel.objects.get(pk=imovel.pk)
        self.assertEqual(imovel.matricula_normalizada, '456')

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.criar_imovel(apps_depois, '456', 'Duplicado')

    def test_cr04_conflito_de_documento_interrompe_sem_reescrever(self):
        imovel_a = self.criar_imovel(self.apps_antes, '9001', 'Imóvel A')
        imovel_b = self.criar_imovel(self.apps_antes, '9002', 'Imóvel B')
        documento_a = self.criar_documento(
            self.apps_antes,
            imovel_a.pk,
            'M123',
        )
        documento_b = self.criar_documento(
            self.apps_antes,
            imovel_b.pk,
            '123',
        )

        with self.assertRaisesMessage(RuntimeError, 'identidade_documento'):
            self.migrar_para_destino()

        Documento = self.apps_antes.get_model('dominial', 'Documento')
        self.assertEqual(Documento.objects.get(pk=documento_a.pk).numero, 'M123')
        self.assertEqual(Documento.objects.get(pk=documento_b.pk).numero, '123')

    def test_cr04_conflito_de_imovel_interrompe_sem_reescrever(self):
        imovel_a = self.criar_imovel(self.apps_antes, 'M789', 'Prefixado')
        imovel_b = self.criar_imovel(self.apps_antes, '789', 'Canônico')

        with self.assertRaisesMessage(RuntimeError, 'identidade_imovel'):
            self.migrar_para_destino()

        Imovel = self.apps_antes.get_model('dominial', 'Imovel')
        self.assertEqual(Imovel.objects.get(pk=imovel_a.pk).matricula, 'M789')
        self.assertEqual(Imovel.objects.get(pk=imovel_b.pk).matricula, '789')

    def test_reversao_restaura_constraints_sobre_valores_legados(self):
        imovel_a = self.criar_imovel(self.apps_antes, '9001', 'Imóvel A')
        imovel_b = self.criar_imovel(self.apps_antes, '9002', 'Imóvel B')
        self.criar_documento(self.apps_antes, imovel_a.pk, 'M123')

        self.migrar_para_destino()
        apps_revertidas = self.migrar_para_origem()
        Documento = apps_revertidas.get_model('dominial', 'Documento')
        Imovel = apps_revertidas.get_model('dominial', 'Imovel')

        self.assertNotIn(
            'numero_normalizado',
            {campo.name for campo in Documento._meta.get_fields()},
        )
        self.assertNotIn(
            'matricula_normalizada',
            {campo.name for campo in Imovel._meta.get_fields()},
        )

        # O schema 0047 volta deliberadamente à unicidade textual bruta.
        self.criar_documento(apps_revertidas, imovel_b.pk, '123')
        self.criar_imovel(apps_revertidas, 'M456', 'Prefixado')
        self.criar_imovel(apps_revertidas, '456', 'Canônico')
