"""``input_do_campo`` e ``prefill_do_ato``: o contrato do formulário.

``prefill_do_ato`` é o que a revisão consome por ato (``views/revisar``);
``input_do_campo`` é o mapa chave-da-linha → input, compartilhado pelas
evidências de origem e de partes.
"""

import re
import unicodedata
from datetime import date

from dominial.models import Cartorios, Pessoas

from .. import importacao, vocabulario
from .areas import _area_em_outra_unidade, area_para_input
from ..destinos import _normalizar
from .erros import AtoInexistente
from .numeros import _numero_composto, _numero_simples
from ..revisao import _montar_dados
from ..rotulos import analisar_rotulo
from .texto import _como_texto, _evidencia, _nomes, data_do_raw

# Chave da linha (o padrão de ``destinos.DESTINOS``, índices como ``*``) →
# nome do input do formulário que a recebe. Fonte ÚNICA: o prefill escreve o
# valor no input e a evidência anexa o trecho ao MESMO input.
#
# Exceções resolvidas por ``input_do_campo``: a forma da AVERBAÇÃO vai para
# ``forma_averbacao`` (o serviço lê o nome conforme o tipo) e o nome da parte
# segue o papel. Os inputs de lista aparecem sem o ``[]``.
CHAVE_PARA_INPUT = {
    '/document/livro': 'livro_documento',
    '/document/folha': 'folha_documento',
    '/acts/*/tipo_sugerido': 'tipo_lancamento',
    '/acts/*/rotulo': 'numero_lancamento_simples',
    '/acts/*/numero_lancamento': 'numero_lancamento_simples',
    '/acts/*/data': 'data',
    '/acts/*/area': 'area',
    '/acts/*/descricao': 'descricao',
    '/acts/*/observacoes': 'observacoes',
    '/acts/*/forma': 'forma_transacao',
    '/acts/*/titulo': 'titulo_transacao',
    '/acts/*/cartorio_transmissao': 'cartorio_transmissao_nome',
    '/acts/*/livro_transacao': 'livro_transacao',
    '/acts/*/folha_transacao': 'folha_transacao',
    '/acts/*/data_transacao': 'data_transacao',
    '/acts/*/origem/tipo_documento': 'tipo_origem',
    '/acts/*/origem/numero': 'numero_origem',
    '/acts/*/origem/cartorio': 'cartorio_origem_nome',
    '/acts/*/origem/livro': 'livro_origem',
    '/acts/*/origem/folha': 'folha_origem',
    '/acts/*/partes/*/nome': '{papel}_nome',
}

INPUT_FORMA_DA_AVERBACAO = 'forma_averbacao'

# Vocabulário pinado (#372): o casamento aproximado não é silencioso.
MOTIVO_FORMA_DO_VOCABULARIO = 'forma_ajustada_vocabulario'
ROTULO_DA_FORMA = 'Forma'
TEXTO_FORMA_DO_VOCABULARIO = (
    "Forma lida '{lido}' casou por aproximação com '{canonica}' do "
    "vocabulário congelado; confira o valor antes de salvar."
)


def forma_do_vocabulario(forma):
    """``(valor, pendência)`` da forma; sem casamento, mantém o valor do A3.

    O dicionário é a cópia pinada do artefato do ocr-service (``vocabulario``)
    — nada de produção em runtime. Casar exato ou normalizado troca o valor
    sem aviso (é o mesmo nome canônico). O casamento aproximado (``fuzzy``)
    troca o valor E deixa uma pendência informativa, para o revisor ver que
    houve ajuste. Empate, baixa confiança ou valor vazio devolvem a forma
    original intacta: o vocabulário nunca inventa valor.

    Fail-open: se o JSON pinado não conferir (``VocabularioInvalido``), a
    tela continua com o valor do A3 — o loader segue estrito, mas o prefill
    não derruba a revisão.
    """
    try:
        casamento = vocabulario.casar(vocabulario.CAMPO_FORMA, forma)
    except vocabulario.VocabularioInvalido:
        return forma, None
    if not casamento.casa:
        return forma, None
    if casamento.metodo != vocabulario.FUZZY:
        return casamento.valor, None
    return casamento.valor, {
        'motivo': MOTIVO_FORMA_DO_VOCABULARIO,
        'rotulo': ROTULO_DA_FORMA,
        'texto': TEXTO_FORMA_DO_VOCABULARIO.format(
            lido=forma, canonica=casamento.valor,
        ),
        'bloqueante': False,
    }


