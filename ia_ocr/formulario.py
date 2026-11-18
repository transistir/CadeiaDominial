"""Pré-preenchimento do formulário de lançamento pela revisão (I-14 / #341, fase 1).

A revisão da extração vira o próprio formulário de lançamento — um ato por
aba, sem gravar nada até o usuário salvar AQUELE ato. Este módulo é o que o
formulário consome: ``prefill_do_ato`` lê o estado ATUAL das linhas do ato
``N`` (``revisao._montar_dados``, sem exigir revisão concluída) e devolve, no
formato que os templates do formulário manual já esperam, o que preencher:

- ``form_data``: o mesmo dicionário que ``_form_data_do_post`` monta — chaves
  com o NOME DO INPUT, valores sempre em ``str`` (o template compara
  ``form_data.tipo_lancamento == tipo.id|stringformat:"s"``). Só entra chave
  com valor lido: ausência é "nada lido", nunca ``None`` (que o template
  imprimiria como ``None``);
- ``origens_separadas``: o formato de ``_origens_separadas_do_post``;
- ``transmitentes`` / ``adquirentes``: a lista de ``{'id', 'nome'}`` do
  ``_pessoa_form.html``;
- ``evidencias``: ``{input: {pagina, trecho, confianca_baixa}}`` — a chave é o
  nome do input; nos inputs repetidos (``transmitente_nome[]``,
  ``cartorio_origem_nome[]``...) é o nome SEM os colchetes mais a posição na
  lista, ``transmitente_nome[0]``. O trecho sai mascarado (CPF/RG);
- ``pendencias``: avisos do que foi lido e não entrou no formulário: o que
  não tem campo no lançamento (informativo) e a área lida em unidade que não
  é hectare (decisão do revisor: o input é em ha e nada é convertido em
  silêncio). Nunca citam a chave ``/acts/...``.

Nada daqui grava ou cria cadastro: cartório que a revisão marcou "criar
novo" entra só com o nome e o id vazio — o bloqueio é da fase 2.

O número composto (``numero_lancamento``, "R1 M237") sai do MESMO gerador do
POST manual (``LancamentoFormService._gerar_numero_lancamento``, com a sigla
da matrícula): o JS do formulário manual só preenche esse campo com a sigla
pura ("M237") — e, em modo de edição, apaga o número simples a partir dele —,
então o HTML já tem que chegar com o composto certo (#341, M1).
"""

import re
from datetime import date
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace

from dominial.models import Cartorios, Pessoas
from dominial.services.lancamento_form_service import LancamentoFormService
from dominial.utils.documento_identidade_utils import normalizar_numero_documento

from . import importacao, revisao
from .destinos import _normalizar
from .revisao import MOTIVO_BAIXA_CONFIANCA, MOTIVO_UNIDADE_AREA, _montar_dados
from .rotulos import analisar_rotulo

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

MOTIVO_LIDO_SEM_CAMPO = 'lido_sem_campo'
TEXTO_LIDO_SEM_CAMPO = 'lido, sem campo no lançamento'

# Área lida em unidade que não é hectare: o input é em ha, então o valor NÃO
# entra nele (120 m² viraria 120 ha). Mesmo motivo estável da revisão antiga.
MOTIVO_AREA_EM_OUTRA_UNIDADE = MOTIVO_UNIDADE_AREA
ROTULO_DA_AREA = 'Área'
# Enum ``unidade`` do A3 → como o revisor lê a unidade.
UNIDADES_DE_AREA = {'ha': 'ha', 'm2': 'm²', 'alqueires': 'alqueires', 'ares': 'ares'}
TEXTO_AREA_EM_OUTRA_UNIDADE = (
    '{lido} no documento{complemento} — o campo Área (em hectares) ficou '
    'vazio: converta o valor para hectares e preencha o campo, ou preencha '
    'manualmente. Nada é convertido sem a sua decisão.'
)

# Folhas do A3 que o formulário não tem (``revisao.LINHAS_IGNORADAS``, #328):
# a linha não existe, mas o payload segue com o valor lido.
_ROTULO_DA_FOLHA_IGNORADA = {
    'valor_transacao': 'Valor da transação',
    'detalhes': 'Detalhes',
}

