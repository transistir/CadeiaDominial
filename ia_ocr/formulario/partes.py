"""Partes do ato: transmitentes e adquirentes no formato do ``_pessoa_form.html``."""

from .prefill import input_do_campo
from .texto import _evidencia


def _partes(ato, linhas, nomes_pessoas, evidencias):
    """``(transmitentes, adquirentes)`` no formato do ``_pessoa_form.html``.

    Cadastro escolhido: nome e id do CADASTRO — o serviço do formulário só
    reaproveita a pessoa vinculada quando o texto digitado é igual ao nome
    dela. Sem escolha (ou "criar novo"): o nome lido, id vazio. CPF/RG não
    entram (regra I-11f); ver ``_lidos_sem_campo``.
    """
    listas = {'transmitente': [], 'adquirente': []}
    for parte in ato.partes:
        lista = listas.get(parte.papel)
        if lista is None:
            continue
        nome_do_cadastro = (
            nomes_pessoas.get(parte.pessoa_id)
            if parte.pessoa_id is not None else None
        )
        nome = (nome_do_cadastro or parte.nome or '').strip()
        if not nome:
            continue
        lista.append({
            'id': str(parte.pessoa_id) if nome_do_cadastro else '',
            'nome': nome,
        })
        chave_do_nome = f'{parte.chave}/nome'
        evidencia = _evidencia(linhas, chave_do_nome)
        if evidencia is not None:
            nome_do_input = input_do_campo(chave_do_nome, papel=parte.papel)
            evidencias[f'{nome_do_input}[{len(lista) - 1}]'] = evidencia
    return listas['transmitente'], listas['adquirente']
