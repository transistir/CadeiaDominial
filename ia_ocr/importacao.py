"""Gravação da revisão finalizada em lançamentos do dominial (I-6 / #263).

``importar`` recebe a extração vigente de um job ``revisado``, o token de
versão do bloco e os ponteiros dos atos marcados, e grava cada ato em um
savepoint próprio: os erros de TODOS os atos são coletados antes da
resposta, mas nada persiste sem o bloco inteiro válido (rollback total ao
primeiro erro — inclusive da transição final do job).

Quem entra na importação: as linhas ``aceito``/``editado`` e TAMBÉM as
``sugerido`` sem ``requer_revisao`` — a finalização da revisão já é o
aceite humano (#263-I6-B). O cabeçalho ``/document/*`` e o ``/closure`` são
só conferência: nada é gravado no ``Documento``.

Decisões de gravação (brief #263):

- **pessoa** (D): ``criar novo`` com CPF já cadastrado reutiliza o cadastro
  (busca pelos dígitos); só o nome igual não basta — homônimos existem. A
  mesma pessoa não é criada duas vezes na mesma importação (cache por CPF
  ou nome canônico).
- **cartório** (E): ``criar novo`` busca ``nome__iexact`` e cria apenas
  quando não acha (mesma regra do fluxo manual,
  ``lancamento_campos_service``).
- **origem**: o texto do lançamento é o prefixo canônico (M/T) + número
  normalizado; a ``LancamentoOrigem`` e o documento de origem vêm do
  ``LancamentoOrigemService`` com o mapeamento do "POST corrente" definido
  na instância — nunca do sinal ``post_save`` (que engole exceções).
"""

import re
import uuid

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from dominial.managers import documentos_for_user
from dominial.models import (
    Cartorios, Documento, DocumentoDigital, Lancamento, LancamentoPessoa,
    LancamentoTipo, Pessoas,
)
from dominial.services.cache_service import CacheService
from dominial.services.lancamento_origem_service import LancamentoOrigemService
from dominial.utils.documento_identidade_utils import (
    normalizar_numero_documento,
)

from . import destinos, revisao, services
from .estados import IMPORTADO, REVISADO
from .models import ImportacaoIA, OcrJob
from .revisao import _normalizar_nome, _so_digitos

MOTIVO_TRANSICAO = 'importacao_ia'

PREFIXO_TIPO_DOCUMENTO = {'matricula': 'M', 'transcricao': 'T'}

# Inverso do mapa de destinos: campo do modelo → padrão de chave de linha.
# ``_chave_de_erro`` concreta o padrão com o índice do ato (e da parte, nos
# erros de LancamentoPessoa/Pessoas); campos sem padrão caem no próprio ato.
_PADRAO_POR_CAMPO: dict[str, list[str]] = {}
for _chave, _entrada in destinos.DESTINOS.items():
    if isinstance(_entrada, tuple) and _entrada[1] is not None:
        _PADRAO_POR_CAMPO.setdefault(
            f'{_entrada[0]}.{_entrada[1]}', [],
        ).append(_chave)


class ImportacaoInvalida(Exception):
    """Um ou mais atos não puderam ser gravados (HTTP 422)."""

    code = 'importacao_invalida'

    def __init__(self, linhas):
        self.linhas = list(linhas)
        super().__init__(self.code)


