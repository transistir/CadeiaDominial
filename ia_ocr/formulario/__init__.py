"""Pré-preenchimento do formulário de lançamento pela revisão (I-14 / #341, fase 1).

A revisão da extração vira o próprio formulário de lançamento — um ato por
aba, sem gravar nada até o usuário salvar AQUELE ato. Este módulo é o que o
formulário consome: ``prefill_do_ato`` lê o estado ATUAL das linhas do ato
``N`` (``revisao._montar_dados``, sem exigir revisão concluída) e devolve, no
formato que os templates do formulário manual já esperam, o que preencher:

- ``form_data``: o mesmo dicionário que ``_form_data_do_post`` monta — chaves
  com o NOME DO INPUT, valores sempre em ``str`` (o template compara
  ``form_data.tipo_lancamento == tipo.id|stringformat:"s"``). Só entra chave
  com valor lido: ausência é "nada lido", nunca ``None`` (que o template
  imprimiria como ``None``);
- ``origens_separadas``: o formato de ``_origens_separadas_do_post``;
- ``transmitentes`` / ``adquirentes``: a lista de ``{'id', 'nome'}`` do
  ``_pessoa_form.html``;
- ``evidencias``: ``{input: {pagina, trecho, confianca_baixa}}`` — a chave é o
  nome do input; nos inputs repetidos (``transmitente_nome[]``,
  ``cartorio_origem_nome[]``...) é o nome SEM os colchetes mais a posição na
  lista, ``transmitente_nome[0]``. O trecho sai mascarado (CPF/RG);
- ``pendencias``: avisos do que foi lido e não entrou no formulário: o que
  não tem campo no lançamento (informativo) e a área lida em unidade que não
  é hectare (decisão do revisor: o input é em ha e nada é convertido em
  silêncio). Nunca citam a chave ``/acts/...``.

Nada daqui grava ou cria cadastro: cartório que a revisão marcou "criar
novo" entra só com o nome e o id vazio — o bloqueio é da fase 2.

O número composto (``numero_lancamento``, "R1 M237") sai do MESMO gerador do
POST manual (``LancamentoFormService._gerar_numero_lancamento``, com a sigla
da matrícula): o JS do formulário manual só preenche esse campo com a sigla
pura ("M237") — e, em modo de edição, apaga o número simples a partir dele —,
então o HTML já tem que chegar com o composto certo (#341, M1).
"""

from .erros import AtoInexistente
from .texto import _como_texto, _evidencia, _nomes
from .numeros import _numero_composto, _numero_legivel, _numero_simples
from .areas import (
    MOTIVO_AREA_EM_OUTRA_UNIDADE,
    ROTULO_DA_AREA,
    TEXTO_AREA_EM_OUTRA_UNIDADE,
    UNIDADES_DE_AREA,
    _area_em_outra_unidade,
    _unidade_da_area_no_payload,
    area_exige_decisao,
)
# ``prefill`` ANTES de ``origens``/``partes``: o import deles fica no fim de
# ``prefill.py`` (ciclo via ``input_do_campo``) e só resolve com ``prefill``
# já inicializado.
from .prefill import (
    CHAVE_PARA_INPUT,
    INPUT_FORMA_DA_AVERBACAO,
    input_do_campo,
    prefill_do_ato,
)
from .origens import (
    MOTIVO_LIDO_SEM_CAMPO,
    TEXTO_DA_ORIGEM,
    TEXTO_LIDO_SEM_CAMPO,
    _ROTULO_DA_FOLHA_IGNORADA,
    _cartorio,
    _lidos_sem_campo,
    _origens_separadas,
    _texto_da_origem,
)
from .partes import _partes

__all__ = [
    'AtoInexistente', 'CHAVE_PARA_INPUT', 'INPUT_FORMA_DA_AVERBACAO',
    'MOTIVO_AREA_EM_OUTRA_UNIDADE', 'MOTIVO_LIDO_SEM_CAMPO',
    'ROTULO_DA_AREA', 'TEXTO_AREA_EM_OUTRA_UNIDADE', 'TEXTO_DA_ORIGEM',
    'TEXTO_LIDO_SEM_CAMPO', 'UNIDADES_DE_AREA', '_ROTULO_DA_FOLHA_IGNORADA',
    '_area_em_outra_unidade', '_cartorio', '_como_texto', '_evidencia',
    '_lidos_sem_campo', '_nomes', '_numero_composto', '_numero_legivel',
    '_numero_simples', '_origens_separadas', '_partes', '_texto_da_origem',
    '_unidade_da_area_no_payload', 'area_exige_decisao', 'input_do_campo',
    'prefill_do_ato',
]
