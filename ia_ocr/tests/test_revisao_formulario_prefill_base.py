"""Testes do pré-preenchimento do formulário de lançamento (I-14 / #341, fase 1).

``prefill_do_ato`` lê o estado ATUAL da revisão (job em ``extraido``, nada
finalizado) e devolve o que o formulário manual consome: ``form_data`` com o
nome dos inputs, ``origens_separadas``, ``transmitentes``/``adquirentes``,
``evidencias`` e avisos do que foi lido sem campo no lançamento. Um caso por
destino, mais o round-trip do ``origens_separadas`` pelo
``_origens_separadas_do_post`` do formulário.

Migração VERBATIM de ``ia_ocr/tests/test_revisao_formulario_prefill.py``
(Etapa 13 do plano de 400 linhas): nenhum teste aqui — só ``PrefillBase``
(setUp + helpers); as 9 classes por cenário ficam em
``test_revisao_formulario_prefill_*.py``.
"""

from django.test import TestCase

from dominial.models import Cartorios, Documento, LancamentoTipo
from ia_ocr.formulario import prefill_do_ato
from ia_ocr.models import CampoSugerido, ExtracaoSugerida
from ia_ocr.revisao import desnormalizar

from .payloads_extracao import (
    SCHEMA_VERSION, payload_averbacao, payload_registro,
)
from .test_importacao_base import ImportacaoFixture


class PrefillBase(ImportacaoFixture, TestCase):
    """Job em ``extraido`` e documento sem livro/folha, com os três tipos."""

    def setUp(self):
        super().setUp()
        self.job.status = 'extraido'
        self.job.save(update_fields=['status'])
        self.tipo_averbacao = LancamentoTipo.objects.create(tipo='averbacao')
        self.tipo_inicio = LancamentoTipo.objects.create(
            tipo='inicio_matricula',
        )
        # A fábrica do documento define livro/folha; aqui ele ainda não os tem.
        Documento.objects.filter(pk=self.documento.pk).update(
            livro='', folha='', numero='M237',
        )
        self.documento.refresh_from_db()

    def _aberta(self, payload):
        """Extração em revisão: nada escolhido, nada finalizado."""
        extracao = ExtracaoSugerida.objects.create(
            ocr_job=self.job, schema_version=SCHEMA_VERSION,
            payload=payload, payload_servico=payload, provider='local-model',
        )
        CampoSugerido.objects.bulk_create(
            desnormalizar(extracao, payload, [self.pagina]),
        )
        return extracao

    def _registro(self, **campos):
        """Payload do registro com os campos do ato acrescentados/trocados."""
        payload = payload_registro(self.job.job_id)
        payload['acts'][0].update(campos)
        return payload

    def _averbacao(self, **campos):
        payload = payload_averbacao(self.job.job_id)
        payload['acts'][0].update(campos)
        return payload

    def _prefill(self, payload, indice=0):
        return prefill_do_ato(self._aberta(payload), indice, self.documento)

    def _cartorio(self, nome='Cartório sintético do prefill'):
        return Cartorios.objects.create(
            nome=nome, cns=f'CNS-{nome[:8]}', estado='SP',
        )
