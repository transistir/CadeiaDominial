"""Teste do JS do card OCR via Node puro (sem dependências novas).

O harness ia_ocr/tests/js/ocr_card.test.js avalia static/dominial/js/
ocr_card.js num sandbox vm com DOM/fetch/timers mockados à mão. Aqui só
orquestramos o Node e falhamos com stdout/stderr na mensagem, para dar
evidência no CI (fecha o P2 "Polling lacks automated tests" do PR #279).
"""

import shutil
import subprocess
import unittest
from pathlib import Path

TESTE_JS = Path(__file__).resolve().parent / "js" / "ocr_card.test.js"


@unittest.skipUnless(shutil.which("node"), "node não instalado")
class TesteJsOcrCard(unittest.TestCase):
    def test_ocr_card_js_passa_no_harness_node(self):
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
