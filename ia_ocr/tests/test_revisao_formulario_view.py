"""Testes da tela de revisão como formulário de lançamento (I-14 / #341, fase 2).

``revisar_job_ocr`` leva ao primeiro ato pendente e ``revisar_ato_ocr`` é o
formulário de lançamento do ato. Garantias:

- GET e navegação entre atos NÃO gravam nada no banco além de
  ``django_session`` (o rascunho do ato);
- o POST que salva é o do formulário manual, processado pelo mesmo
  ``LancamentoService`` — paridade provada com o HTML renderizado;
- a revisão não reimplementa regra do service (número repetido, duplicata).
"""

import json
import re
from copy import deepcopy
from html.parser import HTMLParser

from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from dominial.models import (
    Cartorios, Documento, Lancamento, LancamentoOrigem, LancamentoPessoa,
    Pessoas, UserTI,
)
from ia_ocr.models import CampoSugerido, ImportacaoIA, OcrJobTransicao

from .factories import criar_documento_digital
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


class EntradaETelaTest(RevisaoFormularioBase):
    def test_entrada_leva_ao_primeiro_ato_pendente(self):
        resposta = self.client.get(self.url_entrada())

        self.assertRedirects(resposta, self.url_ato(0), fetch_redirect_response=False)

    def test_formulario_do_ato_vem_preenchido(self):
        resposta = self.client.get(self.url_ato(0))

        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, 'dominial/lancamento_form.html')
        html = resposta.content.decode()
        self.assertIn('Revisão da extração · ato 1 de 3', html)
        self.assertIn('📄 Revisar Lançamento', html)
        self.assertRegex(html, r'<input[^>]*name="numero_lancamento_simples"[^>]*value="1"')
        self.assertRegex(html, r'<input[^>]*name="data"[^>]*value="2020-02-15"')
        self.assertRegex(
            html,
            r'<option value="%s"[^>]*selected' % self.tipo_registro.pk,
        )
        for nome in ('JOÃO DA SILVA', 'MARIA DA SILVA', 'PEDRO SANTOS'):
            self.assertIn(f'value="{nome}"', html)

    def test_sidebar_lista_os_atos_com_estado(self):
        html = self.client.get(self.url_ato(1)).content.decode()

        self.assertIn('ia-revisao-sidebar', html)
        for rotulo in ('1. R1', '2. Av1', '3. R2'):
            self.assertIn(rotulo, html)
        # Ato 2 em edição; os outros dois pendentes, com o destino da aba.
        self.assertEqual(html.count('ia-ato-pendente'), 2 + 1)  # 2 abas + css
        self.assertIn(f'data-ir-para="0"', html)
        self.assertIn(f'data-ir-para="2"', html)
        # O script do formulário cita a classe no seletor; nenhuma ABA a usa.
        self.assertNotRegex(html, r'class="[^"]*js-lancamento-resumo')

    def test_evidencias_e_js_so_na_revisao(self):
        html = self.client.get(self.url_ato(0)).content.decode()

        self.assertIn('id="ia-evidencias"', html)
        self.assertIn('ocr_revisao_formulario.js', html)
        self.assertIn('data-url-texto=', html)

    def test_nenhuma_chave_tecnica_na_tela(self):
        html = self.client.get(self.url_ato(0)).content.decode()
        banner = html[html.index('id="ia-revisao-banner"'):]
        banner = banner[:banner.index('</section>')]

        self.assertNotIn('/acts/', banner)

    def test_evidencia_vai_mascarada_para_o_json(self):
        CampoSugerido.objects.filter(
            extracao=self.extracao, chave='/acts/0/descricao',
        ).delete()
        CampoSugerido.objects.filter(
            extracao=self.extracao, chave='/acts/0/observacoes',
        ).delete()
        CampoSugerido.objects.filter(
            extracao=self.extracao, chave='/acts/0/data',
        ).update(evidencia_trecho='compra, CPF 123.456.789-00 em 15/02/2020')

        html = self.client.get(self.url_ato(0)).content.decode()

        self.assertNotIn('123.456.789-00', html)
        self.assertIn('CPF ***', html)

    def test_json_de_evidencias_traz_pagina_trecho_e_posicao_das_partes(self):
        html = self.client.get(self.url_ato(0)).content.decode()

        bruto = re.search(
            r'<script id="ia-evidencias" type="application/json">(.*?)</script>',
            html, re.S,
        ).group(1)
        evidencias = json.loads(bruto)

        self.assertEqual(evidencias['data'], {
            'pagina': 1, 'trecho': '15 de fevereiro de 2020',
            'confianca_baixa': False,
        })
        self.assertEqual(evidencias['transmitente_nome[1]']['trecho'], 'MARIA DA SILVA')
        self.assertEqual(evidencias['adquirente_nome[0]']['trecho'], 'PEDRO SANTOS')
        # Nada de chave técnica de linha como nome de campo.
        self.assertFalse([nome for nome in evidencias if '/' in nome])

    def test_novo_lancamento_manual_nao_tem_nada_da_revisao(self):
        resposta = self.client.get(reverse('novo_lancamento_documento', kwargs={
            'tis_id': self.imovel.terra_indigena_id.pk,
            'imovel_id': self.imovel.pk, 'documento_id': self.documento.pk,
        }))

        html = resposta.content.decode()
        self.assertEqual(resposta.status_code, 200)
        for marca in ('ia-evidencias', 'ia-revisao-sidebar', 'ia-revisao-banner',
                      'ocr_revisao_formulario.js', 'data-ir-para'):
            self.assertNotIn(marca, html)
        self.assertIn('lancamento-sidebar', html + 'lancamento-sidebar')

    def test_consultas_do_get_nao_crescem_com_o_numero_de_atos(self):
        with CaptureQueriesContext(connection) as com_tres:
            self.assertEqual(self.client.get(self.url_ato(0)).status_code, 200)
        payload = self._payload_de_tres_atos()
        payload['acts'] += deepcopy(payload['acts'])
        self.job.extracoes.all().delete()
        self.extracao = self._aberta(payload)

        with CaptureQueriesContext(connection) as com_seis:
            resposta = self.client.get(self.url_ato(0))

        self.assertEqual(resposta.status_code, 200)
        self.assertIn('ato 1 de 6', resposta.content.decode())
        self.assertEqual(len(com_seis), len(com_tres))

    def test_ato_inexistente_e_404(self):
        self.assertEqual(self.client.get(self.url_ato(9)).status_code, 404)

    def test_job_ainda_sem_extracao_volta_para_o_texto(self):
        self.job.status = 'concluido'
        self.job.save(update_fields=['status'])

        resposta = self.client.get(self.url_ato(0))

        self.assertRedirects(
            resposta, reverse('texto_job_ocr', kwargs=self.kwargs()),
            fetch_redirect_response=False,
        )

    def test_job_importado_volta_para_o_documento(self):
        self.job.status = 'importado'
        self.job.save(update_fields=['status'])

        resposta = self.client.get(self.url_entrada())

        self.assertRedirects(resposta, self.url_documento(), fetch_redirect_response=False)


