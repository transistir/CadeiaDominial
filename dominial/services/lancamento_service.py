"""
Service para operações relacionadas a lançamentos
"""

from ..models import Lancamento, LancamentoTipo, LancamentoPessoa, Pessoas
from django.core.exceptions import ValidationError


class LancamentoService:
    """
    Service para gerenciar operações com lançamentos
    """
    
    @staticmethod
    def criar_lancamento(documento, tipo, numero_lancamento, data, **kwargs):
        """
        Cria um novo lançamento
        """
        # Validações básicas
        if not numero_lancamento:
            raise ValueError("Número do lançamento é obrigatório")
        
        # Validar se o número já existe no documento
        if Lancamento.objects.filter(documento=documento, numero_lancamento=numero_lancamento).exists():
            raise ValidationError("Este número de lançamento já existe neste documento")
        
        lancamento = Lancamento.objects.create(
            documento=documento,
            tipo=tipo,
            numero_lancamento=numero_lancamento,
            data=data,
            **kwargs
        )
        
        return lancamento
    
    @staticmethod
    def adicionar_pessoas_lancamento(lancamento, pessoas_data):
        """
        Adiciona pessoas a um lançamento
        """
        for pessoa_data in pessoas_data:
            LancamentoPessoa.objects.create(
                lancamento=lancamento,
                pessoa=pessoa_data['pessoa'],
                tipo=pessoa_data['tipo'],
                percentual=pessoa_data['percentual'],
                nome_digitado=pessoa_data.get('nome_digitado')
            )
    
    @staticmethod
    def obter_lancamentos_documento(documento):
        """
        Obtém todos os lançamentos de um documento
        """
        return Lancamento.objects.filter(documento=documento).order_by('data')
    
    @staticmethod
    def validar_lancamento_tipo(lancamento, tipo):
        """
        Valida se o lançamento atende aos requisitos do tipo
        """
        if tipo.requer_cartorio_origem and not lancamento.cartorio_origem:
            raise ValidationError("Cartório de origem é obrigatório para este tipo de lançamento")
        
        if tipo.requer_titulo and not lancamento.titulo:
            raise ValidationError("Título é obrigatório para este tipo de lançamento")
        
        if tipo.requer_descricao and not lancamento.descricao:
            raise ValidationError("Descrição é obrigatória para este tipo de lançamento")
        
        if tipo.requer_forma and not lancamento.forma:
            raise ValidationError("Forma é obrigatória para este tipo de lançamento")
        
        return True 