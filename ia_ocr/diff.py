"""Diff entre o texto do OCR e o texto confirmado (issue #261 / I-4).

Server-side, com difflib e sem dependência JS. O resultado é uma lista de
trechos ``(tipo, texto)``; o template os renderiza com autoescape — nunca
HTML montado aqui, porque o texto é de documento (conteúdo não confiável).
"""

import difflib
import re

IGUAL = 'igual'
REMOVIDO = 'removido'
ADICIONADO = 'adicionado'

# Palavras e espaços como tokens: o espaço é token próprio para o diff
# preservar a pontuação e a quebra de linha exatas.
_TOKENS = re.compile(r'\s+|\S+')
_LINHAS = re.compile(r'[^\n]*\n|[^\n]+')

# O diff por palavra é quadrático no pior caso; acima deste total de tokens
# (original + confirmado) cai para linhas, que mantém o custo baixo.
LIMITE_TOKENS = 20000


def _acrescentar(segmentos, tipo, texto):
    if not texto:
        return
    if segmentos and segmentos[-1][0] == tipo:
        segmentos[-1] = (tipo, segmentos[-1][1] + texto)
    else:
        segmentos.append((tipo, texto))


def _so_espaco_na_linha(texto):
    """Espaços/tabs apenas: sem quebra de linha e sem nenhuma palavra."""
    return not texto.strip() and '\n' not in texto


def segmentos_diff(original, confirmado):
    """Trechos que transformam ``original`` em ``confirmado``.

    ``IGUAL`` + ``REMOVIDO`` remontam o original; ``IGUAL`` + ``ADICIONADO``
    remontam o confirmado. Trocas separadas apenas por espaço na mesma linha
    viram um bloco só ("Boa Vista" → "Santa Maria", e não duas trocas
    coladas); a quebra de linha mantém os blocos separados.
    """
    tokens_a = _TOKENS.findall(original)
    tokens_b = _TOKENS.findall(confirmado)
    if len(tokens_a) + len(tokens_b) > LIMITE_TOKENS:
        tokens_a = _LINHAS.findall(original)
        tokens_b = _LINHAS.findall(confirmado)

    # autojunk=False: o espaço é o token mais frequente e a heurística o
    # trataria como "lixo", degradando o alinhamento em textos longos.
    comparador = difflib.SequenceMatcher(None, tokens_a, tokens_b, autojunk=False)
    blocos = comparador.get_opcodes()
    segmentos = []
    removido = adicionado = ''  # troca em montagem

    def fechar_troca():
        nonlocal removido, adicionado
        _acrescentar(segmentos, REMOVIDO, removido)
        _acrescentar(segmentos, ADICIONADO, adicionado)
        removido = adicionado = ''

    for indice, (tag, i1, i2, j1, j2) in enumerate(blocos):
        if tag == 'equal':
            texto = ''.join(tokens_a[i1:i2])
            ha_troca_depois = indice + 1 < len(blocos)
            if (removido or adicionado) and ha_troca_depois and _so_espaco_na_linha(texto):
                removido += texto
                adicionado += texto
                continue
            fechar_troca()
            _acrescentar(segmentos, IGUAL, texto)
        else:
            removido += ''.join(tokens_a[i1:i2])
            adicionado += ''.join(tokens_b[j1:j2])
    fechar_troca()
    return segmentos
