"""Máscaras de CPF/RG da evidência (I-5) — porte dos casos que viviam em
``test_revisao_tela_navegacao_parte2.py``/``parte3.py`` (#341 fase 3).

A função mudou de dono (``views`` → ``mascaras``) antes de a tela de cards
ser aposentada (fase 4): estes casos ficam e passam a resolver o nome no
módulo dono, ``ia_ocr.mascaras``, para sobreviverem à remoção da tela.
"""

from django.test import SimpleTestCase

from ia_ocr import mascaras


class MascararEvidenciaTest(SimpleTestCase):
    """Casos verbatim das partes 2 e 3 de ``RevisaoTelaTest``."""

    CASOS_MASCARADOS = (
        ('RG 123456', 'RG ***'),
        ('RG 123456,', 'RG ***,'),
        ('RG 1234567.', 'RG ***.'),
        ('RG 1.234.567', 'RG ***'),
        ('RG 12.345.678', 'RG ***'),
        ('RG 12.345.678-9', 'RG ***'),
        ('R.G. 12.345.678-9', 'R.G. ***'),
        ('RG nº 1.234.567', 'RG nº ***'),
        ('RG n.º 123456', 'RG n.º ***'),
        ('RG nº 123456', 'RG nº ***'),
        ('RG nº. 123456', 'RG nº. ***'),
        ('RG n° 123456', 'RG n° ***'),
        ('RG 12 345 678-9', 'RG ***'),
        ('RG n.º 1.234.567', 'RG n.º ***'),
        ('RG nº. 1234567', 'RG nº. ***'),
        ('12.345.678-9', '***'),
        ('12.345.678-X', '***'),
        ('CPF 123.456.789-00', 'CPF ***'),
        ('CPF 123 456 789 00', 'CPF ***'),
        ('CPF 12345678900', 'CPF ***'),
    )

    CASOS_INTACTOS = (
        'MATRÍCULA Nº 142718 FICHA 01',
        'matrícula 123456',
        'com 123456 apenas',
        'R$ 1500000',
        'R$ 15000000',
        'valor R$ 15000000,00',
        '15000000',
        'R$ 1.500.000,00',
        '1500000,00',
        '250000 m²',
        'CNS 123456789012345',
        '10/01/2020',
        '2020-01-10',
        '0001234-56.2020.8.16.0001',
    )

    def test_mascara_cpf_e_rg_sem_apagar_seis_digitos(self):
        mascarar = mascaras._mascarar_evidencia
        self.assertEqual(
            mascarar('CPF 123.456.789-00 e RG 12.345.678-9'),
            'CPF *** e RG ***',
        )
        self.assertEqual(
            mascarar('Trecho sem documento, com 123456 apenas'),
            'Trecho sem documento, com 123456 apenas',
        )

    def test_mascara_rg_pelo_rotulo(self):
        mascarar = mascaras._mascarar_evidencia
        for trecho, esperado in self.CASOS_MASCARADOS:
            with self.subTest(trecho=trecho):
                self.assertEqual(mascarar(trecho), esperado)

    def test_mascara_preserva_numeros_sem_rotulo(self):
        mascarar = mascaras._mascarar_evidencia
        for trecho in self.CASOS_INTACTOS:
            with self.subTest(trecho=trecho):
                self.assertEqual(mascarar(trecho), trecho)

    def test_mascara_preserva_data_iso_valor_cns_e_processo(self):
        mascarar = mascaras._mascarar_evidencia
        trecho = (
            'Data 10/01/2020, ISO 2020-01-10, valor R$ 1.500.000,00, '
            'CNS 123456789012345, processo 0001234-56.2020.8.16.0001.'
        )
        self.assertEqual(mascarar(trecho), trecho)

    def test_mascara_cpf_e_rg_com_pontuacao_final(self):
        mascarar = mascaras._mascarar_evidencia
        self.assertEqual(
            mascarar('CPF 12345678900 e RG 1234567-X, matrícula 123456.'),
            'CPF *** e RG ***, matrícula 123456.',
        )

    def test_mascara_rg_seguido_de_pontuacao(self):
        mascarar = mascaras._mascarar_evidencia
        self.assertEqual(mascarar('RG 123456.'), 'RG ***.')
        self.assertEqual(
            mascarar('RG 123456, emitido pelo oficial'),
            'RG ***, emitido pelo oficial',
        )

    def test_mascara_preserva_pontuacao_de_numero_maior(self):
        mascarar = mascaras._mascarar_evidencia
        trecho = (
            'Valor 1.500.000,00 e 1500000,00, datas 10/01/2020 e '
            '2020-01-10, CNS 123456789012345'
        )
        self.assertEqual(mascarar(trecho), trecho)

    def test_mascara_cpf_com_espacos_contiguo_e_rg_curto(self):
        mascarar = mascaras._mascarar_evidencia
        self.assertEqual(
            mascarar('CPF 123 456 789 00 e CPF 12345678900.'),
            'CPF *** e CPF ***.',
        )
        self.assertEqual(
            mascarar('RG 123456 e RG 123456789.'),
            'RG *** e RG ***.',
        )

    def test_mascara_preserva_valor_sem_milhar_e_processo_longo(self):
        mascarar = mascaras._mascarar_evidencia
        trecho = (
            'Valor 1500000,00, processo 000123456789, '
            'CNS 123456789012345.'
        )
        self.assertEqual(mascarar(trecho), trecho)

    def test_mascara_vazia_volta_como_veio(self):
        self.assertIs(mascaras._mascarar_evidencia(''), '')
        self.assertIsNone(mascaras._mascarar_evidencia(None))


class MascararDocumentosTest(SimpleTestCase):
    """Rótulos de cadastro usam os máscaras por documento (via _rotulo_pessoa)."""

    def test_cpf_mantem_os_dois_ultimos_digitos(self):
        self.assertEqual(
            mascaras._mascarar_cpf('123.456.789-00'),
            'CPF ***.***.***-00',
        )
        self.assertEqual(mascaras._mascarar_cpf('1234'), 'CPF ***.***.***-34')

    def test_cpf_sem_digitos_suficientes(self):
        self.assertEqual(mascaras._mascarar_cpf(''), 'CPF ***')
        self.assertEqual(mascaras._mascarar_cpf(None), 'CPF ***')
        self.assertEqual(mascaras._mascarar_cpf('1'), 'CPF ***')

    def test_rg_mantem_os_dois_ultimos_digitos(self):
        self.assertEqual(mascaras._mascarar_rg('12.345.678-9'), 'RG ***89')
        self.assertEqual(mascaras._mascarar_rg('123456789'), 'RG ***89')

    def test_rg_sem_digitos_suficientes(self):
        self.assertEqual(mascaras._mascarar_rg(''), 'RG ***')
        self.assertEqual(mascaras._mascarar_rg(None), 'RG ***')
        self.assertEqual(mascaras._mascarar_rg('7'), 'RG ***')
