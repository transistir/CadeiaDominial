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
  ou por nome canônico + RG; sem CPF nem RG, cada ato grava o seu). A
  criação por CPF é serializada como a do cartório, com as travas tomadas
  de uma vez e em ordem global (rodada 6); o ``IntegrityError`` e a
  unicidade que vencer o ``full_clean`` continuam relendo a vencedora
  (defesa para o cadastro manual, que não passa pelas travas).
- **cartório** (E): ``criar novo`` busca ``nome__iexact`` e cria apenas
  quando não acha (mesma regra do fluxo manual,
  ``lancamento_campos_service``); a criação é serializada pelo nome, com
  as travas tomadas de uma vez e em ordem global (rodadas 4 e 5).
- **origem**: o texto do lançamento é o prefixo canônico (M/T) + número
  normalizado; a ``LancamentoOrigem`` e o documento de origem vêm do
  ``LancamentoOrigemService`` com o mapeamento do "POST corrente" definido
  na instância — nunca do sinal ``post_save`` (que engole exceções).
"""
#
# Pacote desde a Etapa 2 do imposto de 400 linhas: o antigo
# ``ia_ocr/importacao.py`` virou módulos por responsabilidade e este
# ``__init__`` reexporta tudo que o módulo único tinha no nível de topo — os
# consumidores seguem fazendo ``from ia_ocr import importacao`` e
# ``from ia_ocr.importacao import X`` sem mudança nenhuma.
#
# Os call sites dos nomes que os testes fazem ``patch.object`` no pacote
# (``_atos_marcados``, ``_vincular``, ``_trava_nome_cartorio``, ``_trava_cpf``)
# resolvem o nome AQUI (``from .. import importacao`` no submódulo), então o
# patch continua valendo depois do split.

from .ato import _importar_ato
from .ato_documento import (
    PREFIXO_TIPO_DOCUMENTO,
    _NUMERO_SIMPLES,
    _existente,
    _lancamento_duplicado,
    _numero_de_ato_do_campo,
    _numero_do_campo,
    _resolver_tipo_e_numero,
    _tipo_documento_da_origem,
    _url_lancamento,
)
from .avisos import (
    AVISO_HOMONIMO_OUTRO_TIPO,
    CHAVE_PAYLOAD_IMPORTACAO,
    VERSAO_AVISOS_GRAVADOS,
    _NOME_DO_TIPO_DA_ORIGEM,
    _aviso_homonimo,
    _avisos_gravados_da_extracao,
    _gravar_avisos_da_importacao,
    _registro_homonimo,
    _texto_do_aviso_gravado,
    _texto_ou_none,
)
from .cartorios import (
    _avisos_livro_folha_da_origem,
    _resolver_cartorio,
    _trava_nome_cartorio,
    _travar_cartorios_a_criar,
)
from .erros import ImportacaoInvalida, _AtoInvalido
from .orquestracao import (
    MOTIVO_TRANSICAO,
    _atos_marcados,
    _marcar_importadas,
    _vincular,
    importar,
    resumo,
)
from .pessoas import (
    _rg_normalizado,
    _resolver_pessoa,
    _vencedora_da_unicidade_cpf,
)
from .resposta import (
    _Erros,
    _PADRAO_POR_CAMPO,
    _chave_de_erro,
    _indice_do_ato,
    _linha_resposta,
    _linhas_por_chave,
    _resultado_gravado,
    _rotulo,
    _rotulo_efetivo,
    pendencias_para_resposta,
)
from .travas import (
    _chave_cpf_da_trava,
    _chave_da_trava,
    _id_da_trava,
    _nome_da_trava,
    _trava_cpf,
    _travar_cpfs_a_criar,
)

__all__ = [
    'AVISO_HOMONIMO_OUTRO_TIPO',
    'CHAVE_PAYLOAD_IMPORTACAO',
    'ImportacaoInvalida',
    'MOTIVO_TRANSICAO',
    'PREFIXO_TIPO_DOCUMENTO',
    'VERSAO_AVISOS_GRAVADOS',
    '_AtoInvalido',
    '_Erros',
    '_NOME_DO_TIPO_DA_ORIGEM',
    '_NUMERO_SIMPLES',
    '_PADRAO_POR_CAMPO',
    '_atos_marcados',
    '_avisos_gravados_da_extracao',
    '_avisos_livro_folha_da_origem',
    '_aviso_homonimo',
    '_chave_cpf_da_trava',
    '_chave_da_trava',
    '_chave_de_erro',
    '_existente',
    '_gravar_avisos_da_importacao',
    '_id_da_trava',
    '_importar_ato',
    '_indice_do_ato',
    '_lancamento_duplicado',
    '_linha_resposta',
    '_linhas_por_chave',
    '_marcar_importadas',
    '_nome_da_trava',
    '_numero_de_ato_do_campo',
    '_numero_do_campo',
    '_registro_homonimo',
    '_resolver_cartorio',
    '_resolver_pessoa',
    '_resolver_tipo_e_numero',
    '_resultado_gravado',
    '_rg_normalizado',
    '_rotulo',
    '_rotulo_efetivo',
    '_texto_do_aviso_gravado',
    '_texto_ou_none',
    '_tipo_documento_da_origem',
    '_trava_cpf',
    '_trava_nome_cartorio',
    '_travar_cartorios_a_criar',
    '_travar_cpfs_a_criar',
    '_url_lancamento',
    '_vencedora_da_unicidade_cpf',
    '_vincular',
    'importar',
    'pendencias_para_resposta',
    'resumo',
]
