"""Token de versão e gravação atômica de blocos de decisão da revisão.

``versao_bloco`` e ``salvar_bloco`` resolvem ``versao_linha`` e
``IndicePessoas`` VIA O PACOTE (``services.<nome>``): os testes fazem
``mock.patch`` em ``ia_ocr.services`` e o patch só vale se o call site
resolver o nome no objeto do pacote, a cada chamada.
"""

import hashlib

from django.db import transaction
from django.utils import timezone

from .. import estados, services, valores
from ..models import ExtracaoSugerida, OcrJob
from ..revisao import (
    IndiceCartorios, aplicar_linha, comarca_do_documento, fallback_cartorio,
    garantir_placeholders_obrigatorios, identidade_parte, linha_ignorada,
    pendencias, pendencias_sem_atos,
)
from .erros import ConflitoVersao, ExtracaoRecusada


def _campos_ordenados(extracao, campos=None):
    """Linhas pela chave, sempre em Python (GET e save usam o mesmo critério).

    Sem ``campos``, ``order_by`` evita a cache de ``prefetch_related`` de uma
    extração carregada antes da gravação (o token sairia do estado antigo).
    """
    if campos is None:
        campos = extracao.campos.order_by('chave')
    return sorted(campos, key=lambda campo: campo.chave)


def versao_bloco(extracao, campos=None) -> str:
    """Hash do pk da extração e das versões persistidas das linhas, pela chave.

    O pk entra porque a reextração recria as linhas no mesmo estado: sem ele,
    o token de uma página antiga valeria na extração substituta.

    Com ``campos``, o hash sai dessa lista (sem nova consulta): a tela usa a
    mesma lista que exibe, para que um save entre as duas leituras não gere
    token novo sobre valores antigos.
    """
    versoes = ''.join(
        services.versao_linha(campo) for campo in _campos_ordenados(extracao, campos)
    )
    return hashlib.sha256(f'{extracao.pk}:{versoes}'.encode('utf-8')).hexdigest()


def _travar_extracao_revisao(extracao):
    """Dentro de atomic, trava job antes da extração, como a reextração."""
    job = OcrJob.objects.select_for_update().get(pk=extracao.ocr_job_id)
    travada = ExtracaoSugerida.objects.select_for_update().get(
        pk=extracao.pk, ocr_job=job,
    )
    vigente = job.extracao_vigente()
    if vigente is None or vigente.pk != travada.pk:
        raise ExtracaoRecusada('extracao_nao_vigente')
    travada.ocr_job = job
    return travada


def _validar_limites_bloco(extracao, decisoes):
    """Revalida os limites das linhas enviadas neste bloco.

    A sugestão nunca passou pelo formulário; sem esta checagem, um valor
    acima de ``max_length``/``max_digits``/``decimal_places`` só quebraria
    na I-6, depois de a revisão já ter sido dada por concluída.

    Só as linhas presentes em ``decisoes``: a tela salva um card por POST,
    então uma linha intocada acima do limite não pode impedir a correção de
    outra. Na finalização, ``pendencias`` continua bloqueando as intocadas.

    ``pendencias`` já respeita o descarte da própria linha e dos ancestrais
    (ato/parte).
    """
    for pendencia in pendencias(extracao):
        if (
            pendencia['motivo'] == valores.MOTIVO_LIMITE
            and pendencia['chave'] in decisoes
        ):
            erro = valores.ValorInvalido(
                'valor acima do limite do destino'
            )
            erro.chave = pendencia['chave']
            raise erro


def _preparar_fallback_cartorio(extracao, campos, decisoes):
    """Escolha de cartório vinda do fallback da tela: valida contra o índice.

    Para campo ``cartorio`` cujo id escolhido não está nos candidatos atuais,
    o fallback é SEMPRE recalculado (mesmo índice/comarca, ``valor`` da
    decisão em curso) e atribuído em memória quando contém a escolha; fora
    dele, ``aplicar_linha`` mantém a recusa. Nada é gravado (#318): o
    fallback vem sem corte — milhares de ids por campo inflariam o JSON — e
    congelar ``[escolhido]`` no banco fazia o segundo save (trocar de
    cartório) virar 422, pois o recalculo nem rodava. Devolve as chaves
    preparadas com o ``match_candidatos`` original, para o ``save()`` do
    bloco seguinte gravar o estado de antes; ``cartorio_escolhido_id`` é o
    que a tela usa.
    """
    indice = None
    comarca = None
    preparados = {}
    for chave, decisao in decisoes.items():
        campo = campos[chave]
        escolhido = (decisao.get('escolha') or {}).get('cartorio_escolhido_id')
        if (
            escolhido is None or campo.tipo_valor != 'cartorio'
            or escolhido in (campo.match_candidatos or [])
        ):
            continue
        if indice is None:
            indice = IndiceCartorios()
            comarca = comarca_do_documento(extracao)
        fallback = fallback_cartorio(
            campo, indice, comarca, valor=decisao.get('valor'),
        )
        if escolhido in fallback:
            preparados[chave] = campo.match_candidatos
            campo.match_candidatos = fallback
    return preparados


