"""Telas da app ia_ocr: texto OCR e revisão da extração estruturada.

Mesma política de acesso do upload digital: ``login_required`` + hierarquia
TI→Imóvel→Documento (``_get_contexto_documento``); fora do escopo → 404, o
padrão do projeto. As mutações são POST com redirect de volta à tela (PRG) e
delegam a ``ia_ocr.services``: a view nunca grava página nem transiciona o job
diretamente. Nenhum log daqui carrega texto de documento ou nome de arquivo
(PII).

Pacote desde a etapa 3 do limite de 400 linhas por arquivo —
``ia_ocr/views.py`` era o monólito de 1.429 linhas. Módulos:

- ``jobs`` — tela do texto OCR e contexto da hierarquia;
- ``paginas`` — ações de página (confirmar/editar/bulk/reprocessar/extração);
- ``campos`` — entrada legada da tela de cards, agora redirect à revisão;
- ``decisoes`` — save do bloco de decisões e contrato JSON do POST;
- ``importar`` — importação (I-6) e finalização da revisão (#262);
- ``revisar`` — formulário do ato (I-14/#341);
- ``revisar_extras`` — complementos da revisão (duplicata, sem atos);
- ``resposta`` — avisos, URLs, paginação e o decorator JSON;
- ``middleware`` — CSRF em JSON.

Regra sobre patches de teste — SÓ os nomes que os testes resolvem via
``ia_ocr.views.<nome>`` passam pelo pacote; todo o resto é chamada direta
com import do módulo dono (``from .jobs import _contexto_job`` etc.), a
mesma forma do monólito:

- ``render`` (``mock.patch('ia_ocr.views.render')``),
  ``_disponibilidade_extracao``
  (``mock.patch('ia_ocr.views._disponibilidade_extracao')``) e
  ``_extracao_trocada_no_post``
  (``mock.patch('ia_ocr.views._extracao_trocada_no_post')``, definido em
  ``revisar``) são chamados VIA O PACOTE (``views.<nome>(...)``) pelos
  módulos acima, a cada chamada: o patch só age se o call site resolver o
  nome no objeto do pacote.
- ``views.services`` e ``views.revisao`` continuam sendo os módulos irmãos
  ``ia_ocr.services``/``ia_ocr.revisao`` (reexportados logo abaixo): os
  testes fazem ``mock.patch('ia_ocr.views.services.<op>')`` e
  ``mock.patch('ia_ocr.views.revisao.pendencias')``, que resolvem o
  atributo NO MÓDULO — e os call sites dos submódulos chamam
  ``services.<op>(...)``/``revisao.<op>(...)`` no MESMO objeto, importado
  de ``..``. Por isso nenhum submódulo deste pacote se chama
  ``services`` ou ``revisao`` — as telas de revisão do I-14 estão em
  ``revisar.py`` e as de importação em ``importar.py``.
- ``assertLogs('ia_ocr.views', ...)`` pega os logs dos módulos acima por
  PROPAGAÇÃO: cada um loga com ``getLogger(__name__)``
  (``ia_ocr.views.<módulo>``, filho de ``ia_ocr.views``).

Uso em tempo de IMPORTAÇÃO (decorators, constantes) também vem por import
direto do módulo dono — patch em decorator já aplicado não teria efeito
nem no monólito. Um ``from .x import nome`` em UMA chamada de runtime que
o teste patcha esconderia o nome do patch; fora desses nomes, o import
direto é equivalente ao monólito (um namespace único, resolução estática).
"""

from django.shortcuts import render  # noqa: F401 — alvo de patch: ia_ocr.views.render

# Módulos irmãos reexportados: alvos de patch via ia_ocr.views.<módulo>.
from .. import revisao, services  # noqa: F401

from .middleware import _CsrfJsonMiddleware  # noqa: F401
from .resposta import (  # noqa: F401
    _aviso_nao_consta,
    _avisos_da_resposta,
    _avisos_descritos,
    _destino,
    _disponibilidade_extracao,
    _numero_pagina,
    _pagina_pedida,
    _respostas_json_ocr,
    _url_tela,
    _versao_do_formulario,
)
from .jobs import _contexto_job, _kwargs_job, _sem_atos_elegivel, texto_job_ocr  # noqa: F401
from .paginas import (  # noqa: F401
    MENSAGEM_PAGINA_DESATUALIZADA,
    confirmar_pagina_ocr,
    confirmar_paginas_ocr,
    editar_pagina_ocr,
    extrair_campos_ocr,
    reprocessar_job_ocr,
)
from ..mascaras import (  # noqa: F401 — alvos de patch/uso: ia_ocr.views._mascarar_*
    _mascarar_cpf,
    _mascarar_evidencia,
    _mascarar_rg,
)
from .campos import campos_job_ocr  # noqa: F401
from .decisoes import (  # noqa: F401
    _chave_valor_invalido,
    _decisoes_bloco,
    _recusar_decisao,
    salvar_bloco_ocr,
)
from .importar import finalizar_revisao_ocr, importar_job_ocr  # noqa: F401
from .revisar_extras import (  # noqa: F401
    revisar_ato_duplicata_ocr,
    revisar_sem_atos_ocr,
)
from .revisar import (  # noqa: F401
    MENSAGEM_ATO_JA_SALVO,
    MENSAGEM_DUPLICATA_NA_REVISAO,
    MENSAGEM_ERRO_INTERNO_DO_ATO,
    MENSAGEM_EXTRACAO_TROCOU,
    MENSAGEM_REVISAO_CONCLUIDA,
    _depois_de_salvar,
    _destino_da_navegacao,
    _extracao_trocada_no_post,
    _fora_da_revisao,
    _mostrar_ato,
    _navegar_entre_atos,
    _salvar_ato,
    _url_ato,
    _url_documento,
    _url_entrada,
    revisar_ato_ocr,
    revisar_job_ocr,
)
