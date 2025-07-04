"""
Service para processamento de cartório de origem do lançamento
"""
from ..models import Cartorios
import uuid

class LancamentoCartorioService:
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