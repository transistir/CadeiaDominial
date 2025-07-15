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
        CORREÇÃO: Processa múltiplas origens com seus respectivos cartórios
        """
        if not origem:
            return None
        
        # Processar origens identificadas
        origens_processadas = processar_origens_para_documentos(origem, imovel, lancamento)
        
        if not origens_processadas:
            return None
        
        # CORREÇÃO: Processar múltiplas origens com seus respectivos cartórios
        # Extrair origens individuais do texto concatenado
        origens_individuals = [o.strip() for o in origem.split(';') if o.strip()]
        
        # Se há múltiplas origens, processar cada uma com seu cartório específico
        if len(origens_individuals) > 1:
            return LancamentoOrigemService._processar_multiplas_origens(
                lancamento, origens_individuals, imovel
            )
        else:
            # Processamento original para uma única origem
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
    def _processar_multiplas_origens(lancamento, origens_individuals, imovel):
        """
        Processa múltiplas origens com seus respectivos cartórios
        """
        documentos_criados = []
        
        # Para cada origem individual, criar documento com cartório específico
        for origem_individual in origens_individuals:
            # Processar origem individual para extrair informações
            origens_processadas = processar_origens_para_documentos(origem_individual, imovel, lancamento)
            
            for origem_info in origens_processadas:
                # Buscar cartório específico para esta origem
                cartorio_origem = LancamentoOrigemService._buscar_cartorio_origem(
                    lancamento, origem_individual
                )
                
                documento_criado = LancamentoOrigemService._criar_documento_automatico_com_cartorio(
                    imovel, lancamento, origem_info, cartorio_origem
                )
                if documento_criado:
                    documentos_criados.append(documento_criado)
        
        if documentos_criados:
            return f'Foram criados {len(documentos_criados)} documento(s) automaticamente a partir das múltiplas origens identificadas.'
        
        return f'Foram identificadas {len(origens_individuals)} origem(ns) para criação automática de documentos.'
    
    @staticmethod
    def _buscar_cartorio_origem(lancamento, origem_individual):
        """
        Busca o cartório específico para uma origem individual
        Extrai do cache temporário ou usa fallback
        """
        from django.core.cache import cache
        
        # Tentar buscar mapeamento do cache
        cache_key = f"mapeamento_origens_lancamento_{lancamento.id}"
        mapeamento = cache.get(cache_key)
        
        if mapeamento:
            # Buscar cartório específico para esta origem
            for item in mapeamento:
                if item['origem'] == origem_individual:
                    # Buscar cartório pelo ID
                    try:
                        cartorio = Cartorios.objects.get(id=item['cartorio_id'])
                        return cartorio
                    except Cartorios.DoesNotExist:
                        # Fallback: buscar por nome
                        try:
                            cartorio = Cartorios.objects.get(nome__iexact=item['cartorio_nome'])
                            return cartorio
                        except Cartorios.DoesNotExist:
                            pass
        
        # Fallback: usar cartório de origem do lançamento
        if lancamento.cartorio_origem:
            return lancamento.cartorio_origem
        else:
            return lancamento.documento.cartorio
    
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
            
            # VERIFICAR SE É EDIÇÃO DE CARTÓRIO OU NOVA ORIGEM
            # Buscar documento existente com o mesmo número (independente do cartório)
            documento_existente_mesmo_numero = Documento.objects.filter(
                numero=origem_info['numero'],
                imovel=imovel
            ).first()
            
            if documento_existente_mesmo_numero:
                # Existe um documento com o mesmo número
                if documento_existente_mesmo_numero.cartorio == cartorio_origem:
                    # Mesmo cartório, documento já existe
                    return None
                else:
                    # Cartório diferente - POSSÍVEL EDIÇÃO DE CARTÓRIO
                    # Verificar se é uma edição válida (não é criação de nova origem)
                    if LancamentoOrigemService._is_edicao_cartorio_valida(
                        documento_existente_mesmo_numero, cartorio_origem, lancamento
                    ):
                        # É uma edição de cartório válida - atualizar o documento existente
                        return LancamentoOrigemService._atualizar_cartorio_documento(
                            documento_existente_mesmo_numero, cartorio_origem, lancamento
                        )
                    else:
                        # É uma nova origem com cartório diferente - criar novo documento
                        pass
            
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
    
    @staticmethod
    def _criar_documento_automatico_com_cartorio(imovel, lancamento, origem_info, cartorio_origem):
        """
        Cria um documento automaticamente a partir de uma origem com cartório específico
        """
        try:
            # Obter tipo de documento
            tipo_doc = DocumentoTipo.objects.get(tipo=origem_info['tipo'])
            
            # DETERMINAR LIVRO E FOLHA: Herdar do primeiro lançamento do documento criado pela origem
            livro_origem = None
            folha_origem = None
            
            # Buscar o primeiro lançamento do documento que foi criado pela origem
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
            
            # VERIFICAR SE É EDIÇÃO DE CARTÓRIO OU NOVA ORIGEM
            # Buscar documento existente com o mesmo número (independente do cartório)
            documento_existente_mesmo_numero = Documento.objects.filter(
                numero=origem_info['numero'],
                imovel=imovel
            ).first()
            
            if documento_existente_mesmo_numero:
                # Existe um documento com o mesmo número
                if documento_existente_mesmo_numero.cartorio == cartorio_origem:
                    # Mesmo cartório, documento já existe
                    return None
                else:
                    # Cartório diferente - POSSÍVEL EDIÇÃO DE CARTÓRIO
                    # Verificar se é uma edição válida (não é criação de nova origem)
                    if LancamentoOrigemService._is_edicao_cartorio_valida(
                        documento_existente_mesmo_numero, cartorio_origem, lancamento
                    ):
                        # É uma edição de cartório válida - atualizar o documento existente
                        return LancamentoOrigemService._atualizar_cartorio_documento(
                            documento_existente_mesmo_numero, cartorio_origem, lancamento
                        )
                    else:
                        # É uma nova origem com cartório diferente - criar novo documento
                        pass
            
            # Verificar se já existe um documento com esse número e cartório
            documento_existente = Documento.objects.filter(
                numero=origem_info['numero'], 
                cartorio=cartorio_origem
            ).first()
            
            if documento_existente:
                # Documento já existe, não criar novamente
                return None
            
            # Criar documento com cartório específico da origem
            dados_documento = {
                'imovel': imovel,
                'tipo': tipo_doc,
                'numero': origem_info['numero'],
                'data': date.today(),
                'cartorio': cartorio_origem,  # CARTÓRIO ESPECÍFICO DA ORIGEM
                'livro': livro_origem if livro_origem else '0',  # LIVRO HERDADO DA ORIGEM
                'folha': folha_origem if folha_origem else '0',  # FOLHA HERDADA DA ORIGEM
                'origem': f'Criado automaticamente a partir de origem: {origem_info["numero"]}',
                'observacoes': f'Documento criado automaticamente ao identificar origem "{origem_info["numero"]}" no lançamento {lancamento.numero_lancamento}. Cartório da origem: {cartorio_origem.nome}. Livro: {livro_origem or "não informado"}, Folha: {folha_origem or "não informada"}'
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
    
    @staticmethod
    def _is_edicao_cartorio_valida(documento_existente, novo_cartorio, lancamento):
        """
        Verifica se a mudança de cartório é uma edição válida
        Regras:
        1. O documento existente não pode ter lançamentos
        2. O novo cartório deve ser diferente do atual
        3. O lançamento deve ser do tipo 'inicio_matricula' (primeiro lançamento)
        """
        # Verificar se o documento não tem lançamentos
        if documento_existente.lancamentos.exists():
            return False
        
        # Verificar se o cartório é realmente diferente
        if documento_existente.cartorio == novo_cartorio:
            return False
        
        # Verificar se é o primeiro lançamento (início de matrícula)
        if lancamento.tipo.tipo != 'inicio_matricula':
            return False
        
        return True
    
    @staticmethod
    def _atualizar_cartorio_documento(documento, novo_cartorio, lancamento):
        """
        Atualiza o cartório de um documento existente
        """
        try:
            # Atualizar o cartório do documento
            documento.cartorio = novo_cartorio
            documento.observacoes = f"{documento.observacoes or ''}\n[EDITADO] Cartório atualizado para {novo_cartorio.nome} em {date.today()}"
            documento.save()
            
            # Invalidar cache do imóvel
            CacheService.invalidate_documentos_imovel(documento.imovel.id)
            CacheService.invalidate_tronco_principal(documento.imovel.id)
            
            print(f"Documento {documento.numero} atualizado: cartório alterado de {documento.cartorio} para {novo_cartorio.nome}")
            
            return documento
            
        except Exception as e:
            print(f"Erro ao atualizar cartório do documento: {e}")
            return None 