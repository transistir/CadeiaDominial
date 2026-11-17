"""Tela de revisão de campos (I-5): render, escape, pendências e somente leitura."""

import copy
import json
import re

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.shortcuts import resolve_url
from django.template.loader import render_to_string
from django.test import SimpleTestCase, override_settings
from django.test.html import Element, parse_html
from django.utils import timezone

from dominial.models import Cartorios, LancamentoTipo, Pessoas
from ia_ocr import estados, revisao, rotulos, services, views
from ia_ocr.models import CampoSugerido, ExtracaoSugerida, OcrJob
from ia_ocr.revisao import IndiceCartorios, IndicePessoas, enriquecer_payload

from .base_texto import TelaTextoBase
from .payloads_extracao import (
    PROVIDER, SCHEMA_VERSION, TEXTO_PAGINA_1, _campo, payload_averbacao,
    payload_com_closure,
    payload_registro,
)
from .test_ui_card_ocr import _atributos, _elementos

RAW_MALICIOSO = '<script>alert(1)</script>"><img onerror=1>'


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


class RevisaoTelaTest(TelaRevisaoBase):
    def _botao_finalizar(self, resposta):
        html = resposta.content.decode()
        botao = re.search(r'<button[^>]*data-ocr-finalizar[^>]*>', html)
        self.assertIsNotNone(botao)
        return botao.group(0)

    @staticmethod
    def _valor_do_card(html, chave):
        card = next(
            card for card in _elementos(
                html, 'article', presentes=('data-campo',),
            )
            if _atributos(card)['data-chave'] == chave
        )
        for tag in ('input', 'textarea', 'select'):
            elementos = _descendentes(card, tag, 'data-campo-valor')
            if not elementos:
                continue
            elemento = elementos[0]
            if tag == 'input':
                return _atributos(elemento).get('value', '')
            if tag == 'select':
                return _valor_do_select(elemento)
            return ''.join(
                filho for filho in elemento.children if isinstance(filho, str)
            )
        return None

    def test_tela_exige_extraido(self):
        self._extracao()
        OcrJob.objects.filter(pk=self.job.pk).update(status=estados.CONCLUIDO)

        resposta = self._tela()

        self.assertRedirects(resposta, self.url_tela(), fetch_redirect_response=False)
        self.assertTrue(self.mensagens(resposta))

    def test_tela_renderiza_campos_e_versao(self):
        extracao = self._extracao()

        resposta = self._tela()

        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, 'ia_ocr/revisao_campos.html')
        self.assertContains(resposta, 'data-ocr-revisao')
        self.assertContains(resposta, f'data-versao="{resposta.context["versao"]}"')
        self.assertContains(resposta, ' data-campo\n', count=extracao.campos.count())
        self.assertContains(resposta, '← Voltar ao processamento')

    def test_tela_escapa_texto_do_ocr(self):
        payload = payload_averbacao(self.job.job_id)
        payload['document']['numero']['raw'] = RAW_MALICIOSO
        self._extracao(payload)

        resposta = self._tela()

        self.assertEqual(resposta.status_code, 200)
        self.assertNotContains(resposta, '<script>alert(1)</script>')
        self.assertNotContains(resposta, '"><img onerror=1>')
        self.assertContains(resposta, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertContains(resposta, '&quot;&gt;&lt;img onerror=1&gt;')

    def _artigo(self, html, chave):
        achado = re.search(
            r'<article[^>]*data-chave="%s".*?</article>' % re.escape(chave),
            html, re.S,
        )
        self.assertIsNotNone(achado, chave)
        return achado.group(0)

    def test_salvar_incluir_false_em_obrigatorio_e_coagido(self):
        extracao = self._extracao()
        salvar = self.client.post(
            self.url('salvar_bloco_ocr'),
            data=json.dumps({
                'versao': self._tela().context['versao'],
                'decisoes': [{'chave': '/document/cartorio', 'incluir': False}],
            }),
            content_type='application/json',
        )
        self.assertEqual(salvar.status_code, 200, salvar.content)
        campo = extracao.campos.get(chave='/document/cartorio')
        self.assertNotEqual(campo.status_revisao, 'descartado')

    def test_salvar_incluir_false_em_nao_obrigatorio_descarta(self):
        extracao = self._extracao()
        salvar = self.client.post(
            self.url('salvar_bloco_ocr'),
            data=json.dumps({
                'versao': self._tela().context['versao'],
                'decisoes': [{'chave': '/document/numero', 'incluir': False}],
            }),
            content_type='application/json',
        )
        self.assertEqual(salvar.status_code, 200, salvar.content)
        campo = extracao.campos.get(chave='/document/numero')
        self.assertEqual(campo.status_revisao, 'descartado')

    def test_tela_obrigatorio_sem_checkbox_incluir_e_com_badge(self):
        self._extracao()
        html = self._tela().content.decode()
        obrigatorio = self._artigo(html, '/document/cartorio')
        self.assertNotIn('data-campo-incluir', obrigatorio)
        self.assertIn('Obrigatório', obrigatorio)
        opcional = self._artigo(html, '/document/numero')
        self.assertIn('data-campo-incluir', opcional)
        self.assertNotIn('Obrigatório', opcional)

    def test_tela_obrigatorio_legado_descartado_aparece_incluido(self):
        extracao = self._extracao()
        extracao.campos.filter(chave='/document/cartorio').update(
            status_revisao='descartado',
        )
        html = self._tela().content.decode()
        self.assertNotIn(' descartado"', self._artigo(html, '/document/cartorio'))

    def test_tela_pendencia_de_cartorio_em_linguagem_de_negocio(self):
        self._extracao_com_cartorio_nulo()
        html = self._tela().content.decode()
        bloco = re.search(r'data-ocr-pendencias.*?</section>', html, re.S).group(0)
        self.assertIn('escolha o cartório', bloco)
        principal = re.sub(r'<details.*?</details>', '', bloco, flags=re.S)
        principal = re.sub(r'title="[^"]*"', '', principal)
        self.assertNotIn('/document/cartorio', principal)

    def test_tela_pendencias_de_atos_distintos_dizem_o_campo(self):
        # Greptile P2 (#317): duas datas faltando em atos diferentes não podem
        # vir textos idênticos — o local diz qual ato corrigir.
        payload = payload_averbacao(self.job.job_id)
        payload['acts'].append(payload_registro(self.job.job_id)['acts'][0])
        for ato in payload['acts']:
            ato.pop('data')
        self._extracao(payload)

        resposta = self._tela()
        html = resposta.content.decode()

        self.assertEqual(resposta.status_code, 200)
        self.assertIn(
            'Ato 1 — data: Campo obrigatório não preenchido — informe a data',
            html,
        )
        self.assertIn(
            'Ato 2 — data: Campo obrigatório não preenchido — informe a data',
            html,
        )

    def test_campo_obrigatorio(self):
        self.assertTrue(revisao.campo_obrigatorio('/document/tipo'))
        self.assertTrue(revisao.campo_obrigatorio('/acts/0/data'))
        self.assertTrue(revisao.campo_obrigatorio('/acts/2/tipo_sugerido'))
        self.assertFalse(revisao.campo_obrigatorio('/document/numero'))
        self.assertFalse(revisao.campo_obrigatorio('/acts/0/partes/1/nome'))

    def test_tela_mostra_pendencias_e_desabilita_finalizar(self):
        extracao = self._extracao()
        self.assertTrue(revisao.pendencias(extracao))

        resposta = self._tela()

        self.assertContains(resposta, 'data-ocr-pendencias')
        self.assertIn('disabled', self._botao_finalizar(resposta))

    def test_tela_sem_pendencia_habilita_finalizar(self):
        extracao = self._extracao(resolver=True)
        self.assertEqual(revisao.pendencias(extracao), [])

        resposta = self._tela()

        self.assertNotContains(resposta, 'data-ocr-pendencias')
        self.assertNotIn('disabled', self._botao_finalizar(resposta))
        self.assertNotContains(resposta, 'data-ocr-somente-leitura')

    def test_tela_mostra_rotulos_dos_candidatos(self):
        candidatos = [
            Pessoas.objects.create(nome='JOÃO DA SILVA', cpf='11111111111'),
            Pessoas.objects.create(nome='JOÃO PEREIRA', cpf='22222222222'),
        ]
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['partes'][0]['match_pessoa_candidatos'] = [
            candidato.pk for candidato in candidatos
        ]
        self._extracao(payload)

        resposta = self._tela()

        self.assertContains(resposta, 'CPF ***.***.***-11')
        self.assertContains(resposta, 'CPF ***.***.***-22')
        self.assertContains(
            resposta, f'<option value="{candidatos[0].pk}"',
        )
        self.assertContains(
            resposta, f'<option value="{candidatos[1].pk}"',
        )
        self.assertNotContains(resposta, 'Registro #11')
        self.assertNotContains(resposta, '11111111111')
        self.assertNotContains(resposta, '22222222222')

    def test_tela_mostra_evidencia_e_link_da_pagina(self):
        self.job.paginas.filter(numero_pagina=2).update(
            texto_ocr='Página dois Nº 42.718',
        )
        payload = payload_averbacao(self.job.job_id)
        payload['document']['numero']['evidencia'] = {
            'pagina': 2, 'trecho': 'Nº 42.718',
        }
        self._extracao(payload)

        resposta = self._tela()

        self.assertContains(resposta, 'Página 2')
        self.assertContains(resposta, 'Nº 42.718')
        self.assertContains(resposta, f'{self.url_pdf()}#page=2')

    def test_tela_somente_leitura_apos_revisado(self):
        extracao = self._extracao(resolver=True)
        ExtracaoSugerida.objects.filter(pk=extracao.pk).update(
            finalizada_em=timezone.now(), finalizada_por=self.dono,
        )
        OcrJob.objects.filter(pk=self.job.pk).update(status=estados.REVISADO)

        resposta = self._tela()

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'data-ocr-somente-leitura')
        self.assertIn('disabled', self._botao_finalizar(resposta))
        html = resposta.content.decode()
        valores = re.findall(
            r'<(?:input|textarea|select)[^>]*data-campo-valor[^>]*>', html,
        )
        # Cards = linhas NÃO ignoradas (Tarefa C #322: extração antiga com
        # valor_transacao salva não entra na tela nem na contagem).
        cards_esperados = sum(
            1 for campo in extracao.campos.all()
            if not revisao.linha_ignorada(campo.chave)
        )
        self.assertEqual(len(valores), cards_esperados)
        for tag in valores:
            self.assertIn(' disabled', tag)

    def test_campo_limpo_nao_ressuscita_ao_recarregar_nem_conferir(self):
        self._extracao()
        chave = '/document/numero'
        versao = self._tela().context['versao']

        # Limpar o texto opcional grava '' (vazio intencional, não None).
        for conferido in (False, True):
            with self.subTest(conferido=conferido):
                resposta = self.client.post(
                    self.url('salvar_bloco_ocr'),
                    data=json.dumps({'versao': versao, 'decisoes': [{
                        'chave': chave, 'incluir': True,
                        'conferido': conferido, 'valor': '',
                    }]}),
                    content_type='application/json',
                )
                self.assertEqual(resposta.status_code, 200, resposta.content)
                versao = resposta.json()['versao']

                html = self._tela().content.decode()
                self.assertEqual(self._valor_do_card(html, chave), '')

    def test_tela_exige_login_e_permissao(self):
        self._extracao()
        url = self.url('campos_job_ocr')

        self.client.logout()
        resposta = self.client.get(url)
        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(resposta.url.startswith(
            f'{resolve_url(settings.LOGIN_URL)}?next=',
        ))

        self.client.force_login(self.sem_acesso)
        self.assertEqual(self.client.get(url).status_code, 404)

    def _extracao_com_cartorio_nulo(self, payload=None):
        """Payload com cartório obrigatório sem nome; demais linhas resolvidas."""
        payload = payload or payload_registro(self.job.job_id)
        payload['document']['cartorio']['normalized'] = None
        extracao = self._extracao(payload)
        for campo in extracao.campos.all():
            if campo.chave == '/document/cartorio':
                continue
            campo.status_revisao = 'aceito'
            if campo.tipo_valor in ('parte', 'cartorio'):
                campo.criar_novo = True
            campo.save()
        return extracao

    def _salvar_cartorio(self, decisao):
        salvar = self.client.post(
            self.url('salvar_bloco_ocr'),
            data=json.dumps({
                'versao': self._tela().context['versao'],
                'decisoes': [{
                    'chave': '/document/cartorio', 'incluir': True, **decisao,
                }],
            }),
            content_type='application/json',
        )
        return salvar

    def test_salvar_cartorio_digitado_satisfaz_obrigatorio(self):
        extracao = self._extracao_com_cartorio_nulo()

        salvar = self._salvar_cartorio({
            'valor': 'Cartório Novo', 'escolha': {'criar_novo': True},
        })

        self.assertEqual(salvar.status_code, 200, salvar.content)
        campo = extracao.campos.get(chave='/document/cartorio')
        self.assertEqual(campo.valor_final, 'Cartório Novo')
        self.assertEqual(campo.status_revisao, 'editado')
        self.assertFalse(any(
            pendencia['chave'] == '/document/cartorio'
            and pendencia['motivo'] == 'obrigatorio_ausente'
            for pendencia in revisao.pendencias(extracao)
        ))

    def test_finalizar_com_cartorio_digitado(self):
        extracao = self._extracao_com_cartorio_nulo()
        salvar = self._salvar_cartorio({
            'valor': 'Cartório Novo', 'escolha': {'criar_novo': True},
        })
        self.assertEqual(salvar.status_code, 200, salvar.content)

        finalizar = self.client.post(
            self.url('finalizar_revisao_ocr'),
            data=json.dumps({'versao': salvar.json()['versao']}),
            content_type='application/json',
        )

        self.assertEqual(finalizar.status_code, 200, finalizar.content)
        extracao.refresh_from_db()
        dados = revisao.dados_revisados(extracao)
        self.assertEqual(dados.documento.cartorio_nome, 'Cartório Novo')
        self.assertTrue(dados.documento.cartorio_criar_novo)

    def test_criar_novo_cartorio_opcional_sem_nome_gera_pendencia(self):
        extracao = self._extracao(resolver=True)
        self.assertEqual(revisao.pendencias(extracao), [])
        chave = '/document/cri_atual'

        salvar = self.client.post(
            self.url('salvar_bloco_ocr'),
            data=json.dumps({
                'versao': self._tela().context['versao'],
                'decisoes': [{
                    'chave': chave, 'incluir': True, 'valor': '',
                    'escolha': {'criar_novo': True},
                }],
            }),
            content_type='application/json',
        )

        self.assertEqual(salvar.status_code, 200, salvar.content)
        self.assertIn(
            {'chave': chave, 'motivo': 'criar_novo_sem_nome',
             'bloqueante': True},
            revisao.pendencias(extracao),
        )

        salvar = self.client.post(
            self.url('salvar_bloco_ocr'),
            data=json.dumps({
                'versao': salvar.json()['versao'],
                'decisoes': [{
                    'chave': chave, 'incluir': True, 'valor': 'Cartório Novo',
                    'escolha': {'criar_novo': True},
                }],
            }),
            content_type='application/json',
        )

        self.assertEqual(salvar.status_code, 200, salvar.content)
        self.assertFalse(any(
            pendencia['motivo'] == 'criar_novo_sem_nome'
            for pendencia in revisao.pendencias(extracao)
        ))

    def test_escolher_cartorio_existente_zera_nome(self):
        cartorio = Cartorios.objects.create(
            nome='Cartório Existente', cns='E2E-novo', estado='PR',
        )
        extracao = self._extracao_com_cartorio_nulo()
        # A tela só oferece match_candidatos: o cartório foi criado depois da
        # extração, então simula a lista recomputada que o select exibiria.
        extracao.campos.filter(chave='/document/cartorio').update(
            match_candidatos=[cartorio.pk],
        )

        salvar = self._salvar_cartorio({
            'valor': 'Cartório Digitado',
            'escolha': {'cartorio_id': cartorio.pk, 'criar_novo': False},
        })

        self.assertEqual(salvar.status_code, 200, salvar.content)
        campo = extracao.campos.get(chave='/document/cartorio')
        self.assertIsNone(campo.valor_final)
        self.assertEqual(campo.cartorio_escolhido_id, cartorio.pk)
        self.assertFalse(any(
            pendencia['chave'] == '/document/cartorio'
            and pendencia['motivo'] == 'obrigatorio_ausente'
            for pendencia in revisao.pendencias(extracao)
        ))

        finalizar = self.client.post(
            self.url('finalizar_revisao_ocr'),
            data=json.dumps({'versao': salvar.json()['versao']}),
            content_type='application/json',
        )
        self.assertEqual(finalizar.status_code, 200, finalizar.content)
        extracao.refresh_from_db()
        dados = revisao.dados_revisados(extracao)
        self.assertEqual(dados.documento.cartorio_id, cartorio.pk)

    def test_cartorio_digitado_acima_do_limite_e_422(self):
        self._extracao_com_cartorio_nulo()

        salvar = self._salvar_cartorio({
            'valor': 'x' * 10001, 'escolha': {'criar_novo': True},
        })

        self.assertEqual(salvar.status_code, 422, salvar.content)
        self.assertEqual(salvar.json()['erro'], 'valor_invalido')
        self.assertEqual(salvar.json()['chave'], '/document/cartorio')

    def test_cartorio_nome_no_limite_de_200_e_aceito(self):
        extracao = self._extracao_com_cartorio_nulo()

        salvar = self._salvar_cartorio({
            'valor': 'x' * 200, 'escolha': {'criar_novo': True},
        })

        self.assertEqual(salvar.status_code, 200, salvar.content)
        campo = extracao.campos.get(chave='/document/cartorio')
        self.assertEqual(campo.valor_final, 'x' * 200)

    def test_cartorio_nome_acima_de_200_e_422(self):
        self._extracao_com_cartorio_nulo()

        salvar = self._salvar_cartorio({
            'valor': 'x' * 201, 'escolha': {'criar_novo': True},
        })

        self.assertEqual(salvar.status_code, 422, salvar.content)
        self.assertEqual(salvar.json()['erro'], 'valor_invalido')
        self.assertEqual(salvar.json()['chave'], '/document/cartorio')

    def test_cartorio_nome_acima_de_200_bloqueia_finalizacao(self):
        extracao = self._extracao_com_cartorio_nulo()
        extracao.campos.filter(chave='/document/cartorio').update(
            normalized='x' * 201, status_revisao='editado', criar_novo=True,
        )
        versao = self._tela().context['versao']

        finalizar = self.client.post(
            self.url('finalizar_revisao_ocr'),
            data=json.dumps({'versao': versao}),
            content_type='application/json',
        )

        self.assertEqual(finalizar.status_code, 422, finalizar.content)
        self.assertIn(
            {
                'chave': '/document/cartorio',
                'motivo': 'valor_acima_do_limite_destino',
                'bloqueante': True,
            },
            finalizar.json()['pendencias'],
        )

    def _extracao_com_cartorio_ocr_longo(self, cartorio_pk=None):
        """OCR traz nome acima de 200; opcionalmente com candidato existente."""
        extracao = self._extracao(resolver=True)
        extracao.campos.filter(chave='/document/cartorio').update(
            normalized='x' * 250,
            match_candidatos=[cartorio_pk] if cartorio_pk else [],
            status_revisao='sugerido',
            criar_novo=False,
        )
        return extracao

    def test_cartorio_existente_escolhido_aceita_nome_longo_do_ocr(self):
        cartorio = Cartorios.objects.create(
            nome='Cartório Existente', cns='E2E-longo', estado='PR',
        )
        extracao = self._extracao_com_cartorio_ocr_longo(cartorio.pk)

        salvar = self._salvar_cartorio({
            'escolha': {'cartorio_id': cartorio.pk, 'criar_novo': False},
        })

        self.assertEqual(salvar.status_code, 200, salvar.content)
        campo = extracao.campos.get(chave='/document/cartorio')
        self.assertEqual(campo.cartorio_escolhido_id, cartorio.pk)
        self.assertFalse(any(
            pendencia['chave'] == '/document/cartorio'
            for pendencia in revisao.pendencias(extracao)
        ))

    def test_cartorio_existente_escolhido_finaliza_com_nome_longo_do_ocr(self):
        cartorio = Cartorios.objects.create(
            nome='Cartório Existente', cns='E2E-longo', estado='PR',
        )
        self._extracao_com_cartorio_ocr_longo(cartorio.pk)

        salvar = self._salvar_cartorio({
            'escolha': {'cartorio_id': cartorio.pk, 'criar_novo': False},
        })
        self.assertEqual(salvar.status_code, 200, salvar.content)

        finalizar = self.client.post(
            self.url('finalizar_revisao_ocr'),
            data=json.dumps({'versao': salvar.json()['versao']}),
            content_type='application/json',
        )

        self.assertEqual(finalizar.status_code, 200, finalizar.content)

    def test_cartorio_nome_longo_do_ocr_sem_escolha_e_422(self):
        self._extracao_com_cartorio_ocr_longo()

        salvar = self._salvar_cartorio({'escolha': {'criar_novo': False}})

        self.assertEqual(salvar.status_code, 422, salvar.content)
        self.assertEqual(salvar.json()['erro'], 'valor_invalido')
        self.assertEqual(salvar.json()['chave'], '/document/cartorio')

    @staticmethod
    def _campo_sintetico(valor):
        return {
            'raw': valor, 'normalized': valor, 'confianca': 0.95,
            'requer_revisao': False, 'evidencia': None,
        }

    def _extracao_com_rg_longo(self, comprimento):
        """OCR sugere documento de identificação RG acima do limite da parte."""
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['partes'][2]['documento_identificacao'] = {
            'tipo': self._campo_sintetico('RG'),
            'valor': self._campo_sintetico('x' * comprimento),
        }
        return self._extracao(payload, resolver=True)

    def test_rg_acima_de_20_e_422_no_save_com_a_chave(self):
        chave = '/acts/0/partes/2/documento_identificacao/valor'
        self._extracao_com_rg_longo(21)

        salvar = self.client.post(
            self.url('salvar_bloco_ocr'),
            data=json.dumps({
                'versao': self._tela().context['versao'],
                'decisoes': [{'chave': chave, 'incluir': True,
                              'conferido': True}],
            }),
            content_type='application/json',
        )

        self.assertEqual(salvar.status_code, 422, salvar.content)
        self.assertEqual(salvar.json()['erro'], 'valor_invalido')
        self.assertEqual(salvar.json()['chave'], chave)

    def test_rg_acima_de_20_bloqueia_a_finalizacao(self):
        chave = '/acts/0/partes/2/documento_identificacao/valor'
        self._extracao_com_rg_longo(21)

        finalizar = self.client.post(
            self.url('finalizar_revisao_ocr'),
            data=json.dumps({'versao': self._tela().context['versao']}),
            content_type='application/json',
        )

        self.assertEqual(finalizar.status_code, 422, finalizar.content)
        self.assertIn({
            'chave': chave, 'motivo': 'valor_acima_do_limite_destino',
            'bloqueante': True,
        }, finalizar.json()['pendencias'])

    def test_evidencia_mascara_documentos_com_7_ou_mais_digitos(self):
        payload = payload_averbacao(self.job.job_id)
        payload['document']['numero']['evidencia'] = {
            'pagina': 1,
            'trecho': 'Transmitente: JOÃO DA SILVA (CPF 123.456.789-00).',
        }
        extracao = self._extracao(payload)

        resposta = self._tela()

        self.assertContains(resposta, 'CPF ***')
        self.assertNotContains(resposta, '123.456.789-00')
        self.assertEqual(
            extracao.campos.get(chave='/document/numero').evidencia_trecho,
            'Transmitente: JOÃO DA SILVA (CPF 123.456.789-00).',
        )

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
        mascarar = views._mascarar_evidencia
        self.assertEqual(
            mascarar('CPF 123.456.789-00 e RG 12.345.678-9'),
            'CPF *** e RG ***',
        )
        self.assertEqual(
            mascarar('Trecho sem documento, com 123456 apenas'),
            'Trecho sem documento, com 123456 apenas',
        )

    def test_mascara_rg_pelo_rotulo(self):
        mascarar = views._mascarar_evidencia
        for trecho, esperado in self.CASOS_MASCARADOS:
            with self.subTest(trecho=trecho):
                self.assertEqual(mascarar(trecho), esperado)

    def test_mascara_preserva_numeros_sem_rotulo(self):
        mascarar = views._mascarar_evidencia
        for trecho in self.CASOS_INTACTOS:
            with self.subTest(trecho=trecho):
                self.assertEqual(mascarar(trecho), trecho)

    def test_mascara_preserva_data_iso_valor_cns_e_processo(self):
        mascarar = views._mascarar_evidencia
        trecho = (
            'Data 10/01/2020, ISO 2020-01-10, valor R$ 1.500.000,00, '
            'CNS 123456789012345, processo 0001234-56.2020.8.16.0001.'
        )
        self.assertEqual(mascarar(trecho), trecho)

    def test_mascara_cpf_e_rg_com_pontuacao_final(self):
        mascarar = views._mascarar_evidencia
        self.assertEqual(
            mascarar('CPF 12345678900 e RG 1234567-X, matrícula 123456.'),
            'CPF *** e RG ***, matrícula 123456.',
        )

    def test_mascara_rg_seguido_de_pontuacao(self):
        mascarar = views._mascarar_evidencia
        self.assertEqual(mascarar('RG 123456.'), 'RG ***.')
        self.assertEqual(
            mascarar('RG 123456, emitido pelo oficial'),
            'RG ***, emitido pelo oficial',
        )

    def test_mascara_preserva_pontuacao_de_numero_maior(self):
        mascarar = views._mascarar_evidencia
        trecho = (
            'Valor 1.500.000,00 e 1500000,00, datas 10/01/2020 e '
            '2020-01-10, CNS 123456789012345'
        )
        self.assertEqual(mascarar(trecho), trecho)

    def test_mascara_cpf_com_espacos_contiguo_e_rg_curto(self):
        mascarar = views._mascarar_evidencia
        self.assertEqual(
            mascarar('CPF 123 456 789 00 e CPF 12345678900.'),
            'CPF *** e CPF ***.',
        )
        self.assertEqual(
            mascarar('RG 123456 e RG 123456789.'),
            'RG *** e RG ***.',
        )

    def test_mascara_preserva_valor_sem_milhar_e_processo_longo(self):
        mascarar = views._mascarar_evidencia
        trecho = (
            'Valor 1500000,00, processo 000123456789, '
            'CNS 123456789012345.'
        )
        self.assertEqual(mascarar(trecho), trecho)

    def _titulos_da_evidencia(self, campo, trecho):
        CampoSugerido.objects.filter(pk=campo.pk).update(
            evidencia_trecho=trecho, evidencia_pagina=1,
        )
        html = self._tela().content.decode()
        trechos = _elementos(
            html, 'span', presentes=('title',),
            valores={'class': 'campo-trecho'},
        )
        return [_atributos(span)['title'] for span in trechos]

    def test_tela_mascara_title_dos_casos_com_rotulo(self):
        extracao = self._extracao()
        campo = extracao.campos.get(chave='/document/numero')
        for trecho, esperado in self.CASOS_MASCARADOS:
            with self.subTest(trecho=trecho):
                self.assertIn(
                    esperado, self._titulos_da_evidencia(campo, trecho),
                )

    def test_tela_preserva_title_dos_casos_sem_rotulo(self):
        extracao = self._extracao()
        campo = extracao.campos.get(chave='/document/numero')
        for trecho in self.CASOS_INTACTOS:
            with self.subTest(trecho=trecho):
                self.assertIn(
                    trecho, self._titulos_da_evidencia(campo, trecho),
                )

    def test_evidencia_mascarada_nao_altera_valor_do_campo(self):
        extracao = self._extracao(payload_registro(self.job.job_id))
        chave = '/acts/0/partes/0/documento_identificacao/valor'
        campo = extracao.campos.get(chave=chave)
        CampoSugerido.objects.filter(pk=campo.pk).update(
            evidencia_trecho='CPF 123.456.789-00', evidencia_pagina=1,
        )

        resposta = self._tela()
        html = resposta.content.decode()

        self.assertEqual(self._valor_do_card(html, chave), '12345678900')
        campo.refresh_from_db()
        self.assertEqual(campo.normalized, '12345678900')
        trechos = _elementos(
            html, 'span', presentes=('title',),
            valores={'class': 'campo-trecho'},
        )
        self.assertIn(
            'CPF ***', [_atributos(trecho)['title'] for trecho in trechos],
        )

    def test_valor_transacao_do_payload_nao_vira_card_e_finaliza(self):
        """Tarefa C #322: o campo não existe no formulário de lançamento."""
        extracao = self._extracao(
            payload_registro(self.job.job_id), resolver=True,
        )
        self.assertEqual(revisao.pendencias(extracao), [])
        self.assertNotIn(
            '/acts/0/valor_transacao', self._chaves_na_tela(),
        )

        finalizar = self.client.post(
            self.url('finalizar_revisao_ocr'),
            data=json.dumps({'versao': self._tela().context['versao']}),
            content_type='application/json',
        )
        self.assertEqual(finalizar.status_code, 200, finalizar.content)

    def test_linha_antiga_de_valor_transacao_nao_aparece_na_tela(self):
        """Tarefa C #322: extração antiga com a linha salva — sem card."""
        extracao = self._extracao(
            payload_registro(self.job.job_id), resolver=True,
        )
        CampoSugerido.objects.create(
            extracao=extracao,
            chave='/acts/0/valor_transacao',
            raw='R$ 150.000,00',
            normalized='150000.00',
            tipo_valor='decimal',
            status_revisao='sugerido',
            requer_revisao=True,
        )

        self.assertNotIn(
            '/acts/0/valor_transacao', self._chaves_na_tela(),
        )

        finalizar = self.client.post(
            self.url('finalizar_revisao_ocr'),
            data=json.dumps({'versao': self._tela().context['versao']}),
            content_type='application/json',
        )
        self.assertEqual(finalizar.status_code, 200, finalizar.content)

    def test_obrigatorio_vazio_continua_bloqueando_finalizacao(self):
        extracao = self._extracao(
            payload_registro(self.job.job_id), resolver=True,
        )
        chave = '/document/data'

        salvar = self.client.post(
            self.url('salvar_bloco_ocr'),
            data=json.dumps({
                'versao': self._tela().context['versao'],
                'decisoes': [{
                    'chave': chave, 'incluir': True, 'valor': '',
                }],
            }),
            content_type='application/json',
        )
        self.assertEqual(salvar.status_code, 200, salvar.content)

        finalizar = self.client.post(
            self.url('finalizar_revisao_ocr'),
            data=json.dumps({'versao': salvar.json()['versao']}),
            content_type='application/json',
        )

        self.assertEqual(finalizar.status_code, 422, finalizar.content)
        self.assertIn(
            {
                'chave': chave,
                'motivo': 'obrigatorio_ausente',
                'bloqueante': True,
            },
            finalizar.json()['pendencias'],
        )
        self.assertFalse(any(
            pendencia['chave'] == chave
            and pendencia['motivo'] == 'valor_incompativel_destino'
            for pendencia in finalizar.json()['pendencias']
        ))

    def test_enum_obrigatorio_vazio_bloqueia_finalizacao(self):
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['origem'] = {
            'tipo_documento': dict(payload['document']['tipo']),
        }
        extracao = self._extracao(payload, resolver=True)
        chave = '/acts/0/origem/tipo_documento'
        self.assertFalse(any(
            pendencia['chave'] == chave
            for pendencia in revisao.pendencias(extracao)
        ))

        salvar = self.client.post(
            self.url('salvar_bloco_ocr'),
            data=json.dumps({
                'versao': self._tela().context['versao'],
                'decisoes': [{
                    'chave': chave, 'incluir': True, 'valor': '',
                }],
            }),
            content_type='application/json',
        )
        self.assertEqual(salvar.status_code, 200, salvar.content)
        self.assertEqual(
            extracao.campos.get(chave=chave).valor_final, '',
        )

        finalizar = self.client.post(
            self.url('finalizar_revisao_ocr'),
            data=json.dumps({'versao': salvar.json()['versao']}),
            content_type='application/json',
        )

        self.assertEqual(finalizar.status_code, 422, finalizar.content)
        self.assertIn(
            {
                'chave': chave,
                'motivo': 'valor_incompativel_destino',
                'bloqueante': True,
            },
            finalizar.json()['pendencias'],
        )

    def test_decimal_so_espacos_salva_como_vazio(self):
        extracao = self._extracao(
            payload_registro(self.job.job_id), resolver=True,
        )
        # Tarefa C #322: valor_transacao não é mais linha de revisão.
        for chave in ('/acts/0/area',):
            with self.subTest(chave=chave):
                salvar = self.client.post(
                    self.url('salvar_bloco_ocr'),
                    data=json.dumps({
                        'versao': self._tela().context['versao'],
                        'decisoes': [{
                            'chave': chave, 'incluir': True, 'valor': '   ',
                        }],
                    }),
                    content_type='application/json',
                )

                self.assertEqual(salvar.status_code, 200, salvar.content)
                self.assertEqual(
                    extracao.campos.get(chave=chave).valor_final, '',
                )

    def test_descartar_campo_exigido_pelo_tipo_nao_estoura(self):
        LancamentoTipo.objects.create(
            tipo='averbacao', requer_descricao=True, requer_observacao=False,
        )
        extracao = self._extracao()

        salvar = self.client.post(
            self.url('salvar_bloco_ocr'),
            data=json.dumps({
                'versao': self._tela().context['versao'],
                'decisoes': [{'chave': '/acts/0/descricao', 'incluir': False}],
            }),
            content_type='application/json',
        )

        self.assertEqual(salvar.status_code, 200, salvar.content)
        campo = extracao.campos.get(chave='/acts/0/descricao')
        self.assertEqual(campo.status_revisao, 'descartado')

    def test_mudar_tipo_com_titulo_descartado_nao_estoura(self):
        LancamentoTipo.objects.create(
            tipo='registro', requer_titulo=True,
            requer_cartorio_origem=False, requer_observacao=False,
        )
        extracao = self._extracao()
        CampoSugerido.objects.create(
            extracao=extracao,
            chave='/acts/0/titulo',
            raw='Título antigo',
            normalized='Título antigo',
            tipo_valor='texto',
            status_revisao='descartado',
        )

        salvar = self.client.post(
            self.url('salvar_bloco_ocr'),
            data=json.dumps({
                'versao': self._tela().context['versao'],
                'decisoes': [{
                    'chave': '/acts/0/tipo_sugerido',
                    'incluir': True, 'valor': 'registro',
                }],
            }),
            content_type='application/json',
        )

        self.assertEqual(salvar.status_code, 200, salvar.content)
        campo = extracao.campos.get(chave='/acts/0/titulo')
        self.assertEqual(campo.status_revisao, 'descartado')

    def test_finaliza_usando_apenas_os_controles_renderizados(self):
        # Cartório do documento: match único; cri_atual: dois homônimos;
        # JOÃO por CPF; MARIA e PEDRO sem cadastro (único caminho: criar).
        Cartorios.objects.create(nome='CRI de Guaíra', cns='E2E-1', estado='PR')
        homonimos = [
            Cartorios.objects.create(
                nome='Cartório de Registro de Imóveis de Guaíra',
                cns=f'E2E-{indice}', estado='PR',
            )
            for indice in (2, 3)
        ]
        Pessoas.objects.create(nome='JOÃO DA SILVA', cpf='12345678900')
        payload = enriquecer_payload(
            payload_registro(self.job.job_id), IndicePessoas(), IndiceCartorios(),
        )
        self._extracao(payload)

        html = self._tela().content.decode()
        toolbar = _elementos(html, 'div', presentes=('data-ocr-toolbar',))[0]
        versao = _atributos(toolbar)['data-versao']
        decisoes = [
            decisao for card in _elementos(html, 'article', presentes=('data-campo',))
            if (decisao := _decisao_do_card(card)) is not None
        ]
        escolhas = {d['chave']: d['escolha'] for d in decisoes if 'escolha' in d}
        self.assertEqual(
            escolhas['/document/cri_atual']['cartorio_id'], homonimos[0].pk,
        )
        self.assertTrue(escolhas['/acts/0/partes/2']['criar_novo'])

        salvar = self.client.post(
            self.url('salvar_bloco_ocr'),
            data=json.dumps({'versao': versao, 'decisoes': decisoes}),
            content_type='application/json',
        )
        self.assertEqual(salvar.status_code, 200, salvar.content)

        finalizar = self.client.post(
            self.url('finalizar_revisao_ocr'),
            data=json.dumps({'versao': salvar.json()['versao']}),
            content_type='application/json',
        )
        self.assertEqual(finalizar.status_code, 200, finalizar.content)
        self.assertIn('redirect', finalizar.json())


