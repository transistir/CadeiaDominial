"""
Service para operações com tipos e validação de lançamentos
"""
from ..models import Lancamento, LancamentoTipo

class LancamentoTipoService:
    @staticmethod
    def obter_tipos_lancamento_por_documento(documento):
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
    def validar_numero_lancamento(numero_lancamento, documento):
        if not numero_lancamento or not numero_lancamento.strip():
            return False, 'O número do lançamento é obrigatório.'
        lancamento_existente = Lancamento.objects.filter(
            documento=documento,
            numero_lancamento=numero_lancamento.strip()
        ).first()
        if lancamento_existente:
            return False, f'Já existe um lançamento com o número "{numero_lancamento.strip()}" neste documento.'
        return True, None 