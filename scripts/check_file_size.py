#!/usr/bin/env python3
"""Trava de 400 linhas por arquivo — Etapa 0 do plano de refatoração.

Varre os arquivos VERSIONADOS do repositório (`git ls-files`; sem git, cai no
os.walk) com extensão .py, .js, .html, .css, e falha se algum arquivo:
  a) passa do limite sem estar no baseline (novo arquivo acima do limite);
  b) está no baseline e difere do estado atual — o baseline exige igualdade
     exata: cresceu OU encolheu, ambos violam (a catraca aperta sozinha);
  c) está no baseline mas caiu para dentro do limite (remova a entrada);
  d) está no baseline mas não existe mais (entrada órfã).

Com --base-ref REF, o baseline do disco é comparado com o da ref base
(`git show REF:scripts/file_size_baseline.json`): chave nova ou valor maior
viola — o PR não pode abençoar o próprio baseline. Dois casos especiais:
  - REF não existe (`git rev-parse --verify` falha): aviso em stderr e a
    comparação é ignorada (o hook local não tem a ref; o CI tem).
  - REF existe mas o JSON não (base anterior ao baseline): bootstrap — o
    baseline da base é reconstruído medindo cada arquivo do baseline atual
    na árvore da REF (`git show REF:<caminho>`); entrada só é legítima se o
    arquivo existia na base e já passava do limite lá. Sem caminho
    silencioso: violações saem pelo mesmo exit 1.

--write-baseline só reduz ou remove entradas: se o estado atual adicionaria
chave ou aumentaria valor em relação ao JSON que já está no disco, falha com
exit 2 sem gravar nada.

Baseline: scripts/file_size_baseline.json, contando só arquivos acima do limite.
Só stdlib; requer Python 3.11+.

Uso:
    python scripts/check_file_size.py                 # check (exit 1 se violar)
    python scripts/check_file_size.py --quiet         # só imprime violações
    python scripts/check_file_size.py --write-baseline
    python scripts/check_file_size.py --base-ref origin/develop
    python scripts/check_file_size.py --limit 300     # limite ad hoc

Exit: 0 ok; 1 violações; 2 recusa do --write-baseline.
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


def _git_out(raiz: Path, argumentos: list[str]) -> bytes:
    """Saída bruta de um comando git; levanta OSError/CalledProcessError."""
    resultado = subprocess.run(
        ["git", "-C", str(raiz), *argumentos],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return resultado.stdout


def _caminhos_versionados(raiz: Path) -> list[str] | None:
    """Caminhos relativos versionados (`git ls-files`); None se git falhar."""
    try:
        bruto = _git_out(raiz, ["ls-files", "-z"])
    except (OSError, subprocess.CalledProcessError):
        return None
    return [os.fsdecode(parte) for parte in bruto.split(b"\0") if parte]


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


def carregar_json_baseline(texto: str) -> dict[str, int]:
    dados = json.loads(texto)
    return {str(k): int(v) for k, v in dados.get("files", {}).items()}


def carregar_baseline(raiz: Path) -> dict[str, int]:
    caminho = caminho_baseline(raiz)
    if not caminho.exists():
        return {}
    return carregar_json_baseline(caminho.read_text(encoding="utf-8"))


def ref_existe(raiz: Path, base_ref: str) -> bool:
    """A ref base existe no repositório? (`git rev-parse --verify`.)"""
    try:
        _git_out(raiz, ["rev-parse", "--verify", base_ref])
    except (OSError, subprocess.CalledProcessError):
        return False
    return True


def baseline_da_base(raiz: Path, base_ref: str) -> dict[str, int] | None:
    """Baseline da ref base via `git show REF:scripts/<nome>`; None se a ref
    não o tiver (ou o JSON for ilegível)."""
    try:
        bruto = _git_out(raiz, ["show", f"{base_ref}:scripts/{BASELINE_NOME}"])
    except (OSError, subprocess.CalledProcessError):
        return None
    try:
        return carregar_json_baseline(bruto.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None


def linhas_na_ref(raiz: Path, base_ref: str, relativo: str) -> int | None:
    """Linhas do arquivo na árvore da ref; None se o arquivo não existir lá."""
    try:
        bruto = _git_out(raiz, ["show", f"{base_ref}:{relativo}"])
    except (OSError, subprocess.CalledProcessError):
        return None
    return len(bruto.decode("utf-8", errors="replace").splitlines())


def violacoes_bootstrap_da_base(
    raiz: Path, base_ref: str, baseline: dict[str, int], limite: int
) -> list[str]:
    """Violações quando a ref base existe mas o JSON de baseline não.

    Bootstrap: o baseline da base é reconstruído medindo cada arquivo do
    baseline atual na árvore da ref (`git show REF:<caminho>`); entrada
    legítima só se o arquivo existia na base e já passava do limite lá —
    o valor da base é essa contagem. Entrada para arquivo ausente ou pequeno
    na base é "entrada nova" (o PR não abençoa o próprio baseline).
    """
    violacoes: list[str] = []
    for relativo, valor_atual in baseline.items():
        linhas = linhas_na_ref(raiz, base_ref, relativo)
        if linhas is None:
            violacoes.append(f"VIOLACAO: entrada nova no baseline: {relativo}")
        elif linhas <= limite:
            violacoes.append(
                f"VIOLACAO: entrada nova no baseline: {relativo} "
                f"(na base tinha {linhas} linhas)"
            )
        elif valor_atual > linhas:
            violacoes.append(
                f"VIOLACAO: baseline cresceu em {relativo} "
                f"(base {linhas} → atual {valor_atual})"
            )
    return violacoes


def comparar_baseline_com_base(
    baseline: dict[str, int], base: dict[str, int]
) -> list[str]:
    """Violações do baseline do disco contra o da base: só pode encolher.

    Chave nova ou valor maior em relação à base viola; valor menor ou chave
    removida é OK.
    """
    violacoes: list[str] = []
    for relativo, valor_atual in baseline.items():
        if relativo not in base:
            violacoes.append(
                f"VIOLACAO: entrada nova no baseline: {relativo} "
                f"({valor_atual} linhas)"
            )
        elif valor_atual > base[relativo]:
            violacoes.append(
                f"VIOLACAO: baseline cresceu em {relativo} "
                f"(base {base[relativo]} → atual {valor_atual})"
            )
    return violacoes


def _acima_do_limite_agora(raiz: Path, limite: int) -> dict[str, int]:
    """Estado atual: arquivos acima do limite e suas contagens de linha."""
    acima: dict[str, int] = {}
    for relativo in coletar_arquivos(raiz):
        linhas = contar_linhas(raiz, relativo)
        if linhas > limite:
            acima[relativo] = linhas
    return acima


def escrever_baseline(raiz: Path, limite: int) -> tuple[int, list[str]]:
    """Regrava o baseline com o estado atual, se ele só reduzir o existente.

    O estado atual não pode ADICIONAR chave nem AUMENTAR valor em relação ao
    JSON que já está no disco; se puder, devolve (0, recusados) sem gravar
    nada. Devolve (quantos_gravou, []) quando grava.
    """
    acima = _acima_do_limite_agora(raiz, limite)
    no_disco = carregar_baseline(raiz)
    recusados = [
        relativo
        for relativo in sorted(acima)
        if relativo not in no_disco or acima[relativo] > no_disco[relativo]
    ]
    if recusados:
        return 0, recusados
    caminho = caminho_baseline(raiz)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    dados = {"limit": limite, "files": dict(sorted(acima.items()))}
    caminho.write_text(json.dumps(dados, indent=2) + "\n", encoding="utf-8")
    return len(acima), []


def avaliar(raiz: Path, limite: int, baseline: dict[str, int]):
    """Compara o estado atual com o baseline (igualdade exata exigida).

    Devolve (violacoes, total_varridos, acima_do_limite) onde violacoes é
    lista de strings prefixadas com "VIOLACAO:".
    """
    violacoes: list[str] = []
    atuais: dict[str, int] = {}
    acima_do_limite = 0

    for relativo in coletar_arquivos(raiz):
        linhas = contar_linhas(raiz, relativo)
        atuais[relativo] = linhas
        if linhas <= limite:
            if relativo in baseline:
                violacoes.append(
                    f"VIOLACAO: {relativo} não passa mais do limite; "
                    f"remova a entrada do baseline"
                )
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
        elif linhas < baseline[relativo]:
            violacoes.append(
                f"VIOLACAO: baseline desatualizado em {relativo} "
                f"(baseline {baseline[relativo]} → atual {linhas}); "
                f"rode --write-baseline"
            )

    for relativo in baseline:
        if relativo not in atuais:
            violacoes.append(
                f"VIOLACAO: {relativo}: entrada órfã no baseline; "
                f"rode --write-baseline"
            )

    violacoes.sort()
    return violacoes, len(atuais), acima_do_limite


def main(argv: list[str] | None = None, raiz: Path | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Trava de tamanho de arquivo (padrão: 400 linhas)."
    )
    parser.add_argument("--limit", type=int, default=LIMITE, help="limite de linhas")
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="regrava o baseline com o estado atual (só reduz ou remove; "
        "exit 2 se recusado)",
    )
    parser.add_argument(
        "--base-ref",
        default=None,
        help="ref base (ex.: origin/develop) para comparar o baseline via "
        "`git show REF:scripts/<baseline>`",
    )
    parser.add_argument(
        "--quiet", action="store_true", help="imprime somente violações"
    )
    args = parser.parse_args(argv)

    raiz = Path(raiz).resolve() if raiz is not None else descobrir_raiz()

    if args.write_baseline:
        gravados, recusados = escrever_baseline(raiz, args.limit)
        if recusados:
            for relativo in recusados:
                print(
                    "recusado: --write-baseline só reduz ou remove entradas; "
                    f"{relativo} precisa ser refatorado"
                )
            return 2
        print(
            f"baseline gravado: scripts/{BASELINE_NOME} "
            f"({gravados} arquivo(s) acima do limite de {args.limit})"
        )
        return 0

    baseline = carregar_baseline(raiz)
    violacoes, total, acima = avaliar(raiz, args.limit, baseline)

    if args.base_ref:
        if not ref_existe(raiz, args.base_ref):
            print(
                "aviso: base-ref indisponível; comparação de baseline ignorada",
                file=sys.stderr,
            )
        else:
            base = baseline_da_base(raiz, args.base_ref)
            if base is None:
                # A ref existe mas não tem JSON de baseline (base anterior ao
                # baseline): bootstrap mede a árvore da ref.
                violacoes.extend(
                    violacoes_bootstrap_da_base(
                        raiz, args.base_ref, baseline, args.limit
                    )
                )
            else:
                violacoes.extend(comparar_baseline_com_base(baseline, base))
            violacoes.sort()

    if not args.quiet:
        print(f"arquivos: {total}, acima do limite: {acima}, violacoes: {len(violacoes)}")
    for violacao in violacoes:
        print(violacao)

    return 1 if violacoes else 0


if __name__ == "__main__":
    sys.exit(main())