class NadaGravaTest(RevisaoFormularioBase):
    def _escritas(self, consultas):
        return [
            consulta['sql'] for consulta in consultas
            if consulta['sql'].lstrip().upper().startswith(
                ('INSERT', 'UPDATE', 'DELETE'),
            )
        ]

    def test_get_e_navegacao_so_escrevem_na_sessao(self):
        antes = self.contagens()
        status_antes = self.job.status
        revisado_antes = list(
            CampoSugerido.objects.filter(extracao=self.extracao)
            .order_by('pk').values_list('pk', 'revisado_em', 'status_revisao'),
        )

        with CaptureQueriesContext(connection) as consultas:
            self.client.get(self.url_entrada())
            for indice in (0, 1, 2, 1, 0):
                resposta = self.client.get(self.url_ato(indice))
                self.assertEqual(resposta.status_code, 200)
            # Navegar com o que foi digitado: POST com ``_ir_para``.
            pagina = self.client.get(self.url_ato(0))
            navegacao = self.client.post(
                self.url_ato(0),
                post_do_html(pagina, _ir_para='2', observacoes='anotação minha'),
            )
            self.assertRedirects(
                navegacao, self.url_ato(2), fetch_redirect_response=False,
            )
            self.client.get(self.url_ato(2))

        escritas = self._escritas(consultas.captured_queries)
        self.assertTrue(escritas, 'o rascunho deve escrever a sessão')
        for sql in escritas:
            self.assertIn('django_session', sql)
        self.assertEqual(self.contagens(), antes)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, status_antes)
        self.assertEqual(
            list(
                CampoSugerido.objects.filter(extracao=self.extracao)
                .order_by('pk').values_list('pk', 'revisado_em', 'status_revisao'),
            ),
            revisado_antes,
        )

    def test_get_sozinho_nao_escreve_nem_a_sessao(self):
        with CaptureQueriesContext(connection) as consultas:
            self.client.get(self.url_ato(1))

        self.assertEqual(self._escritas(consultas.captured_queries), [])


class RascunhoTest(RevisaoFormularioBase):
    def test_edicao_sobrevive_a_ida_e_volta(self):
        pagina = self.client.get(self.url_ato(0))
        post = post_do_html(
            pagina, _ir_para='1', forma_transacao='Doação rascunhada',
            observacoes='nota do revisor',
        )
        # Segunda linha de origem digitada à mão: volta pelo mesmo caminho do
        # re-render de erro do formulário manual.
        post['origem_completa[]'] = ['M123', 'T45']
        post['cartorio_origem_nome[]'] = ['', '']
        post['cartorio_origem[]'] = ['', '']
        post['livro_origem[]'] = ['2', '3']
        post['folha_origem[]'] = ['10', '11']
        self.client.post(self.url_ato(0), post)

        self.client.get(self.url_ato(1))
        volta = self.client.get(self.url_ato(0))

        html = volta.content.decode()
        self.assertRegex(html, r'name="forma_transacao"[^>]*value="Doação rascunhada"')
        self.assertIn('nota do revisor', html)
        self.assertIn('value="M123"', html)
        self.assertIn('value="T45"', html)
        self.assertIn('Suas alterações não salvas deste ato foram restauradas.', html)

    def test_rascunho_e_por_ato(self):
        pagina = self.client.get(self.url_ato(0))
        self.client.post(
            self.url_ato(0), post_do_html(pagina, _ir_para='1', observacoes='só do ato 1'),
        )

        outro = self.client.get(self.url_ato(2)).content.decode()

        self.assertNotIn('só do ato 1', outro)

    def test_destino_invalido_fica_no_mesmo_ato(self):
        pagina = self.client.get(self.url_ato(0))

        resposta = self.client.post(
            self.url_ato(0), post_do_html(pagina, _ir_para='99'),
        )

        self.assertRedirects(resposta, self.url_ato(0), fetch_redirect_response=False)

    def test_rascunho_nao_guarda_o_token_csrf_nem_o_destino(self):
        pagina = self.client.get(self.url_ato(0))
        self.client.post(
            self.url_ato(0),
            {**post_do_html(pagina, _ir_para='1'), 'csrfmiddlewaretoken': 'x'},
        )

        guardado = self.client.session['ia_ocr_rascunhos'][str(self.extracao.pk)]['0']

        self.assertNotIn('csrfmiddlewaretoken', guardado)
        self.assertNotIn('_ir_para', guardado)

    def test_so_os_ultimos_documentos_ficam_na_sessao(self):
        from ia_ocr import revisao_ato

        sessao = self.client.session
        sessao[revisao_ato.CHAVE_SESSAO] = {
            str(numero): {'0': {'data': ['2020-01-01']}} for numero in (901, 902, 903)
        }
        sessao.save()

        pagina = self.client.get(self.url_ato(0))
        self.client.post(self.url_ato(0), post_do_html(pagina, _ir_para='1'))

        guardados = list(self.client.session[revisao_ato.CHAVE_SESSAO])
        self.assertEqual(guardados, ['902', '903', str(self.extracao.pk)])


