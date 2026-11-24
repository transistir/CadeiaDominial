"""Vocabulário pinado do prefill (#372): cópia vendorizada, sem produção.

O app **não** gera dicionário nem varre o banco de produção: lê o JSON
commitado em ``ia_ocr/schemas/vocabulario_prod.json``, cópia BYTE A BYTE de
``dados/vocabulario_prod.sintetico.json`` do ocr-service (#74, Fase A.1).
Os dados são 100% sintéticos (12 registros, 3 cartórios fictícios).

Duas conferências de integridade, com significados DIFERENTES:

- ``SHA256_DO_ARQUIVO`` — sha256 dos BYTES do arquivo vendorizado (o que
  ``sha256sum`` imprime). Qualquer reformatação do JSON muda este hash;
- ``SHA256_DO_DOCUMENTO`` — hash CANÔNICO do documento (``json.dumps`` com
  ``sort_keys``/separadores compactos, ``ensure_ascii=False`` e o
  ``meta.sha256`` removido antes de hashear). É o mesmo ``meta.sha256``
  gravado pelo gerador do artefato.

Casamento de um valor lido (A3) contra um campo do vocabulário, em três
degraus, do mais estrito ao mais tolerante:

1. ``exato`` — igual ao valor canônico, só aparando espaços das pontas;
2. ``normalizado`` — sem acento, sem caixa, espaços colapsados e ordem dos
   tokens ignorada (``"Venda e compra"`` ≡ ``"Compra e Venda"``);
3. ``fuzzy`` — similaridade de tokens acima de ``LIMIAR_FUZZY``, exigindo
   vencedor único com margem sobre o segundo colocado.

Empate entre candidatos ou similaridade baixa NÃO produzem valor: o
chamador mantém o valor do A3 (``Casamento.valor`` é ``None``). O
vocabulário nunca inventa valor.
"""

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from typing import Optional

SCHEMA = 'vocabulario-prod/v1'
# Campo do vocabulário que o prefill consome (#372): a forma do ato.
CAMPO_FORMA = 'forma'
DIRETORIO = Path(__file__).resolve().parent / 'schemas'
CAMINHO_VOCABULARIO = DIRETORIO / 'vocabulario_prod.json'

# sha256 dos BYTES de ``vocabulario_prod.json`` (artefato do ocr-service #74).
SHA256_DO_ARQUIVO = (
    '8f684d3b8022e5399086d97ce871c091c8d45b4d2474e67f0ad65c05381a6932'
)
# ``meta.sha256``: hash canônico do documento, NÃO o dos bytes do arquivo.
SHA256_DO_DOCUMENTO = (
    '232daf1b3c108e4280d82be8cf4c0b3c8fb2f38bb9f04038bf74b729bfaca8c6'
)

EXATO = 'exato'
NORMALIZADO = 'normalizado'
FUZZY = 'fuzzy'

MOTIVO_EMPATE = 'empate'
MOTIVO_BAIXA_CONFIANCA = 'baixa_confianca'
MOTIVO_VAZIO = 'vazio'

# Só vale a pena arriscar fuzzy em texto com alguma substância e com um
# vencedor claramente destacado do segundo colocado.
LIMIAR_FUZZY = 0.88
MARGEM_FUZZY = 0.05
MIN_CARACTERES_FUZZY = 5

_PONTUACAO = re.compile(r'[^\w\s]')


class VocabularioInvalido(Exception):
    """O JSON vendorizado não confere com o artefato pinado."""


@dataclass(frozen=True)
class Entrada:
    """Um valor canônico do vocabulário e quantas vezes apareceu."""

    valor: str
    ocorrencias: int


@dataclass(frozen=True)
class Casamento:
    """Resultado do casamento; ``valor`` ``None`` = mantém o valor do A3."""

    campo: str
    texto: str
    valor: Optional[str] = None
    metodo: Optional[str] = None
    ocorrencias: int = 0
    similaridade: float = 0.0
    motivo: Optional[str] = None

    @property
    def casa(self):
        return self.valor is not None


