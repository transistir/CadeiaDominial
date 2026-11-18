"""Revisão por ato no formulário de lançamento (I-14 / #341, fase 2).

A tela de revisão é o PRÓPRIO formulário de lançamento, um ato por vez. Este
módulo reúne o que a view precisa além do pré-preenchimento (``formulario``):

- ``atos_da_revisao``: as abas da sidebar. O estado de cada ato sai do banco
  (``ImportacaoIA`` do lançamento daquele ato), nunca de uma coluna nova;
- rascunho por ato na SESSÃO (``guardar_rascunho`` e companhia): navegar entre
  atos não escreve nada no banco além de ``django_session``;
- ``estado_do_formulario``: reconstrói ``form_data``/origens/partes a partir de
  um POST (rascunho ou re-render de erro) reaproveitando os helpers do
  formulário manual — o mesmo caminho que o ``novo_lancamento`` usa;
- ``salvar_ato``: o ÚNICO caminho de gravação. Chama
  ``LancamentoService.criar_lancamento_completo`` com o mesmo ``request`` do
  formulário manual (nenhuma regra de duplicidade ou de validação é
  reimplementada aqui) e, na mesma transação, registra os vínculos de
  auditoria no formato da importação.
"""

from dataclasses import dataclass, field
from types import SimpleNamespace

from django.db import transaction
from django.http import QueryDict

from dominial.models import Cartorios, DocumentoDigital
from dominial.services.cache_service import CacheService
from dominial.services.lancamento_origem_service import LancamentoOrigemService
from dominial.services.lancamento_service import LancamentoService
from dominial.views.lancamento_views import (
    _form_data_do_post, _origens_separadas_do_post,
)

from . import estados, importacao, revisao, services
from .formulario import TEXTO_DA_ORIGEM
from .models import ImportacaoIA
from .rotulos import analisar_rotulo

ESTADO_PENDENTE = 'pendente'
ESTADO_IMPORTADO = 'importado'

MOTIVO_TRANSICAO = 'revisao_formulario'

# Chave da sessão: {extracao.pk: {indice: {input: [valores]}}}. Só os últimos
# ``LIMITE_EXTRACOES_NO_RASCUNHO`` documentos em revisão ficam guardados.
CHAVE_SESSAO = 'ia_ocr_rascunhos'
LIMITE_EXTRACOES_NO_RASCUNHO = 3
# Campos do POST que nunca entram no rascunho: o token CSRF é do pedido, e o
# destino da navegação é uma instrução, não um dado do ato.
FORA_DO_RASCUNHO = frozenset({'csrfmiddlewaretoken', '_ir_para'})

MENSAGEM_JOB_FORA_DE_REVISAO = (
    'Esta extração não está mais em revisão. Nada foi gravado.'
)
MENSAGEM_ATO_FORA_DA_REVISAO = (
    'Este ato não faz mais parte da revisão. Nada foi gravado.'
)
MENSAGEM_CARTORIO_NAO_CADASTRADO = (
    "❌ O cartório da transmissão '{nome}' não está cadastrado. Selecione um "
    'cartório da lista ou cadastre-o antes de salvar. Nada foi gravado.'
)

_PREFIXO_DA_ABA = {'registro': 'R', 'averbacao': 'Av'}


@dataclass
class Resultado:
    """O que aconteceu com o POST de salvar o ato.

    ``situacao``: ``salvo`` | ``invalido`` (o service recusou; nada gravado) |
    ``duplicata`` (origem já existe em outra cadeia; nada gravado) |
    ``ja_salvo`` | ``recusado`` (job/ato fora da revisão).
    """

    situacao: str
    mensagem: str = ''
    mensagem_origens: str | None = None
    lancamento: object = None
    lancamento_id: int | None = None
    # Índices dos atos que continuam pendentes depois deste POST, na ordem
    # da revisão. Vazio com ``salvo`` = a revisão acabou.
    restantes: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Atos e abas
# ---------------------------------------------------------------------------

