"""Validação do payload de extração estruturada contra o schema A3.

Os schemas em ia_ocr/schemas/ são o contrato byte a byte com o serviço de
OCR (hoje v1.1 e v1.2); nunca editar à mão. Há MAIS DE UM contrato
vendorizado de propósito, por compatibilidade de rollout: serviço e app não
sobem juntos, então durante a virada o app recebe payload do serviço antigo
(v1.1) e do novo (v1.2) e aceita os dois. Antes, dois arquivos juntos eram
erro (troca mal feita: o antigo não saiu no PR); agora é decisão explícita —
aposentar um contrato é apagar o arquivo e o sha256 pinado nos testes.

A identidade de cada contrato é o ``const`` de ``properties.schema_version``
(nunca o literal no código, o nome do arquivo ou o ``$id``: o ``$id`` do v1.2
do serviço ainda diz v1.1, descuido de lá que não se conserta aqui).
``CONTRATOS`` mapeia versão → (caminho, schema, validador), e o loader recusa
arquivo cujo nome não seja o próprio ``const`` (o que também impede a mesma
versão em dois arquivos).

- ``SCHEMA_VERSION`` é a versão MAIS NOVA (ordenada como versão, não como
  texto) e é o que vai na requisição (services); ``SCHEMA_PATH`` é o arquivo
  dela.
- ``validar_payload`` escolhe o contrato pelo ``schema_version`` DO PAYLOAD:
  serviço antigo (v1.1) segue funcionando, novo (v1.2) é aceito, e versão
  ausente ou desconhecida é ``schema_versao_desconhecida``. Cada payload vale
  pelo contrato que declara: nada é afrouxado (o v1.1 continua rejeitando o
  que só o v1.2 conhece).

A validação estrutural roda SEM format_checker: em campo de valor o
`format` do A3 é anotação, não checagem — data inválida em campo de valor
(``2024-02-30``, ``31/12/2024``) NÃO derruba o payload; quem trata é a
desnormalização (normalized=NULL + requer_revisao). Checagem estrita de
formato só existe em ``meta``.
"""

import datetime
import json
import re
import uuid
from pathlib import Path
from typing import NamedTuple

from jsonschema import Draft202012Validator


class Contrato(NamedTuple):
    """Um contrato vendorizado: arquivo, schema lido e validador pronto."""

    caminho: Path
    schema: dict
    validador: Draft202012Validator


def _versao_do_schema(schema):
    """Versão do contrato: o `const` de `properties.schema_version`."""
    return schema['properties']['schema_version']['const']


_SUFIXO_DE_VERSAO = re.compile(r'-v(\d+(?:\.\d+)*)$')


def _chave_de_versao(versao):
    """Ordem de versão: ``v1.10`` > ``v1.2`` (como texto, seria o contrário)."""
    achado = _SUFIXO_DE_VERSAO.search(versao)
    if achado is None:
        raise ValueError(
            f'versão de contrato sem sufixo -vN[.M]: {versao!r}'
        )
    return tuple(int(parte) for parte in achado.group(1).split('.'))


def _carregar_contratos(diretorio):
    """Lê TODOS os contratos vendorizados: versão (``const``) → Contrato.

    Cada arquivo tem de ser coerente com o próprio ``const``: versão com
    sufixo numérico e nome do arquivo igual à versão. Cópia renomeada sem
    trocar o ``const`` (ou o contrário) é troca mal feita — erro, em vez de
    validar contra o contrato errado; e, como o nome é único na pasta, duas
    versões iguais nunca coexistem no mapa.
    """
    contratos = {}
    for caminho in sorted(diretorio.glob('umbelino-extracao-matricula-*.json')):
        with open(caminho, encoding='utf-8') as arquivo:
            schema = json.load(arquivo)
        versao = _versao_do_schema(schema)
        _chave_de_versao(versao)
        if caminho.stem != versao:
            raise ValueError(
                f'{caminho.name} declara {versao!r} em schema_version: o '
                'nome do arquivo tem de ser a própria versão'
            )
        contratos[versao] = Contrato(caminho, schema, Draft202012Validator(schema))
    if not contratos:
        raise FileNotFoundError(
            f'nenhum contrato vendorizado em {diretorio}'
        )
    return contratos


