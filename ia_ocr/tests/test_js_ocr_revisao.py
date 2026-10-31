"""Teste do JS da revisão sem atos via Node puro (sem dependências novas).

O harness `ia_ocr/tests/js/ocr_revisao.test.js` avalia
`static/dominial/js/ocr_revisao.js` num sandbox vm com DOM/fetch/timers
mockados à mão. Aqui só orquestramos o Node e falhamos com stdout/stderr na
mensagem, para dar evidência no CI (issue #262 / I-5).
"""

import shutil
import subprocess
import sys
import unittest
from pathlib import Path

TESTE_JS = Path(__file__).resolve().parent / "js" / "ocr_revisao.test.js"
AVISO_SEM_NODE = "AVISO: node ausente no PATH — teste de JS da revisão PULADO"


class TesteJsOcrRevisao(unittest.TestCase):
    def test_ocr_revisao_js_passa_no_harness_node(self):
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
