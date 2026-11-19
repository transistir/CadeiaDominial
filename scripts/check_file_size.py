#!/usr/bin/env python3
"""Trava de 400 linhas por arquivo — Etapa 0 do plano de refatoração.

Varre os arquivos VERSIONADOS do repositório (`git ls-files`; sem git, cai no
os.walk) com extensão .py, .js, .html, .css, e falha se algum arquivo:
  a) passa do limite sem estar no baseline (novo arquivo acima do limite);
  b) está no baseline e cresceu (baseline do estado atual só pode encolher);
  c) está no baseline mas não existe mais (entrada órfã).

Arquivo do baseline que encolheu é OK — o check sugere atualizar o baseline.

Baseline: scripts/file_size_baseline.json, contando só arquivos acima do limite.
Só stdlib; requer Python 3.11+.

Uso:
    python scripts/check_file_size.py                 # check (exit 1 se violar)
    python scripts/check_file_size.py --quiet         # só imprime violações
    python scripts/check_file_size.py --write-baseline
    python scripts/check_file_size.py --limit 300     # limite ad hoc
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path, PurePosixPath

LIMITE = 400

#: Extensões vigiadas pelo limite.
EXTENSOES = {".py", ".js", ".html", ".css"}

#: Diretórios nunca varridos (VCS, dependências, artefatos, migrações Django,
#: checkouts aninhados e configurações de agente).
DIRETORIOS_IGNORADOS = {
    ".git",
    "node_modules",
    "migrations",
    "old",
    "staticfiles",
    ".venv",
    "venv",
    "dist",
    "build",
    "__pycache__",
    "worktrees",
    ".hermes",
    ".claude",
}

BASELINE_NOME = "file_size_baseline.json"


def descobrir_raiz() -> Path:
    """Raiz do repositório = diretório pai de scripts/."""
    return Path(__file__).resolve().parent.parent


def caminho_baseline(raiz: Path) -> Path:
    return raiz / "scripts" / BASELINE_NOME


def _diretorio_ignorado(nome: str) -> bool:
    """Nome de diretório a pular: na lista fixa ou qualquer `.venv*`."""
    return nome in DIRETORIOS_IGNORADOS or nome.startswith(".venv")


def _aceitavel(relativo: str) -> bool:
    """Filtros comuns: extensão vigiada e nenhum diretório ignorado no caminho."""
    if PurePosixPath(relativo).suffix not in EXTENSOES:
        return False
    partes = PurePosixPath(relativo).parts
    return all(not _diretorio_ignorado(parte) for parte in partes[:-1])


def _caminhos_versionados(raiz: Path) -> list[str] | None:
    """Caminhos relativos versionados (`git ls-files`); None se git falhar."""
    try:
        resultado = subprocess.run(
            ["git", "-C", str(raiz), "ls-files", "-z"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return [os.fsdecode(bruto) for bruto in resultado.stdout.split(b"\0") if bruto]


def _caminhos_do_walk(raiz: Path) -> list[str]:
    """Fallback para árvore sem git: os.walk pulando diretórios ignorados."""
    encontrados: list[str] = []
    for dirpath, nomes_dir, nomes_arq in os.walk(raiz):
        nomes_dir[:] = sorted(d for d in nomes_dir if not _diretorio_ignorado(d))
        for nome in sorted(nomes_arq):
            encontrados.append((Path(dirpath) / nome).relative_to(raiz).as_posix())
    return encontrados


def coletar_arquivos(raiz: Path) -> list[str]:
    """Caminhos relativos (posix) dos arquivos vigiados, ordenados.

    Prefere a lista de arquivos VERSIONADOS (`git ls-files`), para não entrar
    em checkouts aninhados (worktrees/, .venv*/); sem git disponível, cai no
    os.walk. Os filtros de extensão e de diretório valem nos dois caminhos.
    """
    caminhos = _caminhos_versionados(raiz)
    if caminhos is None:
        caminhos = _caminhos_do_walk(raiz)
    return sorted(caminho for caminho in caminhos if _aceitavel(caminho))


def contar_linhas(raiz: Path, relativo: str) -> int:
    texto = (raiz / relativo).read_text(encoding="utf-8", errors="replace")
    return len(texto.splitlines())


def carregar_baseline(raiz: Path) -> dict[str, int]:
    caminho = caminho_baseline(raiz)
    if not caminho.exists():
        return {}
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    return {str(k): int(v) for k, v in dados.get("files", {}).items()}


def escrever_baseline(raiz: Path, limite: int) -> int:
    """Regrava o baseline com o estado atual; devolve quantos arquivos gravou."""
    acima: dict[str, int] = {}
    for relativo in coletar_arquivos(raiz):
        linhas = contar_linhas(raiz, relativo)
        if linhas > limite:
            acima[relativo] = linhas
    caminho = caminho_baseline(raiz)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    dados = {"limit": limite, "files": dict(sorted(acima.items()))}
    caminho.write_text(json.dumps(dados, indent=2) + "\n", encoding="utf-8")
    return len(acima)


def avaliar(raiz: Path, limite: int, baseline: dict[str, int]):
    """Compara o estado atual com o baseline.

    Devolve (violacoes, sugestoes, total_varridos, acima_do_limite) onde
    violacoes é lista de strings prefixadas com "VIOLACAO:".
    """
    violacoes: list[str] = []
    sugestoes: list[str] = []
    atuais: dict[str, int] = {}
    acima_do_limite = 0

    for relativo in coletar_arquivos(raiz):
        linhas = contar_linhas(raiz, relativo)
        atuais[relativo] = linhas
        if linhas <= limite:
            continue
        acima_do_limite += 1
        if relativo not in baseline:
            violacoes.append(
                f"VIOLACAO: novo arquivo acima do limite: {relativo} "
                f"({linhas} linhas > {limite})"
            )
        elif linhas > baseline[relativo]:
            violacoes.append(
                f"VIOLACAO: {relativo}: arquivo legado cresceu "
                f"(baseline {baseline[relativo]} → atual {linhas})"
            )

    for relativo, linhas_baseline in baseline.items():
        if relativo not in atuais:
            violacoes.append(
                f"VIOLACAO: {relativo}: entrada órfã no baseline; "
                f"rode --write-baseline"
            )
            continue
        if atuais[relativo] < linhas_baseline:
            sugestoes.append(
                f"OK: {relativo} pode atualizar o baseline "
                f"({linhas_baseline} → {atuais[relativo]})"
            )

    violacoes.sort()
    sugestoes.sort()
    return violacoes, sugestoes, len(atuais), acima_do_limite


def main(argv: list[str] | None = None, raiz: Path | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Trava de tamanho de arquivo (padrão: 400 linhas)."
    )
    parser.add_argument("--limit", type=int, default=LIMITE, help="limite de linhas")
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="regrava o baseline com o estado atual (só arquivos acima do limite)",
    )
    parser.add_argument(
        "--quiet", action="store_true", help="imprime somente violações"
    )
    args = parser.parse_args(argv)

    raiz = Path(raiz).resolve() if raiz is not None else descobrir_raiz()

    if args.write_baseline:
        gravados = escrever_baseline(raiz, args.limit)
        print(
            f"baseline gravado: scripts/{BASELINE_NOME} "
            f"({gravados} arquivo(s) acima do limite de {args.limit})"
        )
        return 0

    baseline = carregar_baseline(raiz)
    violacoes, sugestoes, total, acima = avaliar(raiz, args.limit, baseline)

    if not args.quiet:
        for sugestao in sugestoes:
            print(sugestao)
        print(f"arquivos: {total}, acima do limite: {acima}, violacoes: {len(violacoes)}")
    for violacao in violacoes:
        print(violacao)

    return 1 if violacoes else 0


if __name__ == "__main__":
    sys.exit(main())
