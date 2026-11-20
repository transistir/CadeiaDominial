"""``input_do_campo`` e ``prefill_do_ato``: o contrato do formulário.

``prefill_do_ato`` é o que a revisão consome por ato (``views/revisar``);
``input_do_campo`` é o mapa chave-da-linha → input, compartilhado pelas
evidências de origem e de partes.
"""

from dominial.models import Cartorios, Pessoas

from .. import importacao
from .areas import _area_em_outra_unidade
from ..destinos import _normalizar
from .erros import AtoInexistente
from .numeros import _numero_composto, _numero_simples
from ..revisao import _montar_dados
from ..rotulos import analisar_rotulo
from .texto import _como_texto, _evidencia, _nomes

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

    def colocar(chave_da_linha, valor):
        """Escreve ``valor`` no input da linha e anexa a evidência dela."""
        texto = _como_texto(valor)
        if texto is None:
            return
        nome = input_do_campo(chave_da_linha, tipo_codigo)
        form_data[nome] = texto
        evidencia = _evidencia(linhas, chave_da_linha)
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
    colocar(f'{chave}/data', ato.data)
    # M3: área em m²/alqueires/ares não entra no input em hectares.
    area_em_outra_unidade = _area_em_outra_unidade(extracao, indice, linhas, chave)
    if area_em_outra_unidade is None:
        colocar(f'{chave}/area', ato.area)
    colocar(f'{chave}/descricao', ato.descricao)
    colocar(f'{chave}/observacoes', ato.observacoes)
    colocar(f'{chave}/forma', ato.forma)
    colocar(f'{chave}/titulo', ato.titulo)

    id_transmissao, nome_transmissao = _cartorio(
        ato.cartorio_transmissao_id, ato.cartorio_transmissao_nome,
        nomes_cartorios,
    )
    if id_transmissao:
        form_data['cartorio_transmissao'] = id_transmissao
    colocar(f'{chave}/cartorio_transmissao', nome_transmissao)
    colocar(f'{chave}/livro_transacao', ato.livro_transacao)
    colocar(f'{chave}/folha_transacao', ato.folha_transacao)
    colocar(f'{chave}/data_transacao', ato.data_transacao)

    origens_separadas = _origens_separadas(
        ato, linhas, nomes_cartorios, evidencias,
    )
    transmitentes, adquirentes = _partes(ato, linhas, nomes_pessoas, evidencias)

    pendencias = _lidos_sem_campo(extracao, indice, ato)
    if area_em_outra_unidade is not None:
        # Antes dos avisos informativos: é a única que pede decisão.
        pendencias.insert(0, area_em_outra_unidade)

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
