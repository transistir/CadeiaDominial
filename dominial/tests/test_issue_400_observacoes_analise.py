"""
Issue #400 (U-M237-08) — observações documentais × analíticas.

Fonte de verdade do desenho: ``docs/produto-3/ARQUITETURA_OCR_ASSISTIDO.md``
§5 (Q1=b). O campo único ``Lancamento.observacoes`` guarda os dois tipos de
conteúdo, mas a análise SEMPRE sai com autoria e data
(``[ANÁLISE — <autor> — AAAA-MM-DD]``) e o texto documental NUNCA recebe
prefixo. Sem migration nesta etapa.
"""

from datetime import date
from types import SimpleNamespace

from django.contrib.auth.models import AnonymousUser
from django.test import SimpleTestCase
from django.utils import timezone

from dominial.services.keyword_alerta_service import buscar_keyword
from dominial.services.observacoes_analise import (
    AnaliseSemAutor,
    MARCADOR_ANALISE_RE,
    ROTULO_ANALISE,
    marcador_analise,
    nome_do_autor,
    observacoes_da_requisicao,
    registrar_analise,
    remover_analises,
    tem_analise,
)


class UsuarioDeTeste:
    """Usuário mínimo: o módulo só usa ``get_full_name``/``get_username``."""

    is_authenticated = True

    def __init__(self, username='fulano', nome_completo=''):
        self.username = username
        self._nome_completo = nome_completo

    def get_full_name(self):
        return self._nome_completo

    def get_username(self):
        return self.username


class MarcadorAnaliseTest(SimpleTestCase):
    def test_rotulo_exportado(self):
        self.assertEqual(ROTULO_ANALISE, 'ANÁLISE')

    def test_formato_exato_com_data_explicita(self):
        self.assertEqual(
            marcador_analise('fulano', date(2026, 11, 25)),
            '[ANÁLISE — fulano — 2026-11-25]',
        )

    def test_data_default_e_a_data_local_iso(self):
        self.assertEqual(
            marcador_analise('fulano'),
            f'[ANÁLISE — fulano — {timezone.localdate().isoformat()}]',
        )

    def test_regex_reconhece_o_marcador_e_captura_autor_e_data(self):
        casamento = MARCADOR_ANALISE_RE.match(
            '[ANÁLISE — Fulano de Tal — 2026-11-25] Soma confere.'
        )

        self.assertIsNotNone(casamento)
        self.assertEqual(casamento.group('autor'), 'Fulano de Tal')
        self.assertEqual(casamento.group('data'), '2026-11-25')

    def test_regex_nao_casa_texto_documental(self):
        self.assertIsNone(
            MARCADOR_ANALISE_RE.match('Área remanescente de 55 ha 69 a 85 ca')
        )


class AutorTest(SimpleTestCase):
    def test_nome_completo_tem_prioridade(self):
        usuario = UsuarioDeTeste(username='fulano', nome_completo='  Fulano de Tal  ')
        self.assertEqual(nome_do_autor(usuario), 'Fulano de Tal')

    def test_sem_nome_completo_usa_username(self):
        self.assertEqual(nome_do_autor(UsuarioDeTeste(username='fulano')), 'fulano')

    def test_anonimo_e_none_nao_tem_autor(self):
        self.assertIsNone(nome_do_autor(None))
        self.assertIsNone(nome_do_autor(AnonymousUser()))


class RegistrarAnaliseTest(SimpleTestCase):
    def test_autor_ausente_ou_so_espacos_levanta_erro(self):
        for autor in (None, '', '   '):
            with self.subTest(autor=autor):
                with self.assertRaises(AnaliseSemAutor):
                    registrar_analise('documental', 'texto analítico', autor)

    def test_data_invalida_levanta_erro(self):
        for data in ('25/11/2026', '2026-11', 'ontem'):
            with self.subTest(data=data):
                with self.assertRaises(AnaliseSemAutor):
                    marcador_analise('fulano', data)

    def test_texto_analitico_vazio_nao_prefixa_o_documental(self):
        documental = '  Área remanescente de 55 ha 69 a 85 ca  '
        for vazio in ('', '   ', None):
            with self.subTest(vazio=vazio):
                self.assertEqual(
                    registrar_analise(documental, vazio, 'fulano'),
                    documental,
                )

    def test_analise_vazia_sem_autor_nao_levanta_erro(self):
        # Sem texto não há análise: a ausência de autor é irrelevante.
        self.assertEqual(registrar_analise('documental', '', None), 'documental')

    def test_documental_e_analitica_saem_em_blocos_separados(self):
        resultado = registrar_analise(
            '  Área remanescente de 55 ha  ',
            '  Soma das áreas confere com o R.5.  ',
            'fulano',
            date(2026, 11, 25),
        )

        self.assertEqual(
            resultado,
            'Área remanescente de 55 ha\n\n'
            '[ANÁLISE — fulano — 2026-11-25] Soma das áreas confere com o R.5.',
        )

    def test_documental_vazio_gera_so_o_bloco_analitico(self):
        for documental in ('', '   ', None):
            with self.subTest(documental=documental):
                self.assertEqual(
                    registrar_analise(
                        documental, 'Av.7 encerra a matrícula.',
                        'fulano', date(2026, 11, 25),
                    ),
                    '[ANÁLISE — fulano — 2026-11-25] Av.7 encerra a matrícula.',
                )


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
            '[ANÁLISE — fulano — 2026-11-25] Bloco analítico.\n\n'
            'Segundo bloco documental.'
        )

        self.assertEqual(
            remover_analises(texto),
            'Primeiro bloco documental.\n\nSegundo bloco documental.',
        )

    def test_texto_sem_analise_volta_intacto(self):
        documental = 'Atenção: área remanescente pendente de confirmação.'
        self.assertEqual(remover_analises(documental), documental)


class TemAnaliseTest(SimpleTestCase):
    def test_marcador_presente(self):
        self.assertTrue(
            tem_analise('[ANÁLISE — fulano — 2026-11-25] Texto.')
        )

    def test_texto_documental_que_fala_de_analise_nao_conta(self):
        self.assertFalse(
            tem_analise('Análise do cartório: área remanescente pendente.')
        )


class ObservacoesDaRequisicaoTest(SimpleTestCase):
    def _request(self, post, user=None):
        return SimpleNamespace(POST=post, user=user)

    def test_sem_analise_devolve_o_post_exatamente_como_veio(self):
        for valor in (None, '', '  documental  '):
            with self.subTest(valor=valor):
                request = self._request({'observacoes': valor})
                self.assertEqual(observacoes_da_requisicao(request), valor)

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
            'conclusão',
        )

    def test_analise_sem_autor_levanta_erro(self):
        request = self._request(
            {'observacoes': 'documental', 'analise_texto': 'conclusão'},
            AnonymousUser(),
        )

        with self.assertRaises(AnaliseSemAutor):
            observacoes_da_requisicao(request)


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
        request = self._request(
            {
                'observacoes': (
                    'documental\r\n\r\n'
                    '[ANÁLISE — fulano — 2026-11-25] análise antiga'
                ),
                'analise_texto': 'análise nova',
            },
            UsuarioDeTeste(),
        )

        self.assertEqual(
            observacoes_da_requisicao(request),
            'documental\n\n'
            '[ANÁLISE — fulano — 2026-11-25] análise antiga\n\n'
            f'[ANÁLISE — fulano — {timezone.localdate().isoformat()}] '
            'análise nova',
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