# Separa o tipo (M/T) do número no texto da origem. Igual ao critério de
# ``_origens_separadas_do_post``, mas o número aceita o ponto de milhar que o
# OCR traz (``M42.718``): com ``\d+`` o input visível perdia o ``.718`` e o
# usuário salvava outra matrícula sem perceber (#341, fase 2). Mesma forma de
# "número puro" do parser de rótulos (``importacao._NUMERO_SIMPLES``).
TEXTO_DA_ORIGEM = re.compile(r'^([MT])(\d+(?:\.\d+)*)')


class AtoInexistente(LookupError):
    """O índice não é de um ato incluído da revisão (inexistente ou descartado)."""

    def __init__(self, chave):
        self.chave = chave
        super().__init__(chave)


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


def _nomes(modelo, ids):
    """``{pk: nome}`` dos cadastros — uma query, nenhuma sem ids."""
    if not ids:
        return {}
    return dict(modelo.objects.filter(pk__in=ids).values_list('pk', 'nome'))


def _como_texto(valor):
    """Valor tipado → texto do input; vazio (ou só espaços) → ``None``."""
    if valor is None:
        return None
    if isinstance(valor, date):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        # 'f' evita a notação científica que o input de área não aceita.
        return format(valor, 'f')
    texto = str(valor)
    return texto if texto.strip() else None


def _evidencia(linhas, chave):
    """``{pagina, trecho, confianca_baixa}`` da linha, ou ``None`` sem evidência."""
    # Importação tardia: ``views`` vai consumir este módulo (fase 2) e a
    # máscara de CPF/RG mora lá.
    from .views import _mascarar_evidencia

    campo = linhas.get(chave)
    if campo is None or campo.status_revisao == 'descartado':
        return None
    trecho = _mascarar_evidencia(campo.evidencia_trecho or '')
    if campo.evidencia_pagina is None and not trecho:
        return None
    return {
        'pagina': campo.evidencia_pagina,
        'trecho': trecho,
        'confianca_baixa': MOTIVO_BAIXA_CONFIANCA in (campo.motivos_revisao or ()),
    }


def _numero_simples(chave, rotulo, ato):
    """``(chave da linha, número do ato sem prefixo)`` para o input simples.

    O número é o do RÓTULO (``'R-5'`` → ``'5'``), o que o A3 sempre traz.
    Rótulo sem número de ato (referência de matrícula ``M-3-14511``, texto
    não reconhecido) cai no ``numero_lancamento`` da revisão — a mesma
    leitura da gravação, que só aceita ali um número de ato válido.
    """
    if rotulo.reconhecido and not rotulo.eh_matricula and rotulo.numero:
        return f'{chave}/rotulo', rotulo.numero
    return (
        f'{chave}/numero_lancamento',
        importacao._numero_de_ato_do_campo(ato.numero_lancamento),
    )


def _numero_composto(tipo, numero, documento):
    """Número completo ("R1 M237"), ou ``None`` quando não há o que compor.

    Chama o gerador do POST do formulário manual com a sigla da matrícula
    (``documento.numero``, o mesmo que o template põe em ``sigla_matricula``)
    — não repete a regra aqui. Só os três tipos que o JS do formulário
    compõe (registro, averbação, início de matrícula); registro/averbação
    sem número de ato ficam sem composto, como no formulário manual, onde o
    revisor ainda vai digitar o número simples.
    """
    if tipo is None or tipo.tipo not in ('registro', 'averbacao', 'inicio_matricula'):
        return None
    if tipo.tipo != 'inicio_matricula' and not numero:
        return None
    pedido = SimpleNamespace(POST={'sigla_matricula': documento.numero or ''})
    composto = LancamentoFormService._gerar_numero_lancamento(
        numero or '', tipo, pedido,
    )
    return composto.strip() or None


def _numero_legivel(normalizado):
    """Decimal canônico → "120" / "12,5" (pt-BR, sem zeros à direita); senão ''."""
    try:
        numero = Decimal(str(normalizado))
    except (InvalidOperation, ValueError):
        return ''
    if not numero.is_finite():
        return ''
    return format(numero.normalize(), 'f').replace('.', ',')


