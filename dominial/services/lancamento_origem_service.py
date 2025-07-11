"""
Service para processamento de origens automáticas dos lançamentos
"""
from ..utils.hierarquia_utils import processar_origens_para_documentos
from ..models import Documento, DocumentoTipo, Cartorios, Lancamento
from ..services.cri_service import CRIService
from ..services.cache_service import CacheService
from datetime import date
import uuid

class LancamentoOrigemService:
    @staticmethod
    def processar_origens_automaticas(lancamento, origem, imovel):
        """
        Processa origens para criar documentos automáticos
        IMPLEMENTAÇÃO CORRETA: Usa o cartório de origem do lançamento para criar documentos
        """
        if not origem:
            return None
        
        # Processar origens identificadas
        origens_processadas = processar_origens_para_documentos(origem, imovel, lancamento)
        
        if not origens_processadas:
            return None
        
        # Criar documentos automáticos usando o cartório de origem do lançamento
        documentos_criados = []
        
        for origem_info in origens_processadas:
            documento_criado = LancamentoOrigemService._criar_documento_automatico(
                imovel, lancamento, origem_info
            )
            if documento_criado:
                documentos_criados.append(documento_criado)
        
        if documentos_criados:
            return f'Foram criados {len(documentos_criados)} documento(s) automaticamente a partir das origens identificadas.'
        
        return f'Foram identificadas {len(origens_processadas)} origem(ns) para criação automática de documentos.'
    
    @staticmethod
    def _criar_documento_automatico(imovel, lancamento, origem_info):
        """
        Cria um documento automaticamente a partir de uma origem
        CORREÇÃO: Usa o cartório de origem do lançamento (lancamento.cartorio_origem)
        HERANÇA: Livro e folha são herdados do primeiro lançamento do documento criado pela origem
        """
        try:
            # Obter tipo de documento
            tipo_doc = DocumentoTipo.objects.get(tipo=origem_info['tipo'])
            
            # DETERMINAR CARTÓRIO: Usar o cartório de origem do lançamento
            cartorio_origem = None
            
            # Se o lançamento tem cartório de origem definido, usar ele
            if lancamento.cartorio_origem:
                cartorio_origem = lancamento.cartorio_origem
            else:
                # Fallback: usar cartório do documento atual
                cartorio_origem = lancamento.documento.cartorio
            
            # DETERMINAR LIVRO E FOLHA: Herdar do primeiro lançamento do documento criado pela origem
            livro_origem = None
            folha_origem = None
            
            # Buscar o primeiro lançamento do documento que foi criado pela origem
            # Este documento terá o cartório da origem e será usado para herdar livro e folha
            documento_origem = Documento.objects.filter(
                numero=origem_info['numero'],
                cartorio=cartorio_origem
            ).first()
            
            if documento_origem:
                # Buscar o primeiro lançamento deste documento para herdar livro e folha
                primeiro_lancamento_origem = Lancamento.objects.filter(
                    documento=documento_origem
                ).order_by('id').first()
                
                if primeiro_lancamento_origem:
                    # Herdar livro e folha do primeiro lançamento da origem
                    if primeiro_lancamento_origem.livro_origem and primeiro_lancamento_origem.livro_origem.strip():
                        livro_origem = primeiro_lancamento_origem.livro_origem.strip()
                    if primeiro_lancamento_origem.folha_origem and primeiro_lancamento_origem.folha_origem.strip():
                        folha_origem = primeiro_lancamento_origem.folha_origem.strip()
            
            # Se não encontrou livro e folha da origem, usar os campos do lançamento atual
            if not livro_origem and lancamento.livro_origem and lancamento.livro_origem.strip():
                livro_origem = lancamento.livro_origem.strip()
            if not folha_origem and lancamento.folha_origem and lancamento.folha_origem.strip():
                folha_origem = lancamento.folha_origem.strip()
            
            # Verificar se já existe um documento com esse número e cartório
            documento_existente = Documento.objects.filter(
                numero=origem_info['numero'], 
                cartorio=cartorio_origem
            ).first()
            
            if documento_existente:
                # Documento já existe, não criar novamente
                return None
            
            # Criar documento com cartório da origem
            dados_documento = {
                'imovel': imovel,
                'tipo': tipo_doc,
                'numero': origem_info['numero'],
                'data': date.today(),
                'cartorio': cartorio_origem,  # CARTÓRIO DA ORIGEM
                'livro': livro_origem if livro_origem else '0',  # LIVRO HERDADO DA ORIGEM
                'folha': folha_origem if folha_origem else '0',  # FOLHA HERDADA DA ORIGEM
                'origem': f'Criado automaticamente a partir de origem: {origem_info["numero"]}',
                'observacoes': f'Documento criado automaticamente ao identificar origem "{origem_info["numero"]}" no lançamento {lancamento.numero_lancamento}. Cartório herdado da origem: {cartorio_origem.nome}. Livro: {livro_origem or "não informado"}, Folha: {folha_origem or "não informada"}'
            }
            
            # Criar documento usando CRIService com CRI da origem
            documento_criado = CRIService.criar_documento_com_cri(
                imovel, dados_documento, cri_origem=cartorio_origem
            )
            
            # Invalidar cache do imóvel
            CacheService.invalidate_documentos_imovel(imovel.id)
            CacheService.invalidate_tronco_principal(imovel.id)
            
            return documento_criado
            
        except DocumentoTipo.DoesNotExist:
            # Se o tipo não existir, não criar documento
            return None
        except Exception as e:
            # Log do erro mas não falhar o processo
            print(f"Erro ao criar documento automático: {e}")
            return None 