"""Template tags da revisão da importação assistida (#332)."""

from django import template

from ..revisao_ato.avisos_registrados import avisos_do_lancamento

register = template.Library()


@register.inclusion_tag('ia_ocr/_avisos_do_lancamento.html')
def avisos_da_importacao(lancamento):
    """Painel de avisos registrados na importação do lançamento."""
    return {'avisos': avisos_do_lancamento(lancamento)}
