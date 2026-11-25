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
    blocos_de_analise,
    marcador_analise,
    nome_do_autor,
    normalizar_quebras,
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

    def test_autor_com_caractere_do_marcador_ou_quebra_levanta_erro(self):
        # O formato é contrato: autor não pode forjar nem quebrar o marcador.
        for autor in ('fulano — x', 'fulano]', '[ANÁLISE', 'fulano\nforjado',
                      'fulano\rforjado'):
            with self.subTest(autor=autor):
                with self.assertRaises(AnaliseSemAutor):
                    marcador_analise(autor, date(2026, 11, 25))

    def test_normalizar_quebras_converte_crlf_e_cr(self):
        self.assertEqual(normalizar_quebras('a\r\nb\rc'), 'a\nb\nc')
        self.assertEqual(normalizar_quebras(''), '')
        self.assertIsNone(normalizar_quebras(None))


class AutorTest(SimpleTestCase):
    def test_nome_completo_tem_prioridade(self):
        usuario = UsuarioDeTeste(username='fulano', nome_completo='  Fulano de Tal  ')
        self.assertEqual(nome_do_autor(usuario), 'Fulano de Tal')

    def test_sem_nome_completo_usa_username(self):
        self.assertEqual(nome_do_autor(UsuarioDeTeste(username='fulano')), 'fulano')

    def test_anonimo_e_none_nao_tem_autor(self):
        self.assertIsNone(nome_do_autor(None))
        self.assertIsNone(nome_do_autor(AnonymousUser()))

    def test_nome_com_caracteres_do_marcador_nao_derruba_a_gravacao(self):
        # #400 v4d: "Maria [FUNAI]" fazia marcador_analise levantar
        # AnaliseSemAutor na gravação (500). O nome sai sanitizado.
        usuario = UsuarioDeTeste(username='maria', nome_completo='Maria [FUNAI]')

        autor = nome_do_autor(usuario)

        self.assertEqual(autor, 'Maria FUNAI')
        self.assertEqual(
            marcador_analise(autor, date(2026, 11, 25)),
            '[ANÁLISE — Maria FUNAI — 2026-11-25]',
        )

    def test_nome_completo_so_com_invalidos_cai_para_o_username(self):
        usuario = UsuarioDeTeste(username='maria', nome_completo='[—]')
        self.assertEqual(nome_do_autor(usuario), 'maria')

    def test_quebra_de_linha_no_username_vira_espaco(self):
        usuario = UsuarioDeTeste(username='ma\nria', nome_completo='')
        self.assertEqual(nome_do_autor(usuario), 'ma ria')


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
            '[ANÁLISE — fulano — 2026-11-25] Soma das áreas confere com o R.5.\n'
            '[/ANÁLISE]',
        )

    def test_documental_vazio_gera_so_o_bloco_analitico(self):
        for documental in ('', '   ', None):
            with self.subTest(documental=documental):
                self.assertEqual(
                    registrar_analise(
                        documental, 'Av.7 encerra a matrícula.',
                        'fulano', date(2026, 11, 25),
                    ),
                    '[ANÁLISE — fulano — 2026-11-25] Av.7 encerra a matrícula.\n'
                    '[/ANÁLISE]',
                )

    def test_paragrafos_internos_ficam_dentro_do_bloco(self):
        # P1 #2 do Greptile: ``\n\n`` no texto do revisor não pode deixar o
        # segundo parágrafo solto como se fosse documental.
        resultado = registrar_analise(
            '', 'Soma confere.\n\nPENDENTE de certidão', 'fulano',
            date(2026, 11, 25),
        )

        self.assertEqual(
            resultado,
            '[ANÁLISE — fulano — 2026-11-25] Soma confere.\n\n'
            'PENDENTE de certidão\n[/ANÁLISE]',
        )
        self.assertEqual(remover_analises(resultado), '')

    def test_texto_do_revisor_nao_pode_fechar_o_bloco_por_conta_propria(self):
        # O fechamento e o marcador são do servidor: digitá-los no texto
        # analítico não pode encerrar o bloco e vazar o resto como documental.
        resultado = registrar_analise(
            '', 'fim forjado [/ANÁLISE] PENDENTE de certidão', 'fulano',
            date(2026, 11, 25),
        )

        self.assertEqual(remover_analises(resultado), '')
        self.assertIsNone(buscar_keyword(resultado))
