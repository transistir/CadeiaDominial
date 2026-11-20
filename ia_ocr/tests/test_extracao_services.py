"""Fachada de testes dos serviços de extração OCR.

Os corpos de ``SolicitarExtracaoTest`` vivem nas partes para manter este
módulo abaixo do limite de 400 linhas. Os nomes e ids dos testes são preservados.
"""

import re
from contextlib import contextmanager
from unittest import mock

from django.db import connection
from django.db.models import Max
from django.test import (
    SimpleTestCase, TestCase, TransactionTestCase, override_settings,
)
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from dominial.models import Cartorios, Documento, Lancamento, LancamentoPessoa, Pessoas
from ia_ocr import estados, services
from ia_ocr.models import CampoSugerido, OcrJob
from ia_ocr.revisao import pendencias

from .factories import criar_job_concluido, criar_usuario
from .payloads_extracao import TEXTO_PAGINA_1, payload_registro
from .test_extracao_services_parte1 import SolicitarExtracaoTestParte1
from .test_extracao_services_parte2 import SolicitarExtracaoTestParte2


class BackendExtracaoFalso:
    """Devolve o envelope configurado, sem cópia para detectar mutações."""

    def __init__(self, envelope=None):
        self.envelope = envelope

    def extrair(self, requisicao):
        return self.envelope



ESCRITA = re.compile(r'\s*(INSERT|UPDATE|DELETE)\b', re.IGNORECASE)
ESCRITA_NO_DOMINIO = re.compile(
    r'\s*(INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+["`]?dominial_', re.IGNORECASE,
)


CONFIG_EXTRACAO = {
    'EXTRACAO_BACKEND': 'ia_ocr.tests.test_extracao_services.BackendExtracaoFalso',
    'EXTRACAO_HTTP_TIMEOUT_SECONDS': 120,
}


class ExtracaoFixtureMixin:
    def setUp(self):
        super().setUp()
        self.usuario = criar_usuario()
        self.job = criar_job_concluido(
            textos=[TEXTO_PAGINA_1.replace('MATRÍCULA', 'MATR1CULA'), 'Verso sintético.'],
            criado_por=self.usuario,
        )
        documento = self.job.documento_digital.documento
        documento.tipo.tipo = 'matricula'
        documento.tipo.save(update_fields=['tipo'])
        documento.cartorio.cidade = 'Guaíra'
        documento.cartorio.save(update_fields=['cidade'])
        self.envelope = {
            'extracao': payload_registro(self.job.job_id),
            'dpi': 300,
            'paginas': [
                {'pagina': 1, 'texto_corrigido': TEXTO_PAGINA_1},
                {'pagina': 2, 'texto_corrigido': 'Verso corrigido.'},
            ],
        }
        self.backend = BackendExtracaoFalso(self.envelope)
        patch_backend = mock.patch(
            'ia_ocr.services.get_extracao_backend', return_value=self.backend,
        )
        self.get_backend = patch_backend.start()
        self.addCleanup(patch_backend.stop)
        patch_extrair = mock.patch.object(
            self.backend, 'extrair', wraps=self.backend.extrair,
        )
        self.extrair = patch_extrair.start()
        self.addCleanup(patch_extrair.stop)

    def assertReservaLimpa(self):
        self.job.refresh_from_db()
        self.assertIsNone(self.job.extracao_reserva)
        self.assertIsNone(self.job.extracao_reservada_ate)

    def assertSemPersistencia(self):
        self.assertReservaLimpa()
        self.assertEqual(self.job.status, estados.CONCLUIDO)
        self.assertIsNone(self.job.dpi)
        self.assertFalse(self.job.extracoes.exists())
        self.assertFalse(self.job.transicoes.exists())
        self.assertFalse(CampoSugerido.objects.exists())
        for pagina in self.job.paginas.all():
            self.assertIsNone(pagina.texto_corrigido)
            self.assertIsNone(pagina.corrigido_em)



@override_settings(**CONFIG_EXTRACAO)
class SolicitarExtracaoTest(
    SolicitarExtracaoTestParte1,
    SolicitarExtracaoTestParte2,
    ExtracaoFixtureMixin,
    TestCase,
):
    """Nome preservado para os ids de teste; corpo nas partes."""


