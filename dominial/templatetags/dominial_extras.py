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

 