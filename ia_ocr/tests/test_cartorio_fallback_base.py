"""Infraestrutura compartilhada de CartorioFallbackTest."""

"""Seletor de cartório nunca vazio (#315): fallback pela comarca do texto."""

import json

from dominial.models import Cartorios
from ia_ocr import revisao
from ia_ocr.models import CampoSugerido
from ia_ocr.revisao import IndiceCartorios

from .test_revisao_tela_base import _descendentes
from .test_ui_card_ocr import _atributos, _elementos

CHAVE = '/document/cartorio'
CABECALHO = (
    '1º OFÍCIO DO REGISTRO DE IMÓVEIS E HIPOTECAS\n'
    'COMARCA DE ITAMARAJU - ESTADO DA BAHIA\nMatrícula 1\n'
)




class CartorioFallbackBase:
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


    def _candidatos(self, extracao):
        return revisao.candidatos_cartorio_fallback(
            extracao, CHAVE, IndiceCartorios(),
            revisao.comarca_do_documento(extracao),
        )


    def _lista_completa(self):
        """Lista completa do índice: todos os cartórios por (nome, id).

        Inclui o cartório da fixture base (``CRI Teste …``, SP), cujo nome
        precede ``Registro de Imóveis …`` na ordenação.
        """
        return [
            self.documento.cartorio_id, self.itamaraju.pk, self.outro.pk,
        ]


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


    def _povoar_501_na_uf(self):
        """501 cartórios na BA com o alvo na posição 501 — a última.

        Antes do #318 o corte de 500 escondia o alvo do ``<select>`` e o
        save o recusava (id fora do fallback): duplicata de volta.
        """
        Cartorios.objects.bulk_create(
            Cartorios(
                nome=f'A Cartório BA {i:03d}', cidade='PORTO SEGURO',
                estado='BA', cns=f'9000{i:05d}',
            )
            for i in range(1, 499)
        )
        return Cartorios.objects.create(
            nome='Z Cartório Alvo da UF', cidade='PORTO SEGURO',
            estado='BA', cns='9499999',
        )


    def _povoar_501_no_total(self):
        """501 cartórios no índice com o alvo na última posição."""
        Cartorios.objects.bulk_create(
            Cartorios(
                nome=f'Cartório Total {i:03d}', cidade='PORTO SEGURO',
                estado='BA', cns=f'9100{i:05d}',
            )
            for i in range(1, 498)
        )
        return Cartorios.objects.create(
            nome='Z Cartório Sem Comarca', cidade='PORTO SEGURO',
            estado='BA', cns='9599999',
        )


    def _opcoes_cartorio(self):
        """Ids oferecidos no ``<select>`` do card de cartório, pela tela."""
        html = self._tela().content.decode()
        card = next(
            c for c in _elementos(html, 'article', presentes=('data-campo',))
            if _atributos(c)['data-chave'] == CHAVE
        )
        select = _descendentes(card, 'select', 'data-ocr-escolha')[0]
        return [
            _atributos(o)['value']
            for o in _descendentes(select, 'option', 'value')
            if _atributos(o)['value']
        ]

