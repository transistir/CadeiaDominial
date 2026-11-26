"""Entrega do app, item 3: confiança nula não é baixa confiança.

``confianca: null`` significa ausência de medida, não 0.0. Só o segundo
caso entra no limiar e vira ``baixa_confianca``. Este é um teste de
regressão: o código atual já exige ``confianca is not None``.
"""

from django.test import TestCase

from .payloads_extracao import payload_registro
from .test_revisao_desnormalizar_parte1 import DesnormalizarTestParte1


class ConfiancaNulaTest(DesnormalizarTestParte1, TestCase):
    CHAVES = (
        '/document/numero',        # campo
        '/acts/0',                 # ato
        '/acts/0/partes/0',        # parte
    )

    def _payload_com_confianca(self, confianca):
        payload = payload_registro(self.job.job_id)
        payload['document']['numero']['confianca'] = confianca
        payload['document']['numero']['requer_revisao'] = False
        payload['acts'][0]['confianca'] = confianca
        payload['acts'][0]['requer_revisao'] = False
        payload['acts'][0]['partes'][0]['confianca'] = confianca
        payload['acts'][0]['partes'][0]['requer_revisao'] = False
        return payload

    def test_confianca_nula_nao_vira_baixa_confianca(self):
        por_chave = self._por_chave(
            self._linhas(self._payload_com_confianca(None), validar=False)
        )

        for chave in self.CHAVES:
            with self.subTest(chave=chave):
                linha = por_chave[chave]
                self.assertIsNone(linha.confianca)
                self.assertNotIn('baixa_confianca', linha.motivos_revisao)
                self.assertFalse(linha.requer_revisao)

    def test_confianca_zero_e_baixa_confianca(self):
        por_chave = self._por_chave(
            self._linhas(self._payload_com_confianca(0.0), validar=False)
        )

        for chave in self.CHAVES:
            with self.subTest(chave=chave):
                linha = por_chave[chave]
                self.assertEqual(linha.confianca, 0.0)
                self.assertIn('baixa_confianca', linha.motivos_revisao)
                self.assertTrue(linha.requer_revisao)
