"""
Issue #400 (v4b) — a análise digitada sobrevive ao retry e ao fluxo de duplicata.

P1 #3 do Greptile (PR #409): ``_form_data_do_post`` copiava só ``observacoes`` e
o template de confirmação de duplicata encaminhava só ``observacoes``. Um create
rejeitado (área ambígua) re-renderizava o formulário com a análise vazia, e a
importação de cadeia duplicada gravava o lançamento sem o bloco analítico que o
revisor tinha digitado.

A análise continua sendo do servidor (P1 #1, v4a): o valor que volta ao
textarea é o texto digitado — a autoria e a data nascem do usuário logado na
hora da gravação, nunca do cliente.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from dominial.models import Documento, Imovel, Lancamento
from dominial.services.observacoes_analise import (
    observacoes_da_requisicao,
)

from .test_issue_400_roundtrip_integracao import (
    ANALITICO,
    AUTOR,
    DATA,
    DOCUMENTAL,
    MARCADOR,
    Issue400RoundTripBase,
    _valor_do_textarea,
)

FECHAMENTO = '[/ANÁLISE]'


class Issue400AnaliseSobreviveAoRetryTest(Issue400RoundTripBase):
    """Create rejeitado por área ambígua devolve a análise no HTML."""

    def _post_area_ambigua(self, analise_texto=ANALITICO):
        dados = self._campos_comuns(DOCUMENTAL)
        dados['area'] = '1.000'  # ambíguo: parser único recusa (#396)
        dados['analise_texto'] = analise_texto
        return self.client.post(self.url_novo(), dados)

    def test_erro_de_area_ambigua_re_renderiza_a_analise_digitada(self):
        response = self._post_area_ambigua()

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertEqual(
            _valor_do_textarea(html, 'analise_texto').strip(), ANALITICO)
        # O textarea documental continua só com o documental.
        self.assertEqual(
            _valor_do_textarea(html, 'observacoes').strip(), DOCUMENTAL)
        self.assertFalse(Lancamento.objects.filter(documento=self.doc).exists())

    def test_reenvio_do_form_re_renderizado_grava_a_analise_uma_unica_vez(self):
        retry = self._post_area_ambigua()
        html = retry.content.decode()

        # O navegador reenvia exatamente os textareas re-renderizados.
        dados = self._campos_comuns(_valor_do_textarea(html, 'observacoes'))
        dados['analise_texto'] = _valor_do_textarea(html, 'analise_texto')
        dados['area'] = ''
        response = self.client.post(self.url_novo(), dados)

        self.assertEqual(
            response.status_code, 302, response.content.decode()[:800])
        lancamento = Lancamento.objects.get(documento=self.doc)
        self.assertEqual(lancamento.observacoes.count(MARCADOR), 1)
        self.assertIn(f'{MARCADOR} {ANALITICO}', lancamento.observacoes)
        self.assertEqual(lancamento.observacoes.count(FECHAMENTO), 1)


class Issue400AnaliseNaDuplicataTest(Issue400RoundTripBase):
    """Confirmar duplicata grava o lançamento COM a análise e o autor certo."""

    def _criar_cadeia_duplicada(self):
        imovel_origem = Imovel.objects.create(
            terra_indigena_id=self.tis, nome='FAZENDA ORIGEM',
            proprietario=self.pessoa, matricula='M-ORIG-400',
            tipo_documento_principal='transcricao', cartorio=self.cri)
        doc_origem = Documento.objects.create(
            imovel=imovel_origem, tipo=self.tipo_transcricao, numero='T9001',
            data='2026-08-31', cartorio=self.cri, livro='3H', folha='154')
        Lancamento.objects.create(
            documento=doc_origem, tipo=self.tipo_inicio,
            numero_lancamento='T9001', data='1950-03-10')
        return imovel_origem, doc_origem

    def _post_que_abre_a_duplicata(self, doc_origem):
        dados = self._campos_comuns(DOCUMENTAL)
        dados['origem_completa[]'] = [doc_origem.numero]
        dados['cartorio_origem[]'] = [str(self.cri.id)]
        dados['cartorio_origem_nome[]'] = [self.cri.nome]
        dados['analise_texto'] = ANALITICO
        return self.client.post(self.url_novo(), dados)

    def _url_importar(self):
        return reverse('importar_duplicata', kwargs={
            'tis_id': self.tis.id, 'imovel_id': self.imovel.id,
            'documento_id': self.doc.id})

    def test_pagina_de_confirmacao_encaminha_a_analise_digitada(self):
        _, doc_origem = self._criar_cadeia_duplicada()

        response = self._post_que_abre_a_duplicata(doc_origem)

        self.assertTemplateUsed(response, 'dominial/duplicata_importacao.html')
        html = response.content.decode()
        self.assertIn('name="analise_texto"', html)
        self.assertIn(f'value="{ANALITICO}"', html)
        self.assertFalse(Lancamento.objects.filter(documento=self.doc).exists())

    def test_confirmacao_grava_o_lancamento_com_bloco_e_autor(self):
        _, doc_origem = self._criar_cadeia_duplicada()
        duplicata = self._post_que_abre_a_duplicata(doc_origem)
        self.assertTemplateUsed(duplicata, 'dominial/duplicata_importacao.html')
        # Confirma que o template re-renderiza a análise no campo oculto.
        self.assertIn(
            f'name="analise_texto" value="{ANALITICO}"',
            duplicata.content.decode(),
        )

        dados = self._campos_comuns(DOCUMENTAL)
        dados.update({
            'documento_origem_id': str(doc_origem.id),
            'documentos_importaveis[]': [str(doc_origem.id)],
            'origem_completa[]': [doc_origem.numero],
            'cartorio_origem[]': [str(self.cri.id)],
            'cartorio_origem_nome[]': [self.cri.nome],
            'analise_texto': ANALITICO,
        })
        response = self.client.post(self._url_importar(), dados)

        self.assertEqual(
            response.status_code, 302, response.content.decode()[:800])
        lancamento = Lancamento.objects.get(documento=self.doc)
        self.assertIn(f'{MARCADOR} {ANALITICO}', lancamento.observacoes)
        self.assertIn(FECHAMENTO, lancamento.observacoes)
        self.assertEqual(lancamento.observacoes.count(FECHAMENTO), 1)
        # Autor = usuário logado, nunca o nome que o cliente mandar.
        self.assertIn(f'[ANÁLISE — {AUTOR} — {DATA}]', lancamento.observacoes)


class Issue400IdempotenciaDaAnaliseTest(TestCase):
    """Reenviar o mesmo bloco (mesmo em outro dia) não duplica a análise."""

    def _request(self, post, user):
        from types import SimpleNamespace
        return SimpleNamespace(POST=post, user=user)

    def test_bloco_identico_em_outro_dia_nao_duplica(self):
        user = User.objects.create_user(
            username='revisor', password='x', first_name='Fulano',
            last_name='de Tal')
        existente = (
            'documental\n\n'
            '[ANÁLISE — Fulano de Tal — 2026-11-20] conclusão antiga\n'
            '[/ANÁLISE]'
        )
        request = self._request({
            'observacoes': 'documental',
            'analise_texto': 'conclusão antiga',
        }, user)

        resultado = observacoes_da_requisicao(
            request, analise_existente=existente)

        self.assertEqual(resultado, existente)
        self.assertEqual(resultado.count('[/ANÁLISE]'), 1)

    def test_texto_novo_ainda_e_acrescentado(self):
        user = User.objects.create_user(
            username='revisor2', password='x', first_name='Fulano',
            last_name='de Tal')
        existente = (
            '[ANÁLISE — Fulano de Tal — 2026-11-20] conclusão antiga\n'
            '[/ANÁLISE]'
        )
        request = self._request({
            'observacoes': 'documental',
            'analise_texto': 'outra conclusão',
        }, user)

        resultado = observacoes_da_requisicao(
            request, analise_existente=existente)

        self.assertIn('conclusão antiga', resultado)
        self.assertIn('outra conclusão', resultado)
        self.assertEqual(resultado.count('[/ANÁLISE]'), 2)
