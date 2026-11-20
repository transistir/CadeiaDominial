"""Fachada de testes dos serviços de revisão OCR.

Os corpos de ``RevisaoServicesTest`` vivem nas partes para manter este
módulo abaixo do limite de 400 linhas. Os nomes e ids dos testes são preservados.
"""

from django.test import TestCase, override_settings
from django.utils import timezone

from ia_ocr import estados, services
from ia_ocr.models import CampoSugerido, ExtracaoSugerida, OcrJob, PaginaOcr
from ia_ocr.revisao import desnormalizar, pendencias, pendencias_sem_atos

from .factories import criar_documento_digital, criar_usuario
from .payloads_extracao import PROVIDER, SCHEMA_VERSION, TEXTO_PAGINA_1, payload_averbacao
from .test_revisao_services_parte1 import RevisaoServicesTestParte1
from .test_revisao_services_parte2 import RevisaoServicesTestParte2


class RevisaoServicesTest(
    RevisaoServicesTestParte1,
    RevisaoServicesTestParte2,
    TestCase,
):
    """Nome preservado para os ids de teste; corpo nas partes."""


class FinalizarSemAtosTest(TestCase):
    """Issue #262 (I-5): finalizar com nenhum_ato só sob flag + confirmação.

    O serviço de extração ainda devolve ``acts: []``; a pendência continua
    existindo (nunca é escondida), mas o revisor pode concluir a revisão
    confirmando explicitamente que não há atos a importar. Sem a flag, nada
    muda: a revisão continua bloqueada.
    """

    def setUp(self):
        self.usuario = criar_usuario()
        self.job = OcrJob.objects.create(
            documento_digital=criar_documento_digital(upload_por=self.usuario),
            status=estados.EXTRAIDO, criado_por=self.usuario,
        )
        self.pagina = PaginaOcr.objects.create(
            ocr_job=self.job, numero_pagina=1, texto_ocr=TEXTO_PAGINA_1,
        )

    def _extracao(self, payload=None):
        payload = payload or payload_averbacao(self.job.job_id)
        extracao = ExtracaoSugerida.objects.create(
            ocr_job=self.job, schema_version=SCHEMA_VERSION,
            payload=payload, payload_servico=payload, provider=PROVIDER,
            solicitada_por=self.usuario,
        )
        CampoSugerido.objects.bulk_create(
            desnormalizar(extracao, payload, [self.pagina]),
        )
        return extracao

    def _extracao_sem_atos(self):
        payload = payload_averbacao(self.job.job_id)
        payload['acts'] = []
        extracao = self._extracao(payload)
        # Sem atos, o cabeçalho ainda precisa das escolhas de cartório.
        extracao.campos.filter(tipo_valor='cartorio').update(criar_novo=True)
        self.assertEqual(pendencias(extracao), [{
            'chave': '/acts', 'motivo': 'nenhum_ato', 'bloqueante': True,
        }])
        return extracao

    def _assert_nao_finalizada(self, extracao):
        extracao.refresh_from_db()
        self.job.refresh_from_db()
        self.assertIsNone(extracao.finalizada_em)
        self.assertIsNone(extracao.finalizada_por)
        self.assertEqual(self.job.status, estados.EXTRAIDO)
        self.assertFalse(self.job.transicoes.exists())

    @override_settings(OCR_PERMITIR_FINALIZAR_SEM_ATOS=False)
    def test_flag_desligada_confirmacao_nao_destrava(self):
        extracao = self._extracao_sem_atos()

        with self.assertRaises(services.RevisaoIncompleta) as contexto:
            services.finalizar_revisao(
                extracao, self.usuario, confirmar_sem_atos=True,
            )

        self.assertEqual(contexto.exception.pendencias, pendencias(extracao))
        self._assert_nao_finalizada(extracao)

    @override_settings(OCR_PERMITIR_FINALIZAR_SEM_ATOS=True)
    def test_flag_ligada_sem_confirmacao_nao_destrava(self):
        extracao = self._extracao_sem_atos()

        with self.assertRaises(services.RevisaoIncompleta):
            services.finalizar_revisao(
                extracao, self.usuario, confirmar_sem_atos=False,
            )

        self._assert_nao_finalizada(extracao)

    @override_settings(OCR_PERMITIR_FINALIZAR_SEM_ATOS=True)
    def test_flag_ligada_com_confirmacao_finaliza_e_audita_motivo(self):
        extracao = self._extracao_sem_atos()
        antes = timezone.now()

        resultado = services.finalizar_revisao(
            extracao, self.usuario, confirmar_sem_atos=True,
        )

        extracao.refresh_from_db()
        self.job.refresh_from_db()
        self.assertEqual(resultado.pk, extracao.pk)
        self.assertGreaterEqual(extracao.finalizada_em, antes)
        self.assertEqual(extracao.finalizada_por, self.usuario)
        self.assertEqual(self.job.status, estados.REVISADO)
        transicao = self.job.transicoes.get()
        self.assertEqual(transicao.de_status, estados.EXTRAIDO)
        self.assertEqual(transicao.para_status, estados.REVISADO)
        self.assertEqual(transicao.motivo, 'revisao_finalizada_sem_atos')

    @override_settings(OCR_PERMITIR_FINALIZAR_SEM_ATOS=True)
    def test_pode_finalizar_sem_atos_so_no_cenario_limpo(self):
        # Issue #262: a regra fica num lugar só; só o cenário limpo (flag
        # ligada + apenas nenhum_ato + nenhum bloqueio de campo) é elegível.
        extracao = self._extracao_sem_atos()
        self.assertTrue(services.pode_finalizar_sem_atos(extracao))

        with override_settings(OCR_PERMITIR_FINALIZAR_SEM_ATOS=False):
            self.assertFalse(services.pode_finalizar_sem_atos(extracao))

        outra = self._extracao()
        self.assertTrue(pendencias(outra))
        self.assertFalse(services.pode_finalizar_sem_atos(outra))

        payload = payload_averbacao(self.job.job_id)
        payload['acts'] = []
        payload['document'].pop('data')
        com_bloqueio = self._extracao(payload)
        self.assertEqual(pendencias(com_bloqueio), [{
            'chave': '/acts', 'motivo': 'nenhum_ato', 'bloqueante': True,
        }])
        self.assertFalse(services.pode_finalizar_sem_atos(com_bloqueio))

    @override_settings(OCR_PERMITIR_FINALIZAR_SEM_ATOS=True)
    def test_campo_obrigatorio_pendente_sem_atos_ainda_bloqueia(self):
        # Issue #262: sem atos, ``pendencias`` só enxerga ``nenhum_ato``; o
        # campo obrigatório ausente precisa bloquear a confirmação mesmo assim.
        payload = payload_averbacao(self.job.job_id)
        payload['acts'] = []
        payload['document'].pop('data')
        extracao = self._extracao(payload)
        self.assertEqual(pendencias(extracao), [{
            'chave': '/acts', 'motivo': 'nenhum_ato', 'bloqueante': True,
        }])
        self.assertIn(
            {
                'chave': '/document/data',
                'motivo': 'obrigatorio_ausente',
                'bloqueante': True,
            },
            pendencias_sem_atos(extracao),
        )

        with self.assertRaises(services.RevisaoIncompleta):
            services.finalizar_revisao(
                extracao, self.usuario, confirmar_sem_atos=True,
            )

        self._assert_nao_finalizada(extracao)

        # Payload normal de averbação, sem decisões: não há nenhum_ato, mas
        # sobram obrigatórios pendentes — a confirmação não pode ignorá-los.
        extracao = self._extracao()
        self.assertTrue(pendencias(extracao))
        self.assertNotIn(
            'nenhum_ato', [item['motivo'] for item in pendencias(extracao)],
        )

        with self.assertRaises(services.RevisaoIncompleta):
            services.finalizar_revisao(
                extracao, self.usuario, confirmar_sem_atos=True,
            )

        self._assert_nao_finalizada(extracao)