def atos_da_revisao(extracao, dados=None, linhas=None):
    """As abas da revisão, na ordem do A3: ``[{indice, chave, posicao, rotulo,
    estado, lancamento_id}]``.

    ``importado`` = existe ``ImportacaoIA`` de um lançamento ATUAL (não
    excluído) para a linha do ato NESTA extração. Lançamento excluído depois
    deixa o rastro mas volta o ato a ``pendente`` — o revisor pode salvá-lo
    de novo. Só lê o banco.
    """
    dados = dados if dados is not None else revisao._montar_dados(extracao)
    linhas = linhas if linhas is not None else importacao._linhas_por_chave(extracao)
    salvos = dict(
        ImportacaoIA.objects.filter(
            ocr_job_id=extracao.ocr_job_id, modelo='Lancamento',
            campo__extracao_id=extracao.pk, lancamento__isnull=False,
        ).values_list('campo__chave', 'lancamento_id')
    )
    atos = []
    for posicao, ato in enumerate(dados.atos, start=1):
        indice = int(ato.chave.rsplit('/', 1)[1])
        lancamento_id = salvos.get(ato.chave)
        atos.append({
            'indice': indice,
            'chave': ato.chave,
            'posicao': posicao,
            'rotulo': _rotulo_da_aba(ato, linhas, indice),
            'estado': ESTADO_IMPORTADO if lancamento_id else ESTADO_PENDENTE,
            'lancamento_id': lancamento_id,
        })
    return atos


def _rotulo_da_aba(ato, linhas, indice):
    """``R5``/``Av3``/``Abertura`` — o mesmo rótulo efetivo que decide o tipo."""
    analisado = analisar_rotulo(
        (revisao.rotulo_efetivo(ato.chave, linhas) or '').strip(),
    )
    if analisado.reconhecido and not analisado.eh_matricula and analisado.numero:
        prefixo = _PREFIXO_DA_ABA.get(analisado.tipo)
        if prefixo:
            return f'{prefixo}{analisado.numero}'
    if 'inicio_matricula' in (ato.tipo, analisado.tipo):
        return 'Abertura'
    return f'Ato {indice + 1}'


def proximo_pendente(atos, depois_de=None):
    """Primeiro ato pendente depois do ``depois_de`` (índice), com volta ao início.

    ``None`` quando não resta nenhum. Sem ``depois_de``, o primeiro pendente.
    """
    pendentes = [ato for ato in atos if ato['estado'] == ESTADO_PENDENTE]
    if not pendentes:
        return None
    if depois_de is not None:
        posicoes = {ato['indice']: ato['posicao'] for ato in atos}
        a_partir = posicoes.get(depois_de)
        if a_partir is not None:
            for ato in pendentes:
                if ato['posicao'] > a_partir:
                    return ato
    return pendentes[0]


# ---------------------------------------------------------------------------
# Rascunho por ato (sessão)
# ---------------------------------------------------------------------------

def guardar_rascunho(request, extracao, indice):
    """Guarda o POST do ato na sessão — a única escrita de navegar entre atos."""
    post = {
        nome: list(valores) for nome, valores in request.POST.lists()
        if nome not in FORA_DO_RASCUNHO
    }
    rascunhos = request.session.get(CHAVE_SESSAO) or {}
    chave = str(extracao.pk)
    por_ato = rascunhos.pop(chave, {})
    por_ato[str(indice)] = post
    # Reinserido no fim: o mais recente fica, o mais antigo sai.
    rascunhos[chave] = por_ato
    while len(rascunhos) > LIMITE_EXTRACOES_NO_RASCUNHO:
        rascunhos.pop(next(iter(rascunhos)))
    request.session[CHAVE_SESSAO] = rascunhos


def rascunho_do_ato(request, extracao, indice):
    """O rascunho do ato como ``QueryDict`` (o formato do POST), ou ``None``."""
    bruto = (request.session.get(CHAVE_SESSAO) or {}).get(
        str(extracao.pk), {},
    ).get(str(indice))
    if not isinstance(bruto, dict) or not bruto:
        return None
    post = QueryDict(mutable=True)
    for nome, valores in bruto.items():
        post.setlist(nome, [str(valor) for valor in valores])
    return post


