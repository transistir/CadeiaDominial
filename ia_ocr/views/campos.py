"""Tela de revisão dos campos sugeridos (``campos_job_ocr``) e os helpers
de máscara de PII, rótulos de cadastro, fallback de cartório e opções do
tipo sugerido.

Extraídos do monólito de views (etapa 3, limite de 400 linhas). Só
``render`` é chamado VIA O PACOTE (``views.render``): o teste faz
``mock.patch('ia_ocr.views.render')``, que só vale se o call site
resolver o nome no objeto do pacote, a cada chamada.
``mock.patch('ia_ocr.views.revisao.pendencias')`` age no MÓDULO
``ia_ocr.revisao``, que o call site segue usando como atributo de módulo
(``revisao.pendencias(...)``). Todo outro helper de outro módulo do
pacote vem por import direto do dono e é chamada direta. Ver o docstring
do ``__init__.py``.
"""
import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.text import slugify
from django.views.decorators.http import require_GET

from dominial.models import Cartorios, LancamentoTipo, Pessoas

from .. import estados, revisao, rotulos, services, views
from .jobs import _contexto_job, _kwargs_job
from .resposta import _aviso_nao_consta, _avisos_descritos, _url_tela


def _mascarar_cpf(cpf):
    digitos = re.sub(r'\D', '', cpf or '')
    return f'CPF ***.***.***-{digitos[-2:]}' if len(digitos) >= 2 else 'CPF ***'


_CPF = re.compile(r'\b\d{3}[.\s]?\d{3}[.\s]?\d{3}[-.\s]?\d{2}\b')
_RG = re.compile(r'\b\d{1,2}\.\d{3}\.\d{3}-?[\dXx]\b')
_RG_ROTULO = re.compile(
    r'(?i)(\bR\.?G\.?(?:\s*n\.?\s*[º°o]?\.?)?\s*[:\-]?\s*)'
    r'\d(?:[.\-/\s]?\d){4,11}(?:[-\s]?[\dXx])?'
)


def _mascarar_evidencia(trecho):
    """Esconde CPF/RG no trecho exibido; datas, valores e CNS ficam intactos."""
    if not trecho:
        return trecho
    mascarado = _CPF.sub('***', trecho)
    mascarado = _RG.sub('***', mascarado)
    return _RG_ROTULO.sub(r'\1***', mascarado)


def _mascarar_rg(rg):
    digitos = re.sub(r'\D', '', rg or '')
    return f'RG ***{digitos[-2:]}' if len(digitos) >= 2 else 'RG ***'


def _rotulo_pessoa(pessoa):
    if pessoa is None:
        return 'Cadastro indisponível'
    if pessoa.cpf:
        documento = _mascarar_cpf(pessoa.cpf)
    elif pessoa.rg:
        documento = _mascarar_rg(pessoa.rg)
    else:
        documento = ''
    return f'{pessoa.nome} — {documento}' if documento else pessoa.nome


def _rotulo_cartorio(cartorio):
    if cartorio is None:
        return 'Cadastro indisponível'
    rotulo = cartorio.nome
    local = '/'.join(
        parte for parte in (cartorio.cidade, cartorio.estado) if parte
    )
    if local:
        rotulo = f'{rotulo} — {local}'
    if cartorio.cns:
        rotulo = f'{rotulo} — CNS {cartorio.cns}'
    return rotulo


def _anexar_opcoes_cadastro(campos):
    """Rótulos dos candidatos, em uma query por tipo (pessoa/cartório).

    Nunca consulta o banco no template e nunca expõe documento completo:
    CPF/RG saem mascarados com os dois últimos dígitos.
    """
    ids_pessoas = set()
    ids_cartorios = set()
    for campo in campos:
        if campo.tipo_valor == 'parte':
            ids_pessoas.update(campo.match_candidatos or [])
            if campo.pessoa_escolhida_id:
                ids_pessoas.add(campo.pessoa_escolhida_id)
        elif campo.tipo_valor == 'cartorio':
            ids_cartorios.update(campo.match_candidatos or [])
            if campo.cartorio_escolhido_id:
                ids_cartorios.add(campo.cartorio_escolhido_id)
    pessoas = {
        p.pk: p for p in Pessoas.objects.filter(
            pk__in=ids_pessoas,
        ).only('nome', 'cpf', 'rg')
    }
    cartorios = {
        c.pk: c for c in Cartorios.objects.filter(
            pk__in=ids_cartorios,
        ).only('nome', 'cidade', 'estado', 'cns')
    }

    def opcoes(ids, escolhido, rotulos):
        lista = list(ids or [])
        if escolhido and escolhido not in lista:
            lista.append(escolhido)
        return [
            {'id': pk, 'rotulo': rotulos.get(pk, 'Cadastro indisponível')}
            for pk in lista
        ]

    rotulos_pessoas = {
        pk: _rotulo_pessoa(pessoa) for pk, pessoa in pessoas.items()
    }
    rotulos_cartorios = {
        pk: _rotulo_cartorio(cartorio) for pk, cartorio in cartorios.items()
    }
    for campo in campos:
        if campo.tipo_valor == 'parte':
            campo.opcoes_cadastro = opcoes(
                campo.match_candidatos, campo.pessoa_escolhida_id,
                rotulos_pessoas,
            )
        elif campo.tipo_valor == 'cartorio':
            campo.opcoes_cadastro = opcoes(
                campo.match_candidatos, campo.cartorio_escolhido_id,
                rotulos_cartorios,
            )
        else:
            campo.opcoes_cadastro = []


