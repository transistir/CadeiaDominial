"""Parser de rótulos de lançamento (I-11b / #322).

Rótulo é o carimbo que abre cada ato na matrícula: ``'R-1'``,
``'Av: 2-237'``, ``'M-3-14511'``. Decisão do cliente (Hiure, 09/11):
lançamento SEMPRE começa com ``R`` (registro) ou ``Av`` (averbação);
``M`` é número de matrícula — rótulo válido, mas nunca um lançamento;
``"R: 1-237"`` traz número de ato ``1`` e matrícula ``237``, e o texto
depois do carimbo (protocolo, data, comarca) é ignorado.

Módulo PURO, sem Django e sem I/O. ``analisar_rotulo`` NUNCA levanta
exceção: entrada vazia, estranha, com prefixo desconhecido ou SEM número
do ato cai em ``reconhecido=False`` com um ``motivo`` — o destino do
bucket de não reconhecidos é decisão da UI (#321). ``classificar_atos``
consome o payload da extração (``document`` + ``acts``) e devolve o
cabeçalho do início de matrícula (que NÃO é um ato), os lançamentos em
ordem REVERSA (maior ``ordem`` primeiro; sem ``ordem`` válida, o índice
do payload + 1 — a mesma regra da revisão) e os não reconhecidos.
"""

import math
import re
from dataclasses import dataclass

# Valores válidos de ``tipo_sugerido.normalized`` no contrato A3.
TIPOS_SUGERIDOS = ('registro', 'averbacao', 'inicio_matricula')

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

# Campos do cabeçalho (``/document/*``) que formam o início de matrícula.
CAMPOS_INICIO_MATRICULA = (
    'livro', 'numero', 'cartorio', 'area', 'data', 'imovel_descricao',
)


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


def classificar_atos(payload) -> Classificacao:
    """Classifica os atos do payload da extração; nunca levanta exceção.

    - ``inicio_matricula``: os campos do cabeçalho ``/document/*`` (que
      NÃO é um ato); ``None`` sem ``document``.
    - ``lancamentos``: só o que é R/Av com número, em ordem REVERSA; o tipo
      resolvido prefere o RÓTULO — ``tipo_sugerido.normalized`` presente e
      válido é usado quando concorda; divergindo, prevalece o rótulo e o
      item sai com ``divergencia=True`` (não é erro fatal).
    - ``nao_reconhecidos``: rótulos que o parser não entendeu (rotulo
      ``M`` com número não entra em nenhuma das duas listas — é referência
      de matrícula, não lançamento, e não é erro).

    ``ordem``: a chave de ordenação é a ``ordem`` válida do ato ou, sem
    ela, o índice do payload + 1 (``revisao.py`` idem — P1-2, #322 rodada
    3); o campo ``ordem`` exposto no item segue COMO VEIO (índice + 1
    quando a chave não veio). ``acts`` que não é lista e ``ordem``
    NaN/Infinity não levantam exceção: caem em vazio/índice (P2-6).
    """
    document = payload.get('document') if isinstance(payload, dict) else None
    inicio = None
    if isinstance(document, dict) and document:
        inicio = {
            nome: _valor_do_campo(document.get(nome))
            for nome in CAMPOS_INICIO_MATRICULA
        }

    ordenaveis = []
    nao_reconhecidos = []
    atos = payload.get('acts') if isinstance(payload, dict) else None
    if not isinstance(atos, list):
        # ``acts`` que não é lista (número, bool, texto) não é iterável de
        # atos: sem lançamentos e sem não reconhecidos — e sem TypeError
        # (#322 rodada 3, P2-6).
        atos = []
    for indice, ato in enumerate(atos):
        if not isinstance(ato, dict):
            continue
        ordem = ato['ordem'] if 'ordem' in ato else indice + 1
        rotulo = _valor_do_campo(ato.get('rotulo'))
        analisado = analisar_rotulo(rotulo)
        if not analisado.reconhecido:
            nao_reconhecidos.append({
                'ordem': ordem,
                'rotulo': rotulo,
                'motivo': analisado.motivo,
                'ato': ato,
            })
            continue
        if analisado.eh_matricula:
            continue
        sugerido = _valor_do_campo(ato.get('tipo_sugerido'))
        # Divergência só quando os DOIS lados são tipos válidos e diferem:
        # tipo_sugerido ausente/inválido é como se não existisse (o prefixo
        # do rótulo decide sozinho, sem registrar conflito).
        divergencia = (
            sugerido in TIPOS_SUGERIDOS and sugerido != analisado.tipo
        )
        ordenaveis.append((
            _ordem_ordenavel(ato.get('ordem'), indice),
            {
                'ordem': ordem,
                'tipo': analisado.tipo,
                'numero': analisado.numero,
                'matricula': analisado.matricula,
                'ato': ato,
                'divergencia': divergencia,
            },
        ))
    # Chave inteira (``ordem`` vem como string no payload real, #322) com
    # fallback no índice do payload; o campo exposto segue como veio.
    ordenaveis.sort(key=lambda par: par[0], reverse=True)
    return Classificacao(
        inicio_matricula=inicio,
        lancamentos=[item for _, item in ordenaveis],
        nao_reconhecidos=nao_reconhecidos,
    )
