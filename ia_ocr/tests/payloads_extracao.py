"""Payloads sintéticos no shape do A3 vendorizado (fixtures da revisão I-5).

Três cenários — registro com partes/valores, averbação com descrição e
registro com closure preenchido — todos válidos contra
``validar_payload(payload, job_id, [1])``. Todo campo de valor carrega
evidência cujo trecho é substring literal de ``TEXTO_PAGINA_1`` (o texto
OCR sintético da página 1 dos testes); nada aqui vem de documento real.

A versão do contrato vem de ``ia_ocr.extracao_schema`` (fonte única): a MAIS
NOVA (hoje v1.2), a que o app pede ao serviço. Teste que precisa de outro
contrato (v1.1 de serviço antigo) declara o ``schema_version`` à mão.
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


# Matrícula M237/Itamaraju (caso público ocr-service #72), redigida: nomes e
# imóvel fictícios. O serviço passou a emitir o ATO DE ABERTURA quando o
# documento nasce de uma transcrição (ocr-service #75) — esta fixture prova
# que o app já o mapeia sem campo, template ou migration novos.
TEXTO_M237 = '\n'.join((
    'MATRÍCULA Nº 237 LIVRO 2 FLS 237 DATA 09.06.1982',
    'IMÓVEL: o imóvel rural denominado "FAZENDA MODELO", situado no '
    'município de Itamaraju, com a área de 169 hectares, 09 ares e 40 '
    'centiares.',
    'Abertura: matrícula aberta em face da TRANSCRIÇÃO Nº 4.321, Livro 3, '
    'Folha 12, CRI de Itamaraju.',
    'Proprietário: ANA FICTÍCIA DE ALMEIDA.',
    'R-1, de 10.07.1982: Escritura Pública de Compra e Venda.',
    'Av-2, de 12.08.1983: averbação de construção de casa sede.',
    'Av-3, de 03.09.1984: averbação de retificação de área.',
    'R-4, de 04.10.1985: Escritura Pública de Doação.',
    'R-5, de 05.11.1986: Escritura Pública de Compra e Venda.',
    'Av-6, de 06.12.1987: averbação de penhora.',
    'Av-7, de 07.01.1988: averbação de cancelamento de penhora.',
))

_AREA_M237 = '169 hectares, 09 ares e 40 centiares'


def _area_m237(trecho=_AREA_M237):
    return _campo(
        '169.0940', trecho, raw=trecho, unidade='ha',
    )


def _documento_m237():
    """Cabeçalho da M237 — todos os trechos são substring de ``TEXTO_M237``."""
    cartorio = _campo(
        'CRI de Itamaraju', 'CRI de Itamaraju', municipio='Itamaraju',
        match_sugerido={'cartorio_id': None, 'candidatos': []},
    )
    return {
        'tipo': _campo('matricula', 'MATRÍCULA Nº 237', raw='MATRÍCULA'),
        'numero': _campo('237', 'Nº 237', raw='Nº 237'),
        'data': _campo('1982-06-09', 'DATA 09.06.1982', raw='09.06.1982'),
        'cartorio': cartorio,
        'cri_atual': dict(cartorio),
        'livro': _campo('2', 'LIVRO 2', raw='LIVRO 2'),
        'folha': _campo('237', 'FLS 237', raw='FLS 237'),
        'imovel_descricao': _campo('FAZENDA MODELO', 'FAZENDA MODELO'),
        'area': _area_m237(),
    }


def _ato_m237(ordem, rotulo, tipo, data_iso, data_texto, trecho, **extras):
    """Ato sintético da M237 — evidência sempre literal em ``TEXTO_M237``."""
    ato = {
        'ordem': ordem,
        'rotulo': _campo(rotulo, trecho, raw=rotulo),
        'tipo_sugerido': _campo(tipo, trecho, raw=rotulo),
        'data': _campo(data_iso, data_texto, raw=data_texto),
        'confianca': 0.95,
        'requer_revisao': False,
        'evidencia': _evidencia(trecho),
    }
    ato.update(extras)
    return ato


def _ato_abertura_m237():
    """O ato de abertura: início de matrícula nascido da transcrição 4.321."""
    return _ato_m237(
        1, 'M-237', 'inicio_matricula', '1982-06-09', '09.06.1982',
        'MATRÍCULA Nº 237',
        area=_area_m237(),
        livro_transacao=_campo(None, 'LIVRO 2'),
        folha_transacao=_campo(None, 'FLS 237'),
        origem={
            'tipo_documento': _campo(
                'transcricao', 'TRANSCRIÇÃO Nº 4.321', raw='TRANSCRIÇÃO',
            ),
            'numero': _campo('4321', 'TRANSCRIÇÃO Nº 4.321', raw='4.321'),
            'livro': _campo('3', 'Livro 3', raw='Livro 3'),
            'folha': _campo('12', 'Folha 12', raw='Folha 12'),
        },
        partes=[_parte('adquirente', 'ANA FICTÍCIA DE ALMEIDA')],
    )


def payload_m237_abertura(job_id):
    """Matrícula M237 com o ato de abertura + 7 R/Av, na ordem do A3.

    O primeiro ato (``ordem=1``) é a abertura (``inicio_matricula``) e os
    demais são R-1, Av-2, Av-3, R-4, R-5, Av-6 e Av-7, com ``ordem`` 2..8.
    """
    return {
        'schema_version': SCHEMA_VERSION,
        'document': _documento_m237(),
        'acts': [
            _ato_abertura_m237(),
            _ato_m237(
                2, 'R-1', 'registro', '1982-07-10', '10.07.1982',
                'R-1, de 10.07.1982',
            ),
            _ato_m237(
                3, 'Av-2', 'averbacao', '1983-08-12', '12.08.1983',
                'Av-2, de 12.08.1983',
            ),
            _ato_m237(
                4, 'Av-3', 'averbacao', '1984-09-03', '03.09.1984',
                'Av-3, de 03.09.1984',
            ),
            _ato_m237(
                5, 'R-4', 'registro', '1985-10-04', '04.10.1985',
                'R-4, de 04.10.1985',
            ),
            _ato_m237(
                6, 'R-5', 'registro', '1986-11-05', '05.11.1986',
                'R-5, de 05.11.1986',
            ),
            _ato_m237(
                7, 'Av-6', 'averbacao', '1987-12-06', '06.12.1987',
                'Av-6, de 06.12.1987',
            ),
            _ato_m237(
                8, 'Av-7', 'averbacao', '1988-01-07', '07.01.1988',
                'Av-7, de 07.01.1988',
            ),
        ],
        'closure': None,
        'meta': _meta(job_id),
    }