# Item 4: forma = natureza, título = instrumento, data_transacao = data do
# instrumento. A classificação é literal (sem acento/caixa), sem adivinhar.
MARCAS_DE_INSTRUMENTO = (
    'escritura', 'transcri', 'carta de', 'formal de partilha',
    'alvara', 'mandado', 'termo de', 'instrumento',
)
MOTIVO_FORMA_TITULO_REINTERPRETADOS = 'forma_titulo_reinterpretados'
ROTULO_FORMA_E_TITULO = 'Forma e título'
TEXTO_FORMA_TITULO_REINTERPRETADOS = (
    "Forma e título reinterpretados: o instrumento '{instrumento}' foi para "
    "o título e a natureza '{natureza}' para a forma; confira antes de salvar."
)
MOTIVO_DATA_TRANSACAO_DO_INSTRUMENTO = 'data_transacao_do_instrumento'
ROTULO_DATA_TRANSACAO = 'Data da transmissão'
TEXTO_DATA_TRANSACAO_DO_INSTRUMENTO = (
    'Data da transmissão ajustada para a data do instrumento ({data}).'
)
TEXTO_DATA_TRANSACAO_DIVERGENTE = (
    'Data da transmissão do A3 ({a3}) difere da data do instrumento '
    '({data}); vale a data do instrumento.'
)

_MESES_PT_SEM_ACENTO = {
    'janeiro': 1, 'fevereiro': 2, 'marco': 3, 'abril': 4, 'maio': 5,
    'junho': 6, 'julho': 7, 'agosto': 8, 'setembro': 9, 'outubro': 10,
    'novembro': 11, 'dezembro': 12,
}
_DATA_NUMERICA_NO_TEXTO = re.compile(
    r'(?<!\d)(?P<dia>\d{1,2})[./](?P<mes>\d{1,2})[./](?P<ano>\d{4})(?!\d)'
)
_DATA_POR_EXTENSO = re.compile(
    r'(?<!\d)(?P<dia>\d{1,2})\s+de\s+(?P<mes>[a-z]+)\s+de\s+'
    r'(?P<ano>\d{4})(?!\d)'
)


def _sem_acento(texto):
    """Texto em minúsculas e sem acento (classificação e meses pt-BR)."""
    decomposto = unicodedata.normalize('NFKD', texto)
    return ''.join(
        caractere for caractere in decomposto
        if not unicodedata.combining(caractere)
    ).lower()


def _classe_da_forma(texto):
    """``'instrumento'``, ``'natureza'`` ou ``None`` para texto vazio."""
    if not isinstance(texto, str) or not texto.strip():
        return None
    normalizado = _sem_acento(texto)
    if any(marca in normalizado for marca in MARCAS_DE_INSTRUMENTO):
        return 'instrumento'
    return 'natureza'


def _forma_e_titulo(forma, titulo):
    """``(forma, titulo, instrumento, houve_swap)`` do ato.

    Troca SÓ quando um dos textos é instrumento e o outro é natureza. Mesma
    classe (ou texto ausente) mantém o mapeamento atual do A3.
    """
    classe_forma = _classe_da_forma(forma)
    classe_titulo = _classe_da_forma(titulo)
    if (
        classe_forma is not None and classe_titulo is not None
        and classe_forma != classe_titulo
    ):
        if classe_forma == 'instrumento':
            return titulo, forma, forma, True
        return forma, titulo, titulo, True
    instrumento = forma if classe_forma == 'instrumento' else (
        titulo if classe_titulo == 'instrumento' else None
    )
    return forma, titulo, instrumento, False


def _data_valida(dia, mes, ano):
    try:
        return date(int(ano), int(mes), int(dia))
    except (TypeError, ValueError):
        return None


def data_do_instrumento(texto):
    """Data explícita no texto do instrumento, ou ``None``.

    Aceita ``dd.mm.aaaa``, ``dd/mm/aaaa`` e ``dd de <mês> de aaaa`` (meses
    pt-BR sem acento), sempre validando o calendário. Não completa dígitos
    nem aproxima: fora do formato exato devolve ``None``.
    """
    if not isinstance(texto, str) or not texto.strip():
        return None
    normalizado = _sem_acento(texto)
    for achado in _DATA_NUMERICA_NO_TEXTO.finditer(normalizado):
        data = _data_valida(
            achado.group('dia'), achado.group('mes'), achado.group('ano'),
        )
        if data is not None:
            return data
    for achado in _DATA_POR_EXTENSO.finditer(normalizado):
        mes = _MESES_PT_SEM_ACENTO.get(achado.group('mes'))
        if mes is None:
            continue
        data = _data_valida(achado.group('dia'), mes, achado.group('ano'))
        if data is not None:
            return data
    return None


