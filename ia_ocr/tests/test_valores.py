"""Testes do codec de valores do I-5: payload → texto canônico → Django.

Três mundos: payload A3 (str/bool/null), formulário de revisão (o que o
humano digita) e os alvos Django (date/Decimal/bool/str/None). O codec
garante ida e volta determinística — nada de `str(True)`.
"""

import datetime
from decimal import Decimal

from django.db import models
from django.test import SimpleTestCase

from dominial.models import Lancamento

from ia_ocr.valores import (
    ErroInterno,
    ValorInvalido,
    do_formulario,
    do_payload,
    para_python,
)

# Destinos reais: DecimalField(max_digits=10, decimal_places=2)
VALOR_TRANSACAO = Lancamento._meta.get_field('valor_transacao')
# CharField(max_length=255)
TITULO = Lancamento._meta.get_field('titulo')


class DecimalLimites(SimpleTestCase):
    """do_formulario('decimal', …) contra max_digits/decimal_places reais."""

    def test_aceita_virgula_e_ponto(self):
        self.assertEqual(do_formulario('decimal', '1234,56', VALOR_TRANSACAO), '1234.56')
        self.assertEqual(do_formulario('decimal', '1234.56', VALOR_TRANSACAO), '1234.56')
        self.assertEqual(do_formulario('decimal', '  1 ,5  ', None), '1.5')

    def test_rejeita_negativo_e_nao_numero(self):
        for texto in ('-1', '-0,01', 'abc', '1,2,3'):
            with self.subTest(texto=texto):
                with self.assertRaises(ValorInvalido):
                    do_formulario('decimal', texto, VALOR_TRANSACAO)

    def test_decimal_limites_do_destino(self):
        """decimal_places=2 e max_digits=10 de Lancamento.valor_transacao."""
        self.assertEqual(
            do_formulario('decimal', '99999999.99', VALOR_TRANSACAO),
            '99999999.99',
        )
        # 9 inteiros + 2 casas = 11 > max_digits=10
        with self.assertRaises(ValorInvalido):
            do_formulario('decimal', '999999999.99', VALOR_TRANSACAO)
        # 3 casas > decimal_places=2
        with self.assertRaises(ValorInvalido):
            do_formulario('decimal', '1.234', VALOR_TRANSACAO)
        # 5 casas > decimal_places=4 de Lancamento.area
        with self.assertRaises(ValorInvalido):
            do_formulario('decimal', '1.99999', Lancamento._meta.get_field('area'))


class Tipos(SimpleTestCase):
    def test_booleano_false_ida_e_volta(self):
        """False grava 'false' e relê como False — nunca 'False'/'true'."""
        canonico = do_payload('booleano', False)
        self.assertEqual(canonico, 'false')
        self.assertIs(para_python('booleano', canonico), False)

        self.assertEqual(do_formulario('booleano', 'false', None), 'false')
        self.assertIs(
            para_python('booleano', do_formulario('booleano', 'false', None)),
            False,
        )
        self.assertIs(
            para_python('booleano', do_payload('booleano', True)), True
        )

    def test_booleano_aceita_so_canonico(self):
        for texto in ('True', 'FALSE', 'sim', '1'):
            with self.subTest(texto=texto):
                with self.assertRaises(ValorInvalido):
                    do_formulario('booleano', texto, None)

    def test_null_preservado(self):
        """None do payload e texto vazio do formulário voltam como None."""
        for tipo in ('data', 'decimal', 'booleano', 'texto', 'enum'):
            with self.subTest(tipo=tipo):
                self.assertEqual(do_payload(tipo, None), '')
                self.assertIsNone(para_python(tipo, ''))
                self.assertIsNone(para_python(tipo, None))
                self.assertEqual(do_formulario(tipo, None, None), '')
                self.assertEqual(do_formulario(tipo, '', None), '')

    def test_objeto_rejeitado(self):
        """do_payload só aceita str/bool/None; outro tipo é erro interno."""
        for valor in ({'a': 1}, ['x'], 42, 1.5, datetime.date(2024, 1, 1)):
            with self.subTest(valor=valor):
                with self.assertRaises(ErroInterno):
                    do_payload('texto', valor)

    def test_data_invalida_rejeitada(self):
        """Regex estrita + fromisoformat: nada de data brasileira/colada."""
        for texto in (
            '2024-02-30',
            '20240101',
            '31/12/2024',
            ' 2024-01-01',
            '2024-1-1',
            'ontem',
        ):
            with self.subTest(texto=texto):
                with self.assertRaises(ValorInvalido):
                    do_formulario('data', texto, None)

    def test_data_valida_ida_e_volta(self):
        self.assertEqual(do_formulario('data', '2024-02-29', None), '2024-02-29')
        self.assertEqual(
            para_python('data', '2024-02-29'), datetime.date(2024, 2, 29)
        )
        self.assertIsInstance(para_python('data', '2024-02-29'), datetime.date)

    def test_texto_max_length_do_destino(self):
        """max_length do destino; 10 000 quando sem destino."""
        self.assertEqual(do_formulario('texto', 'x' * 255, TITULO), 'x' * 255)
        with self.assertRaises(ValorInvalido):
            do_formulario('texto', 'x' * 256, TITULO)

        self.assertEqual(do_formulario('texto', 'x' * 10_000, None), 'x' * 10_000)
        with self.assertRaises(ValorInvalido):
            do_formulario('texto', 'x' * 10_001, None)

    def test_enum_respeita_choices_do_destino(self):
        destino = models.CharField(choices=[('a', 'A'), ('b', 'B')], max_length=10)
        self.assertEqual(do_formulario('enum', 'a', destino), 'a')
        with self.assertRaises(ValorInvalido):
            do_formulario('enum', 'z', destino)
        # sem destino (ou sem choices) não rejeita
        self.assertEqual(do_formulario('enum', 'a', None), 'a')

    def test_ida_e_volta_decimal_alem_do_canonico(self):
        """Texto canônico do formulário relê como Decimal no alvo Django."""
        canonico = do_formulario('decimal', '99,99', VALOR_TRANSACAO)
        self.assertEqual(para_python('decimal', canonico), Decimal('99.99'))
