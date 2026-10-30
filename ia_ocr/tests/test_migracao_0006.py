"""Migração 0006 (I-5): campos da fase de extração, data legado e constraints.

Cobre dependências mínimas, avanço da migração anterior (0005, versão da
página, da I-4) com dados legados e a reversão com raw/normalized NULL (o
reverso devolve '' antes da volta ao NOT NULL).
"""

from django.conf import settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.loader import MigrationLoader
from django.test import SimpleTestCase, TransactionTestCase

MIGRACAO_ANTERIOR = ('ia_ocr', '0005_paginaocr_versao')
MIGRACAO_0006 = ('ia_ocr', '0006_extracao_revisao')


class DependenciasDa0006Test(SimpleTestCase):
    def test_dependencias_minimas(self):
        # MigrationLoader(None, ...) lê o grafo do disco, sem banco.
        loader = MigrationLoader(None, ignore_no_migrations=True)
        node = loader.graph.node_map[MIGRACAO_0006]
        pais = {p.key for p in node.parents if p is not None}
        app_usuario = settings.AUTH_USER_MODEL.split('.')[0]
        pais_usuario = {p for p in pais if p[0] == app_usuario}
        self.assertEqual(
            pais - pais_usuario,
            {MIGRACAO_ANTERIOR, ('dominial', '0001_initial')},
        )
        self.assertEqual(len(pais_usuario), 1)


