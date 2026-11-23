"""Runner do espelho JS do parser de área (#396).

O núcleo é Python (``dominial/utils/area_br.py``); este teste garante que o
aviso do formulário usa a MESMA regra, para o usuário não ser barrado no
backend por algo que o front deixou passar (ou vice-versa).
"""

import shutil
import subprocess
import unittest
from pathlib import Path

TESTE_JS = Path(__file__).parent / "js" / "area_br.test.js"


@unittest.skipUnless(shutil.which("node"), "node não instalado")
class AreaBrJsTest(unittest.TestCase):
    def test_area_js_passa_no_harness_node(self):
        resultado = subprocess.run(
            ["node", str(TESTE_JS)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(
            resultado.returncode, 0,
            f"stdout: {resultado.stdout}\nstderr: {resultado.stderr}",
        )
        self.assertIn("area_br.test.js: OK", resultado.stdout)
