"""Codec de valores do I-5 entre os três mundos da extração.

- *payload* do serviço de extração (schema A3): ``str``/``bool``/``null``;
- *formulário* de revisão: o texto canônico que o humano digita/edita;
- alvos Django: ``date``/``Decimal``/``bool``/``str``/``None``.

O texto canônico é determinístico: booleano ``'true'``/``'false'`` (nunca
``str(True)``), data ISO ``yyyy-mm-dd``, decimal com ponto. ``null`` é
texto vazio só na gravação — na releitura volta explicitamente ``None``.
Mensagens de erro carregam TIPO e LIMITES, nunca o valor lido (o payload
de matrícula é PII e `str(exc)` vive de logs e tracebacks).
"""

import datetime
import re
from decimal import Decimal, InvalidOperation

# Texto livre sem destino: o mesmo limite anti-lixo da validação de payload.
LIMITE_TEXTO = 10_000

# Motivo estável de pendência: tipo do valor não aceito pelo destino.
MOTIVO_INCOMPATIVEL = 'valor_incompativel_destino'
_INCOMPATIVEL = MOTIVO_INCOMPATIVEL

# Motivo estável de pendência: valor cabe na natureza, mas não nos limites.
MOTIVO_LIMITE = 'valor_acima_do_limite_destino'

# Decimal com expoente além disso é lixo/DoS: formatar materializaria
# milhares/milhões de caracteres antes de o limite do destino decidir.
LIMITE_EXPOENTE_DECIMAL = 10_000

_DATA_ESTRITA = re.compile(r'^\d{4}-\d{2}-\d{2}$')


class ValorInvalido(ValueError):
    """Valor do formulário não cabe no destino — vai para revisão."""

    # Preenchido pelo save quando o valor inválido não veio de uma decisão.
    chave = None


class ErroInterno(ValueError):
    """Tipo inesperado vindo do payload — bug do chamador, não do dado."""


def do_payload(tipo, valor):
    """Valor do payload A3 → texto canônico para ``CampoSugerido``.

    Aceita somente ``str``, ``bool`` (→ ``'true'``/``'false'``) e ``None``
    (→ ``''``). Qualquer outro tipo é erro interno: o schema A3 admitiu
    apenas string/booleano/null, então o que chegou fora disso é bug da
    desnormalização, não dado do documento.
    """
    if valor is None:
        return ''
    if isinstance(valor, bool):
        return 'true' if valor else 'false'
    if isinstance(valor, str):
        return valor
    raise ErroInterno(
        f'valor de tipo {tipo!r} no payload não é str/bool/null'
    )


def do_formulario(tipo, texto, destino=None):
    """Texto digitado no formulário → texto canônico, ou ``ValorInvalido``.

    ``destino`` vem de ``destinos.destino_de()``: ``Destino`` (objetos
    com ``max_length``/``max_digits``/``decimal_places`` como o Field
    Django alvo) ou ``SEM_DESTINO`` — de onde vêm os limites.

    ``tipo='area'`` é decimal (``Lancamento.area`` ≡ 12,4; SEM_DESTINO
    ≡ 20,4). Texto vazio/``None`` é o canônico de ``null``.
    """
    if texto is None:
        return ''
    if not isinstance(texto, str):
        raise ErroInterno(
            f'valor de tipo {tipo!r} do formulário não é str'
        )
    if texto == '':
        return ''

    if tipo == 'data':
        _validar_data(texto)
    elif tipo in ('decimal', 'area'):
        return _texto_decimal(texto, destino)
    elif tipo == 'texto':
        limite = _max_length_do_destino(destino)
        if len(texto) > limite:
            raise ValorInvalido(
                f'texto acima do limite de {limite} caracteres do destino'
            )
    elif tipo == 'enum':
        _validar_enum(texto, destino)
    elif tipo == 'booleano':
        if texto not in ('true', 'false'):
            raise ValorInvalido(
                "booleano só aceita o canônico 'true'/'false'"
            )
    else:
        raise ErroInterno(f'tipo {tipo!r} sem conversor de formulário')

    return texto


def para_python(tipo, texto):
    """Texto canônico gravado → valor Python do alvo Django.

    ``''``/``None`` → ``None`` explícito (null preservado); ``data`` →
    ``date``; ``decimal`` → ``Decimal``; ``booleano`` → ``True``/``False``;
    fora do canônico → ``ValorInvalido`` (quem gravou sem passar pelo
    codec deixou lixo que não pode virar valor silenciosamente).
    """
    if texto is None or texto == '':
        return None
    if not isinstance(texto, str):
        raise ErroInterno(
            f'valor de tipo {tipo!r} no banco não é str'
        )

    if tipo == 'data':
        _validar_data(texto)
        return datetime.date.fromisoformat(texto)
    if tipo in ('decimal', 'area'):
        try:
            return _validar_decimal_canonico(Decimal(texto))
        except InvalidOperation:
            raise ValorInvalido(
                'decimal gravado fora do canônico (não é número)'
            ) from None
    if tipo == 'booleano':
        if texto == 'true':
            return True
        if texto == 'false':
            return False
        raise ValorInvalido(
            "booleano gravado fora do canônico ('true'/'false')"
        )
    return texto