def _mais_nova(contratos):
    """A versão mais nova do mapa (por número de versão, não por nome)."""
    return max(contratos, key=_chave_de_versao)


CONTRATOS = _carregar_contratos(Path(__file__).parent / 'schemas')
SCHEMA_VERSION = _mais_nova(CONTRATOS)
SCHEMA_PATH = CONTRATOS[SCHEMA_VERSION].caminho

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


# O nome de uma chave extra só entra no caminho se tiver cara de campo do A3
# (ASCII snake_case, ex.: ``data_transacao``): é o que torna o diagnóstico
# possível. Texto livre vindo do serviço — possível PII numa chave inventada —
# não: o caminho alimenta logs e a mensagem da exceção.
_NOME_DE_CAMPO = re.compile(r'[A-Za-z_][A-Za-z0-9_]{0,63}')
_CHAVE_EXTRA_OPACA = '<chave_extra>'


def _erro_estrutural_para_excecao(erro):
    codigo = _CODIGOS_ESTRUTURAIS.get(erro.validator, 'schema_violado')
    caminho = _caminho(erro.absolute_path)
    if erro.validator == 'additionalProperties':
        # instance/schema só para derivar o NOME da chave extra (estrutura,
        # não valor) — nenhum dos dois vai para a exceção.
        permitidas = set(erro.schema.get('properties', {}))
        extras = sorted(set(erro.instance) - permitidas)
        if extras:
            extra = extras[0]
            nome_seguro = isinstance(extra, str) and _NOME_DE_CAMPO.fullmatch(extra)
            caminho = f'{caminho}.{extra if nome_seguro else _CHAVE_EXTRA_OPACA}'
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


def _contrato_do_payload(payload):
    """O contrato que o PAYLOAD declara em ``schema_version``.

    Ausente, não-texto ou fora de ``CONTRATOS`` → ``schema_versao_desconhecida``:
    sem contrato conhecido não há contra o que validar, e escolher um por
    palpite (o mais novo, o mais antigo) esconderia a divergência. O
    ``isinstance`` evita ``TypeError`` com valor não-hashable (``[]``, ``{}``).
    """
    versao = payload.get('schema_version')
    contrato = CONTRATOS.get(versao) if isinstance(versao, str) else None
    if contrato is None:
        raise PayloadExtracaoInvalido(
            'schema_versao_desconhecida', '$.schema_version'
        )
    return contrato


def validar_payload(payload, job_id, paginas):
    """Valida o payload do job contra o A3 e as regras de contorno do I-5.

    - Contrato: o do ``schema_version`` do próprio payload (v1.1 ou v1.2);
      versão ausente/desconhecida → ``schema_versao_desconhecida``.
    - Estrutura: Draft 2020-12 (additionalProperties, required, enums e
      confiança 0–1) SEM format_checker (ver docstring do módulo).
    - ``meta`` estrita: job_id do job ou UUID válido (qualquer forma aceita
      por ``uuid.UUID``) do serviço, páginas dentro do job, provider ≤ 100 e
      ``texto_confirmado_em`` como date-time de verdade.
    - Contagem: atos ≤ 300, partes por ato ≤ 40, cada `ordem` única e
      volume total ≤ 10 000 objetos/10 000 chars por string.

    `paginas` é qualquer iterável de números de página do job.
    """
    if not isinstance(payload, dict):
        raise PayloadExtracaoInvalido('tipo_invalido', '$')

    contrato = _contrato_do_payload(payload)
    primeiro_erro = next(contrato.validador.iter_errors(payload), None)
    if primeiro_erro is not None:
        raise _erro_estrutural_para_excecao(primeiro_erro)

    meta = payload.get('meta', {})
    if meta.get('job_id') != str(job_id):
        # O ocrcadeia gera um ID próprio; preservar o valor para rastreabilidade.
        try:
            uuid.UUID(meta['job_id'])
        except (ValueError, TypeError, AttributeError):
            raise PayloadExtracaoInvalido('job_id_invalido', '$.meta.job_id') from None
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