def limpar_rascunho(request, extracao, indice):
    """Descarta o rascunho do ato (salvo com sucesso)."""
    rascunhos = request.session.get(CHAVE_SESSAO) or {}
    por_ato = rascunhos.get(str(extracao.pk))
    if not por_ato or str(indice) not in por_ato:
        return
    del por_ato[str(indice)]
    if not por_ato:
        rascunhos.pop(str(extracao.pk), None)
    request.session[CHAVE_SESSAO] = rascunhos


# ---------------------------------------------------------------------------
# Estado do formulário a partir de um POST
# ---------------------------------------------------------------------------

def estado_do_formulario(post):
    """``form_data``/origens/partes do POST, pelos helpers do formulário manual.

    É o que o ``novo_lancamento`` faz no re-render de erro (#157/#161): aqui
    serve o rascunho da sessão e o erro do salvar. Os helpers do ``dominial``
    leem ``request.POST``; um objeto com só esse atributo basta.
    """
    pedido = SimpleNamespace(POST=post)
    origens = _origens_separadas_do_post(pedido)
    for origem in origens:
        # O helper manual só conhece número de dígitos puros e cortaria o
        # ``.718`` de ``M42.718`` no input visível; o texto oculto segue
        # inteiro e é ele que vai no POST.
        achado = TEXTO_DA_ORIGEM.match((origem.get('texto') or '').strip())
        if achado:
            origem['tipo_origem'], origem['numero_origem'] = achado.groups()
    return {
        'form_data': _form_data_do_post(pedido),
        'origens_separadas': origens,
        'transmitentes': _pessoas_do_post(post, 'transmitente'),
        'adquirentes': _pessoas_do_post(post, 'adquirente'),
    }


def _pessoas_do_post(post, papel):
    """``[{nome, id}]`` do POST — como o re-render de erro do formulário manual."""
    ids = post.getlist(f'{papel}[]')
    return [
        {'nome': nome.strip(), 'id': ids[posicao] if posicao < len(ids) else ''}
        for posicao, nome in enumerate(post.getlist(f'{papel}_nome[]'))
        if nome.strip()
    ]


# ---------------------------------------------------------------------------
# Salvar o ato
# ---------------------------------------------------------------------------

def salvar_ato(request, tis, imovel, documento, job, extracao, indice):
    """Grava o ato ``indice`` pelo caminho do formulário manual.

    Tudo numa transação, com a ordem de travas da importação
    (``DocumentoDigital`` → job/extração → ``Documento``, esta última dentro
    do próprio service): o clique duplo e a reextração concorrente se
    serializam em vez de correr. A regra de validação e de duplicidade é a
    do formulário manual (herdada, não copiada). Não cria cartório — o nome
    da transmissão sem cadastro é recusado antes do service, que o criaria —
    nem grava CPF/RG.

    Levanta ``services.ExtracaoRecusada`` quando a extração deixou de ser a
    vigente; qualquer outra exceção volta à view, que desfaz tudo (o ``with``
    sai com rollback) e re-renderiza o formulário com o que foi digitado.
    """
    chave = f'/acts/{indice}'
    with transaction.atomic():
        DocumentoDigital.objects.select_for_update().get(
            pk=job.documento_digital_id,
        )
        extracao = services._travar_extracao_revisao(extracao)
        job = extracao.ocr_job
        if job.status not in (estados.EXTRAIDO, estados.REVISADO):
            return Resultado('recusado', mensagem=MENSAGEM_JOB_FORA_DE_REVISAO)

        dados = revisao._montar_dados(extracao)
        linhas = importacao._linhas_por_chave(extracao)
        atos = atos_da_revisao(extracao, dados, linhas)
        atual = next((ato for ato in atos if ato['indice'] == indice), None)
        if atual is None:
            return Resultado('recusado', mensagem=MENSAGEM_ATO_FORA_DA_REVISAO)
        if atual['estado'] == ESTADO_IMPORTADO:
            # Clique duplo, aba velha ou "voltar" do navegador: o ato já virou
            # lançamento e salvar de novo criaria um segundo (com outro
            # número, o service não barraria).
            return Resultado(
                'ja_salvo', lancamento_id=atual['lancamento_id'],
                restantes=_restantes(atos, indice),
            )

        desconhecido = _cartorio_da_transmissao_nao_cadastrado(request.POST)
        if desconhecido:
            return Resultado(
                'invalido',
                mensagem=MENSAGEM_CARTORIO_NAO_CADASTRADO.format(nome=desconhecido),
            )

        resultado = LancamentoService.criar_lancamento_completo(
            request, tis, imovel, documento,
        )
        primeiro, segundo = resultado
        if isinstance(primeiro, dict) and primeiro.get('tipo') == 'duplicata_encontrada':
            return Resultado('duplicata', mensagem=segundo or '')
        if not primeiro:
            return Resultado('invalido', mensagem=segundo or '')

        lancamento = primeiro
        ato = next(item for item in dados.atos if item.chave == chave)
        importacao._vincular(
            job, request.user, lancamento,
            _registros_do_ato(lancamento, ato, chave), linhas,
        )
        importacao._marcar_importadas(extracao, request.user, [chave])

        restantes = _restantes(atos, indice)
        if job.status == estados.EXTRAIDO:
            job.transicionar(
                estados.REVISADO, usuario=request.user, motivo=MOTIVO_TRANSICAO,
            )
        if not restantes:
            job.transicionar(
                estados.IMPORTADO, usuario=request.user, motivo=MOTIVO_TRANSICAO,
            )
        imovel_id = imovel.pk
        transaction.on_commit(lambda: (
            CacheService.invalidate_documentos_imovel(imovel_id),
            CacheService.invalidate_tronco_principal(imovel_id),
        ))
        return Resultado(
            'salvo', mensagem_origens=segundo, lancamento=lancamento,
            lancamento_id=lancamento.pk, restantes=restantes,
        )