class SalvarAtoTest(RevisaoFormularioBase):
    def test_salvar_grava_um_lancamento_com_os_campos_do_prefill(self):
        antes = self.contagens()

        resposta = self.salvar(0)

        self.assertRedirects(resposta, self.url_ato(1), fetch_redirect_response=False)
        depois = self.contagens()
        self.assertEqual(depois['Lancamento'] - antes['Lancamento'], 1)
        lancamento = Lancamento.objects.get(documento=self.documento)
        self.assertEqual(lancamento.tipo, self.tipo_registro)
        self.assertEqual(lancamento.numero_lancamento, 'R1 M237')
        self.assertEqual(str(lancamento.data), '2020-02-15')
        self.assertEqual(str(lancamento.area), '12.5000')
        self.assertEqual(
            sorted(lancamento.pessoas.values_list('tipo', 'nome_digitado')),
            [
                ('adquirente', 'PEDRO SANTOS'),
                ('transmitente', 'JOÃO DA SILVA'),
                ('transmitente', 'MARIA DA SILVA'),
            ],
        )

    def test_vinculo_de_auditoria_no_formato_da_importacao(self):
        self.salvar(0)

        lancamento = Lancamento.objects.get(documento=self.documento)
        vinculo = ImportacaoIA.objects.get(modelo='Lancamento')
        self.assertEqual(vinculo.objeto_id, lancamento.pk)
        self.assertEqual(vinculo.lancamento, lancamento)
        self.assertEqual(vinculo.campo.chave, '/acts/0')
        self.assertEqual(vinculo.ocr_job, self.job)
        self.assertEqual(vinculo.criado_por, self.usuario)
        pessoas = ImportacaoIA.objects.filter(modelo='LancamentoPessoa')
        self.assertEqual(pessoas.count(), 3)
        self.assertEqual(
            sorted(pessoas.values_list('campo__chave', flat=True)),
            ['/acts/0/partes/0', '/acts/0/partes/1', '/acts/0/partes/2'],
        )

    def test_linhas_do_ato_ficam_importadas_e_as_outras_nao(self):
        self.salvar(0)

        status = dict(CampoSugerido.objects.filter(
            extracao=self.extracao, chave__in=('/acts/0/data', '/acts/1/data'),
        ).values_list('chave', 'status_revisao'))
        self.assertEqual(status, {
            '/acts/0/data': 'importado', '/acts/1/data': 'sugerido',
        })

    def test_segundo_ato_continua_pendente_e_a_sidebar_reflete(self):
        self.salvar(0)

        resposta = self.client.get(self.url_ato(1))

        html = resposta.content.decode()
        self.assertIn('ato 2 de 3', html)
        self.assertIn('1 de 3 salvo', html)
        self.assertIn('✔ salvo', html)
        lancamento = Lancamento.objects.get(documento=self.documento)
        self.assertIn(
            reverse('editar_lancamento', kwargs={
                'tis_id': self.imovel.terra_indigena_id.pk,
                'imovel_id': self.imovel.pk, 'lancamento_id': lancamento.pk,
            }),
            html,
        )
        self.assertEqual(Lancamento.objects.count(), 1)

    def test_job_vira_revisado_no_primeiro_ato(self):
        self.salvar(0)

        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'revisado')
        self.assertTrue(OcrJobTransicao.objects.filter(
            ocr_job=self.job, para_status='revisado', motivo='revisao_formulario',
        ).exists())

    def test_ato_fora_de_ordem_e_permitido(self):
        resposta = self.salvar(2)

        # Depois do último, a volta ao primeiro pendente.
        self.assertRedirects(resposta, self.url_ato(0), fetch_redirect_response=False)
        self.assertEqual(
            ImportacaoIA.objects.get(modelo='Lancamento').campo.chave, '/acts/2',
        )
        self.assertEqual(
            Lancamento.objects.get(documento=self.documento).numero_lancamento,
            'R2 M237',
        )

    def test_ultimo_ato_conclui_a_revisao(self):
        self.salvar(2)
        self.salvar(0)
        resposta = self.salvar(1)

        self.assertRedirects(resposta, self.url_documento(), fetch_redirect_response=False)
        self.assertIn(
            '✅ Revisão concluída: todos os atos desta extração foram resolvidos.',
            self.mensagens(resposta),
        )
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'importado')
        self.assertEqual(Lancamento.objects.filter(documento=self.documento).count(), 3)
        # E a entrada da revisão passa a levar ao documento.
        self.assertRedirects(
            self.client.get(self.url_entrada()), self.url_documento(),
            fetch_redirect_response=False,
        )

    def test_salvar_limpa_o_rascunho_do_ato(self):
        pagina = self.client.get(self.url_ato(0))
        self.client.post(self.url_ato(0), post_do_html(pagina, _ir_para='1'))
        self.assertIn('0', self.client.session['ia_ocr_rascunhos'][str(self.extracao.pk)])

        self.salvar(0)

        self.assertNotIn(
            str(self.extracao.pk), self.client.session.get('ia_ocr_rascunhos', {}),
        )

    def test_get_de_ato_salvo_vai_para_a_edicao_do_lancamento(self):
        self.salvar(0)

        resposta = self.client.get(self.url_ato(0))

        lancamento = Lancamento.objects.get(documento=self.documento)
        self.assertRedirects(
            resposta,
            reverse('editar_lancamento', kwargs={
                'tis_id': self.imovel.terra_indigena_id.pk,
                'imovel_id': self.imovel.pk, 'lancamento_id': lancamento.pk,
            }),
            fetch_redirect_response=False,
        )


