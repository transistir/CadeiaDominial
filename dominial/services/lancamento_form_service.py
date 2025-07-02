"""
Service para processamento de dados do formulário de lançamento
"""
from ..models import LancamentoTipo

class LancamentoFormService:
    @staticmethod
    def processar_dados_lancamento(request, tipo_lanc):
        """
        Processa os dados básicos do formulário de lançamento
        """
        # Processar número do lançamento
        numero_simples = request.POST.get('numero_lancamento_simples', '').strip()
        numero_lancamento = request.POST.get('numero_lancamento', '').strip()
        
        # Se não foi gerado automaticamente, gerar agora
        if numero_simples and not numero_lancamento:
            numero_lancamento = LancamentoFormService._gerar_numero_lancamento(numero_simples, tipo_lanc, request)
        
        data = request.POST.get('data')
        observacoes = request.POST.get('observacoes')
        data_clean = data if data and data.strip() else None
        
        # Campos básicos da matrícula/transcrição
        livro = request.POST.get('livro') if request.POST.get('livro') and request.POST.get('livro').strip() else None
        folha = request.POST.get('folha') if request.POST.get('folha') and request.POST.get('folha').strip() else None
        cartorio_id = request.POST.get('cartorio')
        cartorio_nome = request.POST.get('cartorio_nome', '').strip()
        
        # Processar cartório
        cartorio_origem = None
        if cartorio_id and cartorio_id.strip():
            from ..models import Cartorios
            try:
                cartorio_origem = Cartorios.objects.get(id=cartorio_id)
            except Cartorios.DoesNotExist:
                pass
        elif cartorio_nome:
            from ..models import Cartorios
            try:
                cartorio_origem = Cartorios.objects.get(nome__iexact=cartorio_nome)
            except Cartorios.DoesNotExist:
                import uuid
                cns_unico = f"CNS{str(uuid.uuid4().int)[:10]}"
                cartorio_origem = Cartorios.objects.create(
                    nome=cartorio_nome,
                    cns=cns_unico,
                    cidade=Cartorios.objects.first().cidade if Cartorios.objects.exists() else None
                )
        
        # Campos específicos por tipo (mantidos para compatibilidade)
        forma_value = request.POST.get('forma', '').strip()
        descricao_clean = request.POST.get('descricao') if request.POST.get('descricao') and request.POST.get('descricao').strip() else None
        titulo_clean = request.POST.get('titulo') if request.POST.get('titulo') and request.POST.get('titulo').strip() else None
        area = request.POST.get('area')
        origem = request.POST.get('origem_completa') or request.POST.get('origem')
        
        # Processar campo forma baseado no tipo de lançamento
        if tipo_lanc.tipo == 'averbacao':
            forma_value = request.POST.get('forma_averbacao', '').strip()
            descricao_clean = request.POST.get('descricao') if request.POST.get('descricao') and request.POST.get('descricao').strip() else None
        elif tipo_lanc.tipo == 'registro':
            forma_value = request.POST.get('forma_registro', '').strip()
        elif tipo_lanc.tipo == 'inicio_matricula':
            forma_value = request.POST.get('forma_inicio', '').strip()
            descricao_clean = request.POST.get('descricao') if request.POST.get('descricao') and request.POST.get('descricao').strip() else None
        else:
            forma_value = request.POST.get('forma', '').strip()
        
        return {
            'numero_lancamento': numero_lancamento,
            'data': data_clean,
            'observacoes': observacoes,
            'livro_origem': livro,
            'folha_origem': folha,
            'cartorio_origem': cartorio_origem,
            'forma': forma_value if forma_value else None,
            'descricao': descricao_clean,
            'titulo': titulo_clean,
            'area': area,
            'origem': origem,
        }

    @staticmethod
    def _gerar_numero_lancamento(numero_simples, tipo_lanc, request):
        """
        Gera o número completo do lançamento baseado no tipo e na matrícula
        """
        # Obter a sigla da matrícula/transcrição do imóvel
        # Isso precisa ser obtido do contexto da view
        sigla_matricula = request.POST.get('sigla_matricula', '')
        
        if tipo_lanc.tipo == 'averbacao':
            return f"AV{numero_simples}{sigla_matricula}"
        elif tipo_lanc.tipo == 'registro':
            return f"R{numero_simples}{sigla_matricula}"
        elif tipo_lanc.tipo == 'inicio_matricula':
            return sigla_matricula  # Repete a sigla da matrícula
        else:
            return numero_simples

    @staticmethod
    def processar_campos_averbacao(request, lancamento):
        forma_value = request.POST.get('forma_averbacao', '').strip()
        lancamento.forma = forma_value if forma_value else None
        if request.POST.get('incluir_cartorio_averbacao') == 'on':
            cartorio_origem_id = request.POST.get('cartorio_origem_averbacao')
            cartorio_origem_nome = request.POST.get('cartorio_origem_nome_averbacao', '').strip()
            if cartorio_origem_id and cartorio_origem_id.strip():
                lancamento.cartorio_origem_id = cartorio_origem_id
            elif cartorio_origem_nome:
                from ..models import Cartorios
                try:
                    cartorio = Cartorios.objects.get(nome__iexact=cartorio_origem_nome)
                    lancamento.cartorio_origem = cartorio
                except Cartorios.DoesNotExist:
                    import uuid
                    cns_unico = f"CNS{str(uuid.uuid4().int)[:10]}"
                    cartorio = Cartorios.objects.create(
                        nome=cartorio_origem_nome,
                        cns=cns_unico,
                        cidade=Cartorios.objects.first().cidade if Cartorios.objects.exists() else None
                    )
                    lancamento.cartorio_origem = cartorio
            lancamento.livro_origem = request.POST.get('livro_origem_averbacao') if request.POST.get('livro_origem_averbacao') and request.POST.get('livro_origem_averbacao').strip() else None
            lancamento.folha_origem = request.POST.get('folha_origem_averbacao') if request.POST.get('folha_origem_averbacao') and request.POST.get('folha_origem_averbacao').strip() else None
            lancamento.data_origem = request.POST.get('data_origem_averbacao') if request.POST.get('data_origem_averbacao') else None
            lancamento.titulo = request.POST.get('titulo_averbacao') if request.POST.get('titulo_averbacao') and request.POST.get('titulo_averbacao').strip() else None
        else:
            lancamento.cartorio_origem_id = None
            lancamento.livro_origem = None
            lancamento.folha_origem = None
            lancamento.data_origem = None

    @staticmethod
    def processar_campos_registro(request, lancamento):
        # Campos específicos do registro (transmitentes e adquirentes são processados separadamente)
        # Não há mais campos específicos no bloco de registro, apenas pessoas
        pass

    @staticmethod
    def processar_campos_transacao(request, lancamento):
        """
        Processa os campos do bloco de transação (Transmissão)
        """
        # Campos de transação
        forma_value = request.POST.get('forma_transacao', '').strip()
        lancamento.forma = forma_value if forma_value else None
        
        titulo_value = request.POST.get('titulo_transacao', '').strip()
        lancamento.titulo = titulo_value if titulo_value else None
        
        # Cartório de transação
        cartorio_transacao_id = request.POST.get('cartorio_transacao')
        cartorio_transacao_nome = request.POST.get('cartorio_transacao_nome', '').strip()
        if cartorio_transacao_id and cartorio_transacao_id.strip():
            lancamento.cartorio_origem_id = cartorio_transacao_id
        elif cartorio_transacao_nome:
            from ..models import Cartorios
            try:
                cartorio = Cartorios.objects.get(nome__iexact=cartorio_transacao_nome)
                lancamento.cartorio_origem = cartorio
            except Cartorios.DoesNotExist:
                import uuid
                cns_unico = f"CNS{str(uuid.uuid4().int)[:10]}"
                cartorio = Cartorios.objects.create(
                    nome=cartorio_transacao_nome,
                    cns=cns_unico,
                    cidade=Cartorios.objects.first().cidade if Cartorios.objects.exists() else None
                )
                lancamento.cartorio_origem = cartorio
        else:
            lancamento.cartorio_origem_id = None
        
        # Livro, folha e data de transação
        livro_transacao_clean = request.POST.get('livro_transacao') if request.POST.get('livro_transacao') and request.POST.get('livro_transacao').strip() else None
        folha_transacao_clean = request.POST.get('folha_transacao') if request.POST.get('folha_transacao') and request.POST.get('folha_transacao').strip() else None
        lancamento.livro_origem = livro_transacao_clean
        lancamento.folha_origem = folha_transacao_clean
        lancamento.data_origem = request.POST.get('data_transacao') if request.POST.get('data_transacao') else None

    @staticmethod
    def processar_campos_inicio_matricula(request, lancamento):
        forma_value = request.POST.get('forma_inicio', '').strip()
        lancamento.forma = forma_value if forma_value else None
        area_value = request.POST.get('area', '').strip() if request.POST.get('area') else None
        lancamento.area = float(area_value) if area_value else None
        lancamento.origem = request.POST.get('origem_completa', '').strip() if request.POST.get('origem_completa') else None
        lancamento.descricao = request.POST.get('descricao', '').strip() if request.POST.get('descricao') else None
        lancamento.titulo = request.POST.get('titulo', '').strip() if request.POST.get('titulo') else None 