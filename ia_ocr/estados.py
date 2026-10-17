"""Máquina de estados do OcrJob (issue #258 / I-1).

Estados (arquitetura.md §3 / fluxo.md §3):

    pendente → em_execucao → concluido → texto_confirmado → extraido → revisado → importado
                       └→ falhou → (retry manual) → pendente

Toda transição é auditada em OcrJobTransicao, na mesma transação do UPDATE.
"""

from django.core.exceptions import ValidationError

PENDENTE = 'pendente'
EM_EXECUCAO = 'em_execucao'
CONCLUIDO = 'concluido'
FALHOU = 'falhou'
TEXTO_CONFIRMADO = 'texto_confirmado'
EXTRAIDO = 'extraido'
REVISADO = 'revisado'
IMPORTADO = 'importado'

STATUS_CHOICES = [
    (PENDENTE, 'Pendente'),
    (EM_EXECUCAO, 'Em execução'),
    (CONCLUIDO, 'Concluído'),
    (FALHOU, 'Falhou'),
    (TEXTO_CONFIRMADO, 'Texto confirmado'),
    (EXTRAIDO, 'Extraído'),
    (REVISADO, 'Revisado'),
    (IMPORTADO, 'Importado'),
]

# Mapa de transições válidas (de → conjunto de destinos).
# `falhou → pendente` consta no mapa, mas só é executável via `OcrJob.retry()`.
TRANSICOES_VALIDAS = {
    PENDENTE: {EM_EXECUCAO},
    EM_EXECUCAO: {CONCLUIDO, FALHOU},
    FALHOU: {PENDENTE},
    CONCLUIDO: {TEXTO_CONFIRMADO},
    TEXTO_CONFIRMADO: {EXTRAIDO},
    EXTRAIDO: {REVISADO},
    REVISADO: {IMPORTADO},
}

# Agrupamentos usados pelo card "Extrair texto com IA" (issue #260): fonte
# única — a view injeta no template, que expõe ao JS via data-* em JSON.
STATUS_ATIVOS = [PENDENTE, EM_EXECUCAO]
STATUS_COM_TEXTO = [CONCLUIDO, TEXTO_CONFIRMADO, EXTRAIDO, REVISADO, IMPORTADO]
# Estados em que o texto das páginas ainda aceita edição/confirmação (tela de
# confirmação, issue #261) e em que o card libera "Revisar texto". Depois de
# texto_confirmado o texto vira somente leitura.
STATUS_REVISAVEIS = [CONCLUIDO]


class TransicaoInvalida(ValidationError):
    """Transição não permitida pelo mapa de estados (ou pré-condição descumprida)."""


class TransicaoConcorrente(Exception):
    """O estado persistido mudou entre a leitura e o UPDATE (CAS perdido)."""
