"""
Service para processamento de cartório de origem do lançamento
"""
from ..models import Cartorios
import uuid

class LancamentoCartorioService:
    @staticmethod
    def processar_cartorio_origem(request, tipo_lanc, lancamento):
        """
        Processa o cartório de origem do lançamento
        Agora o cartório é sempre obrigatório no bloco básico
        """
        cartorio_origem_id = request.POST.get('cartorio')
        cartorio_origem_nome = request.POST.get('cartorio_nome', '').strip()
        
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