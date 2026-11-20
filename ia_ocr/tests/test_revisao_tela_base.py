"""Infraestrutura de teste do job em ``extraido`` (I-5) — migração VERBATIM
de ``ia_ocr/tests/test_revisao_tela.py`` (Etapa 10 do plano de 400 linhas).

Nenhum teste aqui: só ``TelaRevisaoBase`` (setUp + ``_extracao``). Os
helpers da tela de cards (``_tela``, ``_descendentes``, ``_valor_do_select``,
``_decisao_do_card``, ``_texto_fora_de_details``) saíram junto com a tela,
aposentada na fase 4 da #341 — quem segue usando esta base é a família do
fallback de cartório (``test_cartorio_fallback_*``), que só precisa da
montagem do job.
"""

from ia_ocr import estados, revisao
from ia_ocr.models import CampoSugerido, ExtracaoSugerida, OcrJob

from .base_texto import TelaTextoBase
from .payloads_extracao import (
    PROVIDER,
    SCHEMA_VERSION,
    TEXTO_PAGINA_1,
    payload_averbacao,
)


class TelaRevisaoBase(TelaTextoBase):
    """Infraestrutura do job em ``extraido``; sem testes (reutilizável)."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.dono)
        self.documento.tipo.tipo = 'matricula'
        self.documento.tipo.save(update_fields=['tipo'])
        self.job.paginas.filter(numero_pagina=1).update(texto_ocr=TEXTO_PAGINA_1)
        OcrJob.objects.filter(pk=self.job.pk).update(status=estados.EXTRAIDO)
        self.job.refresh_from_db()

    def _extracao(self, payload=None, resolver=False):
        payload = payload or payload_averbacao(self.job.job_id)
        extracao = ExtracaoSugerida.objects.create(
            ocr_job=self.job, schema_version=SCHEMA_VERSION,
            payload=payload, payload_servico=payload, provider=PROVIDER,
        )
        linhas = revisao.desnormalizar(extracao, payload, list(self.job.paginas.all()))
        if resolver:
            for linha in linhas:
                linha.status_revisao = 'aceito'
                if linha.tipo_valor in ('parte', 'cartorio'):
                    linha.criar_novo = True
        CampoSugerido.objects.bulk_create(linhas)
        return extracao