def importar(extracao, usuario, versao, atos):
    """Grava os atos marcados da revisão finalizada e devolve a resposta.

    Ordem das travas (a mesma da exclusão do PDF, para não deadlockar):
    ``DocumentoDigital`` → job → extração → ``Documento``. Job ``importado``
    devolve o resultado gravado (idempotência); qualquer outro estado que
    não ``revisado`` recusa. Erros de ato viram ``ImportacaoInvalida``
    DENTRO da transação: nada persiste.
    """
    with transaction.atomic():
        job = OcrJob.objects.select_related(
            'documento_digital__documento__imovel',
        ).get(pk=extracao.ocr_job_id)
        DocumentoDigital.objects.select_for_update().get(
            pk=job.documento_digital_id,
        )
        extracao = services._travar_extracao_revisao(extracao)
        job = extracao.ocr_job
        if job.status == IMPORTADO:
            return _resultado_gravado(extracao)
        if job.status != REVISADO:
            raise services.ExtracaoRecusada('estado_invalido')
        if not isinstance(versao, str) or not versao:
            raise services.ExtracaoRecusada('versao_ausente')
        if versao != services.versao_bloco(extracao):
            raise services.ConflitoVersao([])

        dados = revisao.dados_revisados(extracao)
        marcados = _atos_marcados(dados, atos)
        documento = (
            Documento.objects.select_related('imovel').select_for_update()
            .get(pk=job.documento_digital.documento_id)
        )
        imovel = documento.imovel
        linhas = _linhas_por_chave(extracao)
        cache_pessoas: dict[str, Pessoas] = {}
        documentos_usuario = documentos_for_user(usuario)

        respostas = []
        importadas = []
        for ato in dados.atos:
            if ato.chave not in marcados:
                respostas.append(_linha_resposta(
                    ato.chave, _rotulo(ato.chave, linhas), 'ignorado',
                ))
                continue
            # Savepoint: o erro de um ato não interrompe a coleta dos demais.
            with transaction.atomic():
                resposta, erros = _importar_ato(
                    ato, documento, imovel, usuario, job, linhas,
                    cache_pessoas, documentos_usuario,
                )
            if erros.itens:
                resposta = _linha_resposta(
                    ato.chave, _rotulo(ato.chave, linhas), 'erro',
                    erros=erros.itens,
                )
            else:
                importadas.append(ato.chave)
            respostas.append(resposta)

        if any(resposta['status'] == 'erro' for resposta in respostas):
            # Há pelo menos um ato com erro: os que gravaram agora sofrem
            # rollback — a resposta os marca como não gravados.
            for resposta in respostas:
                if resposta['status'] == 'criado':
                    resposta.update(status='nao_gravado', lancamento_id=None, url=None)
            raise ImportacaoInvalida(respostas)

        _marcar_importadas(extracao, usuario, importadas)
        job.transicionar(IMPORTADO, usuario=usuario, motivo=MOTIVO_TRANSICAO)
        transaction.on_commit(lambda: (
            CacheService.invalidate_documentos_imovel(imovel.pk),
            CacheService.invalidate_tronco_principal(imovel.pk),
        ))
        return {'ok': True, 'linhas': respostas}


def resumo(extracao):
    """Prévia consultiva da importação (GET do PR2): atos, tipo e duplicados.

    Não trava nada nem grava: é o que a tela de confirmação exibe antes de
    o usuário marcar os atos e disparar o POST.
    """
    dados = revisao.dados_revisados(extracao)
    linhas = _linhas_por_chave(extracao)
    job = extracao.ocr_job
    documento = Documento.objects.select_related('imovel').get(
        pk=job.documento_digital.documento_id,
    )
    atos = []
    for ato in dados.atos:
        tipo = (
            LancamentoTipo.objects.filter(tipo=ato.tipo).order_by('pk').first()
        )
        duplicado = (
            _lancamento_duplicado(documento, tipo, ato.data, ato.numero_lancamento)
            if tipo is not None else None
        )
        atos.append({
            'chave': ato.chave,
            'rotulo': _rotulo(ato.chave, linhas),
            'tipo': ato.tipo,
            'partes': len(ato.partes),
            'duplicado': duplicado is not None,
            'existente': _existente(duplicado) if duplicado else None,
            'erro': None if tipo is not None else 'tipo_inexistente',
        })
    return {'atos': atos}


# ---------------------------------------------------------------------------
# Gravação de um ato
# ---------------------------------------------------------------------------

