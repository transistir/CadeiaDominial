"""
Utilitários para cálculos de hierarquia de documentos e cadeia dominial
"""

import re
from ..models import Documento, DocumentoTipo


def ajustar_nivel_para_nova_conexao(documentos, from_numero, to_numero):
    """
    Se ambos os documentos já existem, não altera nenhum nível.
    Apenas mantém os níveis atuais.
    """
    # Não faz nada, apenas retorna os documentos inalterados
    return documentos


def calcular_niveis_hierarquicos_otimizada(documentos, conexoes):
    """
    Calcula os níveis hierárquicos de forma otimizada, respeitando
    os níveis existentes e movendo apenas quando necessário.
    """
    # TODO: Implementar lógica otimizada de cálculo de níveis
    # Esta função será implementada na Fase 2
    pass


def identificar_tronco_principal(imovel, escolhas_origem=None):
    """
    Identifica o tronco principal da cadeia dominial de um imóvel.
    """
    if escolhas_origem is None:
        escolhas_origem = {}
    
    documentos = Documento.objects.filter(imovel=imovel).order_by('data')
    
    # Buscar documentos importados que são referenciados pelos lançamentos deste imóvel
    documentos_importados = identificar_documentos_importados(imovel)
    
    # Adicionar documentos importados à lista
    documentos = list(documentos) + documentos_importados
    
    if not documentos:
        return []

    tronco_principal = []
    # CORREÇÃO: Começar pela matrícula atual (que foi convertida em documento durante o cadastro do imóvel)
    # Primeiro, tentar encontrar o documento que corresponde à matrícula do imóvel
    documento_atual = next((doc for doc in documentos if doc.tipo.tipo == 'matricula' and doc.numero == imovel.matricula), None)
    
    # Se não encontrou o documento da matrícula atual, procurar por matrículas
    if not documento_atual:
        matriculas = [doc for doc in documentos if doc.tipo.tipo == 'matricula']
        if matriculas:
            # Se não há documento específico da matrícula do imóvel, usar a matrícula mais recente
            documento_atual = max(matriculas, key=lambda x: x.data)
        else:
            # Se não há matrículas, procurar por transcrições
            transcricoes = [doc for doc in documentos if doc.tipo.tipo == 'transcricao']
            if transcricoes:
                documento_atual = max(transcricoes, key=lambda x: x.data)
            else:
                return []

    while documento_atual:
        tronco_principal.append(documento_atual)
        
        # Verificar se há escolha de origem para este documento
        escolha_atual = escolhas_origem.get(str(documento_atual.id))
        
        # Buscar lançamentos do documento atual que têm origens
        lancamentos_com_origem = documento_atual.lancamentos.filter(origem__isnull=False).exclude(origem='')
        
        # Se não há lançamentos com origens, verificar se há uma escolha de origem
        if not lancamentos_com_origem.exists():
            if escolha_atual:
                # Se há escolha mas não há lançamentos com origens, buscar o documento escolhido
                proximo_documento = next((doc for doc in documentos if doc.numero == escolha_atual), None)
                if proximo_documento and proximo_documento not in tronco_principal:
                    documento_atual = proximo_documento
                    continue
            break
        
        # Extrair códigos de origem dos lançamentos (apenas origens normais, não fim de cadeia)
        origens_identificadas = []
        for lancamento in lancamentos_com_origem:
            if lancamento.origem:
                # Separar origens normais de fim de cadeia
                origens_individuals = [o.strip() for o in lancamento.origem.split(';') if o.strip()]
                origens_normais = []
                
                for origem_individual in origens_individuals:
                    # Verificar se é fim de cadeia
                    padroes_fim_cadeia = [
                        'Destacamento Público:',
                        'Outra:',
                        'Sem Origem:',
                        'FIM_CADEIA'
                    ]
                    
                    is_fim_cadeia = any(padrao in origem_individual for padrao in padroes_fim_cadeia)
                    
                    if not is_fim_cadeia:
                        origens_normais.append(origem_individual)
                
                # Processar apenas origens normais
                for origem_normal in origens_normais:
                    codigos = re.findall(r'[MT]\d+', origem_normal)
                    for codigo in codigos:
                        doc_existente = next((doc for doc in documentos if doc.numero == codigo), None)
                        if doc_existente:
                            origens_identificadas.append(doc_existente)
        
        # Escolher próximo documento baseado na escolha do usuário ou padrão
        proximo_documento = None
        
        if escolha_atual:
            # Se há escolha específica, usar ela
            proximo_documento = next((doc for doc in origens_identificadas if doc.numero == escolha_atual), None)
        
        if not proximo_documento:
            # Se não há escolha ou escolha não encontrada, usar a origem com maior número
            if origens_identificadas:
                # Ordenar por número (maior primeiro) e pegar a primeira
                origens_ordenadas = sorted(origens_identificadas, 
                    key=lambda x: int(str(x.numero).replace('M', '').replace('T', '')), 
                    reverse=True)
                proximo_documento = origens_ordenadas[0]
        
        if not proximo_documento or proximo_documento in tronco_principal:
            break
        documento_atual = proximo_documento
    return tronco_principal


