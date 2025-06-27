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
        return imovel.documento_set.filter(ativo=True).first()
    
    @staticmethod
    def criar_documento_matricula_automatico(imovel):
        """
        Cria automaticamente um documento de matrícula para o imóvel
        
        Args:
            imovel: Imóvel para criar o documento
            
        Returns:
            Documento: Documento de matrícula criado
        """
        return Documento.objects.create(
            imovel=imovel,
            tipo='matricula',
            numero='MAT001',
            ativo=True
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
        return imovel.documento_set.all().order_by('-ativo', 'tipo', 'numero')
    
    @staticmethod
    def ativar_documento(documento):
        """
        Ativa um documento e desativa os outros do mesmo imóvel
        
        Args:
            documento: Documento a ser ativado
            
        Returns:
            Documento: Documento ativado
        """
        # Desativar outros documentos do mesmo imóvel
        documento.imovel.documento_set.exclude(id=documento.id).update(ativo=False)
        
        # Ativar o documento
        documento.ativo = True
        documento.save()
        
        return documento
    
    @staticmethod
    def desativar_documento(documento):
        """
        Desativa um documento
        
        Args:
            documento: Documento a ser desativado
            
        Returns:
            Documento: Documento desativado
        """
        documento.ativo = False
        documento.save()
        return documento 