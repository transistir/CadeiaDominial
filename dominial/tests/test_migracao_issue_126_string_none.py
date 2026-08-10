from datetime import date

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


CAMPOS_POR_MODELO = {
    'Lancamento': (
        'titulo', 'forma', 'descricao', 'origem', 'detalhes',
        'observacoes', 'numero_lancamento', 'livro_transacao',
        'folha_transacao', 'livro_origem', 'folha_origem',
    ),
    'Documento': (
        'origem', 'observacoes', 'classificacao_fim_cadeia',
        'sigla_patrimonio_publico',
    ),
    'Imovel': ('observacoes',),
    'Alteracoes': (
        'titulo', 'observacoes', 'livro', 'folha',
        'livro_origem', 'folha_origem',
    ),
    'FimCadeia': ('descricao', 'sigla'),
    'LancamentoOrigem': ('livro', 'folha'),
}


class NormalizaNoneTextualMigrationTest(TransactionTestCase):
    migrate_from = [('dominial', '0055_add_data_presumida_documento')]
    migrate_to = [('dominial', '0056_normaliza_none_textual')]

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        self.apps_antes = executor.loader.project_state(self.migrate_from).apps
        self._criar_base()

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        super().tearDown()

    def _criar_base(self):
        apps = self.apps_antes
        Cartorio = apps.get_model('dominial', 'Cartorios')
        TIs = apps.get_model('dominial', 'TIs')
        Pessoas = apps.get_model('dominial', 'Pessoas')
        DocumentoTipo = apps.get_model('dominial', 'DocumentoTipo')
        LancamentoTipo = apps.get_model('dominial', 'LancamentoTipo')
        AlteracoesTipo = apps.get_model('dominial', 'AlteracoesTipo')

        self.cartorio = Cartorio.objects.create(
            nome='Cartório 126', cns='CNS-126', cidade='Teste', estado='TS',
        )
        self.tis = TIs.objects.create(nome='TI 126', codigo='TI-126', etnia='Teste')
        self.pessoa = Pessoas.objects.create(nome='Pessoa 126')
        self.doc_tipo = DocumentoTipo.objects.create(tipo='matricula')
        self.lanc_tipo = LancamentoTipo.objects.create(tipo='averbacao')
        self.alt_tipo = AlteracoesTipo.objects.create(tipo='averbacao')

        self.imovel = apps.get_model('dominial', 'Imovel').objects.create(
            terra_indigena_id_id=self.tis.pk,
            proprietario_id=self.pessoa.pk,
            nome='Imóvel 126',
            matricula='126',
            cartorio_id=self.cartorio.pk,
        )
        self.documento = apps.get_model('dominial', 'Documento').objects.create(
            imovel_id=self.imovel.pk,
            tipo_id=self.doc_tipo.pk,
            numero='M126',
            data=date(2026, 1, 1),
            cartorio_id=self.cartorio.pk,
            livro='1',
            folha='1',
        )

    def _criar_instancia(self, apps, model_name, valor, extra_seq=0):
        """Cria uma instância do modelo com `valor` em todos os campos auditados."""
        model = apps.get_model('dominial', model_name)
        dados = {campo: valor for campo in CAMPOS_POR_MODELO[model_name]}

        if model_name == 'Lancamento':
            dados.update(
                documento_id=self.documento.pk,
                tipo_id=self.lanc_tipo.pk,
                data=date(2026, 1, 1),
            )
        elif model_name == 'Documento':
            dados.update(
                imovel_id=self.imovel.pk,
                tipo_id=self.doc_tipo.pk,
                numero=f'M-EXTRA-{extra_seq}',
                data=date(2026, 1, 1),
                cartorio_id=self.cartorio.pk,
                livro='1',
                folha='1',
            )
        elif model_name == 'Imovel':
            dados.update(
                terra_indigena_id_id=self.tis.pk,
                proprietario_id=self.pessoa.pk,
                nome=f'Imóvel Extra {extra_seq}',
                matricula=f'EXTRA-{extra_seq}',
                cartorio_id=self.cartorio.pk,
            )
        elif model_name == 'Alteracoes':
            dados.update(
                imovel_id_id=self.imovel.pk,
                tipo_alteracao_id_id=self.alt_tipo.pk,
                cartorio_id=self.cartorio.pk,
                cartorio_origem_id=self.cartorio.pk,
            )
        elif model_name == 'FimCadeia':
            dados.update(
                nome=f'Fim de Cadeia {extra_seq}',
                classificacao='sem_origem',
            )
        elif model_name == 'LancamentoOrigem':
            lanc = apps.get_model('dominial', 'Lancamento').objects.create(
                documento_id=self.documento.pk,
                tipo_id=self.lanc_tipo.pk,
                data=date(2026, 1, 1),
            )
            dados.update(
                lancamento_id=lanc.pk,
                indice_origem=extra_seq or 1,
                tipo_documento='matricula',
                numero=f'LO-{extra_seq}',
                cartorio_id=self.cartorio.pk,
            )

        return model.objects.create(**dados)

    def migrar_para_destino(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        return executor.loader.project_state(self.migrate_to).apps

    def migrar_para_origem(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        return executor.loader.project_state(self.migrate_from).apps

    def test_migracao_converte_todos_os_campos_auditados_em_null(self):
        instancias = {}
        for idx, model_name in enumerate(CAMPOS_POR_MODELO):
            instancias[model_name] = self._criar_instancia(
                self.apps_antes, model_name, 'None', extra_seq=idx,
            )

        apps_depois = self.migrar_para_destino()

        for model_name, campos in CAMPOS_POR_MODELO.items():
            model = apps_depois.get_model('dominial', model_name)
            instancia = model.objects.get(pk=instancias[model_name].pk)
            for campo in campos:
                self.assertIsNone(
                    getattr(instancia, campo),
                    f'{model_name}.{campo} deveria ser None após a migração',
                )

    def test_migracao_preserva_textos_validos_e_vazios(self):
        lancamento = self._criar_instancia(self.apps_antes, 'Lancamento', 'Compra e Venda')
        Lancamento = self.apps_antes.get_model('dominial', 'Lancamento')
        lancamento.titulo = ''
        lancamento.forma = None
        lancamento.descricao = 'none'
        lancamento.observacoes = ' None '
        lancamento.save()

        apps_depois = self.migrar_para_destino()
        Lancamento = apps_depois.get_model('dominial', 'Lancamento')
        atualizado = Lancamento.objects.get(pk=lancamento.pk)

        self.assertEqual(atualizado.origem, 'Compra e Venda')
        self.assertEqual(atualizado.titulo, '')
        self.assertIsNone(atualizado.forma)
        self.assertEqual(atualizado.descricao, 'none')
        self.assertEqual(atualizado.observacoes, ' None ')

    def test_migracao_e_idempotente(self):
        self._criar_instancia(self.apps_antes, 'Lancamento', 'None')

        self.migrar_para_destino()
        apps_depois = self.migrar_para_origem()

        Lancamento = apps_depois.get_model('dominial', 'Lancamento')
        self.assertEqual(Lancamento.objects.filter(titulo='None').count(), 0)

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        Lancamento = executor.loader.project_state(self.migrate_to).apps.get_model(
            'dominial', 'Lancamento'
        )
        self.assertEqual(Lancamento.objects.filter(titulo='None').count(), 0)

    def test_reversao_nao_recria_string_none(self):
        lancamento = self._criar_instancia(self.apps_antes, 'Lancamento', 'None')

        self.migrar_para_destino()
        apps_revertidas = self.migrar_para_origem()

        Lancamento = apps_revertidas.get_model('dominial', 'Lancamento')
        atualizado = Lancamento.objects.get(pk=lancamento.pk)
        self.assertIsNone(atualizado.titulo)

    def test_migracao_usa_todos_os_modelos_historicos(self):
        instancias = {}
        for idx, model_name in enumerate(CAMPOS_POR_MODELO):
            instancias[model_name] = self._criar_instancia(
                self.apps_antes, model_name, 'None', extra_seq=100 + idx,
            )

        apps_depois = self.migrar_para_destino()

        for model_name in CAMPOS_POR_MODELO:
            model = apps_depois.get_model('dominial', model_name)
            self.assertTrue(
                model.objects.filter(pk=instancias[model_name].pk).exists()
            )
