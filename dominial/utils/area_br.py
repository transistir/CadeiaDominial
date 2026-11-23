"""Parser único de área em hectares (issue #396).

Por que existe: o campo Área aceitava `1.000` como decimal (`float('1.000') ==
1.0`) e gravava `1.0000` ha — mil hectares viravam um, sem erro. Havia quatro
conversões divergentes nos services (`float(area.replace(',', '.'))`) e a
validação usava `float(area)`. Este módulo é o único caminho de texto → área.

Regra (registrada na #396 antes do código):

- vírgula é **sempre** decimal (convenção pt-BR do produto, a mesma de
  ``ia_ocr/revisao/area_ha.py``);
- ponto é milhar **somente** quando forma grupo de 3 dígitos **e** há vírgula
  ou mais de um ponto;
- separador único com exatamente 3 dígitos após e 1–3 antes é **ambíguo**
  (milhar × decimal) → ``AreaInvalida``, nunca interpretação;
- máximo de 4 casas e 8 dígitos inteiros (limite de ``numeric(12, 4)``);
- tudo em ``Decimal``; nenhum caminho usa ``float``.

O custo aceito é ``55,698`` exigir ``55,6980`` ou ``55698`` — preferível a
mudar magnitude em silêncio.
"""

from decimal import Decimal, InvalidOperation
import re

CASAS_DECIMAIS = 4
MAX_DIGITOS_INTEIROS = 8
_QUANTUM = Decimal('0.0001')
_MAX_ECO = 24  # não ecoar entrada gigante na mensagem de erro

_SO_DIGITOS_E_SEPARADORES = re.compile(r'^[0-9.,]+$')
# Grupo de milhar com ponto: 1.234 / 1.234.567 (usado com e sem vírgula).
_MILHAR = re.compile(r'^[0-9]{1,3}(?:\.[0-9]{3})+$')


class AreaInvalida(ValueError):
    """Entrada de área que não pode ser convertida sem adivinhar."""

    def __init__(self, mensagem, valor=None):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.valor = valor


def _eco(valor):
    texto = str(valor).strip()
    return texto if len(texto) <= _MAX_ECO else texto[:_MAX_ECO] + '…'


def _erro_invalido(valor, detalhe=''):
    sufixo = f' {detalhe}' if detalhe else ''
    return AreaInvalida(
        f'Área inválida: {_eco(valor)!r}.{sufixo} '
        'Use apenas números, com vírgula decimal (ex.: 150,5000).',
        valor,
    )


def _erro_ambiguo(valor, inteiro, decimais):
    """Mensagem com AS DUAS leituras, sem escolher por conta própria."""
    como_decimal = Decimal(f'{inteiro}.{decimais}')
    como_milhar = Decimal(f'{inteiro}{decimais}')
    return AreaInvalida(
        'Área ambígua: '
        f'{_eco(valor)} pode ser {como_decimal:.4f} ha (decimal) ou '
        f'{como_milhar:.0f} ha (milhar). '
        f'Digite {como_decimal:.4f} ou {como_milhar:.0f} para confirmar.',
        valor,
    )


def _partes(texto):
    """Devolve (inteiro, decimais) ou levanta ``AreaInvalida``."""
    if ',' in texto and '.' in texto:
        if texto.rfind('.') > texto.rfind(','):
            # 1,234.56: mistura de convenções (en-US). Recusar, não converter.
            raise _erro_invalido(
                texto, 'Formato com ponto depois da vírgula não é aceito.'
            )
        inteiro, decimais = texto.rsplit(',', 1)
        if not _MILHAR.match(inteiro):
            raise _erro_invalido(texto, 'Separador de milhar fora de grupos de 3.')
        inteiro = inteiro.replace('.', '')
        return inteiro, decimais

    if '.' in texto:
        partes = texto.split('.')
        if len(partes) == 2:
            inteiro, decimais = partes
            # `0.012` (120 m²) NÃO é ambíguo: zero à esquerda não abre grupo de
            # milhar. A ambiguidade exige inteiro sem zero inicial.
            if (
                len(decimais) == 3
                and 1 <= len(inteiro) <= 3
                and not inteiro.startswith('0')
            ):
                raise _erro_ambiguo(texto, inteiro, decimais)
            return inteiro, decimais
        # Dois ou mais pontos: só pode ser milhar (1.234.567).
        if not _MILHAR.match(texto):
            raise _erro_invalido(texto, 'Separador de milhar fora de grupos de 3.')
        return texto.replace('.', ''), ''

    if ',' in texto:
        partes = texto.split(',')
        if len(partes) != 2:
            raise _erro_invalido(texto, 'Mais de uma vírgula.')
        inteiro, decimais = partes
        if (
            len(decimais) == 3
            and 1 <= len(inteiro) <= 3
            and not inteiro.startswith('0')
        ):
            raise _erro_ambiguo(texto, inteiro, decimais)
        return inteiro, decimais

    return texto, ''


def parse_area_br(valor, max_inteiros=MAX_DIGITOS_INTEIROS):
    """Texto do formulário → ``Decimal`` em hectares (4 casas), ou ``None``.

    Aceita ``None``/string vazia como "sem área". ``Decimal`` já convertido é
    quantizado (caminho da herança e da revisão). Qualquer ambiguidade ou
    formato inválido levanta ``AreaInvalida`` — nunca devolve um número
    adivinhado.
    """
    if valor is None:
        return None
    if isinstance(valor, Decimal):
        return valor.quantize(_QUANTUM)
    if isinstance(valor, bool) or isinstance(valor, float):
        raise AreaInvalida(
            'Área inválida: valor numérico de ponto flutuante não é aceito; '
            'envie o texto como o usuário digitou.',
            valor,
        )
    if isinstance(valor, int):
        valor = str(valor)

    texto = str(valor).replace('\u00a0', ' ').strip()
    if not texto:
        return None
    if any(caractere.isspace() for caractere in texto):
        raise _erro_invalido(texto, 'Não use espaços.')
    if not _SO_DIGITOS_E_SEPARADORES.match(texto):
        raise _erro_invalido(texto, 'Caracteres não numéricos.')

    inteiro, decimais = _partes(texto)
    if not inteiro:
        raise _erro_invalido(texto, 'Falta a parte inteira.')
    if len(decimais) > CASAS_DECIMAIS:
        raise _erro_invalido(
            texto, f'Máximo de {CASAS_DECIMAIS} casas decimais.'
        )
    if (
        max_inteiros is not None
        and len(inteiro.lstrip('0') or '0') > max_inteiros
    ):
        raise _erro_invalido(texto, 'Valor acima do limite da coluna de área.')

    try:
        area = Decimal(f"{inteiro or '0'}.{decimais or '0'}")
    except InvalidOperation:
        raise _erro_invalido(texto) from None
    return area.quantize(_QUANTUM)
