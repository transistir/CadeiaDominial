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
def origem_formatada(lancamento):
    """
    Template filter para formatar origem de forma legível
    Para fim de cadeia, mostra apenas o tipo e sigla (se houver)
    """
    if not lancamento.origem:
        return '-'
    
    origem = lancamento.origem.strip()
    
    # Se for fim de cadeia (formato antigo), formatar de forma legível
    if 'FIM_CADEIA' in origem:
        origem_parts = origem.split(':')
        
        if len(origem_parts) >= 4:
            tipo_fim_cadeia = origem_parts[3] if len(origem_parts) > 3 else ''
            sigla_patrimonio = origem_parts[5] if len(origem_parts) > 5 else ''
            
            # Mapear tipos para nomes legíveis
            tipo_nomes = {
                'destacamento_publico': 'Destacamento Público',
                'outra': 'Outra',
                'sem_origem': 'Sem Origem'
            }
            
            tipo_legivel = tipo_nomes.get(tipo_fim_cadeia, tipo_fim_cadeia)
            
            # Se tem sigla do patrimônio público, adicionar
            if sigla_patrimonio and sigla_patrimonio.strip():
                return f"{tipo_legivel} : {sigla_patrimonio.strip()}"
            else:
                return tipo_legivel
    
    # Para origens normais, retornar como está
    return origem

@register.filter
def origem_formatada_completa(lancamento):
    """
    Template filter para formatar origem completa: M123(Cartório); Destacamento Público:INCRA:Origem Lídima
    """
    if not lancamento.origem:
        return '-'
    
    origens_formatadas = []
    origens = [o.strip() for o in lancamento.origem.split(';') if o.strip()]
    
    for origem in origens:
        # Verificar se é fim de cadeia usando padrões
        padroes_fim_cadeia = [
            'Destacamento Público:',
            'Outra:',
            'Sem Origem:',
            'FIM_CADEIA'
        ]
        
        is_fim_cadeia = any(padrao in origem for padrao in padroes_fim_cadeia)
        
        if is_fim_cadeia:
            # Para fim de cadeia, usar formato legível
            origens_formatadas.append(origem)
        else:
            # Para origem normal, adicionar cartório se disponível
            cartorio_nome = lancamento.cartorio_origem.nome if lancamento.cartorio_origem else ''
            if cartorio_nome:
                origem_formatada = f"{origem}({cartorio_nome})"
            else:
                origem_formatada = origem
            origens_formatadas.append(origem_formatada)
    
    return '; '.join(origens_formatadas)

@register.filter
def numero_documento_criado(lancamento):
    """
    Template filter para gerar sigla composta: TipoLançamento + Número + TipoDocumento + NúmeroDocumento
    Formato: R1 M123, AV1 M123, M123 (para início de matrícula)
    """
    # Obter tipo de lançamento
    tipo_lancamento = lancamento.tipo.tipo if lancamento.tipo else ''
    
    # Extrair apenas o número do lançamento (remover prefixos como R, AV, etc.)
    numero_lancamento_completo = lancamento.numero_lancamento or ''
    numero_lancamento = numero_lancamento_completo
    
    # Extrair apenas o número puro do lançamento
    # Se o numero_lancamento tem formato como "R6M6726", extrair apenas "6"
    # Se tem formato como "AV3M6726", extrair apenas "3"
    # Se tem formato como "M6726", extrair apenas "6726"
    # Se tem formato como "14125", usar "14125"
    
    if numero_lancamento_completo.startswith('R'):
        # Formato: R6M6726 -> extrair "6"
        numero_lancamento = numero_lancamento_completo[1:]  # Remove o 'R'
        # Se ainda tem letras, extrair apenas os dígitos no início
        import re
        match = re.match(r'^(\d+)', numero_lancamento)
        if match:
            numero_lancamento = match.group(1)
    elif numero_lancamento_completo.startswith('AV'):
        # Formato: AV3M6726 -> extrair "3"
        numero_lancamento = numero_lancamento_completo[2:]  # Remove o 'AV'
        # Se ainda tem letras, extrair apenas os dígitos no início
        import re
        match = re.match(r'^(\d+)', numero_lancamento)
        if match:
            numero_lancamento = match.group(1)
    elif numero_lancamento_completo.startswith('M'):
        # Formato: M6726 -> extrair "6726"
        numero_lancamento = numero_lancamento_completo[1:]  # Remove o 'M'
    else:
        # Formato: 14125 -> usar "14125"
        numero_lancamento = numero_lancamento_completo
    
    # Obter sigla do tipo de documento e número do documento
    tipo_documento = lancamento.documento.tipo.tipo if lancamento.documento.tipo else ''
    numero_documento = lancamento.documento.numero or ''
    
    # Mapear tipo de documento para sigla
    sigla_documento = ''
    if tipo_documento == 'matricula':
        sigla_documento = 'M'
    elif tipo_documento == 'transcricao':
        sigla_documento = 'T'
    else:
        sigla_documento = tipo_documento.upper()[:1]  # Primeira letra em maiúscula
    
    # Gerar sigla baseada no tipo de lançamento
    if tipo_lancamento == 'registro':
        return f"R{numero_lancamento} {sigla_documento}{numero_documento}"
    elif tipo_lancamento == 'averbacao':
        return f"AV{numero_lancamento} {sigla_documento}{numero_documento}"
    elif tipo_lancamento == 'inicio_matricula':
        return f"{sigla_documento}{numero_documento}"
    else:
        # Fallback para outros tipos
        return f"{tipo_lancamento.upper()}{numero_lancamento} {sigla_documento}{numero_documento}"

 