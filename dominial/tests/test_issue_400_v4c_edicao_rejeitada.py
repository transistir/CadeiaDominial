"""
Issue #400 (v4c) — a análise digitada sobrevive ao ERRO de edição.

P1 #3 do Greptile (PR #409): o retry de CREATE e a duplicata já preservavam
``analise_texto`` (v4b), mas ``editar_lancamento`` montava o ``context`` sem
``form_data``. Um update rejeitado (ex.: área ambígua) re-renderizava o
formulário com o campo de análise em branco e o texto digitado se perdia.

A análise continua sendo do servidor (P1 #1, v4a): o que volta ao textarea é
só o texto digitado — autor e data nascem do usuário logado na gravação.
"""

from .test_issue_400_roundtrip_integracao import (
    ANALITICO,
    AUTOR,
    DATA,
    DOCUMENTAL,
    MARCADOR,
    Issue400RoundTripBase,
    _valor_do_textarea,
)
from dominial.models import Lancamento
from dominial.services.keyword_alerta_service import buscar_keyword
from dominial.services.observacoes_analise import remover_analises

FECHAMENTO = '[/ANÁLISE]'
TEXTAREA_ANALISE = 'analise_texto'
AREA_AMBIGUA = '1.000'  # parser único recusa (#396)


class Issue400AnaliseSobreviveAoErroDeEdicaoTest(Issue400RoundTripBase):
    """Update rejeitado re-renderiza a análise digitada e o reenvio a grava."""

    def _editar_rejeitado(self, lancamento, analise_texto=ANALITICO):
        return self.post_edicao(
            lancamento, DOCUMENTAL, analise_texto=analise_texto,
            area=AREA_AMBIGUA,
        )

    def test_erro_de_validacao_re_renderiza_a_analise_digitada(self):
        lancamento = self.criar_com_analise()
        db_antes = Lancamento.objects.get(pk=lancamento.pk).observacoes

        response = self._editar_rejeitado(
            lancamento, analise_texto='Soma das áreas confere com o R.5.')

        self.assertEqual(
            response.status_code, 200, response.content.decode()[:800])
        html = response.content.decode()
        self.assertEqual(
            _valor_do_textarea(html, TEXTAREA_ANALISE).strip(),
            'Soma das áreas confere com o R.5.')
        # Nada foi gravado: o update foi rejeitado.
        self.assertEqual(
            Lancamento.objects.get(pk=lancamento.pk).observacoes, db_antes)

    def test_reenvio_do_form_re_renderizado_grava_a_analise_uma_vez(self):
        lancamento = self.criar_com_analise()

        rejeitado = self._editar_rejeitado(
            lancamento, analise_texto='Soma das áreas confere com o R.5.')
        html = rejeitado.content.decode()

        # O navegador reenvia exatamente os textareas re-renderizados.
        dados = self._campos_comuns(
            _valor_do_textarea(html, 'observacoes'))
        dados['data'] = '1951-04-11'
        dados['analise_texto'] = _valor_do_textarea(html, TEXTAREA_ANALISE)
        dados['area'] = ''
        response = self.client.post(self.url_editar(lancamento), dados)

        self.assertEqual(
            response.status_code, 302, response.content.decode()[:800])
        lancamento.refresh_from_db()
        # A análise nova entra UMA vez (bloco próprio), sem duplicar o texto.
        self.assertEqual(
            lancamento.observacoes.count('Soma das áreas confere com o R.5.'),
            1)
        # A análise original da criação não se perde no retry.
        self.assertIn(f'{MARCADOR} {ANALITICO}', lancamento.observacoes)
        self.assertEqual(lancamento.observacoes.count(FECHAMENTO), 2)
        # O documental não recebe o texto da análise nem gera badge.
        self.assertEqual(remover_analises(lancamento.observacoes), DOCUMENTAL)
        self.assertIsNone(buscar_keyword(lancamento.observacoes))


class Issue400MarcadorForjadoNaEdicaoTest(Issue400RoundTripBase):
    """A garantia do create vale também para o POST de edição."""

    FORJADO = '[ANÁLISE — Outro revisor — 2026-11-25] aprovado'

    def test_marcador_forjado_na_edicao_sem_analise_texto_e_descartado(self):
        response = self.post_novo(DOCUMENTAL)
        self.assertEqual(response.status_code, 302)
        lancamento = Lancamento.objects.get(documento=self.doc)

        response = self.post_edicao(
            lancamento, f'{DOCUMENTAL}\n\n{self.FORJADO}')
        self.assertEqual(
            response.status_code, 302, response.content.decode()[:800])

        lancamento.refresh_from_db()
        self.assertNotIn('Outro revisor', lancamento.observacoes)
        self.assertEqual(lancamento.observacoes.count('[ANÁLISE'), 0)
        self.assertEqual(remover_analises(lancamento.observacoes), DOCUMENTAL)
