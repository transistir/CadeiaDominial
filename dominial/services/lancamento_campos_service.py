"""
Service especializado para processamento de campos específicos por tipo de lançamento
"""

from ..models import Cartorios
import uuid


class LancamentoCamposService:
    """
    Service para processar campos específicos por tipo de lançamento
    """
    
    @staticmethod
    def processar_campos_por_tipo(request, lancamento):
        """
        Processa campos específicos baseado no tipo de lançamento
        """
        # Verificar se o documento é uma transcrição
        is_transcricao = lancamento.documento.tipo.tipo == 'transcricao'
        
        if lancamento.tipo.tipo == 'averbacao':
            LancamentoCamposService._processar_campos_averbacao(request, lancamento)
            # Para transcrições, sempre processar campos de transação
            if is_transcricao:
                LancamentoCamposService._processar_campos_transacao(request, lancamento)
        elif lancamento.tipo.tipo == 'registro':
            LancamentoCamposService._processar_campos_registro(request, lancamento)
            # Para registro, também processar campos de transação
            LancamentoCamposService._processar_campos_transacao(request, lancamento)
        elif lancamento.tipo.tipo == 'inicio_matricula':
            LancamentoCamposService._processar_campos_inicio_matricula(request, lancamento)
            # Para transcrições, sempre processar campos de transação
            if is_transcricao:
                LancamentoCamposService._processar_campos_transacao(request, lancamento)
    
    @staticmethod
    def _processar_campos_averbacao(request, lancamento):
        """
        Processa campos específicos para lançamentos do tipo averbação
        """
        # Processar forma
        forma_value = request.POST.get('forma_averbacao', '').strip()
        lancamento.forma = forma_value if forma_value else None
        
        # Processar descrição
        descricao_value = request.POST.get('descricao', '').strip()
        lancamento.descricao = descricao_value if descricao_value else None
        
        # Processar área
        area_value = request.POST.get('area', '').strip()
        lancamento.area = float(area_value) if area_value else None
        
        # Processar origem (se presente)
        origem_value = request.POST.get('origem_completa', '').strip()
        if origem_value:
            lancamento.origem = origem_value
        
        # Processar cartório da origem (se presente)
        cartorio_origem_id = request.POST.get('cartorio_origem')
        cartorio_origem_nome = request.POST.get('cartorio_origem_nome', '').strip()
        
        if cartorio_origem_id and cartorio_origem_id.strip():
            lancamento.cartorio_origem_id = cartorio_origem_id
        elif cartorio_origem_nome:
            try:
                cartorio = Cartorios.objects.get(nome__iexact=cartorio_origem_nome)
                lancamento.cartorio_origem = cartorio
            except Cartorios.DoesNotExist:
                # Criar novo cartório com CNS único
                cns_unico = f"CNS{str(uuid.uuid4().int)[:10]}"
                cartorio = Cartorios.objects.create(
                    nome=cartorio_origem_nome,
                    cns=cns_unico,
                    cidade=Cartorios.objects.first().cidade if Cartorios.objects.exists() else None
                )
                lancamento.cartorio_origem = cartorio
    
    @staticmethod
    def _processar_campos_registro(request, lancamento):
        """
        Processa campos específicos para lançamentos do tipo registro
        """
        # Campos específicos do registro (transmitentes e adquirentes são processados separadamente)
        # Não há mais campos específicos no bloco de registro, apenas pessoas
        
        # Processar área
        area_value = request.POST.get('area', '').strip()
        lancamento.area = float(area_value) if area_value else None
        
        # Processar origem (se presente)
        origem_value = request.POST.get('origem_completa', '').strip()
        if origem_value:
            lancamento.origem = origem_value
        
        # Processar cartório da origem (se presente)
        cartorio_origem_id = request.POST.get('cartorio_origem')
        cartorio_origem_nome = request.POST.get('cartorio_origem_nome', '').strip()
        
        if cartorio_origem_id and cartorio_origem_id.strip():
            lancamento.cartorio_origem_id = cartorio_origem_id
        elif cartorio_origem_nome:
            try:
                cartorio = Cartorios.objects.get(nome__iexact=cartorio_origem_nome)
                lancamento.cartorio_origem = cartorio
            except Cartorios.DoesNotExist:
                # Criar novo cartório com CNS único
                cns_unico = f"CNS{str(uuid.uuid4().int)[:10]}"
                cartorio = Cartorios.objects.create(
                    nome=cartorio_origem_nome,
                    cns=cns_unico,
                    cidade=Cartorios.objects.first().cidade if Cartorios.objects.exists() else None
                )
                lancamento.cartorio_origem = cartorio

    @staticmethod
    def _processar_campos_transacao(request, lancamento):
        """
        Processa campos do bloco de transação (Transmissão)
        """
        # Campos de transação
        forma_value = request.POST.get('forma_transacao', '').strip()
        lancamento.forma = forma_value if forma_value else None
        
        titulo_value = request.POST.get('titulo_transacao', '').strip()
        lancamento.titulo = titulo_value if titulo_value else None
        
        # Cartório de transmissão (usar campo específico)
        cartorio_transmissao_id = request.POST.get('cartorio_transmissao')
        cartorio_transmissao_nome = request.POST.get('cartorio_transmissao_nome', '').strip()
        
        if cartorio_transmissao_id and cartorio_transmissao_id.strip():
            lancamento.cartorio_transmissao_id = cartorio_transmissao_id
        elif cartorio_transmissao_nome:
            try:
                cartorio = Cartorios.objects.get(nome__iexact=cartorio_transmissao_nome)
                lancamento.cartorio_transmissao = cartorio
            except Cartorios.DoesNotExist:
                # Criar novo cartório com CNS único
                cns_unico = f"CNS{str(uuid.uuid4().int)[:10]}"
                cartorio = Cartorios.objects.create(
                    nome=cartorio_transmissao_nome,
                    cns=cns_unico,
                    cidade=Cartorios.objects.first().cidade if Cartorios.objects.exists() else None
                )
                lancamento.cartorio_transmissao = cartorio
        else:
            lancamento.cartorio_transmissao_id = None
        
        # Livro, folha e data de transação
        lancamento.livro_transacao = request.POST.get('livro_transacao') if request.POST.get('livro_transacao') and request.POST.get('livro_transacao').strip() else None
        lancamento.folha_transacao = request.POST.get('folha_transacao') if request.POST.get('folha_transacao') and request.POST.get('folha_transacao').strip() else None
        
        # Processar data de transação com validação
        data_transacao_value = request.POST.get('data_transacao', '').strip()
        if data_transacao_value:
            # Validar formato da data (YYYY-MM-DD)
            if len(data_transacao_value) == 10 and data_transacao_value.count('-') == 2:
                try:
                    # Tentar converter para validar o formato
                    from datetime import datetime
                    datetime.strptime(data_transacao_value, '%Y-%m-%d')
                    lancamento.data_transacao = data_transacao_value
                except ValueError:
                    # Se a data for inválida, definir como None
                    lancamento.data_transacao = None
            else:
                lancamento.data_transacao = None
        else:
            lancamento.data_transacao = None
    
    @staticmethod
    def _processar_campos_inicio_matricula(request, lancamento):
        """
        Processa campos específicos para lançamentos do tipo início de matrícula
        HERANÇA: Livro e folha são herdados do primeiro lançamento do documento criado pela origem
        """
        # Processar múltiplas origens
        origens_completas = request.POST.getlist('origem_completa[]')
        cartorios_origem_ids = request.POST.getlist('cartorio_origem[]')
        cartorios_origem_nomes = request.POST.getlist('cartorio_origem_nome[]')
        livros_origem = request.POST.getlist('livro_origem[]')
        folhas_origem = request.POST.getlist('folha_origem[]')
        
        # Se há múltiplas origens, concatenar com ponto e vírgula
        if origens_completas:
            # Filtrar origens vazias
            origens_validas = [origem.strip() for origem in origens_completas if origem.strip()]
            if origens_validas:
                lancamento.origem = '; '.join(origens_validas)
        
        # PROCESSAR CARTÓRIO DE ORIGEM para múltiplas origens
        # CORREÇÃO: Associar cada origem com seu respectivo cartório
        # Para início de matrícula, o cartório de origem é usado para criar documentos automáticos
        cartorio_origem_encontrado = None
        
        # Criar mapeamento de origens com seus respectivos cartórios
        origens_com_cartorios = []
        
        for i, origem in enumerate(origens_completas):
            if origem and origem.strip():
                cartorio_origem = None
        
                # Tentar encontrar cartório por ID primeiro
                if i < len(cartorios_origem_ids) and cartorios_origem_ids[i] and cartorios_origem_ids[i].strip():
                    try:
                        cartorio_origem = Cartorios.objects.get(id=cartorios_origem_ids[i])
                    except Cartorios.DoesNotExist:
                        pass
        
                # Se não encontrou por ID, tentar por nome
                if not cartorio_origem and i < len(cartorios_origem_nomes) and cartorios_origem_nomes[i] and cartorios_origem_nomes[i].strip():
                    try:
                        cartorio_origem = Cartorios.objects.get(nome__iexact=cartorios_origem_nomes[i])
                    except Cartorios.DoesNotExist:
                        # Criar novo cartório se não existir
                        cns_unico = f"CNS{str(uuid.uuid4().int)[:10]}"
                        cartorio_origem = Cartorios.objects.create(
                            nome=cartorios_origem_nomes[i],
                            cns=cns_unico,
                            cidade=Cartorios.objects.first().cidade if Cartorios.objects.exists() else None
                        )
                
                # Adicionar origem com seu cartório ao mapeamento
                if cartorio_origem:
                    origens_com_cartorios.append({
                        'origem': origem.strip(),
                        'cartorio': cartorio_origem,
                        'livro': livros_origem[i] if i < len(livros_origem) else None,
                        'folha': folhas_origem[i] if i < len(folhas_origem) else None
                    })
                    
                    # Usar o primeiro cartório válido encontrado como cartório de origem do lançamento
                    if not cartorio_origem_encontrado:
                        cartorio_origem_encontrado = cartorio_origem
        
        # Salvar o mapeamento de origens com cartórios no lançamento
        # CORREÇÃO: Não usar campo observações para evitar interferir com dados do usuário
        if origens_com_cartorios:
            lancamento.origem = '; '.join([item['origem'] for item in origens_com_cartorios])
            
            # Armazenar mapeamento em uma variável de sessão ou cache temporário
            # Por enquanto, usar apenas o primeiro cartório como cartório de origem do lançamento
            # TODO: Implementar sistema de mapeamento mais robusto (ex: campo JSON no modelo)
            lancamento.cartorio_origem = cartorio_origem_encontrado
            
            # Armazenar mapeamento em cache temporário para uso posterior
            from django.core.cache import cache
            cache_key = f"mapeamento_origens_lancamento_{lancamento.id if lancamento.id else 'novo'}"
            mapeamento_origens = []
            for item in origens_com_cartorios:
                mapeamento_origens.append({
                    'origem': item['origem'],
                    'cartorio_id': item['cartorio'].id,
                    'cartorio_nome': item['cartorio'].nome,
                    'livro': item['livro'],
                    'folha': item['folha']
                })
            cache.set(cache_key, mapeamento_origens, timeout=3600)  # 1 hora
        
        # PROCESSAR LIVRO E FOLHA DE ORIGEM para múltiplas origens
        # HERANÇA: Buscar livro e folha do primeiro lançamento do documento criado pela origem
        livro_origem_encontrado = None
        folha_origem_encontrada = None
        
        # Primeiro, tentar herdar do primeiro lançamento do documento da origem
        if cartorio_origem_encontrado and origens_validas:
            # Buscar documento da origem (primeira origem válida)
            primeira_origem = origens_validas[0]
            # Extrair número da origem (assumindo que é o primeiro número encontrado)
            import re
            numero_match = re.search(r'\d+', primeira_origem)
            if numero_match:
                numero_origem = numero_match.group()
                
                # Buscar documento da origem
                from ..models import Documento
                documento_origem = Documento.objects.filter(
                    numero=numero_origem,
                    cartorio=cartorio_origem_encontrado
                ).first()
                
                if documento_origem:
                    # Buscar primeiro lançamento deste documento
                    from ..models import Lancamento
                    primeiro_lancamento_origem = Lancamento.objects.filter(
                        documento=documento_origem
                    ).order_by('id').first()
                    
                    if primeiro_lancamento_origem:
                        # Herdar livro e folha do primeiro lançamento da origem
                        if primeiro_lancamento_origem.livro_origem and primeiro_lancamento_origem.livro_origem.strip():
                            livro_origem_encontrado = primeiro_lancamento_origem.livro_origem.strip()
                        if primeiro_lancamento_origem.folha_origem and primeiro_lancamento_origem.folha_origem.strip():
                            folha_origem_encontrada = primeiro_lancamento_origem.folha_origem.strip()
        
        # Se não encontrou por herança, usar os campos do formulário
        if not livro_origem_encontrado:
            for livro in livros_origem:
                if livro and livro.strip():
                    livro_origem_encontrado = livro.strip()
                    break
        
        if not folha_origem_encontrada:
            for folha in folhas_origem:
                if folha and folha.strip():
                    folha_origem_encontrada = folha.strip()
                    break
        
        # Salvar livro e folha de origem encontrados no lançamento
        if livro_origem_encontrado:
            lancamento.livro_origem = livro_origem_encontrado
        
        if folha_origem_encontrada:
            lancamento.folha_origem = folha_origem_encontrada
        
        # Para início de matrícula, NÃO sobrescrever o cartório da matrícula
        # O cartório da matrícula já foi definido nos campos básicos
        # O cartório da origem é apenas informativo e não deve substituir o cartório da matrícula
        
        # Processar área
        area_value = request.POST.get('area', '').strip()
        lancamento.area = float(area_value) if area_value else None
        
        # Processar data de origem
        data_origem_value = request.POST.get('data_origem', '').strip()
        if data_origem_value:
            try:
                from datetime import datetime
                lancamento.data_origem = datetime.strptime(data_origem_value, '%Y-%m-%d').date()
            except ValueError:
                lancamento.data_origem = None
        else:
            lancamento.data_origem = None 