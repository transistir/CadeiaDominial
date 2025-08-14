"""
Service para gerenciar identificação e informações de documentos importados
"""

from django.db.models import Q
from ..models import Documento, DocumentoImportado


class DocumentoImportadoService:
    """
    Service para identificar e gerenciar documentos importados
    """
    
    @staticmethod
    def is_documento_importado(documento):
        """
        Verifica se um documento foi importado de outra cadeia dominial
        
        Args:
            documento: Objeto Documento
            
        Returns:
            bool: True se o documento foi importado
        """
        return DocumentoImportado.objects.filter(documento=documento).exists()
    
    @staticmethod
    def get_info_importacao(documento):
        """
        Obtém informações detalhadas sobre a importação de um documento
        
        Args:
            documento: Objeto Documento
            
        Returns:
            dict: Informações da importação ou None se não foi importado
        """
        try:
            # CORREÇÃO: Usar filter().first() em vez de get() para evitar MultipleObjectsReturned
            doc_importado = DocumentoImportado.objects.select_related(
                'imovel_origem', 'importado_por'
            ).filter(documento=documento).order_by('-data_importacao').first()
            
            if not doc_importado:
                return None
            
            return {
                'imovel_origem': {
                    'id': doc_importado.imovel_origem.id,
                    'matricula': doc_importado.imovel_origem.matricula,
                    'nome': doc_importado.imovel_origem.nome
                },
                'data_importacao': doc_importado.data_importacao,
                'importado_por': {
                    'id': doc_importado.importado_por.id,
                    'username': doc_importado.importado_por.username,
                    'nome': doc_importado.importado_por.get_full_name() or doc_importado.importado_por.username
                } if doc_importado.importado_por else None,
                'origem_info': doc_importado.get_origem_info(),
                'importador_info': doc_importado.get_importador_info()
            }
        except Exception as e:
            # Log do erro para debug
            print(f"Erro ao obter info de importação para documento {documento.id}: {str(e)}")
            return None
    
    @staticmethod
    def get_documentos_importados_imovel(imovel):
        """
        Obtém todos os documentos importados de um imóvel
        
        Args:
            imovel: Objeto Imovel
            
        Returns:
            QuerySet: Documentos importados do imóvel
        """
        return DocumentoImportado.objects.filter(
            documento__imovel=imovel
        ).select_related(
            'documento',
            'documento__tipo',
            'documento__cartorio',
            'imovel_origem',
            'importado_por'
        )
    
    @staticmethod
    def get_documentos_importados_ids(imovel):
        """
        Obtém apenas os IDs dos documentos importados de um imóvel
        
        Args:
            imovel: Objeto Imovel
            
        Returns:
            set: Set com IDs dos documentos importados
        """
        return set(
            DocumentoImportado.objects.filter(
                documento__imovel=imovel
            ).values_list('documento_id', flat=True)
        )
    
    @staticmethod
    def get_tooltip_importacao(documento):
        """
        Gera texto para tooltip de documento importado
        
        Args:
            documento: Objeto Documento
            
        Returns:
            str: Texto do tooltip ou None se não foi importado
        """
        info = DocumentoImportadoService.get_info_importacao(documento)
        if info:
            return f"📄 Importado de {info['imovel_origem']['matricula']}\n👤 {info['importador_info']}\n🕒 {info['data_importacao'].strftime('%d/%m/%Y %H:%M')}"
        return None 