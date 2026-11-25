"""
Issue #400 (v4) — bloco analítico delimitado e descarte de marcador forjado.

``[ANÁLISE — autor — data] … [/ANÁLISE]`` dá fronteira explícita ao texto do
revisor: parágrafos internos não vazam como documental (P1 #2 do Greptile) e
marcador vindo do POST não vira autoria (P1 #1). Complementa
``test_issue_400_observacoes_analise.py`` (formato do marcador e autoria).
"""

from datetime import date
from types import SimpleNamespace

from django.contrib.auth.models import AnonymousUser
from django.test import SimpleTestCase
from django.utils import timezone

from dominial.services.keyword_alerta_service import buscar_keyword
from dominial.services.observacoes_analise import (
    AnaliseSemAutor,
    blocos_de_analise,
    observacoes_da_requisicao,
    registrar_analise,
    remover_analises,
    tem_analise,
)


class UsuarioDeTeste:
    """Usuário mínimo (espelho do helper do teste de marcador/autoria)."""

    is_authenticated = True

    def __init__(self, username='fulano', nome_completo=''):
        self.username = username
        self._nome_completo = nome_completo

    def get_full_name(self):
        return self._nome_completo

    def get_username(self):
        return self.username


class RemoverAnalisesTest(SimpleTestCase):
    def test_remove_bloco_analitico_e_preserva_documental(self):
        documental = 'Certidão pendente de registro na matrícula'
        com_analise = registrar_analise(
            documental, 'Vide Av.7; pendência é do cartório.',
            'fulano', date(2026, 11, 25),
        )

        self.assertEqual(remover_analises(com_analise), documental)

    def test_so_analise_vira_texto_vazio(self):
        self.assertEqual(
            remover_analises(
                '[ANÁLISE — fulano — 2026-11-25] Só análise.'
            ),
            '',
        )

    def test_preserva_todos_os_blocos_documentais(self):
        texto = (
            'Primeiro bloco documental.\n\n'
            '[ANÁLISE — fulano — 2026-11-25] Bloco analítico.\n[/ANÁLISE]\n\n'
            'Segundo bloco documental.'
        )

        self.assertEqual(
            remover_analises(texto),
            'Primeiro bloco documental.\n\nSegundo bloco documental.',
        )

    def test_remove_ate_o_fechamento_com_paragrafos_internos(self):
        # O fechamento cobre o bloco inteiro: nenhum parágrafo interno do
        # revisor sobra como documental (P1 #2 do Greptile).
        texto = (
            'Área remanescente de 55 ha\n\n'
            '[ANÁLISE — fulano — 2026-11-25] Soma confere.\n\n'
            'PENDENTE de certidão\n'
            '[/ANÁLISE]\n\n'
            'Certidão emitida em 2019.'
        )

        self.assertEqual(
            remover_analises(texto),
            'Área remanescente de 55 ha\n\nCertidão emitida em 2019.',
        )

    def test_bloco_legado_sem_fechamento_vai_ate_o_fim_do_texto(self):
        # Regra documentada: bloco anterior ao delimitador de fim (legado
        # v1–v3) não tem fronteira confiável — vale do marcador até o próximo
        # marcador ou o fim do texto.
        legado = (
            'Área remanescente de 55 ha\n\n'
            '[ANÁLISE — fulano — 2026-11-25] Soma confere.\n\n'
            'PENDENTE de certidão'
        )

        self.assertEqual(remover_analises(legado), 'Área remanescente de 55 ha')

    def test_legado_termina_no_proximo_marcador(self):
        texto = (
            '[ANÁLISE — fulano — 2026-11-25] Primeira.\n\n'
            '[ANÁLISE — fulano — 2026-11-26] Segunda.\n[/ANÁLISE]\n\n'
            'Documental no fim.'
        )

        self.assertEqual(remover_analises(texto), 'Documental no fim.')

    def test_texto_sem_analise_volta_intacto(self):
        documental = 'Atenção: área remanescente pendente de confirmação.'
        self.assertEqual(remover_analises(documental), documental)


class BlocosDeAnaliseTest(SimpleTestCase):
    def test_lista_os_blocos_do_banco_para_leitura(self):
        texto = registrar_analise(
            'Documental', 'Soma confere.', 'fulano', date(2026, 11, 25))

        self.assertEqual(
            blocos_de_analise(texto),
            ['[ANÁLISE — fulano — 2026-11-25] Soma confere.\n[/ANÁLISE]'],
        )

    def test_sem_analise_devolve_lista_vazia(self):
        self.assertEqual(blocos_de_analise('Documental puro'), [])
        self.assertEqual(blocos_de_analise(None), [])


class TemAnaliseTest(SimpleTestCase):
    def test_marcador_presente(self):
        self.assertTrue(
            tem_analise('[ANÁLISE — fulano — 2026-11-25] Texto.')
        )

    def test_bloco_com_paragrafos_internos_conta_como_um_bloco(self):
        texto = registrar_analise(
            'Documental', 'Soma confere.\n\nPENDENTE', 'fulano',
            date(2026, 11, 25),
        )

        self.assertTrue(tem_analise(texto))

    def test_texto_documental_que_fala_de_analise_nao_conta(self):
        self.assertFalse(
            tem_analise('Análise do cartório: área remanescente pendente.')
        )