class ExtracaoRevisao0006Test(TransactionTestCase):
    migrate_from = [MIGRACAO_ANTERIOR]
    migrate_to = [MIGRACAO_0006]

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        self.apps_antes = executor.loader.project_state(
            self.migrate_from
        ).apps

    def tearDown(self):
        # Restaurar o grafo inteiro, não só a 0006: a 0007/0008 foi
        # des-aplicada junto no setUp (dependem da dominial) e o flush do
        # TransactionTestCase precisa de todas as tabelas do estado atual.
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def _migrar(self, destino):
        executor = MigrationExecutor(connection)
        executor.migrate(destino)
        return executor.loader.project_state(destino).apps

    def _criar_job_com_extracao(self, apps):
        """Job + extração + 2 campos no estado anterior (modelos históricos).

        O DocumentoDigital sai da fábrica corrente: as tabelas dominial do
        banco de teste ficam no estado atual — só a ia_ocr volta no tempo.
        """
        from ia_ocr.tests.factories import criar_documento_digital

        OcrJob = apps.get_model('ia_ocr', 'OcrJob')
        ExtracaoSugerida = apps.get_model('ia_ocr', 'ExtracaoSugerida')
        CampoSugerido = apps.get_model('ia_ocr', 'CampoSugerido')
        # O modelo histórico de OcrJob aponta para o DocumentoDigital
        # histórico (classe ≠ da corrente): liga pelo id.
        documento_digital = criar_documento_digital()
        job = OcrJob.objects.create(
            documento_digital_id=documento_digital.pk,
        )
        extracao = ExtracaoSugerida.objects.create(
            ocr_job=job,
            schema_version='umbelino-extracao-matricula-v1',
            payload={'marcador': 1},
            provider='stub',
        )
        campos = [
            CampoSugerido.objects.create(
                extracao=extracao, chave=letra, raw='', normalized='',
            )
            for letra in ('a', 'b')
        ]
        return job, extracao, campos

    def test_anterior_com_extracao_e_campos_para_0006(self):
        job, extracao, campos = self._criar_job_com_extracao(self.apps_antes)

        apps_depois = self._migrar(self.migrate_to)
        ExtracaoSugerida = apps_depois.get_model('ia_ocr', 'ExtracaoSugerida')
        CampoSugerido = apps_depois.get_model('ia_ocr', 'CampoSugerido')

        extracao_depois = ExtracaoSugerida.objects.get(pk=extracao.pk)
        self.assertEqual(extracao_depois.payload_servico, {'marcador': 1})

        for campo_legado, letra in zip(campos, ('a', 'b')):
            campo = CampoSugerido.objects.get(pk=campo_legado.pk)
            with self.subTest(chave=letra):
                self.assertEqual(campo.tipo_valor, 'texto')
                self.assertTrue(campo.requer_revisao)
                self.assertEqual(campo.motivos_revisao, ['legado'])
                campo.full_clean()

    def test_colunas_texto_corrigido_e_dpi(self):
        """0006 acrescenta ocrjob.dpi, paginaocr.texto_corrigido e
        paginaocr.corrigido_em, todos nullable (decisão #290/16-10)."""
        job, _, _ = self._criar_job_com_extracao(self.apps_antes)
        pagina_antes = self.apps_antes.get_model(
            'ia_ocr', 'PaginaOcr'
        ).objects.create(
            ocr_job=job, numero_pagina=1, texto_ocr='texto do ocr',
        )

        apps_depois = self._migrar(self.migrate_to)
        OcrJob = apps_depois.get_model('ia_ocr', 'OcrJob')
        PaginaOcr = apps_depois.get_model('ia_ocr', 'PaginaOcr')

        # Ler as colunas novas prova que existem; o SELECT seria recusado
        # com OperationalError caso contrário.
        job_depois = OcrJob.objects.get(pk=job.pk)
        pagina_depois = PaginaOcr.objects.get(pk=pagina_antes.pk)
        # Nenhum valor informado: NULL é aceito (nullable).
        self.assertIsNone(job_depois.dpi)
        self.assertIsNone(pagina_depois.texto_corrigido)
        self.assertIsNone(pagina_depois.corrigido_em)

    def test_texto_corrigido_distinto_de_texto_ocr(self):
        """O texto devolvido pelo serviço (corrigido) convive com o texto
        original do OCR: gravar um não apaga o outro."""
        job, _, _ = self._criar_job_com_extracao(self.apps_antes)
        pagina_antes = self.apps_antes.get_model(
            'ia_ocr', 'PaginaOcr'
        ).objects.create(
            ocr_job=job, numero_pagina=1, texto_ocr='a',
        )

        apps_depois = self._migrar(self.migrate_to)
        PaginaOcr = apps_depois.get_model('ia_ocr', 'PaginaOcr')
        pagina = PaginaOcr.objects.get(pk=pagina_antes.pk)
        pagina.texto_corrigido = 'b'
        pagina.save(update_fields=['texto_corrigido'])
        pagina.refresh_from_db()
        self.assertEqual(pagina.texto_ocr, 'a')
        self.assertEqual(pagina.texto_corrigido, 'b')

    def test_reversao_com_raw_normalized_null(self):
        self._criar_job_com_extracao(self.apps_antes)
        apps_0006 = self._migrar(self.migrate_to)
        ExtracaoSugerida = apps_0006.get_model('ia_ocr', 'ExtracaoSugerida')
        CampoSugerido = apps_0006.get_model('ia_ocr', 'CampoSugerido')
        extracao = ExtracaoSugerida.objects.get()
        campo = CampoSugerido.objects.create(
            extracao=extracao, chave='z', raw=None, normalized=None,
        )
        pk_campo, pk_extracao = campo.pk, extracao.pk

        apps_anterior = self._migrar(self.migrate_from)
        CampoSugerido = apps_anterior.get_model('ia_ocr', 'CampoSugerido')
        # O reverso rodou antes da volta ao NOT NULL e preencheu com ''.
        revertido = CampoSugerido.objects.get(pk=pk_campo)
        self.assertEqual(revertido.raw, '')
        self.assertEqual(revertido.normalized, '')

        apps_volta = self._migrar(self.migrate_to)
        CampoSugerido = apps_volta.get_model('ia_ocr', 'CampoSugerido')
        avancado = CampoSugerido.objects.get(pk=pk_campo)
        self.assertEqual(avancado.raw, '')
        self.assertEqual(avancado.normalized, '')
        self.assertEqual(avancado.extracao_id, pk_extracao)
