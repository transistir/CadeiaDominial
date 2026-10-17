"""System checks de configuração e viabilidade do serviço OCR (#259).

Só opinam quando o backend configurado é o real (`OcrServiceBackend`): com
`StubBackend` (default da I-1) nenhum check dispara — a fila continua
operando sem serviço configurado. O mesmo gatilho vale para a validação
de lease do worker (`process_ocr_queue`), que reaproveita os helpers daqui.
"""

import json

from django.conf import settings
from django.core import checks

from ia_ocr.extracao_schema import SCHEMA_PATH

CAMINHO_BACKEND_REAL = 'ia_ocr.backends.OcrServiceBackend'
# Default de EXTRACAO_BACKEND (D3 cria o módulo): nunca opinar com ele.
CAMINHO_BACKEND_STUB_EXTRACAO = 'ia_ocr.extracao_backends.StubExtracaoBackend'
TETO_PAGINAS_SERVICO = 100
TETO_BYTES_SERVICO = 52_428_800

# Faixa viável de um timeout HTTP SÍNCRONO dentro do request web: o gunicorn
# encerra o worker em 300 s — o chamada inteira tem de caber antes disso.
MIN_TIMEOUT_EXTRACAO_SECONDS = 10
MAX_TIMEOUT_EXTRACAO_SECONDS = 240


def backend_real():
    """True quando o backend configurado é o cliente do serviço OCR."""
    return getattr(settings, 'OCR_BACKEND', '') == CAMINHO_BACKEND_REAL


def lease_minimo_seconds():
    """Orçamento máximo de um job: páginas + folga de fila + margem."""
    return (
        settings.OCR_MAX_PAGINAS * settings.OCR_SEGUNDOS_POR_PAGINA
        + settings.OCR_FOLGA_FILA_SECONDS
        + settings.OCR_MARGEM_PERSISTENCIA_SECONDS
    )


def conta_do_orcamento():
    """A conta do orçamento máximo com os números em uso (para mensagens)."""
    return (
        f'{settings.OCR_MAX_PAGINAS} × '
        f'{settings.OCR_SEGUNDOS_POR_PAGINA} + '
        f'{settings.OCR_FOLGA_FILA_SECONDS} + '
        f'{settings.OCR_MARGEM_PERSISTENCIA_SECONDS} = '
        f'{lease_minimo_seconds()} s'
    )


def conferir_configuracao_ocr(app_configs=None, **kwargs):
    if not backend_real():
        return []

    erros = []

    url = settings.OCR_SERVICE_URL
    if not url:
        erros.append(checks.Error(
            'OCR_SERVICE_URL não configurada: o backend '
            'ia_ocr.backends.OcrServiceBackend exige a URL do serviço OCR.',
            hint='Defina OCR_SERVICE_URL (ex.: https://ocr-teste.transistir.com).',
            id='ia_ocr.E001',
        ))

    access_configurado = bool(
        settings.OCR_ACCESS_CLIENT_ID and settings.OCR_ACCESS_CLIENT_SECRET
    )
    if url and access_configurado and not url.startswith('https://'):
        erros.append(checks.Error(
            f'OCR_SERVICE_URL ({url}) não usa https://: com credenciais do '
            'Cloudflare Access configuradas a URL tem de começar com '
            'https:// — a credencial só pode viajar por TLS.',
            hint='Configure OCR_SERVICE_URL com https://.',
            id='ia_ocr.E002',
        ))

    for nome, ident, cabecalho, codigo in (
        ('OCR_INTERNAL_TOKEN', 'ia_ocr.E003', 'X-Internal-Token', '401'),
        ('OCR_ACCESS_CLIENT_ID', 'ia_ocr.E004',
         'CF-Access-Client-Id', '403'),
        ('OCR_ACCESS_CLIENT_SECRET', 'ia_ocr.E005',
         'CF-Access-Client-Secret', '403'),
    ):
        if not getattr(settings, nome):
            erros.append(checks.Error(
                f'{nome} vazio: o serviço OCR responde {codigo} sem o '
                f'cabeçalho {cabecalho}.',
                hint=f'Defina {nome} no ambiente do worker.',
                id=ident,
            ))

    margem = settings.OCR_MARGEM_PERSISTENCIA_SECONDS
    timeout_http = settings.OCR_HTTP_TIMEOUT_SECONDS
    if margem < 2 * timeout_http:
        erros.append(checks.Error(
            f'OCR_MARGEM_PERSISTENCIA_SECONDS ({margem}) é menor que '
            f'2 × OCR_HTTP_TIMEOUT_SECONDS ({timeout_http}): o timeout do '
            'requests é por operação de socket (DNS, envio e leitura podem '
            'estourar separadamente) e a margem tem de cobrir o estouro.',
            hint=f'Use OCR_MARGEM_PERSISTENCIA_SECONDS >= {2 * timeout_http}.',
            id='ia_ocr.E006',
        ))

    lease = settings.OCR_JOB_TIMEOUT_SECONDS
    minimo = lease_minimo_seconds()
    if lease < minimo:
        erros.append(checks.Error(
            f'OCR_JOB_TIMEOUT_SECONDS ({lease}) não cobre o orçamento máximo '
            'de um job: OCR_MAX_PAGINAS × OCR_SEGUNDOS_POR_PAGINA + '
            'OCR_FOLGA_FILA_SECONDS + OCR_MARGEM_PERSISTENCIA_SECONDS = '
            f'{conta_do_orcamento()}. O reap encerraria o job mais pesado '
            'antes de ele concluir e persistir.',
            hint=f'Use OCR_JOB_TIMEOUT_SECONDS >= {minimo}.',
            id='ia_ocr.E007',
        ))

    if settings.OCR_MAX_PAGINAS > TETO_PAGINAS_SERVICO:
        erros.append(checks.Error(
            f'OCR_MAX_PAGINAS ({settings.OCR_MAX_PAGINAS}) é maior que o '
            f'teto do contrato do serviço ({TETO_PAGINAS_SERVICO}): o '
            'diagnóstico local barraria PDFs que o serviço aceitaria.',
            hint=f'Use OCR_MAX_PAGINAS <= {TETO_PAGINAS_SERVICO}.',
            id='ia_ocr.E008',
        ))

    if settings.OCR_MAX_BYTES > TETO_BYTES_SERVICO:
        erros.append(checks.Error(
            f'OCR_MAX_BYTES ({settings.OCR_MAX_BYTES}) é maior que o limite '
            f'do serviço ({TETO_BYTES_SERVICO} bytes = 50 MiB): uploads '
            'acima disso seriam recusados com FILE_TOO_LARGE só depois de '
            'gastar o upload inteiro.',
            hint=f'Use OCR_MAX_BYTES <= {TETO_BYTES_SERVICO}.',
            id='ia_ocr.E009',
        ))

    intervalo = settings.OCR_POLL_INTERVAL_SECONDS
    if not 5 <= intervalo <= 10:
        erros.append(checks.Warning(
            f'OCR_POLL_INTERVAL_SECONDS ({intervalo}) fora da faixa '
            'recomendada de 5 a 10 s: intervalo menor sobrecarrega o '
            'serviço com polls; maior aumenta a latência da fila.',
            hint='Use OCR_POLL_INTERVAL_SECONDS entre 5 e 10.',
            id='ia_ocr.W001',
        ))

    return erros


