"""
Service para verificação de duplicatas de origem/cartório.
Detecta quando uma origem/cartório já existe em outras cadeias dominiais.
"""

from django.conf import settings
from django.db.models import Q
from typing import Dict, List, Optional, Any
from ..models import Documento, DocumentoImportado, Lancamento
from .documento_identidade_service import DocumentoIdentidadeService
from ..utils.documento_identidade_utils import DocumentoIdentidade


class DuplicataVerificacaoService:
    """
    Service responsável por verificar duplicatas de origem/cartório
    e calcular documentos importáveis.
    """

    @staticmethod
    def _tipo_do_codigo(codigo):
        """Deduz o tipo documental (matricula/transcricao) do prefixo M/T de um código."""
        if not codigo:
            return None
        primeiro = codigo.strip()[:1].upper()
        if primeiro == 'M':
            return 'matricula'
        if primeiro == 'T':
            return 'transcricao'
        return None

    @staticmethod
    def _resolver_documento(codigo, cartorio_id):
        """
        Resolve um documento pela identidade completa (tipo, número normalizado
        e cartório), nunca por número isolado. Sem cartório, com tipo
        incompatível ou com identidade ambígua, não seleciona nenhum documento.
        """
        if not codigo or not cartorio_id:
            return None
        tipo = DuplicataVerificacaoService._tipo_do_codigo(codigo)
        if not tipo:
            return None
        try:
            identidade = DocumentoIdentidade(tipo, codigo, cartorio_id)
        except (TypeError, ValueError):
            return None
        resultado = DocumentoIdentidadeService.resolver(identidade)
        return resultado.documento if resultado.status == 'encontrado' else None

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

        # Resolver documento pela identidade completa (tipo, número e cartório)
        documento_existente = DuplicataVerificacaoService._resolver_documento(origem, cartorio_id)

        if not documento_existente or documento_existente.imovel_id == imovel_atual_id:
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

            lancamentos_do_documento = Lancamento.objects.filter(
                documento=documento
            )

            for lancamento in lancamentos_do_documento:
                if lancamento.origem:
                    # Separar múltiplas origens (separadas por ;)
                    origens = [o.strip() for o in lancamento.origem.split(';') if o.strip()]

                    for origem_numero in origens:
                        # Resolver documento de origem pela identidade completa
                        # (tipo, número normalizado e cartório do lançamento)
                        documento_anterior = DuplicataVerificacaoService._resolver_documento(
                            origem_numero, lancamento.cartorio_origem_id
                        )

                        if documento_anterior:
                            # Verificar se já não foi importado
                            if not DocumentoImportado.objects.filter(
                                documento=documento_anterior,
                                imovel_origem=documento_origem.imovel
                            ).exists():
                                documentos_importaveis.append(documento_anterior)
                                # Buscar recursivamente as origens deste documento
                                buscar_cadeia_recursiva(documento_anterior)
        
        # Iniciar busca recursiva a partir do documento origem
        buscar_cadeia_recursiva(documento_origem)
        
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
                    origens = [o.strip() for o in lancamento.origem.split(';') if o.strip()]

                    for origem_numero in origens:
                        # Resolver documento de origem pela identidade completa
                        documento_anterior = DuplicataVerificacaoService._resolver_documento(
                            origem_numero, lancamento.cartorio_origem_id
                        )

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