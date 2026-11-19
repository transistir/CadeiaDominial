"""Comarca do cabeçalho e fallback de cartório."""

import re
from dataclasses import dataclass

from .estruturas import _normalizar_nome


# Cidade: hífen interno SEM espaços é parte do nome (XIQUE-XIQUE,
# SÃO JOÃO DEL-REI); com espaços em volta, ` - ` / ` / ` / ` , ` (ou
# apertado) separa a UF/estado. Apóstrofo preserva OLHO D'ÁGUA. O mesmo
# hífen interno engole a UF colada (ITAMARAJU-BA); o sufixo que é
# sigla/nome de estado é separado depois do match, em
# ``comarca_do_documento``.
_COMARCA = re.compile(
    r'COMARCA\s+DE\s+([A-ZÀ-Ú][A-ZÀ-Ú .\'’]*(?:-[A-ZÀ-Ú]+)*)'
    r'(?:\s*[-–—/,]\s*(?:ESTADO\s+D[AEO]\s+)?([A-ZÀ-Ú][A-ZÀ-Ú ]*))?',
    re.IGNORECASE,
)
_UFS = {
    'ACRE': 'AC', 'ALAGOAS': 'AL', 'AMAPA': 'AP', 'AMAZONAS': 'AM',
    'BAHIA': 'BA', 'CEARA': 'CE', 'DISTRITO FEDERAL': 'DF',
    'ESPIRITO SANTO': 'ES', 'GOIAS': 'GO', 'MARANHAO': 'MA',
    'MATO GROSSO': 'MT', 'MATO GROSSO DO SUL': 'MS', 'MINAS GERAIS': 'MG',
    'PARA': 'PA', 'PARAIBA': 'PB', 'PARANA': 'PR', 'PERNAMBUCO': 'PE',
    'PIAUI': 'PI', 'RIO DE JANEIRO': 'RJ', 'RIO GRANDE DO NORTE': 'RN',
    'RIO GRANDE DO SUL': 'RS', 'RONDONIA': 'RO', 'RORAIMA': 'RR',
    'SANTA CATARINA': 'SC', 'SAO PAULO': 'SP', 'SERGIPE': 'SE',
    'TOCANTINS': 'TO',
}
_SIGLAS = frozenset(_UFS.values())
LIMITE_CANDIDATOS_FALLBACK = 20
TAMANHO_CABECALHO = 600


@dataclass(frozen=True)
class Comarca:
    cidade: str
    uf: str | None = None


def comarca_do_documento(extracao):
    """``Comarca`` do CABEÇALHO (página 1, 600 primeiros caracteres).

    Só ``COMARCA DE <CIDADE>``: trecho do corpo que cita outra comarca não
    conta. Mais de uma cidade distinta no cabeçalho é ambíguo → ``None``.
    """
    textos = extracao.ocr_job.paginas.filter(numero_pagina=1).values_list(
        'texto_confirmado', 'texto_corrigido', 'texto_ocr',
    ).first() or ()
    texto = next((t for t in textos if t), '')[:TAMANHO_CABECALHO]
    achados = {}
    for achado in _COMARCA.finditer(texto):
        cidade = achado.group(1).strip(' .')
        if cidade:
            texto_uf = _normalizar_nome(achado.group(2) or '').upper()
            uf = _UFS.get(texto_uf) or (
                texto_uf if texto_uf in _SIGLAS else None
            )
            # UF colada por hífen (regressão do hífen interno, #318): o
            # mesmo hífen que preserva XIQUE-XIQUE engoliu a sigla em
            # `ITAMARAJU-BA`/`ITAMARAJU-BAHIA`. Sufixo que é sigla/nome de
            # estado separa: cidade = parte antes, UF = sufixo normalizado
            # (vence o grupo separado, que não coexiste no cabeçalho real).
            base, _, sufixo = cidade.rpartition('-')
            if base:
                chave_colada = _normalizar_nome(sufixo).upper()
                uf_colada = _UFS.get(chave_colada) or (
                    chave_colada if chave_colada in _SIGLAS else None
                )
                if uf_colada:
                    cidade, uf = base.strip(' .'), uf_colada
            _cidade, ufs = achados.setdefault(
                _normalizar_nome(cidade), (cidade, set()),
            )
            if uf:
                ufs.add(uf)
    if len(achados) != 1:
        return None
    (cidade, ufs), = achados.values()
    # Mesma cidade com UFs diferentes (BOM JESUS - PI / - GO) é ambígua.
    if len(ufs) > 1:
        return None
    return Comarca(cidade, next(iter(ufs), None))


def candidatos_cartorio_fallback(
    extracao, chave, indice, comarca=None,
) -> list[int]:
    """Candidatos de cartório quando o serviço não trouxe nenhum.

    Sem escrita: devolve os ``match_candidatos`` do campo; senão os estágios
    de ``fallback_cartorio`` — match único por nome (com a cidade da
    ``comarca``); cartórios da cidade da comarca (até 20, por nome); da UF
    (sem corte); lista completa (sem corte). Nunca vazio com o índice
    povoado.
    ``comarca`` vem de ``comarca_do_documento`` (calculada uma vez).
    """
    campo = extracao.campos.filter(chave=chave).first()
    if campo is None:
        return []
    if campo.match_candidatos:
        return list(campo.match_candidatos)
    return fallback_cartorio(campo, indice, comarca)


def fallback_cartorio(campo, indice, comarca, valor=None):
    """``valor`` (decisão em curso) tem precedência sobre o salvo.

    Estágios, parando no primeiro não vazio (incremento B do I-10):
    (a) match único do valor pelo índice; (b) cartórios da cidade da
    comarca (até 20); (c) cartórios da UF da comarca, sem corte;
    (d) lista completa, sem corte. Com cabeçalho ilegível (``comarca``
    ``None``) ou cidade fora do índice, o seletor ainda sai preenchido —
    nunca ``[]`` com o índice povoado.

    Trade-off dos estágios (c) e (d) sem limite (#318): a lista completa
    só é montada quando não há candidatos e, no pior caso, quando o
    cabeçalho é ilegível. Cortar em 500 deixava o registro na posição
    501+ inalcançável no ``<select>`` — e o save só aceita id que esteja
    no próprio fallback —, recriando a duplicata que o fallback existe
    para evitar. A alternativa era manter o beco sem saída.
    """
    valor = valor or campo.valor_final or campo.normalized
    escolhido, _candidatos = indice.match(
        valor, comarca.cidade if comarca else None,
        comarca.uf if comarca else None,
    )
    if escolhido is not None:
        return [escolhido]
    if comarca is not None:
        da_cidade = indice.ids_da_cidade(
            comarca.cidade, comarca.uf, LIMITE_CANDIDATOS_FALLBACK,
        )
        if da_cidade:
            return da_cidade
        da_uf = indice.ids_da_uf(comarca.uf)
        if da_uf:
            return da_uf
    return indice.ids_de_todos()