class AreaEmOutraUnidadeSalvarTest(RevisaoFormularioBase):
    """M3: área não-ha exige uma decisão explícita no POST que salva o ato."""

    def setUp(self):
        super().setUp()
        payload = self._payload_de_tres_atos()
        payload['acts'] = [payload['acts'][0]]
        payload['acts'][0]['area'] = {
            **self._campo('120.00', 'área construída 120,00 m2'),
            'unidade': 'm2',
            'raw': '120,00 m2',
        }
        self.job.extracoes.all().delete()
        self.extracao = self._aberta(payload)

    def test_area_preenchida_em_hectares_salva_e_importa_o_ato(self):
        resposta = self.salvar(0, area='0.012')

        self.assertRedirects(
            resposta, self.url_documento(), fetch_redirect_response=False,
        )
        lancamento = Lancamento.objects.get(documento=self.documento)
        self.assertEqual(str(lancamento.area), '0.0120')
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'importado')

    def test_descarte_explicito_salva_sem_area_e_importa_o_ato(self):
        resposta = self.salvar(0, area='', descartar_area='1')

        self.assertRedirects(
            resposta, self.url_documento(), fetch_redirect_response=False,
        )
        lancamento = Lancamento.objects.get(documento=self.documento)
        self.assertIsNone(lancamento.area)
        campo = self.extracao.campos.get(chave='/acts/0/area')
        self.assertEqual(campo.status_revisao, 'importado')
        self.assertFalse(campo.area_convertida)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'importado')

    def test_sem_area_nem_descarte_volta_com_erro_e_nao_grava(self):
        antes = self.contagens()

        resposta = self.salvar(0, area='')

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(self.contagens(), antes)
        self.assertFalse(
            Lancamento.objects.filter(documento=self.documento).exists(),
        )
        self.assertFalse(ImportacaoIA.objects.filter(ocr_job=self.job).exists())
        self.assertIn(
            'A área foi lida em unidade diferente de hectare',
            ' '.join(self.mensagens(resposta)),
        )
        html = resposta.content.decode()
        self.assertRegex(
            html,
            r'name="descartar_area"[^>]*form="lancamento-form"',
        )
        self.assertIn('Área lida em m², descartada pelo revisor.', html)
        campo = self.extracao.campos.get(chave='/acts/0/area')
        self.assertEqual(campo.status_revisao, 'sugerido')
        self.assertFalse(campo.area_convertida)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'extraido')


