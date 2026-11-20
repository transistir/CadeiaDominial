"""Origem do ato: cartório, texto da matrícula/transmissão e lido-sem-campo."""

import re

from dominial.utils.documento_identidade_utils import normalizar_numero_documento

from .. import importacao, revisao
from .prefill import input_do_campo
from .texto import _evidencia

MOTIVO_LIDO_SEM_CAMPO = 'lido_sem_campo'
TEXTO_LIDO_SEM_CAMPO = 'lido, sem campo no lançamento'

# Folhas do A3 que o formulário não tem (``revisao.LINHAS_IGNORADAS``, #328):
# a linha não existe, mas o payload segue com o valor lido.
_ROTULO_DA_FOLHA_IGNORADA = {
    'valor_transacao': 'Valor da transação',
    'detalhes': 'Detalhes',
}

# Separa o tipo (M/T) do número no texto da origem. Igual ao critério de
# ``_origens_separadas_do_post``, mas o número aceita o ponto de milhar que o
# OCR traz (``M42.718``): com ``\d+`` o input visível perdia o ``.718`` e o
# usuário salvava outra matrícula sem perceber (#341, fase 2). Mesma forma de
# "número puro" do parser de rótulos (``importacao._NUMERO_SIMPLES``).
TEXTO_DA_ORIGEM = re.compile(r'^([MT])(\d+(?:\.\d+)*)')


def _cartorio(cartorio_id, nome_da_linha, nomes):
    """``(id, nome)`` em texto para os inputs de cartório.

    Cadastro escolhido: o NOME DO CADASTRO (é o que o autocomplete grava no
    input) com o id. Sem escolha — ou "criar novo" —, só o nome lido e o id
    vazio: nenhum cadastro é inventado aqui.
    """
    nome = nomes.get(cartorio_id) if cartorio_id is not None else None
    if nome is not None:
        return str(cartorio_id), nome
    return '', (nome_da_linha or '').strip()


def _texto_da_origem(origem, numero):
    """``'M123'``/``'T45'``: prefixo do tipo documental + número normalizado.

    A mesma montagem da gravação (``revisao_ato.salvar_ato``). Número
    vazio ou incompatível com o tipo (``'T45'`` numa matrícula) não vira
    texto: o campo fica vazio e quem decide é o revisor.
    """
    if not numero:
        return ''
    tipo_documento = importacao._tipo_documento_da_origem(origem, numero)
    try:
        normalizado = normalizar_numero_documento(numero, tipo_documento)
    except (TypeError, ValueError):
        return ''
    return importacao.PREFIXO_TIPO_DOCUMENTO[tipo_documento] + normalizado


def _origens_separadas(ato, linhas, nomes_cartorios, evidencias):
    """``origens_separadas`` no formato de ``_origens_separadas_do_post``.

    O A3 tem UMA origem por ato; sem nada a preencher a lista é vazia, como
    no re-render do POST. O fim de cadeia fica desligado (decisão humana).
    """
    origem = ato.origem
    if not origem:
        return []
    numero = (origem.get('numero') or '').strip()
    texto = _texto_da_origem(origem, numero)
    id_cartorio, nome_cartorio = _cartorio(
        origem.get('cartorio_id'), origem.get('cartorio_nome'),
        nomes_cartorios,
    )
    livro = (origem.get('livro') or '').strip()
    folha = (origem.get('folha') or '').strip()
    if not any((texto, id_cartorio, nome_cartorio, livro, folha)):
        return []

    for sufixo, preenchido in (
        ('tipo_documento', texto), ('numero', texto),
        ('cartorio', nome_cartorio), ('livro', livro), ('folha', folha),
    ):
        if not preenchido:
            continue
        chave = f'{ato.chave}/origem/{sufixo}'
        evidencia = _evidencia(linhas, chave)
        if evidencia is not None:
            evidencias[f'{input_do_campo(chave)}[0]'] = evidencia

    achado = TEXTO_DA_ORIGEM.match(texto)
    return [{
        'texto': texto,
        'index': 0,
        'tipo_origem': achado.group(1) if achado else '',
        'numero_origem': achado.group(2) if achado else '',
        'cartorio_nome': nome_cartorio,
        'cartorio_id': id_cartorio,
        'livro': livro,
        'folha': folha,
        'fim_cadeia': False,
        'tipo_fim_cadeia': '',
        'classificacao_fim_cadeia': '',
        'especificacao_fim_cadeia': '',
        'sigla_patrimonio_publico': '',
        'info_adicional_fim_cadeia': '',
        'is_destacamento_publico': False,
    }]


def _lidos_sem_campo(extracao, indice, ato):
    """Avisos do que foi lido e não tem lugar no lançamento (só informativos).

    Data da origem, CPF/RG das partes, valor da transação e detalhes: nada
    disso entra em ``form_data``. O aviso leva o rótulo de negócio e nunca a
    chave da linha; CPF/RG sequer têm o valor repetido aqui.
    """
    rotulos = []
    if ato.origem and ato.origem.get('data') is not None:
        rotulos.append('Data da origem')
    if any(parte.cpf or parte.rg for parte in ato.partes):
        rotulos.append('CPF/RG das partes')

    payload = extracao.payload_servico or extracao.payload or {}
    atos_payload = payload.get('acts') or []
    ato_payload = atos_payload[indice] if indice < len(atos_payload) else {}
    for nome, rotulo in _ROTULO_DA_FOLHA_IGNORADA.items():
        folha = ato_payload.get(nome) if isinstance(ato_payload, dict) else None
        if revisao._eh_folha(folha) and any(
            isinstance(valor, str) and valor.strip()
            for valor in (folha.get('normalized'), folha.get('raw'))
        ):
            rotulos.append(rotulo)

    return [
        {
            'motivo': MOTIVO_LIDO_SEM_CAMPO,
            'rotulo': rotulo,
            'texto': TEXTO_LIDO_SEM_CAMPO,
            'bloqueante': False,
        }
        for rotulo in rotulos
    ]
