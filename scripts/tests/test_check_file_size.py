"""Testes do travador de 400 linhas por arquivo (check_file_size.py).

Roda com: python -m unittest discover -s scripts/tests -v
Sem dependências externas — só stdlib (e git nos testes de --base-ref).
"""

import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
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
        """Executa main() capturando stdout e stderr; devolve (código, out, err)."""
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            codigo = check_file_size.main(list(args), raiz=self.raiz)
        return codigo, out.getvalue(), err.getvalue()

    def iniciar_git(self):
        """Repo git na raiz temporária; devolve função `_git(*args)`."""
        def _git(*args):
            subprocess.run(
                ["git", "-C", str(self.raiz), *args],
                check=True,
                capture_output=True,
            )

        _git("init", "-q")
        _git("config", "user.email", "teste@local")
        _git("config", "user.name", "Teste")
        return _git

    def commit_base(self, arquivos, linhas=450):
        """Commit "base" com app/legado.py + baseline; devolve `_git`."""
        _git = self.iniciar_git()
        self.escrever("app/legado.py", linhas)
        self.gravar_baseline(arquivos)
        _git("add", "-A")
        _git("commit", "-qm", "base")
        return _git


class TestLimiteBasico(VerificacaoTamanhoBase):
    def test_arquivo_novo_de_401_linhas_falha(self):
        self.escrever("app/novo.py", 401)
        codigo, saida, _ = self.rodar()
        self.assertEqual(codigo, 1)
        self.assertIn("VIOLACAO:", saida)
        self.assertIn("novo arquivo acima do limite", saida)
        self.assertIn("app/novo.py", saida)

    def test_arquivo_de_400_linhas_passa(self):
        self.escrever("app/no_limite.py", 400)
        codigo, saida, _ = self.rodar()
        self.assertEqual(codigo, 0)
        self.assertNotIn("VIOLACAO:", saida)
        self.assertIn("violacoes: 0", saida)

    def test_limite_custom_via_flag(self):
        self.escrever("app/curto.py", 11)
        codigo, saida, _ = self.rodar("--limit", "10")
        self.assertEqual(codigo, 1)
        self.assertIn("novo arquivo acima do limite", saida)


class TestBaselineLegado(VerificacaoTamanhoBase):
    def test_arquivo_legado_que_cresceu_falha(self):
        self.escrever("app/legado.py", 402)
        self.gravar_baseline({"app/legado.py": 401})
        codigo, saida, _ = self.rodar()
        self.assertEqual(codigo, 1)
        self.assertIn("VIOLACAO:", saida)
        self.assertIn("arquivo legado cresceu (baseline 401 → atual 402)", saida)

    def test_arquivo_legado_igual_ao_baseline_passa(self):
        self.escrever("app/legado.py", 450)
        self.gravar_baseline({"app/legado.py": 450})
        codigo, saida, _ = self.rodar()
        self.assertEqual(codigo, 0)
        self.assertNotIn("VIOLACAO:", saida)

    def test_desatualizado_viola_e_write_baseline_resolve(self):
        # Atual < baseline: antes era "sugestão", agora a catraca exige exatidão.
        self.escrever("app/legado.py", 450)
        self.gravar_baseline({"app/legado.py": 500})
        codigo, saida, _ = self.rodar()
        self.assertEqual(codigo, 1)
        self.assertIn(
            "VIOLACAO: baseline desatualizado em app/legado.py "
            "(baseline 500 → atual 450); rode --write-baseline",
            saida,
        )
        codigo, _, _ = self.rodar("--write-baseline")
        self.assertEqual(codigo, 0)
        codigo, saida, _ = self.rodar()
        self.assertEqual(codigo, 0)
        self.assertNotIn("VIOLACAO:", saida)

    def test_arquivo_que_caiu_para_dentro_do_limite_viola(self):
        self.escrever("app/legado.py", 350)
        self.gravar_baseline({"app/legado.py": 450})
        codigo, saida, _ = self.rodar()
        self.assertEqual(codigo, 1)
        self.assertIn(
            "VIOLACAO: app/legado.py não passa mais do limite; "
            "remova a entrada do baseline",
            saida,
        )

    def test_entrada_orfa_no_baseline_falha(self):
        # O arquivo listado não existe mais na árvore.
        self.escrever("app/existente.py", 100)
        self.gravar_baseline({"app/apagado.py": 500})
        codigo, saida, _ = self.rodar()
        self.assertEqual(codigo, 1)
        self.assertIn("VIOLACAO:", saida)
        self.assertIn("entrada órfã no baseline; rode --write-baseline", saida)
        self.assertIn("app/apagado.py", saida)


