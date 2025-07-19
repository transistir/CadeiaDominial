"""
Service para verificação de duplicatas de origem/cartório.
Detecta quando uma origem/cartório já existe em outras cadeias dominiais.
"""

from django.conf import settings
from django.db.models import Q
from typing import Dict, List, Optional, Any
from ..models import Documento, DocumentoImportado, Lancamento


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
            return {'tem_duplicata': False}
        
        # Buscar documento com mesmo número e cartório em outros imóveis
        documento_existente = Documento.objects.filter(
            numero=origem,
            cartorio_id=cartorio_id
        ).exclude(
            imovel_id=imovel_atual_id
        ).select_related('imovel', 'cartorio', 'tipo').first()
        
        if not documento_existente:
            return {'tem_duplicata': False}
        
        # Calcular documentos importáveis
        documentos_importaveis = DuplicataVerificacaoService.calcular_documentos_importaveis(
            documento_existente
        )
        
        # Obter cadeia dominial
        cadeia_dominial = DuplicataVerificacaoService.obter_cadeia_dominial_origem(
            documento_existente
        )
        
        return {
            'tem_duplicata': True,
            'documento_origem': documento_existente,
            'documentos_importaveis': documentos_importaveis,
            'cadeia_dominial': cadeia_dominial
        }
    
    @staticmethod
    def calcular_documentos_importaveis(documento_origem: Documento) -> List[Documento]:
        """
        Calcula quais documentos podem ser importados a partir de um documento origem.
        Busca documentos que são origem deste documento (cadeia dominial anterior).
        
        Args:
            documento_origem: Documento de origem para calcular importáveis
            
        Returns:
            Lista de documentos que podem ser importados
        """
        documentos_importaveis = []
        
        # Buscar lançamentos deste documento para encontrar suas origens
        from ..models import Lancamento
        
        lancamentos_do_documento = Lancamento.objects.filter(
            documento=documento_origem
        )
        
        for lancamento in lancamentos_do_documento:
            print(f"DEBUG CADEIA: Lançamento {lancamento.id} - Origem: '{lancamento.origem}' - Cartório Origem: {lancamento.cartorio_origem}")
            
            if lancamento.origem:
                # Separar múltiplas origens (separadas por ;)
                origens = [o.strip() for o in lancamento.origem.split(';')]
                print(f"DEBUG CADEIA: Origens separadas: {origens}")
                
                for origem_numero in origens:
                    if origem_numero:
                        print(f"DEBUG CADEIA: Buscando documento {origem_numero} no cartório {lancamento.cartorio_origem}")
                        
                        # Buscar documento com este número (independente do cartório)
                        documento_anterior = Documento.objects.filter(
                            numero=origem_numero
                        ).first()
                        
                        if documento_anterior:
                            print(f"DEBUG CADEIA: Documento encontrado: {documento_anterior.numero} - {documento_anterior.imovel.nome}")
                            
                            # Verificar se já não foi importado
                            if not DocumentoImportado.objects.filter(
                                documento=documento_anterior,
                                imovel_origem=documento_origem.imovel
                            ).exists():
                                
                                documentos_importaveis.append(documento_anterior)
                                print(f"DEBUG CADEIA: Documento adicionado à lista de importáveis")
                            else:
                                print(f"DEBUG CADEIA: Documento já foi importado")
                        else:
                            print(f"DEBUG CADEIA: Documento {origem_numero} não encontrado no cartório {lancamento.cartorio_origem}")
        
        return documentos_importaveis
    
    @staticmethod
    def obter_cadeia_dominial_origem(documento_origem: Documento) -> List[Dict[str, Any]]:
        """
        Obtém informações completas da cadeia dominial de um documento origem.
        Busca recursivamente todos os documentos da cadeia.
        
        Args:
            documento_origem: Documento de origem
            
        Returns:
            Lista com informações da cadeia dominial completa
        """
        cadeia = []
        documentos_processados = set()  # Para evitar loops infinitos
        
        def adicionar_documento_e_origens(documento):
            if documento.id in documentos_processados:
                return
            
            documentos_processados.add(documento.id)
            
            # Adicionar o documento atual
            cadeia.append({
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
        
        return cadeia
    
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