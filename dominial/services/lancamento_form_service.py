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
        if not numero_lancamento:
            if numero_simples:
                numero_lancamento = LancamentoFormService._gerar_numero_lancamento(numero_simples, tipo_lanc, request)
            else:
                # Se não há número simples nem número completo, deixar vazio para validação
                numero_lancamento = ''
        
        data = request.POST.get('data')
        observacoes = request.POST.get('observacoes')
        
        # Processar data com validação
        data_clean = None
        if data and data.strip():
            data_value = data.strip()
            # Validar formato da data (YYYY-MM-DD)
            if len(data_value) == 10 and data_value.count('-') == 2:
                try:
                    # Tentar converter para validar o formato
                    from datetime import datetime
                    datetime.strptime(data_value, '%Y-%m-%d')
                    data_clean = data_value
                except ValueError:
                    # Se a data for inválida, definir como None
                    data_clean = None
            else:
                data_clean = None
        
        # Campos do documento (livro e folha do documento atual)
        livro_documento = request.POST.get('livro_documento') if request.POST.get('livro_documento') and request.POST.get('livro_documento').strip() else None
        folha_documento = request.POST.get('folha_documento') if request.POST.get('folha_documento') and request.POST.get('folha_documento').strip() else None
        
        # Campos de origem (livro e folha dos documentos de ORIGEM — arrays do form)
        # IMPORTANTE (#118): livro_origem[]/folha_origem[] pertencem à ORIGEM,
        # NÃO ao documento atual. São lidos aqui e repassados para alimentar o
        # fluxo de criação do documento de origem (lancamento_campos_service →
        # lancamento_origem_service). Jamais devem alimentar o documento atual.
        livros_origem = request.POST.getlist('livro_origem[]')
        folhas_origem = request.POST.getlist('folha_origem[]')
        livro_origem = livros_origem[0].strip() if livros_origem and livros_origem[0].strip() else None
        folha_origem = folhas_origem[0].strip() if folhas_origem and folhas_origem[0].strip() else None
        cartorio_id = request.POST.get('cartorio')
        cartorio_nome = request.POST.get('cartorio_nome', '').strip()
        
        # Processar cartório - CORREÇÃO: Não criar cartórios automaticamente
        cartorio_origem = None
        if cartorio_id and cartorio_id.strip():
            from ..models import Cartorios
            try:
                cartorio_origem = Cartorios.objects.get(id=cartorio_id)
            except Cartorios.DoesNotExist:
                # Cartório não encontrado - deixar como None
                pass
        elif cartorio_nome:
            from ..models import Cartorios
            try:
                cartorio_origem = Cartorios.objects.get(nome__iexact=cartorio_nome)
            except Cartorios.DoesNotExist:
                # CORREÇÃO: Não criar cartório automaticamente
                # O usuário deve selecionar um cartório existente
                cartorio_origem = None
        
        # Processar múltiplas origens
        origens_completas = request.POST.getlist('origem_completa[]')
        if origens_completas:
            # Filtrar origens vazias e concatenar
            origens_validas = [origem.strip() for origem in origens_completas if origem.strip()]
            origem = '; '.join(origens_validas) if origens_validas else None
        else:
            # Fallback para campo único
            origem = request.POST.get('origem_completa') or request.POST.get('origem')
        
        # Inicializar descricao_clean
        descricao_clean = None
        
        # Processar campo forma baseado no tipo de lançamento
        if tipo_lanc.tipo == 'averbacao':
            forma_value = request.POST.get('forma_averbacao', '').strip()
            descricao_clean = request.POST.get('descricao') if request.POST.get('descricao') and request.POST.get('descricao').strip() else None
        elif tipo_lanc.tipo == 'registro':
            # Issue #157: `forma_registro` era um nome fantasma (nenhum template
            # emitia esse campo); o bloco Transmissão posta `forma_transacao`.
            forma_value = request.POST.get('forma_transacao', '').strip()
        elif tipo_lanc.tipo == 'inicio_matricula':
            # Issue #157: idem — `forma_inicio` nunca era emitido.
            forma_value = request.POST.get('forma_transacao', '').strip()
            descricao_clean = request.POST.get('descricao') if request.POST.get('descricao') and request.POST.get('descricao').strip() else None
        else:
            forma_value = request.POST.get('forma', '').strip()
        
        titulo_clean = request.POST.get('titulo') if request.POST.get('titulo') and request.POST.get('titulo').strip() else None
        area = request.POST.get('area')
        
        return {
            'numero_lancamento': numero_lancamento,
            'data': data_clean,
            'observacoes': observacoes,
            'livro_documento': livro_documento,
            'folha_documento': folha_documento,
            'livro_origem': livro_origem,
            'folha_origem': folha_origem,
            'cartorio_origem': cartorio_origem,
            'forma': forma_value if forma_value else None,
            'descricao': descricao_clean,
            'titulo': titulo_clean,
            'area': area,
            'origem': origem,
            # Adicionar flag para indicar se cartório é válido
            'cartorio_valido': cartorio_origem is not None,
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
            return f"AV{numero_simples} {sigla_matricula}"
        elif tipo_lanc.tipo == 'registro':
            return f"R{numero_simples} {sigla_matricula}"
        elif tipo_lanc.tipo == 'inicio_matricula':
            return sigla_matricula  # Repete a sigla da matrícula
        else:
            return numero_simples
