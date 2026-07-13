"""
Utilitários para cálculos de hierarquia de documentos e cadeia dominial
"""

import re
from ..models import Documento, DocumentoTipo
from .documento_identidade_utils import DocumentoIdentidade


def _obter_origens_lancamento(lancamento):
    # Import tardio evita o ciclo models -> utils -> services -> utils durante
    # a inicialização do Django.
    from ..services.lancamento_origem_leitura_service import (
        LancamentoOrigemLeituraService,
    )

    return LancamentoOrigemLeituraService.obter_origens(lancamento)


def _tipo_do_codigo(codigo):
    """Deduz o tipo documental (matricula/transcricao) do prefixo M/T de um código."""
    if not codigo:
        return None
    primeiro = codigo.strip()[:1].upper()
    if primeiro == 'M':
        return 'matricula'
    if primeiro == 'T':
        return 'transcricao'
    return None


def _resolver_documento_por_codigo(codigo, cartorio):
    """
    Resolve um documento pela identidade completa (tipo, número normalizado e
    cartório), nunca por número isolado. Sem cartório, com tipo incompatível
    ou com identidade ambígua, não seleciona nenhum documento.
    """
    from ..services.documento_identidade_service import DocumentoIdentidadeService

    if not cartorio:
        return None
    tipo = _tipo_do_codigo(codigo)
    if not tipo:
        return None
    try:
        identidade = DocumentoIdentidade(tipo, codigo, cartorio.pk)
    except (TypeError, ValueError):
        return None
    resultado = DocumentoIdentidadeService.resolver(identidade)
    return resultado.documento if resultado.status == 'encontrado' else None


def _selecionar_origem_contextual(origens, codigo_escolhido):
    """Aceita a escolha textual apenas entre origens já resolvidas no contexto."""
    tipo = _tipo_do_codigo(codigo_escolhido)
    if not tipo:
        return None

    compativeis = []
    for documento in origens:
        if documento.tipo.tipo != tipo:
            continue
        try:
            escolha = DocumentoIdentidade(tipo, codigo_escolhido, documento.cartorio_id)
        except (TypeError, ValueError):
            return None
        if documento.numero_normalizado == escolha.numero_normalizado:
            compativeis.append(documento)

    return compativeis[0] if len(compativeis) == 1 else None


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
    # Começar pelo documento que representa a identidade registral do imóvel.
    # A busca inclui tipo, número canônico e cartório, sem depender da forma do
    # prefixo nem da ordem da lista de documentos importados.
    documento_atual = next(
        (
            doc
            for doc in documentos
            if doc.imovel_id == imovel.id
            and doc.tipo.tipo == imovel.tipo_documento_principal
            and doc.numero_normalizado == imovel.matricula_normalizada
            and doc.cartorio_id == imovel.cartorio_id
        ),
        None,
    )
    
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
        lancamentos_com_origem = documento_atual.lancamentos.all()
        
        # Se não há lançamentos com origens, verificar se há uma escolha de origem
        # Extrair códigos de origem dos lançamentos (apenas origens normais, não fim de cadeia)
        origens_identificadas = []
        for lancamento in lancamentos_com_origem:
            for origem in _obter_origens_lancamento(lancamento):
                doc_existente = _resolver_documento_por_codigo(
                    origem.codigo,
                    origem.cartorio,
                )
                if (
                    doc_existente
                    and doc_existente.pk
                    not in {doc.pk for doc in origens_identificadas}
                ):
                    origens_identificadas.append(doc_existente)

        if not origens_identificadas:
            break
        
        # Escolher próximo documento baseado na escolha do usuário ou padrão
        proximo_documento = None
        
        if escolha_atual:
            # O valor legado da sessão ainda é textual. Ele só é aceito quando
            # identifica exatamente uma das origens já resolvidas com o
            # cartório de seu lançamento.
            proximo_documento = _selecionar_origem_contextual(
                origens_identificadas,
                escolha_atual,
            )
        
        if not proximo_documento:
            # Se não há escolha ou escolha não encontrada, usar a origem com maior número
            if origens_identificadas:
                # Ordenar por número (maior primeiro) e pegar a primeira
                origens_ordenadas = sorted(origens_identificadas, 
                    key=lambda x: int(x.numero_normalizado),
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
    lancamentos_com_origem = Lancamento.objects.filter(documento__imovel=imovel)

    # Coletar códigos de origem referenciados, cada um com o cartório do
    # lançamento que o informou (a resolução nunca cruza cartórios)
    codigos_origem = []
    for lancamento in lancamentos_com_origem:
        for origem in _obter_origens_lancamento(lancamento):
            codigos_origem.append((origem.codigo, origem.cartorio))

    documentos_compartilhados = []
    documentos_processados = set()

    def expandir_documentos_recursivamente(codigos_com_cartorio):
        """Função recursiva para expandir documentos compartilhados"""
        for codigo, cartorio in codigos_com_cartorio:
            chave = (codigo, cartorio.pk if cartorio else None)
            if chave in documentos_processados:
                continue
            documentos_processados.add(chave)

            doc_compartilhado = _resolver_documento_por_codigo(codigo, cartorio)

            if doc_compartilhado and doc_compartilhado.imovel_id != imovel.id:
                if doc_compartilhado.id not in {doc.id for doc in documentos_compartilhados}:
                    documentos_compartilhados.append(doc_compartilhado)

                # Buscar origens deste documento compartilhado
                lancamentos_doc = doc_compartilhado.lancamentos.all()

                codigos_origem_doc = []
                for lancamento in lancamentos_doc:
                    for origem in _obter_origens_lancamento(lancamento):
                        codigos_origem_doc.append((origem.codigo, origem.cartorio))

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

    cartorio_origem = lancamento.cartorio_origem if lancamento else None

    # Resolver pela identidade completa (tipo, número normalizado e cartório
    # do lançamento) - nunca por número isolado.
    documento_existente = _resolver_documento_por_codigo(numero_documento, cartorio_origem)
    if documento_existente and documento_existente.imovel_id == imovel_atual.id:
        # É o próprio documento do imóvel atual, não uma origem em outro imóvel
        documento_existente = None

    if documento_existente:
        # Documento existe em outro imóvel - NÃO criar duplicado
        # Em vez disso, deve importar a cadeia dominial
        print(f"AVISO: Documento {numero_documento} já existe no imóvel {documento_existente.imovel.id} (número: {documento_existente.numero}) - não criando duplicado")
        return False

    # REGRA PÉTREA: Se é lançamento de início de matrícula e não existe em outros imóveis
    if lancamento and lancamento.tipo and lancamento.tipo.tipo == 'inicio_matricula':
        # Verificar se não existe no imóvel atual, com a mesma identidade completa
        documento_no_imovel_atual = (
            cartorio_origem
            and Documento.objects.filter(
                tipo__tipo=_tipo_do_codigo(numero_documento),
                numero=numero_documento,
                cartorio=cartorio_origem,
                imovel=imovel_atual,
            ).exists()
        )

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
