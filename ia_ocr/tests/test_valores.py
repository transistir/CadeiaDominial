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

from ia_ocr import valores
from ia_ocr.destinos import SEM_DESTINO, destino_de
from ia_ocr.valores import (
    MOTIVO_INCOMPATIVEL,
    ErroInterno,
    ValorInvalido,
    do_formulario,
    do_payload,
    para_python,
    validar_destino,
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

    def test_so_espacos_vira_vazio_sem_conversor(self):
        self.assertEqual(do_formulario('decimal', '   ', VALOR_TRANSACAO), '')
        self.assertEqual(
            do_formulario('area', '   ', destino_de('/acts/0/area')), '',
        )

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
        # 9 inteiros sem casas: max_digits - decimal_places = 8 inteiros
        with self.assertRaises(ValorInvalido):
            do_formulario('decimal', '999999999', VALOR_TRANSACAO)
        # 3 casas > decimal_places=2
        with self.assertRaises(ValorInvalido):
            do_formulario('decimal', '1.234', VALOR_TRANSACAO)
        # 5 casas > decimal_places=4 de Lancamento.area
        with self.assertRaises(ValorInvalido):
            do_formulario('decimal', '1.99999', Lancamento._meta.get_field('area'))


class DecimalNaoFinito(SimpleTestCase):
    """NaN/Infinity e expoentes absurdos nunca viram Decimal materializado."""

    def test_rejeita_nao_finitos_e_expoentes_absurdos(self):
        for texto in (
            'NaN', 'nan', 'sNaN',
            'Infinity', 'inf', '-Infinity', '-inf',
            '1e999999', '1e-999999',
        ):
            with self.subTest(texto=texto):
                with self.assertRaises(ValorInvalido):
                    do_formulario('decimal', texto, VALOR_TRANSACAO)

    def test_para_python_tambem_rejeita_nao_finito(self):
        for texto in ('NaN', 'Infinity', '1e999999'):
            with self.subTest(texto=texto):
                with self.assertRaises(ValorInvalido):
                    para_python('decimal', texto)


class ValidarLimites(SimpleTestCase):
    """Sugestão intocada precisa caber no destino (finalização e save)."""

    def test_texto_acima_do_max_length(self):
        destino = destino_de('/acts/0/titulo')
        self.assertIsNone(valores.validar_limites(destino, 'x' * 255))
        self.assertEqual(
            valores.validar_limites(destino, 'x' * 256),
            valores.MOTIVO_LIMITE,
        )

    def test_decimal_acima_de_digitos_e_casas(self):
        destino = destino_de('/acts/0/valor_transacao')
        self.assertIsNone(valores.validar_limites(destino, '99999999.99'))
        self.assertEqual(
            valores.validar_limites(destino, '999999999.99'),
            valores.MOTIVO_LIMITE,
        )
        self.assertEqual(
            valores.validar_limites(destino, '999999999'),
            valores.MOTIVO_LIMITE,
        )
        self.assertEqual(
            valores.validar_limites(destino, '1.234'),
            valores.MOTIVO_LIMITE,
        )

    def test_area_acima_do_destino(self):
        destino = destino_de('/acts/0/area')
        self.assertIsNone(valores.validar_limites(destino, '1234.5678'))
        self.assertIsNone(valores.validar_limites(destino, '99999999.9999'))
        self.assertEqual(
            valores.validar_limites(destino, '1.99999'),
            valores.MOTIVO_LIMITE,
        )
        self.assertEqual(
            valores.validar_limites(destino, '999999999'),
            valores.MOTIVO_LIMITE,
        )

    def test_valor_nulo_e_destinos_sem_conversor_nao_acusam(self):
        self.assertIsNone(
            valores.validar_limites(destino_de('/acts/0/titulo'), None)
        )
        self.assertIsNone(
            valores.validar_limites(destino_de('/acts/0'), 'R-1')
        )
        self.assertIsNone(
            valores.validar_limites(
                destino_de('/acts/0/partes/0'), 'transmitente',
            )
        )


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


class PorDestino(SimpleTestCase):
    """do_formulario recebe `Destino | SEM_DESTINO` (§2.A, item 5)."""

    def test_area_do_destino(self):
        """12,4 de Lancamento.area, resolvido por destino_de."""
        destino = destino_de('/acts/0/area')
        self.assertEqual(do_formulario('area', '1234,5678', destino),
                         '1234.5678')
        with self.assertRaises(ValorInvalido):
            do_formulario('area', '1.99999', destino)  # 5 casas > 4
        with self.assertRaises(ValorInvalido):
            do_formulario('area', '999999999.9999', destino)  # 13 dígitos > 12

    def test_area_sem_destino_20_4(self):
        self.assertEqual(
            do_formulario('area', '1.2345', SEM_DESTINO), '1.2345'
        )
        self.assertEqual(
            do_formulario('area', '1' * 20, SEM_DESTINO), '1' * 20
        )
        with self.assertRaises(ValorInvalido):
            do_formulario('area', '1' * 21, SEM_DESTINO)
        with self.assertRaises(ValorInvalido):
            do_formulario('area', '1.99999', SEM_DESTINO)

    def test_sem_destino_texto_limite_10k(self):
        self.assertEqual(
            do_formulario('texto', 'x' * 10_000, SEM_DESTINO), 'x' * 10_000
        )
        with self.assertRaises(ValorInvalido):
            do_formulario('texto', 'x' * 10_001, SEM_DESTINO)

    def test_decimal_do_destino_valor_transacao(self):
        destino = destino_de('/acts/0/valor_transacao')
        self.assertEqual(
            do_formulario('decimal', '99999999.99', destino), '99999999.99'
        )
        with self.assertRaises(ValorInvalido):
            do_formulario('decimal', '999999999.99', destino)

    def test_texto_do_destino_titulo(self):
        destino = destino_de('/acts/0/titulo')
        self.assertEqual(do_formulario('texto', 'x' * 255, destino), 'x' * 255)
        with self.assertRaises(ValorInvalido):
            do_formulario('texto', 'x' * 256, destino)


class ValidarDestino(SimpleTestCase):
    """Naturais incompatíveis com o destino → motivo (§18)."""

    def test_validar_destino_data_em_campo_texto(self):
        campo = destino_de('/acts/0/titulo')  # texto
        self.assertEqual(
            validar_destino(campo, datetime.date(2024, 1, 1)),
            MOTIVO_INCOMPATIVEL,
        )
        self.assertEqual(
            validar_destino(SEM_DESTINO, datetime.date(2024, 1, 1)),
            MOTIVO_INCOMPATIVEL,
        )

    def test_compatibles_retornam_none(self):
        campo = destino_de('/acts/0/titulo')
        self.assertIsNone(validar_destino(campo, 'texto comum'))
        self.assertIsNone(validar_destino(campo, None))

        decimal_campo = destino_de('/acts/0/valor_transacao')
        self.assertIsNone(validar_destino(decimal_campo, Decimal('1.5')))
        self.assertIsNone(validar_destino(decimal_campo, Decimal('0')))

        data_campo = destino_de('/acts/0/data')
        self.assertIsNone(validar_destino(data_campo, '2024-02-29'))
        self.assertEqual(
            validar_destino(data_campo, '31/12/2024'), MOTIVO_INCOMPATIVEL
        )
        self.assertEqual(
            validar_destino(data_campo, '2024-02-30'), MOTIVO_INCOMPATIVEL
        )

        booleano_campo = destino_de('/acts/0/eh_inicio_matricula')
        self.assertIsNone(validar_destino(booleano_campo, 'true'))
        self.assertIsNone(validar_destino(booleano_campo, 'false'))
        self.assertIsNone(validar_destino(booleano_campo, True))
        self.assertEqual(
            validar_destino(booleano_campo, 'sim'), MOTIVO_INCOMPATIVEL
        )

    def test_enum_e_booleano_vazios_nao_sao_ausencia_legitima(self):
        enum_campo = destino_de('/acts/0/origem/tipo_documento')
        for valor in (None, '', '   '):
            with self.subTest(tipo='enum', valor=valor):
                self.assertEqual(
                    validar_destino(enum_campo, valor), MOTIVO_INCOMPATIVEL,
                )

        booleano_campo = destino_de('/acts/0/eh_inicio_matricula')
        for valor in (None, '', '   '):
            with self.subTest(tipo='booleano', valor=valor):
                self.assertEqual(
                    validar_destino(booleano_campo, valor), MOTIVO_INCOMPATIVEL,
                )
