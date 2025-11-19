"""
Service para verificação de duplicatas de origem/cartório.
Detecta quando uma origem/cartório já existe em outras cadeias dominiais.
"""

import logging
from django.conf import settings
from django.db.models import Q
from typing import Dict, List, Optional, Any
from ..models import Documento, DocumentoImportado, Lancamento

logger = logging.getLogger(__name__)


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
        if not getattr(settings, 'DUPLICATA_VERIFICACAO_ENABLED', True):
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

        # Obter cadeia dominial
        cadeia_dominial = DuplicataVerificacaoService.obter_cadeia_dominial_origem(
            documento_existente
        )

        # Serializar documento para dict
        documento_dict = {
            'id': documento_existente.id,  # Include ID to avoid MultipleObjectsReturned
            'numero': documento_existente.numero,
            'imovel': {
                'id': documento_existente.imovel.id,
                'matricula': documento_existente.imovel.matricula
            }
        }

        return {
            'existe': True,
            'documento': documento_dict,
            'documentos_importaveis': documentos_importaveis,
            'cadeia_dominial': cadeia_dominial
        }
    
    @staticmethod
    def calcular_documentos_importaveis(documento_origem: Documento) -> List[Documento]:
        """
        Calcula quais documentos podem ser importados a partir de um documento origem.
        Busca recursivamente toda a cadeia dominial (documentos que são origem deste documento).
        
        Args:
            documento_origem: Documento de origem para calcular importáveis
            
        Returns:
            Lista de documentos que podem ser importados (incluindo toda a cadeia dominial)
        """
        documentos_importaveis = []
        documentos_processados = set()  # Para evitar loops infinitos
        
        def buscar_cadeia_recursiva(documento):
            if documento.id in documentos_processados:
                return
            
            documentos_processados.add(documento.id)
            
            # Buscar lançamentos deste documento para encontrar suas origens
            from ..models import Lancamento
            
            lancamentos_do_documento = Lancamento.objects.filter(
                documento=documento
            )
            
            for lancamento in lancamentos_do_documento:
                logger.debug(f" CADEIA: Lançamento {lancamento.id} - Origem: '{lancamento.origem}' - Cartório Origem: {lancamento.cartorio_origem}")
                
                if lancamento.origem:
                    # Separar múltiplas origens (separadas por ;)
                    origens = [o.strip() for o in lancamento.origem.split(';')]
                    logger.debug(f" CADEIA: Origens separadas: {origens}")
                    
                    for origem_numero in origens:
                        if origem_numero:
                            logger.debug(f" CADEIA: Buscando documento {origem_numero} no cartório {lancamento.cartorio_origem}")
                            
                            # Buscar documento com este número (independente do cartório)
                            documento_anterior = Documento.objects.filter(
                                numero=origem_numero
                            ).first()
                            
                            if documento_anterior:
                                logger.debug(f" CADEIA: Documento encontrado: {documento_anterior.numero} - {documento_anterior.imovel.nome}")

                                # Verificar se já não foi importado (de qualquer propriedade)
                                # Alinhado com ImportacaoCadeiaService: verifica apenas pelo documento
                                if not DocumentoImportado.objects.filter(
                                    documento=documento_anterior
                                ).exists():

                                    documentos_importaveis.append(documento_anterior)
                                    logger.debug(f" CADEIA: Documento adicionado à lista de importáveis")

                                    # Buscar recursivamente as origens deste documento
                                    buscar_cadeia_recursiva(documento_anterior)
                                else:
                                    logger.debug(f" CADEIA: Documento já foi importado")
                            else:
                                logger.debug(f" CADEIA: Documento {origem_numero} não encontrado no cartório {lancamento.cartorio_origem}")
        
        # Iniciar busca recursiva a partir do documento origem
        buscar_cadeia_recursiva(documento_origem)
        
        return documentos_importaveis
    
    @staticmethod
    def obter_cadeia_dominial_origem(documento_origem: Documento) -> Dict[str, Any]:
        """
        Obtém informações completas da cadeia dominial de um documento origem.
        Busca recursivamente todos os documentos da cadeia.

        Args:
            documento_origem: Documento de origem

        Returns:
            Dict com informações da cadeia dominial completa
        """
        cadeia_documentos = []
        documentos_processados = set()  # Para evitar loops infinitos

        def adicionar_documento_e_origens(documento):
            if documento.id in documentos_processados:
                return

            documentos_processados.add(documento.id)

            # Adicionar o documento atual
            cadeia_documentos.append({
                'documento': documento,
                'lancamentos': list(documento.lancamentos.all())
            })

            # Buscar origens deste documento
            lancamentos_do_documento = Lancamento.objects.filter(
                documento=documento
            )

            for lancamento in lancamentos_do_documento:
                if lancamento.origem:
                    # Separar múltiplas origens
                    origens = [o.strip() for o in lancamento.origem.split(';')]

                    for origem_numero in origens:
                        if origem_numero:
                            # Buscar documento com este número
                            documento_anterior = Documento.objects.filter(
                                numero=origem_numero
                            ).first()

                            if documento_anterior and documento_anterior.id not in documentos_processados:
                                # Recursivamente adicionar o documento anterior
                                adicionar_documento_e_origens(documento_anterior)

        # Iniciar a busca recursiva
        adicionar_documento_e_origens(documento_origem)

        # Retornar dict com documento_origem e total_documentos
        return {
            'documento_origem': {
                'numero': documento_origem.numero,
                'id': documento_origem.id
            },
            'total_documentos': len(cadeia_documentos),
            'documentos': cadeia_documentos
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