class DuplicataTest(RevisaoFormularioBase):
    def test_salvar_duas_vezes_grava_um_lancamento_so(self):
        pagina = self.client.get(self.url_ato(0))
        post = post_do_html(pagina)

        self.client.post(self.url_ato(0), post)
        segunda = self.client.post(self.url_ato(0), post)

        self.assertEqual(Lancamento.objects.filter(documento=self.documento).count(), 1)
        self.assertEqual(ImportacaoIA.objects.filter(modelo='Lancamento').count(), 1)
        self.assertIn(
            'Este ato já foi salvo como lançamento. Nada foi gravado de novo.',
            self.mensagens(segunda),
        )

    def test_numero_repetido_e_barrado_pelo_service_do_formulario(self):
        # Lançamento criado fora da revisão com o MESMO número: quem recusa
        # é a regra do service manual, não uma checagem nova da revisão.
        Lancamento.objects.create(
            documento=self.documento, tipo=self.tipo_registro,
            numero_lancamento='R1 M237', data='2019-01-01',
        )
        antes = self.contagens()

        resposta = self.salvar(0, observacoes='o que eu digitei')

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(self.contagens(), antes)
        self.assertTrue(any(
            'Já existe um lançamento com o número' in texto
            for texto in self.mensagens(resposta)
        ))
        html = resposta.content.decode()
        self.assertIn('data-numero-lancamento-error="true"', html)
        self.assertIn('o que eu digitei', html)
        self.assertIn('Revisão da extração · ato 1 de 3', html)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'extraido')

    def test_erro_do_service_preserva_a_digitacao_e_nao_grava(self):
        antes = self.contagens()

        resposta = self.salvar(
            0, tipo_lancamento='', observacoes='texto digitado',
            numero_lancamento_simples='7',
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(self.contagens(), antes)
        self.assertIn('Tipo de lançamento é obrigatório', self.mensagens(resposta))
        html = resposta.content.decode()
        self.assertIn('texto digitado', html)
        self.assertRegex(html, r'name="numero_lancamento_simples"[^>]*value="7"')
        self.assertIn('JOÃO DA SILVA', html)

    def test_erro_interno_nao_vaza_e_nao_deixa_gravar_pela_metade(self):
        from unittest import mock

        antes = self.contagens()
        with mock.patch(
            'ia_ocr.revisao_ato.importacao._vincular', side_effect=RuntimeError('falhou'),
        ), self.assertLogs('ia_ocr.views', level='ERROR'):
            resposta = self.salvar(0)

        self.assertEqual(resposta.status_code, 200)
        # O lançamento criado antes da falha foi desfeito junto: nada de ato
        # "salvo" sem o vínculo da auditoria.
        self.assertEqual(self.contagens(), antes)
        self.assertNotIn('falhou', resposta.content.decode())
        self.assertIn('❌ Erro interno ao salvar o ato. Tente novamente.', self.mensagens(resposta))

    def test_duplicata_de_origem_nao_cria_nada_nem_perde_a_digitacao(self):
        from unittest import mock

        info = {'tipo': 'duplicata_encontrada', 'duplicata_info': {}}
        antes = self.contagens()
        with mock.patch(
            'ia_ocr.revisao_ato.LancamentoService.criar_lancamento_completo',
            return_value=(info, 'Origem já existe em outra cadeia.'),
        ):
            resposta = self.salvar(0, observacoes='digitado antes')

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(self.contagens(), antes)
        self.assertIn('digitado antes', resposta.content.decode())
        self.assertTrue(any('já existe em outra cadeia' in t for t in self.mensagens(resposta)))


class ExtracaoTrocadaTest(RevisaoFormularioBase):
    """M2 (#341): POST de página renderizada sobre outra extração não grava.

    A reextração troca a vigente no meio da revisão; o navegador segue com o
    formulário da ANTIGA aberto. Sem o hidden ``extracao_id`` validado sob
    trava, o POST gravava os dados da extração antiga e marcava como
    importado o ato da MESMA posição na nova.
    """

    def _reextrair(self):
        """Extração nova (R9) no lugar da vigente, como a reextração faria."""
        payload = self._payload_de_tres_atos()
        payload['acts'][0]['rotulo'] = self._campo('R-9', 'R-9/M237')
        payload['acts'][0]['observacoes'] = self._campo(
            'lido pela reextração', 'reextraído',
        )
        return self._aberta(payload)

    def test_post_da_pagina_antiga_nao_grava_nem_marca_ato_da_extracao_nova(self):
        pagina = self.client.get(self.url_ato(0))
        post = post_do_html(pagina)
        self.assertEqual(post['extracao_id'], [str(self.extracao.pk)])
        nova = self._reextrair()
        antes = self.contagens()

        resposta = self.client.post(self.url_ato(0), post)

        self.assertRedirects(
            resposta, self.url_entrada(), fetch_redirect_response=False,
        )
        self.assertTrue(any(
            'A extração deste documento mudou' in texto
            for texto in self.mensagens(resposta)
        ))
        self.assertEqual(self.contagens(), antes)
        # O ato 0 da extração NOVA segue pendente — nada marcado como importado.
        from ia_ocr import revisao_ato

        atos = revisao_ato.atos_da_revisao(nova)
        self.assertEqual(atos[0]['estado'], revisao_ato.ESTADO_PENDENTE)
        self.assertEqual(
            CampoSugerido.objects.filter(
                extracao=nova, status_revisao='importado',
            ).count(),
            0,
        )

    def test_save_revalida_hidden_dentro_da_transacao_autoritativa(self):
        """Mesmo se a checagem preliminar não vir a troca, o save recusa."""
        from unittest import mock

        pagina = self.client.get(self.url_ato(0))  # HTML da R1
        post = post_do_html(pagina)
        nova = self._reextrair()  # vigente agora começa por R9
        antes = self.contagens()

        # Simula a janela entre a guarda preliminar e o save. Sem a validação
        # do hidden dentro de ``revisao_ato.salvar_ato``, os dados R1 seriam
        # gravados e o ato R9 da extração nova seria marcado como importado.
        with mock.patch(
            'ia_ocr.views._extracao_trocada_no_post', return_value=None,
        ):
            resposta = self.client.post(self.url_ato(0), post)

        self.assertRedirects(
            resposta, self.url_entrada(), fetch_redirect_response=False,
        )
        self.assertTrue(any(
            'A extração deste documento mudou' in texto
            for texto in self.mensagens(resposta)
        ))
        self.assertEqual(self.contagens(), antes)
        self.assertEqual(
            CampoSugerido.objects.filter(
                extracao=nova, status_revisao='importado',
            ).count(),
            0,
        )

    def test_navegacao_guarda_rascunho_dentro_da_transacao_da_trava(self):
        """A trava não pode ser solta entre validar o hidden e o rascunho."""
        from unittest import mock

        from ia_ocr import revisao_ato

        pagina = self.client.get(self.url_ato(0))
        profundidade_externa = len(connection.atomic_blocks)
        profundidades = []
        guardar_real = revisao_ato.guardar_rascunho

        def observar_transacao(*args, **kwargs):
            profundidades.append(len(connection.atomic_blocks))
            return guardar_real(*args, **kwargs)

        with mock.patch.object(
            revisao_ato, 'guardar_rascunho', side_effect=observar_transacao,
        ):
            resposta = self.client.post(self.url_ato(0), post_do_html(
                pagina, _ir_para='1', observacoes='rascunho atual',
            ))

        self.assertRedirects(
            resposta, self.url_ato(1), fetch_redirect_response=False,
        )
        self.assertEqual(len(profundidades), 1)
        self.assertGreater(profundidades[0], profundidade_externa)

    def test_navegacao_da_pagina_antiga_nao_guarda_rascunho(self):
        pagina = self.client.get(self.url_ato(0))
        self._reextrair()

        resposta = self.client.post(self.url_ato(0), post_do_html(
            pagina, _ir_para='1', observacoes='digitado na página antiga',
        ))

        self.assertRedirects(
            resposta, self.url_entrada(), fetch_redirect_response=False,
        )
        # O digitado era da extração antiga: nada guardado na sessão — nem
        # sob a nova (onde envenenaria o ato 0), nem sob a antiga.
        self.assertEqual(self.client.session.get('ia_ocr_rascunhos') or {}, {})

    def test_post_sem_a_identidade_da_extracao_e_recusado(self):
        pagina = self.client.get(self.url_ato(0))
        post = post_do_html(pagina)
        del post['extracao_id']
        antes = self.contagens()

        resposta = self.client.post(self.url_ato(0), post)

        self.assertRedirects(
            resposta, self.url_entrada(), fetch_redirect_response=False,
        )
        self.assertTrue(any(
            'A extração deste documento mudou' in texto
            for texto in self.mensagens(resposta)
        ))
        self.assertEqual(self.contagens(), antes)

    def test_post_da_pagina_da_extracao_atual_salva_normalmente(self):
        nova = self._reextrair()

        pagina = self.client.get(self.url_ato(0))
        post = post_do_html(pagina)
        self.assertEqual(post['extracao_id'], [str(nova.pk)])

        resposta = self.client.post(self.url_ato(0), post)

        self.assertEqual(resposta.status_code, 302, self.mensagens(resposta))
        self.assertEqual(
            Lancamento.objects.filter(documento=self.documento).count(), 1,
        )


class RollbackDoErroInternoTest(RevisaoFormularioBase):
    """M4 (#341): depois do rollback, o livro/folha falsamente definidos somem."""

    def test_re_render_do_erro_interno_nao_trava_livro_que_o_banco_nao_tem(self):
        from unittest import mock

        pagina = self.client.get(self.url_ato(0))
        self.documento.refresh_from_db()
        self.assertEqual(self.documento.livro, '')

        with mock.patch(
            'ia_ocr.revisao_ato.importacao._vincular', side_effect=RuntimeError('falhou'),
        ), self.assertLogs('ia_ocr.views', level='ERROR'):
            resposta = self.client.post(
                self.url_ato(0), post_do_html(pagina, livro_documento='99'),
            )

        self.assertEqual(resposta.status_code, 200)
        # O banco voltou ao estado anterior (rollback)…
        self.documento.refresh_from_db()
        self.assertEqual(self.documento.livro, '')
        # …e a tela também: o input segue editável e com o que foi digitado,
        # não travado (disabled) com o '99' que só existia em memória.
        html = resposta.content.decode()
        entrada = re.search(r'<input[^>]*name="livro_documento"[^>]*>', html).group(0)
        self.assertNotIn('disabled', entrada)
        self.assertIn('value="99"', entrada)


class PermissaoTest(RevisaoFormularioBase):
    def setUp(self):
        super().setUp()
        self.intruso = User.objects.create_user(username='intruso-revisao')

    def test_sem_acesso_recebe_404_no_get_e_no_post(self):
        self.client.force_login(self.intruso)
        antes = self.contagens()

        for url in (self.url_entrada(), self.url_ato(0)):
            self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(self.url_ato(0), {'tipo_lancamento': '1'}).status_code, 404)
        self.assertEqual(
            self.client.post(self.url_ato(0), {'_ir_para': '1'}).status_code, 404,
        )

        self.assertEqual(self.contagens(), antes)
        self.assertNotIn('ia_ocr_rascunhos', self.client.session)

    def test_ti_de_outro_documento_recebe_404(self):
        outro = criar_documento_digital(upload_por=self.usuario)
        UserTI.objects.create(
            user=self.usuario, tis=outro.documento.imovel.terra_indigena_id,
        )
        url = reverse('revisar_ato_ocr', kwargs={
            'tis_id': outro.documento.imovel.terra_indigena_id.pk,
            'imovel_id': outro.documento.imovel.pk,
            'documento_id': outro.documento.pk,
            'job_id': self.job.job_id, 'indice': 0,
        })

        self.assertEqual(self.client.get(url).status_code, 404)

    def test_anonimo_vai_para_o_login(self):
        self.client.logout()

        resposta = self.client.get(self.url_ato(0))

        self.assertEqual(resposta.status_code, 302)
        self.assertIn('login', resposta['Location'])

    def test_metodo_nao_permitido(self):
        self.assertEqual(self.client.put(self.url_ato(0)).status_code, 405)
        self.assertEqual(self.client.post(self.url_entrada()).status_code, 405)


