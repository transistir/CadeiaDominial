"""Testes do travador de 400 linhas por arquivo (check_file_size.py).

Roda com: python -m unittest discover -s scripts/tests -v
Sem dependências externas — só stdlib.
"""

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import check_file_size  # noqa: E402


class VerificacaoTamanhoBase(unittest.TestCase):
    """Base com helpers para montar árvores de arquivos temporárias."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.raiz = Path(self._tmp.name)

    def escrever(self, relativo, linhas):
        """Grava um arquivo com `linhas` linhas dentro da raiz temporária."""
        caminho = self.raiz / relativo
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text("linha\n" * linhas, encoding="utf-8")
        return caminho

    def gravar_baseline(self, arquivos, limite=400):
        """Grava um baseline no lugar onde o script espera encontrá-lo."""
        pasta = self.raiz / "scripts"
        pasta.mkdir(parents=True, exist_ok=True)
        conteudo = json.dumps({"limit": limite, "files": arquivos}, indent=2) + "\n"
        (pasta / "file_size_baseline.json").write_text(conteudo, encoding="utf-8")

    def ler_baseline(self):
        caminho = self.raiz / "scripts" / "file_size_baseline.json"
        return json.loads(caminho.read_text(encoding="utf-8"))

    def rodar(self, *args):
        """Executa main() capturando stdout; devolve (exit_code, saída)."""
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            codigo = check_file_size.main(list(args), raiz=self.raiz)
        return codigo, buffer.getvalue()


class TestLimiteBasico(VerificacaoTamanhoBase):
    def test_arquivo_novo_de_401_linhas_falha(self):
        self.escrever("app/novo.py", 401)
        codigo, saida = self.rodar()
        self.assertEqual(codigo, 1)
        self.assertIn("VIOLACAO:", saida)
        self.assertIn("novo arquivo acima do limite", saida)
        self.assertIn("app/novo.py", saida)

    def test_arquivo_de_400_linhas_passa(self):
        self.escrever("app/no_limite.py", 400)
        codigo, saida = self.rodar()
        self.assertEqual(codigo, 0)
        self.assertNotIn("VIOLACAO:", saida)
        self.assertIn("violacoes: 0", saida)

    def test_limite_custom_via_flag(self):
        self.escrever("app/curto.py", 11)
        codigo, saida = self.rodar("--limit", "10")
        self.assertEqual(codigo, 1)
        self.assertIn("novo arquivo acima do limite", saida)


class TestBaselineLegado(VerificacaoTamanhoBase):
    def test_arquivo_legado_que_cresceu_falha(self):
        self.escrever("app/legado.py", 402)
        self.gravar_baseline({"app/legado.py": 401})
        codigo, saida = self.rodar()
        self.assertEqual(codigo, 1)
        self.assertIn("VIOLACAO:", saida)
        self.assertIn("arquivo legado cresceu (baseline 401 → atual 402)", saida)

    def test_arquivo_legado_que_encolheu_passa_e_sugere(self):
        self.escrever("app/legado.py", 401)
        self.gravar_baseline({"app/legado.py": 500})
        codigo, saida = self.rodar()
        self.assertEqual(codigo, 0)
        self.assertNotIn("VIOLACAO:", saida)
        self.assertIn("pode atualizar o baseline (500 → 401)", saida)

    def test_arquivo_legado_igual_ao_baseline_passa(self):
        self.escrever("app/legado.py", 450)
        self.gravar_baseline({"app/legado.py": 450})
        codigo, saida = self.rodar()
        self.assertEqual(codigo, 0)
        self.assertNotIn("VIOLACAO:", saida)

    def test_entrada_orfa_no_baseline_falha(self):
        # O arquivo listado não existe mais na árvore.
        self.escrever("app/existente.py", 100)
        self.gravar_baseline({"app/apagado.py": 500})
        codigo, saida = self.rodar()
        self.assertEqual(codigo, 1)
        self.assertIn("VIOLACAO:", saida)
        self.assertIn("entrada órfã no baseline; rode --write-baseline", saida)
        self.assertIn("app/apagado.py", saida)


class TestWriteBaseline(VerificacaoTamanhoBase):
    def test_grava_somente_acima_do_limite_e_check_seguinte_passa(self):
        self.escrever("app/grande.py", 401)
        self.escrever("app/pequeno.py", 300)
        codigo, saida = self.rodar("--write-baseline")
        self.assertEqual(codigo, 0)
        self.assertIn("1", saida)  # informa quantos arquivos foram gravados

        baseline = self.ler_baseline()
        self.assertEqual(baseline["limit"], 400)
        self.assertEqual(list(baseline["files"].keys()), ["app/grande.py"])
        self.assertEqual(baseline["files"]["app/grande.py"], 401)

        codigo, saida = self.rodar()
        self.assertEqual(codigo, 0)
        self.assertNotIn("VIOLACAO:", saida)

    def test_baseline_ordenado_e_com_newline_final(self):
        self.escrever("app/z.py", 401)
        self.escrever("app/a.py", 402)
        self.rodar("--write-baseline")
        bruto = (self.raiz / "scripts" / "file_size_baseline.json").read_text(
            encoding="utf-8"
        )
        self.assertTrue(bruto.endswith("\n"))
        baseline = json.loads(bruto)
        self.assertEqual(list(baseline["files"].keys()), ["app/a.py", "app/z.py"])


class TestIgnorados(VerificacaoTamanhoBase):
    def test_extensoes_nao_listadas_nao_contam(self):
        self.escrever("app/notas.txt", 500)
        self.escrever("app/leiame.md", 500)
        codigo, saida = self.rodar()
        self.assertEqual(codigo, 0)
        self.assertIn("acima do limite: 0", saida)

    def test_diretorios_ignorados_nao_contam(self):
        self.escrever("app/migrations/antigo.py", 500)
        self.escrever(".git/hooks/amostra.py", 500)
        self.escrever("app/node_modules/pacote.js", 500)
        self.escrever("app/__pycache__/compilado.py", 500)
        self.escrever("app/staticfiles/estilo.css", 500)
        self.escrever("app/old/copia.html", 500)
        self.escrever("app/venv/lib/dependencia.py", 500)
        self.escrever("app/dist/saida.js", 500)
        self.escrever("app/build/gerado.js", 500)
        self.escrever("app/.venv/lib/dependencia.py", 500)
        codigo, saida = self.rodar()
        self.assertEqual(codigo, 0)
        self.assertIn("acima do limite: 0", saida)

    def test_extensoes_vigiadas_contam(self):
        self.escrever("app/script.js", 401)
        self.escrever("app/tela.html", 402)
        self.escrever("app/estilo.css", 403)
        self.escrever("app/modulo.py", 404)
        codigo, saida = self.rodar()
        self.assertEqual(codigo, 1)
        self.assertEqual(saida.count("VIOLACAO:"), 4)


class TestQuiet(VerificacaoTamanhoBase):
    def test_quiet_imprime_somente_violacoes(self):
        self.escrever("app/grande.py", 401)
        self.escrever("app/pequeno.py", 10)
        codigo, saida = self.rodar("--quiet")
        self.assertEqual(codigo, 1)
        self.assertIn("VIOLACAO:", saida)
        self.assertNotIn("arquivos:", saida)
        self.assertNotIn("violacoes:", saida)

    def test_quiet_suprime_sugestao_de_encolhimento(self):
        self.escrever("app/legado.py", 401)
        self.gravar_baseline({"app/legado.py": 500})
        codigo, saida = self.rodar("--quiet")
        self.assertEqual(codigo, 0)
        self.assertNotIn("pode atualizar o baseline", saida)


class TestConstantes(unittest.TestCase):
    def test_limite_padrao(self):
        self.assertEqual(check_file_size.LIMITE, 400)


if __name__ == "__main__":
    unittest.main()
