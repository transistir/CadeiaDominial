"""``resolucoes_de_tipo`` com descartes — migração VERBATIM de
``ia_ocr/tests/test_revisao.py`` (Etapa 5, grupo 3 do plano de
400 linhas). Corpos verbatim; só imports e a linha de classe mudam.
"""

from copy import deepcopy
from django.test import TestCase

from ia_ocr.models import CampoSugerido, ExtracaoSugerida, OcrJob, PaginaOcr

from ia_ocr.revisao import desnormalizar, resolucoes_de_tipo
from .factories import criar_documento_digital
from .payloads_extracao import (
    SCHEMA_VERSION, TEXTO_PAGINA_1, payload_averbacao,
)


class ResolucoesDeTipoCustoTest(TestCase):
    """Uma leitura só: as queries de ``resolucoes_de_tipo`` não crescem com descartes."""

    def setUp(self):
        self.job = OcrJob.objects.create(
            documento_digital=criar_documento_digital()
        )
        self.paginas = [PaginaOcr.objects.create(
            ocr_job=self.job, numero_pagina=1, texto_ocr=TEXTO_PAGINA_1,
        )]

    def _extracao_com_descartes(self, descartes):
        """Extração de 3 atos de averbação com ``descartes`` deles descartados."""
        payload = payload_averbacao(self.job.job_id)
        atos = [deepcopy(payload['acts'][0]) for _ in range(3)]
        for ordem, ato in enumerate(atos, start=1):
            ato['ordem'] = ordem
        payload['acts'] = atos
        extracao = ExtracaoSugerida.objects.create(
            ocr_job=self.job, schema_version=SCHEMA_VERSION,
            payload=payload, payload_servico=payload, provider='local-model',
        )
        CampoSugerido.objects.bulk_create(
            desnormalizar(extracao, payload, self.paginas)
        )
        for indice in range(descartes):
            extracao.campos.filter(chave=f'/acts/{indice}').update(
                status_revisao='descartado',
            )
        return extracao

    def test_uma_leitura_so_independente_dos_descartes(self):
        # P2 Greptile (#322/PR #327, rodada 13): cada ato descartado
        # relia ``extracao.campos.all()`` no seu ``_contexto_revisao``
        # (e o loop externo relia de novo) — O(D) leituras além da
        # primeira. ``por_chave`` montado UMA vez faz a leitura ser
        # única: 1 ato descartado e 3 atos descartados executam a MESMA
        # contagem de queries (diferença tolerada: zero).
        extracao_1 = self._extracao_com_descartes(1)
        extracao_3 = self._extracao_com_descartes(3)

        with self.assertNumQueries(1) as um_descarte:
            resolucoes_1 = resolucoes_de_tipo(extracao_1)
        with self.assertNumQueries(len(um_descarte)) as tres_descartes:
            resolucoes_3 = resolucoes_de_tipo(extracao_3)

        self.assertEqual(len(um_descarte), len(tres_descartes))
        # Todo ato tem entrada, inclusive os descartados (rodada 12) —
        # a contagem travada acima é a da resolução COMPLETA.
        self.assertEqual(set(resolucoes_1), set(resolucoes_3))
        self.assertEqual(
            set(resolucoes_3), {'/acts/0', '/acts/1', '/acts/2'},
        )
