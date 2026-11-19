"""Teste do JS da revisão dentro do formulário de lançamento (I-14 / #341).

O harness ``ia_ocr/tests/js/ocr_revisao_formulario.test.js`` carrega
``static/dominial/js/ocr_revisao_formulario.js`` no Node puro (sem
dependências) e confere: número da origem com ponto de milhar, selo de
evidência e navegação entre atos. Aqui só orquestramos o Node (mesmo padrão
de ``test_js_ocr_revisao.py``).
"""

import shutil
import subprocess
import sys
import unittest
from pathlib import Path

TESTE_JS = Path(__file__).resolve().parent / "js" / "ocr_revisao_formulario.test.js"
AVISO_SEM_NODE = "AVISO: node ausente no PATH — teste de JS do formulário da revisão PULADO"


class TesteJsOcrRevisaoFormulario(unittest.TestCase):
    def test_ocr_revisao_formulario_js_passa_no_harness_node(self):
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