class OrigemComPontoTest(RevisaoFormularioBase):
    """O OCR traz ``42.718``; o campo visível e o POST não podem perdê-lo."""

    def setUp(self):
        super().setUp()
        self.cartorio_origem = self._cartorio('CRI da Origem Pontuada')
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['origem'] = {
            'tipo_documento': self._campo('matricula', 'MATRÍCULA Nº 42.718'),
            'numero': self._campo('M42.718', '42.718'),
            'cartorio': self._campo('CRI da Origem', 'CRI de Guaíra'),
            'livro': self._campo('2', 'Livro 2-RG'),
            'folha': self._campo('123', 'Folha 087'),
        }
        self.job.extracoes.all().delete()
        self.extracao = self._aberta(payload)
        self.extracao.campos.filter(chave='/acts/0/origem/cartorio').update(
            cartorio_escolhido=self.cartorio_origem,
        )

    def test_numero_com_ponto_aparece_inteiro_no_input_e_no_texto_oculto(self):
        html = self.client.get(self.url_ato(0)).content.decode()

        self.assertRegex(html, r'<input[^>]*name="numero_origem_0"[^>]*value="42.718"')
        self.assertRegex(
            html, r'name="origem_completa\[\]"[^>]*value="M42.718"',
        )

    def test_pattern_e_maxlength_aceitam_o_numero_com_ponto(self):
        html = self.client.get(self.url_ato(0)).content.decode()
        entrada = re.search(r'<input[^>]*name="numero_origem_0"[^>]*>', html).group(0)

        padrao = re.search(r'pattern="([^"]*)"', entrada).group(1)
        limite = int(re.search(r'maxlength="(\d+)"', entrada).group(1))

        self.assertTrue(re.fullmatch(padrao, '42.718'))
        self.assertTrue(re.fullmatch(padrao, '366'))
        self.assertFalse(re.fullmatch(padrao, '42.'))
        self.assertFalse(re.fullmatch(padrao, 'abc'))
        self.assertGreaterEqual(limite, len('12.345.678'))

    def test_pattern_vale_tambem_para_a_origem_em_branco_do_formulario_manual(self):
        resposta = self.client.get(reverse('novo_lancamento_documento', kwargs={
            'tis_id': self.imovel.terra_indigena_id.pk,
            'imovel_id': self.imovel.pk, 'documento_id': self.documento.pk,
        }))

        self.assertIn('pattern="[0-9]+([.][0-9]+)*"', resposta.content.decode())

    def test_o_post_leva_o_numero_com_ponto_e_o_lancamento_guarda(self):
        resposta = self.salvar(0)

        self.assertEqual(resposta.status_code, 302)
        lancamento = Lancamento.objects.get(documento=self.documento)
        self.assertEqual(lancamento.origem, 'M42.718')
        self.assertEqual(
            list(LancamentoOrigem.objects.filter(lancamento=lancamento)
                 .values_list('numero_normalizado', flat=True)),
            ['42.718'],
        )

    def test_origem_estruturada_entra_na_auditoria_com_a_linha_da_origem(self):
        self.salvar(0)

        vinculo = ImportacaoIA.objects.get(modelo='LancamentoOrigem')
        self.assertEqual(vinculo.campo.chave, '/acts/0/origem/numero')
        self.assertEqual(
            vinculo.objeto_id,
            Lancamento.objects.get(documento=self.documento)
            .origens_estruturadas.get().pk,
        )

    def test_rascunho_e_re_render_de_erro_mantem_o_numero_inteiro(self):
        resposta = self.salvar(0, tipo_lancamento='')

        html = resposta.content.decode()
        self.assertRegex(html, r'<input[^>]*name="numero_origem_0"[^>]*value="42.718"')
        self.assertRegex(html, r'name="origem_completa\[\]"[^>]*value="M42.718"')


