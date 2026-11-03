"""Teste do JS da extração automática via Node puro (sem dependências novas).

O harness `ia_ocr/tests/js/ocr_auto_extrair.test.js` avalia
`static/dominial/js/ocr_auto_extrair.js` num sandbox vm com DOM/fetch/timers
mockados à mão. Aqui só orquestramos o Node e falhamos com stdout/stderr na
mensagem, para dar evidência no CI (issue #314).
"""

import shutil
import subprocess
import sys
import unittest
from pathlib import Path

TESTE_JS = Path(__file__).resolve().parent / "js" / "ocr_auto_extrair.test.js"
AVISO_SEM_NODE = "AVISO: node ausente no PATH — teste de JS da extração automática PULADO"


class TesteJsOcrAutoExtrair(unittest.TestCase):
    def test_ocr_auto_extrair_js_passa_no_harness_node(self):
        if shutil.which("node") is None:
            # Pulo explícito: sem node, a cobertura de JS não roda e ninguém
            # deve achar que rodou (mesmo padrão de test_js_ocr_card.py).
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