def _texto_fora_de_details(no):
    """Texto visível sem atributos nem detalhes, inclusive os aninhados."""
    if isinstance(no, str):
        return no
    if no.name in ('details', 'script', 'style'):
        return ''
    return ' '.join(_texto_fora_de_details(filho) for filho in no.children)


class FormularioPorAtoTest(TelaRevisaoBase):
    """Contrato de apresentação I-11a (#321), sem mudar decisões da revisão."""

    def _payload_formulario(self):
        payload = payload_com_closure(self.job.job_id)
        ato = payload['acts'][0]
        for nome, valor in (
            ('numero_lancamento', '1'), ('forma', 'Compra e venda'),
            ('titulo', 'Escritura pública'), ('descricao', 'Descrição do ato'),
            ('detalhes', 'Informação complementar'),
            ('eh_inicio_matricula', False), ('observacoes', 'Observações do ato'),
            ('cartorio_transmissao', 'CRI de Guaíra'),
        ):
            ato[nome] = _campo(valor, 'R-1/42.718')
        ato['origem'] = {
            'numero': _campo('42', 'R-1/42.718'),
            'cartorio': _campo('CRI de Guaíra', 'CRI de Guaíra'),
        }
        return payload

    def test_formulario_abre_pela_secao_documento(self):
        payload = self._payload_formulario()
        self._extracao(payload)
        resposta = self._tela()
        html = resposta.content.decode()

        self.assertEqual(_texto_fora_de_details(_elementos(html, 'h2')[0]), 'Documento')
        secoes = resposta.context['secoes']
        self.assertEqual(secoes[0]['tipo'], 'documento')
        self.assertEqual([c.chave for c in secoes[0]['campos']], [
            '/document/' + nome for nome in (
                'tipo', 'numero', 'data', 'cartorio', 'livro', 'folha',
                'imovel_descricao', 'area',
            )
        ])
        campos = resposta.context['campos']
        self.assertCountEqual(self._chaves_do_html(html), [c.chave for c in campos])
        antes = [dict(c.__dict__) for c in campos]
        with self.assertNumQueries(0):
            revisao.secoes_da_tela(campos, payload=payload)
        self.assertEqual([c.__dict__ for c in campos], antes)

        # Não reconhecidos usa o payload do serviço; legado usa o salvo.
        desconhecido = copy.deepcopy(payload)
        desconhecido['acts'][0]['rotulo']['normalized'] = 'X-9'
        for servico, salvo in ((desconhecido, payload), ({}, desconhecido)):
            with self.subTest(payload_servico=bool(servico)):
                ExtracaoSugerida.objects.update(payload_servico=servico, payload=salvo)
                html = self._tela().content.decode()
                secao = _elementos(html, 'section', valores={
                    'data-secao': 'nao_reconhecidos',
                })[0]
                self.assertIn('X-9', str(secao))
                self.assertFalse(_descendentes(secao, 'article', 'data-campo'))

    def test_atos_em_ordem_reversa(self):
        payload = self._payload_formulario()
        payload['acts'] = [copy.deepcopy(payload['acts'][0]) for _ in range(3)]
        for ato in payload['acts']:
            ato['rotulo'].update(normalized=None, raw=None)
        extracao = self._extracao(payload)

        def titulos(resposta):
            return [
                _texto_fora_de_details(_elementos(str(secao), 'h2')[0])
                for secao in _elementos(resposta.content.decode(), 'section',
                                       valores={'data-secao': 'ato'})
            ]

        self.assertEqual(titulos(self._tela()), ['Ato 3', 'Ato 2', 'Ato 1'])
        for indice, rotulo in enumerate(('R-1', 'Av-2', 'R-3')):
            extracao.campos.filter(chave=f'/acts/{indice}/rotulo').update(
                normalized=rotulo, raw='Texto bruto diferente',
            )
        resposta = self._tela()
        self.assertEqual(titulos(resposta), ['Ato R-3', 'Ato Av-2', 'Ato R-1'])
        secoes = [s for s in resposta.context['secoes'] if s['tipo'] == 'ato']
        self.assertEqual([s['tipo_display'] for s in secoes], [
            'Registro', 'Averbação', 'Registro',
        ])
        for secao in secoes:
            prefixo = secao['chave_ato']
            total = sum(
                p['chave'] == prefixo or p['chave'].startswith(prefixo + '/')
                for p in resposta.context['pendencias']
            )
            self.assertEqual(secao['pendencias_do_ato'], total)
            self.assertContains(resposta, f'{total} pendência')

    def test_nenhuma_chave_interna_fora_do_detalhe_tecnico(self):
        LancamentoTipo.objects.update_or_create(
            tipo='registro', defaults={'requer_forma': True},
        )
        payload = self._payload_formulario()
        del payload['acts'][0]['forma']
        self._extracao(payload)
        resposta = self._tela()
        self.assertTrue(resposta.context['avisos'])
        self.assertTrue(resposta.context['pendencias'])
        visivel = _texto_fora_de_details(parse_html(resposta.content.decode()))
        for interno in (
            '/document/', '/acts/', 'SEM_DESTINO', 'requer_forma',
            'escolha_pendente', 'dominial.Lancamento',
        ):
            with self.subTest(interno=interno):
                self.assertNotIn(interno, visivel)
        self.assertIn('Campo recomendado não preenchido', visivel)

    def test_rotulo_de_negocio_por_campo(self):
        self._extracao(self._payload_formulario())
        html = self._tela().content.decode()
        cards = {
            _atributos(c)['data-chave']: c
            for c in _elementos(html, 'article', presentes=('data-campo',))
        }
        for chave, esperado in (
            ('/acts/0/tipo_sugerido', 'Tipo do lançamento'),
            ('/acts/0/numero_lancamento', 'Número'),
            ('/acts/0/data', 'Data'), ('/acts/0/area', 'Área (ha)'),
            ('/document/numero', 'Número do documento'),
            ('/acts/0/cartorio_transmissao', 'Cartório da transmissão'),
        ):
            with self.subTest(chave=chave):
                rotulo = _descendentes(cards[chave], 'label', 'data-campo-rotulo')[0]
                self.assertEqual(_texto_fora_de_details(rotulo), esperado)
        visivel = _texto_fora_de_details(parse_html(html))
        self.assertIn('Partes', visivel)
        self.assertIn('Origem', visivel)
        self.assertNotIn('tipo_sugerido', visivel)
        self.assertNotIn('numero_lancamento', visivel)
        self.assertEqual(revisao.rotulo_de_campo('/acts/0/campo_desconhecido'),
                         'Campo desconhecido')

    def test_campo_fora_do_formulario_fica_em_outros_dados(self):
        self._extracao(self._payload_formulario(), resolver=True)
        resposta = self._tela()
        html = resposta.content.decode()
        outros = _elementos(html, 'section', valores={'data-secao': 'outros'})[0]
        self.assertIn('Outros dados lidos', str(outros))
        detalhe = _elementos(str(outros), 'details', valores={'class': 'outros-dados'})[0]
        self.assertNotIn('open', _atributos(detalhe))
        chaves_outros = self._chaves_do_html(str(detalhe))
        for chave in (
            '/acts/0/detalhes', '/acts/0/eh_inicio_matricula', '/acts/0/rotulo',
            '/document/cri_atual',
            '/closure/indicio_fim_cadeia',
        ):
            with self.subTest(chave=chave):
                self.assertIn(chave, chaves_outros)
                self.assertEqual(self._chaves_do_html(html).count(chave), 1)
        ato = next(s for s in resposta.context['secoes'] if s['tipo'] == 'ato')
        self.assertEqual(ato['campos'][0].chave, '/acts/0')
        grupos = list(dict.fromkeys(c.chave.split('/')[3] for c in ato['campos'][1:]))
        self.assertEqual(grupos, [
            'tipo_sugerido', 'numero_lancamento', 'data', 'forma', 'titulo',
            'descricao', 'area', 'partes', 'cartorio_transmissao', 'origem',
            'observacoes',
        ])
        pendentes = {p['chave'] for p in resposta.context['pendencias']}
        for card in _elementos(html, 'article', presentes=('data-campo',)):
            detalhes = _elementos(str(card), 'details', valores={'class': 'campo-detalhe'})
            self.assertEqual(len(detalhes), 1)
            self.assertEqual('open' in _atributos(detalhes[0]),
                             _atributos(card)['data-chave'] in pendentes)
        # O agrupador também acolhe folhas legadas, sem reativá-las no save.
        legados = [
            CampoSugerido(chave='/acts/0/valor_transacao', normalized='150000'),
            CampoSugerido(chave='/acts/0/campo_desconhecido', normalized='extra'),
            CampoSugerido(chave='/acts/0/area/dado_extra', normalized='extra'),
        ]
        secoes = revisao.secoes_da_tela(legados)
        self.assertEqual(secoes[-1]['tipo'], 'outros')
        self.assertEqual([c.chave for c in secoes[-1]['campos']],
                         [c.chave for c in legados])

    def test_ato_descartado_aparece_no_proprio_bloco(self):
        extracao = self._extracao(self._payload_formulario())
        for status in ('sugerido', 'descartado'):
            with self.subTest(status=status):
                extracao.campos.filter(chave='/acts/0').update(status_revisao=status)
                html = self._tela().content.decode()
                secao = _elementos(html, 'section', valores={
                    'data-chave-ato': '/acts/0',
                })[0]
                cards = _descendentes(secao, 'article', 'data-campo')
                self.assertEqual([_atributos(c)['data-chave'] for c in cards[:2]],
                                 ['/acts/0', '/acts/0/tipo_sugerido'])
                incluir = _descendentes(cards[0], 'input', 'data-campo-incluir')
                self.assertEqual(len(incluir), 1)
                self.assertIn('Incluir', _texto_fora_de_details(cards[0]))
                self.assertEqual('checked' in _atributos(incluir[0]),
                                 status != 'descartado')
                self.assertEqual('descartado' in _atributos(secao)['class'].split(),
                                 status == 'descartado')
                outros = _elementos(html, 'section', valores={'data-secao': 'outros'})[0]
                self.assertNotIn('/acts/0', self._chaves_do_html(str(outros)))
                self.assertEqual(self._chaves_do_html(html).count('/acts/0'), 1)

    def test_pendencia_em_outros_abre_o_detalhe(self):
        extracao = self._extracao(self._payload_formulario(), resolver=True)
        chave = '/acts/0/detalhes'
        extracao.campos.filter(chave=chave).update(
            status_revisao='sugerido', requer_revisao=True,
        )

        resposta = self._tela()
        html = resposta.content.decode()
        pendencia = next(p for p in resposta.context['pendencias'] if p['chave'] == chave)
        self.assertContains(resposta, f'href="#{pendencia["alvo"]}"')
        outros = _elementos(html, 'details', valores={'class': 'outros-dados'})[0]
        self.assertIn('open', _atributos(outros))
        card = _elementos(str(outros), 'article', valores={'data-chave': chave})[0]
        detalhe = _elementos(str(card), 'details', valores={'class': 'campo-detalhe'})[0]
        self.assertIn('open', _atributos(detalhe))
        controle = _descendentes(card, 'textarea', 'data-campo-valor')[0]
        self.assertEqual(_atributos(controle)['id'], pendencia['alvo'])

    def test_titulo_do_ato_usa_rotulo_da_linha_do_ato(self):
        payload = payload_averbacao(self.job.job_id)
        payload['acts'][0]['rotulo']['normalized'] = 'Av-5'
        payload['acts'] = [copy.deepcopy(payload['acts'][0]) for _ in range(6)]
        extracao = self._extracao(payload)
        chave = '/acts/5'
        extracao.campos.filter(chave=f'{chave}/rotulo').delete()

        def titulo():
            secao = _elementos(self._tela().content.decode(), 'section', valores={
                'data-chave-ato': chave,
            })[0]
            return _texto_fora_de_details(_elementos(str(secao), 'h2')[0])

        self.assertEqual(titulo(), 'Ato Av-5')
        # A folha ganha quando incluída, mas seu descarte devolve a decisão
        # à linha estrutural; descartar ambas usa o número da seção.
        folha = CampoSugerido.objects.create(
            extracao=extracao, chave=f'{chave}/rotulo', tipo_valor='texto',
            normalized='R-9', valor_final='Av-7', status_revisao='editado',
        )
        self.assertEqual(titulo(), 'Ato Av-7')
        folha.status_revisao = 'descartado'
        folha.save(update_fields=['status_revisao'])
        self.assertEqual(titulo(), 'Ato Av-5')
        extracao.campos.filter(chave=chave).update(status_revisao='descartado')
        self.assertEqual(titulo(), 'Ato 6')

    def test_campo_texto_continua_textarea(self):
        payload = self._payload_formulario()
        for nome in ('titulo', 'forma'):
            payload['acts'][0][nome]['normalized'] = 'A\nB'
        extracao = self._extracao(payload)
        resposta = self._tela()
        html = resposta.content.decode()
        decisoes = []
        for nome in ('titulo', 'forma'):
            with self.subTest(campo=nome):
                chave = f'/acts/0/{nome}'
                card = _elementos(html, 'article', valores={'data-chave': chave})[0]
                controles = _descendentes(card, 'textarea', 'data-campo-valor')
                self.assertEqual(len(controles), 1)
                self.assertFalse(_descendentes(card, 'input', 'data-campo-valor'))
                atributos = _atributos(controles[0])
                self.assertEqual(atributos['data-tipo'], 'texto')
                self.assertIn('campo-valor', atributos['class'].split())
                # O parser de HTML normaliza espaços; leia o valor literal
                # para garantir que o formulário conserva a quebra de linha.
                valor = re.search(
                    rf'<textarea\b[^>]*id="{atributos["id"]}"[^>]*>(.*?)</textarea>',
                    html, re.S,
                ).group(1)
                self.assertEqual(valor, 'A\nB')
                decisoes.append({
                    'chave': chave, 'valor': valor, 'incluir': True, 'conferido': True,
                })
        salvar = self.client.post(
            self.url('salvar_bloco_ocr'),
            data=json.dumps({'versao': resposta.context['versao'], 'decisoes': decisoes}),
            content_type='application/json',
        )
        self.assertEqual(salvar.status_code, 200, salvar.content)
        for decisao in decisoes:
            campo = extracao.campos.get(chave=decisao['chave'])
            self.assertEqual(revisao._valor_efetivo(campo), 'A\nB')

    @override_settings(OCR_PERMITIR_FINALIZAR_SEM_ATOS=True)
    def test_pendencia_aponta_para_campo_existente(self):
        def conferir_links(resposta):
            html = resposta.content.decode()
            bloco = _elementos(html, 'section', presentes=('data-ocr-pendencias',))[0]
            links = _descendentes(bloco, 'a', 'href')
            self.assertTrue(links)
            self.assertEqual(len(links), len(resposta.context['pendencias']))
            ids = re.findall(r'\bid="([^"]+)"', html)
            for link in links:
                alvo = _atributos(link)['href'].removeprefix('#')
                self.assertEqual(ids.count(alvo), 1, alvo)
                controles = [
                    elemento for tag in ('input', 'select', 'textarea')
                    for elemento in _elementos(html, tag, valores={'id': alvo})
                ]
                self.assertEqual(len(controles), 1, alvo)

        self._extracao(self._payload_formulario())
        conferir_links(self._tela())
        payload = payload_averbacao(self.job.job_id)
        payload['acts'] = []
        self._extracao(payload, resolver=True)
        resposta = self._tela()
        conferir_links(resposta)
        self.assertContains(resposta, 'href="#campo-sem-atos"')
        with self.settings(OCR_PERMITIR_FINALIZAR_SEM_ATOS=False):
            self.assertNotContains(self._tela(), 'href="#campo-sem-atos"')
        for chave, acao in (
            ('/acts/0/tipo_sugerido', 'informe o tipo do lançamento'),
            ('/document/data', 'informe a data'),
            ('/document/cartorio', 'escolha o cartório'),
        ):
            descricao = revisao.descrever_pendencia({
                'chave': chave, 'motivo': 'obrigatorio_ausente',
            })
            self.assertEqual(descricao['acao'], acao)

    def test_bloco_do_tipo_intacto(self):
        payload = self._payload_formulario()
        # Sugestão divergente: a opção selecionada vem do resolvedor (#327).
        payload['acts'][0]['rotulo']['normalized'] = 'Av-1'
        self._extracao(payload)
        resposta = self._tela()
        card = _elementos(resposta.content.decode(), 'article', valores={
            'data-chave': '/acts/0/tipo_sugerido',
        })[0]
        selects = _descendentes(card, 'select', 'data-campo-valor')
        self.assertEqual(len(selects), 1)
        select = selects[0]
        self.assertEqual(_atributos(select)['data-tipo'], 'enum')
        self.assertEqual(_atributos(select)['id'], 'campo-acts0tipo_sugerido')
        opcoes = _descendentes(select, 'option', 'value')
        self.assertEqual([_atributos(o)['value'] for o in opcoes],
                         ['', *rotulos.TIPOS_SUGERIDOS])
        self.assertEqual([_texto_fora_de_details(o) for o in opcoes[1:]],
                         [o['display'] for o in resposta.context['opcoes_tipo_sugerido']])
        selecionadas = [o for o in opcoes if 'selected' in _atributos(o)]
        self.assertEqual(len(selecionadas), 1)
        self.assertEqual(_atributos(selecionadas[0])['value'], 'averbacao')
        campo = next(c for c in resposta.context['campos'] if c.eh_tipo_sugerido)
        self.assertEqual(_valor_do_select(select), campo.tipo_exibido)
        self.assertFalse(_descendentes(card, 'input', 'data-campo-valor'))