def _data_transacao_do_instrumento(instrumento, data_do_a3):
    """``(data, pendência)``: a data do instrumento vence a do A3, se houver."""
    data = data_do_instrumento(instrumento)
    if data is None:
        return data_do_a3, None
    if data_do_a3 is not None and data != data_do_a3:
        texto = TEXTO_DATA_TRANSACAO_DIVERGENTE.format(
            a3=data_do_a3, data=data.isoformat(),
        )
    else:
        texto = TEXTO_DATA_TRANSACAO_DO_INSTRUMENTO.format(
            data=data.isoformat(),
        )
    return data, {
        'motivo': MOTIVO_DATA_TRANSACAO_DO_INSTRUMENTO,
        'rotulo': ROTULO_DATA_TRANSACAO,
        'texto': texto,
        'bloqueante': False,
    }


def input_do_campo(chave, tipo=None, papel=None):
    """Nome do input que recebe a linha ``chave``, ou ``None`` sem input.

    ``chave`` é o ponteiro concreto (``/acts/0/data``) ou o padrão
    (``/acts/*/data``). ``tipo`` (código do tipo do ato) desvia a forma da
    averbação; ``papel`` completa o nome da parte.
    """
    padrao = _normalizar(chave)
    if padrao == '/acts/*/forma' and tipo == 'averbacao':
        return INPUT_FORMA_DA_AVERBACAO
    nome = CHAVE_PARA_INPUT.get(padrao)
    return nome.format(papel=papel) if nome is not None else None


