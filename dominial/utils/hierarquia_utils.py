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
    if not documentos.exists():
        return []

    tronco_principal = []
    # Começar pelo documento mais antigo (primeira matrícula ou transcrição)
    documento_atual = documentos.filter(tipo__tipo='matricula').order_by('data').first()
    if not documento_atual:
        documento_atual = documentos.filter(tipo__tipo='transcricao').order_by('data').first()
    if not documento_atual:
        return []

    while documento_atual:
        tronco_principal.append(documento_atual)
        # Buscar lançamentos do documento atual que têm origens
        lancamentos_com_origem = documento_atual.lancamentos.filter(origem__isnull=False).exclude(origem='')
        if not lancamentos_com_origem.exists():
            break
        
        # Verificar se há escolha de origem para este documento
        escolha_atual = escolhas_origem.get(str(documento_atual.id))
        
        # Extrair códigos de origem dos lançamentos
        origens_identificadas = []
        for lancamento in lancamentos_com_origem:
            if lancamento.origem:
                codigos = re.findall(r'[MT]\d+', lancamento.origem)
                for codigo in codigos:
                    doc_existente = Documento.objects.filter(imovel=imovel, numero=codigo).first()
                    if doc_existente:
                        origens_identificadas.append(doc_existente)
        
        # Escolher próximo documento baseado na escolha do usuário ou padrão
        proximo_documento = None
        
        if escolha_atual:
            # Se há escolha específica, usar ela
            proximo_documento = next((doc for doc in origens_identificadas if doc.numero == escolha_atual), None)
        
        if not proximo_documento:
            # Se não há escolha ou escolha não encontrada, usar padrão (maior número)
            matriculas = [doc for doc in origens_identificadas if doc.tipo.tipo == 'matricula']
            if matriculas:
                proximo_documento = max(matriculas, key=lambda x: int(x.numero.replace('M', '')))
            else:
                transcricoes = [doc for doc in origens_identificadas if doc.tipo.tipo == 'transcricao']
                if transcricoes:
                    proximo_documento = max(transcricoes, key=lambda x: int(x.numero.replace('T', '')))
        
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
    
    for origem in origens:
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