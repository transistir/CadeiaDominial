"""Expressões de banco compartilhadas para a identidade registral."""

from django.db import models
from django.db.models.functions import Substr, Trim, Upper
from django.db.models.lookups import In


def numero_documento_normalizado_expression(nome_campo):
    """Replica no banco a normalização conservadora do número documental."""
    numero_limpo = Trim(models.F(nome_campo))
    primeiro_caractere = Upper(Substr(numero_limpo, 1, 1))
    tem_prefixo_apresentacao = In(
        primeiro_caractere,
        [models.Value('M'), models.Value('T')],
    )
    return models.Case(
        models.When(
            tem_prefixo_apresentacao,
            then=Trim(Substr(numero_limpo, 2)),
        ),
        default=numero_limpo,
        output_field=models.CharField(max_length=50),
    )
