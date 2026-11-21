"""Leitura do parâmetro ``?escolhas`` da URL (escolhas de origem).

Função pura com a MESMA semântica de ``tronco_principal``
(``dominial/views/cadeia_dominial_views.py``), que é a referência e está
congelado no baseline de 400 linhas: mudou lá, muda aqui — e aqui mudou,
confira lá. Formato do valor: JSON ``{"<documento_id>": "<escolha>"}``, em
que a escolha canônica é ``documento:<id>`` (códigos legados como ``T40``
continuam válidos quando não ambíguos).
"""

import json


def escolhas_da_url(valor):
    """Interpreta ``?escolhas`` exatamente como ``tronco_principal`` faz.

    - ``None`` (parâmetro ausente) → ``None``: quem chama usa a sessão;
    - JSON válido ``dict[str, str]`` → o próprio dict;
    - JSON válido de outro tipo → ``{}`` (descarta a sessão);
    - JSON inválido → ``{}`` (descarta a sessão).

    Referência: ``tronco_principal`` em
    ``dominial/views/cadeia_dominial_views.py`` (congelado no baseline de
    400 linhas) — as duas leituras têm que permanecer gêmeas.
    """
    if valor is None:
        return None
    try:
        decodificadas = json.loads(valor)
    except json.JSONDecodeError:
        return {}
    if (
        isinstance(decodificadas, dict)
        and all(
            isinstance(chave, str) and isinstance(origem, str)
            for chave, origem in decodificadas.items()
        )
    ):
        return decodificadas
    return {}
