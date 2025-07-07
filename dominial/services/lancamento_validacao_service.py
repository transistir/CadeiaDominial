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
        
        # Validar se o número do lançamento tem o formato correto baseado no tipo
        numero_lancamento = dados_lancamento.get('numero_lancamento', '')
        tipo_lancamento = dados_lancamento.get('tipo_lancamento')
        
        if tipo_lancamento:
            if tipo_lancamento.tipo == 'averbacao' and not numero_lancamento.startswith('AV'):
                return False, 'Lançamentos do tipo "Averbação" devem ter o prefixo "AV" seguido do número e sigla da matrícula.'
            elif tipo_lancamento.tipo == 'registro' and not numero_lancamento.startswith('R'):
                return False, 'Lançamentos do tipo "Registro" devem ter o prefixo "R" seguido do número e sigla da matrícula.'
        
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
        
        return True, None 