class TipoSugeridoSelectTest(TelaRevisaoBase):
    """Tarefa B (#322/PR #327): o card do tipo é <select>, como o formulário.

    As opções DESENHADAS e o enum ACEITO no save vêm da MESMA fonte — o
    contrato A3 (``rotulos.TIPOS_SUGERIDOS``; revisão Opus, MUST-FIX #322).
    O rótulo de exibição vem do cadastro (``LancamentoTipo``) quando a
    linha existe e de ``TIPO_CHOICES`` quando não vem; valor efetivo fora
    do enum ganha opção extra selecionada em vez de cair na vazia. Valor
    fora do enum enviado no POST continua sendo recusado com 422.
    """

    def setUp(self):
        super().setUp()
        # Produção tem as 3 linhas de LancamentoTipo; a suíte não semeia.
        for tipo in ('averbacao', 'registro', 'inicio_matricula'):
            LancamentoTipo.objects.get_or_create(tipo=tipo)

    def _card(self, html):
        achado = re.search(
            r'<article[^>]*data-chave="/acts/0/tipo_sugerido".*?</article>',
            html, re.S,
        )
        self.assertIsNotNone(achado)
        return achado.group(0)

    def _tag_select(self, html):
        tags = [
            tag for tag in re.findall(r'<select[^>]*>', self._card(html))
            if 'data-campo-valor' in tag
        ]
        self.assertEqual(len(tags), 1, tags)
        return tags[0]

    def _salvar_tipo(self, decisao):
        return self.client.post(
            self.url('salvar_bloco_ocr'),
            data=json.dumps({
                'versao': self._tela().context['versao'],
                'decisoes': [{
                    'chave': '/acts/0/tipo_sugerido', 'incluir': True,
                    **decisao,
                }],
            }),
            content_type='application/json',
        )

    def test_card_do_tipo_e_select_com_as_opcoes_do_contrato(self):
        self._extracao()

        html = self._tela().content.decode()
        card = self._card(html)

        self.assertIn('data-tipo="enum"', self._tag_select(html))
        self.assertIn('<option value=""></option>', card)
        # Uma opção por código do contrato, com o display do cadastro.
        for codigo in rotulos.TIPOS_SUGERIDOS:
            self.assertIn(f'<option value="{codigo}"', card)
        for _codigo, display in LancamentoTipo.TIPO_CHOICES:
            self.assertIn(f'>{display}</option>', card)
        # Selecionado = tipo_exibido da view (aqui o rótulo 'Av-1' resolve
        # 'averbacao', concordando com a sugestão).
        self.assertIn('<option value="averbacao" selected>', card)
        # O select é o único editor da chave: nada de input de texto.
        self.assertIsNone(re.search(r'<input[^>]*type="text"', card))
        self.assertNotIn('<textarea', card)

    def test_post_cada_opcao_desenhada_e_aceito(self):
        # MUST-FIX (revisão Opus): nenhum valor que o select oferece pode
        # dar 422 — opções e enum vêm da mesma fonte.
        extracao = self._extracao()

        for codigo in rotulos.TIPOS_SUGERIDOS:
            with self.subTest(codigo=codigo):
                salvar = self._salvar_tipo(
                    {'conferido': True, 'valor': codigo},
                )
                self.assertEqual(salvar.status_code, 200, salvar.content)
                campo = extracao.campos.get(chave='/acts/0/tipo_sugerido')
                self.assertEqual(
                    campo.valor_final if campo.valor_final is not None
                    else campo.normalized,
                    codigo,
                )

    def test_normalizado_sem_linha_no_cadastro_nao_perde_o_valor(self):
        # MUST-FIX (revisão Opus): 'inicio_matricula' está no contrato mas
        # sem linha no cadastro — antes, nenhuma opção era marcada, o
        # navegador enviava a vazia e o save apagava a sugestão. Agora a
        # opção sai de TIPO_CHOICES, selecionada, e o valor sobrevive.
        # P2-2 (#322/PR #327): com o tipo exibido resolvido pelo ato, o
        # rótulo 'Av-1' é neutralizado para a SUGESTÃO decidir — senão o
        # card mostraria 'averbacao' (o que a importação usaria) em vez
        # da sugestão 'inicio_matricula' que este teste exercita.
        extracao = self._extracao()
        extracao.campos.filter(chave='/acts/0/tipo_sugerido').update(
            normalized='inicio_matricula',
        )
        extracao.campos.filter(
            chave__in=('/acts/0', '/acts/0/rotulo'),
        ).update(normalized=None, raw=None, valor_final=None)
        LancamentoTipo.objects.filter(tipo='inicio_matricula').delete()

        html = self._tela().content.decode()
        card = self._card(html)
        self.assertIn('<option value="inicio_matricula" selected>', card)
        self.assertIn('>Início de Matrícula</option>', card)

        salvar = self._salvar_tipo(
            {'conferido': True, 'valor': 'inicio_matricula'},
        )
        self.assertEqual(salvar.status_code, 200, salvar.content)
        campo = extracao.campos.get(chave='/acts/0/tipo_sugerido')
        # O design envia o MESMO valor do normalized: valor_final fica None
        # por desenho e a decisão vive em escolha_explicita.
        self.assertIsNone(campo.valor_final)
        self.assertTrue(campo.escolha_explicita)
        self.assertEqual(
            campo.valor_final if campo.valor_final is not None
            else campo.normalized,
            'inicio_matricula',
        )

        # Save seguinte conferindo sem valor: o efetivo permanece.
        salvar = self._salvar_tipo({'conferido': True})
        self.assertEqual(salvar.status_code, 200, salvar.content)
        campo = extracao.campos.get(chave='/acts/0/tipo_sugerido')
        self.assertEqual(
            campo.valor_final if campo.valor_final is not None
            else campo.normalized,
            'inicio_matricula',
        )

    def test_select_seleciona_valor_final_revisado(self):
        extracao = self._extracao()
        extracao.campos.filter(chave='/acts/0/tipo_sugerido').update(
            valor_final='registro', status_revisao='editado',
        )

        html = self._tela().content.decode()

        self.assertIn('<option value="registro" selected>', self._card(html))
        self.assertNotIn(
            '<option value="averbacao" selected>', self._card(html),
        )

    def test_select_mostra_o_tipo_resolvido_do_ato(self):
        # P2-2 (#322/PR #327): rótulo 'Av-5' × sugestão 'registro' sem
        # decisão do revisor — o card mostra o MESMO tipo que pendências,
        # prévia e importação resolvem (o rótulo vence), não o normalized
        # cru: o card não pode exibir um tipo e a importação usar outro.
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['rotulo'] = {
            'raw': 'Av-5', 'normalized': 'Av-5', 'confianca': 0.95,
            'requer_revisao': False,
        }
        self._extracao(payload)

        html = self._tela().content.decode()
        card = self._card(html)

        self.assertIn('<option value="averbacao" selected>', card)
        self.assertNotIn('<option value="registro" selected>', card)

    def test_select_com_linha_descartada_mostra_o_tipo_do_rotulo(self):
        # P2 (#322/PR #327, rodada 10): linha de tipo DESCARTADA com edição
        # preservada ('registro') — ``_contexto_revisao`` remove a linha e
        # o resolvedor usa o rótulo 'Av-5'. A cópia antiga da precedência
        # na view mostrava o ``valor_final`` morto; o card tem que exibir
        # o que a importação usa ('averbacao'), nunca 'registro'.
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['rotulo'] = {
            'raw': 'Av-5', 'normalized': 'Av-5', 'confianca': 0.95,
            'requer_revisao': False,
        }
        extracao = self._extracao(payload)
        extracao.campos.filter(chave='/acts/0/tipo_sugerido').update(
            status_revisao='descartado', valor_final='registro',
        )

        html = self._tela().content.decode()
        card = self._card(html)

        self.assertIn('<option value="averbacao" selected>', card)
        self.assertNotIn('<option value="registro" selected>', card)

    def test_select_com_ato_descartado_preserva_o_tipo_salvo(self):
        # P2 Greptile / P3-1 Opus (#322/PR #327, rodada 11): aqui é o ATO
        # (/acts/0) que está descartado, não a linha de tipo. O card do
        # tipo CONTINUA na tela — a view só filtra LINHAS_IGNORADAS, o
        # template desenha o card com a classe ``descartado`` e o checkbox
        # de reinclusão. Rodada 12: ``resolucoes_de_tipo`` devolve a
        # entrada do ato descartado (MESMO resolvedor, contexto que ignora
        # só o descarte do próprio ato), então o select marca a escolha
        # explícita salva — antes dela, o select vinha EM BRANCO com tipo
        # salvo e o JS enviava valor='' no "Conferido" da reinclusão,
        # apagando o tipo (origem 'limpo').
        extracao = self._extracao()
        extracao.campos.filter(chave='/acts/0').update(
            status_revisao='descartado',
        )
        extracao.campos.filter(chave='/acts/0/tipo_sugerido').update(
            valor_final='averbacao', status_revisao='editado',
        )

        html = self._tela().content.decode()
        card = self._card(html)

        self.assertIn('<option value="averbacao" selected>', card)

    def test_select_com_ato_descartado_e_tipo_limpo_continua_vazio(self):
        # Rodada 11→12: no ato descartado o '' gravado É a decisão de
        # "sem tipo" — o resolvedor devolve origem 'limpo' (não cai no
        # normalized 'averbacao' nem no rótulo) e o select fica sem opção
        # marcada, como no ato presente.
        extracao = self._extracao()
        extracao.campos.filter(chave='/acts/0').update(
            status_revisao='descartado',
        )
        extracao.campos.filter(chave='/acts/0/tipo_sugerido').update(
            valor_final='', status_revisao='editado',
        )

        html = self._tela().content.decode()
        card = self._card(html)

        self.assertIn('<option value=""></option>', card)
        self.assertIsNone(re.search(r'<option[^>]*\sselected', card))

    def test_select_com_ato_descartado_mostra_o_tipo_do_rotulo(self):
        # Rodada 12 (review Opus r11, caso a): ato descartado SEM escolha
        # do revisor (normalized 'registro', valor_final nulo, sem flag) e
        # rótulo divergente 'Av-5'. O fallback da rodada 11 copiava a
        # precedência na view e exibia o normalized cru ('registro'); ao
        # reincluir e conferir, o JS enviaria esse valor, a flag viraria
        # True e a importação gravaria 'registro' — o rótulo deixaria de
        # vencer sem aviso. O card marca o que o MESMO resolvedor devolve
        # no contexto que ignora só o descarte do próprio ato.
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['rotulo'] = {
            'raw': 'Av-5', 'normalized': 'Av-5', 'confianca': 0.95,
            'requer_revisao': False,
        }
        extracao = self._extracao(payload)
        extracao.campos.filter(chave='/acts/0').update(
            status_revisao='descartado',
        )

        html = self._tela().content.decode()
        card = self._card(html)

        self.assertIn('<option value="averbacao" selected>', card)
        self.assertNotIn('<option value="registro" selected>', card)

    def test_select_com_ato_e_linha_de_tipo_descartados_mostra_o_rotulo(self):
        # Rodada 12 (review Opus r11, caso c): além do ato, a linha de
        # tipo está descartada com edição preservada ('registro'). O
        # descarte da linha de DENTRO continua valendo no contexto do ato
        # descartado — o resolvedor pula o valor_final morto e usa o
        # rótulo 'Av-5', a mesma semântica do ato presente com a linha de
        # tipo descartada.
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['rotulo'] = {
            'raw': 'Av-5', 'normalized': 'Av-5', 'confianca': 0.95,
            'requer_revisao': False,
        }
        extracao = self._extracao(payload)
        extracao.campos.filter(chave='/acts/0').update(
            status_revisao='descartado',
        )
        extracao.campos.filter(chave='/acts/0/tipo_sugerido').update(
            status_revisao='descartado', valor_final='registro',
        )

        html = self._tela().content.decode()
        card = self._card(html)

        self.assertIn('<option value="averbacao" selected>', card)
        self.assertNotIn('<option value="registro" selected>', card)

    def test_select_com_ato_descartado_e_valor_fora_do_contrato_mostra_o_resolvido(self):
        # Rodada 12 (review Opus r11, caso b): valor explícito FORA do
        # contrato (estado do backfill da 0009: flag marcada, valor_final
        # nulo, normalized 'transcricao') com rótulo 'R-3'. O fallback
        # exibia 'transcricao' — não marca opção do contrato nenhuma e
        # ainda ganhava opção extra; o 'Conferido' da reinclusão enviaria
        # '' e apagaria o tipo. O resolvedor cai no rótulo: marca
        # 'registro', sem opção extra de um valor que o save recusaria.
        payload = payload_averbacao(self.job.job_id)
        payload['acts'][0]['rotulo'] = {
            'raw': 'R-3', 'normalized': 'R-3', 'confianca': 0.95,
            'requer_revisao': False,
        }
        extracao = self._extracao(payload)
        extracao.campos.filter(chave='/acts/0').update(
            status_revisao='descartado',
        )
        extracao.campos.filter(chave='/acts/0/tipo_sugerido').update(
            normalized='transcricao', escolha_explicita=True,
            status_revisao='aceito', valor_final=None,
        )

        html = self._tela().content.decode()
        card = self._card(html)

        self.assertIn('<option value="registro" selected>', card)
        self.assertNotIn('transcricao', card)

    def test_select_com_valor_explicito_fora_do_contrato_mostra_o_resolvido(self):
        # P2 (#322/PR #327, rodada 10): 'transcricao' fora de
        # TIPOS_SUGERIDOS com escolha_explicita=True — estado que o
        # backfill da 0009 pode criar a partir de 'aceito'/'importado'
        # legados. O resolvedor NÃO usa esse valor (cai no rótulo), e o
        # card mostra o que a importação usa; sem opção extra de um tipo
        # que o próprio save recusaria com 422.
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['rotulo'] = {
            'raw': 'Av-5', 'normalized': 'Av-5', 'confianca': 0.95,
            'requer_revisao': False,
        }
        extracao = self._extracao(payload)
        extracao.campos.filter(chave='/acts/0/tipo_sugerido').update(
            normalized='transcricao', escolha_explicita=True,
            status_revisao='aceito', valor_final=None,
        )

        html = self._tela().content.decode()
        card = self._card(html)

        self.assertIn('<option value="averbacao" selected>', card)
        self.assertNotIn('transcricao', card)

    def test_select_com_tipo_limpo_nao_seleciona_opcao_nenhuma(self):
        # P2-1 + P2-2 (#322/PR #327): ``valor_final=''`` é tipo APAGADO —
        # decisão válida; nenhuma opção marcada (o navegador enviaria a
        # vazia) e a pendência de ``tipo_sugerido`` volta a bloquear.
        extracao = self._extracao()
        extracao.campos.filter(chave='/acts/0/tipo_sugerido').update(
            valor_final='', status_revisao='editado',
        )

        html = self._tela().content.decode()
        card = self._card(html)

        self.assertIn('<option value=""></option>', card)
        self.assertIsNone(re.search(r'<option[^>]*\sselected', card))

    def test_somente_leitura_desabilita_o_select(self):
        extracao = self._extracao()
        ExtracaoSugerida.objects.filter(pk=extracao.pk).update(
            finalizada_em=timezone.now(), finalizada_por=self.dono,
        )
        OcrJob.objects.filter(pk=self.job.pk).update(status=estados.REVISADO)

        html = self._tela().content.decode()

        self.assertIn(' disabled', self._tag_select(html))

    def test_post_registro_diferente_salva_valor_final(self):
        # SHOULD-FIX (revisão Opus): o POST com valor DIFERENTE do
        # normalized prova o salvamento — o sugerido aqui é 'averbacao'.
        extracao = self._extracao()

        salvar = self._salvar_tipo({'conferido': True, 'valor': 'registro'})

        self.assertEqual(salvar.status_code, 200, salvar.content)
        campo = extracao.campos.get(chave='/acts/0/tipo_sugerido')
        self.assertEqual(campo.valor_final, 'registro')
        self.assertEqual(campo.status_revisao, 'editado')
        self.assertTrue(campo.escolha_explicita)

    def test_post_mesmo_valor_marca_escolha_explicita(self):
        # Caso separado (SHOULD-FIX, revisão Opus): valor IGUAL ao sugerido
        # deixa o ``valor_final`` nulo, mas a flag marca que o revisor
        # passou pelo card — e é ela que vence o rótulo na importação.
        extracao = self._extracao()

        salvar = self._salvar_tipo({'conferido': True, 'valor': 'averbacao'})

        self.assertEqual(salvar.status_code, 200, salvar.content)
        campo = extracao.campos.get(chave='/acts/0/tipo_sugerido')
        self.assertIsNone(campo.valor_final)
        self.assertEqual(campo.status_revisao, 'aceito')
        self.assertTrue(campo.escolha_explicita)

    def test_post_fora_do_enum_e_422_sem_gravar(self):
        extracao = self._extracao()

        salvar = self.client.post(
            self.url('salvar_bloco_ocr'),
            data=json.dumps({
                'versao': self._tela().context['versao'],
                'decisoes': [{
                    'chave': '/acts/0/tipo_sugerido',
                    'incluir': True, 'conferido': True,
                    'valor': 'compra_e_venda',
                }],
            }),
            content_type='application/json',
        )

        self.assertEqual(salvar.status_code, 422, salvar.content)
        self.assertEqual(salvar.json()['erro'], 'valor_invalido')
        self.assertEqual(salvar.json()['chave'], '/acts/0/tipo_sugerido')
        # Sem refresh redundante: ``campos.get`` relê do banco (nit revisão).
        campo = extracao.campos.get(chave='/acts/0/tipo_sugerido')
        self.assertEqual(campo.normalized, 'averbacao')
        self.assertIsNone(campo.valor_final)
        self.assertEqual(campo.status_revisao, 'sugerido')


