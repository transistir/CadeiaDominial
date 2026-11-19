"""Exceções estáveis e sanitização de códigos/timings do OCR.

Contrato de erro consumido pelas views e pelos testes: nenhuma exceção
carrega texto de documento ou dados do PDF (PII) — o que vem de fora
(backend) é sanitizado (allowlist de códigos, mensagens locais fixas)
antes de virar log ou coluna.
"""

import re

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


class ExtracaoPayloadInvalido(Exception):
    """O serviço respondeu, mas o payload está fora do contrato vendorizado.

    Distinta de ``ExtracaoIndisponivel`` (falha da CHAMADA — transporte,
    autenticação, tamanho): aqui a chamada deu certo e repetir não resolve;
    é divergência de contrato, a levar ao suporte. Carrega só ``codigo`` e
    ``caminho`` do ``PayloadExtracaoInvalido`` — estrutura, nunca o valor
    lido (payload de matrícula é PII).
    """

    code = 'extracao_payload_invalido'

    def __init__(self, codigo, caminho):
        self.codigo = codigo
        self.caminho = caminho
        super().__init__(f'{self.code}: {codigo} ({caminho})')


class ExtracaoIncompativel(Exception):
    """O serviço recusou o formato da requisição — versão de contrato (422).

    Distinta de ``ExtracaoIndisponivel`` (transporte, 429, 5xx, prazo: o
    serviço não respondeu): aqui o serviço respondeu e recusou, então a
    mensagem de "não respondeu" mentiria e repetir não resolve — como
    ``ExtracaoPayloadInvalido``, é divergência de versão a levar ao suporte.
    """

    code = 'extracao_incompativel'


# Código estável do backend (MAIUSCULAS_E_UNDERLINE): é o único formato que
# vai ao log. O backend é plugável (EXTRACAO_BACKEND); texto livre, quebra de
# linha ou código gigante não entram.
_CODIGO_BACKEND_ESTAVEL = re.compile(r'[A-Z][A-Z0-9_]{0,63}')


def _codigo_backend_para_log(codigo):
    if isinstance(codigo, str) and _CODIGO_BACKEND_ESTAVEL.fullmatch(codigo):
        return codigo
    return 'DESCONHECIDO'


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
