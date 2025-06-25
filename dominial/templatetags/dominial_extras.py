from django import template

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