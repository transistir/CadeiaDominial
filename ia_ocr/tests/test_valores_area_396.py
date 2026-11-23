"""#396 — o codec do formulário da revisão usa o parser único de área.

``ia_ocr.valores.do_formulario('area', texto)`` recebia texto digitado e fazia
``replace(',', '.')``: ``1.000`` virava 1 ha, o mesmo P0 do formulário manual.
"""

from django.test import SimpleTestCase

from ia_ocr import destinos
from ia_ocr.valores import (
    MOTIVO_LIMITE, ValorInvalido, do_formulario, validar_limites,
)


class AreaDoFormularioRevisaoTest(SimpleTestCase):
    def test_ambiguo_e_recusado_com_as_duas_leituras(self):
        for entrada in ('1.000', '1,000'):
            with self.subTest(entrada=entrada):
                with self.assertRaises(ValorInvalido) as ctx:
                    do_formulario('area', entrada)
                self.assertIn('ambígua', str(ctx.exception).lower())

    def test_milhar_ptbr_vira_decimal(self):
        self.assertEqual(do_formulario('area', '1.234,5678'), '1234.5678')

    def test_formatos_aceitos(self):
        self.assertEqual(do_formulario('area', '150,5'), '150.5')
        self.assertEqual(do_formulario('area', '150.5'), '150.5')
        self.assertEqual(do_formulario('area', '0,012'), '0.012')

    def test_vazio_continua_vazio(self):
        self.assertEqual(do_formulario('area', ''), '')


class AreaCanonicaSalvaTest(SimpleTestCase):
    """Valor JÁ SALVO (canônico) não passa pela regra de ambiguidade.

    `validar_limites` revalida o que está gravado antes de finalizar a revisão.
    Aplicar a regra de texto digitado a `74.675`/`1.000` bloqueava a revisão
    (Greptile P1 no PR #403).
    """

    def setUp(self):
        self.destino = destinos.destino_de('/acts/0/area')

    def test_canonico_de_tres_casas_passa(self):
        self.assertIsNone(validar_limites(self.destino, '74.675'))

    def test_canonico_um_milhar_passa_como_um_hectare(self):
        self.assertIsNone(validar_limites(self.destino, '1.000'))

    def test_canonico_fora_do_formato_nao_passa(self):
        for valor in ('1.234.567,89', 'abc', '123456789'):
            with self.subTest(valor=valor):
                self.assertEqual(validar_limites(self.destino, valor), MOTIVO_LIMITE)

    def test_texto_digitado_continua_estrito(self):
        for valor in ('1.000', '1,000'):
            with self.subTest(valor=valor):
                with self.assertRaises(ValorInvalido):
                    do_formulario('area', valor)
