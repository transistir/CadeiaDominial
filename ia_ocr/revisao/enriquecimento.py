"""Matching determinístico escrito numa cópia do payload A3."""

import copy

from .estruturas import MATCH_PESSOA_CANDIDATOS


# Campos fieldCartorio do A3, por posição no payload (schema vendorizado):
# cada um recebe ``match_sugerido`` no enriquecimento.

_CARTORIOS_DO_DOCUMENTO = ('cartorio', 'cri_atual')
_CARTORIOS_DO_ATO = ('cartorio_transmissao',)

def _normalized(no):
    """``normalized`` de um campo A3; ``None`` se o nó não é dict."""
    return no.get('normalized') if isinstance(no, dict) else None


def enriquecer_payload(payload, indice_pessoas, indice_cartorios):
    """Matching determinístico escrito numa CÓPIA do payload A3.

    - todo fieldCartorio (``document.cartorio``/``cri_atual``,
      ``acts[].cartorio_transmissao``, ``acts[].origem.cartorio``) recebe
      ``match_sugerido`` = ``{cartorio_id: único|None, candidatos: [ids]}``;
    - toda parte (``acts[].partes[]``) recebe ``match_pessoa_id``
      (único|None) e ``match_pessoa_candidatos`` (ids, vazia quando há
      único) pelo nome + documento de identificação.

    O original não é mutado. ``match_sugerido`` e ``match_pessoa_id`` são do
    schema vendorizado; ``match_pessoa_candidatos`` é extensão LOCAL (o A3
    da party não tem lista de candidatos) — o enriquecido só é válido no A3
    sem ela, e só ``payload_servico`` passa por ``validar_payload``. Match
    vindo do serviço, se houver, é sobrescrito — matching é decisão desta
    camada, nunca do modelo.
    """
    enriquecido = copy.deepcopy(payload)
    document = enriquecido.get('document')
    if isinstance(document, dict):
        for nome in _CARTORIOS_DO_DOCUMENTO:
            _sugerir_cartorio(document.get(nome), indice_cartorios)
    for ato in enriquecido.get('acts') or []:
        if not isinstance(ato, dict):
            continue
        for nome in _CARTORIOS_DO_ATO:
            _sugerir_cartorio(ato.get(nome), indice_cartorios)
        origem = ato.get('origem')
        if isinstance(origem, dict):
            _sugerir_cartorio(origem.get('cartorio'), indice_cartorios)
        for parte in ato.get('partes') or []:
            _sugerir_pessoa(parte, indice_pessoas)
    return enriquecido


def _sugerir_cartorio(campo, indice_cartorios):
    """``match_sugerido`` de um fieldCartorio (nó ausente/não-dict: nada)."""
    if not isinstance(campo, dict):
        return
    escolhido, candidatos = indice_cartorios.match(
        _normalized(campo), campo.get('municipio')
    )
    campo['match_sugerido'] = {
        'cartorio_id': escolhido,
        'candidatos': candidatos,
    }


def _sugerir_pessoa(parte, indice_pessoas):
    """``match_pessoa_id`` + ``match_pessoa_candidatos`` de uma party.

    Nome + documento de identificação. Homônimos ficam em
    ``match_pessoa_candidatos`` (ids em ordem de pk) com ``match_pessoa_id``
    nulo: o revisor escolhe.
    """
    if not isinstance(parte, dict):
        return
    documento = parte.get('documento_identificacao')
    if not isinstance(documento, dict):
        documento = {}
    escolhido, candidatos = indice_pessoas.match(
        _normalized(parte.get('nome')),
        _normalized(documento.get('tipo')),
        _normalized(documento.get('valor')),
    )
    parte['match_pessoa_id'] = escolhido
    parte[MATCH_PESSOA_CANDIDATOS] = sorted(candidatos)
