"""
Service para processamento de origens automáticas dos lançamentos
"""
from ..utils.hierarquia_utils import processar_origens_para_documentos

class LancamentoOrigemService:
    @staticmethod
    def processar_origens_automaticas(lancamento, origem, imovel):
        if origem:
            origens_processadas = processar_origens_para_documentos(origem, imovel, lancamento)
            if origens_processadas:
                return f'Foram identificadas {len(origens_processadas)} origem(ns) para criação automática de documentos.'
        return None 