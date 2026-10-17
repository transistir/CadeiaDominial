"""Validação do payload de extração estruturada contra o schema A3.

O schema em ia_ocr/schemas/ é o contrato byte a byte com o serviço de
OCR (umbelino-extracao-matricula-v1); nunca editar à mão.

A validação estrutural roda SEM format_checker: em campo de valor o
`format` do A3 é anotação, não checagem — data inválida em campo de valor
(``2024-02-30``, ``31/12/2024``) NÃO derruba o payload; quem trata é a
desnormalização (normalized=NULL + requer_revisao). Checagem estrita de
formato só existe em ``meta``.
"""

import datetime
import json
from pathlib import Path

from jsonschema import Draft202012Validator

SCHEMA_PATH = Path(__file__).parent / 'schemas' / 'umbelino-extracao-matricula-v1.json'

# Limites anti-lixo de contorno (I-5): uma matrícula real tem dezenas de
# atos, meia dúzia de partes por ato e campos legíveis. Payload acima disso
# é estouro estrutural do serviço, não leitura a ser revisada.
LIMITE_ATOS = 300
LIMITE_PARTES_POR_ATO = 40
LIMITE_LINHAS = 10_000  # objetos do payload (cada um vira linha na desnormalização)
LIMITE_TEXTO = 10_000  # caracteres por string de valor

# validator do jsonschema → codigo estável de rejeição
_CODIGOS_ESTRUTURAIS = {
    'additionalProperties': 'propriedade_extra',
    'const': 'valor_const_inesperado',
    'minimum': 'valor_fora_do_intervalo',
    'maximum': 'valor_fora_do_intervalo',
    'enum': 'valor_fora_do_enum',
}


class PayloadExtracaoInvalido(Exception):
    """Payload rejeitado: código + caminho, nunca o valor lido.

    `str(exc)` não carrega valor do payload (nem bruto nem normalizado):
    a mensagem vive de logs e tracebacks, e payload de matrícula é PII.
    """

    def __init__(self, codigo, caminho):
        self.codigo = codigo
        self.caminho = caminho
        super().__init__(f'{codigo} ({caminho})')


def _caminho(path):
    """absolute_path do jsonschema → notação enxuta: ``acts[3].partes``."""
    texto = '$'
    for item in path:
        texto += f'[{item}]' if isinstance(item, int) else f'.{item}'
    return texto


def _carregar_validador():
    with open(SCHEMA_PATH, encoding='utf-8') as arquivo:
        schema = json.load(arquivo)
    return Draft202012Validator(schema)


_VALIDADOR = _carregar_validador()


def _erro_estrutural_para_excecao(erro):
    codigo = _CODIGOS_ESTRUTURAIS.get(erro.validator, 'schema_violado')
    caminho = _caminho(erro.absolute_path)
    if erro.validator == 'additionalProperties':
        # instance/schema só para derivar o NOME da chave extra (estrutura,
        # não valor) — nenhum dos dois vai para a exceção.
        permitidas = set(erro.schema.get('properties', {}))
        extras = sorted(set(erro.instance) - permitidas)
        if extras:
            caminho = f'{caminho}.{extras[0]}'
    return PayloadExtracaoInvalido(codigo, caminho)


def _e_date_time_iso(valor):
    """``texto_confirmado_em`` exige date-time ISO de verdade (data E hora).

    `2024-02-30T10:00:00` (data impossível), `ontem`, `31/12/2024` e
    date/solo-time não passam. Offset de fuso é opcional.
    """
    if not isinstance(valor, str):
        return False
    try:
        lido = datetime.datetime.fromisoformat(valor)
    except ValueError:
        return False
    return isinstance(lido, datetime.datetime)


def _varrer(valor, caminho):
    """Passeia o payload aplicando os limites de volume do I-5.

    - string de valor acima de LIMITE_TEXTO → `campo_muito_longo` no
      caminho exato da string (o caminho é estrutura; o valor não vai).
    - mais de LIMITE_LINHAS objetos (cada objeto do payload desnormaliza
      em uma linha de CampoSugerido/evidência) → `limite_excedido`.

    Retorna o número de objetos vistos; levanta na primeira violação.
    """
    if isinstance(valor, dict):
        total = 1
        for chave, item in valor.items():
            total += _varrer(item, f'{caminho}.{chave}')
            if total > LIMITE_LINHAS:
                raise PayloadExtracaoInvalido('limite_excedido', '$')
        return total
    if isinstance(valor, list):
        total = 0
        for indice, item in enumerate(valor):
            total += _varrer(item, f'{caminho}[{indice}]')
            if total > LIMITE_LINHAS:
                raise PayloadExtracaoInvalido('limite_excedido', '$')
        return total
    if isinstance(valor, str) and len(valor) > LIMITE_TEXTO:
        raise PayloadExtracaoInvalido('campo_muito_longo', caminho)
    return 0


def validar_payload(payload, job_id, paginas):
    """Valida o payload do job contra o A3 e as regras de contorno do I-5.

    - Estrutura: Draft 2020-12 (additionalProperties, required, enums e
      confiança 0–1) SEM format_checker (ver docstring do módulo).
    - ``meta`` estrita: job_id do job, páginas dentro do job, provider ≤ 100
      e ``texto_confirmado_em`` como date-time de verdade.
    - Contagem: atos ≤ 300, partes por ato ≤ 40, cada `ordem` única e
      volume total ≤ 10 000 objetos/10 000 chars por string.

    `paginas` é qualquer iterável de números de página do job.
    """
    if not isinstance(payload, dict):
        raise PayloadExtracaoInvalido('tipo_invalido', '$')

    primeiro_erro = next(_VALIDADOR.iter_errors(payload), None)
    if primeiro_erro is not None:
        raise _erro_estrutural_para_excecao(primeiro_erro)

    meta = payload.get('meta', {})
    if meta.get('job_id') != str(job_id):
        raise PayloadExtracaoInvalido('job_id_divergente', '$.meta.job_id')
    fora_do_job = set(meta.get('pages_used') or []) - set(paginas)
    if fora_do_job:
        raise PayloadExtracaoInvalido('pagina_fora_do_job', '$.meta.pages_used')
    if len(meta.get('provider') or '') > 100:
        raise PayloadExtracaoInvalido('provider_muito_longo', '$.meta.provider')
    em = meta.get('texto_confirmado_em')
    if em is not None and not _e_date_time_iso(em):
        raise PayloadExtracaoInvalido(
            'formato_invalido', '$.meta.texto_confirmado_em'
        )

    atos = payload.get('acts') or []
    if len(atos) > LIMITE_ATOS:
        raise PayloadExtracaoInvalido('limite_excedido', '$.acts')
    ordens = set()
    for indice, ato in enumerate(atos):
        if len(ato.get('partes') or []) > LIMITE_PARTES_POR_ATO:
            raise PayloadExtracaoInvalido(
                'limite_excedido', f'$.acts[{indice}].partes'
            )
        if ato.get('ordem') in ordens:
            raise PayloadExtracaoInvalido(
                'ordem_repetida', f'$.acts[{indice}].ordem'
            )
        ordens.add(ato.get('ordem'))

    _varrer(payload, '$')