def sha256_do_arquivo(caminho=None):
    """sha256 dos bytes do arquivo (default: o JSON vendorizado)."""
    caminho = Path(caminho) if caminho is not None else CAMINHO_VOCABULARIO
    try:
        return hashlib.sha256(caminho.read_bytes()).hexdigest()
    except OSError as exc:
        raise VocabularioInvalido(
            f'não foi possível ler {caminho}: {exc}'
        ) from exc


def sha256_do_documento(documento):
    """Hash canônico do documento, igual ao ``meta.sha256`` do artefato."""
    copia = dict(documento)
    meta = dict(copia.get('meta') or {})
    meta.pop('sha256', None)
    copia['meta'] = meta
    canonico = json.dumps(
        copia, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
    )
    return hashlib.sha256(canonico.encode('utf-8')).hexdigest()


@lru_cache(maxsize=1)
def carregar():
    """Documento vendorizado, conferido contra os dois hashes pinados.

    Só abre o arquivo do pacote — nenhuma conexão, nenhuma variável de
    ambiente, nenhuma query. Levanta ``VocabularioInvalido`` se os bytes ou
    o hash canônico divergirem do artefato que o repo pinou.
    """
    if sha256_do_arquivo() != SHA256_DO_ARQUIVO:
        raise VocabularioInvalido(
            'vocabulario_prod.json não é a cópia byte a byte do artefato '
            f'dos bytes {SHA256_DO_ARQUIVO}'
        )
    try:
        with CAMINHO_VOCABULARIO.open(encoding='utf-8') as arquivo:
            documento = json.load(arquivo)
    except OSError as exc:
        raise VocabularioInvalido(
            f'não foi possível abrir {CAMINHO_VOCABULARIO}: {exc}'
        ) from exc
    except json.JSONDecodeError as exc:
        raise VocabularioInvalido(
            f'{CAMINHO_VOCABULARIO.name} não é JSON válido: {exc}'
        ) from exc
    if documento.get('schema') != SCHEMA:
        raise VocabularioInvalido(
            f'schema {documento.get("schema")!r} != {SCHEMA!r}'
        )
    if (documento.get('meta') or {}).get('sha256') != SHA256_DO_DOCUMENTO:
        raise VocabularioInvalido('meta.sha256 diverge do artefato pinado')
    if sha256_do_documento(documento) != SHA256_DO_DOCUMENTO:
        raise VocabularioInvalido('hash canônico do documento divergiu')
    return documento


@lru_cache(maxsize=None)
def entradas(campo):
    """``Entrada`` do campo do vocabulário (``forma``, ``titulo``...)."""
    documento = carregar()
    if campo not in documento:
        raise KeyError(campo)
    grupo = documento[campo]
    if not isinstance(grupo, list):
        raise VocabularioInvalido(f'campo {campo!r} não é lista')
    return tuple(
        Entrada(valor=item['valor'], ocorrencias=int(item['ocorrencias']))
        for item in grupo
    )


def _sem_acento(texto):
    decomposto = unicodedata.normalize('NFKD', texto)
    return ''.join(
        caractere for caractere in decomposto
        if not unicodedata.combining(caractere)
    )


def _normalizar(texto):
    return ' '.join(_sem_acento(str(texto)).casefold().split())


def _tokens(texto):
    return tuple(sorted(_PONTUACAO.sub(' ', _normalizar(texto)).split()))


def _sem_resultado(campo, texto, motivo):
    return Casamento(campo=campo, texto=texto, motivo=motivo)


def _token_com_erro_de_digitacao(lido, canonico):
    """Um token é erro de digitação do outro: mesmo tamanho, ≤1 troca.

    Vale 0 diferença, 1 substituição de caractere ou 1 transposição de
    caracteres adjacentes. Inserção/remoção reprova (tamanhos diferentes).
    """
    if len(lido) != len(canonico):
        return False
    diferentes = [
        indice for indice, (a, b) in enumerate(zip(lido, canonico)) if a != b
    ]
    if len(diferentes) <= 1:
        return True
    if len(diferentes) != 2:
        return False
    primeiro, segundo = diferentes
    return (
        segundo == primeiro + 1
        and lido[primeiro] == canonico[segundo]
        and lido[segundo] == canonico[primeiro]
    )


