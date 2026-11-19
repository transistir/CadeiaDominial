"""Travas de criação serializada: nomes de cartório (decisão E) e CPFs de
partes (decisão D) — tomadas de uma vez, em ordem global, antes do primeiro
ato (#263 rodadas 5 e 6).

Os nomes de trava são chamados VIA O PACOTE (``importacao._trava_cpf``): os
testes fazem ``patch.object`` em ``ia_ocr.importacao`` e o patch só vale se o
call site resolver o nome no objeto do pacote, a cada chamada.
"""
import hashlib

from django.db import connection

from .. import importacao
from ..revisao import _so_digitos


def _nome_da_trava(nome):
    """Nome do cartório como a trava o compara: sem bordas e sem caixa."""
    return (nome or '').strip().casefold()


def _id_da_trava(material):
    """Id ``bigint`` de uma trava de importação, do material já qualificado.

    63 bits do blake2b: estável entre processos (o ``hash()`` do Python
    não é) e nunca negativo no ``bigint``. Calculado no Python, não com
    ``hashtext`` no SQL, porque a ordem global das travas tem que ser a do
    id TRAVADO — ordenar pelo material e travar o hash deixaria dois
    materiais de hash colidente inverterem a sequência entre duas
    importações (o ABBA de volta).
    """
    digest = hashlib.blake2b(material.encode('utf-8'), digest_size=8).digest()
    return int.from_bytes(digest, 'big') >> 1


def _chave_da_trava(nome):
    """Id ``bigint`` da trava do nome de cartório — e a ordem global delas."""
    return _id_da_trava(_nome_da_trava(nome))


def _chave_cpf_da_trava(cpf):
    """Id ``bigint`` da trava do CPF — em espaço SEPARADO do do cartório.

    O material do CPF é hasheado com o prefixo ``'cpf:'``: sem a
    qualificação, um CPF colidiria com o id da trava do cartório cujo nome
    normalizado fosse o mesmo material — dois tipos de trava distintos
    disputando o MESMO id, uma importação esperando a outra sem disputar
    nada (#263 rodada 6, Codex P1).
    """
    return _id_da_trava(f'cpf:{cpf}')


def _travar_cpfs_a_criar(dados, marcados):
    """Trava de uma vez, em ordem global, os CPFs que a importação pode criar.

    Espelho do ``_travar_cartorios_a_criar`` para a decisão D (rodada 6,
    Codex P1): duas importações em documentos distintos que criam o MESMO
    CPF — ou CPFs distintos em ordens opostas de atos — disputam as
    entradas não commitadas do índice unique de ``Pessoas.cpf`` na ordem
    dos atos, e o Postgres aborta uma delas com ``deadlock_detected``. O
    handler de ``IntegrityError`` do ``_resolver_pessoa`` não vê o
    deadlock (é ``OperationalError``) e a trava do ``Documento`` não cobre
    ``Pessoas``. Em ordem crescente do id e antes do primeiro ato (nada
    gravado ainda), duas importações disputam os CPFs na MESMA sequência:
    uma espera a outra, nunca fecha ciclo.

    O conjunto espelha as partes do ``_resolver_pessoa`` — CPFs de partes
    com ``criar_novo`` e CPF não vazio, normalizados por ``_so_digitos``
    (o mesmo material do lookup e do INSERT, máscara inclusive). Parte
    escolhida pelo id nunca trava. Parte sem CPF não trava: sem material
    não há índice a disputar, e o nome puro nunca identifica (homônimo
    existe). Ato que vai parar antes das partes (tipo inexistente,
    duplicata) entra mesmo assim: travar a mais só serializa, travar a
    menos reabriria o ABBA.
    """
    cpfs = set()
    for ato in dados.atos:
        if ato.chave not in marcados:
            continue
        for parte in ato.partes:
            if not parte.criar_novo or not parte.cpf:
                continue
            cpf = _so_digitos(parte.cpf)
            if cpf:
                cpfs.add(cpf)
    for cpf in sorted(cpfs, key=lambda candidato: (
        _chave_cpf_da_trava(candidato), candidato,
    )):
        importacao._trava_cpf(cpf)


def _trava_cpf(cpf):
    """Serializa a criação de pessoa pelo CPF (decisão D).

    Espelho do ``_trava_nome_cartorio`` para CPFs de partes a criar: fecha
    a janela busca→INSERT do ``_resolver_pessoa`` — e, com as travas todas
    tomadas antes do primeiro ato em ordem global, elimina o deadlock do
    índice unique de ``Pessoas.cpf`` entre duas importações (#263 rodada
    6, Codex P1). O cadastro manual não passa por aqui, por isso o handler
    de ``IntegrityError`` fica de pé como defesa. A trava morre com a
    transação; no sqlite (um escritor por vez) é no-op.
    """
    if connection.vendor != 'postgresql':
        return
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT pg_advisory_xact_lock(%s::bigint)',
            [_chave_cpf_da_trava(cpf)],
        )