def _unidade_da_area_no_payload(extracao, indice):
    """Código da unidade (``m2``, ``alqueires``...) da área do ato, ou ``None``."""
    payload = extracao.payload_servico or extracao.payload or {}
    atos = payload.get('acts') or []
    ato = atos[indice] if indice < len(atos) else {}
    folha = ato.get('area') if isinstance(ato, dict) else None
    unidade = folha.get('unidade') if isinstance(folha, dict) else None
    return unidade if isinstance(unidade, str) else None


def _area_em_outra_unidade(extracao, indice, linhas, chave):
    """Pendência da área lida em unidade que não é hectare; ``None`` se não há.

    O input do formulário é em hectares. A linha de área marcada com
    ``unidade_area`` (e ainda sem conversão confirmada) traz o número na
    unidade do documento: colocá-lo no input trocaria a unidade em silêncio
    — 120 m² seriam gravados como 120 ha (#341, M3). Aqui o valor original
    vira pendência com a unidade; quem converte (ou preenche à mão) é o
    revisor. Linha descartada, ou convertida na revisão (``area_convertida``,
    cujo ``valor_final`` já está em ha), segue o caminho normal.
    """
    campo = linhas.get(f'{chave}/area')
    if (
        campo is None or campo.status_revisao == 'descartado'
        or campo.area_convertida
        or MOTIVO_UNIDADE_AREA not in (campo.motivos_revisao or ())
    ):
        return None
    numero = _numero_legivel(campo.normalized)
    unidade = UNIDADES_DE_AREA.get(_unidade_da_area_no_payload(extracao, indice))
    if numero:
        lido = f'{numero} {unidade}' if unidade else numero
        complemento = '' if unidade else ' (unidade não identificada)'
    else:
        # Sem canônico (normalização inválida): o texto como foi lido.
        lido = (campo.raw or '').strip()
        complemento = ''
    if not lido:
        return None
    return {
        'motivo': MOTIVO_AREA_EM_OUTRA_UNIDADE,
        'rotulo': ROTULO_DA_AREA,
        'texto': TEXTO_AREA_EM_OUTRA_UNIDADE.format(
            lido=lido, complemento=complemento,
        ),
        'bloqueante': False,
    }


def _cartorio(cartorio_id, nome_da_linha, nomes):
    """``(id, nome)`` em texto para os inputs de cartório.

    Cadastro escolhido: o NOME DO CADASTRO (é o que o autocomplete grava no
    input) com o id. Sem escolha — ou "criar novo" —, só o nome lido e o id
    vazio: nenhum cadastro é inventado aqui.
    """
    nome = nomes.get(cartorio_id) if cartorio_id is not None else None
    if nome is not None:
        return str(cartorio_id), nome
    return '', (nome_da_linha or '').strip()


def _texto_da_origem(origem, numero):
    """``'M123'``/``'T45'``: prefixo do tipo documental + número normalizado.

    A mesma montagem da gravação (``importacao._importar_ato``). Número
    vazio ou incompatível com o tipo (``'T45'`` numa matrícula) não vira
    texto: o campo fica vazio e quem decide é o revisor.
    """
    if not numero:
        return ''
    tipo_documento = importacao._tipo_documento_da_origem(origem, numero)
    try:
        normalizado = normalizar_numero_documento(numero, tipo_documento)
    except (TypeError, ValueError):
        return ''
    return importacao.PREFIXO_TIPO_DOCUMENTO[tipo_documento] + normalizado