def _importar_ato(
    ato, documento, imovel, usuario, job, linhas,
    cache_pessoas, documentos_usuario,
):
    """Grava um ato (lançamento + origem + partes) e devolve a linha resposta.

    Sempre devolve ``(resposta | None, erros)``: com erro, quem chamou faz o
    savepoint desfazer tudo o que este ato criou (cartórios, pessoas,
    documento de origem).
    """
    chave = ato.chave
    erros = _Erros(chave)

    tipo = LancamentoTipo.objects.filter(tipo=ato.tipo).order_by('pk').first()
    if tipo is None:
        erros.add(
            f'{chave}/tipo_sugerido', 'tipo_inexistente',
            'O tipo de lançamento não está configurado no sistema.',
        )
        return None, erros

    duplicado = _lancamento_duplicado(
        documento, tipo, ato.data, ato.numero_lancamento,
    )
    if duplicado is not None:
        erros.add(
            chave, 'lancamento_duplicado',
            'Já existe um lançamento deste ato no documento.',
            existente=_existente(duplicado),
        )
        return None, erros

    # Cartório de transmissão é opcional; o da origem, exigido pela origem.
    criados_cartorios = []
    cartorio_transmissao = _resolver_cartorio(
        ato.cartorio_transmissao_id, ato.cartorio_transmissao_criar_novo,
        ato.cartorio_transmissao_nome,
        f'{chave}/cartorio_transmissao', criados_cartorios,
    )

    origem = ato.origem
    texto_origem = None
    mapeamento = None
    cartorio_origem = None
    if origem is not None and (
        (origem.get('numero') or '').strip() or origem.get('tipo_documento')
    ):
        cartorio_origem = _resolver_cartorio(
            origem.get('cartorio_id'), origem.get('cartorio_criar_novo'),
            origem.get('cartorio_nome'), f'{chave}/origem/cartorio',
            criados_cartorios,
        )
        if cartorio_origem is None:
            if origem.get('cartorio_id') is not None:
                erros.add(
                    f'{chave}/origem/cartorio', 'decisao_perdida',
                    'O cartório escolhido para a origem não existe mais.',
                )
            else:
                erros.add(
                    f'{chave}/origem/cartorio', 'valor_obrigatorio',
                    'O cartório da origem é obrigatório para importar o ato.',
                )
            return None, erros
        numero = (origem.get('numero') or '').strip()
        if not numero:
            erros.add(
                f'{chave}/origem/numero', 'valor_obrigatorio',
                'O número da origem é obrigatório para importar o ato.',
            )
            return None, erros
        tipo_documento = _tipo_documento_da_origem(origem, numero)
        try:
            normalizado = normalizar_numero_documento(numero, tipo_documento)
        except (TypeError, ValueError) as exc:
            # Mensagem fixa do util: cita o prefixo, nunca o número inteiro.
            erros.add(
                f'{chave}/origem/numero', 'valor_incompativel_destino', str(exc),
            )
            return None, erros
        texto_origem = PREFIXO_TIPO_DOCUMENTO[tipo_documento] + normalizado
        mapeamento = [{
            'indice': 0,
            'origem': texto_origem,
            'cartorio_id': cartorio_origem.pk,
            'livro': origem.get('livro'),
            'folha': origem.get('folha'),
        }]

    lancamento = Lancamento(
        documento=documento,
        tipo=tipo,
        numero_lancamento=ato.numero_lancamento,
        data=ato.data,
        valor_transacao=ato.valor,
        area=ato.area,
        titulo=ato.titulo,
        forma=ato.forma,
        descricao=ato.descricao,
        detalhes=ato.detalhes,
        observacoes=ato.observacoes,
        eh_inicio_matricula=bool(ato.eh_inicio_matricula),
        cartorio_origem=cartorio_origem,
        cartorio_transmissao=cartorio_transmissao,
        livro_origem=origem.get('livro') if origem else None,
        folha_origem=origem.get('folha') if origem else None,
        data_origem=origem.get('data') if origem else None,
    )
    if texto_origem is not None:
        lancamento.origem = texto_origem
    try:
        lancamento.full_clean()
    except ValidationError as exc:
        erros.do_modelo(exc, 'dominial.Lancamento')
        return None, erros

    # Mapeamento do "POST corrente" antes do save: o sinal post_save roda o
    # mesmo serviço sem queryset, e a chamada explícita abaixo é a fonte da
    # verdade (o sinal engole exceções — nunca confiar nele).
    if mapeamento is not None:
        LancamentoOrigemService.definir_mapeamento(lancamento, mapeamento)
    try:
        lancamento.save()
        aviso = LancamentoOrigemService.processar_origens_automaticas(
            lancamento, lancamento.origem or '', imovel,
            documentos_queryset=documentos_usuario,
        )
    finally:
        LancamentoOrigemService.limpar_mapeamento(lancamento)

    registros = [('Lancamento', lancamento.pk, chave)]
    registros.extend(
        (modelo, objeto.pk, chave_linha)
        for modelo, objeto, chave_linha in criados_cartorios
    )
    if mapeamento is not None:
        origem_estruturada = lancamento.origens_estruturadas.first()
        if origem_estruturada is not None:
            registros.append((
                'LancamentoOrigem', origem_estruturada.pk,
                f'{chave}/origem/numero',
            ))

    for parte in ato.partes:
        pessoa, pessoa_criada = _resolver_pessoa(parte, cache_pessoas, erros)
        if pessoa is None:
            return None, erros
        vinculo, vinculo_criado = LancamentoPessoa.objects.get_or_create(
            lancamento=lancamento, pessoa=pessoa, tipo=parte.papel,
            defaults={'nome_digitado': parte.nome},
        )
        if vinculo_criado:
            registros.append(('LancamentoPessoa', vinculo.pk, parte.chave))
        if pessoa_criada:
            registros.append(('Pessoas', pessoa.pk, parte.chave))

    _vincular(job, usuario, lancamento, registros, linhas)
    resposta = _linha_resposta(
        chave, _rotulo(chave, linhas), 'criado', lancamento=lancamento,
        avisos=[aviso] if aviso else [],
    )
    return resposta, erros


