"""Testes do número do lançamento no NAVEGADOR da revisão (I-14 / #341, M1).

Dois níveis, mesmos arquivos reais:

1. O harness ``ia_ocr/tests/js/formulario_real.test.js`` roda os JS de
   verdade (``lancamento_form.js`` + ``ocr_revisao_formulario.js``) contra
   um DOM mínimo — orquestração Node no padrão de ``test_js_ocr_revisao.py``.
2. ``NumeroCompostoNoNavegadorTest`` fecha o ciclo no Django: renderiza a
   página da revisão, semeia o harness com os values QUE O SERVIDOR EMITIU,
   devolve o que os dois scripts deixam nos campos e ENVIA isso como POST —
   o número gravado é o que o navegador de verdade enviaria. Sem o composto
   no HTML (fase 1), o JS gruda a sigla pura ("M237") e o POST salvaria
   "M237" em vez de "R1 M237" — é o MUST-FIX 1 do review.
"""

import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

from dominial.models import Lancamento

from .test_revisao_formulario_view import RevisaoFormularioBase, _Formulario, post_do_html

TESTE_JS = Path(__file__).resolve().parent / "js" / "formulario_real.test.js"
HARNESS_JS = Path(__file__).resolve().parent / "js" / "formulario_real.js"
AVISO_SEM_NODE = "AVISO: node ausente no PATH — teste de JS do número real PULADO"


class TesteJsFormularioReal(unittest.TestCase):
    def test_formulario_real_passa_no_harness_node(self):
        if shutil.which("node") is None:
            print(AVISO_SEM_NODE, file=sys.stderr)
            self.skipTest(AVISO_SEM_NODE)
        resultado = subprocess.run(
            ["node", str(TESTE_JS)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(
            resultado.returncode,
            0,
            "harness Node falhou (rc=%s)\n--- stdout ---\n%s\n--- stderr ---\n%s"
            % (resultado.returncode, resultado.stdout, resultado.stderr),
        )


def _rodar_no_navegador(pagina, **trocas):
    """O HTML renderizado → seed do harness → o que os JS reais deixam nos campos.

    O seed sai dos values que o servidor emitiu (``_Formulario`` os coleta
    por ``id``); ``modoEdicao`` vem do script inline que o template só gera
    com ``modo_edicao``. Devolve ``(resultado, seed)``.
    """
    if shutil.which("node") is None:
        print(AVISO_SEM_NODE, file=sys.stderr)
        raise unittest.SkipTest(AVISO_SEM_NODE)
    html = pagina.content.decode()
    formulario = _Formulario()
    formulario.feed(html)
    sigla = re.search(
        r'name="sigla_matricula"[^>]*value="([^"]*)"', html,
    )
    seed = {
        'tipo': (formulario.ids.get('tipo_lancamento') or {}).get('tipo'),
        'simples': formulario.ids.get('numero_lancamento_simples', ''),
        'composto': formulario.ids.get('numero_lancamento', ''),
        'sigla': sigla.group(1) if sigla else '',
        'modoEdicao': "classList.add('modo-edicao')" in html,
        'revisao': True,
        **trocas,
    }
    resultado = subprocess.run(
        ["node", str(HARNESS_JS)],
        input=json.dumps(seed),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert resultado.returncode == 0, resultado.stderr
    return json.loads(resultado.stdout), seed


class NumeroCompostoNoNavegadorTest(RevisaoFormularioBase):
    """M1 (#341): HTML → JS reais → POST → o número gravado."""

    def test_o_numero_do_registro_sobrevive_ao_js_e_e_salvo_como(self):
        pagina = self.client.get(self.url_ato(0))
        self.assertEqual(pagina.status_code, 200)

        resultado, seed = _rodar_no_navegador(pagina)

        # O que o servidor renderizou E o que o navegador enviaria.
        self.assertEqual(seed['composto'], 'R1 M237')
        self.assertEqual(resultado['erros'], [])
        self.assertEqual(resultado['composto'], 'R1 M237')
        self.assertEqual(resultado['simples'].strip(), '1')

        resposta = self.client.post(self.url_ato(0), post_do_html(
            pagina,
            numero_lancamento=resultado['composto'],
            numero_lancamento_simples=resultado['simples'],
        ))

        self.assertEqual(resposta.status_code, 302, self.mensagens(resposta))
        self.assertEqual(
            Lancamento.objects.get(documento=self.documento).numero_lancamento,
            'R1 M237',
        )

    def test_em_modo_de_edicao_o_numero_simples_e_preservado(self):
        # O contexto herdado do novo_lancamento liga modo_edicao a partir do
        # 2º lançamento: sem o composto no HTML, o JS apagava o número simples
        # a partir da sigla pura.
        Lancamento.objects.create(
            documento=self.documento, tipo=self.tipo_registro,
            numero_lancamento='R0 M237', data='2019-01-01',
        )
        pagina = self.client.get(self.url_ato(0))
        self.assertEqual(pagina.status_code, 200)

        resultado, seed = _rodar_no_navegador(pagina)

        self.assertTrue(seed['modoEdicao'])
        self.assertEqual(resultado['erros'], [])
        self.assertEqual(resultado['composto'], 'R1 M237')
        self.assertEqual(resultado['simples'].strip(), '1')

        resposta = self.client.post(self.url_ato(0), post_do_html(
            pagina,
            numero_lancamento=resultado['composto'],
            numero_lancamento_simples=resultado['simples'],
        ))

        self.assertEqual(resposta.status_code, 302, self.mensagens(resposta))
        self.assertEqual(
            Lancamento.objects.filter(documento=self.documento)
            .latest('pk').numero_lancamento,
            'R1 M237',
        )
