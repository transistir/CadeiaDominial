"""System checks de configuração e viabilidade do serviço OCR (#259).

Só opinam quando o backend configurado é o real (`OcrServiceBackend`): com
`StubBackend` (default da I-1) nenhum check dispara — a fila continua
operando sem serviço configurado. O mesmo gatilho vale para a validação
de lease do worker (`process_ocr_queue`), que reaproveita os helpers daqui.
"""

from django.conf import settings
from django.core import checks

CAMINHO_BACKEND_REAL = 'ia_ocr.backends.OcrServiceBackend'
TETO_PAGINAS_SERVICO = 100
TETO_BYTES_SERVICO = 52_428_800


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
