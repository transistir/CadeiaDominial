"""Campos obrigatórios, rótulos e textos de pendência."""

import re

from django.utils.text import slugify

from .estruturas import (
    MOTIVO_CRIAR_NOVO_SEM_NOME, _CHAVE_OBRIGATORIA_ATO, _OBRIGATORIOS_ATO,
    _OBRIGATORIOS_DOCUMENTO,
)


def rotulo_efetivo(chave, linhas):
    """Rótulo que decide tipo/número: ``valor_final``, ``normalized`` ou ``raw``.

    P1 (#322 rodadas 4–6): a folha ``/acts/N/rotulo`` vence a linha
    estrutural; ``valor_final`` vazio (revisor limpou o campo) não decide
    nada; linha DESCARTADA é pulada candidato a candidato (folha →
    estrutural), nunca volta ``None`` no meio. Esta é a leitura da
    importação (``importacao._rotulo_efetivo`` delega para cá) e da
    revisão (P1-2, rodada 7): uma única regra decide o tipo nos dois
    caminhos.
    """
    for candidata in (f'{chave}/rotulo', chave):
        campo = linhas.get(candidata)
        if campo is None or campo.status_revisao == 'descartado':
            continue
        if campo.valor_final:
            return campo.valor_final
        if campo.normalized is not None:
            return campo.normalized
        if campo.raw is not None:
            return campo.raw
    return None

def campo_obrigatorio(chave: str) -> bool:
    """A linha é obrigatória (documento ou ato) e não pode ser descartada."""
    if chave.startswith('/document/'):
        return chave[len('/document/'):] in _OBRIGATORIOS_DOCUMENTO
    achado = _CHAVE_OBRIGATORIA_ATO.fullmatch(chave)
    return bool(achado) and achado.group(1) in _OBRIGATORIOS_ATO


_ROTULO_PENDENCIA = {
    'nenhum_ato': 'Nenhum ato reconhecido neste documento',
    'obrigatorio_ausente': 'Campo obrigatório não preenchido',
    'escolha_pendente': 'Cadastro não escolhido',
    'baixa_confianca': 'Confira este valor (baixa confiança)',
    'trecho_ausente': 'Sem trecho de origem',
    'normalizacao_invalida': 'Valor não reconhecido',
    'unidade_area': 'Área em unidade não reconhecida',
    MOTIVO_CRIAR_NOVO_SEM_NOME: 'Informe o nome do novo cartório',
    'revisao_pendente': 'Confira este valor',
    'decisao_perdida': 'A decisão anterior não foi aplicada',
    'match_invalidado': 'O cadastro escolhido não corresponde mais ao texto',
    'valor_incompativel_destino': 'Valor não aceito neste campo',
    'valor_acima_do_limite_destino': 'Valor acima do limite deste campo',
}
_ACAO_PENDENCIA = {
    'escolha_pendente': 'escolha o cadastro correspondente',
    'trecho_ausente': 'confira no documento',
    'normalizacao_invalida': 'corrija o valor',
    'unidade_area': 'confirme a conversão',
    'revisao_pendente': 'confirme ou corrija',
    'decisao_perdida': 'revise o campo',
    'match_invalidado': 'escolha novamente',
    'valor_incompativel_destino': 'corrija o valor',
    'valor_acima_do_limite_destino': 'reduza o valor',
}
_ACAO_OBRIGATORIO = {
    'tipo': 'informe o tipo do documento',
    'tipo_sugerido': 'informe o tipo do lançamento',
    'data': 'informe a data',
    'cartorio': 'escolha o cartório',
    'cartorio_transmissao': 'escolha o cadastro do cartório da transmissão',
}

# Onde está o campo citado pela pendência (Greptile P2 #317): índices 1-based.
_LOCAL_DOCUMENTO = {
    'tipo': 'tipo',
    'data': 'data',
    'cartorio': 'cartório',
}
_LOCAL_ATO = {
    'data': 'data',
    'tipo_sugerido': 'tipo',
    'cartorio_transmissao': 'cartório de transmissão',
    'origem/cartorio': 'cartório de origem',
    'valor_transacao': 'valor',
}
_CHAVE_ATO_LOCAL = re.compile(r'/acts/(\d+)(?:/(.+))?')
_CHAVE_PARTE_LOCAL = re.compile(r'partes/(\d+)(?:/(.+))?')


def _rotulo_fallback(caminho: str) -> str:
    """Último segmento com ``_`` por espaço — nunca quebra."""
    return caminho.rsplit('/', 1)[-1].replace('_', ' ')


