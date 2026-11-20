"""Análise do TEXTO do rótulo: reconhecimento, tipo e precedência."""

import re

from .tipos import TIPOS_SUGERIDOS, Rotulo, _nao_reconhecido

# Prefixo do rótulo: 1–3 letras no começo do texto + separador opcional
# (``-``, ``:``, ``.`` e/ou espaços) + o corpo. Caixa alta/baixa indiferente.
# Meia-risca (U+2013) e travessão (U+2014) valem como ``-``: o OCR/Word traz
# ``'R–5'`` e sem eles o texto caía em ``sem_prefixo`` e a recomposição
# gravava ``'RR–5 M237'`` (#322 rodada 4, P2-4).
_ROTULO = re.compile(
    r'^\s*(?P<prefixo>[A-Za-z]{1,3})\s*(?P<sep>[-–—:.]?\s*)(?P<corpo>\S.*)?$',
    re.IGNORECASE,
)

# Número com pontuação preservada como veio ('12.345' NÃO vira '12345').
_NUMERO = re.compile(r'\d+(?:\.\d+)*')

# O corpo é dividido no primeiro destes separadores: o primeiro número é o
# ato, o segundo é a matrícula de origem ('R: 1-237', 'R-1/42.718'). Os
# travessões tipográficos ('R: 1—237') valem como o '-' (rodada 4, P2-4).
_SEPARADOR_DE_NUMEROS = re.compile(r'[-–—/]')

_PREFIXOS = {'r': 'registro', 'av': 'averbacao', 'm': None}


def _dois_numeros(corpo):
    """Os dois primeiros números do corpo do rótulo: ato e matrícula.

    ``'5-237 – PROTOCOLO Nº 13.607'`` → ``('5', '237')``: a matrícula é o
    número imediatamente depois do primeiro separador, nunca o primeiro
    número que aparecer no resto do texto (o ``Nº 13.607`` do protocolo).
    """
    partes = _SEPARADOR_DE_NUMEROS.split(corpo, maxsplit=1)
    primeiro = _NUMERO.match(partes[0].strip())
    segundo = (
        _NUMERO.match(partes[1].strip()) if len(partes) > 1 else None
    )
    return (
        primeiro.group(0) if primeiro else None,
        segundo.group(0) if segundo else None,
    )


def analisar_rotulo(texto) -> Rotulo:
    """Analisa o texto do rótulo; NUNCA levanta exceção.

    Normalização: ``strip`` e colapso de espaços internos; zeros à esquerda
    do número preservados ('R-007' → '007') e pontuação da matrícula como
    veio ('M: 12.345' → '12.345'). Texto que não abre com um prefixo de
    1–3 letras + número é cabeçalho/comum → ``sem_prefixo``; abre com
    outra letra + número ('X-1') → ``prefixo_desconhecido``; prefixo
    R/Av/M SEM número ('R', 'Av. Brasil, 123', 'R$ 5.000') não é
    lançamento → ``sem_numero`` (#322 rodada 3, P2-5).
    """
    if texto is None:
        return _nao_reconhecido('vazio')
    if not isinstance(texto, str):
        try:
            texto = str(texto)
        except Exception:
            return _nao_reconhecido('sem_prefixo')
    compacto = ' '.join(texto.split())
    if not compacto:
        return _nao_reconhecido('vazio')

    achado = _ROTULO.match(compacto)
    if achado is None:
        return _nao_reconhecido('sem_prefixo')
    prefixo = achado.group('prefixo').lower()
    corpo = (achado.group('corpo') or '').strip()
    tipo = _PREFIXOS.get(prefixo)
    if prefixo != 'm' and tipo is None:
        # 1–3 letras que não são R/Av/M: com número em seguida é um rótulo
        # desconhecido ('X-1'); texto comum ('O imóvel rural...') não tem
        # prefixo de rótulo.
        if _NUMERO.match(corpo):
            return _nao_reconhecido('prefixo_desconhecido')
        return _nao_reconhecido('sem_prefixo')

    primeiro, segundo = _dois_numeros(corpo)
    if primeiro is None and segundo is None:
        # P2-5 (#322 rodada 3): prefixo conhecido SEM número não é rótulo de
        # lançamento — 'Av. Brasil, 123' é endereço, 'R$ 5.000' é valor, 'M'
        # é carimbo vazio. Vai ao bucket de não reconhecidos; a UI decide
        # (#321).
        return _nao_reconhecido('sem_numero')
    if prefixo == 'm':
        # 'M-3-14511' → a matrícula é o ÚLTIMO número do carimbo ('14511'),
        # não o '3'; 'M: 12.345' → o único número que veio.
        return Rotulo(
            tipo=None, numero=None, matricula=segundo or primeiro,
            eh_matricula=True, reconhecido=True, motivo=None,
        )
    if primeiro is None:
        # R/Av com número só DEPOIS do separador ('Ra-237'): sem o número do
        # ATO não há lançamento a gravar — mesmo motivo do sem número.
        return _nao_reconhecido('sem_numero')
    return Rotulo(
        tipo=tipo, numero=primeiro, matricula=segundo,
        eh_matricula=False, reconhecido=True, motivo=None,
    )


