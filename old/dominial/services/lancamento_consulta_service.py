"""
Service especializado para consultas e filtros de lançamentos
"""

from django.db.models import Q, Case, When, IntegerField, Value
from django.core.paginator import Paginator
from ..models import Lancamento, DocumentoTipo, LancamentoTipo
import re


class LancamentoConsultaService:
    """
    Service para consultas e filtros de lançamentos
    """
    
    @staticmethod
    def _extrair_numero_simples(numero_lancamento):
        """
        Extrai o número simples do numero_lancamento para ordenação
        Ex: "R4M235" -> 4, "AV12M235" -> 12, "AV4 M2725" -> 4, "M235" -> 0 (início de matrícula)
        """
        if not numero_lancamento:
            return 0
        
        # Para início de matrícula, retornar 0 para ficar por último
        if not numero_lancamento.startswith(('R', 'AV')):
            return 0
        
        # Extrair número após R ou AV (com ou sem espaço)
        match = re.search(r'^(R|AV)(\d+)', numero_lancamento)
        if match:
            return int(match.group(2))
        
        return 0
    
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
        
        # Ordenar por ID primeiro, depois aplicar ordenação por número simples em Python
        lancamentos = lancamentos.order_by('id')
        
        # Converter para lista e ordenar por número simples em Python (decrescente)
        lancamentos_list = list(lancamentos)
        lancamentos_list.sort(key=lambda x: (
            -LancamentoConsultaService._extrair_numero_simples(x.numero_lancamento),
            x.id
        ))
        
        # Paginação manual
        total_registros = len(lancamentos_list)
        total_paginas = (total_registros + itens_por_pagina - 1) // itens_por_pagina
        pagina_atual = int(pagina) if pagina else 1
        inicio = (pagina_atual - 1) * itens_por_pagina
        fim = inicio + itens_por_pagina
        lancamentos_paginados = lancamentos_list[inicio:fim]
        
        return {
            'lancamentos': lancamentos_paginados,
            'total_registros': total_registros,
            'total_paginas': total_paginas,
            'pagina_atual': pagina_atual,
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
    def obter_lancamentos_por_documento(documento, ordenacao='numero_simples'):
        """
        Obtém todos os lançamentos de um documento específico
        
        Args:
            documento: Documento para buscar lançamentos
            ordenacao: Campo para ordenação ('id', 'data', 'numero_lancamento', 'numero_simples')
            
        Returns:
            List: Lançamentos do documento ordenados
        """
        lancamentos = Lancamento.objects.filter(documento=documento)\
            .select_related('tipo')\
            .prefetch_related('pessoas')
        
        if ordenacao == 'data':
            lancamentos = lancamentos.order_by('data', 'id')
        elif ordenacao == 'numero_lancamento':
            lancamentos = lancamentos.order_by('numero_lancamento', 'id')
        elif ordenacao == 'numero_simples':
            # Ordenar por número simples (decrescente), com início de matrícula por último
            lancamentos_list = list(lancamentos)
            lancamentos_list.sort(key=lambda x: (
                -LancamentoConsultaService._extrair_numero_simples(x.numero_lancamento),
                x.id
            ))
            return lancamentos_list
        else:
            lancamentos = lancamentos.order_by('id')
        
        return lancamentos
    
    @staticmethod
    def obter_lancamentos_por_imovel(imovel, ordenacao='numero_simples'):
        """
        Obtém todos os lançamentos de um imóvel
        
        Args:
            imovel: Imóvel para buscar lançamentos
            ordenacao: Campo para ordenação ('id', 'data', 'numero_lancamento', 'numero_simples')
            
        Returns:
            List: Lançamentos do imóvel ordenados
        """
        lancamentos = Lancamento.objects.filter(documento__imovel=imovel)\
            .select_related('documento', 'documento__tipo', 'tipo')\
            .prefetch_related('pessoas')
        
        if ordenacao == 'data':
            lancamentos = lancamentos.order_by('data', 'id')
        elif ordenacao == 'numero_lancamento':
            lancamentos = lancamentos.order_by('numero_lancamento', 'id')
        elif ordenacao == 'numero_simples':
            # Ordenar por número simples (decrescente), com início de matrícula por último
            lancamentos_list = list(lancamentos)
            lancamentos_list.sort(key=lambda x: (
                -LancamentoConsultaService._extrair_numero_simples(x.numero_lancamento),
                x.id
            ))
            return lancamentos_list
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