def _resolver_pessoa(parte, cache_pessoas, erros):
    """Pessoa da parte (decisão D): escolhida, reutilizada por CPF ou nova.

    Devolve ``(pessoa | None, criada_na_importacao)``.
    """
    chave_parte = parte.chave or ''
    if not parte.criar_novo:
        if parte.pessoa_id is None:
            erros.add(
                chave_parte, 'decisao_perdida',
                'A decisão de pessoa desta parte se perdeu; revise o ato.',
            )
            return None, False
        pessoa = Pessoas.objects.filter(pk=parte.pessoa_id).first()
        if pessoa is None:
            erros.add(
                chave_parte, 'decisao_perdida',
                'A pessoa escolhida para esta parte não existe mais.',
            )
            return None, False
        return pessoa, False

    nome = (parte.nome or '').strip()
    if not nome:
        erros.add(
            f'{chave_parte}/nome', 'valor_obrigatorio',
            'O nome da parte é obrigatório para criar a pessoa.',
        )
        return None, False
    digitos = _so_digitos(parte.cpf) if parte.cpf else ''
    chave_cache = digitos or _normalizar_nome(nome)
    if chave_cache and chave_cache in cache_pessoas:
        return cache_pessoas[chave_cache], False
    pessoa = (
        Pessoas.objects.filter(cpf=digitos).first() if digitos else None
    )
    criada = False
    if pessoa is None:
        pessoa = Pessoas(
            nome=nome, cpf=digitos or None, rg=parte.rg,
        )
        try:
            pessoa.full_clean()
        except ValidationError as exc:
            erros.do_modelo(exc, 'dominial.Pessoas', chave_parte=chave_parte)
            return None, False
        pessoa.save()
        criada = True
    if chave_cache:
        cache_pessoas[chave_cache] = pessoa
    return pessoa, criada


