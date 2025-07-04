"""
Service principal para operações relacionadas à hierarquia de documentos
"""

from .hierarquia_tronco_service import HierarquiaTroncoService
from .hierarquia_arvore_service import HierarquiaArvoreService


class HierarquiaService:
    """
    Service principal para gerenciar a hierarquia de documentos e cadeia dominial
    Mantém compatibilidade com código existente, delegando para services especializados
    """
    
    @staticmethod
    def calcular_hierarquia_documentos(imovel):
        """
        Calcula a hierarquia completa dos documentos de um imóvel
        """
        return HierarquiaTroncoService.calcular_hierarquia_documentos(imovel)
    
    @staticmethod
    def obter_tronco_principal(imovel, escolhas_origem=None):
        """
        Obtém o tronco principal da cadeia dominial com cache
        """
        return HierarquiaTroncoService.obter_tronco_principal(imovel, escolhas_origem)
    
    @staticmethod
    def obter_troncos_secundarios(imovel):
        """
        Obtém os troncos secundários da cadeia dominial
        """
        return HierarquiaTroncoService.obter_troncos_secundarios(imovel)
    
    @staticmethod
    def validar_hierarquia(imovel):
        """
        Valida se a hierarquia de documentos está consistente
        """
        return HierarquiaTroncoService.validar_hierarquia(imovel)

    @staticmethod
    def construir_arvore_cadeia_dominial(imovel):
        """
        Constrói a estrutura de árvore da cadeia dominial para visualização
        """
        return HierarquiaArvoreService.construir_arvore_cadeia_dominial(imovel) 