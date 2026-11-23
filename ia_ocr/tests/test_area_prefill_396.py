"""#396 — canônico de área vindo da revisão OCR vira input com 4 casas.

O parser único classifica `74.675` como ambíguo (regra certa para o que o
usuário digita). O canônico que o sistema já resolveu precisa chegar ao input
como `74.6750`, senão o fluxo de revisão trava.
"""

from decimal import Decimal

from django.test import SimpleTestCase

from dominial.utils.area_br import parse_area_br
from ia_ocr.formulario.areas import area_para_input


class AreaParaInputTest(SimpleTestCase):
    def test_tres_casas_viram_quatro(self):
        self.assertEqual(str(area_para_input(Decimal('74.675'))), '74.6750')
        self.assertEqual(str(area_para_input('74.675')), '74.6750')
        self.assertEqual(str(area_para_input('74,675')), '74.6750')

    def test_quatro_casas_ficam_iguais(self):
        self.assertEqual(str(area_para_input(Decimal('74.6755'))), '74.6755')

    def test_duas_casas_passam_intactas(self):
        # Não é entrada de usuário: o prefill não reformata o que já é aceito.
        self.assertEqual(str(area_para_input('12.50')), '12.50')

    def test_canonico_a3_com_tres_casas_e_decimal(self):
        # A3 usa ponto decimal: `1.000` é 1 ha, não mil.
        self.assertEqual(str(area_para_input('1.000')), '1.0000')

    def test_saida_do_prefill_passa_no_parser_sem_ambiguidade(self):
        for valor in (Decimal('74.675'), '150.5', '0.012'):
            with self.subTest(valor=valor):
                texto = area_para_input(valor)
                self.assertEqual(parse_area_br(texto), Decimal(texto))

    def test_vazio_continua_vazio(self):
        self.assertIsNone(area_para_input(None))
        self.assertIsNone(area_para_input(''))

    def test_valor_que_o_parser_recusa_volta_como_veio(self):
        # Nada é descartado em silêncio: o revisor vê o texto e decide.
        self.assertEqual(str(area_para_input('alqueires 3')), 'alqueires 3')
