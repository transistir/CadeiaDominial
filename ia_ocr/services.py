"""Serviços da fila de OCR e da extração estruturada.

Nenhum log aqui carrega texto de documento ou dados do PDF (PII): apenas
job_id, status, tentativa e códigos de erro estáveis. O que vem de fora
(backend) é sanitizado antes de virar log ou coluna.
"""

import hashlib
import logging
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.utils import timezone

from dominial.models import DocumentoDigital

from . import estados
from .backends import OcrBackendError, ResultadoOcr
from .estados import TransicaoConcorrente
from .extracao_backends import ResultadoExtracao, get_extracao_backend
from .extracao_schema import validar_payload
from .models import (
    ORIGEM_CHOICES, CampoSugerido, ExtracaoSugerida, OcrJob, OcrJobTransicao, PaginaOcr,
    PendenciaLimpezaArquivo,
)
from .revisao import (
    IndiceCartorios, IndicePessoas, aplicar_linha, desnormalizar,
    enriquecer_payload, pendencias, versao_linha,
)

logger = logging.getLogger(__name__)

LIMITE_TIMINGS_CHAVES = 20
# GET /v1/ocr/jobs/{jobId} e .../result em
# ocr-service/contracts/ocr-api.openapi.yaml. Chaves novas exigem atualização
# conjunta do contrato e desta allowlist.
CHAVES_TIMING_PERMITIDAS = frozenset({
    'download_and_validation',
    'inference',
    'total',
})

CODIGOS_ERRO_PERMITIDOS = frozenset({
    # Contrato OCR v1.0.1 (ocr-service/contracts/ocr-api.openapi.yaml).
    'INVALID_INPUT',
    'INVALID_FILE_URL',
    'SOURCE_HOST_NOT_ALLOWED',
    'DOWNLOAD_TIMEOUT',
    'DOWNLOAD_FAILED',
    'TOO_MANY_REDIRECTS',
    'FILE_TOO_LARGE',
    'EMPTY_FILE',
    'INVALID_PDF',
    'ENCRYPTED_PDF',
    'TOO_MANY_PAGES',
    'PDF_PAGE_TOO_LARGE',
    'INVALID_OCR_RESULT',
    'EMPTY_OCR_RESULT',
    'OUTPUT_TOO_LARGE',
    'JOB_NOT_FOUND',
    'JOB_ID_CONFLICT',
    'JOB_TIMEOUT',
    'UNSUPPORTED_MEDIA_TYPE',
    'UNAUTHORIZED',
    'INFERENCE_FAILED',
    # Códigos internos/estáveis usados pela fila e pelo gateway.
    'QUEUE_FULL',
    'SERVICE_UNAVAILABLE',
    'WORKER_TIMEOUT',
    'BACKEND_NAO_IMPLEMENTADO',
    'ERRO_INTERNO',
})

MENSAGENS_ERRO_SEGURAS = {
    'INVALID_INPUT': 'entrada inválida para processamento OCR',
    'INVALID_FILE_URL': 'URL de arquivo inválida',
    'SOURCE_HOST_NOT_ALLOWED': 'origem do arquivo não permitida',
    'DOWNLOAD_TIMEOUT': 'tempo limite excedido ao baixar arquivo',
    'DOWNLOAD_FAILED': 'falha ao baixar arquivo para OCR',
    'TOO_MANY_REDIRECTS': 'redirecionamentos excessivos ao baixar arquivo',
    'FILE_TOO_LARGE': 'arquivo excede o limite de tamanho do serviço',
    'EMPTY_FILE': 'arquivo vazio',
    'INVALID_PDF': 'PDF inválido',
    'ENCRYPTED_PDF': 'PDF criptografado não suportado',
    'TOO_MANY_PAGES': 'documento excede o limite de páginas do serviço',
    'PDF_PAGE_TOO_LARGE': 'página do PDF excede o limite do serviço',
    'INVALID_OCR_RESULT': 'resultado OCR inválido',
    'EMPTY_OCR_RESULT': 'resultado OCR vazio',
    'OUTPUT_TOO_LARGE': 'resultado OCR excede o limite do serviço',
    'JOB_NOT_FOUND': 'job OCR não encontrado',
    'JOB_ID_CONFLICT': 'identificador do job já vinculado a outro arquivo',
    'JOB_TIMEOUT': 'serviço OCR excedeu o tempo limite do job',
    'UNSUPPORTED_MEDIA_TYPE': 'tipo de arquivo não suportado pelo serviço OCR',
    'UNAUTHORIZED': 'acesso ao serviço OCR não autorizado',
    'INFERENCE_FAILED': 'falha na inferência OCR',
    'QUEUE_FULL': 'fila do serviço OCR cheia',
    'SERVICE_UNAVAILABLE': 'serviço OCR indisponível',
    'WORKER_TIMEOUT': 'worker OCR excedeu o tempo limite',
    'BACKEND_NAO_IMPLEMENTADO': 'backend OCR não implementado',
    'ERRO_INTERNO': 'falha interna no processamento do job',
}