@override_settings(**CONFIG_EXTRACAO)
class SomenteSeInexistenteTest(ExtracaoFixtureMixin, TestCase):
    """Guarda da auto-extração (PR #319, Greptile P1 "second tab").

    Duas abas podem renderizar a tela de confirmação antes de existir
    extração; o POST atrasado da segunda (``somente_se_inexistente``) não
    pode criar uma extração vigente nova e esconder as correções gravadas
    sobre a primeira. A guarda vale na leitura otimista E dentro do
    ``transaction.atomic()`` com ``select_for_update()``.
    """

    def test_primeira_solicitacao_automatica_cria_extracao(self):
        extracao = services.solicitar_extracao(
            self.job, self.usuario, somente_se_inexistente=True,
        )

        self.assertEqual(self.job.extracao_vigente(), extracao)
        self.assertEqual(self.job.extracoes.count(), 1)
        self.extrair.assert_called_once()
        self.assertReservaLimpa()

    def test_segunda_solicitacao_automatica_recusa_e_preserva_vigente(self):
        primeira = services.solicitar_extracao(
            self.job, self.usuario, somente_se_inexistente=True,
        )

        with self.assertRaises(services.ExtracaoRecusada) as contexto:
            services.solicitar_extracao(
                self.job, self.usuario, somente_se_inexistente=True,
            )

        self.assertEqual(contexto.exception.code, 'extracao_existente')
        self.assertEqual(self.job.extracoes.count(), 1)
        self.assertEqual(self.job.extracao_vigente(), primeira)
        self.extrair.assert_called_once()
        self.assertReservaLimpa()

    def test_guarda_dentro_da_transacao_com_leitura_otimista_obsoleta(self):
        services.solicitar_extracao(self.job, self.usuario)
        vigente = self.job.extracao_vigente()
        self.extrair.reset_mock()
        # Gêmeo sem extração: o que a leitura otimista (fora da transação)
        # devolveria se a vigente surgisse depois dela. A guarda tem de
        # levantar de novo sob ``select_for_update`` e antes do HTTP.
        gemeo = criar_job_concluido(
            self.job.documento_digital,
            textos=['Gêmeo sintético.'],
            criado_por=self.usuario,
        )

        with mock.patch.object(OcrJob.objects, 'get', return_value=gemeo):
            with self.assertRaises(services.ExtracaoRecusada) as contexto:
                services.solicitar_extracao(
                    self.job, self.usuario, somente_se_inexistente=True,
                )

        self.assertEqual(contexto.exception.code, 'extracao_existente')
        self.extrair.assert_not_called()
        self.assertEqual(self.job.extracoes.count(), 1)
        self.assertEqual(self.job.extracao_vigente(), vigente)
        self.assertReservaLimpa()

    def test_reextracao_manual_sem_flag_continua_criando_versao_nova(self):
        anterior = services.solicitar_extracao(
            self.job, self.usuario, somente_se_inexistente=False,
        )

        nova = services.solicitar_extracao(
            self.job, self.usuario,
            extracao_id=anterior.pk, somente_se_inexistente=False,
        )

        self.assertEqual(self.job.extracoes.count(), 2)
        self.assertEqual(self.job.extracao_vigente(), nova)
        self.assertReservaLimpa()