def _origens_separadas(ato, linhas, nomes_cartorios, evidencias):
    """``origens_separadas`` no formato de ``_origens_separadas_do_post``.

    O A3 tem UMA origem por ato; sem nada a preencher a lista é vazia, como
    no re-render do POST. O fim de cadeia fica desligado (decisão humana).
    """
    origem = ato.origem
    if not origem:
        return []
    numero = (origem.get('numero') or '').strip()
    texto = _texto_da_origem(origem, numero)
    id_cartorio, nome_cartorio = _cartorio(
        origem.get('cartorio_id'), origem.get('cartorio_nome'),
        nomes_cartorios,
    )
    livro = (origem.get('livro') or '').strip()
    folha = (origem.get('folha') or '').strip()
    if not any((texto, id_cartorio, nome_cartorio, livro, folha)):
        return []

    for sufixo, preenchido in (
        ('tipo_documento', texto), ('numero', texto),
        ('cartorio', nome_cartorio), ('livro', livro), ('folha', folha),
    ):
        if not preenchido:
            continue
        chave = f'{ato.chave}/origem/{sufixo}'
        evidencia = _evidencia(linhas, chave)
        if evidencia is not None:
            evidencias[f'{input_do_campo(chave)}[0]'] = evidencia

    achado = TEXTO_DA_ORIGEM.match(texto)
    return [{
        'texto': texto,
        'index': 0,
        'tipo_origem': achado.group(1) if achado else '',
        'numero_origem': achado.group(2) if achado else '',
        'cartorio_nome': nome_cartorio,
        'cartorio_id': id_cartorio,
        'livro': livro,
        'folha': folha,
        'fim_cadeia': False,
        'tipo_fim_cadeia': '',
        'classificacao_fim_cadeia': '',
        'especificacao_fim_cadeia': '',
        'sigla_patrimonio_publico': '',
        'info_adicional_fim_cadeia': '',
        'is_destacamento_publico': False,
    }]


def _partes(ato, linhas, nomes_pessoas, evidencias):
    """``(transmitentes, adquirentes)`` no formato do ``_pessoa_form.html``.

    Cadastro escolhido: nome e id do CADASTRO — o serviço do formulário só
    reaproveita a pessoa vinculada quando o texto digitado é igual ao nome
    dela. Sem escolha (ou "criar novo"): o nome lido, id vazio. CPF/RG não
    entram (regra I-11f); ver ``_lidos_sem_campo``.
    """
    listas = {'transmitente': [], 'adquirente': []}
    for parte in ato.partes:
        lista = listas.get(parte.papel)
        if lista is None:
            continue
        nome_do_cadastro = (
            nomes_pessoas.get(parte.pessoa_id)
            if parte.pessoa_id is not None else None
        )
        nome = (nome_do_cadastro or parte.nome or '').strip()
        if not nome:
            continue
        lista.append({
            'id': str(parte.pessoa_id) if nome_do_cadastro else '',
            'nome': nome,
        })
        chave_do_nome = f'{parte.chave}/nome'
        evidencia = _evidencia(linhas, chave_do_nome)
        if evidencia is not None:
            nome_do_input = input_do_campo(chave_do_nome, papel=parte.papel)
            evidencias[f'{nome_do_input}[{len(lista) - 1}]'] = evidencia
    return listas['transmitente'], listas['adquirente']


def _lidos_sem_campo(extracao, indice, ato):
    """Avisos do que foi lido e não tem lugar no lançamento (só informativos).

    Data da origem, CPF/RG das partes, valor da transação e detalhes: nada
    disso entra em ``form_data``. O aviso leva o rótulo de negócio e nunca a
    chave da linha; CPF/RG sequer têm o valor repetido aqui.
    """
    rotulos = []
    if ato.origem and ato.origem.get('data') is not None:
        rotulos.append('Data da origem')
    if any(parte.cpf or parte.rg for parte in ato.partes):
        rotulos.append('CPF/RG das partes')

    payload = extracao.payload_servico or extracao.payload or {}
    atos_payload = payload.get('acts') or []
    ato_payload = atos_payload[indice] if indice < len(atos_payload) else {}
    for nome, rotulo in _ROTULO_DA_FOLHA_IGNORADA.items():
        folha = ato_payload.get(nome) if isinstance(ato_payload, dict) else None
        if revisao._eh_folha(folha) and any(
            isinstance(valor, str) and valor.strip()
            for valor in (folha.get('normalized'), folha.get('raw'))
        ):
            rotulos.append(rotulo)

    return [
        {
            'motivo': MOTIVO_LIDO_SEM_CAMPO,
            'rotulo': rotulo,
            'texto': TEXTO_LIDO_SEM_CAMPO,
            'bloqueante': False,
        }
        for rotulo in rotulos
    ]
