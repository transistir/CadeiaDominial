from datetime import date

from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class LancamentoOrigemCanonicaMigrationTest(TransactionTestCase):
    migrate_from = [('dominial', '0048_identidade_canonica_gerada')]
    migrate_to = [('dominial', '0049_lancamento_origem_identidade_canonica')]

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        self.apps_antes = executor.loader.project_state(self.migrate_from).apps
        self.cartorio, self.lancamento = self.criar_base()

    def tearDown(self):
        LancamentoOrigem = self.apps_antes.get_model('dominial', 'LancamentoOrigem')
        Lancamento = self.apps_antes.get_model('dominial', 'Lancamento')
        Documento = self.apps_antes.get_model('dominial', 'Documento')
        Imovel = self.apps_antes.get_model('dominial', 'Imovel')
        LancamentoOrigem.objects.all().delete()
        Lancamento.objects.all().delete()
        Documento.objects.all().delete()
        Imovel.objects.all().delete()
        MigrationExecutor(connection).migrate(self.migrate_to)
        super().tearDown()

    def criar_base(self):
        Cartorio = self.apps_antes.get_model('dominial', 'Cartorios')
        TIs = self.apps_antes.get_model('dominial', 'TIs')
        Pessoas = self.apps_antes.get_model('dominial', 'Pessoas')
        DocumentoTipo = self.apps_antes.get_model('dominial', 'DocumentoTipo')
        Imovel = self.apps_antes.get_model('dominial', 'Imovel')
        Documento = self.apps_antes.get_model('dominial', 'Documento')
        LancamentoTipo = self.apps_antes.get_model('dominial', 'LancamentoTipo')
        Lancamento = self.apps_antes.get_model('dominial', 'Lancamento')

        cartorio = Cartorio.objects.create(
            nome='Cartório Origem Canônica',
            cns='ORIGEM-CANONICA',
            cidade='Teste',
            estado='TS',
        )
        tis = TIs.objects.create(nome='TI Origem', codigo='TI-ORIGEM', etnia='Teste')
        pessoa = Pessoas.objects.create(nome='Pessoa Origem')
        tipo_documento = DocumentoTipo.objects.create(tipo='matricula')
        imovel = Imovel.objects.create(
            terra_indigena_id_id=tis.pk,
            proprietario_id=pessoa.pk,
            nome='Imóvel Origem',
            matricula='999',
            tipo_documento_principal='matricula',
            cartorio_id=cartorio.pk,
        )
        documento = Documento.objects.create(
            imovel_id=imovel.pk,
            tipo_id=tipo_documento.pk,
            numero='M999',
            data=date(2026, 1, 1),
            cartorio_id=cartorio.pk,
            livro='1',
            folha='1',
        )
        tipo_lancamento = LancamentoTipo.objects.create(tipo='inicio_matricula')
        lancamento = Lancamento.objects.create(
            documento_id=documento.pk,
            tipo_id=tipo_lancamento.pk,
            data=date(2026, 1, 2),
            origem='M123',
            cartorio_origem_id=cartorio.pk,
        )
        return cartorio, lancamento

    def criar_origem(self, apps, indice, numero, tipo='matricula'):
        LancamentoOrigem = apps.get_model('dominial', 'LancamentoOrigem')
        return LancamentoOrigem.objects.create(
            lancamento_id=self.lancamento.pk,
            indice_origem=indice,
            tipo_documento=tipo,
            numero=numero,
            cartorio_id=self.cartorio.pk,
        )

    def migrar_para_destino(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        return executor.loader.project_state(self.migrate_to).apps

    def migrar_para_origem(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        return executor.loader.project_state(self.migrate_from).apps

    def test_avanco_preserva_legado_e_protege_gravacao_direta(self):
        origem = self.criar_origem(self.apps_antes, 0, ' M 00123 ')

        apps_depois = self.migrar_para_destino()
        LancamentoOrigem = apps_depois.get_model('dominial', 'LancamentoOrigem')
        origem = LancamentoOrigem.objects.get(pk=origem.pk)
        self.assertEqual(origem.numero, ' M 00123 ')
        self.assertEqual(origem.numero_normalizado, '00123')

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.criar_origem(apps_depois, 1, '00123')

    def test_conflito_canonico_interrompe_sem_reescrever(self):
        origem_a = self.criar_origem(self.apps_antes, 0, 'M123')
        origem_b = self.criar_origem(self.apps_antes, 1, '123')

        with self.assertRaisesMessage(RuntimeError, 'identidade_lancamento_origem'):
            self.migrar_para_destino()

        LancamentoOrigem = self.apps_antes.get_model('dominial', 'LancamentoOrigem')
        self.assertEqual(LancamentoOrigem.objects.get(pk=origem_a.pk).numero, 'M123')
        self.assertEqual(LancamentoOrigem.objects.get(pk=origem_b.pk).numero, '123')

    def test_valor_invalido_interrompe_sem_reescrever(self):
        origem = self.criar_origem(self.apps_antes, 0, 'T123')

        with self.assertRaisesMessage(RuntimeError, 'incompatível'):
            self.migrar_para_destino()

        LancamentoOrigem = self.apps_antes.get_model('dominial', 'LancamentoOrigem')
        self.assertEqual(LancamentoOrigem.objects.get(pk=origem.pk).numero, 'T123')

    def test_reversao_restaura_identidade_textual(self):
        self.criar_origem(self.apps_antes, 0, 'M456')
        self.migrar_para_destino()

        apps_revertidas = self.migrar_para_origem()
        LancamentoOrigem = apps_revertidas.get_model('dominial', 'LancamentoOrigem')
        self.assertNotIn(
            'numero_normalizado',
            {campo.name for campo in LancamentoOrigem._meta.get_fields()},
        )
        self.criar_origem(apps_revertidas, 1, '456')