def salvar_bloco(
    extracao, decisoes, usuario, versao_cliente,
) -> tuple[ExtracaoSugerida, str, list[str], list[str]]:
    """Persiste atomicamente decisões indexadas pela chave JSON Pointer.

    Devolve a extração, o token do bloco calculado ainda sob o lock (lido
    depois do commit, ele já poderia incluir a gravação de outro revisor),
    as chaves das partes cuja identidade mudou — nelas a escolha de cadastro
    foi zerada e os candidatos precisam ser relidos do servidor — e as chaves
    dos placeholders criados neste save, que ainda não têm card na tela.
    """
    with transaction.atomic():
        travada = _travar_extracao_revisao(extracao)
        if travada.ocr_job.status != estados.EXTRAIDO:
            raise ExtracaoRecusada('estado_invalido')
        if travada.finalizada_em is not None:
            raise ExtracaoRecusada('extracao_finalizada')

        campos = {campo.chave: campo for campo in travada.campos.all()}
        if any(chave not in campos for chave in decisoes):
            raise ExtracaoRecusada('linha_inexistente')
        if any(linha_ignorada(chave) for chave in decisoes):
            # Tarefa C #322 (revisão Opus): aba aberta antes do deploy pode
            # reenviar o card de valor_transacao — a chave existe numa
            # extração antiga, mas a folha não tem mais destino; aplicar a
            # decisão levantaria ChaveDesconhecida (500). Recusa antes de
            # gravar nada; a view converte em 422.
            raise ExtracaoRecusada('linha_inexistente')
        if versao_cliente != versao_bloco(travada):
            if all('versao' in decisao for decisao in decisoes.values()):
                chaves = [
                    chave for chave, decisao in decisoes.items()
                    if services.versao_linha(campos[chave]) != decisao['versao']
                ]
            else:
                chaves = list(decisoes)
            raise ConflitoVersao(chaves)

        identidades_antes = {
            chave: identidade_parte(chave, campos)
            for chave, campo in campos.items() if campo.tipo_valor == 'parte'
        }
        agora = timezone.now()
        preparados = _preparar_fallback_cartorio(travada, campos, decisoes)
        for chave, decisao in decisoes.items():
            campo = campos[chave]
            argumentos = {
                nome: decisao[nome] for nome in (
                    'incluir', 'valor', 'conferido', 'escolha',
                    'ha_convertido', 'confirmo_conversao',
                ) if nome in decisao
            }
            aplicar_linha(campo, **argumentos, usuario=usuario, agora=agora)
            if chave in preparados:
                # O fallback serviu só para validar a escolha em memória:
                # o banco segue sem lista congelada — o GET recalcula.
                campo.match_candidatos = preparados[chave]
            campo.save()
        # O tipo efetivo pode ter mudado: o novo tipo passa a exigir linhas
        # que a extração original não trouxe (título, descrição, origem).
        campos_novos = [
            campo.chave for campo in garantir_placeholders_obrigatorios(travada)
        ]
        _validar_limites_bloco(travada, decisoes)
        # Só depois de aplicar o bloco inteiro: a escolha antiga enviada
        # junto da correção não pode sobreviver por causa da ordem das linhas.
        indice_pessoas = None
        partes_invalidadas = []
        for chave, identidade_antes in identidades_antes.items():
            identidade = identidade_parte(chave, campos)
            if identidade == identidade_antes:
                continue
            partes_invalidadas.append(chave)
            if indice_pessoas is None:
                indice_pessoas = services.IndicePessoas()
            escolhido, candidatos = indice_pessoas.match(*identidade)
            parte = campos[chave]
            parte.pessoa_escolhida_id = None
            # Mesmo um match único volta como opção, sem decidir pelo revisor.
            parte.match_candidatos = candidatos or (
                [escolhido] if escolhido is not None else []
            )
            parte.criar_novo = False
            parte.revisado_por = usuario
            parte.revisado_em = agora
            parte.save(update_fields=[
                'pessoa_escolhida', 'match_candidatos', 'criar_novo',
                'revisado_por', 'revisado_em',
            ])
        versao = versao_bloco(travada)
    return travada, versao, partes_invalidadas, campos_novos


def _com_bloqueios_de_campo(bloqueios, extracao) -> list[dict]:
    """Junta os bloqueios de campo sem duplicar pares (chave, motivo).

    Sem atos, ``pendencias()`` devolve só ``nenhum_ato``; os bloqueios de
    campo só existem em ``pendencias_sem_atos``. A ordem é a de
    ``pendencias()`` (a tela e o 422 mostram primeiro o que já era visível).
    """
    vistos = {(item['chave'], item['motivo']) for item in bloqueios}
    resultado = list(bloqueios)
    for item in pendencias_sem_atos(extracao):
        par = (item['chave'], item['motivo'])
        if par in vistos:
            continue
        vistos.add(par)
        resultado.append(item)
    return resultado
