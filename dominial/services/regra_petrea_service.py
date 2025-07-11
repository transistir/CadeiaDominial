"""
Service para implementar a regra pétrea dos documentos
"""

from ..models import Documento, Lancamento


class RegraPetreaService:
    """
    Service para implementar a regra pétrea dos documentos
    """
    
    @staticmethod
    def aplicar_regra_petrea(lancamento):
        """
        Aplica a regra pétrea: o primeiro lançamento define o livro e folha do documento
        
        Args:
            lancamento: Objeto Lancamento recém-criado
            
        Returns:
            bool: True se a regra foi aplicada, False se não foi necessário
        """
        documento = lancamento.documento
        
        # Verificar se é o primeiro lançamento do documento
        # Como o lançamento já foi salvo, contar todos os lançamentos do documento
        total_lancamentos = Lancamento.objects.filter(documento=documento).count()
        
        # Verificar se o documento já tem livro e folha definidos
        documento_tem_livro_folha = bool(documento.livro and documento.folha)
        
        if total_lancamentos == 1 and not documento_tem_livro_folha:
            # É o primeiro lançamento e documento não tem livro/folha - aplicar regra pétrea
            return RegraPetreaService._definir_livro_folha_documento(lancamento)
        else:
            # Não é o primeiro lançamento ou documento já tem livro/folha - não aplicar regra pétrea
            return False
    
    @staticmethod
    def _definir_livro_folha_documento(lancamento):
        """
        Define o livro e folha do documento baseado no primeiro lançamento
        
        Args:
            lancamento: Objeto Lancamento (primeiro lançamento)
            
        Returns:
            bool: True se foi definido, False se não foi possível
        """
        documento = lancamento.documento
        
        # Obter livro e folha do lançamento
        livro_lancamento = None
        folha_lancamento = None
        
        # Verificar campos de origem do lançamento (prioridade 1)
        if lancamento.livro_origem and lancamento.livro_origem.strip():
            livro_lancamento = lancamento.livro_origem.strip()
        if lancamento.folha_origem and lancamento.folha_origem.strip():
            folha_lancamento = lancamento.folha_origem.strip()
        
        # Se não encontrou nos campos de origem, verificar campos de transação (prioridade 2)
        if not livro_lancamento and lancamento.livro_transacao and lancamento.livro_transacao.strip():
            livro_lancamento = lancamento.livro_transacao.strip()
        if not folha_lancamento and lancamento.folha_transacao and lancamento.folha_transacao.strip():
            folha_lancamento = lancamento.folha_transacao.strip()
        
        # Se ainda não encontrou, verificar campos básicos do formulário (prioridade 3)
        # Estes dados vêm do processamento do formulário no LancamentoFormService
        if not livro_lancamento and hasattr(lancamento, 'livro_origem'):
            # O campo livro_origem do lançamento pode conter o livro básico
            livro_lancamento = lancamento.livro_origem.strip() if lancamento.livro_origem else None
        
        if not folha_lancamento and hasattr(lancamento, 'folha_origem'):
            # O campo folha_origem do lançamento pode conter a folha básica
            folha_lancamento = lancamento.folha_origem.strip() if lancamento.folha_origem else None
        
        # Atualizar documento se encontrou livro e folha
        if livro_lancamento or folha_lancamento:
            if livro_lancamento:
                documento.livro = livro_lancamento
            if folha_lancamento:
                documento.folha = folha_lancamento
            
            documento.save()
            return True
        
        return False
    
    @staticmethod
    def verificar_regra_petrea_aplicada(documento):
        """
        Verifica se a regra pétrea já foi aplicada ao documento
        
        Args:
            documento: Objeto Documento
            
        Returns:
            bool: True se a regra já foi aplicada (documento tem livro e folha)
        """
        return bool(documento.livro and documento.folha)
    
    @staticmethod
    def obter_livro_folha_primeiro_lancamento(documento):
        """
        Obtém o livro e folha do primeiro lançamento do documento
        
        Args:
            documento: Objeto Documento
            
        Returns:
            tuple: (livro, folha) ou (None, None) se não encontrado
        """
        primeiro_lancamento = Lancamento.objects.filter(documento=documento).order_by('id').first()
        
        if not primeiro_lancamento:
            return None, None
        
        livro = None
        folha = None
        
        # Verificar campos de origem
        if primeiro_lancamento.livro_origem:
            livro = primeiro_lancamento.livro_origem
        if primeiro_lancamento.folha_origem:
            folha = primeiro_lancamento.folha_origem
        
        # Se não encontrou, verificar campos de transação
        if not livro and primeiro_lancamento.livro_transacao:
            livro = primeiro_lancamento.livro_transacao
        if not folha and primeiro_lancamento.folha_transacao:
            folha = primeiro_lancamento.folha_transacao
        
        return livro, folha 