class OrigemAcrescentadaANaoTest(OrigemComPontoTest):
    """N1 (#341): TODAS as origens persistidas ganham vínculo de auditoria.

    O ``.first()`` auditava só a primeira — com a origem lida MAIS uma
    acrescentada no formulário, a segunda nascia sem ``ImportacaoIA``.
    """

    def test_origem_acrescentada_a_mao_tambem_recebe_vinculo(self):
        segunda = self._cartorio('CRI da Segunda Origem')
        pagina = self.client.get(self.url_ato(0))
        post = post_do_html(pagina)
        post['origem_completa[]'] = post['origem_completa[]'] + ['T366']
        post['cartorio_origem_nome[]'] = (
            post['cartorio_origem_nome[]'] + [segunda.nome]
        )
        post['cartorio_origem[]'] = post['cartorio_origem[]'] + [str(segunda.pk)]
        post['livro_origem[]'] = post.get('livro_origem[]', ['']) + ['']
        post['folha_origem[]'] = post.get('folha_origem[]', ['']) + ['']

        resposta = self.client.post(self.url_ato(0), post)

        self.assertEqual(resposta.status_code, 302, self.mensagens(resposta))
        lancamento = Lancamento.objects.get(documento=self.documento)
        origens = list(
            lancamento.origens_estruturadas.order_by('indice_origem')
        )
        self.assertEqual([origem.numero for origem in origens], ['M42.718', 'T366'])

        vinculos = ImportacaoIA.objects.filter(modelo='LancamentoOrigem')
        # Uma por origem persistida — nenhuma fica sem vínculo.
        self.assertEqual(
            set(vinculos.values_list('objeto_id', flat=True)),
            {origem.pk for origem in origens},
        )
        # Só a origem que o OCR leu carrega a linha dela; a digitada à mão
        # não vem de linha nenhuma.
        lida = vinculos.get(objeto_id=origens[0].pk)
        self.assertEqual(lida.campo.chave, '/acts/0/origem/numero')
        manual = vinculos.get(objeto_id=origens[1].pk)
        self.assertIsNone(manual.campo)

    def test_origem_extraida_editada_mantem_a_linha_e_manual_nao_a_herda(self):
        segunda = self._cartorio('Cartório Manual com Valor Antigo')
        pagina = self.client.get(self.url_ato(0))
        post = post_do_html(pagina)
        # A linha zero veio do OCR, mas o revisor corrigiu M42.718 para T777.
        # A segunda foi acrescentada à mão e reutiliza o texto OCR antigo.
        post['origem_completa[]'][0] = 'T777'
        post['origem_completa[]'].append('M42.718')
        post['cartorio_origem_nome[]'].append(segunda.nome)
        post['cartorio_origem[]'].append(str(segunda.pk))
        post['livro_origem[]'] = post.get('livro_origem[]', ['']) + ['']
        post['folha_origem[]'] = post.get('folha_origem[]', ['']) + ['']

        resposta = self.client.post(self.url_ato(0), post)

        self.assertEqual(resposta.status_code, 302, self.mensagens(resposta))
        origens = list(
            Lancamento.objects.get(documento=self.documento)
            .origens_estruturadas.order_by('indice_origem')
        )
        self.assertEqual([origem.numero for origem in origens], ['T777', 'M42.718'])
        vinculos = ImportacaoIA.objects.filter(modelo='LancamentoOrigem')
        self.assertEqual(
            set(vinculos.values_list('objeto_id', flat=True)),
            {origem.pk for origem in origens},
        )
        extraida = vinculos.get(objeto_id=origens[0].pk)
        self.assertEqual(extraida.campo.chave, '/acts/0/origem/numero')
        manual = vinculos.get(objeto_id=origens[1].pk)
        self.assertIsNone(manual.campo)


