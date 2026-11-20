"""Número de lançamento: normalização, composição e chave de ordenação."""

import math

from .analise import analisar_rotulo


def normalizar_numero_lancamento(texto) -> str | None:
    """Número de lançamento gravável/comparável: sem o prefixo do rótulo.

    ``'R-5'`` → ``'5'``; ``'Av: 6-237 – PROTOCOLO...'`` → ``'6'``; o número
    digitado já sem prefixo volta igual; texto que não é rótulo R/Av volta
    só com as bordas removidas (comportamento de antes, #322); vazio →
    ``None``. A MESMA função normaliza os dois lados da duplicata — o que
    o OCR trouxe com prefixo e o que está gravado.
    """
    analisado = analisar_rotulo(texto)
    if (
        analisado.reconhecido
        and not analisado.eh_matricula
        and analisado.numero
    ):
        return analisado.numero
    if not isinstance(texto, str):
        return None
    return texto.strip() or None


def compor_numero_lancamento(tipo, numero, sigla_matricula):
    """Número de lançamento no formato canônico do V1 (fluxo manual).

    Decisão de PRODUTO (#322 rodada 3, tomada pelo orquestrador por falta
    de resposta do cliente): a importação grava o MESMO texto que o fluxo
    manual compõe em ``lancamento_form_service._gerar_numero_lancamento``
    — registro ``'R5 M237'``, averbação ``'AV6 M237'``, início de
    matrícula só a sigla ``'M237'``. ``sigla_matricula`` é o
    ``documento.numero`` (o campo já vem com o prefixo, ex. 'M237',
    'T2540'); vazia, compõe sem ela (``'R5'``). Sete consumidores ordenam
    por ``_extrair_numero_simples``, que exige ``^(R|AV)\\d+`` — gravar o
    número puro joga o lançamento para o fim da lista/cadeia/tabela.
    Sem número do ato não há o que compor (None), e tipo fora de
    registro/averbação/início devolve o número como veio.
    """
    numero = (numero or '').strip()
    sigla = (sigla_matricula or '').strip()
    if tipo == 'inicio_matricula':
        return sigla or None
    if tipo == 'registro':
        prefixo = 'R'
    elif tipo == 'averbacao':
        prefixo = 'AV'
    else:
        return numero or None
    if not numero:
        return None
    return f'{prefixo}{numero} {sigla}'.rstrip()


def _valor_do_campo(campo):
    """Valor de um campo de valor A3: ``normalized`` quando veio, senão ``raw``.

    No payload real os campos críticos do cabeçalho chegam com
    ``normalized=None`` (o texto de OCR fica no ``raw``) — é o que a revisão
    tem em mãos para julgar.
    """
    if not isinstance(campo, dict):
        return None
    if campo.get('normalized') is not None:
        return campo['normalized']
    return campo.get('raw')


def _ordem_ordenavel(ordem, indice):
    """Chave de ordenação inteira do ato: ``ordem`` válida ou índice + 1.

    No payload real ``ordem`` vem como STRING ('1', '7') — o sintético dos
    testes trazia int e escondia o bug de a chave ``isinstance(..., (int,
    float))`` empatar tudo em 0, com a lista saindo na ordem original em
    vez da reversa (#322). Sem ``ordem`` — ou INVÁLIDA: texto sem dígito,
    ``NaN``/``Infinity`` que o ``json.loads`` aceita e não podem passar
    por ``int()`` — a chave é o ÍNDICE do payload + 1, a mesma regra da
    revisão (``metadados.get('ordem', indice + 1)``): o ato do meio do
    documento fica no MEIO, não vai parar no fim (#322 rodada 3,
    P1-2/P2-6). Nunca levanta exceção.
    """
    if isinstance(ordem, float):
        # NaN/±Infinity: int() levantaria ValueError/OverflowError.
        return int(ordem) if math.isfinite(ordem) else indice + 1
    if isinstance(ordem, int):
        return int(ordem)
    if isinstance(ordem, str):
        try:
            return int(ordem.strip())
        except ValueError:
            return indice + 1
    return indice + 1
