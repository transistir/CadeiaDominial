"""Confirmação e edição do texto das páginas, sob a trava do job.

``_normalizar_quebras_de_linha`` é definida aqui e chamada VIA O PACOTE
(``services.<nome>``): o teste de concorrência em PostgreSQL faz
``mock.patch.object(services, '_normalizar_quebras_de_linha')`` para injetar
lentidão dentro de ``editar_pagina``, depois da trava do job. Os demais alvos
de patch via pacote (``versao_linha``, ``IndicePessoas``,
``get_extracao_backend``) pertencem aos outros módulos do pacote.
"""

import logging

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .. import estados, services
from ..models import OcrJob, PaginaOcr
from .erros import EdicaoPendente, PaginaDesatualizada, TextoNaoEditavel

logger = logging.getLogger(__name__)


def _normalizar_quebras_de_linha(texto):
    """CRLF/CR → LF: o textarea envia CRLF e o texto do OCR usa LF.

    Sem isso, confirmar uma página sem tocar no texto a marcaria como
    editada (e o diff acusaria toda quebra de linha).
    """
    return texto.replace('\r\n', '\n').replace('\r', '\n')


def _travar_job_editavel(job):
    """Trava a linha do job e exige `concluido`. Usar dentro de atomic().

    Toda mutação de página (confirmar, editar, bulk) passa por esta trava, e a
    transição para `texto_confirmado` também toma a linha do job no seu CAS:
    o texto não muda depois de confirmado o job, e a transição valida páginas
    já commitadas.
    """
    travado = OcrJob.objects.select_for_update().get(pk=job.pk)
    if travado.status not in estados.STATUS_REVISAVEIS:
        raise TextoNaoEditavel(
            f'job {travado.job_id} está em {travado.status}: o texto não '
            'aceita mais edição.'
        )
    return travado


def _exigir_versao(job, pagina, versao_esperada):
    """Recusa o formulário aberto numa versão anterior da página.

    Chamar com o job já travado e antes de qualquer escrita: a trava serializa
    as mutações, então a versão lida é a última commitada. Sem
    `versao_esperada` (chamadas internas) não há checagem.
    """
    if versao_esperada is not None and versao_esperada != pagina.versao:
        raise PaginaDesatualizada(
            f'job {job.job_id} página {pagina.numero_pagina}: formulário da '
            f'versão {versao_esperada}, mas a página já está na versão '
            f'{pagina.versao}.'
        )


def confirmar_pagina(job, numero_pagina, usuario, texto=None, versao_esperada=None):
    """Confirma o texto de uma página: grava texto_confirmado + auditoria.

    `texto` é o conteúdo do textarea; sem ele, confirma o texto vigente (o
    rascunho salvo ou, na falta dele, o do OCR). Idempotente: reconfirmar o
    mesmo texto mantém quem/quando da confirmação original. O texto do OCR
    nunca é alterado. Exige job `concluido` (``TextoNaoEditavel``) e página
    existente (``PaginaOcr.DoesNotExist``). `versao_esperada` (a versão que o
    formulário exibiu) só é exigida quando o pedido grava: página já
    confirmada com este texto é reenvio (duplo clique, "voltar"), não
    conflito, e devolve sem erro. Se gravaria e a versão é outra, recusa com
    ``PaginaDesatualizada`` sem gravar nada. Devolve ``(pagina, alterada)``.
    """
    with transaction.atomic():
        travado = _travar_job_editavel(job)
        pagina = PaginaOcr.objects.get(
            ocr_job=travado, numero_pagina=numero_pagina,
        )
        texto_final = (
            pagina.texto_exibido if texto is None
            else services._normalizar_quebras_de_linha(texto)
        )
        if pagina.confirmado_em is not None and pagina.texto_exibido == texto_final:
            return pagina, False
        _exigir_versao(travado, pagina, versao_esperada)
        pagina.texto_confirmado = texto_final
        pagina.confirmado_por = usuario
        pagina.confirmado_em = timezone.now()
        pagina.versao += 1
        pagina.save(update_fields=[
            'texto_confirmado', 'confirmado_por', 'confirmado_em', 'versao',
        ])
    logger.info('job_id=%s pagina=%s confirmada', job.job_id, numero_pagina)
    return pagina, True


