"""Utilitários puros de leitura para CNS de cartório e normalização de nome.

Nenhuma função aqui acessa o banco de dados. Servem de apoio ao
relatório de diagnóstico `relatorio_cartorios_suspeitos` (issue #110).
"""

import re
import unicodedata
from dataclasses import dataclass

PREFIXO_SINTETICO = 'CNS'
PREFIXO_INSTITUCIONAL = '8888'

CNS_VAZIO = 'CNS_VAZIO'
CNS_SINTETICO = 'CNS_SINTETICO'
CNS_INSTITUCIONAL = 'CNS_INSTITUCIONAL'
CNS_VALIDO = 'CNS_VALIDO'
DV_NAO_CONFERE = 'DV_NAO_CONFERE'
FORMATO_NAO_PADRAO = 'FORMATO_NAO_PADRAO'


@dataclass(frozen=True, slots=True)
class ClassificacaoCns:
    """Resultado da classificação de um CNS. É evidência, não decisão.

    `dv_confere` é `None` quando o valor não tem o formato de 6 dígitos
    (não se aplica verificação de dígito verificador).
    """

    valor_original: str
    sintetico: bool
    institucional: bool
    dv_confere: bool | None
    motivo: str


def cns_eh_sintetico(cns):
    """CNS sintético = criado automaticamente pelo bug legado (issue #110).

    Regra: `UPPER(TRIM(cns))` começa com o prefixo ``CNS``.
    """
    if not isinstance(cns, str):
        raise TypeError('O CNS deve ser um texto.')
    return cns.strip().upper().startswith(PREFIXO_SINTETICO)


def cns_eh_institucional(cns):
    """CNS institucional (Registro de Imóveis do Brasil) começa com ``8888`` e tem 6 dígitos."""
    if not isinstance(cns, str):
        raise TypeError('O CNS deve ser um texto.')
    valor = cns.strip()
    return bool(re.fullmatch(r'\d{6}', valor)) and valor.startswith(PREFIXO_INSTITUCIONAL)


def calcular_dv_cns(cinco_digitos):
    """Calcula o dígito verificador (módulo 10, algoritmo de Luhn) dos 5 primeiros dígitos."""
    if not isinstance(cinco_digitos, str) or not re.fullmatch(r'\d{5}', cinco_digitos):
        raise ValueError('Os cinco primeiros dígitos do CNS devem ser numéricos.')

    total = 0
    for indice, caractere in enumerate(reversed(cinco_digitos)):
        digito = int(caractere)
        if indice % 2 == 0:
            digito *= 2
            if digito > 9:
                digito -= 9
        total += digito
    return (10 - (total % 10)) % 10


def cns_dv_confere(cns):
    """Retorna se o DV confere; `None` quando o CNS não tem o formato de 6 dígitos.

    Falha de DV nunca é prova de inexistência do cartório — o registro
    oficial sempre prevalece sobre esta heurística (ver plano §5).
    """
    if not isinstance(cns, str):
        raise TypeError('O CNS deve ser um texto.')
    valor = cns.strip()
    if not re.fullmatch(r'\d{6}', valor):
        return None
    cinco_digitos, dv_informado = valor[:5], int(valor[5])
    return calcular_dv_cns(cinco_digitos) == dv_informado


def classificar_cns(cns):
    """Classifica um CNS em uma das categorias de evidência descritas no plano §5."""
    if not isinstance(cns, str):
        raise TypeError('O CNS deve ser um texto.')
    valor = cns.strip()

    if not valor:
        return ClassificacaoCns(valor, False, False, None, CNS_VAZIO)

    if cns_eh_sintetico(valor):
        return ClassificacaoCns(valor, True, False, None, CNS_SINTETICO)

    if cns_eh_institucional(valor):
        return ClassificacaoCns(valor, False, True, cns_dv_confere(valor), CNS_INSTITUCIONAL)

    dv_confere = cns_dv_confere(valor)
    if dv_confere is None:
        return ClassificacaoCns(valor, False, False, None, FORMATO_NAO_PADRAO)
    if dv_confere:
        return ClassificacaoCns(valor, False, False, True, CNS_VALIDO)
    return ClassificacaoCns(valor, False, False, False, DV_NAO_CONFERE)


def normalizar_nome(nome):
    """Normalização auxiliar de nome de cartório: NFKD + casefold + remove pontuação + colapsa espaços.

    Usada apenas para SUGERIR candidatos (nunca decide automaticamente,
    ver plano §4). Limitações conhecidas, deliberadamente não tratadas:
    ordinais ("1º" vs "Primeiro"), siglas ("CRI" vs "RI") e o prefixo
    "Cartório de" podem produzir normalizações diferentes para o mesmo
    cartório.
    """
    if not isinstance(nome, str):
        raise TypeError('O nome do cartório deve ser um texto.')

    forma_decomposta = unicodedata.normalize('NFKD', nome)
    sem_acentos = ''.join(
        caractere for caractere in forma_decomposta if not unicodedata.combining(caractere)
    )
    minusculo = sem_acentos.casefold()
    sem_pontuacao = re.sub(r'[^\w\s]', ' ', minusculo, flags=re.UNICODE)
    return re.sub(r'\s+', ' ', sem_pontuacao).strip()


# Nome explícito preservado para deixar claro o domínio nos pontos de chamada.
normalizar_nome_cartorio = normalizar_nome
