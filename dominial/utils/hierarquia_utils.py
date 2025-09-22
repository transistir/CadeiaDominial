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
    
    # Se não encontrou, verificar se a matrícula do imóvel tem prefixo "M" e o documento não
    if not documento_atual and imovel.matricula.startswith('M'):
        documento_atual = next((doc for doc in documentos if doc.tipo.tipo == 'matricula' and doc.numero == imovel.matricula[1:]), None)
    
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
    Identifica documentos compartilhados que são referenciados pelos lançamentos deste imóvel
    e também os documentos que são referenciados pelos documentos compartilhados (expansão recursiva)
    
    Args:
        imovel: Objeto Imovel
        
    Returns:
        list: Lista de documentos compartilhados (que pertencem a outros imóveis)
    """
    from ..models import Documento, Lancamento
    import re
    
    # Buscar todos os lançamentos do imóvel que têm origens
    lancamentos_com_origem = Lancamento.objects.filter(
        documento__imovel=imovel,
        origem__isnull=False
    ).exclude(origem='')
    
    # Coletar todos os códigos de origem referenciados
    codigos_origem = set()
    for lancamento in lancamentos_com_origem:
        if lancamento.origem:
            # Extrair códigos M/T dos lançamentos
            codigos = re.findall(r'[MT]\d+', lancamento.origem)
            codigos_origem.update(codigos)
    
    # Buscar documentos que correspondem aos códigos e pertencem a outros imóveis
    documentos_compartilhados = []
    documentos_processados = set()
    
    def expandir_documentos_recursivamente(codigos):
        """Função recursiva para expandir documentos compartilhados"""
        for codigo in codigos:
            if codigo in documentos_processados:
                continue
                
            doc_compartilhado = Documento.objects.filter(
                numero=codigo
            ).exclude(
                imovel=imovel  # Excluir documentos do imóvel atual
            ).select_related('cartorio', 'tipo', 'imovel').first()
            
            if doc_compartilhado:
                documentos_compartilhados.append(doc_compartilhado)
                documentos_processados.add(codigo)
                
                # Buscar origens deste documento compartilhado
                lancamentos_doc = doc_compartilhado.lancamentos.filter(
                    origem__isnull=False
                ).exclude(origem='')
                
                codigos_origem_doc = set()
                for lancamento in lancamentos_doc:
                    if lancamento.origem:
                        codigos_orig = re.findall(r'[MT]\d+', lancamento.origem)
                        codigos_origem_doc.update(codigos_orig)
                
                # Expandir recursivamente
                if codigos_origem_doc:
                    expandir_documentos_recursivamente(codigos_origem_doc)
    
    # Expandir recursivamente todos os documentos compartilhados
    expandir_documentos_recursivamente(codigos_origem)
    
    return documentos_compartilhados


def processar_origens_para_documentos(origem_texto, imovel, lancamento):
    """
    Processa o texto de origem de um lançamento e extrai informações de documentos
    que podem ser criados automaticamente.
    
    CORREÇÃO: Implementa validação rigorosa para evitar criação de documentos órfãos
    
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
    
    # Processar apenas origens normais com VALIDAÇÃO RIGOROSA
    for origem in origens_normais:
        # VALIDAÇÃO 1: Apenas origens com formato M/T seguido de números
        if re.match(r'^[MT]\d+$', origem):
            # VALIDAÇÃO 2: Verificar se o documento já existe em outro imóvel
            if _validar_origem_existente(origem, imovel, lancamento):
                tipo = 'matricula' if origem.startswith('M') else 'transcricao'
                origens_processadas.append({
                    'numero': origem,
                    'tipo': tipo,
                    'descricao': f'{tipo.title()} {origem} identificada na origem do lançamento'
                })
            else:
                print(f"AVISO: Origem {origem} não existe em outros imóveis - não criando documento automático")
        
        # VALIDAÇÃO 3: Números simples - assumir como matrícula (padrão)
        elif re.match(r'^\d+$', origem):
            # Para números simples, assumir como matrícula (padrão do sistema)
            if _validar_origem_existente(f'M{origem}', imovel, lancamento):
                origens_processadas.append({
                    'numero': f'M{origem}',
                    'tipo': 'matricula',
                    'descricao': f'Matrícula M{origem} identificada na origem do lançamento'
                })
            else:
                print(f"AVISO: Número {origem} não pode ser criado como M{origem} - não criando documento automático")
        
        # VALIDAÇÃO 4: Texto com números - apenas se contexto for muito claro
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
                
                # VALIDAÇÃO 5: Verificar se existe em outros imóveis
                if _validar_origem_existente(numero_completo, imovel, lancamento):
                    origens_processadas.append({
                        'numero': numero_completo,
                        'tipo': tipo,
                        'descricao': f'{tipo.title()} {numero_completo} extraída do texto: "{origem}"'
                    })
                else:
                    print(f"AVISO: {tipo.title()} {numero_completo} não existe em outros imóveis - não criando documento automático")
    
    return origens_processadas


