"""Tipos do parser de rótulos: resultados de análise e de classificação."""

from dataclasses import dataclass

# Valores válidos de ``tipo_sugerido.normalized`` no contrato A3.
TIPOS_SUGERIDOS = ('registro', 'averbacao', 'inicio_matricula')


@dataclass(frozen=True)
class Rotulo:
    """Resultado da análise de um texto de rótulo."""

    tipo: str | None
    # 'registro' | 'averbacao' | 'inicio_matricula' | None
    numero: str | None
    # Número do ato SEM prefixo ('R-5' → '5').
    matricula: str | None
    # Número da matrícula quando o rótulo o traz ('1-237' → '237').
    eh_matricula: bool
    # True quando o prefixo é M (referência de matrícula, não lançamento).
    reconhecido: bool
    motivo: str | None
    # 'vazio' | 'sem_prefixo' | 'prefixo_desconhecido' | 'sem_numero'


@dataclass(frozen=True)
class Classificacao:
    """Saída de ``classificar_atos`` para o payload da extração."""

    inicio_matricula: dict | None
    # Cabeçalho /document/* — não é um ato; None sem ``document``.
    lancamentos: list
    # {'ordem', 'tipo', 'numero', 'matricula', 'ato', 'divergencia'} em
    # ordem REVERSA (maior ordem primeiro), só R/Av.
    nao_reconhecidos: list
    # {'ordem', 'rotulo', 'motivo', 'ato'} — bucket de decisão da UI (#321).


def _nao_reconhecido(motivo):
    return Rotulo(
        tipo=None, numero=None, matricula=None, eh_matricula=False,
        reconhecido=False, motivo=motivo,
    )
