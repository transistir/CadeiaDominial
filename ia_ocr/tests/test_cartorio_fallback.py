"""Seletor de cartório nunca vazio (#315): fallback pela comarca do texto."""

import json

from dominial.models import Cartorios
from ia_ocr import revisao
from ia_ocr.models import CampoSugerido
from ia_ocr.revisao import IndiceCartorios

from . import test_revisao_tela as tela
from .test_revisao_tela import _atributos, _descendentes, _elementos

CHAVE = '/document/cartorio'
CABECALHO = (
    '1º OFÍCIO DO REGISTRO DE IMÓVEIS E HIPOTECAS\n'
    'COMARCA DE ITAMARAJU - ESTADO DA BAHIA\nMatrícula 1\n'
)


class CartorioFallbackTest(tela.TelaRevisaoBase):
    def setUp(self):
        super().setUp()
        self.itamaraju = Cartorios.objects.create(
            nome='Registro de Imóveis de Itamaraju', cidade='ITAMARAJU',
            estado='BA', cns='140160',
        )
        self.outro = Cartorios.objects.create(
            nome='Registro de Imóveis de Prado', cidade='PRADO',
            estado='BA', cns='140161',
        )

    def _com_cartorio_sem_candidatos(self, texto=CABECALHO):
        self.job.paginas.filter(numero_pagina=1).update(texto_ocr=texto)
        extracao = self._extracao()
        CampoSugerido.objects.filter(extracao=extracao, chave=CHAVE).update(
            raw=None, normalized=None, match_candidatos=[],
            cartorio_escolhido=None, criar_novo=False,
        )
        return extracao

    def test_comarca_do_cabecalho_inclui_cartorio_da_cidade(self):
        extracao = self._com_cartorio_sem_candidatos()
        ids = self._candidatos(extracao)
        self.assertEqual(ids, [self.itamaraju.pk])

    def _candidatos(self, extracao):
        return revisao.candidatos_cartorio_fallback(
            extracao, CHAVE, IndiceCartorios(),
            revisao.comarca_do_documento(extracao),
        )

    def test_comarca_citada_no_corpo_nao_conta(self):
        corpo = (
            'MATRÍCULA Nº 1 - LIVRO 2 - REGISTRO GERAL\n' + 'x ' * 400
            + '\ntranscrição oriunda da COMARCA DE PRADO, conforme registro'
        )
        extracao = self._com_cartorio_sem_candidatos(corpo)
        self.assertEqual(self._candidatos(extracao), [])

    def test_homonimo_de_outro_estado_nao_entra(self):
        Cartorios.objects.create(
            nome='Registro de Imóveis de Itamaraju SP', cidade='ITAMARAJU',
            estado='SP', cns='140162',
        )
        extracao = self._com_cartorio_sem_candidatos()
        self.assertEqual(self._candidatos(extracao), [self.itamaraju.pk])

    def test_uf_por_sigla_filtra_homonimo_de_outro_estado(self):
        Cartorios.objects.create(
            nome='Registro de Imóveis de Itamaraju SP', cidade='ITAMARAJU',
            estado='SP', cns='140163',
        )
        extracao = self._com_cartorio_sem_candidatos(
            'COMARCA DE ITAMARAJU - BA\nMatrícula 1\n'
        )
        self.assertEqual(
            revisao.comarca_do_documento(extracao),
            revisao.Comarca('ITAMARAJU', 'BA'),
        )
        self.assertEqual(self._candidatos(extracao), [self.itamaraju.pk])

    def test_match_unico_por_nome_de_outro_estado_nao_vira_candidato(self):
        Cartorios.objects.create(
            nome='Cartório Único SP', cidade='ITAMARAJU', estado='SP',
            cns='140164',
        )
        extracao = self._com_cartorio_sem_candidatos()
        CampoSugerido.objects.filter(extracao=extracao, chave=CHAVE).update(
            raw='Cartório Único SP', normalized='Cartório Único SP',
        )
        self.assertEqual(self._candidatos(extracao), [self.itamaraju.pk])

    def test_mesma_cidade_com_ufs_diferentes_e_ambigua(self):
        extracao = self._com_cartorio_sem_candidatos(
            'COMARCA DE BOM JESUS - PIAUÍ\nCOMARCA DE BOM JESUS - GOIÁS\n'
        )
        self.assertIsNone(revisao.comarca_do_documento(extracao))
        self.assertEqual(self._candidatos(extracao), [])

    def test_duas_comarcas_no_cabecalho_sao_ambiguas(self):
        extracao = self._com_cartorio_sem_candidatos(
            'COMARCA DE ITAMARAJU - BA\nCOMARCA DE PRADO - BA\n'
        )
        self.assertEqual(self._candidatos(extracao), [])

    def test_municipio_de_nao_e_comarca(self):
        extracao = self._com_cartorio_sem_candidatos(
            'MUNICÍPIO DE ITAMARAJU\n'
        )
        self.assertEqual(self._candidatos(extracao), [])

    def test_sem_comarca_e_sem_valor_devolve_vazio(self):
        extracao = self._com_cartorio_sem_candidatos('Sem cabeçalho útil.')
        self.assertEqual(
            self._candidatos(extracao), [],
        )

    def test_candidatos_preexistentes_sao_devolvidos(self):
        extracao = self._com_cartorio_sem_candidatos()
        CampoSugerido.objects.filter(extracao=extracao, chave=CHAVE).update(
            match_candidatos=[self.outro.pk],
        )
        self.assertEqual(
            self._candidatos(extracao), [self.outro.pk],
        )

    def test_tela_lista_opcao_sem_preselecionar(self):
        extracao = self._com_cartorio_sem_candidatos()
        html = self._tela().content.decode()
        card = next(
            c for c in _elementos(html, 'article', presentes=('data-campo',))
            if _atributos(c)['data-chave'] == CHAVE
        )
        select = _descendentes(card, 'select', 'data-ocr-escolha')[0]
        opcoes = [
            o for o in _descendentes(select, 'option', 'value')
            if _atributos(o)['value']
        ]
        self.assertEqual(
            [_atributos(o)['value'] for o in opcoes], [str(self.itamaraju.pk)],
        )
        self.assertTrue(all('selected' not in _atributos(o) for o in opcoes))
        # Exibição apenas: nada foi gravado.
        campo = extracao.campos.get(chave=CHAVE)
        self.assertEqual(campo.match_candidatos, [])
        self.assertIsNone(campo.cartorio_escolhido_id)

    def _salvar(self, extracao, cartorio_id):
        html = self._tela().content.decode()
        toolbar = _elementos(html, 'div', presentes=('data-ocr-toolbar',))[0]
        return self.client.post(
            self.url('salvar_bloco_ocr'),
            data=json.dumps({
                'versao': _atributos(toolbar)['data-versao'],
                'decisoes': [{
                    'chave': CHAVE, 'incluir': True,
                    'escolha': {
                        'pessoa_id': None, 'cartorio_id': cartorio_id,
                        'criar_novo': False,
                    },
                }],
            }),
            content_type='application/json',
        )

    def test_save_aceita_id_do_fallback_e_persiste_candidatos(self):
        extracao = self._com_cartorio_sem_candidatos()
        resposta = self._salvar(extracao, self.itamaraju.pk)
        self.assertEqual(resposta.status_code, 200, resposta.content)
        campo = extracao.campos.get(chave=CHAVE)
        self.assertEqual(campo.match_candidatos, [self.itamaraju.pk])
        self.assertEqual(campo.cartorio_escolhido_id, self.itamaraju.pk)

    def test_save_recusa_id_fora_do_fallback(self):
        extracao = self._com_cartorio_sem_candidatos()
        resposta = self._salvar(extracao, self.outro.pk)
        self.assertEqual(resposta.status_code, 422, resposta.content)
        self.assertEqual(
            extracao.campos.get(chave=CHAVE).match_candidatos, [],
        )
