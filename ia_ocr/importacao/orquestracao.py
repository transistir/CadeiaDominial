"""Vínculos de auditoria e marcação de linhas importadas.

O motor em lote (``importar``/``resumo``/``_atos_marcados`` e o savepoint
por ato) foi aposentado na fase 4 da #341 junto com a tela de cards: a
gravação agora é um ato por vez, pela revisão no formulário
(``revisao_ato.salvar_ato``). Ficam aqui as duas peças que o caminho novo
também usa:

- ``_vincular`` — grava os ``ImportacaoIA`` dos objetos criados;
- ``_marcar_importadas`` — marca as linhas efetivamente incluídas.

Ambos são chamados VIA O PACOTE (``importacao._vincular``): o call site
resolve o nome no objeto do pacote, a cada chamada.
"""
from django.utils import timezone

from .. import revisao
from ..models import ImportacaoIA


def _vincular(job, usuario, lancamento, registros, linhas):
    """Grava os vínculos de auditoria (ImportacaoIA) dos objetos criados."""
    for modelo, objeto_id, chave_linha in registros:
        campo = linhas.get(chave_linha)
        ImportacaoIA.objects.create(
            ocr_job=job,
            documento_digital_id=job.documento_digital_id,
            campo=campo,
            pagina=campo.evidencia_pagina if campo else None,
            modelo=modelo,
            objeto_id=objeto_id,
            lancamento=lancamento,
            criado_por=usuario,
        )


def _marcar_importadas(extracao, usuario, chaves_atos):
    """Linhas EFETIVAMENTE incluídas dos atos importados → ``importado``.

    Linha descartada (direta ou por ancestral descartado) continua com o
    status e a autoria que a revisão deixou: importação não reescreve
    decisão de descarte (#263 rodada 2). Mesma noção de incluída do
    ``revisao._contexto_revisao`` (a que alimenta a gravação).
    """
    incluidas, _ = revisao._contexto_revisao(extracao)
    chaves_atos = set(chaves_atos)
    alvos = [
        chave for chave in incluidas
        if chave in chaves_atos or any(
            chave.startswith(f'{ato}/') for ato in chaves_atos
        )
    ]
    extracao.campos.filter(chave__in=alvos).update(
        status_revisao='importado',
        revisado_por=usuario,
        revisado_em=timezone.now(),
    )
