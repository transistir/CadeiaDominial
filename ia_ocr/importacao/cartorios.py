"""Cartório da transmissão e da origem (decisão E) e avisos de livro/folha.

``_trava_nome_cartorio`` é chamado VIA O PACOTE (``importacao._trava_nome_cartorio``):
os testes fazem ``patch.object`` em ``ia_ocr.importacao`` e o patch só vale se
o call site resolver o nome no objeto do pacote, a cada chamada.
"""
import uuid

from django.db import connection

from dominial.models import Cartorios

from .. import importacao, revisao
from .travas import _chave_da_trava, _nome_da_trava


def _avisos_livro_folha_da_origem(livro, folha):
    """Avisos do que o documento NÃO traz da origem (#324): um por campo.

    Lê o que ficou GRAVADO no lançamento (já sem bordas): é o mesmo cálculo
    da resposta da importação e do replay do job já importado. Cita só o
    que falta, com a MESMA frase por campo que a tela mostra
    (``revisao.TEXTO_NAO_CONSTA``); o status do ato segue ``criado``.
    """
    avisos = []
    if not (livro or '').strip():
        avisos.append(
            revisao.TEXTO_NAO_CONSTA[revisao.MOTIVO_LIVRO_ORIGEM_NAO_CONSTA]
        )
    if not (folha or '').strip():
        avisos.append(
            revisao.TEXTO_NAO_CONSTA[revisao.MOTIVO_FOLHA_ORIGEM_NAO_CONSTA]
        )
    return avisos


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
        importacao._trava_nome_cartorio(nome)
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
            importacao._trava_nome_cartorio(nome)
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
