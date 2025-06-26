"""
Service para processamento de cartório de origem do lançamento
"""
from ..models import Cartorios
import uuid

class LancamentoCartorioService:
    @staticmethod
    def processar_cartorio_origem(request, tipo_lanc, lancamento):
        cartorio_origem_id = request.POST.get('cartorio_origem')
        cartorio_origem_nome = request.POST.get('cartorio_origem_nome', '').strip()
        if tipo_lanc.tipo == 'averbacao' and request.POST.get('incluir_cartorio_averbacao') == 'on':
            cartorio_origem_id = request.POST.get('cartorio_origem_averbacao')
            cartorio_origem_nome = request.POST.get('cartorio_origem_nome_averbacao', '').strip()
            livro_origem_clean = request.POST.get('livro_origem_averbacao') if request.POST.get('livro_origem_averbacao') and request.POST.get('livro_origem_averbacao').strip() else None
            folha_origem_clean = request.POST.get('folha_origem_averbacao') if request.POST.get('folha_origem_averbacao') and request.POST.get('folha_origem_averbacao').strip() else None
            data_origem_clean = request.POST.get('data_origem_averbacao') if request.POST.get('data_origem_averbacao') else None
            titulo_clean = request.POST.get('titulo_averbacao') if request.POST.get('titulo_averbacao') and request.POST.get('titulo_averbacao').strip() else None
            lancamento.livro_origem = livro_origem_clean
            lancamento.folha_origem = folha_origem_clean
            lancamento.data_origem = data_origem_clean
            lancamento.titulo = titulo_clean
        if cartorio_origem_id and cartorio_origem_id.strip():
            lancamento.cartorio_origem_id = cartorio_origem_id
        elif cartorio_origem_nome:
            try:
                cartorio = Cartorios.objects.get(nome__iexact=cartorio_origem_nome)
                lancamento.cartorio_origem = cartorio
            except Cartorios.DoesNotExist:
                cns_unico = f"CNS{str(uuid.uuid4().int)[:10]}"
                cartorio = Cartorios.objects.create(
                    nome=cartorio_origem_nome,
                    cns=cns_unico,
                    cidade=Cartorios.objects.first().cidade if Cartorios.objects.exists() else None
                )
                lancamento.cartorio_origem = cartorio
        else:
            lancamento.cartorio_origem_id = None 