def _cartorio_da_transmissao_nao_cadastrado(post):
    """Nome lido pelo OCR, sem cadastro escolhido, que o service CRIARIA.

    O formulário manual é rígido com o cartório da origem ("selecione da
    lista"), mas no bloco Transmissão um nome sem id vira ``Cartorios`` novo
    (``lancamento_campos_service``). Quem digita sabe o que está criando; o
    texto que o OCR leu, não: a revisão pré-preenche só o NOME quando o
    cartório não foi escolhido e não pode gravar cadastro por esse caminho
    (#341: nada de cartório criado pelo fluxo da IA). Nome que já existe no
    cadastro (``iexact``, a mesma busca do service) segue normalmente.
    """
    nome = (post.get('cartorio_transmissao_nome') or '').strip()
    if not nome or (post.get('cartorio_transmissao') or '').strip():
        return None
    if Cartorios.objects.filter(nome__iexact=nome).exists():
        return None
    return nome


def _restantes(atos, indice):
    """Índices dos atos pendentes, fora ``indice``, na ordem da revisão."""
    return [
        ato['indice'] for ato in atos
        if ato['estado'] == ESTADO_PENDENTE and ato['indice'] != indice
    ]


def _registros_do_ato(lancamento, ato, chave):
    """Objetos gravados pelo ato → ``(modelo, pk, chave da linha)`` da auditoria.

    O mesmo formato de ``importacao._importar_ato``. Cadastros de pessoa
    criados pelo formulário não entram (o service manual não diz quais são
    novos); o vínculo do lançamento com cada pessoa, sim.
    """
    chave_origem = f'{chave}/origem/numero'
    registros = [('Lancamento', lancamento.pk, chave)]
    estruturada = lancamento.origens_estruturadas.first()
    if estruturada is not None:
        registros.append(('LancamentoOrigem', estruturada.pk, chave_origem))
    registros.extend(
        ('Documento', pk, chave_origem)
        for pk in LancamentoOrigemService.consumir_documentos_criados(lancamento)
    )
    partes = {
        (parte.papel, revisao._normalizar_nome(parte.nome or '')): parte.chave
        for parte in ato.partes
    }
    for vinculo in lancamento.pessoas.select_related('pessoa'):
        nome = vinculo.nome_digitado or vinculo.pessoa.nome
        registros.append((
            'LancamentoPessoa', vinculo.pk,
            partes.get((vinculo.tipo, revisao._normalizar_nome(nome or '')), chave),
        ))
    return registros
