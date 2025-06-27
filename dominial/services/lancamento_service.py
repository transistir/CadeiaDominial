"""
Service principal para operações de lançamento
"""

from ..models import Lancamento, LancamentoTipo, Documento
from .lancamento_criacao_service import LancamentoCriacaoService
from .lancamento_form_service import LancamentoFormService
from .lancamento_tipo_service import LancamentoTipoService
from .lancamento_validacao_service import LancamentoValidacaoService
from .lancamento_documento_service import LancamentoDocumentoService
from .lancamento_cartorio_service import LancamentoCartorioService
from .lancamento_origem_service import LancamentoOrigemService
from .lancamento_pessoa_service import LancamentoPessoaService


class LancamentoService:
    """
    Service principal para operações de lançamento
    """
    
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
    
    @staticmethod
    def obter_tipos_lancamento_por_documento(documento):
        """
        Obtém os tipos de lançamento disponíveis para um documento
        """
        return LancamentoTipoService.obter_tipos_lancamento_por_documento(documento)
    
    @staticmethod
    def validar_numero_lancamento(numero_lancamento, documento, lancamento_id=None):
        """
        Valida se o número do lançamento é único no documento
        """
        return LancamentoValidacaoService.validar_numero_lancamento(numero_lancamento, documento, lancamento_id)
    
    @staticmethod
    def processar_dados_lancamento(request, tipo_lanc):
        """
        Processa os dados do formulário de lançamento
        """
        return LancamentoFormService.processar_dados_lancamento(request, tipo_lanc)
    
    @staticmethod
    def processar_cartorio_origem(request, tipo_lanc, lancamento):
        """
        Processa o cartório de origem do lançamento
        """
        return LancamentoCartorioService.processar_cartorio_origem(request, tipo_lanc, lancamento)
    
    @staticmethod
    def criar_lancamento(documento_ativo, dados_lancamento, tipo_lanc):
        """
        Cria um novo lançamento
        """
        return LancamentoCriacaoService._criar_lancamento_basico(documento_ativo, dados_lancamento, tipo_lanc)
    
    @staticmethod
    def processar_origens_automaticas(lancamento, origem, imovel):
        """
        Processa origens para criar documentos automáticos
        """
        return LancamentoOrigemService.processar_origens_automaticas(lancamento, origem, imovel)
    
    @staticmethod
    def processar_pessoas_lancamento(lancamento, pessoas_data, pessoas_ids, pessoas_percentuais, tipo_pessoa):
        """
        Processa pessoas do lançamento
        """
        return LancamentoPessoaService.processar_pessoas_lancamento(lancamento, pessoas_data, pessoas_ids, pessoas_percentuais, tipo_pessoa)
    
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