"""Testes do validador do payload de extração (schemas A3 vendorizados).

Os contratos são os JSONs em ia_ocr/schemas/ (v1.1 e v1.2), cópias byte a
byte do serviço de OCR — nunca editados à mão. A validação estrutural usa
Draft 2020-12 SEM format_checker: `format` em campo de valor é anotação (data
inválida vira normalized=NULL + requer_revisao na desnormalização, não
rejeição). Cada payload é validado pelo contrato que ELE declara em
``schema_version``.
"""

from pathlib import Path

from ia_ocr import extracao_schema
from ia_ocr.extracao_schema import SCHEMA_VERSION

V1_1 = 'umbelino-extracao-matricula-v1.1'
V1_2 = 'umbelino-extracao-matricula-v1.2'
PASTA_SCHEMAS = Path(extracao_schema.__file__).parent / 'schemas'
# Pinado de propósito (não derivado do módulo): trocar um contrato é decisão
# explícita, com o novo sha256 do ocr-service.
SHA256_DOS_CONTRATOS = {
    V1_1: 'ae296837b964f180c8f80ac1a77815a43ff05eca52b6f3586a237129b9b2caff',
    V1_2: '8be9b56ff0c7a073c151d7c58e80efb7ed97c97ff0ff9f71b7488477c7940bc5',
}
CAMPOS_DE_TRANSMISSAO = ('livro_transacao', 'folha_transacao', 'data_transacao')


def campo(normalized=None, raw=None, confianca=0.9, evidencia=None):
    """Campo A3 mínimo: raw/normalized/confianca/requer_revisao/evidencia."""
    return {
        'raw': raw,
        'normalized': normalized,
        'confianca': confianca,
        'requer_revisao': False,
        'evidencia': evidencia,
    }


def ato(ordem=1, partes=0):
    """Atos A3 mínimo: campos required de #/$defs/act + `partes`."""
    return {
        'ordem': ordem,
        'rotulo': campo('R-1'),
        'tipo_sugerido': campo('registro'),
        'data': campo('2024-01-01'),
        'partes': [
            {
                'papel': 'transmitente',
                'nome': campo('Fulano'),
                'confianca': 0.9,
                'requer_revisao': False,
                'evidencia': None,
            }
            for _ in range(partes)
        ],
        'confianca': 0.9,
        'requer_revisao': False,
        'evidencia': None,
    }


def ato_com_transmissao(ordem=1):
    """Ato do contrato v1.2: livro/folha/data da transmissão (`*_transacao`)."""
    return {
        **ato(ordem),
        'livro_transacao': campo('10-A', raw='Livro 10-A'),
        'folha_transacao': campo('25v', raw='fl. 25v'),
        'data_transacao': campo('2019-12-20', raw='20/12/2019'),
    }


def payload_minimo(
    job_id='11111111-1111-1111-1111-111111111111', paginas=(1,),
    versao=SCHEMA_VERSION,
):
    """Payload que satisfaz o A3 por inteiro (âncora dos testes)."""
    return {
        'schema_version': versao,
        'document': {
            'tipo': campo('matricula'),
            'numero': campo(
                '42.718',
                raw='Nº 42.718',
                evidencia={'pagina': 1, 'trecho': 'matrícula nº 42.718'},
            ),
            'cartorio': campo('CRI de Guaíra'),
        },
        'acts': [],
        'meta': {
            'job_id': job_id,
            'pages_used': list(paginas),
            'provider': 'local-model',
        },
    }



class ExtracaoSchemaBase:
    """Base comum mantida por último na MRO das fachadas."""