_ORIGENS_VALIDAS = frozenset(valor for valor, _rotulo in ORIGEM_CHOICES)


def _sanitizar_timings(timings_ms):
    """Mantém apenas métricas contratuais numéricas, no máximo 20."""
    if not isinstance(timings_ms, dict):
        return None
    sanitizado = {}
    for chave, valor in timings_ms.items():
        if len(sanitizado) >= LIMITE_TIMINGS_CHAVES:
            break
        if (
            chave in CHAVES_TIMING_PERMITIDAS
            and isinstance(valor, (int, float))
            and not isinstance(valor, bool)
        ):
            sanitizado[chave] = valor
    return sanitizado


def _sanitizar_erro_codigo(codigo):
    """Aceita somente códigos estáveis explicitamente allowlisted."""
    if isinstance(codigo, str) and codigo in CODIGOS_ERRO_PERMITIDOS:
        return codigo
    return 'ERRO_INTERNO'


def _mensagem_erro_segura(codigo):
    """Retorna texto local fixo; nunca usa mensagem fornecida pelo backend."""
    return MENSAGENS_ERRO_SEGURAS.get(
        codigo, MENSAGENS_ERRO_SEGURAS['ERRO_INTERNO']
    )


class JobIdConflitante(Exception):
    """job_id já existe vinculado a outro documento digital."""


class JobEmExecucao(Exception):
    codigo = 'JOB_EM_EXECUCAO'


class TextoNaoEditavel(Exception):
    """O texto só aceita edição/confirmação com o job em `concluido`."""
    codigo = 'TEXTO_NAO_EDITAVEL'


class EdicaoPendente(Exception):
    """Há página editada aguardando reconfirmação: o bulk não se aplica."""
    codigo = 'EDICAO_PENDENTE'


class PaginaDesatualizada(Exception):
    """O formulário foi aberto numa versão da página que já mudou."""
    codigo = 'PAGINA_DESATUALIZADA'


class ExtracaoConcorrente(Exception):
    """Reserva ocupada ou estado/extração vigente alterados (HTTP 409)."""

    code = 'extracao_concorrente'


class ExtracaoIndisponivel(Exception):
    """Falha de processamento sem expor dados do serviço (HTTP 503)."""

    code = 'extracao_indisponivel'