@override_settings(**CONFIG_EXTRACAO)
class ZeroEscritaTest(ExtracaoFixtureMixin, TestCase):
    """Aceite da #262: extrair, revisar e finalizar não gravam no domínio."""

    MODELOS = (Documento, Lancamento, LancamentoPessoa, Pessoas, Cartorios)

    def _retrato(self):
        contagens = {m.__name__: m.objects.count() for m in self.MODELOS}
        maximos = {
            m.__name__: m.objects.aggregate(maximo=Max('pk'))['maximo']
            for m in (Documento, Lancamento)
        }
        return contagens, maximos

    def assertRetratoIgual(self, antes, depois, etapa):
        for tipo, (dict_antes, dict_depois) in zip(('count', 'Max(pk)'), zip(antes, depois)):
            for nome, valor in dict_antes.items():
                self.assertEqual(
                    dict_depois[nome], valor,
                    f'{nome}: {tipo} mudou de {valor} para {dict_depois[nome]} após {etapa}',
                )

    @contextmanager
    def assertSemSqlNoDominio(self, etapa):
        """Falha se a etapa emitir INSERT/UPDATE/DELETE em tabela ``dominial_``.

        Olha a tabela-alvo da escrita, não qualquer menção: um UPDATE em
        ``ia_ocr_*`` pode filtrar por subquery em ``dominial_*`` sem gravar lá.
        """
        with CaptureQueriesContext(connection) as capturadas:
            yield capturadas
        escritas = [
            consulta['sql'] for consulta in capturadas.captured_queries
            if ESCRITA_NO_DOMINIO.match(consulta['sql'])
        ]
        self.assertEqual(escritas, [], f'SQL de escrita no domínio após {etapa}')

    def test_zero_escrita_cinco_modelos(self):
        antes = self._retrato()

        with self.assertSemSqlNoDominio('solicitar_extracao') as capturadas:
            extracao = services.solicitar_extracao(self.job, self.usuario)
        # A captura não é vazia: a extração grava, só que fora do domínio.
        self.assertTrue(any(
            ESCRITA.match(consulta['sql']) for consulta in capturadas.captured_queries
        ))
        self.assertRetratoIgual(antes, self._retrato(), 'solicitar_extracao')

        with self.assertSemSqlNoDominio('salvar_bloco'):
            services.salvar_bloco(
                extracao, {'/document/numero': {'incluir': True, 'conferido': True}},
                self.usuario, services.versao_bloco(extracao),
            )
        self.assertRetratoIgual(antes, self._retrato(), 'salvar_bloco')

        # O cenário tem pendência (parte sem cadastro, linhas não conferidas):
        # a recusa é sempre exercida.
        self.assertNotEqual(pendencias(extracao), [])
        with self.assertSemSqlNoDominio('finalizar_revisao recusada'):
            with self.assertRaises(services.RevisaoIncompleta):
                services.finalizar_revisao(extracao, self.usuario)
        self.assertRetratoIgual(antes, self._retrato(), 'finalizar_revisao recusada')

        # Resolve tudo, inclusive `criar_novo` em cartório/partes, e finaliza.
        decisoes = {}
        for campo in extracao.campos.all():
            decisao = {'incluir': True, 'conferido': True}
            if campo.tipo_valor in ('cartorio', 'parte'):
                decisao['escolha'] = {'criar_novo': True}
            decisoes[campo.chave] = decisao
        with self.assertSemSqlNoDominio('salvar_bloco completo'):
            services.salvar_bloco(
                extracao, decisoes, self.usuario, services.versao_bloco(extracao),
            )
        self.assertRetratoIgual(antes, self._retrato(), 'salvar_bloco completo')
        self.assertEqual(pendencias(extracao), [])

        with self.assertSemSqlNoDominio('finalizar_revisao'):
            finalizada = services.finalizar_revisao(extracao, self.usuario)

        self.assertIsNotNone(finalizada.finalizada_em)
        self.assertRetratoIgual(antes, self._retrato(), 'finalizar_revisao')


@override_settings(**CONFIG_EXTRACAO)
class ExtracaoSemTransacaoTest(ExtracaoFixtureMixin, TransactionTestCase):
    def test_http_sem_transacao_aberta(self):
        def extrair(requisicao):
            self.assertFalse(connection.in_atomic_block)
            reservado = OcrJob.objects.get(pk=self.job.pk)
            self.assertIsNotNone(reservado.extracao_reserva)
            self.assertGreater(reservado.extracao_reservada_ate, timezone.now())
            return self.envelope

        self.extrair.side_effect = extrair

        extracao = services.solicitar_extracao(self.job, self.usuario)

        self.extrair.assert_called_once()
        self.assertEqual(self.job.extracao_vigente(), extracao)
        self.assertReservaLimpa()


class VersaoBlocoOrdenacaoTest(SimpleTestCase):
    def test_campos_fora_de_ordem_geram_mesmo_token(self):
        class Campo:
            def __init__(self, chave):
                self.chave = chave

        class Campos:
            def __init__(self, itens):
                self.itens = itens

            def all(self):
                return list(self.itens)

            def order_by(self, _nome):
                return list(self.itens)

        class Extracao:
            pk = 7

            def __init__(self, itens):
                self.campos = Campos(itens)

        itens = [Campo('/document/numero'), Campo('/document/data'),
                 Campo('/document/livro')]
        ordenados = sorted(itens, key=lambda campo: campo.chave)

        with mock.patch(
            'ia_ocr.services.versao_linha',
            side_effect=lambda campo: campo.chave,
        ):
            self.assertEqual(
                services.versao_bloco(Extracao(itens)),
                services.versao_bloco(Extracao(itens), campos=ordenados),
            )
