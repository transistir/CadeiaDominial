"""Infraestrutura da tela de revisão de campos (I-5) — migração VERBATIM de
``ia_ocr/tests/test_revisao_tela.py`` (Etapa 10 do plano de 400 linhas).

Nenhum teste aqui: ``TelaRevisaoBase`` (setUp + helpers da tela) e os
helpers de módulo compartilhados pelas partes (``_descendentes``,
``_valor_do_select``, ``_decisao_do_card``, ``_texto_fora_de_details``).
"""

from django.test.html import Element

from ia_ocr import estados, revisao
from ia_ocr.models import CampoSugerido, ExtracaoSugerida, OcrJob

from .base_texto import TelaTextoBase
from .payloads_extracao import (
    PROVIDER, SCHEMA_VERSION, TEXTO_PAGINA_1, payload_averbacao,
)
from .test_ui_card_ocr import _atributos, _elementos


class TelaRevisaoBase(TelaTextoBase):
    """Infraestrutura da tela de revisão; sem testes (reutilizável)."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.dono)
        self.documento.tipo.tipo = 'matricula'
        self.documento.tipo.save(update_fields=['tipo'])
        self.job.paginas.filter(numero_pagina=1).update(texto_ocr=TEXTO_PAGINA_1)
        OcrJob.objects.filter(pk=self.job.pk).update(status=estados.EXTRAIDO)
        self.job.refresh_from_db()

    def _extracao(self, payload=None, resolver=False):
        payload = payload or payload_averbacao(self.job.job_id)
        extracao = ExtracaoSugerida.objects.create(
            ocr_job=self.job, schema_version=SCHEMA_VERSION,
            payload=payload, payload_servico=payload, provider=PROVIDER,
        )
        linhas = revisao.desnormalizar(extracao, payload, list(self.job.paginas.all()))
        if resolver:
            for linha in linhas:
                linha.status_revisao = 'aceito'
                if linha.tipo_valor in ('parte', 'cartorio'):
                    linha.criar_novo = True
        CampoSugerido.objects.bulk_create(linhas)
        return extracao

    def _tela(self):
        return self.client.get(self.url('campos_job_ocr'))

    @staticmethod
    def _chaves_do_html(html):
        return [
            _atributos(card)['data-chave']
            for card in _elementos(html, 'article', presentes=('data-campo',))
        ]

    def _chaves_na_tela(self):
        return self._chaves_do_html(self._tela().content.decode())



def _texto_fora_de_details(no):
    """Texto visível sem atributos nem detalhes, inclusive os aninhados."""
    if isinstance(no, str):
        return no
    if no.name in ('details', 'script', 'style'):
        return ''
    return ' '.join(_texto_fora_de_details(filho) for filho in no.children)


def _descendentes(no, nome_tag, atributo):
    """Elementos `nome_tag` com `atributo` na subárvore de `no`."""
    achados = []
    for filho in no.children:
        if not isinstance(filho, Element):
            continue
        if filho.name == nome_tag and atributo in _atributos(filho):
            achados.append(filho)
        achados += _descendentes(filho, nome_tag, atributo)
    return achados


def _valor_do_select(select):
    """O que o navegador enviaria: a opção selected, senão a primeira."""
    opcoes = _descendentes(select, 'option', 'value')
    selecionadas = [
        opcao for opcao in opcoes if 'selected' in _atributos(opcao)
    ]
    escolhida = (selecionadas or opcoes or [None])[0]
    if escolhida is None:
        return ''
    return _atributos(escolhida).get('value', '')


def _decisao_do_card(card):
    """A decisão que o ocr_revisao.js mandaria com o card conferido.

    Card sem valor fica de fora (nada a conferir); cards de parte/cartório
    levam ``escolha`` com a opção selecionada, a primeira candidata quando
    nenhuma vem selecionada, ou criar novo quando não há candidata.
    """
    valor = None
    for tag in ('input', 'textarea', 'select'):
        for elemento in _descendentes(card, tag, 'data-campo-valor'):
            atributos = _atributos(elemento)
            if tag == 'input':
                valor = atributos.get('value')
            elif tag == 'select':
                valor = _valor_do_select(elemento)
            else:
                valor = ''.join(
                    filho for filho in elemento.children
                    if isinstance(filho, str)
                )
            tipo = atributos['data-tipo']
    if not valor:
        return None
    decisao = {
        'chave': _atributos(card)['data-chave'],
        'incluir': True,
        'conferido': True,
    }
    # Espelha TIPOS_SEM_VALOR do ocr_revisao.js: sem conversor de formulário.
    if tipo not in ('parte', 'ato'):
        decisao['valor'] = valor
    selects = _descendentes(card, 'select', 'data-ocr-escolha')
    criar = _descendentes(card, 'input', 'data-ocr-criar-novo')
    if selects or criar:
        escolhido = None
        alvo = None
        if selects:
            alvo = _atributos(selects[0])['data-ocr-escolha']
            opcoes = [
                opcao for opcao in _descendentes(selects[0], 'option', 'value')
                if _atributos(opcao)['value']
            ]
            selecionadas = [o for o in opcoes if 'selected' in _atributos(o)]
            escolhida = (selecionadas or opcoes or [None])[0]
            if escolhida is not None:
                escolhido = int(_atributos(escolhida)['value'])
        decisao['escolha'] = {
            'pessoa_id': escolhido if alvo == 'pessoa_id' else None,
            'cartorio_id': escolhido if alvo == 'cartorio_id' else None,
            'criar_novo': escolhido is None and bool(criar),
        }
    return decisao
