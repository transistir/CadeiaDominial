"""Tags de template do download de certidões da cadeia (#334)."""

from django import template

from ..models import DocumentoDigital

register = template.Library()


@register.simple_tag
def cadeia_tem_pdf(cadeia):
    """A cadeia tem ao menos um PDF anexado? Uma consulta EXISTS.

    Recebe a `cadeia` que a view da tabela já buscou (itens com
    `documento`), cobrindo também os importados — o PDF deles fica no
    Documento do imóvel de origem (#297). Usada para exibir o botão
    "Baixar certidões" só quando há o que baixar.
    """
    ids = [item['documento'].id for item in cadeia]
    if not ids:
        return False
    return DocumentoDigital.objects.filter(
        documento_id__in=ids, tipo_mime='application/pdf'
    ).exists()
