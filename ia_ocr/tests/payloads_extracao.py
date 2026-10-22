"""Payloads sintéticos no shape do A3 vendorizado (fixtures da revisão I-5).

Três cenários — registro com partes/valores, averbação com descrição e
registro com closure preenchido — todos válidos contra
``validar_payload(payload, job_id, [1])``. Todo campo de valor carrega
evidência cujo trecho é substring literal de ``TEXTO_PAGINA_1`` (o texto
OCR sintético da página 1 dos testes); nada aqui vem de documento real.

A versão do contrato vem de ``ia_ocr.extracao_schema`` (fonte única).
"""

from ia_ocr.extracao_schema import SCHEMA_VERSION

PROVIDER = 'local-model'
MODEL = 'umbelino-extracao-v1'

TEXTO_PAGINA_1 = '\n'.join((
    'MATRÍCULA Nº 42.718 — CRI de Guaíra',
    'Data de abertura: 10 de janeiro de 2020 (2020-01-10).',
    'Cartório de Registro de Imóveis de Guaíra — CNS 12.345-6.',
    'Livro 2-RG, Folha 087.',
    'IMÓVEL: Lote rural nº 14, Gleba São João, com 12,5 ha.',
    'R-1/42.718, de 15 de fevereiro de 2020 (2020-02-15): Escritura '
    'Pública de Compra e Venda, valor R$ 150.000,00, área 12,50 ha.',
    'Transmitente: JOÃO DA SILVA (CPF 123.456.789-00).',
    'Transmitente: MARIA DA SILVA (CPF 987.654.321-00).',
    'Adquirente: PEDRO SANTOS.',
    'Av-1/42.718, de 20 de março de 2021 (2021-03-20): averbação de '
    'construção de casa sede, área construída 120,00 m2.',
    'Indício de fim de cadeia: origem União.',
))


def _evidencia(trecho):
    return {'pagina': 1, 'trecho': trecho}


def _campo(normalized, trecho, raw=None, confianca=0.95, requer_revisao=False,
           **extras):
    """Campo de valor A3: {raw, normalized, confianca, requer_revisao, evidencia}."""
    campo = {
        'raw': normalized if raw is None else raw,
        'normalized': normalized,
        'confianca': confianca,
        'requer_revisao': requer_revisao,
        'evidencia': _evidencia(trecho),
    }
    campo.update(extras)
    return campo


def _document():
    """Cabeçalho completo: os 9 campos de ``document`` do A3."""
    return {
        'tipo': _campo('matricula', 'MATRÍCULA Nº 42.718', raw='Matrícula'),
        'numero': _campo('42.718', 'Nº 42.718', raw='Nº 42.718'),
        'data': _campo(
            '2020-01-10', '10 de janeiro de 2020',
            raw='10 de janeiro de 2020',
        ),
        'cartorio': _campo('CRI de Guaíra', 'CRI de Guaíra'),
        'cri_atual': _campo(
            'Cartório de Registro de Imóveis de Guaíra',
            'Cartório de Registro de Imóveis de Guaíra',
        ),
        'livro': _campo('2-RG', 'Livro 2-RG', raw='Livro 2-RG'),
        'folha': _campo('087', 'Folha 087', raw='Folha 087'),
        'imovel_descricao': _campo(
            'Lote rural nº 14, Gleba São João',
            'Lote rural nº 14, Gleba São João',
        ),
        'area': _campo('12.5', '12,5 ha', raw='12,5 ha', unidade='ha'),
    }


def _cpf(normalizado, raw):
    """documento_identificacao de CPF: tipo + valor com máscara no raw."""
    return {
        'tipo': _campo('CPF', raw),
        'valor': _campo(normalizado, raw, raw=raw),
    }


def _parte(papel, nome, documento=None):
    return {
        'papel': papel,
        'nome': _campo(nome, nome, confianca=0.92),
        'documento_identificacao': documento,
        'confianca': 0.92,
        'requer_revisao': False,
        'evidencia': _evidencia(nome),
    }


def _ato_registro():
    """R-1 com 2 transmitentes, 1 adquirente, valor e área em ha."""
    return {
        'ordem': 1,
        'rotulo': _campo('R-1', 'R-1/42.718', raw='R-1/42.718'),
        'tipo_sugerido': _campo('registro', 'R-1/42.718', raw='R-1'),
        'data': _campo(
            '2020-02-15', '15 de fevereiro de 2020',
            raw='15 de fevereiro de 2020',
        ),
        'partes': [
            _parte(
                'transmitente', 'JOÃO DA SILVA',
                _cpf('12345678900', '123.456.789-00'),
            ),
            _parte(
                'transmitente', 'MARIA DA SILVA',
                _cpf('98765432100', '987.654.321-00'),
            ),
            _parte('adquirente', 'PEDRO SANTOS'),
        ],
        'valor_transacao': _campo(
            '150000.00', 'R$ 150.000,00', raw='R$ 150.000,00',
        ),
        'area': _campo('12.50', 'área 12,50 ha', raw='12,50 ha', unidade='ha'),
        'confianca': 0.95,
        'requer_revisao': False,
        'evidencia': _evidencia('R-1/42.718'),
    }


def _ato_averbacao():
    """Av-1 com descrição, sem origem e sem partes."""
    return {
        'ordem': 1,
        'rotulo': _campo('Av-1', 'Av-1/42.718', raw='Av-1/42.718'),
        'tipo_sugerido': _campo('averbacao', 'Av-1/42.718', raw='Av-1'),
        'data': _campo(
            '2021-03-20', '20 de março de 2021', raw='20 de março de 2021',
        ),
        'descricao': _campo(
            'averbação de construção de casa sede',
            'averbação de construção de casa sede',
        ),
        'confianca': 0.93,
        'requer_revisao': False,
        'evidencia': _evidencia('Av-1/42.718'),
    }


def _closure():
    """Indício de fim de cadeia preenchido — sempre decisão humana."""
    return {
        'indicio_fim_cadeia': _campo(
            True, 'Indício de fim de cadeia', raw='Indício de fim de cadeia',
        ),
        'origem_publica_sugerida': _campo('União', 'origem União', raw='União'),
        'classificacao_sugerida': _campo(
            'origem_lidima', 'Indício de fim de cadeia',
            raw='sem registro anterior',
        ),
    }


def _meta(job_id):
    return {
        'job_id': str(job_id),
        'provider': PROVIDER,
        'model': MODEL,
        'pages_used': [1],
    }


def payload_registro(job_id):
    """Matrícula com 1 ato de registro (partes, valor e área)."""
    return {
        'schema_version': SCHEMA_VERSION,
        'document': _document(),
        'acts': [_ato_registro()],
        'closure': None,
        'meta': _meta(job_id),
    }


def payload_averbacao(job_id):
    """Matrícula com 1 ato de averbação: descrição, sem origem."""
    return {
        'schema_version': SCHEMA_VERSION,
        'document': _document(),
        'acts': [_ato_averbacao()],
        'closure': None,
        'meta': _meta(job_id),
    }


def payload_com_closure(job_id):
    """Como o registro + closure preenchido."""
    payload = payload_registro(job_id)
    payload['closure'] = _closure()
    return payload
