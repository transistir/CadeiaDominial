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
        numero_lancamento = request.POST.get('numero_lancamento')
        data = request.POST.get('data')
        observacoes = request.POST.get('observacoes')
        eh_inicio_matricula = request.POST.get('eh_inicio_matricula') == 'on'
        data_clean = data if data and data.strip() else None
        livro_origem_clean = request.POST.get('livro_origem') if request.POST.get('livro_origem') and request.POST.get('livro_origem').strip() else None
        folha_origem_clean = request.POST.get('folha_origem') if request.POST.get('folha_origem') and request.POST.get('folha_origem').strip() else None
        forma_value = request.POST.get('forma', '').strip()
        descricao_clean = observacoes if observacoes and observacoes.strip() else None
        titulo_clean = request.POST.get('titulo') if request.POST.get('titulo') and request.POST.get('titulo').strip() else None
        area = request.POST.get('area')
        origem = request.POST.get('origem_completa') or request.POST.get('origem')
        
        # Processar campo forma baseado no tipo de lançamento
        if tipo_lanc.tipo == 'averbacao':
            forma_value = request.POST.get('forma_averbacao', '').strip()
        elif tipo_lanc.tipo == 'registro':
            forma_value = request.POST.get('forma_registro', '').strip()
        elif tipo_lanc.tipo == 'inicio_matricula':
            forma_value = request.POST.get('forma_inicio', '').strip()
        else:
            forma_value = request.POST.get('forma', '').strip()
        
        return {
            'numero_lancamento': numero_lancamento,
            'data': data_clean,
            'observacoes': observacoes,
            'eh_inicio_matricula': eh_inicio_matricula,
            'forma': forma_value if forma_value else None,
            'descricao': descricao_clean,
            'titulo': titulo_clean,
            'livro_origem': livro_origem_clean,
            'folha_origem': folha_origem_clean,
            'area': area,
            'origem': origem,
        }

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
        forma_value = request.POST.get('forma_registro', '').strip()
        lancamento.forma = forma_value if forma_value else None
        cartorio_origem_id = request.POST.get('cartorio_origem')
        cartorio_origem_nome = request.POST.get('cartorio_origem_nome', '').strip()
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
        else:
            lancamento.cartorio_origem_id = None
        livro_origem_clean = request.POST.get('livro_origem') if request.POST.get('livro_origem') and request.POST.get('livro_origem').strip() else None
        folha_origem_clean = request.POST.get('folha_origem') if request.POST.get('folha_origem') and request.POST.get('folha_origem').strip() else None
        lancamento.livro_origem = livro_origem_clean
        lancamento.folha_origem = folha_origem_clean
        lancamento.data_origem = request.POST.get('data_origem') if request.POST.get('data_origem') else None

    @staticmethod
    def processar_campos_inicio_matricula(request, lancamento):
        forma_value = request.POST.get('forma_inicio', '').strip()
        lancamento.forma = forma_value if forma_value else None
        area_value = request.POST.get('area', '').strip() if request.POST.get('area') else None
        lancamento.area = float(area_value) if area_value else None
        lancamento.origem = request.POST.get('origem_completa', '').strip() if request.POST.get('origem_completa') else None
        lancamento.descricao = request.POST.get('descricao', '').strip() if request.POST.get('descricao') else None
        lancamento.titulo = request.POST.get('titulo', '').strip() if request.POST.get('titulo') else None 