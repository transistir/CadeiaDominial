"""Solicitação de extração estruturada: reserva, HTTP e persistência.

``solicitar_extracao`` resolve ``get_extracao_backend`` e ``IndicePessoas``
VIA O PACOTE (``services.<nome>``): os testes fazem ``mock.patch`` em
``ia_ocr.services`` e o patch só vale se o call site resolver o nome no
objeto do pacote, a cada chamada.
"""

import logging
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from .. import estados, services
from ..estados import TransicaoConcorrente
from ..extracao_backends import ExtracaoBackendError, ResultadoExtracao
from ..extracao_schema import (
    SCHEMA_VERSION, PayloadExtracaoInvalido, validar_payload,
)
from ..models import (
    CampoSugerido, ExtracaoSugerida, OcrJob, PaginaOcr, PendenciaLimpezaArquivo,
)
from ..revisao import IndiceCartorios, desnormalizar, enriquecer_payload
from .erros import (
    ExtracaoConcorrente, ExtracaoIncompativel, ExtracaoIndisponivel,
    ExtracaoPayloadInvalido, ExtracaoRecusada, _codigo_backend_para_log,
)

logger = logging.getLogger(__name__)


def _validar_solicitacao_extracao(job, extracao_id, somente_se_inexistente=False):
    if job.status not in {
        estados.CONCLUIDO, estados.TEXTO_CONFIRMADO, estados.EXTRAIDO,
    }:
        raise ExtracaoRecusada('estado_invalido')
    vigente = job.extracao_vigente()
    if somente_se_inexistente and vigente is not None:
        # PR #319: o POST atrasado de uma segunda aba não cria extração
        # vigente nova (o que esconderia as correções gravadas na primeira).
        raise ExtracaoRecusada('extracao_existente')
    vigente_id = vigente.pk if vigente is not None else None
    if extracao_id is not None and str(extracao_id) != str(vigente_id):
        raise ExtracaoConcorrente()
    if (
        job.extracao_reservada_ate is not None
        and job.extracao_reservada_ate > timezone.now()
    ):
        raise ExtracaoConcorrente()
    return vigente_id


def _textos_corrigidos_extracao(envelope, numeros_paginas):
    """Exige uma correção por página e DPI válido antes de persistir."""
    if not isinstance(envelope, dict):
        raise ExtracaoIndisponivel()
    dpi = envelope.get('dpi')
    if type(dpi) is not int or dpi <= 0:
        raise ExtracaoIndisponivel()
    paginas = envelope.get('paginas')
    if not isinstance(paginas, list):
        raise ExtracaoIndisponivel()
    textos = {}
    for pagina in paginas:
        if not isinstance(pagina, dict):
            raise ExtracaoIndisponivel()
        numero = pagina.get('pagina')
        texto = pagina.get('texto_corrigido')
        if (
            type(numero) is not int
            or numero not in numeros_paginas
            or numero in textos
            or not isinstance(texto, str)
        ):
            raise ExtracaoIndisponivel()
        textos[numero] = texto
    if set(textos) != numeros_paginas:
        raise ExtracaoIndisponivel()
    return textos


def _blocos_da_pagina(pagina):
    """Lista de blocos OCR da página para o `contexto.blocos` da requisição.

    O adaptador grava em PaginaOcr.blocos o envelope
    ``{'dpi', 'width_px', 'height_px', 'blocos': [...]}`` (backends.py); o
    combinado na #290 é enviar só a LISTA em ``blocks``. Registros legados
    guardaram a lista direta no campo — a leitura aceita ambos.
    """
    envelope = pagina.blocos
    if isinstance(envelope, dict):
        return envelope.get('blocos')
    return envelope


