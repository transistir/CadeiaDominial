"""
Service para operações relacionadas a documentos
"""

from ..models import Documento, DocumentoTipo, Cartorios
from ..utils.validacao_utils import validar_matricula


class DocumentoService:
    """
    Service para gerenciar operações com documentos
    """
    
    @staticmethod
    def criar_documento(imovel, tipo, numero, data, cartorio, livro, folha, origem=None, observacoes=None):
        """
        Cria um novo documento
        """
        # Validações básicas
        if not validar_matricula(numero):
            raise ValueError("Número de documento inválido")
        
        documento = Documento.objects.create(
            imovel=imovel,
            tipo=tipo,
            numero=numero,
            data=data,
            cartorio=cartorio,
            livro=livro,
            folha=folha,
            origem=origem,
            observacoes=observacoes
        )
        
        return documento
    
    @staticmethod
    def obter_documentos_imovel(imovel):
        """
        Obtém todos os documentos de um imóvel ordenados por data
        """
        return Documento.objects.filter(imovel=imovel).order_by('data')
    
    @staticmethod
    def obter_documento_por_numero(numero, cartorio):
        """
        Obtém um documento pelo número e cartório
        """
        try:
            return Documento.objects.get(numero=numero, cartorio=cartorio)
        except Documento.DoesNotExist:
            return None
    
    @staticmethod
    def validar_documento_unico(numero, cartorio, imovel=None, documento_id=None):
        """
        Valida se o documento é único (não existe outro com mesmo número e cartório)
        """
        queryset = Documento.objects.filter(numero=numero, cartorio=cartorio)
        
        if documento_id:
            queryset = queryset.exclude(id=documento_id)
        
        if imovel:
            queryset = queryset.exclude(imovel=imovel)
        
        return not queryset.exists() 