"""Ordenação da lista de imóveis pela atividade mais recente na cadeia (#375).

A atividade de um imóvel é o instante mais recente entre: edição ou criação
de qualquer documento, edição ou criação de qualquer lançamento, e o próprio
cadastro do imóvel (fallback para linhas antigas, cujo ``atualizado_em`` é
NULL por não ter backfill).
"""
from datetime import datetime, timezone as dt_timezone

from django.db.models import DateTimeField, F, Max, Value
from django.db.models.functions import Cast, Coalesce, Greatest

# Aware em UTC: com USE_TZ=True um datetime naive dispara RuntimeWarning
# ("received a naive datetime") na compilação da query para o Postgres.
EPOCH = Value(
    datetime(1970, 1, 1, tzinfo=dt_timezone.utc), output_field=DateTimeField()
)


def ordenar_por_atividade(qs):
    """Ordena imóveis pela última atividade na cadeia (doc/lançamento), desc.

    - ``Greatest`` entre documento e lançamento é o ponto central: um
      ``Coalesce`` sozinho ignoraria o lançamento quando o imóvel já tem
      documento (regressão #375).
    - ``Coalesce`` com ``Cast(data_cadastro)`` cobre as linhas anteriores à
      migração, cujo ``atualizado_em`` ficou NULL.
    - Desempate por matrícula; ``select_related('cartorio')`` evita N+1 na
      coluna de cartório abreviado da lista.
    """
    return (
        qs.annotate(
            # Paridade com o refactor #132: os atributos continuam expostos
            # nos objetos (guardado por TisDetailOrderingTest), embora o
            # template não os leia.
            ultimo_documento=Max('documentos__data_cadastro'),
            ultimo_lancamento=Max('documentos__lancamentos__data_cadastro'),
            ultima_atividade=Greatest(
                Coalesce(
                    Max('documentos__atualizado_em'),
                    Cast(Max('documentos__data_cadastro'), DateTimeField()),
                    EPOCH,
                ),
                Coalesce(
                    Max('documentos__lancamentos__atualizado_em'),
                    Cast(Max('documentos__lancamentos__data_cadastro'), DateTimeField()),
                    EPOCH,
                ),
                # Coalesce no cast do imóvel: no SQLite o Greatest vira MAX()
                # escalar, que devolve NULL se QUALQUER argumento for NULL
                # (o Postgres ignora os NULLs) — sem o Coalesce, um
                # data_cadastro castado para NULL zeraria a linha inteira.
                Coalesce(Cast(F('data_cadastro'), DateTimeField()), EPOCH),
            ),
        )
        .order_by('-ultima_atividade', 'matricula')
        .select_related('cartorio')
    )
