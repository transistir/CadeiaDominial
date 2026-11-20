"""Serviços da fila de OCR e da extração estruturada.

Nenhum log aqui carrega texto de documento ou dados do PDF (PII): apenas
job_id, status, tentativa e códigos de erro estáveis. O que vem de fora
(backend) é sanitizado antes de virar log ou coluna.

Pacote desde a Etapa 4 do imposto de 400 linhas: o antigo
``ia_ocr/services.py`` virou módulos por responsabilidade e este
``__init__`` reexporta tudo que o módulo único tinha no nível de topo — os
consumidores seguem fazendo ``from ia_ocr import services`` e
``from ia_ocr.services import X`` sem mudança nenhuma.

- Os call sites dos nomes que os testes patcham no pacote
  (``get_extracao_backend``, ``IndicePessoas``, ``versao_linha``,
  ``_normalizar_quebras_de_linha``) resolvem o nome AQUI
  (``from .. import services`` no submódulo), a cada chamada — então o
  patch continua valendo depois do split. ``timezone`` segue sendo o módulo
  ``django.utils.timezone``: ``patch('ia_ocr.services.timezone.now')`` muta
  o módulo compartilhado.
- ``assertLogs('ia_ocr.services', ...)`` pega os logs dos módulos por
  PROPAGAÇÃO: cada um loga com ``getLogger(__name__)``
  (``ia_ocr.services.<módulo>``, filho de ``ia_ocr.services``).
"""

from django.utils import timezone  # alvo de patch: ia_ocr.services.timezone.now

from ..extracao_backends import get_extracao_backend  # alvo de patch
from ..revisao import IndicePessoas, versao_linha  # alvos de patch

from .erros import (
    CHAVES_TIMING_PERMITIDAS,
    CODIGOS_ERRO_PERMITIDOS,
    LIMITE_TIMINGS_CHAVES,
    MENSAGENS_ERRO_SEGURAS,
    ConflitoVersao,
    EdicaoPendente,
    ExtracaoConcorrente,
    ExtracaoIncompativel,
    ExtracaoIndisponivel,
    ExtracaoPayloadInvalido,
    ExtracaoRecusada,
    JobEmExecucao,
    JobIdConflitante,
    PaginaDesatualizada,
    RevisaoIncompleta,
    TextoNaoEditavel,
    _CODIGO_BACKEND_ESTAVEL,
    _codigo_backend_para_log,
    _mensagem_erro_segura,
    _sanitizar_erro_codigo,
    _sanitizar_timings,
)
from .blocos import (
    _campos_ordenados,
    _com_bloqueios_de_campo,
    _preparar_fallback_cartorio,
    _travar_extracao_revisao,
    _validar_limites_bloco,
    salvar_bloco,
    versao_bloco,
)
from .finalizacao import finalizar_revisao, pode_finalizar_sem_atos
from .extracao import (
    _blocos_da_pagina,
    _textos_corrigidos_extracao,
    _validar_solicitacao_extracao,
    registrar_pendencia_limpeza,
    solicitar_extracao,
)
from .jobs import claim_proximo_job, criar_job, reap_jobs_expirados, reprocessar
from .paginas import (
    _exigir_versao,
    _normalizar_quebras_de_linha,  # alvo de patch
    _travar_job_editavel,
    confirmar_pagina,
    confirmar_todas_paginas,
    confirmar_texto,
    editar_pagina,
)
from .conclusao import (
    _ORIGENS_VALIDAS,
    _logar_finalizacao_descartada,
    finalizar,
    marcar_falha_interna,
)

__all__ = [
    'CHAVES_TIMING_PERMITIDAS',
    'CODIGOS_ERRO_PERMITIDOS',
    'ConflitoVersao',
    'EdicaoPendente',
    'ExtracaoConcorrente',
    'ExtracaoIncompativel',
    'ExtracaoIndisponivel',
    'ExtracaoPayloadInvalido',
    'ExtracaoRecusada',
    'IndicePessoas',
    'JobEmExecucao',
    'JobIdConflitante',
    'LIMITE_TIMINGS_CHAVES',
    'MENSAGENS_ERRO_SEGURAS',
    'PaginaDesatualizada',
    'RevisaoIncompleta',
    'TextoNaoEditavel',
    '_CODIGO_BACKEND_ESTAVEL',
    '_ORIGENS_VALIDAS',
    '_blocos_da_pagina',
    '_campos_ordenados',
    '_codigo_backend_para_log',
    '_com_bloqueios_de_campo',
    '_exigir_versao',
    '_logar_finalizacao_descartada',
    '_mensagem_erro_segura',
    '_normalizar_quebras_de_linha',
    '_preparar_fallback_cartorio',
    '_sanitizar_erro_codigo',
    '_sanitizar_timings',
    '_textos_corrigidos_extracao',
    '_travar_extracao_revisao',
    '_travar_job_editavel',
    '_validar_limites_bloco',
    '_validar_solicitacao_extracao',
    'claim_proximo_job',
    'confirmar_pagina',
    'confirmar_todas_paginas',
    'confirmar_texto',
    'criar_job',
    'editar_pagina',
    'finalizar',
    'finalizar_revisao',
    'get_extracao_backend',
    'marcar_falha_interna',
    'pode_finalizar_sem_atos',
    'reap_jobs_expirados',
    'registrar_pendencia_limpeza',
    'reprocessar',
    'salvar_bloco',
    'solicitar_extracao',
    'timezone',
    'versao_bloco',
    'versao_linha',
]
