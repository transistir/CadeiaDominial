"""Orquestração: ``importar`` e ``resumo`` — transação, travas, resposta.

``_atos_marcados`` é chamado VIA O PACOTE (``importacao._atos_marcados``): os
testes fazem ``patch.object`` em ``ia_ocr.importacao`` e o patch só vale se o
call site resolver o nome no objeto do pacote, a cada chamada.
"""
import re

from django.db import transaction
from django.utils import timezone

from dominial.managers import documentos_for_user
from dominial.models import Documento, DocumentoDigital, Pessoas
from dominial.services.cache_service import CacheService

from .. import importacao, revisao, services
from ..estados import IMPORTADO, REVISADO
from ..models import ImportacaoIA, OcrJob
from ..rotulos import analisar_rotulo
from .ato import _importar_ato
from .ato_documento import (
    _existente, _lancamento_duplicado, _resolver_tipo_e_numero,
)
from .avisos import _gravar_avisos_da_importacao
from .cartorios import _travar_cartorios_a_criar
from .erros import _AtoInvalido, ImportacaoInvalida
from .resposta import (
    _linha_resposta, _linhas_por_chave, _resultado_gravado, _rotulo,
    _rotulo_efetivo,
)
from .travas import _travar_cpfs_a_criar

MOTIVO_TRANSICAO = 'importacao_ia'


def importar(extracao, usuario, versao, atos):
    """Grava os atos marcados da revisão finalizada e devolve a resposta.

    Ordem das travas (a mesma da exclusão do PDF, para não deadlockar):
    ``DocumentoDigital`` → job → extração → ``Documento`` — e, por último,
    os nomes de cartório a criar e os CPFs de partes a criar, todos antes
    do primeiro ato e em ordem global (``_travar_cartorios_a_criar``,
    rodada 5; ``_travar_cpfs_a_criar``, rodada 6). Job ``importado``
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

        marcados = importacao._atos_marcados(dados, atos)
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
        # do primeiro ato (#263 rodada 5). CPFs de partes a criar: o mesmo
        # desenho, para o índice unique de ``Pessoas.cpf`` não fechar ciclo
        # entre duas importações (#263 rodada 6).
        nomes_travados = _travar_cartorios_a_criar(dados, marcados)
        _travar_cpfs_a_criar(dados, marcados)
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
        # Avisos produzidos pelos atos que o replay não recalcula (#324
        # rodada 4): ato desfeito não deixa registro aqui.
        avisos_gravados: dict[str, list[dict]] = {}
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
            # Rótulo do ato analisado UMA vez (#322): lido pelo EFETIVO
            # (``valor_final`` do revisor ou, sem ele, ``normalized``/
            # ``raw`` — P1 das rodadas 4–5), ele PREVALECE na decisão do
            # tipo (tipo_sugerido só entra na falta dele) e o número
            # gravado é o composto canônico do V1 ('R5 M237', igual ao
            # fluxo manual). Rótulo não reconhecido mantém o
            # comportamento de antes — o bucket deles é decisão da UI
            # (#321).
            rotulo = analisar_rotulo(_rotulo_efetivo(ato.chave, linhas))
            try:
                with transaction.atomic():
                    resposta, erros = _importar_ato(
                        ato, rotulo, documento, imovel, usuario, job, linhas,
                        cache_pessoas, documentos_usuario,
                        lancamentos_importados, nomes_travados,
                        avisos_gravados=avisos_gravados,
                    )
                    if erros.itens:
                        raise _AtoInvalido(erros)
            except _AtoInvalido as exc:
                for chave_nova in set(cache_pessoas) - chaves_antes:
                    cache_pessoas.pop(chave_nova, None)
                avisos_gravados.pop(ato.chave, None)
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
        # Mesma transação da transição: o aviso gravado e o job ``importado``
        # nascem juntos (ou nenhum dos dois).
        _gravar_avisos_da_importacao(extracao, avisos_gravados)
        job.transicionar(IMPORTADO, usuario=usuario, motivo=MOTIVO_TRANSICAO)
        transaction.on_commit(lambda: (
            CacheService.invalidate_documentos_imovel(imovel.pk),
            CacheService.invalidate_tronco_principal(imovel.pk),
        ))
        return {'ok': True, 'linhas': respostas}


def resumo(extracao):
    """Prévia consultiva da importação (GET do PR2): atos, tipo e duplicados.

    Não trava nada nem grava: é o que a tela de confirmação exibe antes de
    o usuário marcar os atos e disparar o POST. O ``tipo`` de cada item é o
    que a GRAVAÇÃO usará (P2-2, rodada 4) — a mesma resolução do
    ``_importar_ato`` — e o conflito rótulo × tipo_sugerido aparece no
    ``aviso`` do item (str ou None) antes de o usuário confirmar.
    """
    dados = revisao.dados_revisados(extracao)
    linhas = _linhas_por_chave(extracao)
    job = extracao.ocr_job
    documento = Documento.objects.select_related('imovel').get(
        pk=job.documento_digital.documento_id,
    )
    atos = []
    for ato in dados.atos:
        # Mesma resolução do tipo/número que a gravação usa (#322, rodadas
        # 4–5): o rótulo — lido pelo EFETIVO (``valor_final`` do revisor
        # ou, sem ele, ``normalized``/``raw``) — PREVALECE; o
        # tipo_sugerido só decide na falta dele.
        rotulo = analisar_rotulo(_rotulo_efetivo(ato.chave, linhas))
        tipo, numero, avisos = _resolver_tipo_e_numero(ato, rotulo, documento)
        duplicado = (
            _lancamento_duplicado(documento, tipo, ato.data, numero)
            if tipo is not None else None
        )
        atos.append({
            'chave': ato.chave,
            'rotulo': _rotulo(ato.chave, linhas),
            'tipo': tipo.tipo if tipo is not None else ato.tipo,
            'partes': len(ato.partes),
            'duplicado': duplicado is not None,
            'existente': _existente(duplicado) if duplicado else None,
            'erro': None if tipo is not None else 'tipo_inexistente',
            'aviso': avisos[0] if avisos else None,
        })
    return {'atos': atos}


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
