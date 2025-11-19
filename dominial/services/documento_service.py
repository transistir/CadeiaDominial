"""
Service consolidado para operações de documento
Consolida funcionalidades de múltiplos services de documento em um único service coeso
"""

from django.db.models import Q
from ..models import Documento, DocumentoTipo, Cartorios, DocumentoImportado
from ..utils.validacao_utils import validar_matricula


class DocumentoService:
    """
    Service consolidado para gerenciar operações com documentos
    Agrupa funcionalidades relacionadas em um único service coeso
    """
    
    # ==================== OPERAÇÕES BÁSICAS ====================
    
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
    
    # ==================== DOCUMENTOS IMPORTADOS ====================
    
    @staticmethod
    def is_documento_importado(documento):
        """
        Verifica se um documento foi importado de outra cadeia dominial
        """
        return DocumentoImportado.objects.filter(documento=documento).exists()
    
    @staticmethod
    def get_info_importacao(documento):
        """
        Obtém informações detalhadas sobre a importação de um documento
        """
        try:
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
                'importado_por': {
                    'id': doc_importado.importado_por.id if doc_importado.importado_por else None,
                    'username': doc_importado.importado_por.username if doc_importado.importado_por else 'Sistema'
                },
                'data_importacao': doc_importado.data_importacao
            }
        except Exception as e:
            return None
    
    @staticmethod
    def marcar_como_importado(documento, imovel_origem, usuario, motivo=None):
        """
        Marca um documento como importado
        """
        doc_importado, created = DocumentoImportado.objects.get_or_create(
            documento=documento,
            defaults={
                'imovel_origem': imovel_origem,
                'importado_por': usuario
            }
        )
        return doc_importado
    
    # ==================== DOCUMENTOS COMPARTILHADOS ====================
    
    @staticmethod
    def is_documento_compartilhado(documento, imovel_atual):
        """
        Verifica se um documento é compartilhado (pertence a outro imóvel)
        """
        return documento.imovel != imovel_atual
    
    @staticmethod
    def obter_documentos_compartilhados(imovel):
        """
        Obtém documentos que são compartilhados com o imóvel
        """
        # Buscar documentos que são referenciados como origem em lançamentos deste imóvel
        from ..models import Lancamento
        
        lancamentos = Lancamento.objects.filter(
            documento__imovel=imovel
        ).select_related('documento_origem')
        
        documentos_compartilhados = []
        for lancamento in lancamentos:
            if lancamento.documento_origem and lancamento.documento_origem.imovel != imovel:
                documentos_compartilhados.append(lancamento.documento_origem)
        
        return list(set(documentos_compartilhados))  # Remove duplicatas
    
    @staticmethod
    def obter_info_compartilhamento(documento, imovel_atual):
        """
        Obtém informações sobre o compartilhamento de um documento
        """
        if not DocumentoService.is_documento_compartilhado(documento, imovel_atual):
            return None
        
        return {
            'imovel_origem': {
                'id': documento.imovel.id,
                'matricula': documento.imovel.matricula,
                'nome': documento.imovel.nome
            },
            'documento': {
                'id': documento.id,
                'numero': documento.numero,
                'tipo': documento.tipo.get_tipo_display(),
                'cartorio': documento.cartorio.nome if documento.cartorio else None
            }
        }
    
    # ==================== BUSCA E FILTROS ====================
    
    @staticmethod
    def buscar_documentos_por_numero(numero, cartorio=None):
        """
        Busca documentos por número, opcionalmente filtrando por cartório
        """
        queryset = Documento.objects.filter(numero__icontains=numero)
        
        if cartorio:
            queryset = queryset.filter(cartorio=cartorio)
        
        return queryset.select_related('imovel', 'tipo', 'cartorio')
    
    @staticmethod
    def buscar_documentos_por_imovel(imovel, tipo_documento=None):
        """
        Busca documentos de um imóvel, opcionalmente filtrando por tipo
        """
        queryset = Documento.objects.filter(imovel=imovel)
        
        if tipo_documento:
            queryset = queryset.filter(tipo__tipo=tipo_documento)
        
        return queryset.select_related('tipo', 'cartorio').order_by('-data')
    
    # ==================== ESTATÍSTICAS ====================
    
    @staticmethod
    def obter_estatisticas_documentos(imovel=None):
        """
        Obtém estatísticas dos documentos
        """
        queryset = Documento.objects.all()
        
        if imovel:
            queryset = queryset.filter(imovel=imovel)
        
        total = queryset.count()
        from django.db import models
        por_tipo = queryset.values('tipo__tipo').annotate(
            count=models.Count('id')
        ).order_by('tipo__tipo')
        
        importados = queryset.filter(
            documentoimportado__isnull=False
        ).count()
        
        return {
            'total': total,
            'por_tipo': list(por_tipo),
            'importados': importados,
            'locais': total - importados
        }
