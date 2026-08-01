import csv
import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import skipUnless
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import SimpleTestCase, TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext

from dominial.management.commands.relatorio_cartorios_suspeitos import (
    SQL_CTE_ESCRITA,
    SQL_ESCRITA,
    _coletar_diagnostico,
    banco_somente_leitura,
    calcular_severidade,
    classificar_documento,
    coletar_contagens_fks,
    simular_merges,
    validar_relacoes_cartorio,
)
from dominial.models import (
    Alteracoes,
    AlteracoesTipo,
    Cartorios,
    Documento,
    DocumentoTipo,
    Imovel,
    Lancamento,
    LancamentoTipo,
    Pessoas,
    TIs,
)


class ClassificacaoDocumentoTest(SimpleTestCase):
    def test_cinco_estados_respeitam_prioridade(self):
        casos = (
            ((True, True, None), 'ATIVO'),
            ((True, True, 99), 'AMBIGUO'),
            ((False, True, 99), 'EM_CADEIA'),
            ((False, False, 99), 'ORFAO'),
            ((False, False, None), 'DESCARTAVEL'),
        )
        for argumentos, esperado in casos:
            with self.subTest(esperado=esperado):
                self.assertEqual(classificar_documento(*argumentos), esperado)

    def test_severidade_escolhe_o_maximo_de_sinais_sobrepostos(self):
        self.assertEqual(
            calcular_severidade(
                sintetico=True,
                classificacoes=['ORFAO', 'ATIVO'],
                duplicidade_nome=True,
                total_vinculos=2,
            ),
            'CRITICAL',
        )
        self.assertEqual(
            calcular_severidade(
                sintetico=True,
                classificacoes=['ORFAO', 'DESCARTAVEL'],
                duplicidade_nome=False,
                total_vinculos=2,
            ),
            'HIGH',
        )


class RelatorioFixtureMixin:
    @classmethod
    def setUpTestData(cls):
        cls.ti = TIs.objects.create(nome='TI Issue 110', codigo='ISSUE110', etnia='Teste')
        cls.pessoa = Pessoas.objects.create(nome='Pessoa Issue 110', cpf='11000000000')
        cls.tipo_documento = DocumentoTipo.objects.create(tipo='matricula')
        cls.tipo_registro = LancamentoTipo.objects.create(tipo='registro')
        cls.tipo_inicio = LancamentoTipo.objects.create(tipo='inicio_matricula')
        cls.tipo_alteracao = AlteracoesTipo.objects.create(tipo='registro')
        cls.correto = Cartorios.objects.create(
            id=1347,
            nome='Registro de Imóveis de Ponta Porã',
            cns='158030',
            cidade='Ponta Pora',
            estado='MS',
            tipo='CRI',
        )
        dados_fantasmas = (
            (3488, '1º CRI Dourados', 'CNS2339110126'),
            (3529, 'CRI Ponta Porã', 'CNS1089051924'),
            (3707, 'CRI Caarapó', 'CNS1687534899'),
            (3983, 'CRI Iguatemi', 'CNS1472193567'),
        )
        cls.fantasmas = {}
        cls.imoveis = {}
        for cartorio_id, nome, cns in dados_fantasmas:
            cartorio = Cartorios.objects.create(
                id=cartorio_id,
                nome=nome,
                cns=cns,
                cidade='ASSIS BRASIL',
                estado=None,
                tipo='CRI',
            )
            cls.fantasmas[cartorio_id] = cartorio
            cls.imoveis[cartorio_id] = cls._criar_imovel(
                f'F-{cartorio_id}', cartorio, f'Imóvel {cartorio_id}'
            )
        cls.imovel_correto = cls._criar_imovel('CORRETO-110', cls.correto, 'Correto')
        cls.cri_sem_uso = Cartorios.objects.create(
            nome='CRI válido sem uso', cns='123455', cidade='Campo Grande',
            estado='MS', tipo='CRI',
        )
        cls.outro_fantasma = Cartorios.objects.create(
            nome='Tabelionato fora do escopo', cns='OUTRO-110',
            cidade='ASSIS BRASIL', estado=None, tipo='OUTRO',
        )

        cls.ativo = cls._criar_documento(3529, 'A100')
        cls._criar_lancamento(cls.ativo, cls.tipo_registro)

        cls.ambiguo = cls._criar_documento(3529, 'B200')
        cls._criar_lancamento(cls.ambiguo, cls.tipo_registro)
        cls.duplicata_ambiguo = cls._criar_documento_correto('B200')

        cls.em_cadeia = cls._criar_documento(3529, 'C300')
        cls.documento_pai = cls._criar_documento_correto('P301')
        cls.lancamento_cadeia = cls._criar_lancamento(
            cls.documento_pai, cls.tipo_inicio, documento_origem=cls.em_cadeia
        )

        cls.orfao = cls._criar_documento(3529, 'D400')
        cls.duplicata_orfao = cls._criar_documento_correto('D400')
        cls.descartavel = cls._criar_documento(3529, 'E500')

        for cartorio_id in (3488, 3707, 3983):
            documento = cls._criar_documento(cartorio_id, f'A-{cartorio_id}')
            cls._criar_lancamento(documento, cls.tipo_registro)

    @classmethod
    def _criar_imovel(cls, matricula, cartorio, nome):
        return Imovel.objects.create(
            terra_indigena_id=cls.ti,
            nome=nome,
            proprietario=cls.pessoa,
            matricula=matricula,
            tipo_documento_principal='matricula',
            cartorio=cartorio,
        )

    @classmethod
    def _criar_documento(cls, cartorio_id, numero):
        return Documento.objects.create(
            imovel=cls.imoveis[cartorio_id],
            tipo=cls.tipo_documento,
            numero=numero,
            data='2026-08-01',
            cartorio=cls.fantasmas[cartorio_id],
            livro='1',
            folha='1',
        )

    @classmethod
    def _criar_documento_correto(cls, numero):
        return Documento.objects.create(
            imovel=cls.imovel_correto,
            tipo=cls.tipo_documento,
            numero=numero,
            data='2026-08-01',
            cartorio=cls.correto,
            livro='1',
            folha='1',
        )

    @classmethod
    def _criar_lancamento(cls, documento, tipo, documento_origem=None):
        return Lancamento.objects.create(
            documento=documento,
            tipo=tipo,
            data='2026-08-01',
            documento_origem=documento_origem,
            cartorio_origem=documento.cartorio if tipo == cls.tipo_inicio else None,
        )

    def pares_manuais(self):
        return [
            {'source_id': cartorio_id, 'target_id': self.correto.pk, 'linha': indice + 2}
            for indice, cartorio_id in enumerate((3488, 3529, 3707, 3983))
        ]

    def diagnostico(self):
        return _coletar_diagnostico(self.pares_manuais(), None, {})[0]