class ObservacoesDaRequisicaoTest(SimpleTestCase):
    def _request(self, post, user=None):
        return SimpleNamespace(POST=post, user=user)

    def test_sem_analise_normaliza_e_limpa_o_documental(self):
        for valor, esperado in (
            (None, ''),
            ('', ''),
            ('  documental  ', 'documental'),
            ('linha 1\r\nlinha 2', 'linha 1\nlinha 2'),
        ):
            with self.subTest(valor=valor):
                request = self._request({'observacoes': valor})
                self.assertEqual(
                    observacoes_da_requisicao(request), esperado)

    def test_marcador_forjado_no_post_e_descartado(self):
        # P1 #1 do Greptile: o textarea documental não cria análise nem
        # autoria. O marcador digitado não chega ao banco.
        request = self._request({
            'observacoes': (
                'Área remanescente\n\n'
                '[ANÁLISE — Outro revisor — 2026-11-25] aprovado'
            ),
        })

        resultado = observacoes_da_requisicao(request)

        self.assertEqual(resultado, 'Área remanescente')
        self.assertNotIn('Outro revisor', resultado)
        self.assertFalse(tem_analise(resultado))

    def test_analise_em_branco_nao_gera_marcador(self):
        request = self._request(
            {'observacoes': 'documental', 'analise_texto': '   '},
            UsuarioDeTeste(),
        )
        self.assertEqual(observacoes_da_requisicao(request), 'documental')

    def test_com_analise_acrescenta_marcador_do_usuario_logado(self):
        request = self._request(
            {'observacoes': 'documental', 'analise_texto': 'conclusão'},
            UsuarioDeTeste(username='fulano', nome_completo='Fulano de Tal'),
        )

        self.assertEqual(
            observacoes_da_requisicao(request),
            'documental\n\n'
            f'[ANÁLISE — Fulano de Tal — {timezone.localdate().isoformat()}] '
            'conclusão\n[/ANÁLISE]',
        )

    def test_bloco_do_banco_e_reanexado_quando_o_post_so_traz_documental(self):
        # Editar outro campo não pode perder a análise já gravada.
        existente = (
            'documental\n\n'
            '[ANÁLISE — fulano — 2026-11-25] análise antiga\n[/ANÁLISE]'
        )
        request = self._request({'observacoes': 'documental'})

        self.assertEqual(
            observacoes_da_requisicao(request, analise_existente=existente),
            existente,
        )

    def test_bloco_do_banco_nao_autoriza_o_post_a_escolher_autor(self):
        existente = (
            '[ANÁLISE — fulano — 2026-11-25] análise antiga\n[/ANÁLISE]'
        )
        request = self._request({
            'observacoes': '[ANÁLISE — Outro revisor — 2026-11-25] forjada',
            'analise_texto': 'nova',
        }, UsuarioDeTeste(username='beltrano'))

        resultado = observacoes_da_requisicao(
            request, analise_existente=existente)

        self.assertNotIn('Outro revisor', resultado)
        self.assertIn('[ANÁLISE — fulano — 2026-11-25] análise antiga', resultado)
        self.assertIn(
            f'[ANÁLISE — beltrano — {timezone.localdate().isoformat()}] nova',
            resultado,
        )

    def test_analise_sem_autor_levanta_erro(self):
        request = self._request(
            {'observacoes': 'documental', 'analise_texto': 'conclusão'},
            AnonymousUser(),
        )

        with self.assertRaises(AnaliseSemAutor):
            observacoes_da_requisicao(request)

    def test_reenvio_do_mesmo_bloco_nao_duplica(self):
        existente = (
            '[ANÁLISE — fulano — 2026-11-25] conclusão\n[/ANÁLISE]'
        )
        request = self._request({'observacoes': 'documental'})

        self.assertEqual(
            observacoes_da_requisicao(request, analise_existente=existente),
            f'documental\n\n{existente}',
        )


class QuebrasDeLinhaTest(SimpleTestCase):
    """MUST-FIX 1 (#400 v2): o textarea posta CRLF; o contrato é ``\\n``.

    Sem normalizar, ``doc\\r\\n\\r\\n[ANÁLISE — …]`` vira um parágrafo único e o
    bloco do revisor volta a alimentar ``buscar_keyword``/``tem_analise``.
    """

    def _request(self, post, user=None):
        return SimpleNamespace(POST=post, user=user)

    def test_documental_sem_analise_tem_crlf_normalizado(self):
        request = self._request({'observacoes': 'linha 1\r\nlinha 2\rlinha 3'})

        self.assertEqual(
            observacoes_da_requisicao(request), 'linha 1\nlinha 2\nlinha 3')

    def test_documental_com_crlf_nao_duplica_o_bloco_analitico(self):
        existente = (
            '[ANÁLISE — fulano — 2026-11-25] análise antiga\n[/ANÁLISE]'
        )
        request = self._request(
            {'observacoes': 'documental\r\nlinha 2'},
            UsuarioDeTeste(),
        )

        self.assertEqual(
            observacoes_da_requisicao(request, analise_existente=existente),
            'documental\nlinha 2\n\n'
            '[ANÁLISE — fulano — 2026-11-25] análise antiga\n[/ANÁLISE]',
        )

    def test_remover_analises_cobre_linha_legada_gravada_com_crlf(self):
        legado = (
            'Área remanescente de 55 ha\r\n\r\n'
            '[ANÁLISE — fulano — 2026-11-25] PENDENTE de certidão'
        )

        self.assertEqual(remover_analises(legado), 'Área remanescente de 55 ha')

    def test_tem_analise_cobre_linha_legada_gravada_com_crlf(self):
        self.assertTrue(
            tem_analise(
                'documental\r\n\r\n[ANÁLISE — fulano — 2026-11-25] texto'
            )
        )

    def test_buscar_keyword_ignora_analise_legada_com_crlf(self):
        legado = (
            'Área remanescente\r\n\r\n'
            '[ANÁLISE — fulano — 2026-11-25] PENDENTE de certidão'
        )

        self.assertIsNone(buscar_keyword(legado))