class TestWriteBaseline(VerificacaoTamanhoBase):
    def test_reducao_grava_estado_exato_e_check_seguinte_passa(self):
        self.escrever("app/grande.py", 401)
        self.gravar_baseline({"app/grande.py": 450})
        codigo, saida, _ = self.rodar("--write-baseline")
        self.assertEqual(codigo, 0)
        baseline = self.ler_baseline()
        self.assertEqual(baseline["limit"], 400)
        self.assertEqual(baseline["files"], {"app/grande.py": 401})
        codigo, saida, _ = self.rodar()
        self.assertEqual(codigo, 0)
        self.assertNotIn("VIOLACAO:", saida)

    def test_recusa_arquivo_novo_de_401_linhas(self):
        self.escrever("app/novo.py", 401)
        codigo, saida, _ = self.rodar("--write-baseline")
        self.assertEqual(codigo, 2)
        self.assertIn(
            "recusado: --write-baseline só reduz ou remove entradas; "
            "app/novo.py precisa ser refatorado",
            saida,
        )
        self.assertFalse((self.raiz / "scripts" / "file_size_baseline.json").exists())

    def test_recusa_aumento_de_legado_e_nao_grava_nada(self):
        self.escrever("app/legado.py", 460)
        self.gravar_baseline({"app/legado.py": 450})
        codigo, saida, _ = self.rodar("--write-baseline")
        self.assertEqual(codigo, 2)
        self.assertIn("app/legado.py precisa ser refatorado", saida)
        self.assertEqual(self.ler_baseline()["files"]["app/legado.py"], 450)

    def test_baseline_ordenado_e_com_newline_final(self):
        self.escrever("app/z.py", 401)
        self.escrever("app/a.py", 402)
        self.gravar_baseline({"app/z.py": 410, "app/a.py": 415, "app/removido.py": 500})
        codigo, _, _ = self.rodar("--write-baseline")
        self.assertEqual(codigo, 0)
        bruto = (self.raiz / "scripts" / "file_size_baseline.json").read_text(
            encoding="utf-8"
        )
        self.assertTrue(bruto.endswith("\n"))
        baseline = json.loads(bruto)
        self.assertEqual(list(baseline["files"].keys()), ["app/a.py", "app/z.py"])
        self.assertNotIn("app/removido.py", baseline["files"])


class TestBaseRef(VerificacaoTamanhoBase):
    """--base-ref compara o baseline do disco com o da ref base (git show)."""

    def test_chave_nova_no_baseline_viola(self):
        _git = self.commit_base({"app/legado.py": 450})
        self.escrever("app/novo.py", 401)
        self.gravar_baseline({"app/legado.py": 450, "app/novo.py": 401})
        _git("add", "-A")
        codigo, saida, _ = self.rodar("--base-ref", "HEAD")
        self.assertEqual(codigo, 1)
        self.assertEqual(saida.count("VIOLACAO:"), 1)
        self.assertIn("entrada nova no baseline: app/novo.py (401 linhas)", saida)

    def test_valor_aumentado_viola(self):
        _git = self.commit_base({"app/legado.py": 401}, linhas=401)
        self.escrever("app/legado.py", 500)
        self.gravar_baseline({"app/legado.py": 500})
        _git("add", "-A")
        codigo, saida, _ = self.rodar("--base-ref", "HEAD")
        self.assertEqual(codigo, 1)
        self.assertEqual(saida.count("VIOLACAO:"), 1)
        self.assertIn("baseline cresceu em app/legado.py (base 401 → atual 500)", saida)

    def test_valor_reduzido_passa(self):
        _git = self.commit_base({"app/legado.py": 500}, linhas=500)
        self.escrever("app/legado.py", 401)
        self.gravar_baseline({"app/legado.py": 401})
        _git("add", "-A")
        codigo, saida, _ = self.rodar("--base-ref", "HEAD")
        self.assertEqual(codigo, 0)
        self.assertNotIn("VIOLACAO:", saida)

    def test_chave_removida_passa(self):
        violacoes = check_file_size.comparar_baseline_com_base(
            {"app/legado.py": 401},
            {"app/legado.py": 500, "app/outro.py": 450},
        )
        self.assertEqual(violacoes, [])

    def test_ref_inexistente_avisa_em_stderr_e_nao_falha(self):
        self.commit_base({"app/legado.py": 450})
        codigo, saida, erro = self.rodar("--base-ref", "ref-inexistente")
        self.assertEqual(codigo, 0)
        self.assertNotIn("VIOLACAO:", saida)
        self.assertIn(
            "aviso: base-ref indisponível; comparação de baseline ignorada", erro
        )


