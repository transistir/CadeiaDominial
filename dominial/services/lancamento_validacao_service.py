"""
Service especializado para validações de lançamento
"""

from ..models import Lancamento


class LancamentoValidacaoService:
    """
    Service para validações de lançamento
    """
    
    @staticmethod
    def validar_numero_lancamento(numero_lancamento, documento, lancamento_id=None):
        """
        Valida se o número do lançamento é válido e único
        
        Args:
            numero_lancamento: Número do lançamento a validar
            documento: Documento do lançamento
            lancamento_id: ID do lançamento (para validação em modo de edição)
            
        Returns:
            tuple: (is_valid, error_message)
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
        Valida os dados básicos do lançamento
        
        Args:
            dados_lancamento: Dicionário com os dados do lançamento
            
        Returns:
            tuple: (is_valid, error_message)
        """
        # Validar número do lançamento
        if not dados_lancamento.get('numero_lancamento'):
            return False, 'O número do lançamento é obrigatório.'
        
        # Validar data (se fornecida, deve ser válida)
        data = dados_lancamento.get('data')
        if data and data.strip():
            try:
                from datetime import datetime
                datetime.strptime(data, '%Y-%m-%d')
            except ValueError:
                return False, 'A data fornecida não é válida.'
        
        # Validar área (se fornecida, deve ser numérica)
        area = dados_lancamento.get('area')
        if area and area.strip():
            try:
                float(area)
            except ValueError:
                return False, 'A área deve ser um número válido.'
        
        return True, None
    
    @staticmethod
    def validar_pessoas_lancamento(pessoas_data, pessoas_ids, pessoas_percentuais):
        """
        Valida os dados das pessoas do lançamento
        
        Args:
            pessoas_data: Lista de nomes das pessoas
            pessoas_ids: Lista de IDs das pessoas
            pessoas_percentuais: Lista de percentuais das pessoas
            
        Returns:
            tuple: (is_valid, error_message)
        """
        # Verificar se há pelo menos uma pessoa
        if not pessoas_data or not any(p.strip() for p in pessoas_data):
            return False, 'É necessário informar pelo menos uma pessoa.'
        
        # Validar percentuais
        total_percentual = 0
        for i, percentual in enumerate(pessoas_percentuais):
            if pessoas_data[i].strip():  # Só validar se há nome
                try:
                    if percentual and percentual.strip():
                        total_percentual += float(percentual)
                except ValueError:
                    return False, f'Percentual inválido para {pessoas_data[i]}.'
        
        # Verificar se o total é 100% (com tolerância de 0.01)
        if abs(total_percentual - 100.0) > 0.01:
            return False, f'O total dos percentuais deve ser 100%. Atual: {total_percentual:.2f}%'
        
        return True, None 