def _local_de_ato(resto: str | None) -> str:
    """Rótulo do resto do caminho de um ato (``partes`` é 1-based)."""
    if not resto:
        return ''
    partes = _CHAVE_PARTE_LOCAL.fullmatch(resto)
    if partes is not None:
        indice, sub = partes.groups()
        local = f'parte {int(indice) + 1}'
        rotulo = _local_de_ato(sub)
        if rotulo:
            local = f'{local} — {rotulo}'
        return local
    mapeado = _LOCAL_ATO.get(resto)
    if mapeado is not None:
        return mapeado
    return _rotulo_fallback(resto)


def _local_da_chave(chave) -> str:
    """Identificação legível do campo citado pela pendência.

    Chave ausente ou não-string (payload cru/legado) → ``''``, sem exceção;
    resto vazio depois de ``/acts/{i}/`` ou ``/document/`` → rótulo sem
    travessão pendurado.
    """
    if not isinstance(chave, str):
        return ''
    if chave.startswith('/document/'):
        resto = chave[len('/document/'):]
        rotulo = _LOCAL_DOCUMENTO.get(resto) or _rotulo_fallback(resto)
        return f'Documento — {rotulo}' if rotulo else 'Documento'
    if chave == '/acts':
        return 'Documento — atos'
    achado = _CHAVE_ATO_LOCAL.fullmatch(chave.rstrip('/'))
    if achado is not None:
        indice, resto = achado.groups()
        local = f'Ato {int(indice) + 1}'
        rotulo = _local_de_ato(resto)
        if rotulo:
            local = f'{local} — {rotulo}'
        return local
    return _rotulo_fallback(chave)


def descrever_pendencia(item: dict, sem_atos_liberado: bool = False) -> dict:
    """Texto de negócio de uma pendência; chave/motivo crus seguem para suporte.

    Chave ausente/não-string (payload cru/legado) não levanta exceção: o
    texto sai sem local e a ação cai no genérico.
    """
    chave, motivo = item['chave'], item['motivo']
    texto_chave = chave if isinstance(chave, str) else ''
    if motivo == 'obrigatorio_ausente':
        acao = _ACAO_OBRIGATORIO.get(
            texto_chave.rsplit('/', 1)[-1], 'preencha o campo',
        )
    elif motivo == 'nenhum_ato':
        acao = 'confirmar que não há atos' if sem_atos_liberado else ''
    else:
        acao = _ACAO_PENDENCIA.get(motivo, '')
    rotulo = _ROTULO_PENDENCIA.get(motivo)
    if rotulo is None:
        # Motivo fora do mapa: o código cru fica só no <details> (``motivo``).
        rotulo, acao = 'Pendência a revisar', 'revise o campo'
    # Âncora da pendência (I-11a #321, §5): o ``id`` do input do campo na
    # tela — ``campo-<chave slugificada>``, o MESMO que o template gera.
    # ``nenhum_ato`` aponta para o checkbox de confirmação, que só existe
    # com a flag ligada; sem ela (ou sem chave) não há link.
    if motivo == 'nenhum_ato':
        alvo = 'campo-sem-atos' if sem_atos_liberado else None
    elif isinstance(chave, str) and chave:
        alvo = 'campo-' + slugify(chave)
    else:
        alvo = None
    return {
        'chave': chave,
        'motivo': motivo,
        'local': _local_da_chave(chave),
        'rotulo': rotulo,
        'acao': acao,
        'alvo': alvo,
    }

# ---------------------------------------------------------------------------
# Tela de revisão como formulário de lançamento (I-11a / #321)
# ---------------------------------------------------------------------------

# Rótulo de negócio pela FOLHA da chave (último segmento): o formulário de
# lançamento manda — a chave crua nunca vira rótulo visível. ``partes`` e
# ``origem`` rotulam os GRUPOS da seção do ato, não uma linha.
ROTULOS_CAMPO = {
    'tipo_sugerido': 'Tipo do lançamento',
    'numero_lancamento': 'Número',
    'data': 'Data',
    'forma': 'Forma',
    'titulo': 'Título',
    'descricao': 'Descrição',
    'area': 'Área (ha)',
    'observacoes': 'Observações',
    'cartorio_transmissao': 'Cartório da transmissão',
    'livro_transacao': 'Livro da transmissão',
    'folha_transacao': 'Folha da transmissão',
    'data_transacao': 'Data da transmissão',
    'livro': 'Livro',
    'folha': 'Folha',
    'imovel_descricao': 'Descrição do imóvel',
    'numero': 'Número do documento',
    'cartorio': 'Cartório',
    'tipo': 'Tipo do documento',
    'tipo_documento': 'Tipo do documento',
    'nome': 'Nome',
    'partes': 'Partes',
    'origem': 'Origem',
    # Folhas fora do formulário (seção "Outros dados lidos") conhecidas do
    # A3: rótulo humano em vez do fallback mecânico.
    'cri_atual': 'CRI atual',
    'rotulo': 'Rótulo do ato',
    'eh_inicio_matricula': 'Início de matrícula',
    'valor': 'Documento da parte',
    'indicio_fim_cadeia': 'Indício de fim de cadeia',
    'origem_publica_sugerida': 'Origem pública sugerida',
    'classificacao_sugerida': 'Classificação sugerida',
}

