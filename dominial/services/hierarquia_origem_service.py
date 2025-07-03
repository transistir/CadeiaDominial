"""
Service especializado para processamento de origens na hierarquia
"""

from ..models import Documento, Lancamento, Cartorios, DocumentoTipo
from ..utils.hierarquia_utils import processar_origens_para_documentos
from .cache_service import CacheService
from datetime import date


class HierarquiaOrigemService:
    """
    Service para processar origens identificadas de lançamentos
    """
    
    @staticmethod
    def processar_origens_identificadas(imovel):
        """
        Processa origens identificadas de lançamentos que ainda não foram convertidas em documentos
        """
        origens_identificadas = []
        
        # Otimização: usar select_related para reduzir queries
        lancamentos_com_origem = Lancamento.objects.filter(
            documento__imovel=imovel,
            origem__isnull=False
        ).exclude(origem='')\
         .select_related('documento', 'documento__cartorio', 'documento__tipo')
        
        for lancamento in lancamentos_com_origem:
            if lancamento.origem:
                origens_processadas = processar_origens_para_documentos(lancamento.origem, imovel, lancamento)
                
                for origem_info in origens_processadas:
                    origem_identificada = HierarquiaOrigemService._processar_origem_individual(
                        imovel, lancamento, origem_info
                    )
                    if origem_identificada:
                        origens_identificadas.append(origem_identificada)
        
        return origens_identificadas
    
    @staticmethod
    def _processar_origem_individual(imovel, lancamento, origem_info):
        """
        Processa uma origem individual
        """
        # Verificar se já existe um documento com esse número
        documento_existente = Documento.objects.filter(imovel=imovel, numero=origem_info['numero']).first()
        
        if not documento_existente:
            # Criar o documento automaticamente
            return HierarquiaOrigemService._criar_documento_automatico(
                imovel, lancamento, origem_info
            )
        else:
            # Documento já existe, adicionar como origem identificada criada
            return HierarquiaOrigemService._criar_origem_existente(
                lancamento, origem_info, documento_existente
            )
    
    @staticmethod
    def _criar_documento_automatico(imovel, lancamento, origem_info):
        """
        Cria um documento automaticamente a partir de uma origem
        """
        try:
            tipo_doc = DocumentoTipo.objects.get(tipo=origem_info['tipo'])
            
            # Verificar se já existe um documento com esse número
            documento_existente = Documento.objects.filter(imovel=imovel, numero=origem_info['numero']).first()
            if documento_existente:
                # Se já existe, retornar como origem identificada criada
                return HierarquiaOrigemService._criar_origem_identificada(
                    lancamento, origem_info, documento_existente.id, True
                )
            
            documento_criado = Documento.objects.create(
                imovel=imovel,
                tipo=tipo_doc,
                numero=origem_info['numero'],
                data=date.today(),
                cartorio=imovel.cartorio if imovel.cartorio else Cartorios.objects.first(),
                livro='1',  # Livro padrão
                folha='1',  # Folha padrão
                origem=f'Criado automaticamente a partir de origem: {origem_info["numero"]}',
                observacoes=f'Documento criado automaticamente ao identificar origem "{origem_info["numero"]}" no lançamento {lancamento.numero_lancamento}'
            )
            
            # Invalidar cache do imóvel
            CacheService.invalidate_documentos_imovel(imovel.id)
            CacheService.invalidate_tronco_principal(imovel.id)
            
            # Retornar origem identificada criada
            return HierarquiaOrigemService._criar_origem_identificada(
                lancamento, origem_info, documento_criado.id, True
            )
            
        except DocumentoTipo.DoesNotExist:
            # Se o tipo não existir, apenas listar como origem identificada
            return HierarquiaOrigemService._criar_origem_identificada(
                lancamento, origem_info, None, False
            )
    
    @staticmethod
    def _criar_origem_existente(lancamento, origem_info, documento_existente):
        """
        Cria uma origem identificada para um documento que já existe
        """
        return HierarquiaOrigemService._criar_origem_identificada(
            lancamento, origem_info, documento_existente.id, True
        )
    
    @staticmethod
    def _criar_origem_identificada(lancamento, origem_info, documento_id, ja_criado):
        """
        Cria uma estrutura de origem identificada
        """
        return {
            'codigo': origem_info['numero'],
            'tipo': origem_info['tipo'],
            'tipo_display': 'Matrícula' if origem_info['tipo'] == 'matricula' else 'Transcrição',
            'lancamento_origem': lancamento.numero_lancamento,
            'documento_origem': lancamento.documento.numero,
            'data_identificacao': lancamento.data.strftime('%d/%m/%Y'),
            'cor': '#28a745' if origem_info['tipo'] == 'matricula' else '#6f42c1',
            'documento_id': documento_id,
            'ja_criado': ja_criado
        } 