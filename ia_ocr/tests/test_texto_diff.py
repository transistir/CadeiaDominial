"""Diff visual entre o texto do OCR e o texto confirmado (issue #261 / I-4, fatia 2).

Server-side, com difflib, sem dependência JS: `segmentos_diff` devolve
trechos (tipo, texto) e o template os renderiza com autoescape — nada de
`mark_safe` sobre texto de documento.
"""

import time

from django.test import SimpleTestCase

from ia_ocr import services
from ia_ocr.diff import ADICIONADO, IGUAL, REMOVIDO, segmentos_diff

from .base_texto import TelaTextoBase, _texto_completo
from .test_ui_card_ocr import _elementos


def _reconstruir(segmentos, *tipos):
    return ''.join(texto for tipo, texto in segmentos if tipo in tipos)


class SegmentosDiffTest(SimpleTestCase):
    def test_textos_iguais_geram_um_unico_trecho_igual(self):
        self.assertEqual(segmentos_diff('a b c', 'a b c'), [(IGUAL, 'a b c')])

    def test_dois_textos_vazios_nao_geram_trechos(self):
        self.assertEqual(segmentos_diff('', ''), [])

    def test_valor_trocado_gera_removido_e_adicionado(self):
        segmentos = segmentos_diff(
            'Matrícula 1234 do imóvel', 'Matrícula 1284 do imóvel'
        )

        self.assertEqual(segmentos, [
            (IGUAL, 'Matrícula '),
            (REMOVIDO, '1234'),
            (ADICIONADO, '1284'),
            (IGUAL, ' do imóvel'),
        ])

    def test_palavra_inserida_e_palavra_removida(self):
        self.assertEqual(
            segmentos_diff('a c', 'a b c'),
            [(IGUAL, 'a '), (ADICIONADO, 'b '), (IGUAL, 'c')],
        )
        self.assertEqual(
            segmentos_diff('a b c', 'a c'),
            [(IGUAL, 'a '), (REMOVIDO, 'b '), (IGUAL, 'c')],
        )

    def test_troca_de_varias_palavras_vira_um_bloco_so(self):
        """Trocas separadas só por espaço leem melhor como um bloco único."""
        segmentos = segmentos_diff('Fazenda Boa Vista', 'Fazenda Santa Maria')

        self.assertEqual(segmentos, [
            (IGUAL, 'Fazenda '),
            (REMOVIDO, 'Boa Vista'),
            (ADICIONADO, 'Santa Maria'),
        ])

    def test_trocas_em_linhas_diferentes_nao_sao_fundidas(self):
        """A quebra de linha separa os blocos: o diff mantém a granularidade."""
        segmentos = segmentos_diff('foo\nbar', 'baz\nqux')

        self.assertEqual(segmentos, [
            (REMOVIDO, 'foo'),
            (ADICIONADO, 'baz'),
            (IGUAL, '\n'),
            (REMOVIDO, 'bar'),
            (ADICIONADO, 'qux'),
        ])

    def test_texto_todo_novo_ou_todo_removido(self):
        self.assertEqual(segmentos_diff('', 'novo'), [(ADICIONADO, 'novo')])
        self.assertEqual(segmentos_diff('velho', ''), [(REMOVIDO, 'velho')])

    def test_segmentos_remontam_os_dois_textos(self):
        original = 'linha um\nlinha dois com erro\n\nlinha quatro'
        confirmado = 'linha um\nlinha dois corrigida\nlinha tres\nlinha quatro'

        segmentos = segmentos_diff(original, confirmado)

        self.assertEqual(_reconstruir(segmentos, IGUAL, REMOVIDO), original)
        self.assertEqual(_reconstruir(segmentos, IGUAL, ADICIONADO), confirmado)

    def test_trechos_vizinhos_do_mesmo_tipo_sao_fundidos(self):
        segmentos = segmentos_diff('a b c', 'x y z')

        tipos = [tipo for tipo, _texto in segmentos]
        self.assertEqual(tipos, [REMOVIDO, ADICIONADO])

    def test_texto_enorme_cai_para_diff_por_linha_sem_travar(self):
        """O diff por palavra é quadrático: acima do limite usa linhas."""
        original = '\n'.join(f'linha {n}' for n in range(30000))
        confirmado = original.replace('linha 15000\n', 'linha corrigida\n')

        inicio = time.monotonic()
        segmentos = segmentos_diff(original, confirmado)
        duracao = time.monotonic() - inicio

        self.assertLess(duracao, 10)
        self.assertEqual(_reconstruir(segmentos, IGUAL, REMOVIDO), original)
        self.assertEqual(_reconstruir(segmentos, IGUAL, ADICIONADO), confirmado)
        self.assertIn((REMOVIDO, 'linha 15000\n'), segmentos)
        self.assertIn((ADICIONADO, 'linha corrigida\n'), segmentos)

    def test_linhas_repetidas_acima_do_orcamento_usa_diff_grosseiro(self):
        """Linhas repetidas deixam o matcher quadrático: acima do orçamento de
        linhas o miolo vira um bloco só, sem a sequência de micro-blocos."""
        linhas = ['linha repetida\n'] * 5000
        alteradas = list(linhas)
        alteradas[1000] = 'linha corrigida\n'
        alteradas[4000] = 'outra linha corrigida\n'

        segmentos = segmentos_diff(''.join(linhas), ''.join(alteradas))

        self.assertEqual(
            [tipo for tipo, _texto in segmentos], [IGUAL, REMOVIDO, ADICIONADO, IGUAL]
        )
        self.assertEqual(segmentos[0][1], ''.join(linhas[:1000]))
        self.assertEqual(segmentos[1][1], ''.join(linhas[1000:4001]))
        self.assertEqual(segmentos[2][1], ''.join(alteradas[1000:4001]))
        self.assertEqual(segmentos[3][1], ''.join(linhas[4001:]))

    def test_diff_grosseiro_preserva_o_invariante(self):
        """Prefixo e sufixo comuns não se sobrepõem, mesmo com linhas repetidas."""
        linhas = ['linha repetida do texto\n'] * 3000 + ['fim sem quebra']
        espalhadas = list(linhas)
        espalhadas[500] = 'troca\n'
        espalhadas[2500] = 'outra troca\n'
        del espalhadas[2000:2010]
        espalhadas.insert(1500, 'linha inserida\n')
        original = ''.join(linhas)
        casos = {
            'trocas espalhadas': ''.join(espalhadas),
            'remoção de linhas repetidas': ''.join(linhas[:2500] + linhas[-1:]),
            'inserção no início': 'nova primeira linha\n' + original,
            'última linha sem quebra alterada': ''.join(linhas[:-1]) + 'fim alterado',
            'texto todo trocado': 'texto novo',
        }

        for caso, confirmado in casos.items():
            with self.subTest(caso):
                segmentos = segmentos_diff(original, confirmado)

                tipos = [tipo for tipo, _texto in segmentos]
                self.assertLessEqual(tipos.count(REMOVIDO), 1)
                self.assertLessEqual(tipos.count(ADICIONADO), 1)
                self.assertEqual(_reconstruir(segmentos, IGUAL, REMOVIDO), original)
                self.assertEqual(_reconstruir(segmentos, IGUAL, ADICIONADO), confirmado)

    def test_abaixo_do_orcamento_continua_detalhado(self):
        """Poucas linhas, ainda que longas, seguem no matcher: trocas separadas."""
        antes = 'igual antes ' * 1000 + '\n'
        meio = 'igual no meio ' * 1000 + '\n'
        depois = 'igual depois ' * 1000
        original = antes + 'velha um\n' + meio + 'velha dois\n' + depois
        confirmado = antes + 'nova um\n' + meio + 'nova dois\n' + depois

        segmentos = segmentos_diff(original, confirmado)

        self.assertEqual(segmentos, [
            (IGUAL, antes),
            (REMOVIDO, 'velha um\n'),
            (ADICIONADO, 'nova um\n'),
            (IGUAL, meio),
            (REMOVIDO, 'velha dois\n'),
            (ADICIONADO, 'nova dois\n'),
            (IGUAL, depois),
        ])


