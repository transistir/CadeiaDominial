"""#396 — o codec do formulário da revisão usa o parser único de área.

``ia_ocr.valores.do_formulario('area', texto)`` recebia texto digitado e fazia
``replace(',', '.')``: ``1.000`` virava 1 ha, o mesmo P0 do formulário manual.
"""

from django.test import SimpleTestCase

from ia_ocr.valores import ValorInvalido, do_formulario


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
