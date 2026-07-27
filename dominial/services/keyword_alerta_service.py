import re
import unicodedata


PALAVRAS_CHAVE_ALERTA = [
    {'label': 'URGENTE', 'slug': 'urgente', 'priority': 1, 'css_class': 'alerta-urgente'},
    {'label': 'ATENÇÃO', 'slug': 'atencao', 'priority': 2, 'css_class': 'alerta-atencao'},
    {'label': 'PENDENTE', 'slug': 'pendente', 'priority': 3, 'css_class': 'alerta-pendente'},
]


def buscar_keyword(observacoes):
    """
    Retorna a keyword de maior prioridade encontrada nas observações,
    ou None se nenhuma for encontrada.
    - Word boundary matching (\b)
    - Accent-insensitive (ATENCAO matches ATENÇÃO)
    - Case insensitive
    - Retorna o dict da PALAVRAS_CHAVE_ALERTA correspondente
    """
    if not observacoes:
        return None

    # Normalizar acentos: remover diacritics
    def _remover_acentos(s):
        nfkd = unicodedata.normalize('NFKD', s)
        return ''.join(c for c in nfkd if not unicodedata.combining(c))

    obs_normalizada = _remover_acentos(observacoes).lower()
    encontrada = None
    for kw in PALAVRAS_CHAVE_ALERTA:
        kw_normalizada = _remover_acentos(kw['slug']).lower()
        if re.search(r'\b' + re.escape(kw_normalizada) + r'\b', obs_normalizada, re.IGNORECASE):
            if encontrada is None or kw['priority'] < encontrada['priority']:
                encontrada = kw
    return encontrada
