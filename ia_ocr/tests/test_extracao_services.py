"""Orquestração da extração com backend falso, sem rede ou documentos reais."""

import copy
import uuid
from datetime import timedelta
from unittest import mock

from django.db import IntegrityError, connection
from django.db.models import Max
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from dominial.models import Cartorios, Documento, Lancamento, LancamentoPessoa, Pessoas
from ia_ocr import estados, services
from ia_ocr.extracao_backends import ExtracaoBackendError, ResultadoExtracao
from ia_ocr.models import CampoSugerido, ExtracaoSugerida, OcrJob
from ia_ocr.revisao import pendencias

from .factories import criar_job_concluido, criar_usuario
from .payloads_extracao import PROVIDER, SCHEMA_VERSION, TEXTO_PAGINA_1, payload_registro


class BackendExtracaoFalso:
    """Devolve o envelope configurado, sem cópia para detectar mutações."""

    def __init__(self, envelope=None):
        self.envelope = envelope

    def extrair(self, requisicao):
        return self.envelope


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
class SolicitarExtracaoTest(ExtracaoFixtureMixin, TestCase):
    def test_estados_recusados(self):
        for status, _rotulo in estados.STATUS_CHOICES:
            if status in {estados.CONCLUIDO, estados.EXTRAIDO}:
                continue
            with self.subTest(status=status):
                # O objeto do chamador permanece concluido: vale o estado do banco.
                OcrJob.objects.filter(pk=self.job.pk).update(status=status)
                with self.assertRaises(services.ExtracaoRecusada) as contexto:
                    services.solicitar_extracao(self.job, self.usuario)
                self.assertEqual(contexto.exception.code, 'estado_invalido')
                self.get_backend.assert_not_called()
                self.extrair.assert_not_called()
                self.assertFalse(self.job.extracoes.exists())

    def test_pagina_sem_texto_ocr_recusa(self):
        paginas = list(self.job.paginas.all())
        paginas[1].texto_ocr = None
        # A coluna atual é NOT NULL; simula dado incompleto na fronteira de leitura.
        with mock.patch.object(type(self.job.paginas), 'all', return_value=paginas):
            with self.assertRaises(services.ExtracaoRecusada) as contexto:
                services.solicitar_extracao(self.job, self.usuario)
        self.assertEqual(contexto.exception.code, 'sem_texto_ocr')
        self.get_backend.assert_not_called()
        self.extrair.assert_not_called()
        self.assertSemPersistencia()

    def test_persiste_payload_servico_intacto_e_transiciona(self):
        original = copy.deepcopy(self.envelope['extracao'])

        extracao = services.solicitar_extracao(self.job, self.usuario)

        extracao.refresh_from_db()
        self.assertEqual(extracao.payload_servico, original)
        self.assertEqual(extracao.payload_servico, self.envelope['extracao'])
        self.assertIn('match_sugerido', extracao.payload['document']['cartorio'])
        self.assertNotIn('match_sugerido', extracao.payload_servico['document']['cartorio'])
        self.assertEqual(extracao.schema_version, SCHEMA_VERSION)
        self.assertEqual(extracao.provider, PROVIDER)
        self.assertEqual(extracao.solicitada_por, self.usuario)
        self.assertIsNone(extracao.finalizada_em)
        self.assertTrue(extracao.campos.exists())
        tipo = extracao.campos.get(chave='/document/tipo')
        self.assertEqual(tipo.evidencia_trecho, 'MATRÍCULA Nº 42.718')
        self.assertNotIn('trecho_ausente', tipo.motivos_revisao)
        self.assertReservaLimpa()
        self.assertEqual(self.job.status, estados.EXTRAIDO)
        transicao = self.job.transicoes.get()
        self.assertEqual(transicao.de_status, estados.CONCLUIDO)
        self.assertEqual(transicao.para_status, estados.EXTRAIDO)
        self.assertEqual(transicao.usuario, self.usuario)
        self.extrair.assert_called_once()

    def test_grava_texto_corrigido_e_dpi(self):
        originais = list(self.job.paginas.values_list('texto_ocr', flat=True))
        antes = timezone.now()

        services.solicitar_extracao(self.job, self.usuario)

        self.job.refresh_from_db()
        self.assertEqual(self.job.dpi, 300)
        for pagina, original, resposta in zip(
            self.job.paginas.all(), originais, self.envelope['paginas'],
        ):
            self.assertEqual(pagina.texto_ocr, original)
            self.assertEqual(pagina.texto_corrigido, resposta['texto_corrigido'])
            self.assertGreaterEqual(pagina.corrigido_em, antes)
            self.assertLessEqual(pagina.corrigido_em, timezone.now())
            self.assertIsNone(pagina.texto_confirmado)
            self.assertIsNone(pagina.confirmado_em)
            self.assertIsNone(pagina.confirmado_por)

    def test_requisicao_usa_tipo_contexto_e_ocr_original(self):
        documento = self.job.documento_digital.documento
        documento.tipo.tipo = 'transcricao'
        documento.tipo.save(update_fields=['tipo'])
        self.job.dpi = 240
        self.job.save(update_fields=['dpi'])
        pagina = self.job.paginas.get(numero_pagina=1)
        pagina.blocos = [{'text': 'Texto sintético', 'bbox': [10, 20, 30, 40]}]
        pagina.texto_corrigido = 'Correção anterior que não deve ser enviada.'
        pagina.texto_confirmado = 'Confirmação legada que não deve ser enviada.'
        pagina.save(update_fields=['blocos', 'texto_corrigido', 'texto_confirmado'])

        services.solicitar_extracao(self.job, self.usuario)

        self.extrair.assert_called_once_with({
            'schema_version': SCHEMA_VERSION,
            'tipo_documento': 'transcricao',
            'paginas': [
                {'pagina': p.numero_pagina, 'texto': p.texto_ocr}
                for p in self.job.paginas.all()
            ],
            'contexto': {
                'cartorio': documento.cartorio.nome,
                'municipio': 'Guaíra',
                'dpi': 240,
                'blocos': [{'pagina': 1, 'blocks': pagina.blocos}],
            },
        })

    def test_requisicao_sem_blocos_usa_dpi_padrao(self):
        services.solicitar_extracao(self.job, self.usuario)

        requisicao = self.extrair.call_args.args[0]
        self.assertEqual(requisicao['tipo_documento'], 'matricula')
        self.assertEqual(requisicao['contexto']['dpi'], 200)
        self.assertNotIn('blocos', requisicao['contexto'])

    def test_reextracao_cria_nova_vigente_e_preserva_anterior(self):
        anterior = services.solicitar_extracao(self.job, self.usuario)
        campo = anterior.campos.get(chave='/document/numero')
        campo.status_revisao = 'editado'
        campo.valor_final = 'Número revisado'
        campo.revisado_por = self.usuario
        campo.revisado_em = timezone.now()
        campo.save()
        dados_anteriores = ExtracaoSugerida.objects.filter(pk=anterior.pk).values().get()
        campos_anteriores = list(anterior.campos.order_by('pk').values())
        self.envelope['extracao']['document']['numero']['normalized'] = '42.719'

        nova = services.solicitar_extracao(self.job, self.usuario, extracao_id=anterior.pk)

        self.assertGreater(nova.pk, anterior.pk)
        self.assertEqual(self.job.extracao_vigente(), nova)
        self.assertEqual(self.job.extracoes.count(), 2)
        self.assertEqual(
            ExtracaoSugerida.objects.filter(pk=anterior.pk).values().get(), dados_anteriores,
        )
        self.assertEqual(list(anterior.campos.order_by('pk').values()), campos_anteriores)
        self.assertEqual(nova.campos.get(chave=campo.chave).status_revisao, 'sugerido')
        self.assertEqual(self.job.transicoes.count(), 1)
        self.assertReservaLimpa()
        self.assertEqual(self.job.status, estados.EXTRAIDO)

    def test_reextracao_extracao_id_antigo_409(self):
        anterior = services.solicitar_extracao(self.job, self.usuario)
        vigente = services.solicitar_extracao(self.job, self.usuario, extracao_id=anterior.pk)
        self.get_backend.reset_mock()
        self.extrair.reset_mock()

        with self.assertRaises(services.ExtracaoConcorrente) as contexto:
            services.solicitar_extracao(self.job, self.usuario, extracao_id=anterior.pk)

        self.assertEqual(contexto.exception.code, 'extracao_concorrente')
        self.get_backend.assert_not_called()
        self.extrair.assert_not_called()
        self.assertEqual(self.job.extracao_vigente(), vigente)
        self.assertEqual(self.job.extracoes.count(), 2)
        self.assertReservaLimpa()

    def test_reserva_ativa_recusa_sem_rede(self):
        reserva = uuid.uuid4()
        ate = timezone.now() + timedelta(minutes=1)
        OcrJob.objects.filter(pk=self.job.pk).update(
            extracao_reserva=reserva, extracao_reservada_ate=ate,
        )

        with self.assertRaises(services.ExtracaoConcorrente):
            services.solicitar_extracao(self.job, self.usuario)

        self.get_backend.assert_not_called()
        self.extrair.assert_not_called()
        self.job.refresh_from_db()
        self.assertEqual(self.job.extracao_reserva, reserva)
        self.assertEqual(self.job.extracao_reservada_ate, ate)

    def test_reserva_expirada_libera(self):
        agora = timezone.now()
        anterior = uuid.uuid4()
        OcrJob.objects.filter(pk=self.job.pk).update(
            extracao_reserva=anterior,
            extracao_reservada_ate=agora - timedelta(seconds=1),
        )

        def extrair(requisicao):
            reservado = OcrJob.objects.get(pk=self.job.pk)
            self.assertIsNotNone(reservado.extracao_reserva)
            self.assertNotEqual(reservado.extracao_reserva, anterior)
            self.assertEqual(reservado.extracao_reservada_ate, agora + timedelta(seconds=150))
            return self.backend.envelope

        self.extrair.side_effect = extrair
        with mock.patch('ia_ocr.services.timezone.now', return_value=agora):
            services.solicitar_extracao(self.job, self.usuario)

        self.extrair.assert_called_once()
        self.assertReservaLimpa()
        self.assertEqual(self.job.status, estados.EXTRAIDO)

    def test_falha_limpa_reserva(self):
        for erro in (
            ExtracaoBackendError('PRAZO_ESGOTADO', 'Mensagem externa não deve vazar'),
            RuntimeError('Detalhes internos não devem vazar'),
        ):
            with self.subTest(erro=type(erro).__name__):
                self.extrair.side_effect = erro
                with self.assertRaises(services.ExtracaoIndisponivel) as contexto:
                    services.solicitar_extracao(self.job, self.usuario)
                self.assertEqual(contexto.exception.code, 'extracao_indisponivel')
                self.assertNotIn(str(erro), str(contexto.exception))
                self.assertSemPersistencia()

    def test_falha_f3_reverte_paginas_extracao_e_campos(self):
        for erro, excecao in (
            (IntegrityError('Conflito sintético'), services.ExtracaoConcorrente),
            (RuntimeError('Falha sintética'), services.ExtracaoIndisponivel),
        ):
            with self.subTest(erro=type(erro).__name__):
                with mock.patch.object(CampoSugerido.objects, 'bulk_create', side_effect=erro):
                    with self.assertRaises(excecao):
                        services.solicitar_extracao(self.job, self.usuario)
                self.assertSemPersistencia()

    def test_reserva_substituida_nao_e_limpa_por_resposta_tardia(self):
        outra = uuid.uuid4()
        ate = timezone.now() + timedelta(minutes=5)

        def extrair(requisicao):
            OcrJob.objects.filter(pk=self.job.pk).update(
                extracao_reserva=outra, extracao_reservada_ate=ate,
            )
            return self.envelope

        self.extrair.side_effect = extrair
        with self.assertRaises(services.ExtracaoConcorrente):
            services.solicitar_extracao(self.job, self.usuario)

        self.job.refresh_from_db()
        self.assertEqual(self.job.extracao_reserva, outra)
        self.assertEqual(self.job.extracao_reservada_ate, ate)
        self.assertFalse(self.job.extracoes.exists())
        self.assertFalse(self.job.paginas.filter(corrigido_em__isnull=False).exists())

    def test_status_alterado_durante_http_recusa_resposta(self):
        def extrair(requisicao):
            OcrJob.objects.filter(pk=self.job.pk).update(status=estados.TEXTO_CONFIRMADO)
            return self.envelope

        self.extrair.side_effect = extrair
        with self.assertRaises(services.ExtracaoConcorrente):
            services.solicitar_extracao(self.job, self.usuario)

        self.assertReservaLimpa()
        self.assertEqual(self.job.status, estados.TEXTO_CONFIRMADO)
        self.assertFalse(self.job.extracoes.exists())
        self.assertFalse(self.job.paginas.filter(corrigido_em__isnull=False).exists())

    def test_vigente_alterada_durante_http_recusa_resposta(self):
        def extrair(requisicao):
            ExtracaoSugerida.objects.create(
                ocr_job=self.job, schema_version=SCHEMA_VERSION, provider=PROVIDER,
                payload=self.envelope['extracao'], payload_servico=self.envelope['extracao'],
            )
            return self.envelope

        self.extrair.side_effect = extrair
        with self.assertRaises(services.ExtracaoConcorrente):
            services.solicitar_extracao(self.job, self.usuario)

        self.assertReservaLimpa()
        self.assertEqual(self.job.extracoes.count(), 1)
        self.assertEqual(self.job.status, estados.CONCLUIDO)
        self.assertFalse(self.job.paginas.filter(corrigido_em__isnull=False).exists())

    def test_payload_invalido_limpa_reserva_sem_gravar(self):
        self.envelope['extracao']['meta']['job_id'] = str(uuid.uuid4())

        with self.assertRaises(services.ExtracaoIndisponivel):
            services.solicitar_extracao(self.job, self.usuario)

        self.assertSemPersistencia()

    def test_envelope_incompleto_limpa_reserva_sem_gravar(self):
        self.envelope['paginas'].pop()

        with self.assertRaises(services.ExtracaoIndisponivel):
            services.solicitar_extracao(self.job, self.usuario)

        self.assertSemPersistencia()

    def test_aceita_envelope_no_resultado_do_backend_atual(self):
        self.backend.envelope = ResultadoExtracao(payload=self.envelope)

        extracao = services.solicitar_extracao(self.job, self.usuario)

        self.assertEqual(extracao.payload_servico, self.envelope['extracao'])
        self.assertReservaLimpa()

    def test_ambas_transicoes_para_extraido_exigem_extracao(self):
        for status in (estados.CONCLUIDO, estados.TEXTO_CONFIRMADO):
            with self.subTest(status=status):
                OcrJob.objects.filter(pk=self.job.pk).update(status=status)
                self.job.refresh_from_db()
                with self.assertRaises(estados.TransicaoInvalida) as contexto:
                    self.job.transicionar(estados.EXTRAIDO, usuario=self.usuario)
                self.assertEqual(contexto.exception.code, 'sem_extracao')
                self.job.refresh_from_db()
                self.assertEqual(self.job.status, status)
                self.assertFalse(self.job.transicoes.exists())


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

    def test_zero_escrita_cinco_modelos(self):
        antes = self._retrato()

        extracao = services.solicitar_extracao(self.job, self.usuario)
        self.assertRetratoIgual(antes, self._retrato(), 'solicitar_extracao')

        services.salvar_bloco(
            extracao, {'/document/numero': {'incluir': True, 'conferido': True}},
            self.usuario, services.versao_bloco(extracao),
        )
        self.assertRetratoIgual(antes, self._retrato(), 'salvar_bloco')

        if pendencias(extracao):
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
            services.salvar_bloco(
                extracao, decisoes, self.usuario, services.versao_bloco(extracao),
            )
            self.assertEqual(pendencias(extracao), [])

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