def _preencher_fallback_cartorio(extracao, campos):
    """Seletor de cartório nunca vazio: candidatos da comarca, só em memória.

    Roda antes de ``_anexar_opcoes_cadastro`` para os rótulos saírem na mesma
    query. Nada é salvo nem pré-selecionado: a escolha é do revisor.
    """
    sem_candidatos = [
        campo for campo in campos
        if campo.tipo_valor == 'cartorio' and not campo.match_candidatos
    ]
    if not sem_candidatos:
        return
    indice = revisao.IndiceCartorios()
    comarca = revisao.comarca_do_documento(extracao)
    for campo in sem_candidatos:
        campo.match_candidatos = revisao.fallback_cartorio(
            campo, indice, comarca,
        )


def _opcoes_tipo_sugerido():
    """Opções do <select> do tipo, na MESMA fonte do enum aceito no save.

    Revisão Opus (MUST-FIX #322): as opções DESENHADAS saem de
    ``rotulos.TIPOS_SUGERIDOS`` — o mesmo vocabulário que
    ``destinos._do_campo`` aceita no POST. Tipo no cadastro fora do
    contrato não vira opção que dá 422; código no contrato sem linha no
    cadastro continua sendo ofertado. O rótulo de exibição vem do cadastro
    (``get_tipo_display``) quando a linha existe e de
    ``LancamentoTipo.TIPO_CHOICES`` quando não vem.
    """
    configuracoes = {
        tipo.tipo: tipo for tipo in LancamentoTipo.objects.order_by('pk')
    }
    displays = dict(LancamentoTipo.TIPO_CHOICES)
    return [
        {
            'codigo': codigo,
            'display': (
                configuracoes[codigo].get_tipo_display()
                if codigo in configuracoes
                else displays.get(codigo, codigo)
            ),
        }
        for codigo in rotulos.TIPOS_SUGERIDOS
    ]