def validar_limites(campo, valor_efetivo):
    """O valor efetivo cabe nos limites do destino? Devolve motivo ou None.

    A sugestão do payload pode nunca ter passado pelo formulário; por isso
    ``max_length``/``max_digits``/``decimal_places`` são revalidados também
    na finalização e no save. ``MOTIVO_LIMITE`` independe de "conferido":
    valor fora dos limites não pode chegar à I-6.

    Só tipos com conversor de formulário são checados; ``parte``/``cartorio``
    /``ato`` têm a natureza validada por ``validar_destino``.
    """
    if valor_efetivo is None:
        return None
    tipo_valor = getattr(campo, 'tipo_valor', None) or 'texto'
    if tipo_valor not in (
        'texto', 'data', 'decimal', 'area', 'enum', 'booleano',
    ):
        return None

    if isinstance(valor_efetivo, str):
        texto = valor_efetivo
    elif isinstance(valor_efetivo, bool):
        texto = 'true' if valor_efetivo else 'false'
    elif isinstance(valor_efetivo, datetime.date):
        texto = valor_efetivo.isoformat()
    elif isinstance(valor_efetivo, Decimal):
        if not valor_efetivo.is_finite():
            return MOTIVO_LIMITE
        texto = format(valor_efetivo, 'f')
    else:
        return None

    try:
        do_formulario(tipo_valor, texto, campo)
    except (ValorInvalido, ErroInterno):
        return MOTIVO_LIMITE
    return None


def validar_destino(campo, valor_efetivo):
    """O valor efetivo é compatível com o destino? Sinônimos: motivo.

    ``campo`` é o destino da linha (``Destino``/``SEM_DESTINO`` ou o
    Field Django alvo, ambos expondo ``tipo_valor`` e os limites).
    Retorna ``'valor_incompativel_destino'`` quando o valor é de uma
    natureza que o destino não aceita — a pendência independe de
    "conferido" (§18) — ou ``None`` quando cabe.

    Usado por ``desnormalizar`` e por ``pendencias``; limites (tamanho/
    dígitos) NOT são alvo aqui — quem checa é ``do_formulario``.
    """
    if valor_efetivo is None:
        return None
    tipo_valor = getattr(campo, 'tipo_valor', None) or 'texto'
    if isinstance(valor_efetivo, bool):
        return None if tipo_valor == 'booleano' else _INCOMPATIVEL
    if isinstance(valor_efetivo, datetime.date):
        return None if tipo_valor == 'data' else _INCOMPATIVEL
    if isinstance(valor_efetivo, Decimal):
        return None if tipo_valor in ('decimal', 'area') else _INCOMPATIVEL
    if not isinstance(valor_efetivo, str):
        return _INCOMPATIVEL

    if tipo_valor in ('decimal', 'area'):
        try:
            _validar_decimal_canonico(Decimal(valor_efetivo))
        except (InvalidOperation, ValorInvalido):
            return _INCOMPATIVEL
        return None
    if tipo_valor == 'data':
        try:
            _validar_data(valor_efetivo)
        except ValorInvalido:
            return _INCOMPATIVEL
        return None
    if tipo_valor == 'booleano':
        return None if valor_efetivo in ('true', 'false') else _INCOMPATIVEL
    choices = getattr(campo, 'choices', None)
    if choices and valor_efetivo not in {c[0] for c in choices}:
        return _INCOMPATIVEL
    return None


def _validar_data(texto):
    """Regex estrita + ``fromisoformat``: ``2024-02-30`` (impossível),
    ``20240101`` (colado) e ``31/12/2024`` (local) não passam."""
    if not _DATA_ESTRITA.fullmatch(texto):
        raise ValorInvalido(
            "data fora do ISO 'yyyy-mm-dd' estrito"
        )
    try:
        datetime.date.fromisoformat(texto)
    except ValueError:
        raise ValorInvalido('data inexistente no calendário') from None


def _texto_decimal(texto, destino):
    """Decimal ≥ 0 com ``.`` ou ``,``, cabendo em max_digits/decimal_places."""
    canonico = ''.join(texto.split()).replace(',', '.')
    try:
        numero = Decimal(canonico)
    except InvalidOperation:
        raise ValorInvalido('decimal não é número') from None
    numero = _validar_decimal_canonico(numero)
    if numero < 0:
        raise ValorInvalido('decimal negativo não cabe em campo de valor')

    max_digits = getattr(destino, 'max_digits', None)
    decimal_places = getattr(destino, 'decimal_places', None)
    inteira, _, fracionaria = format(numero, 'f').partition('.')
    digitos = len(inteira) if inteira != '0' else 0
    digitos_fracionarios = len(fracionaria)
    if decimal_places is not None and digitos_fracionarios > decimal_places:
        raise ValorInvalido(
            f'decimal acima das {decimal_places} casas do destino'
        )
    if max_digits is not None and digitos + digitos_fracionarios > max_digits:
        raise ValorInvalido(
            f'decimal acima dos {max_digits} dígitos do destino'
        )
    return format(numero, 'f')


def _validar_decimal_canonico(numero):
    """Rejeita NaN/Infinity e expoentes absurdos antes de materializar.

    ``Decimal`` aceita ``NaN``/``Infinity`` e ``1e999999`` sem erro; a
    explosão só apareceria no ``format(..., 'f')``. A checagem é O(1) e
    vale também para valores lidos do banco em ``para_python``.
    """
    if not numero.is_finite():
        raise ValorInvalido('decimal não finito')
    if abs(numero.adjusted()) > LIMITE_EXPOENTE_DECIMAL:
        raise ValorInvalido('decimal com expoente absurdo')
    return numero


def _validar_enum(texto, destino):
    choices = getattr(destino, 'choices', None) if destino is not None else None
    if not choices:
        return
    if texto not in {choice[0] for choice in choices}:
        raise ValorInvalido('valor fora do enum do destino')


def _max_length_do_destino(destino):
    limite = getattr(destino, 'max_length', None) if destino is not None else None
    return limite if limite else LIMITE_TEXTO
