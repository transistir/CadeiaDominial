"""
Service para operações com tipos de lançamento
"""
from ..models import LancamentoTipo


class LancamentoTipoService:
    """
    Service para operações com tipos de lançamento
    """
    
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

    @staticmethod
    def validar_numero_lancamento(numero_lancamento, documento, lancamento_id=None):
        """
        Valida se o número do lançamento é válido e único
        
        Args:
            numero_lancamento: Número do lançamento a validar
            documento: Documento do lançamento
            lancamento_id: ID do lançamento (para validação em modo de edição)
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