def _resolver_cartorio(cartorio_id, criar_novo, nome, chave_linha, criados):
    """FK escolhida ou cartório por nome (decisão E); cria se não achar.

    ``criados`` acumula ``(modelo, cartorio, chave_linha)`` para o vínculo
    de auditoria — cartório reutilizado não gera vínculo novo.
    """
    if criar_novo:
        nome = (nome or '').strip()
        if not nome:
            return None
        cartorio = Cartorios.objects.filter(nome__iexact=nome).first()
        if cartorio is None:
            cartorio = Cartorios.objects.create(
                nome=nome,
                cns=f'CNS{str(uuid.uuid4().int)[:10]}',
            )
            criados.append(('Cartorios', cartorio, chave_linha))
        return cartorio
    if cartorio_id is None:
        return None
    return Cartorios.objects.filter(pk=cartorio_id).first()


def _tipo_documento_da_origem(origem, numero):
    """Tipo documental da origem: o revisado, ou inferido do prefixo M/T."""
    tipo = origem.get('tipo_documento')
    if tipo in PREFIXO_TIPO_DOCUMENTO:
        return tipo
    if numero[:1].upper() == 'T':
        return 'transcricao'
    return 'matricula'


def _lancamento_duplicado(documento, tipo, data, numero):
    """Lançamento existente que colide com o ato, ou None.

    Mesma regra do fluxo manual (``lancamento_validacao_service``): a tupla
    (documento, tipo, data, número) — com número nulo casando null e '' — e
    ainda o número sozinho dentro do documento, mudando tipo ou data.
    """
    filtro = Q(documento=documento, tipo=tipo)
    filtro &= Q(data=data) if data is not None else Q(data__isnull=True)
    if numero:
        filtro &= Q(numero_lancamento=numero)
    else:
        filtro &= Q(numero_lancamento__isnull=True) | Q(numero_lancamento='')
    existente = (
        Lancamento.objects.select_related('documento__imovel')
        .filter(filtro).first()
    )
    if existente is not None:
        return existente
    if numero:
        return (
            Lancamento.objects.select_related('documento__imovel')
            .filter(documento=documento, numero_lancamento=numero).first()
        )
    return None


def _existente(lancamento):
    """``{id, url}`` do lançamento duplicado, sem expor outros dados."""
    return {
        'id': lancamento.pk,
        'url': _url_lancamento(lancamento),
    }


def _url_lancamento(lancamento):
    # O FK do Imovel se chama literalmente ``terra_indigena_id``: o attname
    # do id é ``terra_indigena_id_id`` (herança de nomes do schema legado).
    imovel = lancamento.documento.imovel
    return reverse('editar_lancamento', kwargs={
        'tis_id': imovel.terra_indigena_id_id,
        'imovel_id': imovel.pk,
        'lancamento_id': lancamento.pk,
    })


def _vincular(job, usuario, lancamento, registros, linhas):
    """Grava os vínculos de auditoria (ImportacaoIA) dos objetos criados."""
    for modelo, objeto_id, chave_linha in registros:
        campo = linhas.get(chave_linha)
        ImportacaoIA.objects.create(
            ocr_job=job,
            documento_digital_id=job.documento_digital_id,
            campo=campo,
            pagina=campo.evidencia_pagina if campo else None,
            modelo=modelo,
            objeto_id=objeto_id,
            lancamento=lancamento,
            criado_por=usuario,
        )


def _marcar_importadas(extracao, usuario, chaves_atos):
    """Linhas dos atos importados → ``importado`` com autoria da revisão."""
    filtro = Q()
    for chave in chaves_atos:
        filtro |= Q(chave=chave) | Q(chave__startswith=f'{chave}/')
    extracao.campos.filter(filtro).update(
        status_revisao='importado',
        revisado_por=usuario,
        revisado_em=timezone.now(),
    )


# ---------------------------------------------------------------------------
# Erros por campo
# ---------------------------------------------------------------------------