class ParidadeComOFormularioManualTest(RevisaoFormularioBase):
    """O HTML da revisão, enviado como o navegador envia, grava o mesmo que o manual.

    O POST sai do HTML renderizado da revisão (prova que o template emite os
    nomes certos) e vai, com o mesmo corpo, para o ``novo_lancamento`` e para
    a revisão — um depois do outro no MESMO documento, com a limpeza entre
    eles. Só pode diferir o vínculo de auditoria (``ImportacaoIA``).
    """

    def setUp(self):
        super().setUp()
        cartorio = self._cartorio('CRI da Origem da Paridade')
        payload = self._payload_de_tres_atos()
        payload['acts'][0]['origem'] = {
            'tipo_documento': self._campo('matricula', 'MATRÍCULA Nº 42.718'),
            'numero': self._campo('M42.718', '42.718'),
            'cartorio': self._campo('CRI da Origem', 'CRI de Guaíra'),
            'livro': self._campo('2', 'Livro 2-RG'),
            'folha': self._campo('123', 'Folha 087'),
        }
        payload['acts'][0].update(
            forma=self._campo('Compra e Venda', 'Compra e Venda'),
            titulo=self._campo('Escritura Pública', 'Escritura Pública'),
            livro_transacao=self._campo('10-A', 'Livro 2-RG'),
            folha_transacao=self._campo('25v', 'Folha 087'),
            data_transacao=self._campo('2019-12-20', '10 de janeiro de 2020'),
            observacoes=self._campo('Observação lida', 'Observação lida'),
        )
        self.job.extracoes.all().delete()
        self.extracao = self._aberta(payload)
        self.extracao.campos.filter(chave='/acts/0/origem/cartorio').update(
            cartorio_escolhido=cartorio,
        )
        self.url_manual = reverse('novo_lancamento_documento', kwargs={
            'tis_id': self.imovel.terra_indigena_id.pk,
            'imovel_id': self.imovel.pk, 'documento_id': self.documento.pk,
        })

    def _fotografia(self):
        lancamento = Lancamento.objects.get(documento=self.documento)
        campos = {
            campo.attname: getattr(lancamento, campo.attname)
            for campo in Lancamento._meta.concrete_fields
            if campo.name not in ('id', 'documento')
            and not getattr(campo, 'auto_now', False)
            and not getattr(campo, 'auto_now_add', False)
        }
        return {
            'campos': campos,
            'pessoas': sorted(lancamento.pessoas.values_list(
                'tipo', 'nome_digitado', 'pessoa__nome',
            )),
            'origens': sorted(lancamento.origens_estruturadas.values_list(
                'tipo_documento', 'numero_normalizado', 'cartorio_id',
                'livro', 'folha',
            )),
            'documentos_criados': sorted(
                (doc.tipo.tipo, doc.numero, doc.cartorio_id, doc.livro, doc.folha)
                for doc in Documento.objects.filter(imovel=self.imovel)
                .exclude(pk=self.documento.pk).select_related('tipo')
            ),
            'documento': Documento.objects.values_list('livro', 'folha').get(
                pk=self.documento.pk,
            ),
        }

    def _limpar(self):
        Lancamento.objects.filter(documento=self.documento).delete()
        Documento.objects.filter(imovel=self.imovel).exclude(
            pk=self.documento.pk,
        ).delete()
        Documento.objects.filter(pk=self.documento.pk).update(livro='', folha='')

    def _comparar(self, indice):
        post = post_do_html(self.client.get(self.url_ato(indice)))

        manual = self.client.post(self.url_manual, post)
        self.assertEqual(manual.status_code, 302, self.mensagens(manual))
        fotografia_manual = self._fotografia()
        self.assertEqual(ImportacaoIA.objects.count(), 0)
        self._limpar()

        revisao = self.client.post(self.url_ato(indice), post)
        self.assertEqual(revisao.status_code, 302, self.mensagens(revisao))
        fotografia_revisao = self._fotografia()

        self.assertEqual(fotografia_revisao, fotografia_manual)
        self.assertTrue(ImportacaoIA.objects.filter(
            modelo='Lancamento',
            lancamento=Lancamento.objects.get(documento=self.documento),
        ).exists())
        return fotografia_revisao

    def test_registro_com_origem_transmissao_e_partes(self):
        fotografia = self._comparar(0)

        campos = fotografia['campos']
        self.assertEqual(campos['numero_lancamento'], 'R1 M237')
        self.assertEqual(campos['forma'], 'Compra e Venda')
        self.assertEqual(campos['titulo'], 'Escritura Pública')
        self.assertEqual(campos['livro_transacao'], '10-A')
        self.assertEqual(campos['origem'], 'M42.718')
        self.assertEqual(len(fotografia['pessoas']), 3)
        self.assertEqual(len(fotografia['origens']), 1)

    def test_averbacao_com_descricao(self):
        fotografia = self._comparar(1)

        campos = fotografia['campos']
        self.assertEqual(campos['numero_lancamento'], 'AV1 M237')
        self.assertEqual(campos['descricao'], 'averbação de construção de casa sede')
        self.assertEqual(fotografia['pessoas'], [])


class CartorioDaTransmissaoTest(RevisaoFormularioBase):
    """O nome lido pelo OCR nunca vira cartório novo pelo fluxo da revisão."""

    def _com_transmissao(self, nome):
        payload = self._payload_de_tres_atos()
        payload['acts'][0]['cartorio_transmissao'] = self._campo(nome, nome)
        self.job.extracoes.all().delete()
        self.extracao = self._aberta(payload)

    def test_nome_sem_cadastro_e_recusado_sem_criar_cartorio(self):
        self._com_transmissao('Cartório Inventado pelo OCR')
        antes = self.contagens()

        resposta = self.salvar(0, observacoes='digitado')

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(self.contagens(), antes)
        self.assertFalse(
            Cartorios.objects.filter(nome='Cartório Inventado pelo OCR').exists(),
        )
        self.assertTrue(any(
            "'Cartório Inventado pelo OCR' não está cadastrado" in texto
            for texto in self.mensagens(resposta)
        ))
        html = resposta.content.decode()
        self.assertIn('digitado', html)
        self.assertRegex(
            html, r'name="cartorio_transmissao_nome"[^>]*value="Cartório Inventado pelo OCR"',
        )

    def test_cartorio_escolhido_grava_o_do_cadastro(self):
        cartorio = self._cartorio('Cartório Cadastrado da Transmissão')
        self._com_transmissao('CRI de Guaíra')
        self.extracao.campos.filter(chave='/acts/0/cartorio_transmissao').update(
            cartorio_escolhido=cartorio,
        )
        antes = Cartorios.objects.count()

        resposta = self.salvar(0)

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(Cartorios.objects.count(), antes)
        lancamento = Lancamento.objects.get(documento=self.documento)
        self.assertEqual(lancamento.cartorio_transmissao_id, cartorio.pk)

    def test_nome_que_ja_existe_no_cadastro_segue_sem_criar_outro(self):
        # Só a caixa difere, em ASCII: o ``iexact`` do SQLite dos testes não
        # dobra a caixa de letra acentuada (o Postgres de produção dobra).
        existente = self._cartorio('Cartorio Que Ja Existe')
        self._com_transmissao('CARTORIO QUE JA EXISTE')
        antes = Cartorios.objects.count()

        resposta = self.salvar(0)

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(Cartorios.objects.count(), antes)
        self.assertEqual(
            Lancamento.objects.get(documento=self.documento).cartorio_transmissao_id,
            existente.pk,
        )
