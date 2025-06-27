"""
Service especializado para consultas e filtros de lançamentos
"""

from django.db.models import Q
from django.core.paginator import Paginator
from ..models import Lancamento, DocumentoTipo, LancamentoTipo


class LancamentoConsultaService:
    """
    Service para consultas e filtros de lançamentos
    """
    
    @staticmethod
    def filtrar_lancamentos(filtros=None, pagina=None, itens_por_pagina=10):
        """
        Filtra lançamentos com base nos parâmetros fornecidos
        
        Args:
            filtros: Dicionário com filtros (tipo_documento, tipo_lancamento, busca)
            pagina: Número da página para paginação
            itens_por_pagina: Quantidade de itens por página
            
        Returns:
            dict: Dicionário com lançamentos paginados e metadados
        """
        # Iniciar queryset com otimizações
        lancamentos = Lancamento.objects.select_related(
            'documento', 'documento__tipo', 'documento__imovel', 'tipo'
        ).prefetch_related('pessoas')
        
        # Aplicar filtros se fornecidos
        if filtros:
            lancamentos = LancamentoConsultaService._aplicar_filtros(lancamentos, filtros)
        
        # Ordenar por ordem de inserção (ID crescente)
        lancamentos = lancamentos.order_by('id')
        
        # Paginação
        paginator = Paginator(lancamentos, itens_por_pagina)
        page = paginator.get_page(pagina)
        
        return {
            'lancamentos': page,
            'total_registros': paginator.count,
            'total_paginas': paginator.num_pages,
            'pagina_atual': page.number,
        }
    
    @staticmethod
    def _aplicar_filtros(queryset, filtros):
        """
        Aplica filtros ao queryset de lançamentos
        
        Args:
            queryset: QuerySet base de lançamentos
            filtros: Dicionário com filtros
            
        Returns:
            QuerySet: QuerySet filtrado
        """
        if filtros.get('tipo_documento'):
            queryset = queryset.filter(documento__tipo_id=filtros['tipo_documento'])
        
        if filtros.get('tipo_lancamento'):
            queryset = queryset.filter(tipo_id=filtros['tipo_lancamento'])
        
        if filtros.get('busca'):
            busca = filtros['busca'].strip()
            queryset = queryset.filter(
                Q(documento__numero__icontains=busca) |
                Q(numero_lancamento__icontains=busca) |
                Q(documento__imovel__matricula__icontains=busca) |
                Q(documento__imovel__terra_indigena_id__nome__icontains=busca)
            )
        
        if filtros.get('data_inicio'):
            queryset = queryset.filter(data__gte=filtros['data_inicio'])
        
        if filtros.get('data_fim'):
            queryset = queryset.filter(data__lte=filtros['data_fim'])
        
        if filtros.get('imovel_id'):
            queryset = queryset.filter(documento__imovel_id=filtros['imovel_id'])
        
        if filtros.get('documento_id'):
            queryset = queryset.filter(documento_id=filtros['documento_id'])
        
        return queryset
    
    @staticmethod
    def obter_lancamentos_por_documento(documento, ordenacao='id'):
        """
        Obtém todos os lançamentos de um documento específico
        
        Args:
            documento: Documento para buscar lançamentos
            ordenacao: Campo para ordenação ('id', 'data', 'numero_lancamento')
            
        Returns:
            QuerySet: Lançamentos do documento
        """
        lancamentos = Lancamento.objects.filter(documento=documento)\
            .select_related('tipo')\
            .prefetch_related('pessoas')
        
        if ordenacao == 'data':
            lancamentos = lancamentos.order_by('data', 'id')
        elif ordenacao == 'numero_lancamento':
            lancamentos = lancamentos.order_by('numero_lancamento', 'id')
        else:
            lancamentos = lancamentos.order_by('id')
        
        return lancamentos
    
    @staticmethod
    def obter_lancamentos_por_imovel(imovel, ordenacao='id'):
        """
        Obtém todos os lançamentos de um imóvel
        
        Args:
            imovel: Imóvel para buscar lançamentos
            ordenacao: Campo para ordenação ('id', 'data', 'numero_lancamento')
            
        Returns:
            QuerySet: Lançamentos do imóvel
        """
        lancamentos = Lancamento.objects.filter(documento__imovel=imovel)\
            .select_related('documento', 'documento__tipo', 'tipo')\
            .prefetch_related('pessoas')
        
        if ordenacao == 'data':
            lancamentos = lancamentos.order_by('data', 'id')
        elif ordenacao == 'numero_lancamento':
            lancamentos = lancamentos.order_by('numero_lancamento', 'id')
        else:
            lancamentos = lancamentos.order_by('id')
        
        return lancamentos
    
    @staticmethod
    def obter_estatisticas_lancamentos():
        """
        Obtém estatísticas gerais dos lançamentos
        
        Returns:
            dict: Estatísticas dos lançamentos
        """
        total_lancamentos = Lancamento.objects.count()
        lancamentos_por_tipo = {}
        lancamentos_por_documento = {}
        
        # Contar por tipo de lançamento
        for lancamento in Lancamento.objects.select_related('tipo').all():
            tipo = lancamento.tipo.tipo
            lancamentos_por_tipo[tipo] = lancamentos_por_tipo.get(tipo, 0) + 1
        
        # Contar por tipo de documento
        for lancamento in Lancamento.objects.select_related('documento__tipo').all():
            tipo_doc = lancamento.documento.tipo.tipo
            lancamentos_por_documento[tipo_doc] = lancamentos_por_documento.get(tipo_doc, 0) + 1
        
        return {
            'total_lancamentos': total_lancamentos,
            'lancamentos_por_tipo': lancamentos_por_tipo,
            'lancamentos_por_documento': lancamentos_por_documento,
        }
    
    @staticmethod
    def obter_tipos_para_filtros():
        """
        Obtém os tipos de documento e lançamento para filtros
        
        Returns:
            dict: Tipos para filtros
        """
        return {
            'tipos_documento': DocumentoTipo.objects.all().order_by('tipo'),
            'tipos_lancamento': LancamentoTipo.objects.all().order_by('tipo'),
        } 