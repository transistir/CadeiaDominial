"""Infraestrutura da tela de revisão como formulário (I-14 / #341, fase 2) —
migração VERBATIM de ``ia_ocr/tests/test_revisao_formulario_view.py``
(Etapa 12 do plano de 400 linhas).

Nenhum teste aqui: o parser ``_Formulario``, ``post_do_html``,
``MODELOS_CONTADOS`` e ``RevisaoFormularioBase`` (setUp + helpers).
"""

from copy import deepcopy
from html.parser import HTMLParser

from django.contrib.messages import get_messages
from django.urls import reverse

from dominial.models import (
    Cartorios, Documento, Lancamento, LancamentoOrigem, LancamentoPessoa,
    Pessoas,
)
from ia_ocr.models import ImportacaoIA, OcrJobTransicao

from .payloads_extracao import payload_averbacao, payload_registro
from .test_revisao_formulario_prefill import PrefillBase


class _Formulario(HTMLParser):
    """O ``<form id="lancamento-form">`` renderizado → o POST do navegador.

    Segue o que o navegador envia: campo ``disabled`` e sem ``name`` fora,
    checkbox só marcado, select com a opção marcada (ou a primeira), textarea
    pelo texto. A única lógica de JS reproduzida é a do envio que copia a área
    do campo visível do tipo para o hidden ``area`` (template, fim do script).
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.no_form = False
        self.campos = []
        self.ids = {}
        self._select = None
        self._textarea = None
        self.html_do_form = []

    def handle_starttag(self, tag, atributos):
        atributos = dict(atributos)
        if tag == 'form' and atributos.get('id') == 'lancamento-form':
            self.no_form = True
            return
        if not self.no_form:
            return
        if tag == 'input':
            self._input(atributos)
        elif tag == 'select' and 'name' in atributos:
            self._select = {
                'nome': atributos['name'], 'opcoes': [],
                'desligado': 'disabled' in atributos,
            }
        elif tag == 'option' and self._select is not None:
            self._select['opcoes'].append({
                'valor': atributos.get('value', ''),
                'marcada': 'selected' in atributos,
                'tipo': atributos.get('data-tipo'),
            })
        elif tag == 'textarea' and 'name' in atributos:
            self._textarea = {
                'nome': atributos['name'], 'texto': '',
                'desligado': 'disabled' in atributos,
            }

    def handle_endtag(self, tag):
        if tag == 'form':
            self.no_form = False
        elif tag == 'select' and self._select is not None:
            select, self._select = self._select, None
            marcada = next((o for o in select['opcoes'] if o['marcada']), None)
            escolhida = marcada or (select['opcoes'][0] if select['opcoes'] else None)
            self.ids[select['nome']] = escolhida
            if escolhida is not None and not select['desligado']:
                self.campos.append((select['nome'], escolhida['valor']))
        elif tag == 'textarea' and self._textarea is not None:
            area, self._textarea = self._textarea, None
            if not area['desligado']:
                self.campos.append((area['nome'], area['texto']))

    def handle_data(self, dados):
        if self._textarea is not None:
            self._textarea['texto'] += dados

    def _input(self, atributos):
        if 'id' in atributos:
            self.ids[atributos['id']] = atributos.get('value') or ''
        nome = atributos.get('name')
        if not nome or 'disabled' in atributos:
            return
        tipo = (atributos.get('type') or 'text').lower()
        if tipo in ('submit', 'button', 'image', 'file', 'reset'):
            return
        if tipo in ('checkbox', 'radio'):
            if 'checked' in atributos:
                self.campos.append((nome, atributos.get('value') or 'on'))
            return
        self.campos.append((nome, atributos.get('value') or ''))

    def post(self):
        dados = {}
        for nome, valor in self.campos:
            dados.setdefault(nome, []).append(valor)
        # JS do envio: o hidden ``area`` recebe o campo visível do tipo.
        tipo = (self.ids.get('tipo_lancamento') or {}).get('tipo')
        visivel = {
            'averbacao': 'area_averbacao', 'registro': 'area_transmissao',
            'inicio_matricula': 'area_inicio_matricula',
        }.get(tipo)
        if visivel is not None and visivel in self.ids:
            dados['area'] = [self.ids[visivel].strip().replace(',', '.')]
        return dados


def post_do_html(resposta, **trocas):
    """POST que o navegador enviaria para o formulário da ``resposta``."""
    formulario = _Formulario()
    formulario.feed(resposta.content.decode())
    dados = formulario.post()
    for nome, valor in trocas.items():
        dados[nome] = valor if isinstance(valor, list) else [valor]
    return dados


MODELOS_CONTADOS = (
    Lancamento, LancamentoPessoa, LancamentoOrigem, Documento, Pessoas,
    Cartorios, ImportacaoIA, OcrJobTransicao,
)


class RevisaoFormularioBase(PrefillBase):
    """Job em ``extraido`` com três atos: R-1, Av-1 e R-2."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.usuario)
        self.extracao = self._aberta(self._payload_de_tres_atos())

    def _payload_de_tres_atos(self):
        payload = payload_registro(self.job.job_id)
        averbacao = payload_averbacao(self.job.job_id)['acts'][0]
        segundo = deepcopy(payload['acts'][0])
        segundo['rotulo'] = self._campo('R-2', 'R-2/42.718')
        segundo['data'] = self._campo('2020-05-10', '10 de maio de 2020')
        segundo['partes'] = segundo['partes'][:1] + segundo['partes'][2:]
        payload['acts'] += [averbacao, segundo]
        return payload

    def kwargs(self, **extra):
        return {
            'tis_id': self.imovel.terra_indigena_id.pk,
            'imovel_id': self.imovel.pk,
            'documento_id': self.documento.pk,
            'job_id': self.job.job_id,
            **extra,
        }

    def url_ato(self, indice):
        return reverse('revisar_ato_ocr', kwargs=self.kwargs(indice=indice))

    def url_entrada(self):
        return reverse('revisar_job_ocr', kwargs=self.kwargs())

    def url_documento(self):
        return reverse('documento_detalhado', kwargs={
            'tis_id': self.imovel.terra_indigena_id.pk,
            'imovel_id': self.imovel.pk, 'documento_id': self.documento.pk,
        })

    def contagens(self):
        return {modelo.__name__: modelo.objects.count() for modelo in MODELOS_CONTADOS}

    def mensagens(self, resposta):
        return [str(m) for m in get_messages(resposta.wsgi_request)]

    def salvar(self, indice, **trocas):
        """GET do ato → POST do formulário renderizado (como o navegador)."""
        pagina = self.client.get(self.url_ato(indice))
        self.assertEqual(pagina.status_code, 200)
        return self.client.post(self.url_ato(indice), post_do_html(pagina, **trocas))
