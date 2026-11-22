"""Pendência de área do ato: só o que não converte exige decisão (#341/#373)."""

from ia_ocr.formulario import area_exige_decisao

from .test_revisao_formulario_prefill_base import PrefillBase


class AreaExigeDecisaoTest(PrefillBase):
    """``area_exige_decisao`` após a conversão automática de #373."""

    def _extracao_com_area(self, normalizado, trecho, unidade, raw=None):
        area = {
            **self._campo(normalizado, trecho), 'unidade': unidade,
            'raw': raw or trecho,
        }
        return self._aberta(self._registro(area=area))

    def test_metro_quadrado_convertido_nao_exige_decisao(self):
        extracao = self._extracao_com_area(
            None, 'área construída 120,00 m2', 'm2', raw='120,00 m2',
        )

        self.assertFalse(area_exige_decisao(extracao, 0))

    def test_composto_sem_unidade_convertido_nao_exige_decisao(self):
        extracao = self._extracao_com_area(
            None, 'área 169 hectares, 09 ares e 40 centiares', None,
            raw='169 hectares, 09 ares e 40 centiares',
        )

        self.assertFalse(area_exige_decisao(extracao, 0))

    def test_alqueires_exige_decisao(self):
        extracao = self._extracao_com_area(
            '12.50', 'área 12,50 alqueires', 'alqueires',
            raw='12,50 alqueires',
        )

        self.assertTrue(area_exige_decisao(extracao, 0))

    def test_unidade_ausente_exige_decisao(self):
        extracao = self._extracao_com_area(
            '1234.5678', 'área 1.234,5678', None, raw='1.234,5678',
        )

        self.assertTrue(area_exige_decisao(extracao, 0))
