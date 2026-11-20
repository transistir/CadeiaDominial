"""Números do ato: simples (do rótulo), composto (gerador do POST) e legível."""

from decimal import Decimal, InvalidOperation
from types import SimpleNamespace

from dominial.services.lancamento_form_service import LancamentoFormService

from .. import importacao


def _numero_simples(chave, rotulo, ato):
    """``(chave da linha, número do ato sem prefixo)`` para o input simples.

    O número é o do RÓTULO (``'R-5'`` → ``'5'``), o que o A3 sempre traz.
    Rótulo sem número de ato (referência de matrícula ``M-3-14511``, texto
    não reconhecido) cai no ``numero_lancamento`` da revisão — a mesma
    leitura da gravação, que só aceita ali um número de ato válido.
    """
    if rotulo.reconhecido and not rotulo.eh_matricula and rotulo.numero:
        return f'{chave}/rotulo', rotulo.numero
    return (
        f'{chave}/numero_lancamento',
        importacao._numero_de_ato_do_campo(ato.numero_lancamento),
    )


def _numero_composto(tipo, numero, documento):
    """Número completo ("R1 M237"), ou ``None`` quando não há o que compor.

    Chama o gerador do POST do formulário manual com a sigla da matrícula
    (``documento.numero``, o mesmo que o template põe em ``sigla_matricula``)
    — não repete a regra aqui. Só os três tipos que o JS do formulário
    compõe (registro, averbação, início de matrícula); registro/averbação
    sem número de ato ficam sem composto, como no formulário manual, onde o
    revisor ainda vai digitar o número simples.
    """
    if tipo is None or tipo.tipo not in ('registro', 'averbacao', 'inicio_matricula'):
        return None
    if tipo.tipo != 'inicio_matricula' and not numero:
        return None
    pedido = SimpleNamespace(POST={'sigla_matricula': documento.numero or ''})
    composto = LancamentoFormService._gerar_numero_lancamento(
        numero or '', tipo, pedido,
    )
    return composto.strip() or None


def _numero_legivel(normalizado):
    """Decimal canônico → "120" / "12,5" (pt-BR, sem zeros à direita); senão ''."""
    try:
        numero = Decimal(str(normalizado))
    except (InvalidOperation, ValueError):
        return ''
    if not numero.is_finite():
        return ''
    return format(numero.normalize(), 'f').replace('.', ',')
