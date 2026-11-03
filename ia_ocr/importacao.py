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
  ou por nome canônico + RG; sem CPF nem RG, cada ato grava o seu).
- **cartório** (E): ``criar novo`` busca ``nome__iexact`` e cria apenas
  quando não acha (mesma regra do fluxo manual,
  ``lancamento_campos_service``); a criação é serializada pelo nome, com
  as travas tomadas de uma vez e em ordem global (rodadas 4 e 5).
- **origem**: o texto do lançamento é o prefixo canônico (M/T) + número
  normalizado; a ``LancamentoOrigem`` e o documento de origem vêm do
  ``LancamentoOrigemService`` com o mapeamento do "POST corrente" definido
  na instância — nunca do sinal ``post_save`` (que engole exceções).
"""

import hashlib
import re
import uuid

from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
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
from .valores import MOTIVO_LIMITE

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
# Pessoas não tem linha própria no mapa (só chega via parte): os erros de
# nome/CPF/RG ancoram na linha da parte que os originou, não no ato (#263
# rodada 2 — o message_dict caía em ``/acts/i`` sem a tela saber onde).
_PADRAO_POR_CAMPO['dominial.Pessoas.nome'] = ['/acts/*/partes/*/nome']
_PADRAO_POR_CAMPO['dominial.Pessoas.cpf'] = [
    '/acts/*/partes/*/documento_identificacao/valor',
]
_PADRAO_POR_CAMPO['dominial.Pessoas.rg'] = [
    '/acts/*/partes/*/documento_identificacao/valor',
]


class ImportacaoInvalida(Exception):
    """Um ou mais atos não puderam ser gravados (HTTP 422)."""

    code = 'importacao_invalida'

    def __init__(self, linhas):
        self.linhas = list(linhas)
        super().__init__(self.code)


class _AtoInvalido(Exception):
    """Controle interno: força o savepoint do ato a rodar rollback.

    Devolver erros "normalmente" do ``_importar_ato`` deixava o savepoint
    COMITAR o que o ato inválido já tinha gravado (lançamento parcial,
    pessoas, cartórios) — o rollback só vinha no final, tarde demais para
    os atos seguintes (#263 rodada 2). Levantada DENTRO do atomic do ato,
    ela desfaz o savepoint na hora; o loop captura fora e acumula.
    """

    def __init__(self, erros):
        self.erros = erros
        super().__init__('ato invalido')


def importar(extracao, usuario, versao, atos):
    """Grava os atos marcados da revisão finalizada e devolve a resposta.

    Ordem das travas (a mesma da exclusão do PDF, para não deadlockar):
    ``DocumentoDigital`` → job → extração → ``Documento`` — e, por último,
    os nomes de cartório a criar, todos antes do primeiro ato e em ordem
    global (``_travar_cartorios_a_criar``, #263 rodada 5). Job ``importado``
    devolve o resultado gravado (idempotência); qualquer outro estado que
    não ``revisado`` recusa. A revisão é revalidada ANTES do token: o
    cadastro escolhido que some (FK ``SET_NULL``) muda a linha e envelhece
    o token da tela, e o 409 genérico esconderia ONDE a decisão se perdeu
    (#263 rodada 3). Erros de ato viram ``ImportacaoInvalida`` DENTRO da
    transação: nada persiste.
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
        dados = revisao.dados_revisados(extracao)
        if versao != services.versao_bloco(extracao):
            raise services.ConflitoVersao([])

        marcados = _atos_marcados(dados, atos)
        # Trava SÓ o Documento (#263 rodada 3): sem ``of``, o JOIN do
        # select_related travaria também o Imovel — ciclo possível com o
        # cadastro manual, que trava o Documento e insere documento de
        # origem no mesmo imóvel.
        documento = (
            Documento.objects.select_related('imovel')
            .select_for_update(of=('self',))
            .get(pk=job.documento_digital.documento_id)
        )
        # Nomes de cartório: travados aqui, todos e em ordem global, antes
        # do primeiro ato (#263 rodada 5).
        nomes_travados = _travar_cartorios_a_criar(dados, marcados)
        imovel = documento.imovel
        linhas = _linhas_por_chave(extracao)
        # Chave de identificação ('cpf', digitos) / ('rg', nome, rg) → pessoa.
        cache_pessoas: dict[tuple, Pessoas] = {}
        documentos_usuario = documentos_for_user(usuario)
        # Lançamentos dos atos anteriores DESTA importação: colidir com eles
        # é duplicata interna do payload — o rollback global os desfaz, então
        # nunca viram ``existente`` (#263 rodada 3).
        lancamentos_importados: set[int] = set()

        respostas = []
        importadas = []
        for ato in dados.atos:
            if ato.chave not in marcados:
                respostas.append(_linha_resposta(
                    ato.chave, _rotulo(ato.chave, linhas), 'ignorado',
                ))
                continue
            # Savepoint de verdade (#263 rodada 2): o erro levanta
            # ``_AtoInvalido`` DENTRO do atomic, que desfaz na hora o que
            # este ato gravou (lançamento parcial, pessoas, cartórios) — o
            # que gravou fica de pé para os atos seguintes. As entradas de
            # cache criadas no ato desfeito também são descartadas: elas
            # apontariam para registros que o rollback apagou.
            chaves_antes = set(cache_pessoas)
            try:
                with transaction.atomic():
                    resposta, erros = _importar_ato(
                        ato, documento, imovel, usuario, job, linhas,
                        cache_pessoas, documentos_usuario,
                        lancamentos_importados, nomes_travados,
                    )
                    if erros.itens:
                        raise _AtoInvalido(erros)
            except _AtoInvalido as exc:
                for chave_nova in set(cache_pessoas) - chaves_antes:
                    cache_pessoas.pop(chave_nova, None)
                resposta = _linha_resposta(
                    ato.chave, _rotulo(ato.chave, linhas), 'erro',
                    erros=exc.erros.itens,
                )
            else:
                importadas.append(ato.chave)
                lancamentos_importados.add(resposta['lancamento_id'])
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
    cache_pessoas, documentos_usuario, lancamentos_importados,
    nomes_travados,
):
    """Grava um ato (lançamento + origem + partes) e devolve a linha resposta.

    Sempre devolve ``(resposta | None, erros)``: com erro, o chamador levanta
    ``_AtoInvalido`` DENTRO do savepoint, que desfaz na hora o que este ato
    criou (lançamento parcial, cartórios, pessoas, documento de origem).
    ``lancamentos_importados`` são os gravados pelos atos anteriores desta
    importação (duplicata contra eles é interna, sem ``existente``);
    ``nomes_travados``, os nomes de cartório que o ``importar`` já travou.
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
        Lancamento.objects.exclude(pk__in=lancamentos_importados),
    )
    if duplicado is not None:
        erros.add(
            chave, 'lancamento_duplicado',
            'Já existe um lançamento deste ato no documento.',
            existente=_existente(duplicado),
        )
        return None, erros
    if lancamentos_importados and _lancamento_duplicado(
        documento, tipo, ato.data, ato.numero_lancamento,
        Lancamento.objects.filter(pk__in=lancamentos_importados),
    ) is not None:
        # O outro lançamento só existe dentro desta transação: apontá-lo
        # como ``existente`` levaria a tela a um registro que o rollback
        # global apaga (#263 rodada 3).
        erros.add(
            chave, 'ato_duplicado_na_importacao',
            'Outro ato marcado nesta importação grava o mesmo lançamento.',
        )
        return None, erros

    # Cartório de transmissão é opcional; o da origem, exigido pela origem.
    criados_cartorios = []
    cartorio_transmissao = _resolver_cartorio(
        ato.cartorio_transmissao_id, ato.cartorio_transmissao_criar_novo,
        ato.cartorio_transmissao_nome,
        f'{chave}/cartorio_transmissao', criados_cartorios, nomes_travados,
    )
    if cartorio_transmissao is None and ato.cartorio_transmissao_id is not None:
        # Escolha da revisão que sumiu entre a leitura e a gravação: o ato
        # não grava sem o cartório escolhido (#263 rodada 3, como a origem).
        erros.add(
            f'{chave}/cartorio_transmissao', 'decisao_perdida',
            'O cartório escolhido para a transmissão não existe mais.',
        )
        return None, erros

    origem = ato.origem
    numero = (origem.get('numero') or '').strip() if origem else ''
    tipo_informado = origem.get('tipo_documento') if origem else None
    texto_origem = None
    mapeamento = None
    cartorio_origem = None
    # O cartório da origem é resolvido SEMPRE que há origem — inclusive
    # quando ela só tem o cartório, sem número/tipo (#263 rodada 4,
    # CodeRabbit): o tipo do lançamento pode exigir cartório de origem e a
    # gravação precisa dele na FK. Número/tipo são exigidos só na montagem
    # do texto/mapeamento (abaixo), nunca para resolver o cartório.
    if origem is not None:
        cartorio_origem = _resolver_cartorio(
            origem.get('cartorio_id'), origem.get('cartorio_criar_novo'),
            origem.get('cartorio_nome'), f'{chave}/origem/cartorio',
            criados_cartorios, nomes_travados,
        )
        if cartorio_origem is None:
            if origem.get('cartorio_id') is not None:
                erros.add(
                    f'{chave}/origem/cartorio', 'decisao_perdida',
                    'O cartório escolhido para a origem não existe mais.',
                )
                return None, erros
            if numero or tipo_informado:
                erros.add(
                    f'{chave}/origem/cartorio', 'valor_obrigatorio',
                    'O cartório da origem é obrigatório para importar o ato.',
                )
                return None, erros
        elif numero or tipo_informado:
            if not numero:
                erros.add(
                    f'{chave}/origem/numero', 'valor_obrigatorio',
                    'O número da origem é obrigatório para importar o ato.',
                )
                return None, erros
            tipo_documento = _tipo_documento_da_origem(origem, numero)
            try:
                normalizado = normalizar_numero_documento(
                    numero, tipo_documento,
                )
            except (TypeError, ValueError) as exc:
                # Mensagem fixa do util: cita o prefixo, nunca o número
                # inteiro.
                erros.add(
                    f'{chave}/origem/numero', 'valor_incompativel_destino',
                    str(exc),
                )
                return None, erros
            texto_origem = PREFIXO_TIPO_DOCUMENTO[tipo_documento] + normalizado
            # O valor PERSISTIDO ganha prefixo: a revisão validou o limite
            # da linha (sem prefixo), o destino valida o valor final.
            # Estourou o max_length do LancamentoOrigem.numero é erro da
            # linha da origem — nunca um ValidationError cru lá embaixo
            # virando 500 (#263 rodada 2).
            limite_origem = destinos.destino_de(
                f'{chave}/origem/numero',
            ).max_length
            if limite_origem and len(texto_origem) > limite_origem:
                erros.add(
                    f'{chave}/origem/numero', MOTIVO_LIMITE,
                    'O número da origem, com o prefixo do tipo documental, '
                    'ultrapassa o limite do destino.',
                )
                return None, erros
            mapeamento = [{
                'indice': 0,
                'origem': texto_origem,
                # Tipo documental ESTRUTURADO revisado: viaja com o
                # mapeamento até a criação do documento de origem — o
                # texto livre nunca é reparseado ('T42.718' com pontuação
                # não vira 'M42' + 'M718') (#263 rodada 4, Codex P1).
                'tipo_documento': tipo_documento,
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
    except ValidationError:
        # Defesa em profundidade: o serviço da origem ainda pode recusar
        # algo que nem a revisão nem o pre-check acima viram. Vira erro da
        # linha da origem com mensagem fixa, nunca um 500 (#263 rodada 2).
        erros.add(
            f'{chave}/origem/numero', 'valor_incompativel_destino',
            'O número da origem não pôde ser gravado no lançamento.',
        )
        return None, erros
    finally:
        LancamentoOrigemService.limpar_mapeamento(lancamento)
        # Documento de origem que o caminho de criação devolveu — o do
        # sinal post_save inclusive, que cria durante o save. Nunca o diff
        # do imóvel: ele não está travado e pegaria o documento de outro
        # escritor (#263 rodada 3).
        documentos_origem = (
            LancamentoOrigemService.consumir_documentos_criados(lancamento)
        )

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
        # Documento de origem criado (início de matrícula): entra na
        # auditoria como qualquer outro objeto gravado (#263 rodada 2) —
        # sem isso ele nascia sem vínculo com o PDF nem com o ato.
        registros.extend(
            ('Documento', pk, f'{chave}/origem/numero')
            for pk in documentos_origem
        )

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


def _rg_normalizado(rg):
    """RG comparável: só alfanumérico, em caixa alta (o RG não é só dígito)."""
    return re.sub(r'[^A-Z0-9]', '', (rg or '').upper())


def _resolver_pessoa(parte, cache_pessoas, erros):
    """Pessoa da parte (decisão D): escolhida, reutilizada por identificação ou nova.

    Reuso exige IDENTIFICAÇÃO, nunca nome puro (homônimo existe): CPF por
    cache ou cadastro; RG por cache, e só com o nome igual. Sem CPF e sem
    RG cada ato grava o seu cadastro — não há evidência de mesma pessoa.
    Se o CPF e o RG da MESMA parte apontam para pessoas distintas, é
    conflito: erro na linha da parte, nunca fusão silenciosa (#263 rodada 2).

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
    cpf = _so_digitos(parte.cpf) if parte.cpf else ''
    rg = _rg_normalizado(parte.rg)
    chave_cpf = ('cpf', cpf) if cpf else None
    chave_rg = ('rg', _normalizar_nome(nome), rg) if rg else None

    pessoa_cpf = None
    if chave_cpf is not None:
        pessoa_cpf = cache_pessoas.get(chave_cpf)
        if pessoa_cpf is None:
            pessoa_cpf = Pessoas.objects.filter(cpf=cpf).first()
    pessoa_rg = cache_pessoas.get(chave_rg) if chave_rg is not None else None

    # Checagem DEFENSIVA (#263 rodada 3): ``dados_revisados`` entrega CPF
    # ou RG por parte, nunca os dois (a linha do documento tem um destino
    # só). Fica de guarda caso o contrato da parte passe a trazer ambos.
    if (
        pessoa_cpf is not None and pessoa_rg is not None
        and pessoa_cpf.pk != pessoa_rg.pk
    ):
        erros.add(
            f'{chave_parte}/documento_identificacao/valor',
            'decisao_conflitante',
            'O CPF e o RG desta parte apontam para pessoas cadastradas '
            'diferentes; revise a identificação da parte.',
        )
        return None, False

    pessoa = pessoa_cpf or pessoa_rg
    criada = False
    if pessoa is None:
        pessoa = Pessoas(
            nome=nome, cpf=cpf or None, rg=parte.rg,
        )
        try:
            pessoa.full_clean()
        except ValidationError as exc:
            erros.do_modelo(exc, 'dominial.Pessoas', chave_parte=chave_parte)
            return None, False
        try:
            # Savepoint: o CPF pode ser gravado por OUTRA importação (outro
            # documento) entre o lookup e o INSERT — a trava do Documento
            # não cobre Pessoas. Decisão D: relê a linha vencedora e
            # REUTILIZA; a unicidade de CPF nunca sobe como 500 (#263
            # rodada 4, Greptile P1).
            with transaction.atomic():
                pessoa.save()
        except IntegrityError:
            vencedora = (
                Pessoas.objects.filter(cpf=cpf).first() if cpf else None
            )
            if vencedora is None:
                raise
            pessoa = vencedora
        else:
            criada = True
    if chave_cpf is not None:
        cache_pessoas[chave_cpf] = pessoa
    if chave_rg is not None:
        cache_pessoas[chave_rg] = pessoa
    return pessoa, criada


def _nome_da_trava(nome):
    """Nome do cartório como a trava o compara: sem bordas e sem caixa."""
    return (nome or '').strip().casefold()


def _chave_da_trava(nome):
    """Id ``bigint`` da trava do nome — e a ordem global das travas.

    Calculado aqui, não com ``hashtext`` no SQL: a ordem tem que ser a do
    id TRAVADO. Ordenar pelos nomes e travar o hash deles deixaria dois
    nomes de hash colidente inverterem a sequência entre duas importações
    (o ABBA de volta). 63 bits do blake2b: estável entre processos (o
    ``hash()`` do Python não é) e nunca negativo no ``bigint``.
    """
    digest = hashlib.blake2b(
        _nome_da_trava(nome).encode('utf-8'), digest_size=8,
    ).digest()
    return int.from_bytes(digest, 'big') >> 1


def _travar_cartorios_a_criar(dados, marcados):
    """Trava de uma vez, em ordem global, os nomes que a importação pode criar.

    Travar no uso, na ordem dos atos, fechava ABBA entre importações em
    documentos distintos (#263 rodada 5, Greptile P1): X travava ``A``
    (transmissão) e depois ``B`` (origem), Y travava ``B`` e depois ``A``
    — o Postgres abortava uma delas com 500. Em ordem crescente do id e
    antes do primeiro ato (nada gravado ainda), duas importações disputam
    os nomes na MESMA sequência: uma espera a outra, nunca fecha ciclo.

    Os pedidos espelham as duas chamadas do ``_resolver_cartorio`` no
    ``_importar_ato`` — transmissão e, havendo origem, o cartório dela —
    com a mesma regra: "criar novo" com nome não vazio. Cartório escolhido
    pelo id nunca trava. Nome já cadastrado trava também, por escolha: o
    conjunto vem do payload, não da tabela — consultá-la antes abriria a
    janela do nome que some e o mandaria para uma trava fora de ordem. Ato
    que vai parar antes do cartório (tipo inexistente, duplicata) entra
    mesmo assim: travar a mais só serializa, a menos reabriria o ABBA.

    Devolve os nomes travados, normalizados: ``_resolver_cartorio`` não os
    trava de novo.
    """
    nomes = set()
    for ato in dados.atos:
        if ato.chave not in marcados:
            continue
        pedidos = [(
            ato.cartorio_transmissao_criar_novo,
            ato.cartorio_transmissao_nome,
        )]
        if ato.origem is not None:
            pedidos.append((
                ato.origem.get('cartorio_criar_novo'),
                ato.origem.get('cartorio_nome'),
            ))
        nomes.update(
            _nome_da_trava(nome) for criar_novo, nome in pedidos
            if criar_novo and _nome_da_trava(nome)
        )
    for nome in sorted(
        nomes, key=lambda candidato: (_chave_da_trava(candidato), candidato),
    ):
        _trava_nome_cartorio(nome)
    return frozenset(nomes)


def _trava_nome_cartorio(nome):
    """Serializa a criação de cartório pelo nome normalizado (decisão E).

    ``pg_advisory_xact_lock`` fecha, entre importações em documentos
    distintos, a janela busca→INSERT do ``_resolver_cartorio``: a trava do
    ``Documento`` não cobre ``Cartorios`` e só o CNS é unique (e é gerado)
    — sem isso, duas importações que criam o MESMO nome gravam duas linhas
    (#263 rodada 4, Greptile P1). Quem trava é o
    ``_travar_cartorios_a_criar``; o ``_resolver_cartorio``, só no ramo
    defensivo. A trava morre com a transação; no sqlite (um escritor por
    vez) é no-op.
    """
    if connection.vendor != 'postgresql':
        return
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT pg_advisory_xact_lock(%s::bigint)',
            [_chave_da_trava(nome)],
        )


def _resolver_cartorio(
    cartorio_id, criar_novo, nome, chave_linha, criados, nomes_travados,
):
    """FK escolhida ou cartório por nome (decisão E); cria se não achar.

    ``criados`` acumula ``(modelo, cartorio, chave_linha)`` para o vínculo
    de auditoria — cartório reutilizado não gera vínculo novo.
    ``nomes_travados`` (do ``_travar_cartorios_a_criar``) estão sob a trava
    desde antes do primeiro ato: a busca deles já é a re-busca SOB a trava
    — outra importação que criou o mesmo nome antes já commitou, e a linha
    vencedora é reaproveitada.
    """
    if criar_novo:
        nome = (nome or '').strip()
        if not nome:
            return None
        cartorio = Cartorios.objects.filter(nome__iexact=nome).first()
        if cartorio is None and _nome_da_trava(nome) not in nomes_travados:
            # Defensivo: o conjunto pré-travado cobre todo "criar novo" do
            # payload, então este ramo só roda se esta regra e a do
            # ``_travar_cartorios_a_criar`` divergirem — por isso não
            # reintroduz o ABBA. Se rodar, trava (a única fora da ordem
            # global) e re-busca, como na rodada 4: nunca cria sem trava.
            _trava_nome_cartorio(nome)
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


def _lancamento_duplicado(documento, tipo, data, numero, lancamentos=None):
    """Lançamento existente que colide com o ato, ou None.

    Mesma regra do fluxo manual (``lancamento_validacao_service``): a tupla
    (documento, tipo, data, número) — com número nulo casando null e '' — e
    ainda o número sozinho dentro do documento, mudando tipo ou data.
    ``lancamentos`` restringe onde procurar (padrão: todos).
    """
    if lancamentos is None:
        lancamentos = Lancamento.objects.all()
    lancamentos = lancamentos.select_related('documento__imovel')
    filtro = Q(documento=documento, tipo=tipo)
    filtro &= Q(data=data) if data is not None else Q(data__isnull=True)
    if numero:
        filtro &= Q(numero_lancamento=numero)
    else:
        filtro &= Q(numero_lancamento__isnull=True) | Q(numero_lancamento='')
    existente = lancamentos.filter(filtro).first()
    if existente is not None:
        return existente
    if numero:
        return lancamentos.filter(
            documento=documento, numero_lancamento=numero,
        ).first()
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
    """Linhas EFETIVAMENTE incluídas dos atos importados → ``importado``.

    Linha descartada (direta ou por ancestral descartado) continua com o
    status e a autoria que a revisão deixou: importação não reescreve
    decisão de descarte (#263 rodada 2). Mesma noção de incluída do
    ``revisao._contexto_revisao`` (a que alimenta a gravação).
    """
    incluidas, _ = revisao._contexto_revisao(extracao)
    chaves_atos = set(chaves_atos)
    alvos = [
        chave for chave in incluidas
        if chave in chaves_atos or any(
            chave.startswith(f'{ato}/') for ato in chaves_atos
        )
    ]
    extracao.campos.filter(chave__in=alvos).update(
        status_revisao='importado',
        revisado_por=usuario,
        revisado_em=timezone.now(),
    )


def pendencias_para_resposta(extracao):
    """Pendências estruturadas da revisão invalidada, para a resposta 422.

    A recusa em si já vem do ``RevisaoInvalidada``; o que falta à tela é
    saber ONDE — cada pendência com sua chave de linha. Uma PARTE ou um
    CARTÓRIO que a revisão finalizou como escolha e voltou a ficar
    pendente só acontece quando o cadastro escolhido desapareceu (FKs
    ``SET_NULL``): o motivo vira ``decisao_perdida`` na linha da parte
    (#263 rodada 2) ou do cartório — origem, transmissão (rodada 3).
    """
    linhas = _linhas_por_chave(extracao)
    saida = []
    for pendencia in revisao.pendencias(extracao):
        motivo = pendencia['motivo']
        campo = linhas.get(pendencia['chave'])
        if (
            motivo == 'escolha_pendente'
            and campo is not None
            and campo.tipo_valor in ('parte', 'cartorio')
        ):
            motivo = 'decisao_perdida'
        saida.append({'chave': pendencia['chave'], 'motivo': motivo})
    return saida


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
