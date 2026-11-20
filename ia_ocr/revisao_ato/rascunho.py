"""Rascunho do ato na SESSÃO: navegar entre atos não escreve no banco."""

from django.http import QueryDict

# Chave da sessão: {extracao.pk: {indice: {input: [valores]}}}. Só os últimos
# ``LIMITE_EXTRACOES_NO_RASCUNHO`` documentos em revisão ficam guardados.
CHAVE_SESSAO = 'ia_ocr_rascunhos'
LIMITE_EXTRACOES_NO_RASCUNHO = 3
# Campos do POST que nunca entram no rascunho: o token CSRF é do pedido, o
# destino da navegação é uma instrução e a identidade da extração é do
# POST que a mandou — nada disso é dado do ato.
FORA_DO_RASCUNHO = frozenset({'csrfmiddlewaretoken', '_ir_para', 'extracao_id'})


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