class ExtracaoRecusada(Exception):
    """Pré-condição local não satisfeita, identificada por código estável."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


class ConflitoVersao(Exception):
    """O bloco mudou desde a leitura do cliente (HTTP 409)."""

    code = 'conflito_versao'
    chaves_afetadas: list[str]

    def __init__(self, chaves_afetadas):
        self.chaves_afetadas = list(chaves_afetadas)
        super().__init__(self.code)


class RevisaoIncompleta(Exception):
    """Há pendências que impedem finalizar a revisão (HTTP 422)."""

    code = 'revisao_incompleta'
    pendencias: list[dict]

    def __init__(self, pendencias):
        self.pendencias = list(pendencias)
        super().__init__(self.code)


def versao_bloco(extracao) -> str:
    """Hash das versões persistidas das linhas, ordenadas pela chave."""
    versoes = ''.join(
        versao_linha(campo) for campo in extracao.campos.order_by('chave')
    )
    return hashlib.sha256(versoes.encode('utf-8')).hexdigest()


def _travar_extracao_revisao(extracao):
    """Dentro de atomic, trava job antes da extração, como a reextração."""
    job = OcrJob.objects.select_for_update().get(pk=extracao.ocr_job_id)
    travada = ExtracaoSugerida.objects.select_for_update().get(
        pk=extracao.pk, ocr_job=job,
    )
    vigente = job.extracao_vigente()
    if vigente is None or vigente.pk != travada.pk:
        raise ExtracaoRecusada('extracao_nao_vigente')
    travada.ocr_job = job
    return travada


def salvar_bloco(extracao, decisoes, usuario, versao_cliente) -> ExtracaoSugerida:
    """Persiste atomicamente decisões indexadas pela chave JSON Pointer."""
    with transaction.atomic():
        travada = _travar_extracao_revisao(extracao)
        if travada.ocr_job.status != estados.EXTRAIDO:
            raise ExtracaoRecusada('estado_invalido')
        if travada.finalizada_em is not None:
            raise ExtracaoRecusada('extracao_finalizada')

        campos = {campo.chave: campo for campo in travada.campos.all()}
        if any(chave not in campos for chave in decisoes):
            raise ExtracaoRecusada('linha_inexistente')
        if versao_cliente != versao_bloco(travada):
            if all('versao' in decisao for decisao in decisoes.values()):
                chaves = [
                    chave for chave, decisao in decisoes.items()
                    if versao_linha(campos[chave]) != decisao['versao']
                ]
            else:
                chaves = list(decisoes)
            raise ConflitoVersao(chaves)

        for chave, decisao in decisoes.items():
            campo = campos[chave]
            argumentos = {
                nome: decisao[nome] for nome in (
                    'incluir', 'valor', 'conferido', 'escolha',
                    'ha_convertido', 'confirmo_conversao',
                ) if nome in decisao
            }
            aplicar_linha(campo, **argumentos, usuario=usuario, agora=timezone.now())
            campo.save()
    return travada


def finalizar_revisao(extracao, usuario) -> ExtracaoSugerida:
    """Finaliza a revisão vigente sem pendências e audita uma única transição."""
    with transaction.atomic():
        travada = _travar_extracao_revisao(extracao)
        # Uma repetição chega com o job já revisado (ou importado).
        if travada.finalizada_em is not None:
            return travada
        job = travada.ocr_job
        if job.status != estados.EXTRAIDO:
            raise ExtracaoRecusada('estado_invalido')
        bloqueios = pendencias(travada)
        if bloqueios:
            raise RevisaoIncompleta(bloqueios)

        travada.finalizada_em = timezone.now()
        travada.finalizada_por = usuario
        travada.save(update_fields=['finalizada_em', 'finalizada_por'])
        job.transicionar(
            estados.REVISADO, usuario=usuario, motivo='revisao_finalizada',
        )
    return travada


def _validar_solicitacao_extracao(job, extracao_id):
    if job.status not in {estados.CONCLUIDO, estados.EXTRAIDO}:
        raise ExtracaoRecusada('estado_invalido')
    vigente = job.extracao_vigente()
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


def solicitar_extracao(job, usuario, extracao_id=None) -> ExtracaoSugerida:
    """Reserva → HTTP sem transação → persistência atômica da extração.

    O chamador deve executar fora de uma transação abrangente. Reextrações
    preservam as versões anteriores; a maior PK passa a ser a vigente.
    """
    atual = OcrJob.objects.get(pk=job.pk)
    _validar_solicitacao_extracao(atual, extracao_id)
    reserva = uuid.uuid4()
    try:
        # F1: relê as guardas sob trava e só mantém a reserva durante o HTTP.
        with transaction.atomic():
            travado = OcrJob.objects.select_for_update().get(pk=job.pk)
            vigente_id = _validar_solicitacao_extracao(travado, extracao_id)
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
            blocos = [
                {'pagina': pagina.numero_pagina, 'blocks': pagina.blocos}
                for pagina in paginas if pagina.blocos is not None
            ]
            if blocos:
                contexto['blocos'] = blocos
            requisicao = {
                'schema_version': 'umbelino-extracao-matricula-v1',
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
        envelope = get_extracao_backend().extrair(requisicao)
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
                payload_servico, IndicePessoas(), IndiceCartorios(),
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
            if status_inicial == estados.CONCLUIDO:
                travado.transicionar(estados.EXTRAIDO, usuario=usuario)
    except Exception as erro:
        # Atomic separado: um rollback da F3 não deve restaurar a reserva.
        with transaction.atomic():
            OcrJob.objects.filter(pk=job.pk, extracao_reserva=reserva).update(
                extracao_reserva=None, extracao_reservada_ate=None,
            )
        if isinstance(erro, (IntegrityError, TransicaoConcorrente)):
            raise ExtracaoConcorrente() from None
        if isinstance(erro, (ExtracaoRecusada, ExtracaoConcorrente, ExtracaoIndisponivel)):
            raise
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


def criar_job(documento_digital, job_id=None, criado_por=None, origem='ocr'):
    """Cria (ou recupera) um job de OCR de forma idempotente por job_id.

    O lookup é somente por job_id; os metadados vão em `defaults` — filtro
    divergente no get_or_create causaria IntegrityError na segunda chamada.
    """
    if job_id is None:
        job_id = uuid.uuid4()
    job, criado = OcrJob.objects.get_or_create(
        job_id=job_id,
        defaults={
            'documento_digital': documento_digital,
            'criado_por': criado_por,
            'origem': origem,
            'status': estados.PENDENTE,
        },
    )
    if not criado and job.documento_digital_id != documento_digital.pk:
        raise JobIdConflitante(
            f'job_id {job_id} já existe para outro documento digital.'
        )
    return job, criado


def reprocessar(job, usuario=None, forcar_ocr=True):
    """Cria um novo job de OCR para o documento do job recebido.

    O job anterior permanece INTOCADO: páginas (inclusive confirmadas) e
    auditoria não são reescritas — reprocessar nunca altera histórico. Se o
    próprio job ainda está pendente/em_execucao, recusa com ``JobEmExecucao``
    em vez de criar um sucessor reivindicável. Se já existe OUTRO job do
    documento em pendente/em_execucao, nada é criado e o job vigente é
    devolvido com ``False`` (mesmo estilo de ``criar_job``).
    A checagem e a criação são serializadas por ``select_for_update`` no
    DocumentoDigital: sem constraint parcial, que quebraria a fila da I-1
    (vários pendentes legítimos para o mesmo documento).
    """
    documento_id = job.documento_digital_id
    with transaction.atomic():
        DocumentoDigital.objects.select_for_update().get(pk=documento_id)
        origem_ativa = OcrJob.objects.filter(
            pk=job.pk,
            status__in=[estados.PENDENTE, estados.EM_EXECUCAO],
        ).exists()
        if origem_ativa:
            raise JobEmExecucao(
                'O job de origem ainda está pendente ou em execução.'
            )
        vigente = (
            OcrJob.objects
            .filter(
                documento_digital_id=documento_id,
                status__in=[estados.PENDENTE, estados.EM_EXECUCAO],
            )
            .first()
        )
        if vigente is not None:
            return vigente, False
        novo = OcrJob.objects.create(
            documento_digital_id=documento_id,
            criado_por=usuario,
            origem='ocr',
            forcar_ocr=forcar_ocr,
            status=estados.PENDENTE,
        )
        return novo, True


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
            else _normalizar_quebras_de_linha(texto)
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
        texto_final = _normalizar_quebras_de_linha(texto)
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


def claim_proximo_job(timeout_s=None):
    """Reivindica (CAS) o job mais antigo e persiste seu prazo de lease.

    O ``lease_expira_em`` é gravado no mesmo CAS que muda o status; portanto,
    todo claim novo possui prazo explícito mesmo quando o timeout default é
    usado. O lock apenas reduz disputa: a correção continua vindo do CAS.
    """
    agora = timezone.now()
    if timeout_s is None:
        timeout_s = settings.OCR_JOB_TIMEOUT_SECONDS
    lease_expira_em = agora + timedelta(seconds=timeout_s)
    with transaction.atomic():
        tentados = set()
        while True:
            candidato = (
                OcrJob.objects.select_for_update(skip_locked=True)
                .filter(status=estados.PENDENTE)
                .exclude(pk__in=tentados)
                .order_by('criado_em', 'pk')
                .first()
            )
            if candidato is None or candidato.pk in tentados:
                return None
            tentados.add(candidato.pk)
            rowcount = (
                OcrJob.objects
                .filter(pk=candidato.pk, status=estados.PENDENTE)
                .update(
                    status=estados.EM_EXECUCAO,
                    atualizado_em=agora,
                    lease_expira_em=lease_expira_em,
                )
            )
            if rowcount == 1:
                OcrJobTransicao.objects.create(
                    ocr_job_id=candidato.pk,
                    de_status=estados.PENDENTE,
                    para_status=estados.EM_EXECUCAO,
                    motivo='claim do worker',
                )
                return OcrJob.objects.get(pk=candidato.pk)


def reap_jobs_expirados(timeout_s=None):
    """Reapa leases explícitos vencidos e jobs legados pelo timestamp.

    O fallback ``atualizado_em + timeout_s`` vale somente para linhas criadas
    antes da migração, cujo ``lease_expira_em`` ainda é NULL. Cada candidato
    mantém a transição CAS individual da I-1.
    """
    agora = timezone.now()
    if timeout_s is None:
        timeout_s = settings.OCR_JOB_TIMEOUT_SECONDS
    limite_legado = agora - timedelta(seconds=timeout_s)
    reapados = 0
    expirados = OcrJob.objects.filter(status=estados.EM_EXECUCAO).filter(
        Q(lease_expira_em__lt=agora)
        | Q(lease_expira_em__isnull=True, atualizado_em__lt=limite_legado)
    )
    for job in expirados:
        try:
            job.transicionar(
                estados.FALHOU,
                motivo='WORKER_TIMEOUT',
                tentativa=job.tentativa,
                erro_codigo='WORKER_TIMEOUT',
                erro_mensagem=_mensagem_erro_segura('WORKER_TIMEOUT'),
            )
        except TransicaoConcorrente:
            continue
        reapados += 1
    return reapados


def finalizar(job, resultado_ou_erro, tentativa):
    """Finaliza um job claimado, condicionada ao lease (status + tentativa).

    Se o lease mudou (reap/retry no meio do processamento), o resultado do
    worker antigo é DESCARTADO: nada é gravado, só log com job_id/tentativa.
    Um resultado válido contém exatamente uma entrada para cada página,
    numerada de 1 a ``page_count``, sem duplicatas. ``paginas`` é materializado
    uma única vez para que iteráveis consumíveis, como geradores, sejam seguros.
    Retorna True se a finalização foi aplicada.
    """
    agora = timezone.now()
    if isinstance(resultado_ou_erro, ResultadoOcr):
        resultado = resultado_ou_erro
        try:
            paginas = list(resultado.paginas)
            numeros_paginas = [pagina['numero_pagina'] for pagina in paginas]
        except (KeyError, TypeError):
            paginas = []
            numeros_paginas = []
        page_count_valido = (
            isinstance(resultado.page_count, int)
            and not isinstance(resultado.page_count, bool)
            and resultado.page_count >= 1
        )
        paginas_validas = (
            page_count_valido
            and len(numeros_paginas) == resultado.page_count
            and all(
                isinstance(numero, int)
                and not isinstance(numero, bool)
                and 1 <= numero <= resultado.page_count
                for numero in numeros_paginas
            )
            and len(set(numeros_paginas)) == len(numeros_paginas)
        )
        if not paginas_validas:
            # O contrato exige uma entrada por página, numerada em 1..N.
            # Converte a violação no caminho de erro contratual já sanitizado.
            resultado_ou_erro = OcrBackendError(
                'INVALID_OCR_RESULT', 'páginas do resultado OCR inválidas'
            )

    with transaction.atomic():
        if (
            isinstance(resultado_ou_erro, ResultadoOcr)
            and (
                resultado_ou_erro.origem is None
                or resultado_ou_erro.origem in _ORIGENS_VALIDAS
            )
        ):
            resultado = resultado_ou_erro
            campos = {
                'status': estados.CONCLUIDO,
                'atualizado_em': agora,
                'sha256_pdf': resultado.sha256_pdf,
                'page_count': resultado.page_count,
                'timings_ms': _sanitizar_timings(resultado.timings_ms),
            }
            if resultado.origem is not None:
                # Sem origem no resultado: a origem definida no criar_job
                # (ex.: texto_embutido da I-2) permanece.
                campos['origem'] = resultado.origem
            rowcount = OcrJob.objects.filter(
                pk=job.pk, status=estados.EM_EXECUCAO, tentativa=tentativa,
            ).update(**campos)
            if rowcount == 0:
                _logar_finalizacao_descartada(job, tentativa)
                return False
            PaginaOcr.objects.bulk_create(
                PaginaOcr(
                    ocr_job_id=job.pk,
                    numero_pagina=pagina['numero_pagina'],
                    texto_ocr=pagina.get('texto', ''),
                    blocos=pagina.get('blocos'),
                )
                for pagina in paginas
            )
            OcrJobTransicao.objects.create(
                ocr_job_id=job.pk,
                de_status=estados.EM_EXECUCAO,
                para_status=estados.CONCLUIDO,
                motivo='processado com sucesso',
            )
            timings = campos['timings_ms'] or {}
            if 'total' in timings:
                logger.info(
                    'job_id=%s status=concluido page_count=%s total_ms=%s',
                    job.job_id, resultado.page_count, timings['total'],
                )
            else:
                logger.info(
                    'job_id=%s status=concluido page_count=%s',
                    job.job_id, resultado.page_count,
                )
            return True

        excecao = resultado_ou_erro
        if isinstance(excecao, OcrBackendError):
            codigo = _sanitizar_erro_codigo(excecao.codigo)
        else:
            # Resultado com origem inválida e exceções inesperadas usam o
            # mesmo erro local. Nem o valor inválido nem str(exc) são usados.
            codigo = 'ERRO_INTERNO'
        mensagem = _mensagem_erro_segura(codigo)
        rowcount = OcrJob.objects.filter(
            pk=job.pk, status=estados.EM_EXECUCAO, tentativa=tentativa,
        ).update(
            status=estados.FALHOU,
            atualizado_em=agora,
            erro_codigo=codigo,
            erro_mensagem=mensagem,
        )
        if rowcount == 0:
            _logar_finalizacao_descartada(job, tentativa)
            return False
        OcrJobTransicao.objects.create(
            ocr_job_id=job.pk,
            de_status=estados.EM_EXECUCAO,
            para_status=estados.FALHOU,
            motivo=codigo,
        )
        logger.warning('job_id=%s status=falhou erro_codigo=%s', job.job_id, codigo)
        return True


def marcar_falha_interna(job, tentativa):
    """Último recurso quando a própria finalização falhou (ex.: DatabaseError
    ao persistir páginas): marca o job falhou/ERRO_INTERNO numa NOVA transação
    (a anterior já sofreu rollback), condicionada ao mesmo lease.

    Levanta se não conseguir — quem chama decide (log + reap como rede de
    segurança). Retorna True se marcou, False se o lease já não é nosso.
    """
    agora = timezone.now()
    with transaction.atomic():
        rowcount = OcrJob.objects.filter(
            pk=job.pk, status=estados.EM_EXECUCAO, tentativa=tentativa,
        ).update(
            status=estados.FALHOU,
            atualizado_em=agora,
            erro_codigo='ERRO_INTERNO',
            erro_mensagem=_mensagem_erro_segura('ERRO_INTERNO'),
        )
        if rowcount == 0:
            _logar_finalizacao_descartada(job, tentativa)
            return False
        OcrJobTransicao.objects.create(
            ocr_job_id=job.pk,
            de_status=estados.EM_EXECUCAO,
            para_status=estados.FALHOU,
            motivo='ERRO_INTERNO',
        )
        logger.warning(
            'job_id=%s status=falhou erro_codigo=ERRO_INTERNO '
            '(finalizacao original falhou ao persistir)',
            job.job_id,
        )
        return True


def _logar_finalizacao_descartada(job, tentativa):
    logger.warning(
        'job_id=%s finalizacao descartada: lease mudou (tentativa=%s)',
        job.job_id, tentativa,
    )