def tipo_do_rotulo(texto):
    """Tipo que o prefixo do texto declara ('registro'/'averbacao'), ou None.

    P2-1 (#322 rodada 3): a duplicata compara TIPO + número — os dois lados
    com rótulo R/Av reconhecido e tipos DIFERENTES ('R-5' × 'AV5 M237')
    não colidem. Texto sem rótulo reconhecido (matrícula 'M…', número
    puro, texto comum) devolve None: lado sem tipo conhecido mantém a
    comparação antiga, de texto.
    """
    analisado = analisar_rotulo(texto)
    if analisado.reconhecido and not analisado.eh_matricula:
        return analisado.tipo
    return None


def resolver_tipo(
    tipo_explicito: str | None,
    rotulo_texto: str | Rotulo | None,
    tipo_sugerido: str | None,
) -> tuple[str | None, bool, str]:
    """Resolve o tipo do ato pela precedência estabelecida (#322 rodada 7).

    A escolha EXPLÍCITA do usuário não pode ser sobrescrita pelo rótulo:

    1. ``tipo_explicito`` em ``TIPOS_SUGERIDOS`` (usuário mudou o tipo na
       tela, inclusive via ``aplicar_linha``/fluxo "mudar tipo") — vence;
    2. ``tipo_explicito`` ``''`` (usuário LIMPOU o <select> do tipo) é
       decisão de "sem tipo", não ausência de decisão: devolve
       ``(None, False, 'limpo')`` ANTES de olhar rótulo/sugestão — sem
       isso o ``valor_final=''`` gravado caía no rótulo e o tipo apagado
       era importado sem aviso (P2-1, #322/PR #327; a pendência de
       ``tipo_sugerido`` volta a bloquear, como antes). ``None`` continua
       significando "sem decisão" e mantém a precedência abaixo;
    3. Rótulo efetivo com prefixo R/Av (lido como na rodada 6:
       ``valor_final`` → ``normalized`` → ``raw``, linha descartada
       ignorada);
    4. ``tipo_sugerido`` em ``TIPOS_SUGERIDOS`` (sugestão normalizada do OCR).

    Devolve ``(tipo | None, divergencia: bool, origem: str)``.
    ``origem`` é ``'explicito'``, ``'limpo'``, ``'rotulo'``, ``'sugerido'``
    ou ``'nenhum'``. ``divergencia`` é True quando o rótulo R/Av resolve e
    difere do ``tipo_sugerido`` válido. Módulo PURO, sem Django e sem I/O.
    """
    if isinstance(tipo_explicito, str):
        tipo_exp = tipo_explicito.strip()
        if tipo_exp in TIPOS_SUGERIDOS:
            return tipo_exp, False, 'explicito'
        if not tipo_exp:
            # P2-1 (#322 / PR #327): '' explícito É decisão.
            return None, False, 'limpo'

    analisado = (
        rotulo_texto
        if isinstance(rotulo_texto, Rotulo)
        else analisar_rotulo(rotulo_texto)
    )
    tipo_rotulo = (
        analisado.tipo
        if analisado.reconhecido and not analisado.eh_matricula
        else None
    )

    sug = (
        tipo_sugerido.strip()
        if isinstance(tipo_sugerido, str)
        else None
    )
    eh_sug_valido = sug in TIPOS_SUGERIDOS

    if tipo_rotulo in TIPOS_SUGERIDOS:
        divergencia = bool(eh_sug_valido and sug != tipo_rotulo)
        return tipo_rotulo, divergencia, 'rotulo'

    if eh_sug_valido:
        return sug, False, 'sugerido'

    return None, False, 'nenhum'
