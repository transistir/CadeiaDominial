"""Teste do JS da tela de confirmação do texto OCR via Node puro (issue #261).

O harness ia_ocr/tests/js/ocr_texto.test.js avalia static/dominial/js/
ocr_texto.js num sandbox vm com DOM mínimo mockado à mão (mesmo padrão do card,
test_js_ocr_card.py). Aqui só orquestramos o Node e falhamos com stdout/stderr
na mensagem, para dar evidência no CI.
"""

import shutil
import subprocess
import unittest
from pathlib import Path

TESTE_JS = Path(__file__).resolve().parent / "js" / "ocr_texto.test.js"


@unittest.skipUnless(shutil.which("node"), "node não instalado")
class TesteJsOcrTexto(unittest.TestCase):
    def test_ocr_texto_js_passa_no_harness_node(self):
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