def solicitar_extracao(
    job, usuario, extracao_id=None, somente_se_inexistente=False,
) -> ExtracaoSugerida:
    """Reserva → HTTP sem transação → persistência atômica da extração.

    O chamador deve executar fora de uma transação abrangente. Reextrações
    preservam as versões anteriores; a maior PK passa a ser a vigente.

    ``somente_se_inexistente`` (auto-extração da #314) recusa com
    ``ExtracaoRecusada('extracao_existente')`` quando o job já tem extração
    vigente — inclusive na releitura sob ``select_for_update``, que fecha a
    janela entre a leitura otimista e a transação. Sem o flag, a reextração
    manual funciona como antes.

    Falhas da chamada ao serviço (``ExtracaoBackendError``) e erros
    inesperados viram ``ExtracaoIndisponivel``; resposta fora do contrato
    (``PayloadExtracaoInvalido``) vira ``ExtracaoPayloadInvalido``, com
    código e caminho; 422 do serviço (formato da requisição recusado) vira
    ``ExtracaoIncompativel``. Nenhum dado do serviço vai para log ou exceção.
    """
    atual = OcrJob.objects.get(pk=job.pk)
    _validar_solicitacao_extracao(atual, extracao_id, somente_se_inexistente)
    reserva = uuid.uuid4()
    try:
        # F1: relê as guardas sob trava e só mantém a reserva durante o HTTP.
        with transaction.atomic():
            travado = OcrJob.objects.select_for_update().get(pk=job.pk)
            vigente_id = _validar_solicitacao_extracao(
                travado, extracao_id, somente_se_inexistente,
            )
            status_inicial = travado.status
            paginas = list(travado.paginas.all())
            if not paginas or any(pagina.texto_ocr is None for pagina in paginas):
                raise ExtracaoRecusada('sem_texto_ocr')
            documento = travado.documento_digital.documento
            contexto = {
                'cartorio': documento.cartorio.nome,
                'municipio': documento.cartorio.cidade,
                'dpi': travado.dpi or 200,
            }
            blocos = []
            for pagina in paginas:
                lista = _blocos_da_pagina(pagina)
                if lista is not None:
                    blocos.append(
                        {'pagina': pagina.numero_pagina, 'blocks': lista}
                    )
            if blocos:
                contexto['blocos'] = blocos
            requisicao = {
                'schema_version': SCHEMA_VERSION,
                'job_id': str(travado.job_id),
                'tipo_documento': documento.tipo.tipo,
                'paginas': [
                    {'pagina': pagina.numero_pagina, 'texto': pagina.texto_ocr}
                    for pagina in paginas
                ],
                'contexto': contexto,
            }
            travado.extracao_reserva = reserva
            travado.extracao_reservada_ate = timezone.now() + timedelta(
                seconds=settings.EXTRACAO_HTTP_TIMEOUT_SECONDS + 30,
            )
            travado.save(update_fields=['extracao_reserva', 'extracao_reservada_ate'])

        # F2: nenhuma transação aberta pelo serviço durante a chamada externa.
        envelope = services.get_extracao_backend().extrair(requisicao)
        if isinstance(envelope, ResultadoExtracao):
            envelope = envelope.payload
        numeros_paginas = {pagina.numero_pagina for pagina in paginas}
        textos_corrigidos = _textos_corrigidos_extracao(envelope, numeros_paginas)
        payload_servico = envelope['extracao']
        validar_payload(payload_servico, travado.job_id, numeros_paginas)

        # F3: respostas tardias não podem sobrescrever outra reserva/versão.
        with transaction.atomic():
            travado = OcrJob.objects.select_for_update().get(pk=job.pk)
            vigente = travado.extracao_vigente()
            if (
                travado.extracao_reserva != reserva
                or travado.status != status_inicial
                or (vigente.pk if vigente is not None else None) != vigente_id
            ):
                raise ExtracaoConcorrente()
            agora = timezone.now()
            for pagina in paginas:
                pagina.texto_corrigido = textos_corrigidos[pagina.numero_pagina]
                pagina.corrigido_em = agora
            PaginaOcr.objects.bulk_update(paginas, ['texto_corrigido', 'corrigido_em'])
            payload = enriquecer_payload(
                payload_servico, services.IndicePessoas(), IndiceCartorios(),
            )
            extracao = ExtracaoSugerida.objects.create(
                ocr_job=travado,
                payload_servico=payload_servico,
                payload=payload,
                schema_version=payload_servico['schema_version'],
                provider=payload_servico['meta']['provider'],
                solicitada_por=usuario,
                finalizada_em=None,
            )
            CampoSugerido.objects.bulk_create(desnormalizar(extracao, payload, paginas))
            travado.dpi = envelope['dpi']
            travado.extracao_reserva = None
            travado.extracao_reservada_ate = None
            travado.save(update_fields=['dpi', 'extracao_reserva', 'extracao_reservada_ate'])
            if status_inicial in {estados.CONCLUIDO, estados.TEXTO_CONFIRMADO}:
                travado.transicionar(estados.EXTRAIDO, usuario=usuario)
    except Exception as erro:
        # Atomic separado: um rollback da F3 não deve restaurar a reserva.
        with transaction.atomic():
            OcrJob.objects.filter(pk=job.pk, extracao_reserva=reserva).update(
                extracao_reserva=None, extracao_reservada_ate=None,
            )
        if isinstance(erro, (IntegrityError, TransicaoConcorrente)):
            raise ExtracaoConcorrente() from None
        if isinstance(erro, PayloadExtracaoInvalido):
            # Resposta fora do contrato: código + caminho são estrutura (nunca
            # o valor lido), então podem ir ao log e à exceção.
            logger.warning(
                'job_id=%s extracao_payload_invalido codigo=%s caminho=%s',
                job.job_id, erro.codigo, erro.caminho,
            )
            raise ExtracaoPayloadInvalido(erro.codigo, erro.caminho) from None
        if isinstance(erro, ExtracaoBackendError):
            # Falha da CHAMADA (transporte, autenticação, tamanho, status HTTP
            # inesperado): não há payload para comparar com o contrato, então
            # segue ExtracaoIndisponivel ("não respondeu"). Exceção: o 422 do
            # serviço (EXTRACAO_INCOMPATIVEL) — o serviço respondeu e recusou
            # o formato da requisição, o que merece diagnóstico próprio em
            # vez de "não respondeu". O que distingue uma falha da outra é o
            # código estável, que vai ao log; a mensagem do backend (texto
            # livre) não.
            logger.warning(
                'job_id=%s extracao_backend_falhou codigo=%s',
                job.job_id, _codigo_backend_para_log(erro.codigo),
            )
            if erro.codigo == 'EXTRACAO_INCOMPATIVEL':
                raise ExtracaoIncompativel() from None
            raise ExtracaoIndisponivel() from None
        if isinstance(erro, (ExtracaoRecusada, ExtracaoConcorrente, ExtracaoIndisponivel)):
            raise
        # Inesperado: só o TIPO da exceção (str(erro)/traceback podem trazer
        # valor lido do serviço).
        logger.error(
            'job_id=%s extracao_falhou tipo_erro=%s', job.job_id, type(erro).__name__,
        )
        raise ExtracaoIndisponivel() from None

    job.status = travado.status
    job.dpi = travado.dpi
    job.atualizado_em = travado.atualizado_em
    job.extracao_reserva = None
    job.extracao_reservada_ate = None
    return extracao


def registrar_pendencia_limpeza(
    documento_digital_id, caminho_storage, documento_id=None
):
    """Registra a intenção de limpeza antes da remoção física do arquivo.

    A intenção é gravada na mesma transação que exclui o DocumentoDigital.
    Ela é removida quando a limpeza física conclui e permanece, para retomada
    pelo suporte, somente quando essa limpeza falha. Só o caminho fica no banco,
    nunca em log, para não expor o nome do arquivo fora do sistema.
    """
    return PendenciaLimpezaArquivo.objects.create(
        documento_digital_id=documento_digital_id,
        documento_id=documento_id,
        caminho_storage=caminho_storage,
    )
