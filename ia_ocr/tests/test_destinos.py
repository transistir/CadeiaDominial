"""Testes do mapa de destinos do I-5 (§2.A: pointer → destino).

Cobertura máxima: todo caminho editável do A3 tem entrada (destino ou
SEM_DESTINO) e todo destino existe em `_meta` do modelo real (§25).
"""

import json

from django.apps import apps
from django.test import SimpleTestCase

from ia_ocr import destinos
from ia_ocr.destinos import (
    SEM_DESTINO,
    ChaveDesconhecida,
    caminhos_editaveis,
    destino_de,
)
from ia_ocr.extracao_schema import SCHEMA_PATH


def _schema():
    with open(SCHEMA_PATH, encoding='utf-8') as arquivo:
        return json.load(arquivo)


class Cobertura(SimpleTestCase):
    def test_todo_caminho_editavel_tem_entrada(self):
        faltantes = [
            ponteiro
            for ponteiro in caminhos_editaveis(_schema())
            if not self._tem_entrada(ponteiro)
        ]
        self.assertFalse(
            faltantes,
            'campos editáveis do A3 sem entrada no mapa (§25): '
            f'{faltantes}',
        )

    @staticmethod
    def _tem_entrada(ponteiro):
        try:
            destino_de(ponteiro)
        except ChaveDesconhecida:
            return False
        return True

    def test_todo_destino_existe_em_meta(self):
        faltantes = []
        for padrao, entrada in _destinos_mapa().items():
            if (
                entrada is None
                or isinstance(entrada, destinos.Destino)
                or entrada[1] is None
            ):
                continue
            modelo, campo, _ = entrada
            try:
                apps.get_model(modelo)._meta.get_field(campo)
            except LookupError:
                faltantes.append((padrao, modelo, campo))
        self.assertFalse(
            faltantes,
            'destinos do mapa sem campo em _meta (§25): ' f'{faltantes}',
        )


def _destinos_mapa():
    return destinos.DESTINOS


class PorPapel(SimpleTestCase):
    def test_partes_por_papel(self):
        transmitente = destino_de('/acts/0/partes/3', 'transmitente')
        self.assertEqual(
            transmitente.campo_modelo, 'dominial.LancamentoPessoa.tipo'
        )
        self.assertEqual(transmitente.tipo_valor, 'enum')

        adquirente = destino_de('/acts/*/partes/*', 'adquirente')
        self.assertEqual(
            adquirente.campo_modelo, 'dominial.LancamentoPessoa.tipo'
        )

    def test_papel_sem_parte_e_sem_destino(self):
        for papel in ('conjuge', 'representante', 'testemunha'):
            with self.subTest(papel=papel):
                self.assertIs(
                    destino_de('/acts/0/partes/1', papel), SEM_DESTINO
                )


class DocumentoIdentificacao(SimpleTestCase):
    def test_documento_identificacao_por_tipo(self):
        cpf = destino_de(
            '/acts/0/partes/0/documento_identificacao/valor',
            'CPF',
            '529.982.247-25',  # 11 dígitos com máscara
        )
        self.assertEqual(cpf.campo_modelo, 'dominial.Pessoas.cpf')
        self.assertEqual(cpf.max_length, 11)

        rg = destino_de(
            '/acts/0/partes/0/documento_identificacao/valor',
            'RG',
            'MG-11.234.567',
        )
        self.assertEqual(rg.campo_modelo, 'dominial.Pessoas.rg')
        self.assertEqual(rg.max_length, 20)

    def test_cpf_mascarado_cnj_e_outro_sao_sem_destino(self):
        for tipo, valor in (
            ('CPF', '***.231.628-**'),  # mascarado: dígitos < 11
            ('CNPJ', '04.252.011/0001-10'),
            ('CGC', '33.627.432/0001-00'),
            ('OUTRO', 'ABC-123'),
            ('CPF', None),  # sem valor legível
        ):
            with self.subTest(tipo=tipo, valor=valor):
                self.assertIs(
                    destino_de(
                        '/acts/*/partes/*/documento_identificacao/valor',
                        tipo,
                        valor,
                    ),
                    SEM_DESTINO,
                )


class DestinoDeArea(SimpleTestCase):
    def test_area_do_ato_e_area_do_lancamento(self):
        destino = destino_de('/acts/0/area')
        self.assertEqual(destino.campo_modelo, 'dominial.Lancamento.area')
        self.assertEqual((destino.max_digits, destino.decimal_places), (12, 4))
        self.assertEqual(destino.tipo_valor, 'area')

    def test_area_do_cabecalho_e_sem_destino(self):
        self.assertIs(destino_de('/document/area'), SEM_DESTINO)


class ChaveDesconhecidaLevanta(SimpleTestCase):
    def test_chave_desconhecida_levanta(self):
        for chave in (
            '/document/campo_inexistente',
            '/acts/*/propriedade_extra',
            '/closure/fora_do_mapa',
        ):
            with self.subTest(chave=chave):
                with self.assertRaises(ChaveDesconhecida):
                    destino_de(chave)


class LimitesVemDeMeta(SimpleTestCase):
    def test_limites_do_campo_real(self):
        titulo = destino_de('/acts/0/titulo')
        self.assertEqual(titulo.modelo, 'dominial.Lancamento')
        self.assertEqual(titulo.campo, 'titulo')
        self.assertEqual(titulo.max_length, 255)

        forma = destino_de('/acts/4/forma')
        self.assertEqual(forma.max_length, 100)

        valor = destino_de('/acts/2/valor_transacao')
        self.assertEqual((valor.max_digits, valor.decimal_places), (10, 2))

        for chave in (
            '/document/cartorio',
            '/document/cri_atual',
            '/acts/0/origem/cartorio',
            '/acts/0/cartorio_transmissao',
        ):
            with self.subTest(chave=chave):
                self.assertEqual(destino_de(chave).max_length, 200)

    def test_texto_liberado_da_conferencia_tem_10_mil(self):
        for chave in ('/document/imovel_descricao', '/acts/9/rotulo'):
            with self.subTest(chave=chave):
                destino = destino_de(chave)
                self.assertIs(destino, SEM_DESTINO)
                self.assertEqual(destino.max_length, 10_000)