def prefill_do_ato(extracao, indice, documento):
    """O que o formulário de lançamento recebe para o ato ``indice``.

    ``extracao`` é a extração da revisão (em qualquer estado), ``indice`` o
    ``N`` de ``/acts/N`` e ``documento`` o ``Documento`` que recebe o
    lançamento. Só lê o banco. Levanta ``AtoInexistente`` quando o índice
    não é de um ato incluído (descartado inclusive).

    Devolve ``{form_data, origens_separadas, transmitentes, adquirentes,
    evidencias, pendencias}`` (ver o docstring do módulo).
    """
    # Importação tardia: ``dominial.views`` já importa ``ia_ocr`` e
    # ``ia_ocr.views`` deve consumir este módulo (fase 2) — no topo, ciclo.
    from dominial.views.lancamento_views import _flags_livro_folha_definidos

    indice = int(indice)
    chave = f'/acts/{indice}'
    dados = _montar_dados(extracao)
    ato = next((item for item in dados.atos if item.chave == chave), None)
    if ato is None:
        raise AtoInexistente(chave)
    linhas = importacao._linhas_por_chave(extracao)

    # Tipo: a MESMA resolução da gravação (escolha explícita > rótulo >
    # sugestão). O formulário recebe o número composto calculado abaixo pelo
    # mesmo gerador usado no POST manual.
    rotulo = analisar_rotulo(importacao._rotulo_efetivo(chave, linhas))
    tipo, _composto, _avisos = importacao._resolver_tipo_e_numero(
        ato, rotulo, documento,
    )
    tipo_codigo = tipo.tipo if tipo is not None else None

    ids_pessoas = {
        parte.pessoa_id for parte in ato.partes if parte.pessoa_id is not None
    }
    ids_cartorios = {
        cartorio_id for cartorio_id in (
            ato.cartorio_transmissao_id,
            (ato.origem or {}).get('cartorio_id'),
        ) if cartorio_id is not None
    }
    nomes_pessoas = _nomes(Pessoas, ids_pessoas)
    nomes_cartorios = _nomes(Cartorios, ids_cartorios)

    form_data = {}
    evidencias = {}

    def colocar(chave_da_linha, valor, chave_da_evidencia=None):
        """Escreve ``valor`` no input da linha e anexa a evidência dela."""
        texto = _como_texto(valor)
        if texto is None:
            return
        nome = input_do_campo(chave_da_linha, tipo_codigo)
        form_data[nome] = texto
        evidencia = _evidencia(
            linhas, chave_da_evidencia or chave_da_linha,
        )
        if evidencia is not None:
            evidencias[nome] = evidencia

    # Livro/folha do documento: só quando ele ainda não os tem — o
    # formulário trava o que já está definido (#218).
    flags = _flags_livro_folha_definidos(documento)
    if not flags['doc_livro_definido']:
        colocar('/document/livro', dados.documento.livro)
    if not flags['doc_folha_definida']:
        colocar('/document/folha', dados.documento.folha)

    colocar(f'{chave}/tipo_sugerido', str(tipo.pk) if tipo is not None else None)
    chave_do_numero, numero = _numero_simples(chave, rotulo, ato)
    colocar(chave_do_numero, numero)
    composto = _numero_composto(tipo, numero, documento)
    if composto is not None:
        form_data['numero_lancamento'] = composto
    # O A3 pode trazer ``normalized: null`` com ``raw`` numérico: o ``raw``
    # só vira data quando casa 100% com um formato determinístico (nada é
    # inventado). Texto ambíguo/por extenso fica sem data.
    data = ato.data
    if data is None:
        campo_data = linhas.get(f'{chave}/data')
        data = data_do_raw(campo_data.raw if campo_data is not None else None)
    colocar(f'{chave}/data', data)
    # M3: área em m²/alqueires/ares não entra no input em hectares.
    area_em_outra_unidade = _area_em_outra_unidade(extracao, indice, linhas, chave)
    if area_em_outra_unidade is None:
        # #396: sempre 4 casas — `74.675` seria lido como ambíguo.
        colocar(f'{chave}/area', area_para_input(ato.area))
    colocar(f'{chave}/descricao', ato.descricao)
    colocar(f'{chave}/observacoes', ato.observacoes)
    forma_lida, titulo_lido, instrumento, houve_swap = _forma_e_titulo(
        ato.forma, ato.titulo,
    )
    forma, aviso_da_forma = forma_do_vocabulario(forma_lida)
    if houve_swap:
        colocar(f'{chave}/forma', forma, f'{chave}/titulo')
        colocar(f'{chave}/titulo', titulo_lido, f'{chave}/forma')
    else:
        colocar(f'{chave}/forma', forma)
        colocar(f'{chave}/titulo', titulo_lido)

    id_transmissao, nome_transmissao = _cartorio(
        ato.cartorio_transmissao_id, ato.cartorio_transmissao_nome,
        nomes_cartorios,
    )
    if id_transmissao:
        form_data['cartorio_transmissao'] = id_transmissao
    colocar(f'{chave}/cartorio_transmissao', nome_transmissao)
    colocar(f'{chave}/livro_transacao', ato.livro_transacao)
    colocar(f'{chave}/folha_transacao', ato.folha_transacao)
    data_transacao, pendencia_data = _data_transacao_do_instrumento(
        instrumento, ato.data_transacao,
    )
    colocar(f'{chave}/data_transacao', data_transacao)

    origens_separadas = _origens_separadas(
        ato, linhas, nomes_cartorios, evidencias,
    )
    transmitentes, adquirentes = _partes(ato, linhas, nomes_pessoas, evidencias)

    pendencias = _lidos_sem_campo(extracao, indice, ato)
    if area_em_outra_unidade is not None:
        # Antes dos avisos informativos: é a única que pede decisão.
        pendencias.insert(0, area_em_outra_unidade)
    if aviso_da_forma is not None:
        pendencias.append(aviso_da_forma)
    if houve_swap:
        pendencias.append({
            'motivo': MOTIVO_FORMA_TITULO_REINTERPRETADOS,
            'rotulo': ROTULO_FORMA_E_TITULO,
            'texto': TEXTO_FORMA_TITULO_REINTERPRETADOS.format(
                instrumento=titulo_lido, natureza=forma,
            ),
            'bloqueante': False,
        })
    if pendencia_data is not None:
        pendencias.append(pendencia_data)

    return {
        'form_data': form_data,
        'origens_separadas': origens_separadas,
        'transmitentes': transmitentes,
        'adquirentes': adquirentes,
        'evidencias': evidencias,
        'pendencias': pendencias,
    }


# Ciclo: ``origens``/``partes`` chamam ``input_do_campo`` (definido acima) e
# ``prefill_do_ato`` usa as funções deles. O import no FIM do módulo quebra
# o ciclo sem tocar nos corpos — e o ``__init__`` importa ``prefill`` antes
# de ``origens``/``partes``.
from .origens import _cartorio, _lidos_sem_campo, _origens_separadas  # noqa: E402
from .partes import _partes  # noqa: E402