class RelatorioDiagnosticoTest(RelatorioFixtureMixin, TestCase):
    def test_filtro_apenas_cri_com_estado_ausente(self):
        ids = {item['id'] for item in self.diagnostico()['fantasmas']}

        self.assertNotIn(self.outro_fantasma.pk, ids)
        self.assertNotIn(self.cri_sem_uso.pk, ids)
        self.assertEqual(ids, {3488, 3529, 3707, 3983})

    def test_classifica_ativo_ambiguo_em_cadeia_orfao_e_descartavel(self):
        por_id = {item['id']: item for item in self.diagnostico()['documentos']}

        self.assertEqual(por_id[self.ativo.pk]['classificacao'], 'ATIVO')
        self.assertEqual(por_id[self.ambiguo.pk]['classificacao'], 'AMBIGUO')
        self.assertEqual(
            por_id[self.ambiguo.pk]['duplicata_id'], self.duplicata_ambiguo.pk
        )
        self.assertEqual(por_id[self.em_cadeia.pk]['classificacao'], 'EM_CADEIA')
        self.assertEqual(por_id[self.orfao.pk]['classificacao'], 'ORFAO')
        self.assertEqual(por_id[self.orfao.pk]['duplicata_id'], self.duplicata_orfao.pk)
        self.assertEqual(por_id[self.descartavel.pk]['classificacao'], 'DESCARTAVEL')

    def test_cadeia_informa_lancamento_e_documento_pai(self):
        cadeia = self.diagnostico()['cadeias'][0]

        self.assertEqual(cadeia['documento_id'], self.em_cadeia.pk)
        self.assertEqual(cadeia['lancamento_origem_id'], self.lancamento_cadeia.pk)
        self.assertEqual(cadeia['documento_pai_id'], self.documento_pai.pk)

    def test_quatro_fantasmas_criticos_e_localidade_copiada(self):
        fantasmas = {item['id']: item for item in self.diagnostico()['fantasmas']}

        for cartorio_id in (3488, 3529, 3707, 3983):
            with self.subTest(cartorio_id=cartorio_id):
                self.assertEqual(fantasmas[cartorio_id]['severidade'], 'CRITICAL')
                self.assertIn('LOCALIDADE_COPIADA', fantasmas[cartorio_id]['sinais'])
                self.assertIn('CNS_SINTETICO', fantasmas[cartorio_id]['sinais'])

    def test_contagem_das_oito_fks_em_ate_onze_queries(self):
        with CaptureQueriesContext(connection) as consultas:
            contagens = coletar_contagens_fks([3529])

        self.assertEqual(len(consultas), 8)
        self.assertEqual(contagens[3529]['documento.cartorio'], 5)
        self.assertEqual(contagens[3529]['imovel.cartorio'], 1)
        self.assertEqual(len(contagens[3529]), 8)

    def test_saida_json_atomica_e_recusa_sobrescrever(self):
        with tempfile.TemporaryDirectory() as diretorio:
            destino = Path(diretorio) / 'relatorio.json'
            call_command('relatorio_cartorios_suspeitos', output=destino, format='json')
            relatorio = json.loads(destino.read_text(encoding='utf-8'))

            self.assertTrue(relatorio['metadata']['somente_leitura'])
            self.assertEqual(relatorio['resumo']['fantasmas_cri'], 4)
            with self.assertRaises(CommandError):
                call_command('relatorio_cartorios_suspeitos', output=destino, format='json')
            call_command(
                'relatorio_cartorios_suspeitos', output=destino,
                format='json', force=True,
            )

    def test_saida_csv_tem_record_types_e_ordenacao(self):
        with tempfile.TemporaryDirectory() as diretorio:
            destino = Path(diretorio) / 'relatorio.csv'
            call_command('relatorio_cartorios_suspeitos', output=destino, format='csv')
            with destino.open(encoding='utf-8', newline='') as arquivo:
                registros = list(csv.DictReader(arquivo))

        tipos = {item['record_type'] for item in registros}
        self.assertTrue({'FANTASMA', 'DOCUMENTO', 'LANCAMENTO', 'CADEIA', 'RESUMO'} <= tipos)
        ids_fantasmas = [
            int(item['id']) for item in registros if item['record_type'] == 'FANTASMA'
        ]
        self.assertEqual(ids_fantasmas, sorted(ids_fantasmas))

    def test_fk_nova_falha_explicitamente(self):
        relacao_falsa = SimpleNamespace(
            related_model=Documento,
            field=SimpleNamespace(name='nova_fk_cri'),
        )
        relacoes = list(Cartorios._meta.related_objects) + [relacao_falsa]

        with patch.object(Cartorios._meta, 'related_objects', relacoes):
            with self.assertRaisesMessage(CommandError, 'relações desconhecidas'):
                validar_relacoes_cartorio()


