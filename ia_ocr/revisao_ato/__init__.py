"""Revisão por ato no formulário de lançamento (I-14 / #341, fase 2).

A tela de revisão é o PRÓPRIO formulário de lançamento, um ato por vez. Este
módulo reúne o que a view precisa além do pré-preenchimento (``formulario``):

- ``atos_da_revisao``: as abas da sidebar. O estado de cada ato sai do banco
  (``ImportacaoIA`` do lançamento daquele ato), nunca de uma coluna nova;
- rascunho por ato na SESSÃO (``guardar_rascunho`` e companhia): navegar entre
  atos não escreve nada no banco além de ``django_session``;
- ``estado_do_formulario``: reconstrói ``form_data``/origens/partes a partir de
  um POST (rascunho ou re-render de erro) reaproveitando os helpers do
  formulário manual — o mesmo caminho que o ``novo_lancamento`` usa;
- ``salvar_ato``: o ÚNICO caminho de gravação. Chama
  ``LancamentoService.criar_lancamento_completo`` com o mesmo ``request`` do
  formulário manual (nenhuma regra de duplicidade ou de validação é
  reimplementada aqui) e, na mesma transação, registra os vínculos de
  auditoria no formato da importação.

Pacote desde a Etapa 8 do imposto de 400 linhas: o antigo
``ia_ocr/revisao_ato.py`` virou módulos por responsabilidade e este
``__init__`` reexporta tudo que o módulo único tinha no nível de topo.

- Os call sites dos nomes que os testes patcham no pacote
  (``importacao._vincular``, ``LancamentoService.criar_lancamento_completo``)
  resolvem por ATRIBUTO, a cada chamada, os MESMOS objetos compartilhados de
  antes (o módulo ``ia_ocr.importacao`` e a classe do service) — então o
  patch continua valendo depois do split. ``LancamentoService`` fica
  importado AQUI para o alvo ``ia_ocr.revisao_ato.LancamentoService…``
  resolver pelo pacote, como resolvia pelo módulo.
- ``guardar_rascunho`` é patchado com ``patch.object`` NO PACOTE
  (``ia_ocr.revisao_ato``, o que ``views/revisar.py`` lê) — o reexport
  abaixo mantém o nome no nível de topo.
"""

from .. import estados, importacao, revisao, services
from dominial.services.lancamento_service import LancamentoService

from .consulta import (
    ESTADO_IMPORTADO,
    ESTADO_PENDENTE,
    Resultado,
    _PREFIXO_DA_ABA,
    _rotulo_da_aba,
    atos_da_revisao,
    proximo_pendente,
)
from .rascunho import (
    CHAVE_SESSAO,
    FORA_DO_RASCUNHO,
    LIMITE_EXTRACOES_NO_RASCUNHO,
    guardar_rascunho,
    limpar_rascunho,
    rascunho_do_ato,
)
from .formulario import _pessoas_do_post, estado_do_formulario
from .salvar import (
    MOTIVO_TRANSICAO,
    _cartorio_da_transmissao_nao_cadastrado,
    _registros_do_ato,
    _restantes,
    salvar_ato,
)

__all__ = [
    'CHAVE_SESSAO',
    'ESTADO_IMPORTADO',
    'ESTADO_PENDENTE',
    'FORA_DO_RASCUNHO',
    'LIMITE_EXTRACOES_NO_RASCUNHO',
    'LancamentoService',
    'MOTIVO_TRANSICAO',
    'Resultado',
    '_PREFIXO_DA_ABA',
    '_cartorio_da_transmissao_nao_cadastrado',
    '_pessoas_do_post',
    '_registros_do_ato',
    '_restantes',
    '_rotulo_da_aba',
    'atos_da_revisao',
    'estado_do_formulario',
    'estados',
    'guardar_rascunho',
    'importacao',
    'limpar_rascunho',
    'proximo_pendente',
    'rascunho_do_ato',
    'revisao',
    'salvar_ato',
    'services',
]