def _validar_origem_existente(numero_documento, imovel_atual, lancamento=None):
    """
    Valida se uma origem deve ser criada automaticamente.
    
    Regras de validação:
    1. REGRA PÉTREA: Se é lançamento de início de matrícula, sempre permitir
    2. Se não é início de matrícula: documento deve existir em outro imóvel
    3. O documento não deve existir no imóvel atual
    4. O documento deve ter pelo menos um lançamento real (se existir)
    
    Args:
        numero_documento (str): Número do documento (ex: "M123")
        imovel_atual: Objeto Imovel atual
        lancamento: Objeto Lancamento (opcional, para verificar tipo)
    
    Returns:
        bool: True se a origem deve ser criada, False caso contrário
    """
    from ..models import Documento, Lancamento
    
    # CORREÇÃO: Sempre verificar se documento existe em outros imóveis primeiro
    # Buscar documento em outros imóveis (com e sem prefixo)
    documento_existente = Documento.objects.filter(
        numero=numero_documento
    ).exclude(
        imovel=imovel_atual
    ).first()
    
    # Se não encontrou com prefixo, tentar sem prefixo
    if not documento_existente and numero_documento.startswith(('M', 'T')):
        numero_base = numero_documento[1:]  # Remove M ou T
        documento_existente = Documento.objects.filter(
            numero=numero_base
        ).exclude(
            imovel=imovel_atual
        ).first()
    
    if documento_existente:
        # Documento existe em outro imóvel - NÃO criar duplicado
        # Em vez disso, deve importar a cadeia dominial
        print(f"AVISO: Documento {numero_documento} já existe no imóvel {documento_existente.imovel.id} (número: {documento_existente.numero}) - não criando duplicado")
        return False
    
    # REGRA PÉTREA: Se é lançamento de início de matrícula e não existe em outros imóveis
    if lancamento and lancamento.tipo and lancamento.tipo.tipo == 'inicio_matricula':
        # Verificar se não existe no imóvel atual
        documento_no_imovel_atual = Documento.objects.filter(
            numero=numero_documento,
            imovel=imovel_atual
        ).exists()
        
        if documento_no_imovel_atual:
            return False
        
        # Para início de matrícula, permitir criação apenas se não existe em lugar nenhum
        return True
    
    # Para outros tipos de lançamento, usar validação restritiva
    # (já verificamos se existe em outros imóveis acima)
    if not documento_existente:
        return False
    
    # Verificar se o documento tem lançamentos reais
    lancamentos_count = Lancamento.objects.filter(
        documento=documento_existente
    ).count()
    
    if lancamentos_count == 0:
        return False
    
    # Verificar se não existe no imóvel atual
    documento_no_imovel_atual = Documento.objects.filter(
        numero=numero_documento,
        imovel=imovel_atual
    ).exists()
    
    if documento_no_imovel_atual:
        return False
    
    return True 