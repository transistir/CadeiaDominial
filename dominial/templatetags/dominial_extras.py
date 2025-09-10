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

@register.filter
def numero_documento_criado(lancamento):
    """
    Template filter para obter o número do documento criado por um lançamento de fim de cadeia
    Se não for fim de cadeia, retorna o numero_lancamento normal
    """
    if not lancamento.origem or 'FIM_CADEIA' not in lancamento.origem:
        return lancamento.numero_lancamento
    
    # Extrair informações da origem para identificar o documento criado
    origem_parts = lancamento.origem.split(':')
    if len(origem_parts) >= 2:
        tipo_origem = origem_parts[1] if origem_parts[1] else ''
        numero_origem = origem_parts[2] if len(origem_parts) > 2 else ''
        
        # Construir o número esperado do documento
        if tipo_origem == 'T':
            numero_esperado = f'T{numero_origem}' if numero_origem else 'T00'
        elif tipo_origem == 'M':
            numero_esperado = f'M{numero_origem}' if numero_origem else 'M00'
        else:
            # Se não há tipo de origem, usar o tipo de fim de cadeia
            if len(origem_parts) == 4:  # Formato sem tipo de origem
                tipo_fim_cadeia = origem_parts[2] if len(origem_parts) > 2 else 'sem_origem'
            else:  # Formato com tipo de origem
                tipo_fim_cadeia = origem_parts[3] if len(origem_parts) > 3 else 'sem_origem'
            
            # Para documentos de fim de cadeia, buscar o documento criado pelo lançamento
            from ..models import Documento
            documento_criado = Documento.objects.filter(
                imovel=lancamento.documento.imovel,
                classificacao_fim_cadeia__isnull=False
            ).first()
            
            if documento_criado:
                # Se for destacamento público e tiver sigla, exibir a sigla
                if (documento_criado.sigla_patrimonio_publico and 
                    documento_criado.sigla_patrimonio_publico.strip()):
                    return documento_criado.sigla_patrimonio_publico
                else:
                    return documento_criado.numero
    
    # Fallback: retornar numero_lancamento se não conseguir determinar
    return lancamento.numero_lancamento

 