class SimulacaoMergeTest(RelatorioFixtureMixin, TestCase):
    def _par(self, source, target=None):
        return [{'source_id': source.pk, 'target_id': (target or self.correto).pk, 'linha': 2}]

    def test_simulacao_segura(self):
        source = Cartorios.objects.create(
            nome='Fantasma seguro', cns='CNS-SEGURO', cidade='ASSIS BRASIL',
            estado=None, tipo='CRI',
        )
        resultados, conflitos = simular_merges(self._par(source))

        self.assertEqual(resultados[0]['status'], 'SEGURO')
        self.assertEqual(conflitos, [])

    def test_simulacao_conflito_reporta_os_dois_pks(self):
        resultados, conflitos = simular_merges(self._par(self.fantasmas[3529]))

        self.assertEqual(resultados[0]['status'], 'CONFLITO')
        self.assertTrue(any(item['constraint'] == 'unique_documento_identidade_canonica' for item in conflitos))
        self.assertTrue(all(len(item['pks']) == 2 for item in conflitos))

    def test_simulacao_ciclo(self):
        source = self.fantasmas[3488]
        target = self.fantasmas[3707]
        pares = [
            {'source_id': source.pk, 'target_id': target.pk, 'linha': 2},
            {'source_id': target.pk, 'target_id': source.pk, 'linha': 3},
        ]

        resultados, _ = simular_merges(pares)

        self.assertEqual({item['status'] for item in resultados}, {'CICLO'})

    def test_simulacao_fonte_repetida(self):
        source = self.fantasmas[3488]
        outro_target = Cartorios.objects.create(
            nome='Outro target', cns='TARGET-110', cidade='Dourados',
            estado='MS', tipo='CRI',
        )
        pares = self._par(source) + self._par(source, outro_target)

        resultados, _ = simular_merges(pares)

        self.assertEqual({item['status'] for item in resultados}, {'FONTE_REPETIDA'})

    def test_simulacao_cascade(self):
        source = Cartorios.objects.create(
            nome='Fantasma cascade', cns='CNS-CASCADE', cidade='ASSIS BRASIL',
            estado=None, tipo='CRI',
        )
        alteracao = Alteracoes.objects.create(
            imovel_id=self.imovel_correto,
            tipo_alteracao_id=self.tipo_alteracao,
            cartorio=source,
            cartorio_origem=self.correto,
        )

        resultados, _ = simular_merges(self._par(source))

        self.assertEqual(resultados[0]['status'], 'CASCADE_RISCO')
        self.assertEqual(resultados[0]['cascade_pks']['cartorio'], [alteracao.pk])

    def test_simulacao_cadeia_afetada(self):
        source = Cartorios.objects.create(
            nome='Fantasma cadeia', cns='CNS-CADEIA', cidade='ASSIS BRASIL',
            estado=None, tipo='CRI',
        )
        imovel = self._criar_imovel('CHAIN-SOURCE', source, 'Cadeia source')
        documento = Documento.objects.create(
            imovel=imovel, tipo=self.tipo_documento, numero='CHAIN-1',
            data='2026-08-01', cartorio=source, livro='1', folha='1',
        )
        lancamento = self._criar_lancamento(
            self.documento_pai, self.tipo_inicio, documento_origem=documento
        )

        resultados, _ = simular_merges(self._par(source))

        self.assertEqual(resultados[0]['status'], 'CADEIA_AFETADA')
        self.assertEqual(
            resultados[0]['cadeias_afetadas'][0]['lancamento_origem_id'],
            lancamento.pk,
        )

    def test_simulacao_schema_divergente(self):
        source = Cartorios.objects.create(
            nome='Fantasma drift', cns='CNS-DRIFT', cidade='ASSIS BRASIL',
            estado=None, tipo='CRI',
        )

        with patch(
            'dominial.management.commands.relatorio_cartorios_suspeitos._constraints_divergentes',
            return_value=['constraint ausente'],
        ):
            resultados, _ = simular_merges(self._par(source))

        self.assertEqual(resultados[0]['status'], 'SCHEMA_DIVERGENTE')


