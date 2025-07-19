"""
Service para verificação de duplicatas de origem/cartório.
Detecta quando uma origem/cartório já existe em outras cadeias dominiais.
"""

from django.conf import settings
from django.db.models import Q
from typing import Dict, List, Optional, Any
from ..models import Documento, DocumentoImportado


class DuplicataVerificacaoService:
    """
    Service responsável por verificar duplicatas de origem/cartório
    e calcular documentos importáveis.
    """
    
    @staticmethod
    def verificar_duplicata_origem(origem: str, cartorio_id: int, imovel_atual_id: int) -> Dict[str, Any]:
        """
        Verifica se uma origem/cartório já existe em outras cadeias dominiais.
        
        Args:
            origem: Número da origem/documento
            cartorio_id: ID do cartório
            imovel_atual_id: ID do imóvel atual (para excluir da busca)
            
        Returns:
            Dict com informações sobre a duplicata encontrada ou None
        """
        if not getattr(settings, 'DUPLICATA_VERIFICACAO_ENABLED', False):
            return {'existe': False}
        
        # Buscar documento com mesmo número e cartório em outros imóveis
        documento_existente = Documento.objects.filter(
            numero=origem,
            cartorio_id=cartorio_id
        ).exclude(
            imovel_id=imovel_atual_id
        ).select_related('imovel', 'cartorio', 'tipo').first()
        
        if not documento_existente:
            return {'existe': False}
        
        # Calcular documentos importáveis
        documentos_importaveis = DuplicataVerificacaoService.calcular_documentos_importaveis(
            documento_existente
        )
        
        return {
            'existe': True,
            'documento': {
                'id': documento_existente.id,
                'numero': documento_existente.numero,
                'tipo': documento_existente.tipo.tipo,
                'imovel': {
                    'id': documento_existente.imovel.id,
                    'matricula': documento_existente.imovel.matricula
                },
                'cartorio': {
                    'id': documento_existente.cartorio.id,
                    'nome': documento_existente.cartorio.nome
                }
            },
            'documentos_importaveis': documentos_importaveis,
            'total_importaveis': len(documentos_importaveis)
        }
    
    @staticmethod
    def calcular_documentos_importaveis(documento_origem: Documento) -> List[Dict[str, Any]]:
        """
        Calcula quais documentos podem ser importados a partir de um documento origem.
        Busca documentos anteriores na cadeia dominial (para trás).
        
        Args:
            documento_origem: Documento de origem para calcular importáveis
            
        Returns:
            Lista de documentos que podem ser importados
        """
        documentos_importaveis = []
        
        # Buscar documentos anteriores na cadeia (lancamentos com este documento como origem)
        lancamentos_anteriores = documento_origem.lancamento_set.all()
        
        for lancamento in lancamentos_anteriores:
            documento_anterior = lancamento.documento
            
            # Verificar se já não foi importado
            if not DocumentoImportado.objects.filter(
                documento=documento_anterior,
                imovel_origem=documento_origem.imovel
            ).exists():
                
                documentos_importaveis.append({
                    'id': documento_anterior.id,
                    'numero': documento_anterior.numero,
                    'tipo': documento_anterior.tipo.tipo,
                    'data': documento_anterior.data,
                    'cartorio': {
                        'id': documento_anterior.cartorio.id,
                        'nome': documento_anterior.cartorio.nome
                    }
                })
        
        # Ordenar por data (mais antigos primeiro)
        documentos_importaveis.sort(key=lambda x: x['data'])
        
        return documentos_importaveis
    
    @staticmethod
    def obter_cadeia_dominial_origem(documento_origem: Documento) -> Dict[str, Any]:
        """
        Obtém informações completas da cadeia dominial de um documento origem.
        
        Args:
            documento_origem: Documento de origem
            
        Returns:
            Dict com informações da cadeia dominial
        """
        documentos_importaveis = DuplicataVerificacaoService.calcular_documentos_importaveis(
            documento_origem
        )
        
        return {
            'documento_origem': {
                'id': documento_origem.id,
                'numero': documento_origem.numero,
                'tipo': documento_origem.tipo.tipo,
                'imovel': {
                    'id': documento_origem.imovel.id,
                    'matricula': documento_origem.imovel.matricula
                }
            },
            'documentos_importaveis': documentos_importaveis,
            'total_documentos': len(documentos_importaveis) + 1  # +1 para o documento origem
        }
    
    @staticmethod
    def verificar_performance_consulta(origem: str, cartorio_id: int) -> Dict[str, Any]:
        """
        Verifica a performance da consulta de duplicatas.
        Útil para monitoramento e otimização.
        
        Args:
            origem: Número da origem
            cartorio_id: ID do cartório
            
        Returns:
            Dict com métricas de performance
        """
        import time
        
        inicio = time.time()
        
        # Executar consulta
        resultado = DuplicataVerificacaoService.verificar_duplicata_origem(
            origem, cartorio_id, 0  # imovel_id=0 para teste
        )
        
        tempo_execucao = time.time() - inicio
        
        return {
            'tempo_execucao': tempo_execucao,
            'tempo_aceitavel': tempo_execucao < 0.1,  # Menos de 100ms
            'resultado': resultado
        } 