def backend_extracao_real():
    """True quando EXTRACAO_BACKEND não é o stub (nada a validar aqui)."""
    return (
        getattr(settings, 'EXTRACAO_BACKEND', CAMINHO_BACKEND_STUB_EXTRACAO)
        != CAMINHO_BACKEND_STUB_EXTRACAO
    )


def schema_vendorizado():
    """O schema A3 do contrato de extração (ia_ocr/schemas/)."""
    with open(SCHEMA_PATH, encoding='utf-8') as arquivo:
        return json.load(arquivo)


def conferir_configuracao_extracao(app_configs=None, **kwargs):
    """Configuração da extração estruturada (I-5).

    Só opina com backend real (não-stub): o stub é o default de
    desenvolvimento e não fala com serviço nenhum.
    """
    if not backend_extracao_real():
        return []

    erros = []

    if not settings.EXTRACAO_SERVICE_URL:
        erros.append(checks.Error(
            'EXTRACAO_SERVICE_URL não configurada: o backend configurado '
            'em EXTRACAO_BACKEND exige a URL do serviço de extração.',
            hint='Defina EXTRACAO_SERVICE_URL no ambiente do web.',
            id='ia_ocr.E010',
        ))

    if not settings.EXTRACAO_INTERNAL_TOKEN:
        erros.append(checks.Error(
            'EXTRACAO_INTERNAL_TOKEN vazio: o serviço de extração responde '
            '401 sem o cabeçalho X-Internal-Token.',
            hint='Defina EXTRACAO_INTERNAL_TOKEN no ambiente do web.',
            id='ia_ocr.E011',
        ))

    timeout = settings.EXTRACAO_HTTP_TIMEOUT_SECONDS
    if not (
        MIN_TIMEOUT_EXTRACAO_SECONDS
        <= timeout
        <= MAX_TIMEOUT_EXTRACAO_SECONDS
    ):
        erros.append(checks.Error(
            f'EXTRACAO_HTTP_TIMEOUT_SECONDS ({timeout}) fora da faixa viável '
            f'de {MIN_TIMEOUT_EXTRACAO_SECONDS} a '
            f'{MAX_TIMEOUT_EXTRACAO_SECONDS} s: a chamada de extração é '
            'síncrona dentro do request web e o gunicorn encerra o worker '
            'em 300 s — com timeout acima, o request morre no worker antes '
            'do próprio timeout do HTTP.',
            hint=(
                f'Use EXTRACAO_HTTP_TIMEOUT_SECONDS entre '
                f'{MIN_TIMEOUT_EXTRACAO_SECONDS} e '
                f'{MAX_TIMEOUT_EXTRACAO_SECONDS}.'
            ),
            id='ia_ocr.E012',
        ))

    try:
        import jsonschema
    except ImportError:
        erros.append(checks.Error(
            'jsonschema não está instalado: a validação do payload de '
            'extração contra o schema A3 depende dele '
            '(requirements.txt pina a versão)',
            hint='Instale as dependências de requirements.txt.',
            id='ia_ocr.E013',
        ))
    else:
        try:
            jsonschema.validators.validator_for(
                schema_vendorizado()
            ).check_schema(schema_vendorizado())
        except jsonschema.exceptions.SchemaError as erro:
            erros.append(checks.Error(
                f'O schema vendorizado de extração ({SCHEMA_PATH.name}) '
                f'violou o meta-schema: {erro.message}.',
                hint=(
                    'Não edite o schema à mão: ele é o contrato byte a '
                    'byte com o serviço de extração.'
                ),
                id='ia_ocr.E014',
            ))

    return erros
