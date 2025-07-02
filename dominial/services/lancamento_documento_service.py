"""
Service especializado para operações com documentos relacionados a lançamentos
"""

from ..models import Documento


class LancamentoDocumentoService:
    """
    Service para operações com documentos relacionados a lançamentos
    """
    
    @staticmethod
    def obter_documento_ativo(imovel, documento_id=None):
        """
        Obtém o documento ativo do imóvel
        
        Args:
            imovel: Imóvel para buscar o documento
            documento_id: ID específico do documento (opcional)
            
        Returns:
            Documento: Documento ativo ou None se não encontrado
        """
        if documento_id:
            return Documento.objects.get(id=documento_id, imovel=imovel)
        # Retorna o documento mais recente como ativo
        return imovel.documentos.order_by('-data').first()
    
    @staticmethod
    def criar_documento_matricula_automatico(imovel):
        """
        Cria automaticamente um documento de matrícula para o imóvel
        
        Args:
            imovel: Imóvel para criar o documento
            
        Returns:
            Documento: Documento de matrícula criado
        """
        from ..models import DocumentoTipo
        tipo_matricula = DocumentoTipo.objects.get_or_create(tipo='matricula')[0]
        
        return Documento.objects.create(
            imovel=imovel,
            tipo=tipo_matricula,
            numero='MAT001',
            data='2024-01-01',
            cartorio=imovel.cartorio if imovel.cartorio else None,
            livro='1',
            folha='1'
        )
    
    @staticmethod
    def obter_documentos_por_imovel(imovel):
        """
        Obtém todos os documentos de um imóvel
        
        Args:
            imovel: Imóvel para buscar os documentos
            
        Returns:
            QuerySet: Documentos do imóvel
        """
        return imovel.documentos.all().order_by('-data', 'tipo', 'numero') 