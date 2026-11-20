"""Parte 1 de 2 do corpo de ``SolicitarExtracaoTest`` — migração VERBATIM.

Classe simples, sem ``TestCase``; quem coleta é a fachada em
``test_extracao_services.py``.
"""

"""Orquestração da extração com backend falso, sem rede ou documentos reais."""

import copy
import uuid
from datetime import timedelta
from unittest import mock

from django.db import IntegrityError
from django.utils import timezone

from ia_ocr import estados, services
from ia_ocr.backends import OcrServiceBackend
from ia_ocr.extracao_backends import ExtracaoBackendError
from ia_ocr.models import CampoSugerido, ExtracaoSugerida, OcrJob

from .payloads_extracao import (
    PROVIDER, SCHEMA_VERSION,
)

# Pinados de propósito (não derivados de SCHEMA_VERSION): o que o serviço
# responde e o que o app pede são contratos, não detalhe de implementação.
V1_1 = 'umbelino-extracao-matricula-v1.1'
V1_2 = 'umbelino-extracao-matricula-v1.2'


class SolicitarExtracaoTestParte1:
    def test_estados_recusados(self):
        for status, _rotulo in estados.STATUS_CHOICES:
            if status in {
                estados.CONCLUIDO, estados.TEXTO_CONFIRMADO, estados.EXTRAIDO,
            }:
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

    def test_uuid_do_servico_preservado_e_vinculado_ao_job_do_app(self):
        id_servico = '15987107-0672-4d05-a5d6-675aaaf1419c'
        self.assertNotEqual(id_servico, str(self.job.job_id))
        self.envelope['extracao']['meta'].update(
            job_id=id_servico, provider='workers-ai', pages_used=[1, 2],
        )
        self.envelope['dpi'] = 200
        original = copy.deepcopy(self.envelope['extracao'])

        extracao = services.solicitar_extracao(self.job, self.usuario)

        extracao.refresh_from_db()
        self.job.refresh_from_db()
        self.assertEqual(extracao.payload_servico, original)
        self.assertEqual(extracao.ocr_job, self.job)
        self.assertEqual(self.extrair.call_args.args[0]['job_id'], str(self.job.job_id))
        self.assertEqual(self.job.status, estados.EXTRAIDO)
        self.assertEqual(self.job.dpi, 200)
        self.assertTrue(extracao.campos.exists())
        self.assertReservaLimpa()

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
        self.job.dpi = 300
        self.job.save(update_fields=['dpi'])
        pagina = self.job.paginas.get(numero_pagina=1)
        pagina.blocos = self._blocos_do_adaptador(pagina)
        pagina.texto_corrigido = 'Correção anterior que não deve ser enviada.'
        pagina.texto_confirmado = 'Confirmação legada que não deve ser enviada.'
        pagina.save(update_fields=['blocos', 'texto_corrigido', 'texto_confirmado'])

        services.solicitar_extracao(self.job, self.usuario)

        self.extrair.assert_called_once_with({
            'schema_version': SCHEMA_VERSION,
            'job_id': str(self.job.job_id),
            'tipo_documento': 'transcricao',
            'paginas': [
                {'pagina': p.numero_pagina, 'texto': p.texto_ocr}
                for p in self.job.paginas.all()
            ],
            'contexto': {
                'cartorio': documento.cartorio.nome,
                'municipio': 'Guaíra',
                'dpi': 300,
                'blocos': [
                    {
                        'pagina': 1,
                        # O combinado na #290 é a LISTA de blocos — o
                        # envelope interno {'dpi', 'width_px', 'height_px',
                        # 'blocos'} do adaptador não atravessa a requisição.
                        'blocks': [{'text': 'Texto sintético', 'bbox': [10, 20, 30, 40]}],
                    },
                ],
            },
        })

    @staticmethod
    def _blocos_do_adaptador(pagina):
        """O valor REAL de PaginaOcr.blocos: envelope montado por
        OcrServiceBackend._montar_resultado (backends.py), não um atalho."""
        resultado_servico = {
            'source': {'sha256': 'a' * 64, 'page_count': 1},
            'pages': [
                {
                    'page': pagina.numero_pagina,
                    'text': pagina.texto_ocr,
                    'width_px': 1700,
                    'height_px': 2200,
                    'blocks': [{'text': 'Texto sintético', 'bbox': [10, 20, 30, 40]}],
                },
            ],
        }
        resultado = OcrServiceBackend._montar_resultado(
            None, resultado_servico, 'a' * 64, 200,
        )
        return list(resultado.paginas)[0]['blocos']

    def test_requisicao_aceita_blocos_legados_como_lista_direta(self):
        """Registros legados guardaram a LISTA direto em PaginaOcr.blocos,
        sem envelope: a leitura aceita ambos os formatos."""
        pagina = self.job.paginas.get(numero_pagina=1)
        pagina.blocos = [{'text': 'Legado', 'bbox': [1, 2, 3, 4]}]
        pagina.save(update_fields=['blocos'])

        services.solicitar_extracao(self.job, self.usuario)

        requisicao = self.extrair.call_args.args[0]
        self.assertEqual(
            requisicao['contexto']['blocos'],
            [{'pagina': 1, 'blocks': [{'text': 'Legado', 'bbox': [1, 2, 3, 4]}]}],
        )

    def test_requisicao_inclui_job_id(self):
        extracao = services.solicitar_extracao(self.job, self.usuario)

        requisicao = self.extrair.call_args.args[0]
        self.assertEqual(requisicao['job_id'], str(self.job.job_id))
        # O mesmo job_id ecoado em `meta` é aceito e a extração é persistida.
        self.assertEqual(
            self.envelope['extracao']['meta']['job_id'], str(self.job.job_id),
        )
        self.assertEqual(extracao.ocr_job, self.job)
        self.assertTrue(self.job.extracoes.filter(pk=extracao.pk).exists())

    def test_job_em_texto_confirmado_pode_extrair(self):
        OcrJob.objects.filter(pk=self.job.pk).update(status=estados.TEXTO_CONFIRMADO)

        extracao = services.solicitar_extracao(self.job, self.usuario)

        self.job.refresh_from_db()
        self.assertEqual(self.job.status, estados.EXTRAIDO)
        self.assertEqual(self.job.extracao_vigente(), extracao)
        transicao = self.job.transicoes.get()
        self.assertEqual(transicao.de_status, estados.TEXTO_CONFIRMADO)
        self.assertEqual(transicao.para_status, estados.EXTRAIDO)
        self.assertReservaLimpa()

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