def identificar_troncos_secundarios(imovel, tronco_principal):
    """
    Identifica os troncos secundários da cadeia dominial de um imóvel.
    """
    # TODO: Implementar lógica de identificação dos troncos secundários
    # Esta função será implementada na Fase 2
    pass


def identificar_documentos_importados(imovel):
    """
    Identifica documentos importados que são referenciados pelos lançamentos deste imóvel
    
    Args:
        imovel: Objeto Imovel
        
    Returns:
        list: Lista de documentos importados
    """
    from ..models import DocumentoImportado
    
    # Buscar apenas documentos que foram realmente importados para este imóvel
    documentos_importados = DocumentoImportado.objects.filter(
        documento__imovel=imovel
    ).select_related('documento', 'documento__cartorio', 'documento__tipo', 'imovel_origem')
    
    return [doc_importado.documento for doc_importado in documentos_importados]


def processar_origens_para_documentos(origem_texto, imovel, lancamento):
    """
    Processa o texto de origem de um lançamento e extrai informações de documentos
    que podem ser criados automaticamente.
    
    Args:
        origem_texto (str): Texto contendo as origens (ex: "M123; T456")
        imovel: Objeto Imovel
        lancamento: Objeto Lancamento
    
    Returns:
        list: Lista de dicionários com informações dos documentos identificados
    """
    if not origem_texto:
        return []
    
    origens_processadas = []
    
    # Dividir por ponto e vírgula se houver múltiplas origens
    origens = [o.strip() for o in origem_texto.split(';') if o.strip()]
    
    # Separar origens normais de fim de cadeia
    origens_normais = []
    for origem in origens:
        # Verificar se é fim de cadeia
        padroes_fim_cadeia = [
            'Destacamento Público:',
            'Outra:',
            'Sem Origem:',
            'FIM_CADEIA'
        ]
        
        is_fim_cadeia = any(padrao in origem for padrao in padroes_fim_cadeia)
        
        if not is_fim_cadeia:
            origens_normais.append(origem)
    
    # Processar apenas origens normais
    for origem in origens_normais:
        # Padrão para matrículas (M seguido de números)
        if re.match(r'^M\d+$', origem):
            origens_processadas.append({
                'numero': origem,
                'tipo': 'matricula',
                'descricao': f'Matrícula {origem} identificada na origem do lançamento'
            })
        
        # Padrão para transcrições (T seguido de números)
        elif re.match(r'^T\d+$', origem):
            origens_processadas.append({
                'numero': origem,
                'tipo': 'transcricao',
                'descricao': f'Transcrição {origem} identificada na origem do lançamento'
            })
        
        # Padrão para números simples (assumir como matrícula)
        elif re.match(r'^\d+$', origem):
            origens_processadas.append({
                'numero': f'M{origem}',  # Adicionar prefixo M
                'tipo': 'matricula',
                'descricao': f'Matrícula M{origem} identificada na origem do lançamento'
            })
        
        # Padrão para texto que contém números
        elif re.search(r'\d+', origem):
            # Extrair números do texto
            numeros = re.findall(r'\d+', origem)
            for numero in numeros:
                # Determinar tipo baseado no contexto
                tipo = 'matricula'  # Padrão
                if 'transcrição' in origem.lower() or 'transcricao' in origem.lower():
                    tipo = 'transcricao'
                
                prefixo = 'T' if tipo == 'transcricao' else 'M'
                numero_completo = f'{prefixo}{numero}'
                
                origens_processadas.append({
                    'numero': numero_completo,
                    'tipo': tipo,
                    'descricao': f'{tipo.title()} {numero_completo} extraída do texto: "{origem}"'
                })
    
    return origens_processadas 