class _Erros:
    """Erros do ato ancorados nas chaves de linha que a tela conhece."""

    def __init__(self, chave_ato):
        self.chave_ato = chave_ato
        self.itens = []

    def add(self, chave, codigo, mensagem, **extras):
        item = {'chave': chave, 'codigo': codigo, 'mensagem': mensagem}
        item.update(extras)
        self.itens.append(item)

    def do_modelo(self, exc, campo_modelo, chave_parte=None):
        """``message_dict`` do Django → erro por chave de linha."""
        dicionario = getattr(exc, 'message_dict', None)
        if not isinstance(dicionario, dict):
            # ValidationError de texto (ex.: cartório da origem): sem campo.
            self.add(
                self.chave_ato, 'lancamento_invalido', ' '.join(exc.messages),
            )
            return
        for campo, mensagens in dicionario.items():
            if campo == '__all__':
                chave, codigo = self.chave_ato, 'lancamento_invalido'
            else:
                chave = _chave_de_erro(
                    f'{campo_modelo}.{campo}', self.chave_ato, chave_parte,
                )
                codigo = 'campo_invalido'
            for mensagem in mensagens:
                self.add(chave, codigo, mensagem)


def _chave_de_erro(campo_modelo, chave_ato, chave_parte=None):
    """Campo do modelo → chave de linha concreta; sem padrão, o próprio ato."""
    for padrao in _PADRAO_POR_CAMPO.get(campo_modelo, ()):
        if chave_parte is not None and '/partes/*' in padrao:
            sufixo = padrao.split('/partes/*', 1)[1]
            return f'{chave_parte}{sufixo}'
        if '/partes/' not in padrao:
            return padrao.replace('/acts/*', chave_ato, 1)
    return chave_ato


# ---------------------------------------------------------------------------
# Respostas
# ---------------------------------------------------------------------------

def _linha_resposta(chave, rotulo, status, lancamento=None, avisos=None,
                    erros=None):
    linha = {
        'chave': chave,
        'rotulo': rotulo,
        'status': status,
        'lancamento_id': lancamento.pk if lancamento is not None else None,
        'url': _url_lancamento(lancamento) if lancamento is not None else None,
        'avisos': avisos or [],
    }
    if erros is not None:
        linha['erros'] = erros
    return linha


def _resultado_gravado(extracao):
    """Remonta a resposta 200 do job já importado (idempotência)."""
    linhas = _linhas_por_chave(extracao)
    por_ato = {}
    vinculos = ImportacaoIA.objects.filter(
        ocr_job_id=extracao.ocr_job_id, modelo='Lancamento',
    ).select_related('campo', 'lancamento__documento__imovel')
    for vinculo in vinculos:
        if vinculo.campo is not None and vinculo.lancamento is not None:
            por_ato[vinculo.campo.chave] = vinculo.lancamento
    respostas = []
    for chave in sorted(linhas):
        if linhas[chave].tipo_valor != 'ato':
            continue
        lancamento = por_ato.get(chave)
        respostas.append(_linha_resposta(
            chave, _rotulo(chave, linhas),
            'criado' if lancamento is not None else 'ignorado',
            lancamento=lancamento,
        ))
    return {'ok': True, 'linhas': respostas}


def _linhas_por_chave(extracao):
    return {campo.chave: campo for campo in extracao.campos.all()}


def _rotulo(chave, linhas):
    campo = linhas.get(chave)
    return campo.normalized if campo is not None else None


def _atos_marcados(dados, atos):
    """Valida os ponteiros do POST e devolve o conjunto de chaves marcadas."""
    if not isinstance(atos, list) or not atos:
        raise services.ExtracaoRecusada('nenhum_ato')
    conhecidos = {ato.chave for ato in dados.atos}
    marcados = set()
    for chave in atos:
        if not isinstance(chave, str) or not re.fullmatch(r'/acts/\d+', chave):
            raise services.ExtracaoRecusada('ato_invalido')
        if chave not in conhecidos:
            erro = services.ExtracaoRecusada('ato_invalido')
            erro.chave = chave
            raise erro
        marcados.add(chave)
    return marcados
