"""#373 — área em hectares com 4 casas: conversão e pré-preenchimento."""

from decimal import Decimal

from django.test import SimpleTestCase

from dominial.utils.formatacao_utils import formatar_area_ha
from ia_ocr.formulario import prefill_do_ato
from ia_ocr.revisao.area_ha import converter_para_hectares

from .test_revisao_formulario_prefill_base import PrefillBase


class ConverterParaHectaresTest(SimpleTestCase):
    """Conversão só com unidade explícita ou composto hectare/are/centiare."""

    def test_metro_quadrado_divide_por_dez_mil(self):
        for unidade in ('m2', 'm²'):
            with self.subTest(unidade=unidade):
                self.assertEqual(
                    converter_para_hectares('12.345,67 m²', unidade),
                    Decimal('1.2346'),
                )

    def test_hectare_nao_divide(self):
        self.assertEqual(
            converter_para_hectares('1.234,5678 ha', 'ha'),
            Decimal('1234.5678'),
        )
        self.assertEqual(
            converter_para_hectares('1.234,5678 ha', None),
            Decimal('1234.5678'),
        )

    def test_composto_hectare_are_centiare(self):
        for texto in (
            '169 hectares, 09 ares e 40 centiares',
            '169 ha, 9 a e 40 ca',
        ):
            with self.subTest(texto=texto):
                self.assertEqual(
                    converter_para_hectares(texto, None), Decimal('169.0940'),
                )

    def test_composto_sem_centiares(self):
        self.assertEqual(
            converter_para_hectares('0,5 hectares e 10 ares', None),
            Decimal('0.6000'),
        )

    def test_sem_unidade_e_sem_composto_nao_converte(self):
        self.assertIsNone(converter_para_hectares('1.234,5678', None))

    def test_alqueires_nao_converte(self):
        self.assertIsNone(
            converter_para_hectares('12,5 alqueires', 'alqueires'),
        )

    def test_arredondamento_half_up(self):
        # 0,00005 → 0,0001 (banker's rounding daria 0,0000).
        self.assertEqual(
            converter_para_hectares('0,00005 ha', 'ha'), Decimal('0.0001'),
        )

    def test_zero_negativo_e_lixo_nao_convertem(self):
        for raw, unidade in (
            ('0 ha', 'ha'), ('-5 ha', 'ha'), ('abc ha', 'ha'), ('', 'ha'),
            (None, 'ha'),
        ):
            with self.subTest(raw=raw):
                self.assertIsNone(converter_para_hectares(raw, unidade))


class AreaHaPrefillTest(PrefillBase):
    """Prefill consome o canônico convertido; sem conversão, mantém pendência."""

    def _com_area(self, normalizado, trecho, unidade, raw=None):
        area = {
            **self._campo(normalizado, trecho), 'unidade': unidade,
            'raw': raw or trecho,
        }
        return self._registro(area=area)

    def test_area_metro_quadrado_convertida_nao_gera_pendencia(self):
        extracao = self._aberta(self._com_area(
            None, 'área construída 120,00 m2', 'm2', raw='120,00 m2',
        ))
        resultado = prefill_do_ato(extracao, 0, self.documento)
        campo = extracao.campos.get(chave='/acts/0/area')

        self.assertEqual(resultado['form_data']['area'], '0.0120')
        self.assertFalse(any(
            aviso['motivo'] == 'unidade_area'
            for aviso in resultado['pendencias']
        ))
        self.assertNotIn('unidade_area', campo.motivos_revisao)

    def test_area_sem_unidade_mantem_pendencia(self):
        resultado = self._prefill(self._com_area(
            '1234.5678', 'área 1.234,5678', None, raw='1.234,5678',
        ))

        self.assertNotIn('area', resultado['form_data'])
        self.assertTrue(any(
            aviso['motivo'] == 'unidade_area'
            for aviso in resultado['pendencias']
        ))


class FormatarAreaHaTest(SimpleTestCase):
    """Exibição em 4 casas; zero continua "-" (decisão de 10/09)."""

    def test_quatro_casas_com_virgula(self):
        self.assertEqual(formatar_area_ha(Decimal('169.0940')), '169,0940')

    def test_zero_exibe_traco(self):
        self.assertEqual(formatar_area_ha(Decimal('0.0000')), '-')
