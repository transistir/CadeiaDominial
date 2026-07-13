"""
Service especializado para processamento de origens na hierarquia
"""

from ..models import Documento, Lancamento, Cartorios, DocumentoTipo
from ..utils.hierarquia_utils import processar_origens_para_documentos
from ..utils.documento_identidade_utils import DocumentoIdentidade
from .documento_identidade_service import DocumentoIdentidadeService
from .cache_service import CacheService
from .cri_service import CRIService
from datetime import date


class HierarquiaOrigemService:
    """
    Service para processar origens identificadas de lançamentos
    """
    
    @staticmethod
    def processar_origens_identificadas(imovel, criar_documentos_automaticos=False):
        """
        Processa origens identificadas de lançamentos que ainda não foram convertidas em documentos
        
        Args:
            imovel: Objeto Imovel
            criar_documentos_automaticos: Se True, cria documentos automaticamente para origens identificadas
        """
        origens_identificadas = []
        origens_processadas = set()  # Para evitar duplicação
        
        # Otimização: usar select_related para reduzir queries
        lancamentos_com_origem = Lancamento.objects.filter(
            documento__imovel=imovel,
            origem__isnull=False
        ).exclude(origem='')\
         .select_related('documento', 'documento__cartorio', 'documento__tipo')
        
        for lancamento in lancamentos_com_origem:
            if lancamento.origem:
                origens_processadas_info = processar_origens_para_documentos(lancamento.origem, imovel, lancamento)
                
                for origem_info in origens_processadas_info:
                    # Verificar se esta origem já foi processada (a chave inclui
                    # o cartório, já que a identidade nunca é só tipo+número)
                    cartorio_da_origem = lancamento.cartorio_origem or lancamento.documento.cartorio
                    chave_origem = (
                        f"{origem_info['numero']}_{origem_info['tipo']}_"
                        f"{cartorio_da_origem.id if cartorio_da_origem else ''}"
                    )
                    if chave_origem not in origens_processadas:
                        origem_identificada = HierarquiaOrigemService._processar_origem_individual(
                            imovel, lancamento, origem_info, criar_documentos_automaticos
                        )
                        if origem_identificada:
                            origens_identificadas.append(origem_identificada)
                            origens_processadas.add(chave_origem)
        
        return origens_identificadas
    
    @staticmethod
    def _resolver_documento(tipo, numero, cartorio):
        """
        Resolve um documento pela identidade completa (tipo, número
        normalizado e cartório), nunca por número isolado. Identidades
        ambíguas não são escolhidas.
        """
        if not cartorio:
            return None
        try:
            identidade = DocumentoIdentidade(tipo, numero, cartorio.pk)
        except (TypeError, ValueError):
            return None
        resultado = DocumentoIdentidadeService.resolver(identidade)
        return resultado.documento if resultado.status == 'encontrado' else None

    @staticmethod
    def _processar_origem_individual(imovel, lancamento, origem_info, criar_documentos_automaticos=False):
        """
        Processa uma origem individual
        Implementa a regra dos CRI: verifica se existe documento com CRI da origem
        """
        # O cartório da origem vem de lancamento.cartorio_origem quando
        # informado; só cai para o cartório do documento atual na ausência dele.
        cartorio_origem = lancamento.cartorio_origem or lancamento.documento.cartorio
        documento_existente = HierarquiaOrigemService._resolver_documento(
            origem_info['tipo'], origem_info['numero'], cartorio_origem
        )

        if not documento_existente:
            if criar_documentos_automaticos:
                # Criar o documento automaticamente com CRI da origem
                return HierarquiaOrigemService._criar_documento_automatico(
                    imovel, lancamento, origem_info
                )
            else:
                # Apenas listar como origem identificada sem criar documento
                return HierarquiaOrigemService._criar_origem_identificada(
                    lancamento, origem_info, None, False
                )
        else:
            # Documento já existe com CRI da origem, adicionar como origem identificada criada
            return HierarquiaOrigemService._criar_origem_existente(
                lancamento, origem_info, documento_existente
            )
    
    @staticmethod
    def _criar_documento_automatico(imovel, lancamento, origem_info):
        """
        Cria um documento automaticamente a partir de uma origem
        Implementa a regra dos CRI: documento criado automaticamente herda o CRI da origem
        """
        try:
            tipo_doc = DocumentoTipo.objects.get(tipo=origem_info['tipo'])

            # REGRA DOS CRI: o cartório vem de lancamento.cartorio_origem
            # quando informado; só cai para o cartório do documento atual na
            # ausência dele.
            cartorio_origem = lancamento.cartorio_origem or lancamento.documento.cartorio

            # Verificar se já existe um documento com esta identidade completa
            documento_existente = HierarquiaOrigemService._resolver_documento(
                origem_info['tipo'], origem_info['numero'], cartorio_origem
            )

            if documento_existente:
                # Se já existe, retornar como origem identificada criada
                return HierarquiaOrigemService._criar_origem_identificada(
                    lancamento, origem_info, documento_existente.id, True
                )
            
            # Criar documento usando CRIService
            dados_documento = {
                'imovel': imovel,
                'tipo': tipo_doc,
                'numero': origem_info['numero'],
                'data': date.today(),
                'cartorio': cartorio_origem,  # CRI da origem
                'livro': '0',  # Valor padrão, será atualizado pelo primeiro lançamento
                'folha': '0',  # Valor padrão, será atualizado pelo primeiro lançamento
                'origem': f'Criado automaticamente a partir de origem: {origem_info["numero"]}',
                'observacoes': f'Documento criado automaticamente ao identificar origem "{origem_info["numero"]}" no lançamento {lancamento.numero_lancamento}'
            }
            
            documento_criado = CRIService.criar_documento_com_cri(
                imovel, dados_documento, cri_origem=cartorio_origem
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