@login_required
@require_GET
def campos_job_ocr(request, tis_id, imovel_id, documento_id, job_id):
    """Revisão da extração vigente; após finalizar, a tela é somente leitura."""
    tis, imovel, documento, job = _contexto_job(
        request, tis_id, imovel_id, documento_id, job_id
    )
    kwargs_job = _kwargs_job(tis, imovel, documento, job)
    if job.status not in (estados.EXTRAIDO, estados.REVISADO):
        messages.info(request, 'Extraia os campos antes de revisá-los.')
        return redirect(_url_tela(kwargs_job))
    extracao = job.extracao_vigente()
    if extracao is None:
        raise Http404('Extração indisponível.')
    todas_as_linhas = list(extracao.campos.order_by('chave'))
    # Token do estado salvo: os candidatos abaixo são só de exibição. O
    # token cobre TODAS as linhas salvas — inclusive as ignoradas na tela
    # (Tarefa C #322), que o salvar_bloco ainda considera no seu próprio —
    # senão o primeiro save da extração antiga daria conflito de versão.
    versao = services.versao_bloco(extracao, campos=todas_as_linhas)
    # Linhas em revisao.LINHAS_IGNORADAS (extrações antigas já salvaram
    # valor_transacao) não podem virar card.
    campos = [
        campo for campo in todas_as_linhas
        if not revisao.linha_ignorada(campo.chave)
    ]
    _preencher_fallback_cartorio(extracao, campos)
    _anexar_opcoes_cadastro(campos)
    # P2-2 (#322/PR #327, rodada 10): o card tem que mostrar o tipo que
    # pendências, prévia e importação vão usar — o resolvedor único da
    # revisão, AGORA COM A ORIGEM. Nada de recalcular a precedência aqui:
    # a cópia anterior divergia em dois estados alcançáveis (linha de tipo
    # descartada e valor explícito fora de TIPOS_SUGERIDOS criado pelo
    # backfill da 0009). Rodada 12: a resolução cobre também o ato
    # DESCARTADO (mesmo resolvedor, contexto que ignora só o descarte
    # dele) — o fallback de valor_final/normalized da rodada 11 saiu.
    resolucoes = revisao.resolucoes_de_tipo(extracao)
    for campo in campos:
        campo.evidencia_trecho = _mascarar_evidencia(campo.evidencia_trecho)
        campo.obrigatorio = revisao.campo_obrigatorio(campo.chave)
        # Exclusivo do card de tipo do ATO (/acts/N/tipo_sugerido): nenhuma
        # outra chave do mapa de destinos termina em tipo_sugerido.
        campo.eh_tipo_sugerido = re.fullmatch(
            r'/acts/\d+/tipo_sugerido', campo.chave,
        ) is not None
        if campo.eh_tipo_sugerido:
            # O que o <select> traz selecionado é o que a importação vai
            # usar — inclusive quando a linha de tipo está descartada (o
            # resolvedor já pula a linha e cai no rótulo) e quando o ATO
            # está descartado. Única exceção: origem 'limpo' = select
            # APAGADO (P2-1), decisão de "sem tipo" — nenhuma opção
            # marcada. Sem linha estrutural do ato não há resolução
            # (estado inalcançável: o desnormalizar sempre cria a linha do
            # ato antes da de tipo) e o select fica em branco.
            tipo, origem = resolucoes.get(
                campo.chave.rsplit('/', 1)[0], (None, 'nenhum'),
            )
            campo.tipo_exibido = '' if origem == 'limpo' else tipo
    # I-11a (#321): a tela agrupa como o FORMULÁRIO de lançamento — seção
    # Documento, um bloco por ato em ordem reversa, não reconhecidos e
    # "Outros dados lidos" —, não mais por destino técnico
    # (``dominial.Lancamento.tipo``/``SEM_DESTINO``). As opções do <select>
    # são calculadas UMA vez: o display do subtítulo do ato sai da mesma
    # fonte que desenha as opções.
    opcoes_tipo = _opcoes_tipo_sugerido()
    somente_leitura = job.status == estados.REVISADO
    pendencias = services._com_bloqueios_de_campo(
        revisao.pendencias(extracao), extracao,
    )
    # Issue #262: a confirmação sem atos só aparece quando a ÚNICA pendência é
    # a ausência de atos. A comparação é por conteúdo: a lista de pendências
    # continua sendo exibida e a flag nunca a remove.
    permitir_sem_atos = (
        services.pode_finalizar_sem_atos(extracao) and not somente_leitura
    )
    avisos_descritos = _avisos_descritos(request, extracao)
    # Detalhe técnico do card abre sozinho no campo com pendência, e o
    # cabeçalho do ato conta as pendências que o bloqueiam. O selo "não
    # consta no documento" (#324) marca o campo de livro/folha da origem que
    # o documento não trouxe; o campo segue vazio e editável.
    chaves_pendentes = {item['chave'] for item in pendencias}
    chaves_nao_consta = {
        item['chave'] for item in avisos_descritos
        if _aviso_nao_consta(item)
    }
    for campo in campos:
        campo.pendente = campo.chave in chaves_pendentes
        campo.nao_consta = campo.chave in chaves_nao_consta
    secoes = revisao.secoes_da_tela(
        campos,
        payload=extracao.payload_servico or extracao.payload,
        tipos_display={
            opcao['codigo']: opcao['display'] for opcao in opcoes_tipo
        },
    )
    for secao in secoes:
        if secao['tipo'] != 'ato':
            continue
        prefixo = secao['chave_ato']
        secao['pendencias_do_ato'] = sum(
            1 for item in pendencias
            if item['chave'] == prefixo
            or (
                isinstance(item['chave'], str)
                and item['chave'].startswith(prefixo + '/')
            )
        )
    # Âncora da pendência só quando o alvo existe na tela: linha sem card
    # (estado antigo) não vira link morto (#321 §5).
    ids_da_tela = {'campo-' + slugify(campo.chave) for campo in campos}
    if permitir_sem_atos:
        ids_da_tela.add('campo-sem-atos')
    pendencias_descritas = [
        revisao.descrever_pendencia(item, permitir_sem_atos)
        for item in pendencias
    ]
    for item in pendencias_descritas:
        if item['alvo'] is not None and item['alvo'] not in ids_da_tela:
            item['alvo'] = None
    return views.render(request, 'ia_ocr/revisao_campos.html', {
        'tis': tis,
        'imovel': imovel,
        'documento': documento,
        'arquivo': job.documento_digital,
        'job': job,
        'extracao': extracao,
        'campos': campos,
        'secoes': secoes,
        # Tarefa B #322: o tipo é <select> como no formulário de lançamento;
        # as opções e o enum aceito no save vêm da MESMA fonte (contrato A3).
        'opcoes_tipo_sugerido': opcoes_tipo,
        'codigos_tipo_sugerido': list(rotulos.TIPOS_SUGERIDOS),
        'pendencias': pendencias_descritas,
        'pendencias_total': len(pendencias),
        'permitir_sem_atos': permitir_sem_atos,
        'avisos': avisos_descritos,
        'versao': versao,
        'somente_leitura': somente_leitura,
        'dpi': job.dpi or 200,
        'url_salvar': reverse('salvar_bloco_ocr', kwargs=kwargs_job),
        'url_finalizar': reverse('finalizar_revisao_ocr', kwargs=kwargs_job),
        'url_texto': _url_tela(kwargs_job),
        'url_arquivo': reverse('servir_documento_digital', kwargs={
            'tis_id': tis.pk,
            'imovel_id': imovel.pk,
            'documento_id': documento.pk,
            'arquivo_id': job.documento_digital_id,
        }),
        'url_documento': reverse('documento_detalhado', kwargs={
            'tis_id': tis.pk, 'imovel_id': imovel.pk, 'documento_id': documento.pk,
        }),
    })