# Campos que o formulário de lançamento tem (§2 do #321): abrem linha na
# seção própria; todo o resto (``cri_atual``, ``rotulo``,
# ``eh_inicio_matricula``, ``closure/*``, desconhecidos) vai para "Outros
# dados lidos" — e as folhas de ``LINHAS_IGNORADAS`` nem isso (#328).
CAMPOS_DO_FORMULARIO_DOCUMENTO = (
    'tipo', 'numero', 'data', 'cartorio', 'livro', 'folha',
    'imovel_descricao', 'area',
)
CAMPOS_DO_FORMULARIO_ATO = (
    'tipo_sugerido', 'numero_lancamento', 'data', 'forma', 'titulo',
    'descricao', 'area', 'partes', 'cartorio_transmissao',
    'livro_transacao', 'folha_transacao', 'data_transacao', 'origem', 'observacoes',
)

_ORDEM_DOCUMENTO = {
    nome: ordem for ordem, nome in enumerate(CAMPOS_DO_FORMULARIO_DOCUMENTO)
}
_ORDEM_ATO = {
    nome: ordem for ordem, nome in enumerate(CAMPOS_DO_FORMULARIO_ATO)
}
_ORDEM_PARTE = {
    None: -1,
    'nome': 0,
    'documento_identificacao/tipo': 1,
    'documento_identificacao/valor': 2,
}
_ORDEM_ORIGEM = {
    'cartorio': 0, 'tipo_documento': 1, 'numero': 2, 'livro': 3,
    'folha': 4, 'data': 5,
}
_TEXTO_NAO_RECONHECIDO = {
    'vazio': 'rótulo vazio',
    'sem_prefixo': 'não começa com R ou Av',
    'prefixo_desconhecido': 'prefixo desconhecido',
    'sem_numero': 'sem número do ato',
}
_TEXTO_LONGO = frozenset(
    {'descricao', 'observacoes', 'imovel_descricao'},
)

# Linha estrutural no fim da chave: ``/acts/{n}`` ou ``.../partes/{m}``.
_ESTRUTURAL_NUMERADO = re.compile(r'(?:^|/)(acts|partes)/(\d+)$')
_PARTE_NUMERADA = re.compile(r'partes/(\d+)(?:/(.*))?')


def rotulo_de_campo(chave) -> str:
    """Rótulo de negócio da linha: ``ROTULOS_CAMPO`` pela folha da chave.

    Linha estrutural de ato (``/acts/{n}``) e de parte
    (``/acts/{n}/partes/{m}``) não têm folha nominal: viram ``Ato {n+1}``
    e ``Parte {m+1}``. Folha desconhecida cai no fallback — último
    segmento com ``_`` por espaço e inicial maiúscula, NUNCA a chave
    inteira. Chave ausente/não-string → ``''`` (a tela não derruba).
    """
    if not isinstance(chave, str) or not chave:
        return ''
    estrutural = _ESTRUTURAL_NUMERADO.search(chave)
    if estrutural is not None:
        nome, numero = estrutural.groups()
        artigo = 'Ato' if nome == 'acts' else 'Parte'
        return f'{artigo} {int(numero) + 1}'
    folha = chave.rstrip('/').rsplit('/', 1)[-1]
    if folha in ROTULOS_CAMPO:
        return ROTULOS_CAMPO[folha]
    if not folha:
        return ''
    texto = folha.replace('_', ' ')
    return texto[:1].upper() + texto[1:]


def _ordem_no_formulario_do_ato(resto):
    """Chave de ordenação da linha na seção do ato; ``None`` se não é campo.

    A ordem é a do formulário (§2): ``tipo_sugerido`` … ``observacoes``,
    com ``partes/{m}`` ordenada por índice NUMÉRICO (a ordenação por chave
    em texto colocaria ``partes/10`` antes de ``partes/2``) e ``origem``
    na ordem cartório → documento → número → livro → folha → data.
    """
    nome = resto.split('/', 1)[0]
    ordem = _ORDEM_ATO.get(nome)
    if ordem is None or ('/' in resto and nome not in ('partes', 'origem')):
        return None
    if nome == 'partes':
        achado = _PARTE_NUMERADA.fullmatch(resto)
        if achado is None:
            return (ordem, 10**6, 999, resto)
        indice, sub = achado.groups()
        return (ordem, int(indice), _ORDEM_PARTE.get(sub, 99), sub or '')
    if nome == 'origem':
        sub = resto[len('origem/'):]
        return (ordem, _ORDEM_ORIGEM.get(sub, 99), resto, '')
    return (ordem, 0, resto, '')
