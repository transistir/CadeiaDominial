"""
Service consolidado para operações de lançamento
Consolida funcionalidades de múltiplos services menores em um único service coeso
"""

from ..models import Lancamento, LancamentoTipo, Documento, Pessoas, Cartorios
from .lancamento_criacao_service import LancamentoCriacaoService
from .lancamento_form_service import LancamentoFormService
from .lancamento_validacao_service import LancamentoValidacaoService
from .lancamento_documento_service import LancamentoDocumentoService
from .lancamento_origem_service import LancamentoOrigemService
from .lancamento_consulta_service import LancamentoConsultaService
from .lancamento_campos_service import LancamentoCamposService
from .lancamento_duplicata_service import LancamentoDuplicataService


class LancamentoService:
    """
    Service consolidado para operações de lançamento
    Agrupa funcionalidades relacionadas em um único service coeso
    """
    
    # ==================== DOCUMENTOS ====================
    
    @staticmethod
    def obter_documento_ativo(imovel, documento_id=None):
        """
        Obtém o documento ativo do imóvel
        """
        return LancamentoDocumentoService.obter_documento_ativo(imovel, documento_id)
    
    @staticmethod
    def criar_documento_matricula_automatico(imovel):
        """
        Cria automaticamente um documento de matrícula para o imóvel
        """
        return LancamentoDocumentoService.criar_documento_matricula_automatico(imovel)
    
    # ==================== TIPOS DE LANÇAMENTO ====================
    
    @staticmethod
    def obter_tipos_lancamento_por_documento(documento):
        """
        Obtém os tipos de lançamento disponíveis baseado no tipo do documento
        """
        if documento.tipo.tipo == 'matricula':
            return LancamentoTipo.objects.filter(
                tipo__in=['averbacao', 'registro', 'inicio_matricula']
            ).order_by('tipo')
        elif documento.tipo.tipo == 'transcricao':
            return LancamentoTipo.objects.filter(
                tipo__in=['averbacao', 'inicio_matricula']
            ).order_by('tipo')
        else:
            return LancamentoTipo.objects.all().order_by('tipo')
    
    # ==================== VALIDAÇÕES ====================
    
    @staticmethod
    def validar_numero_lancamento(numero_lancamento, documento, lancamento_id=None):
        """
        Valida se o número do lançamento é válido e único
        """
        if not numero_lancamento or not numero_lancamento.strip():
            return False, 'O número do lançamento é obrigatório.'
        
        lancamento_existente = Lancamento.objects.filter(
            documento=documento,
            numero_lancamento=numero_lancamento.strip()
        )
        
        # Se é uma edição, excluir o próprio registro da verificação
        if lancamento_id:
            lancamento_existente = lancamento_existente.exclude(pk=lancamento_id)
        
        if lancamento_existente.exists():
            return False, f'Já existe um lançamento com o número "{numero_lancamento.strip()}" neste documento.'
        
        return True, None
    
    @staticmethod
    def validar_dados_lancamento(dados_lancamento):
        """
        Valida dados básicos do lançamento
        """
        return LancamentoValidacaoService.validar_dados_lancamento(dados_lancamento)
    
    @staticmethod
    def validar_pessoas_lancamento(pessoas_data, pessoas_ids, pessoas_percentuais):
        """
        Valida pessoas e percentuais do lançamento
        """
        return LancamentoValidacaoService.validar_pessoas_lancamento(pessoas_data, pessoas_ids, pessoas_percentuais)
    
    # ==================== PESSOAS ====================
    
    @staticmethod
    def processar_pessoas_lancamento(lancamento, pessoas_data, pessoas_ids, tipo_pessoa):
        """
        Processa pessoas do lançamento
        """
        for i, nome in enumerate(pessoas_data):
            if nome and nome.strip():
                nome_clean = nome.strip()
                pessoa_id = pessoas_ids[i] if i < len(pessoas_ids) and pessoas_ids[i] else None
                
                if pessoa_id and pessoa_id.strip():
                    # Se foi selecionada uma pessoa existente via autocomplete
                    try:
                        pessoa = Pessoas.objects.get(id=pessoa_id)
                        # Atualizar nome se foi alterado
                        if pessoa.nome != nome_clean:
                            pessoa.nome = nome_clean
                            pessoa.save()
                    except Pessoas.DoesNotExist:
                        # Se o ID não existe, procurar por nome ou criar nova
                        pessoa = Pessoas.objects.filter(nome__iexact=nome_clean).first()
                        if not pessoa:
                            pessoa = Pessoas.objects.create(nome=nome_clean)
                else:
                    # Se não foi selecionada pessoa existente, procurar por nome ou criar nova
                    pessoa = Pessoas.objects.filter(nome__iexact=nome_clean).first()
                    if not pessoa:
                        pessoa = Pessoas.objects.create(nome=nome_clean)
                
                # Usar lancamento.pessoas.create() em vez de lancamentopessoa_set.create()
                lancamento.pessoas.create(
                    pessoa=pessoa,
                    tipo=tipo_pessoa,
                    nome_digitado=nome_clean if not pessoa_id else None
                )
    
    # ==================== CARTÓRIOS ====================
    
    @staticmethod
    def processar_cartorio_origem(request, tipo_lanc, lancamento):
        """
        Processa o cartório de origem do lançamento
        O cartório da matrícula atual já está no documento, não precisa salvar no lançamento
        """
        # O cartório da matrícula atual já está no documento.lancamento.cartorio
        # Não precisamos salvar no campo cartorio_origem do lançamento
        # O campo cartorio_origem é específico para origem (início de matrícula)
        # O campo cartorio_transacao é específico para transação
        pass
    
    # ==================== FORMULÁRIOS ====================
    
    @staticmethod
    def processar_dados_lancamento(request, tipo_lanc):
        """
        Processa os dados do formulário de lançamento
        """
        return LancamentoFormService.processar_dados_lancamento(request, tipo_lanc)
    
    # ==================== CRIAÇÃO E ATUALIZAÇÃO ====================
    
    @staticmethod
    def criar_lancamento(documento_ativo, dados_lancamento, tipo_lanc):
        """
        Cria um novo lançamento
        """
        return LancamentoCriacaoService._criar_lancamento_basico(documento_ativo, dados_lancamento, tipo_lanc)
    
    @staticmethod
    def criar_lancamento_completo(request, tis, imovel, documento_ativo):
        """
        Cria um lançamento completo com todas as validações e processamentos
        """
        return LancamentoCriacaoService.criar_lancamento_completo(request, tis, imovel, documento_ativo)
    
    @staticmethod
    def atualizar_lancamento_completo(request, lancamento, imovel):
        """
        Atualiza um lançamento completo com todas as validações e processamentos
        """
        return LancamentoCriacaoService.atualizar_lancamento_completo(request, lancamento, imovel)
    
    # ==================== ORIGENS ====================
    
    @staticmethod
    def processar_origens_automaticas(lancamento, origem, imovel):
        """
        Processa origens para criar documentos automáticos
        """
        return LancamentoOrigemService.processar_origens_automaticas(lancamento, origem, imovel)
    
    # ==================== CONSULTAS ====================
    
    @staticmethod
    def filtrar_lancamentos(filtros=None, pagina=None, itens_por_pagina=10):
        """
        Filtra lançamentos com paginação
        """
        return LancamentoConsultaService.filtrar_lancamentos(filtros, pagina, itens_por_pagina)
    
    @staticmethod
    def obter_lancamentos_por_documento(documento, ordenacao='id'):
        """
        Obtém lançamentos de um documento específico
        """
        return LancamentoConsultaService.obter_lancamentos_por_documento(documento, ordenacao)
    
    @staticmethod
    def obter_estatisticas_lancamentos():
        """
        Obtém estatísticas gerais dos lançamentos
        """
        return LancamentoConsultaService.obter_estatisticas_lancamentos()
    
    # ==================== CAMPOS ====================
    
    @staticmethod
    def processar_campos_lancamento(request, tipo_lanc, lancamento):
        """
        Processa campos específicos do lançamento
        """
        return LancamentoCamposService.processar_campos_lancamento(request, tipo_lanc, lancamento)
    
    # ==================== DUPLICATAS ====================
    
    @staticmethod
    def verificar_duplicata_lancamento(lancamento):
        """
        Verifica se o lançamento é duplicata
        """
        return LancamentoDuplicataService.verificar_duplicata_lancamento(lancamento)
    
    @staticmethod
    def processar_duplicata_lancamento(lancamento, acao):
        """
        Processa duplicata do lançamento
        """
        return LancamentoDuplicataService.processar_duplicata_lancamento(lancamento, acao)
