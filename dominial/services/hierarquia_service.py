"""
Service consolidado para operações de hierarquia
Consolida funcionalidades de múltiplos services de hierarquia em um único service coeso
"""

from ..utils.hierarquia_utils import identificar_tronco_principal, identificar_troncos_secundarios
from .cache_service import CacheService
from .hierarquia_arvore_service import HierarquiaArvoreService
from .hierarquia_origem_service import HierarquiaOrigemService
from ..managers import documentos_for_user
from ..models import Documento


class HierarquiaService:
    """
    Service consolidado para gerenciar a hierarquia de documentos e cadeia dominial
    Agrupa funcionalidades relacionadas em um único service coeso
    """
    
    # ==================== TRONCO PRINCIPAL ====================
    
    @staticmethod
    def obter_tronco_principal(
        imovel,
        escolhas_origem=None,
        user=None,
        documentos_queryset=None,
    ):
        """
        Obtém o tronco principal da cadeia dominial com cache
        """
        if escolhas_origem is None:
            escolhas_origem = {}
        
        escopo_explicito = user is not None or documentos_queryset is not None
        if documentos_queryset is None:
            documentos_queryset = (
                documentos_for_user(user)
                if user is not None
                else Documento.objects.all()
            )

        # O cache legado é global por imóvel. Para requisições segregadas ele
        # é deliberadamente ignorado, impedindo reutilização entre usuários.
        if not escolhas_origem and not escopo_explicito:
            cached_tronco = CacheService.get_cached_tronco_principal(imovel.id)
            if cached_tronco:
                return cached_tronco
        
        # Calcular tronco considerando escolhas de origem
        tronco = identificar_tronco_principal(
            imovel,
            escolhas_origem,
            documentos_queryset=documentos_queryset,
        )
        
        # Armazenar em cache apenas se não houver escolhas
        if not escolhas_origem and not escopo_explicito:
            CacheService.set_cached_tronco_principal(imovel.id, tronco)
        
        return tronco
    
    @staticmethod
    def obter_troncos_secundarios(
        imovel,
        user=None,
        documentos_queryset=None,
    ):
        """
        Obtém os troncos secundários da cadeia dominial
        """
        if documentos_queryset is None:
            documentos_queryset = (
                documentos_for_user(user)
                if user is not None
                else Documento.objects.all()
            )
        tronco_principal = identificar_tronco_principal(
            imovel,
            documentos_queryset=documentos_queryset,
        )
        return identificar_troncos_secundarios(imovel, tronco_principal)
    
    @staticmethod
    def calcular_hierarquia_documentos(
        imovel,
        user=None,
        documentos_queryset=None,
    ):
        """
        Calcula a hierarquia completa dos documentos de um imóvel
        """
        # Obter todos os documentos do imóvel
        if documentos_queryset is None:
            documentos_queryset = (
                documentos_for_user(user)
                if user is not None
                else Documento.objects.all()
            )
        documentos = documentos_queryset.filter(imovel=imovel).select_related('tipo', 'cartorio')
        
        # Calcular hierarquia baseada nas origens
        hierarquia = {}
        for documento in documentos:
            # Processar origens do documento
            origens = HierarquiaService._extrair_origens_documento(documento)
            hierarquia[documento.id] = {
                'documento': documento,
                'origens': origens,
                'nivel': 0  # Será calculado posteriormente
            }
        
        # Calcular níveis hierárquicos
        HierarquiaService._calcular_niveis_hierarquicos(hierarquia)
        
        return hierarquia
    
    @staticmethod
    def validar_hierarquia(
        imovel,
        user=None,
        documentos_queryset=None,
    ):
        """
        Valida se a hierarquia de documentos está consistente
        """
        try:
            if documentos_queryset is None:
                documentos_queryset = (
                    documentos_for_user(user)
                    if user is not None
                    else Documento.objects.all()
                )
            tronco = HierarquiaService.obter_tronco_principal(
                imovel,
                documentos_queryset=documentos_queryset,
            )
            troncos_secundarios = HierarquiaService.obter_troncos_secundarios(
                imovel,
                documentos_queryset=documentos_queryset,
            )
            
            # Verificar se há documentos órfãos
            todos_documentos = documentos_queryset.filter(imovel=imovel)
            documentos_hierarquia = set()
            
            # Adicionar documentos do tronco principal
            for doc in tronco:
                documentos_hierarquia.add(doc['documento'].id)
            
            # Adicionar documentos dos troncos secundários
            for tronco_sec in troncos_secundarios:
                for doc in tronco_sec:
                    documentos_hierarquia.add(doc['documento'].id)
            
            # Verificar documentos órfãos
            documentos_orfaos = todos_documentos.exclude(id__in=documentos_hierarquia)
            
            return {
                'valida': len(documentos_orfaos) == 0,
                'documentos_orfaos': list(documentos_orfaos),
                'tronco_principal': len(tronco),
                'troncos_secundarios': len(troncos_secundarios)
            }
            
        except Exception as e:
            return {
                'valida': False,
                'erro': str(e),
                'documentos_orfaos': [],
                'tronco_principal': 0,
                'troncos_secundarios': 0
            }
    
    # ==================== ÁRVORE D3 ====================
    
    @staticmethod
    def construir_arvore_cadeia_dominial(
        imovel,
        criar_documentos_automaticos=False,
        user=None,
        documentos_queryset=None,
    ):
        """
        Constrói a estrutura de árvore da cadeia dominial para visualização
        """
        if documentos_queryset is None:
            documentos_queryset = (
                documentos_for_user(user)
                if user is not None
                else Documento.objects.all()
            )
        return HierarquiaArvoreService.construir_arvore_cadeia_dominial(
            imovel,
            criar_documentos_automaticos,
            documentos_queryset=documentos_queryset,
        )
    
    # ==================== ORIGENS ====================
    
    @staticmethod
    def processar_origens_identificadas(imovel, criar_documentos_automaticos=False):
        """
        Processa origens identificadas de lançamentos
        """
        return HierarquiaOrigemService.processar_origens_identificadas(imovel, criar_documentos_automaticos)
    
    # ==================== MÉTODOS AUXILIARES ====================
    
    @staticmethod
    def _extrair_origens_documento(documento):
        """
        Extrai origens de um documento
        """
        origens = []
        if documento.origem:
            # Processar string de origem (formato: "M123, T456")
            origens_str = documento.origem.split(',')
            for origem in origens_str:
                origem = origem.strip()
                if origem:
                    origens.append(origem)
        return origens
    
    @staticmethod
    def _calcular_niveis_hierarquicos(hierarquia):
        """
        Calcula níveis hierárquicos dos documentos
        """
        # Implementação simplificada - pode ser expandida conforme necessário
        for doc_id, dados in hierarquia.items():
            # Nível baseado no número de origens
            dados['nivel'] = len(dados['origens'])