def _erro_de_digitacao(lido, canonico):
    """``lido`` é erro de digitação token a token de ``canonico``?

    Mesmo número de tokens (já normalizados e ordenados) e cada um na mesma
    posição a até 1 substituição/transposição, com o MESMO tamanho. Por isso
    ``'Daçao'`` (5 letras, pagamento em dinheiro) não casa com ``'Doação'``
    (6 letras): faltou uma letra, não foi erro de digitação.
    """
    tokens_lidos = _tokens(lido)
    tokens_canonicos = _tokens(canonico)
    if not tokens_lidos or len(tokens_lidos) != len(tokens_canonicos):
        return False
    return all(
        _token_com_erro_de_digitacao(a, b)
        for a, b in zip(tokens_lidos, tokens_canonicos)
    )


def _resultado(campo, texto, entrada, metodo, similaridade):
    return Casamento(
        campo=campo,
        texto=texto,
        valor=entrada.valor,
        metodo=metodo,
        ocorrencias=entrada.ocorrencias,
        similaridade=similaridade,
    )


def casar(campo, texto):
    """Casa ``texto`` com o vocabulário de ``campo`` do jeito mais estrito.

    Devolve sempre ``Casamento``: ``casa`` indica se há valor canônico.
    Empate, baixa confiança e texto vazio vêm com ``valor=None`` e um
    ``motivo`` — o chamador mantém o valor do A3, nunca inventa.
    """
    bruto = '' if texto is None else str(texto).strip()
    if not bruto:
        return _sem_resultado(campo, bruto, MOTIVO_VAZIO)
    candidatas = entradas(campo)

    exatos = [item for item in candidatas if item.valor == bruto]
    if len(exatos) == 1:
        return _resultado(campo, bruto, exatos[0], EXATO, 1.0)
    if len(exatos) > 1:
        return _sem_resultado(campo, bruto, MOTIVO_EMPATE)

    normalizado = _normalizar(bruto)
    tokens = _tokens(bruto)
    equiparadas = [
        item for item in candidatas
        if _normalizar(item.valor) == normalizado
        or _tokens(item.valor) == tokens
    ]
    if len(equiparadas) == 1:
        return _resultado(campo, bruto, equiparadas[0], NORMALIZADO, 1.0)
    if len(equiparadas) > 1:
        return _sem_resultado(campo, bruto, MOTIVO_EMPATE)

    if not tokens or len(normalizado) < MIN_CARACTERES_FUZZY:
        return _sem_resultado(campo, bruto, MOTIVO_BAIXA_CONFIANCA)

    # Similaridade global sozinha dá falso positivo ('Daçao' ~ 'Doação').
    # Só entram no fuzzy candidatos que sejam erro de digitação token a token.
    aproximadas = [
        item for item in candidatas if _erro_de_digitacao(bruto, item.valor)
    ]
    if not aproximadas:
        return _sem_resultado(campo, bruto, MOTIVO_BAIXA_CONFIANCA)

    alvo = ' '.join(tokens)
    # Chave explícita: nunca comparar ``Entrada`` (dois valores canônicos
    # iguais empatam em ratio e valor — antes virava TypeError).
    pontuadas = sorted(
        (
            (
                SequenceMatcher(
                    None, alvo, ' '.join(_tokens(item.valor)),
                ).ratio(),
                item,
            )
            for item in aproximadas
        ),
        key=lambda par: (par[0], par[1].valor),
    )
    melhor_ratio, melhor = pontuadas[-1]
    if melhor_ratio < LIMIAR_FUZZY:
        return _sem_resultado(campo, bruto, MOTIVO_BAIXA_CONFIANCA)
    if len(pontuadas) > 1 and melhor_ratio - pontuadas[-2][0] < MARGEM_FUZZY:
        return _sem_resultado(campo, bruto, MOTIVO_EMPATE)
    return _resultado(campo, bruto, melhor, FUZZY, melhor_ratio)