def _hash_tabelas_sqlite():
    digest = hashlib.sha256()
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        tabelas = [linha[0] for linha in cursor.fetchall()]
        for tabela in tabelas:
            cursor.execute(f'SELECT * FROM "{tabela}" ORDER BY rowid')
            digest.update(tabela.encode())
            digest.update(repr(cursor.fetchall()).encode())
    return digest.hexdigest()


@skipUnless(connection.vendor == 'sqlite', 'prova específica para SQLite')
class ReadOnlySQLiteTest(RelatorioFixtureMixin, TestCase):
    def test_query_only_bloqueia_escrita_deliberada_e_command_nao_muda_tabelas(self):
        antes = _hash_tabelas_sqlite()
        with banco_somente_leitura():
            with self.assertRaises(sqlite3.OperationalError):
                connection.connection.execute(
                    "UPDATE dominial_cartorios SET nome = 'PROIBIDO' WHERE id = 3488"
                )
        with tempfile.TemporaryDirectory() as diretorio:
            destino = Path(diretorio) / 'read-only.json'
            with CaptureQueriesContext(connection) as consultas:
                call_command(
                    'relatorio_cartorios_suspeitos', output=destino, format='json'
                )
        depois = _hash_tabelas_sqlite()

        self.assertEqual(antes, depois)
        for consulta in consultas.captured_queries:
            with self.subTest(sql=consulta['sql']):
                self.assertIsNone(SQL_ESCRITA.search(consulta['sql']))
                self.assertIsNone(SQL_CTE_ESCRITA.search(consulta['sql']))


@skipUnless(connection.vendor == 'postgresql', 'PostgreSQL não configurado')
class ReadOnlyPostgresTest(RelatorioFixtureMixin, TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        type(self).setUpTestData()

    def test_transaction_read_only_bloqueia_escrita_deliberada(self):
        with banco_somente_leitura():
            with self.assertRaises(Exception):
                with connection.connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE dominial_cartorios SET nome = 'PROIBIDO' WHERE id = 3488"
                    )