def editar_pagina(job, numero_pagina, texto, versao_esperada=None):
    """Salva uma edição do texto e invalida a confirmação da página.

    A página vira "editada": texto_confirmado guarda o rascunho e
    confirmado_em/confirmado_por são zerados, então ela precisa ser
    reconfirmada — sem isso o job não vai para `texto_confirmado`
    (``OcrJob._validar_confirmacao_de_texto``). Texto igual ao vigente não é
    edição: nada muda e a confirmação existente é mantida, qualquer que seja
    `versao_esperada` (reenvio não é conflito). Não há coluna para o autor da
    edição; quem responde pelo texto é quem o confirma. Se gravaria e
    `versao_esperada` é obsoleta: ``PaginaDesatualizada``, como em
    ``confirmar_pagina``. Devolve ``(pagina, alterada)``.
    """
    with transaction.atomic():
        travado = _travar_job_editavel(job)
        pagina = PaginaOcr.objects.get(
            ocr_job=travado, numero_pagina=numero_pagina,
        )
        texto_final = services._normalizar_quebras_de_linha(texto)
        if pagina.texto_exibido == texto_final:
            return pagina, False
        _exigir_versao(travado, pagina, versao_esperada)
        pagina.texto_confirmado = texto_final
        pagina.confirmado_por = None
        pagina.confirmado_em = None
        pagina.versao += 1
        pagina.save(update_fields=[
            'texto_confirmado', 'confirmado_por', 'confirmado_em', 'versao',
        ])
    logger.info('job_id=%s pagina=%s editada', job.job_id, numero_pagina)
    return pagina, True


def confirmar_todas_paginas(job, usuario):
    """Bulk: confirma, como estão no OCR, as páginas ainda não confirmadas.

    Só vale quando o usuário não editou nada: com alguma página "editada"
    (rascunho aguardando reconfirmação) recusa com ``EdicaoPendente`` e nada é
    gravado — as editadas se confirmam uma a uma. Páginas já confirmadas, com
    ou sem edição, não são tocadas: texto e auditoria delas permanecem. As
    confirmadas agora ganham versão nova, o que invalida formulários abertos
    nelas. Não transiciona o job. Devolve quantas páginas foram confirmadas
    agora.
    """
    with transaction.atomic():
        travado = _travar_job_editavel(job)
        pendentes = PaginaOcr.objects.filter(
            ocr_job=travado, confirmado_em__isnull=True,
        )
        if pendentes.filter(texto_confirmado__isnull=False).exists():
            raise EdicaoPendente(
                f'job {travado.job_id} tem página editada aguardando confirmação.'
            )
        total = pendentes.update(
            texto_confirmado=F('texto_ocr'),
            confirmado_por=usuario,
            confirmado_em=timezone.now(),
            versao=F('versao') + 1,
        )
    if total:
        logger.info('job_id=%s paginas=%s confirmadas em lote', job.job_id, total)
    return total


def confirmar_texto(job, usuario):
    """concluido → texto_confirmado ("Extrair campos →").

    A pré-condição (todas as páginas com ``confirmado_em``) é validada por
    ``OcrJob.transicionar`` dentro da transação do CAS: levanta
    ``TransicaoInvalida`` (``paginas_nao_confirmadas`` / ``sem_paginas`` /
    ``transicao_invalida``) e nada é gravado; ``TransicaoConcorrente`` se o job
    mudou de estado no meio. A transição é auditada em ``OcrJobTransicao`` com
    o usuário. A extração dos campos em si é da I-5.
    """
    job.transicionar(
        estados.TEXTO_CONFIRMADO, usuario=usuario,
        motivo='texto confirmado pelo usuário',
    )
    logger.info('job_id=%s status=texto_confirmado', job.job_id)
    return job
