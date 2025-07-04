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
        if lancamento.tipo.tipo == 'averbacao':
            LancamentoCamposService._processar_campos_averbacao(request, lancamento)
        elif lancamento.tipo.tipo == 'registro':
            LancamentoCamposService._processar_campos_registro(request, lancamento)
            # Para registro, também processar campos de transação
            LancamentoCamposService._processar_campos_transacao(request, lancamento)
        elif lancamento.tipo.tipo == 'inicio_matricula':
            LancamentoCamposService._processar_campos_inicio_matricula(request, lancamento)
            # Não processar campos de transação para início de matrícula
    
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
        
        # Cartório de transação (usar campo específico)
        cartorio_transacao_id = request.POST.get('cartorio_transacao')
        cartorio_transacao_nome = request.POST.get('cartorio_transacao_nome', '').strip()
        
        if cartorio_transacao_id and cartorio_transacao_id.strip():
            lancamento.cartorio_transacao_id = cartorio_transacao_id
        elif cartorio_transacao_nome:
            try:
                cartorio = Cartorios.objects.get(nome__iexact=cartorio_transacao_nome)
                lancamento.cartorio_transacao = cartorio
            except Cartorios.DoesNotExist:
                # Criar novo cartório com CNS único
                cns_unico = f"CNS{str(uuid.uuid4().int)[:10]}"
                cartorio = Cartorios.objects.create(
                    nome=cartorio_transacao_nome,
                    cns=cns_unico,
                    cidade=Cartorios.objects.first().cidade if Cartorios.objects.exists() else None
                )
                lancamento.cartorio_transacao = cartorio
        else:
            lancamento.cartorio_transacao_id = None
        
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
        """
        # Processar origem
        origem_value = request.POST.get('origem_completa', '').strip()
        lancamento.origem = origem_value if origem_value else None
        
        # Processar cartório da origem
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
        else:
            lancamento.cartorio_origem_id = None
        
        # Processar área
        area_value = request.POST.get('area', '').strip()
        lancamento.area = float(area_value) if area_value else None
        
        # Processar data de origem com validação
        data_origem_value = request.POST.get('data_origem', '').strip()
        if data_origem_value:
            # Validar formato da data (YYYY-MM-DD)
            if len(data_origem_value) == 10 and data_origem_value.count('-') == 2:
                try:
                    # Tentar converter para validar o formato
                    from datetime import datetime
                    datetime.strptime(data_origem_value, '%Y-%m-%d')
                    lancamento.data_origem = data_origem_value
                except ValueError:
                    # Se a data for inválida, definir como None
                    lancamento.data_origem = None
            else:
                lancamento.data_origem = None
        else:
            lancamento.data_origem = None 