class LinhaIgnoradaSaveTest(TelaRevisaoBase):
    """Tarefa C #322 (revisão Opus): decisão sobre linha ignorada não é 500.

    Extração antiga já salvou ``/acts/0/valor_transacao``; a folha não tem
    mais destino (Tarefa C). Aba aberta antes do deploy pode reenviar o
    card: o save recusa com 422 ``linha_inexistente``, sem gravar nada — e
    o token da tela segue valendo para salvar OUTRO card (o token cobre
    todas as linhas, inclusive a ignorada).
    """

    def _extracao_antiga(self):
        extracao = self._extracao()
        CampoSugerido.objects.create(
            extracao=extracao,
            chave='/acts/0/valor_transacao',
            raw='R$ 150.000,00',
            normalized='150000.00',
            tipo_valor='decimal',
            status_revisao='aceito',
        )
        return extracao

    def test_post_na_linha_ignorada_e_422_sem_gravar(self):
        extracao = self._extracao_antiga()
        versao = self._tela().context['versao']

        salvar = self.client.post(
            self.url('salvar_bloco_ocr'),
            data=json.dumps({
                'versao': versao,
                'decisoes': [{
                    'chave': '/acts/0/valor_transacao',
                    'incluir': True, 'conferido': True, 'valor': '150000.00',
                }],
            }),
            content_type='application/json',
        )

        self.assertEqual(salvar.status_code, 422, salvar.content)
        self.assertEqual(salvar.json()['erro'], 'linha_inexistente')
        campo = extracao.campos.get(chave='/acts/0/valor_transacao')
        self.assertIsNone(campo.valor_final)
        # Nada foi gravado: o token da tela continua sendo o vigente.
        self.assertEqual(services.versao_bloco(extracao), versao)

    def test_salvar_outro_card_com_o_token_da_tela_e_200(self):
        self._extracao_antiga()
        versao = self._tela().context['versao']

        salvar = self.client.post(
            self.url('salvar_bloco_ocr'),
            data=json.dumps({
                'versao': versao,
                'decisoes': [{
                    'chave': '/document/numero',
                    'incluir': True, 'conferido': True,
                }],
            }),
            content_type='application/json',
        )

        self.assertEqual(salvar.status_code, 200, salvar.content)


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


