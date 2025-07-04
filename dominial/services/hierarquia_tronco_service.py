"""
Service especializado para tronco principal e secundários da hierarquia
"""

from ..utils.hierarquia_utils import identificar_tronco_principal, identificar_troncos_secundarios
from .cache_service import CacheService


class HierarquiaTroncoService:
    """
    Service para gerenciar tronco principal e secundários da cadeia dominial
    """
    
    @staticmethod
    def obter_tronco_principal(imovel, escolhas_origem=None):
        """
        Obtém o tronco principal da cadeia dominial com cache
        """
        if escolhas_origem is None:
            escolhas_origem = {}
        
        # Tentar obter do cache primeiro (apenas se não houver escolhas)
        if not escolhas_origem:
            cached_tronco = CacheService.get_cached_tronco_principal(imovel.id)
            if cached_tronco:
                return cached_tronco
        
        # Calcular tronco considerando escolhas de origem
        tronco = identificar_tronco_principal(imovel, escolhas_origem)
        
        # Armazenar em cache apenas se não houver escolhas
        if not escolhas_origem:
            CacheService.set_cached_tronco_principal(imovel.id, tronco)
        
        return tronco
    
    @staticmethod
    def obter_troncos_secundarios(imovel):
        """
        Obtém os troncos secundários da cadeia dominial
        """
        tronco_principal = identificar_tronco_principal(imovel)
        return identificar_troncos_secundarios(imovel, tronco_principal)
    
    @staticmethod
    def calcular_hierarquia_documentos(imovel):
        """
        Calcula a hierarquia completa dos documentos de um imóvel
        """
        from ..models import Documento
        from ..utils.hierarquia_utils import calcular_niveis_hierarquicos_otimizada
        
        # Otimização: usar select_related para cartório e tipo
        documentos = Documento.objects.filter(imovel=imovel)\
            .select_related('cartorio', 'tipo')\
            .prefetch_related('lancamentos', 'lancamentos__tipo')\
            .order_by('data')
        
        conexoes = []
        
        # TODO: Implementar lógica de identificação de conexões
        # Esta será implementada na Fase 2
        
        return calcular_niveis_hierarquicos_otimizada(documentos, conexoes)
    
    @staticmethod
    def validar_hierarquia(imovel):
        """
        Valida se a hierarquia de documentos está consistente
        """
        # TODO: Implementar validações de consistência
        # Esta será implementada na Fase 2
        return True 