class TestIgnorados(VerificacaoTamanhoBase):
    def test_extensoes_nao_listadas_nao_contam(self):
        self.escrever("app/notas.txt", 500)
        self.escrever("app/leiame.md", 500)
        codigo, saida, _ = self.rodar()
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
        codigo, saida, _ = self.rodar()
        self.assertEqual(codigo, 0)
        self.assertIn("acima do limite: 0", saida)

    def test_extensoes_vigiadas_contam(self):
        self.escrever("app/script.js", 401)
        self.escrever("app/tela.html", 402)
        self.escrever("app/estilo.css", 403)
        self.escrever("app/modulo.py", 404)
        codigo, saida, _ = self.rodar()
        self.assertEqual(codigo, 1)
        self.assertEqual(saida.count("VIOLACAO:"), 4)


class TestQuiet(VerificacaoTamanhoBase):
    def test_quiet_imprime_somente_violacoes(self):
        self.escrever("app/grande.py", 401)
        self.escrever("app/pequeno.py", 10)
        codigo, saida, _ = self.rodar("--quiet")
        self.assertEqual(codigo, 1)
        self.assertIn("VIOLACAO:", saida)
        self.assertNotIn("arquivos:", saida)
        self.assertNotIn("violacoes:", saida)

    def test_quiet_mostra_violacao_de_baseline_desatualizado(self):
        self.escrever("app/legado.py", 401)
        self.gravar_baseline({"app/legado.py": 500})
        codigo, saida, _ = self.rodar("--quiet")
        self.assertEqual(codigo, 1)
        self.assertIn("baseline desatualizado em app/legado.py", saida)
        self.assertNotIn("arquivos:", saida)


class TestArquivosVersionados(VerificacaoTamanhoBase):
    """coletar_arquivos deve olhar só o que está versionado no git."""

    @unittest.skipUnless(shutil.which("git"), "git não disponível")
    def test_repo_git_somente_versionados_contam(self):
        _git = self.iniciar_git()

        # Versionado de 401 linhas → violação. Árvores não versionadas de
        # 900 linhas → não aparecem em coletar_arquivos.
        self.escrever("app/versionado.py", 401)
        self.escrever("worktrees/x/enorme.js", 900)
        self.escrever(".venv-ish/lib/dependencia.py", 900)
        _git("add", "app/versionado.py")

        coletados = check_file_size.coletar_arquivos(self.raiz)
        self.assertEqual(coletados, ["app/versionado.py"])

        codigo, saida, _ = self.rodar()
        self.assertEqual(codigo, 1)
        self.assertEqual(saida.count("VIOLACAO:"), 1)
        self.assertIn("app/versionado.py", saida)
        self.assertNotIn("worktrees/", saida)
        self.assertNotIn(".venv-ish", saida)

        # Mesmo se os diretórios ignorados fossem versionados, seguem fora.
        _git("add", "-A")
        self.assertEqual(
            check_file_size.coletar_arquivos(self.raiz), ["app/versionado.py"]
        )


class TestConstantes(unittest.TestCase):
    def test_limite_padrao(self):
        self.assertEqual(check_file_size.LIMITE, 400)


if __name__ == "__main__":
    unittest.main()
