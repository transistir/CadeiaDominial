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
        elif lancamento.tipo.tipo == 'inicio_matricula':
            LancamentoCamposService._processar_campos_inicio_matricula(request, lancamento)
    
    @staticmethod
    def _processar_campos_averbacao(request, lancamento):
        """
        Processa campos específicos para lançamentos do tipo averbação
        """
        # Processar forma
        forma_value = request.POST.get('forma_averbacao', '').strip()
        lancamento.forma = forma_value if forma_value else None
        
        # Processar cartório de origem se checkbox estiver marcado
        if request.POST.get('incluir_cartorio_averbacao') == 'on':
            cartorio_origem_id = request.POST.get('cartorio_origem_averbacao')
            cartorio_origem_nome = request.POST.get('cartorio_origem_nome_averbacao', '').strip()
            
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
            
            # Processar outros campos de cartório
            lancamento.livro_origem = request.POST.get('livro_origem_averbacao') if request.POST.get('livro_origem_averbacao') and request.POST.get('livro_origem_averbacao').strip() else None
            lancamento.folha_origem = request.POST.get('folha_origem_averbacao') if request.POST.get('folha_origem_averbacao') and request.POST.get('folha_origem_averbacao').strip() else None
            lancamento.data_origem = request.POST.get('data_origem_averbacao') if request.POST.get('data_origem_averbacao') else None
            lancamento.titulo = request.POST.get('titulo_averbacao') if request.POST.get('titulo_averbacao') and request.POST.get('titulo_averbacao').strip() else None
        else:
            # Limpar campos de cartório se o checkbox não estiver marcado
            lancamento.cartorio_origem_id = None
            lancamento.livro_origem = None
            lancamento.folha_origem = None
            lancamento.data_origem = None
    
    @staticmethod
    def _processar_campos_registro(request, lancamento):
        """
        Processa campos específicos para lançamentos do tipo registro
        """
        # Processar forma
        forma_value = request.POST.get('forma_registro', '').strip()
        lancamento.forma = forma_value if forma_value else None
        
        # Processar cartório de origem
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
        
        # Processar outros campos
        lancamento.livro_origem = request.POST.get('livro_origem') if request.POST.get('livro_origem') and request.POST.get('livro_origem').strip() else None
        lancamento.folha_origem = request.POST.get('folha_origem') if request.POST.get('folha_origem') and request.POST.get('folha_origem').strip() else None
        lancamento.data_origem = request.POST.get('data_origem') if request.POST.get('data_origem') else None
        lancamento.titulo = request.POST.get('titulo') if request.POST.get('titulo') and request.POST.get('titulo').strip() else None
        lancamento.descricao = request.POST.get('descricao') if request.POST.get('descricao') and request.POST.get('descricao').strip() else None
    
    @staticmethod
    def _processar_campos_inicio_matricula(request, lancamento):
        """
        Processa campos específicos para lançamentos do tipo início de matrícula
        """
        # Processar forma
        forma_value = request.POST.get('forma_inicio', '').strip()
        lancamento.forma = forma_value if forma_value else None
        
        # Processar descrição
        descricao_value = request.POST.get('descricao_inicio', '').strip()
        lancamento.descricao = descricao_value if descricao_value else None 