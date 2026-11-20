"""Contexto para impedir criação automática durante a revisão assistida."""

from contextlib import contextmanager
from contextvars import ContextVar


_criacao_automatica_bloqueada = ContextVar(
    'criacao_automatica_bloqueada', default=False,
)


def criacao_automatica_esta_bloqueada():
    """Indica se o contexto atual não pode criar documentos automaticamente."""
    return _criacao_automatica_bloqueada.get()


@contextmanager
def sem_criacao_automatica():
    """Impede a criação automática de documentos de origem.

    Cartórios e pessoas não são cobertos por esta guarda: só o documento de
    origem deixou de ser criado durante a revisão assistida.
    """
    token = _criacao_automatica_bloqueada.set(True)
    try:
        yield
    finally:
        _criacao_automatica_bloqueada.reset(token)
