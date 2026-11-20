"""Gravação do ato: o ÚNICO caminho de escrita da revisão por ato."""

from django.db import transaction

from dominial.models import Cartorios, DocumentoDigital
from dominial.services.cache_service import CacheService
from dominial.services.lancamento_origem_service import LancamentoOrigemService
from dominial.services.lancamento_service import LancamentoService

from .. import estados, importacao, revisao, services
from ..formulario import area_exige_decisao
from .consulta import (
    ESTADO_IMPORTADO,
    ESTADO_PENDENTE,
    Resultado,
    atos_da_revisao,
)

MOTIVO_TRANSICAO = 'revisao_formulario'

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
MENSAGEM_AREA_SEM_DECISAO = (
    '❌ A área foi lida em unidade diferente de hectare. Preencha a área em '
    'hectares ou marque o descarte explícito. Nada foi gravado.'
)


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
        # A identidade que preencheu a página é validada DEPOIS das travas e
        # permanece protegida até o fim desta transação. Assim, um POST antigo
        # não pode aplicar R1 à extração vigente R9, mesmo que a troca ocorra
        # entre a checagem preliminar da view e este save (#341, M2).
        if (request.POST.get('extracao_id') or '').strip() != str(extracao.pk):
            raise services.ExtracaoRecusada('extracao_nao_vigente')
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

        area_preenchida = bool((request.POST.get('area') or '').strip())
        descarte_explicito = request.POST.get('descartar_area') == '1'
        if (
            area_exige_decisao(extracao, indice, linhas)
            and not area_preenchida
            and not descarte_explicito
        ):
            return Resultado('invalido', mensagem=MENSAGEM_AREA_SEM_DECISAO)

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
    # O A3 oferece no máximo uma origem, renderizada na posição zero. O
    # revisor pode editar esse valor e acrescentar outras linhas: a posição
    # continua identificando a origem extraída, enquanto casar pelo texto
    # atribuiria a evidência a uma linha manual que repetisse o valor antigo.
    tem_origem_extraida = bool(
        str((ato.origem or {}).get('numero') or '').strip()
    )
    for origem in lancamento.origens_estruturadas.order_by('indice_origem'):
        eh_a_extraida = tem_origem_extraida and origem.indice_origem == 0
        registros.append((
            'LancamentoOrigem', origem.pk,
            chave_origem if eh_a_extraida else None,
        ))
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
