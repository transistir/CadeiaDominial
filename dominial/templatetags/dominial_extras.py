from django import template
import re

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Template filter para acessar valores de dicionário por chave"""
    return dictionary.get(key, 0)

@register.filter
def format_status(status):
    """Template filter para formatar status das fases das TIs"""
    if not status:
        return ''
    
    # Converter para lowercase e remover espaços para usar como classe CSS
    return status.lower().replace(' ', '-').replace('ã', 'a').replace('ç', 'c')

@register.filter
def split(value, arg):
    """Template filter para dividir uma string por um separador"""
    if not value:
        return []
    return [item.strip() for item in value.split(arg) if item.strip()]

@register.filter
def strip(value):
    """Template filter para remover espaços em branco"""
    if not value:
        return ''
    return value.strip()

@register.filter
def origem_cartorio(lancamento):
    """
    Template filter para formatar origem com cartório
    """
    if not lancamento.origem:
        return '-'
    
    origem = lancamento.origem.strip()
    
    # Se tem cartório de origem definido, adicionar ao lado
    if lancamento.cartorio_origem:
        return f"{origem} ({lancamento.cartorio_origem.nome})"
    
    return origem

@register.filter
def origem_cartorio_especifico(lancamento, origem_texto):
    """
    Template filter para obter o cartório específico de uma origem
    quando há múltiplas origens com cartórios diferentes
    """
    if not lancamento.origem or not origem_texto:
        return ''
    
    # Tentar recuperar mapeamento do cache
    from django.core.cache import cache
    cache_key = f"mapeamento_origens_lancamento_{lancamento.id}"
    mapeamento_origens = cache.get(cache_key)
    
    if mapeamento_origens:
        # Buscar cartório específico para esta origem
        for mapeamento in mapeamento_origens:
            if mapeamento.get('origem', '').strip() == origem_texto.strip():
                return mapeamento.get('cartorio_nome', '')
    
    # Fallback: usar cartório geral do lançamento
    if lancamento.cartorio_origem:
        return lancamento.cartorio_origem.nome
    
    return ''

 