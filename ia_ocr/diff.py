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

# Por linhas o SequenceMatcher (autojunk=False) também degrada quando as
# linhas se repetem: cada chamada percorre todas as ocorrências da linha e,
# com trocas espalhadas, são até uma chamada por linha — cúbico no pior caso.
# Medido (CPython 3.13) com linhas repetidas e trocas alternadas: 2000 linhas
# somadas ≈ 12 s, 1000 ≈ 1,5 s, 500 ≈ 0,2 s, 400 ≈ 0,1 s. Acima deste total
# (original + confirmado) o diff é grosseiro, em O(n).
LIMITE_LINHAS = 400


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


def _diff_grosseiro(linhas_a, linhas_b):
    """Prefixo e sufixo comuns intactos e o miolo como uma troca só, sem matcher."""
    comum = min(len(linhas_a), len(linhas_b))
    prefixo = 0
    while prefixo < comum and linhas_a[prefixo] == linhas_b[prefixo]:
        prefixo += 1
    # Limitado ao que sobrou do prefixo: com linhas repetidas os dois se
    # sobreporiam e o miolo deixaria de remontar os textos.
    sufixo = 0
    while sufixo < comum - prefixo and linhas_a[-1 - sufixo] == linhas_b[-1 - sufixo]:
        sufixo += 1
    fim_a = len(linhas_a) - sufixo
    fim_b = len(linhas_b) - sufixo

    segmentos = []
    _acrescentar(segmentos, IGUAL, ''.join(linhas_a[:prefixo]))
    _acrescentar(segmentos, REMOVIDO, ''.join(linhas_a[prefixo:fim_a]))
    _acrescentar(segmentos, ADICIONADO, ''.join(linhas_b[prefixo:fim_b]))
    _acrescentar(segmentos, IGUAL, ''.join(linhas_a[fim_a:]))
    return segmentos


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
        if len(tokens_a) + len(tokens_b) > LIMITE_LINHAS:
            return _diff_grosseiro(tokens_a, tokens_b)

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
