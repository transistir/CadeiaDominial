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

 