class DiffNaTelaTest(TelaTextoBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.dono)

    def test_pagina_sem_edicao_nao_mostra_diff(self):
        services.confirmar_pagina(self.job, 1, self.dono)

        resposta = self.client.get(self.url_tela(pagina=1))

        self.assertIsNone(resposta.context['diff'])
        self.assertEqual(
            _elementos(resposta.content.decode(), 'section', presentes=('data-ocr-diff',)),
            [],
        )

    def test_pagina_editada_e_confirmada_mostra_diff_com_remocoes_e_acrescimos(self):
        self.job.paginas.filter(numero_pagina=1).update(
            texto_ocr='Matrícula 1234 do imóvel'
        )
        services.confirmar_pagina(
            self.job, 1, self.dono, texto='Matrícula 1284 do imóvel'
        )

        resposta = self.client.get(self.url_tela(pagina=1))
        conteudo = resposta.content.decode()

        secao = _elementos(conteudo, 'section', presentes=('data-ocr-diff',))
        self.assertEqual(len(secao), 1)
        # Só o <pre> do diff: a legenda também usa <del>/<ins> de exemplo.
        pre = _elementos(conteudo, 'pre', presentes=('data-ocr-diff-texto',))
        self.assertEqual(len(pre), 1)
        filhos = [no for no in pre[0].children if not isinstance(no, str)]
        self.assertEqual(
            [(no.name, _texto_completo(no)) for no in filhos],
            [('del', '1234'), ('ins', '1284')],
        )

    def test_rascunho_editado_tambem_mostra_diff(self):
        services.editar_pagina(self.job, 1, 'Texto sintético da página UM')

        resposta = self.client.get(self.url_tela(pagina=1))

        self.assertIsNotNone(resposta.context['diff'])
        self.assertEqual(
            len(_elementos(resposta.content.decode(), 'section', presentes=('data-ocr-diff',))),
            1,
        )

    def test_diff_escapa_o_texto_do_documento(self):
        services.confirmar_pagina(
            self.job, 1, self.dono, texto='<script>alert(1)</script> página'
        )

        resposta = self.client.get(self.url_tela(pagina=1))

        self.assertNotContains(resposta, '<script>alert(1)</script>')
        self.assertContains(resposta, '&lt;script&gt;alert(1)&lt;/script&gt;')

    def test_legenda_do_diff_explica_remocao_e_acrescimo_em_texto(self):
        services.confirmar_pagina(self.job, 1, self.dono, texto='outro texto')

        resposta = self.client.get(self.url_tela(pagina=1))

        self.assertContains(resposta, 'removido do OCR')
        self.assertContains(resposta, 'acrescentado na revisão')