class RevisaoSemAtosTelaTest(TelaTextoBase):
    """Issue #262: a tela oferece confirmação sem atos só com a flag ligada."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.dono)
        self.documento.tipo.tipo = 'matricula'
        self.documento.tipo.save(update_fields=['tipo'])
        self.job.paginas.filter(numero_pagina=1).update(texto_ocr=TEXTO_PAGINA_1)
        OcrJob.objects.filter(pk=self.job.pk).update(status=estados.EXTRAIDO)
        self.job.refresh_from_db()

    def _extracao_sem_atos(self):
        payload = payload_averbacao(self.job.job_id)
        payload['acts'] = []
        extracao = ExtracaoSugerida.objects.create(
            ocr_job=self.job, schema_version=SCHEMA_VERSION,
            payload=payload, payload_servico=payload, provider=PROVIDER,
        )
        CampoSugerido.objects.bulk_create(
            revisao.desnormalizar(extracao, payload, list(self.job.paginas.all())),
        )
        # Sem atos, o cabeçalho ainda precisa das escolhas de cartório.
        extracao.campos.filter(tipo_valor='cartorio').update(criar_novo=True)
        return extracao

    @override_settings(OCR_PERMITIR_FINALIZAR_SEM_ATOS=True)
    def test_flag_ligada_mostra_aviso_e_mantem_pendencia(self):
        self._extracao_sem_atos()

        resposta = self.client.get(self.url('campos_job_ocr'))
        html = resposta.content.decode()

        self.assertEqual(resposta.status_code, 200)
        self.assertIn('data-permitir-sem-atos="1"', html)
        self.assertIn('0 atos reconhecidos', html)
        self.assertIn('data-ocr-sem-atos', html)
        # A pendência continua visível: nunca é escondida.
        self.assertIn('Nenhum ato reconhecido neste documento', html)

    @override_settings(OCR_PERMITIR_FINALIZAR_SEM_ATOS=False)
    def test_flag_desligada_renderiza_como_hoje(self):
        self._extracao_sem_atos()

        resposta = self.client.get(self.url('campos_job_ocr'))
        html = resposta.content.decode()

        self.assertEqual(resposta.status_code, 200)
        self.assertNotIn('data-permitir-sem-atos', html)
        self.assertNotIn('0 atos reconhecidos', html)
        self.assertNotIn('data-ocr-sem-atos', html)
        self.assertIn('Nenhum ato reconhecido neste documento', html)

    @override_settings(OCR_PERMITIR_FINALIZAR_SEM_ATOS=True)
    def test_campo_obrigatorio_pendente_nao_mostra_confirmacao(self):
        # Issue #262: sem atos e com campo do documento pendente, a tela não
        # pode oferecer a confirmação que destravaria a finalização.
        payload = payload_averbacao(self.job.job_id)
        payload['acts'] = []
        payload['document'].pop('data')
        extracao = ExtracaoSugerida.objects.create(
            ocr_job=self.job, schema_version=SCHEMA_VERSION,
            payload=payload, payload_servico=payload, provider=PROVIDER,
        )
        CampoSugerido.objects.bulk_create(
            revisao.desnormalizar(extracao, payload, list(self.job.paginas.all())),
        )

        resposta = self.client.get(self.url('campos_job_ocr'))
        html = resposta.content.decode()

        self.assertEqual(resposta.status_code, 200)
        self.assertNotIn('data-permitir-sem-atos', html)
        self.assertNotIn('data-ocr-sem-atos', html)
        self.assertIn('Nenhum ato reconhecido neste documento', html)

    @override_settings(OCR_PERMITIR_FINALIZAR_SEM_ATOS=True)
    def test_comentario_do_template_nao_vaza_no_html(self):
        # Issue #262: o bloco de aviso usa {% comment %}; o texto não pode
        # aparecer como conteúdo da página.
        self._extracao_sem_atos()

        resposta = self.client.get(self.url('campos_job_ocr'))
        html = resposta.content.decode()

        self.assertEqual(resposta.status_code, 200)
        self.assertIn('data-permitir-sem-atos="1"', html)
        self.assertNotIn('sem fabricar atos nem esconder a ausência', html)


class DescreverPendenciaMotivosDoMotorTest(SimpleTestCase):
    def test_motivos_do_motor_tem_rotulo_e_acao(self):
        for motivo in (
            'revisao_pendente', 'decisao_perdida', 'match_invalidado',
            'valor_incompativel_destino', 'valor_acima_do_limite_destino',
        ):
            with self.subTest(motivo=motivo):
                d = revisao.descrever_pendencia(
                    {'chave': '/document/x', 'motivo': motivo},
                )
                self.assertNotEqual(d['rotulo'], motivo)
                self.assertTrue(d['acao'])

    def test_motivo_desconhecido_nao_vaza_codigo_cru(self):
        d = revisao.descrever_pendencia(
            {'chave': '/document/x', 'motivo': 'foo_bar'},
        )
        self.assertEqual(d['rotulo'], 'Pendência a revisar')
        self.assertEqual(d['acao'], 'revise o campo')
        self.assertEqual(d['motivo'], 'foo_bar')


class DescreverPendenciaLocalTest(SimpleTestCase):
    """``local`` identifica o campo citado pela pendência (Greptile P2, #317)."""

    def test_regras_mapeadas(self):
        casos = (
            ('/document/tipo', 'Documento — tipo'),
            ('/document/data', 'Documento — data'),
            ('/document/cartorio', 'Documento — cartório'),
            ('/acts/0/data', 'Ato 1 — data'),
            ('/acts/1/tipo_sugerido', 'Ato 2 — tipo'),
            ('/acts/0/cartorio_transmissao', 'Ato 1 — cartório de transmissão'),
            ('/acts/0/valor_transacao', 'Ato 1 — valor'),
            ('/acts/0/origem/cartorio', 'Ato 1 — cartório de origem'),
            ('/acts/1/partes/2', 'Ato 2 — parte 3'),
        )
        for chave, local in casos:
            with self.subTest(chave=chave):
                d = revisao.descrever_pendencia(
                    {'chave': chave, 'motivo': 'revisao_pendente'},
                )
                self.assertEqual(d['local'], local)

    def test_fallback_usa_ultimo_segmento_com_espacos(self):
        casos = (
            ('/acts/0/origem/livro', 'Ato 1 — livro'),
            ('/document/cri_atual', 'Documento — cri atual'),
        )
        for chave, local in casos:
            with self.subTest(chave=chave):
                d = revisao.descrever_pendencia(
                    {'chave': chave, 'motivo': 'revisao_pendente'},
                )
                self.assertEqual(d['local'], local)

    def test_campo_de_parte_mantem_o_prefixo_da_parte(self):
        d = revisao.descrever_pendencia(
            {'chave': '/acts/1/partes/2/nome', 'motivo': 'revisao_pendente'},
        )
        self.assertEqual(d['local'], 'Ato 2 — parte 3 — nome')

    def test_nenhum_ato_aponta_para_os_atos_do_documento(self):
        d = revisao.descrever_pendencia(
            {'chave': '/acts', 'motivo': 'nenhum_ato'},
        )
        self.assertEqual(d['local'], 'Documento — atos')

    def test_chave_motivo_rotulo_e_acao_permanecem(self):
        d = revisao.descrever_pendencia(
            {'chave': '/acts/0/data', 'motivo': 'obrigatorio_ausente'},
        )
        self.assertEqual(d, {
            'chave': '/acts/0/data',
            'motivo': 'obrigatorio_ausente',
            'local': 'Ato 1 — data',
            'rotulo': 'Campo obrigatório não preenchido',
            'acao': 'informe a data',
            'alvo': 'campo-acts0data',
        })

    def test_chave_nao_string_nao_levanta_excecao(self):
        # MUST-FIX Opus (#317): payload cru/legado pode trazer chave None ou
        # não-string; a descrição da pendência não pode derrubar a tela.
        for chave in (None, '', 42):
            with self.subTest(chave=chave):
                self.assertEqual(revisao._local_da_chave(chave), '')
        d = revisao.descrever_pendencia(
            {'chave': None, 'motivo': 'revisao_pendente'},
        )
        self.assertEqual(d['local'], '')
        self.assertEqual(d['rotulo'], 'Confira este valor')
        self.assertEqual(d['acao'], 'confirme ou corrija')

    def test_resto_vazio_nao_deixa_travessao_pendurado(self):
        # ``/acts/0/`` não pode virar "Ato 1 — " nem '' virar "Documento — ".
        casos = (
            ('/acts/0/', 'Ato 1'),
            ('/acts/1/', 'Ato 2'),
            ('/document/', 'Documento'),
            ('/acts/1/partes/2/', 'Ato 2 — parte 3'),
        )
        for chave, local in casos:
            with self.subTest(chave=chave):
                self.assertEqual(revisao._local_da_chave(chave), local)


class PendenciaSemLocalNoTemplateTest(SimpleTestCase):
    """Item de pendência sem ``local`` (dict cru) não imprime ': ' órfão."""

    def _html(self, pendencias):
        # ``user`` só porque o ``default:`` do base.html resolve seu argumento
        # sem o tratamento silencioso de variável ausente.
        return render_to_string('ia_ocr/revisao_campos.html', {
            'user': AnonymousUser(),
            'pendencias': pendencias,
        })

    def test_item_sem_local_nao_comeca_com_dois_pontos(self):
        html = self._html([{
                'chave': '/acts/0/data',
                'motivo': 'obrigatorio_ausente',
                'rotulo': 'Campo obrigatório não preenchido',
                'acao': 'informe a data',
                # sem ``local``: outro produtor de dict / payload legado
            }],
        )
        linha = re.search(
            r'<li class="pendencia"[^>]*>\s*(.*?)\s*<details>', html, re.S,
        ).group(1)
        self.assertIn(
            'Campo obrigatório não preenchido — informe a data', linha,
        )
        self.assertFalse(
            linha.startswith(': '), f'linha começa com ": ": {linha!r}',
        )

    def test_item_com_local_mantem_o_prefixo(self):
        html = self._html([{
            'chave': '/acts/0/data',
            'motivo': 'obrigatorio_ausente',
            'local': 'Ato 1 — data',
            'rotulo': 'Campo obrigatório não preenchido',
            'acao': 'informe a data',
        }])
        self.assertIn(
            'Ato 1 — data: Campo obrigatório não preenchido — informe a data',
            html,
        )
