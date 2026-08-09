from django.test import SimpleTestCase

from dominial.utils.cns_utils import (
    CNS_INSTITUCIONAL,
    CNS_SINTETICO,
    CNS_VALIDO,
    DV_NAO_CONFERE,
    FORMATO_NAO_PADRAO,
    calcular_dv_cns,
    classificar_cns,
    cns_dv_confere,
    cns_eh_sintetico,
    normalizar_nome,
    normalizar_nome_cartorio,
)


class CnsUtilsTest(SimpleTestCase):
    def test_cns_sintetico_usa_upper_trim_e_prefixo(self):
        for valor in ('CNS2339110126', ' cns1089051924 ', 'CNS'):
            with self.subTest(valor=valor):
                self.assertTrue(cns_eh_sintetico(valor))
                self.assertEqual(classificar_cns(valor).motivo, CNS_SINTETICO)

        self.assertFalse(cns_eh_sintetico('158030'))

    def test_cns_canonico_tem_cinco_digitos_e_dv_luhn(self):
        self.assertEqual(calcular_dv_cns('15803'), 0)
        self.assertTrue(cns_dv_confere('158030'))
        self.assertEqual(classificar_cns('158030').motivo, CNS_VALIDO)

    def test_falha_de_dv_tem_motivo_proprio(self):
        resultado = classificar_cns('158031')

        self.assertFalse(resultado.dv_confere)
        self.assertEqual(resultado.motivo, DV_NAO_CONFERE)

    def test_formato_nao_padrao_nao_e_confundido_com_dv_invalido(self):
        resultado = classificar_cns('12345')

        self.assertIsNone(resultado.dv_confere)
        self.assertEqual(resultado.motivo, FORMATO_NAO_PADRAO)

    def test_cns_8888xx_e_institucional_mesmo_com_dv_incorreto(self):
        resultado = classificar_cns('888800')

        self.assertTrue(resultado.institucional)
        self.assertEqual(resultado.motivo, CNS_INSTITUCIONAL)

    def test_normalizar_nome_nfkd_casefold_pontuacao_e_espacos(self):
        nome = '  Cartório   de Registro — Ponta Porã!  '

        self.assertEqual(
            normalizar_nome(nome),
            'cartorio de registro ponta pora',
        )
        self.assertEqual(normalizar_nome_cartorio(nome), normalizar_nome(nome))

    def test_normalizacao_nao_faz_matching_avancado(self):
        self.assertNotEqual(
            normalizar_nome('Cartório de Registro de Imóveis de Ponta Porã'),
            normalizar_nome('Registro de Imóveis de Ponta Porã'),
        )

    def test_entradas_invalidas_falham_explicitamente(self):
        with self.assertRaises(TypeError):
            cns_eh_sintetico(None)
        with self.assertRaises(ValueError):
            calcular_dv_cns('1234A')
        with self.assertRaises(TypeError):
            normalizar_nome(None)
