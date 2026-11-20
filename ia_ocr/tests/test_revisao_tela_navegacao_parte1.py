"""Tela de revisão de campos (I-5) — migração VERBATIM de
``ia_ocr/tests/test_revisao_tela.py`` (Etapa 10 do plano de 400 linhas).

Parte 1 de 3 do corpo de ``RevisaoTelaTest`` (1.056 linhas não cabem em
um arquivo de 400). Classe SIMPLES (sem ``TestCase``): o discovery do
Django não a coleta; quem coleta é a fachada em
``test_revisao_tela_navegacao.py``. Corpos verbatim.
"""

import json
import re

from django.conf import settings
from django.shortcuts import resolve_url
from django.utils import timezone

from dominial.models import Pessoas
from ia_ocr import estados, revisao
from ia_ocr.models import ExtracaoSugerida, OcrJob

from .payloads_extracao import payload_averbacao, payload_registro
from .test_revisao_tela_base import _descendentes, _valor_do_select
from .test_ui_card_ocr import _atributos, _elementos

RAW_MALICIOSO = '<script>alert(1)</script>"><img onerror=1>'


class RevisaoTelaTestParte1:
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

