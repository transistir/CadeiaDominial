"""Desnormalização do payload A3 em linhas de revisão (I-5, §18).

``desnormalizar`` devolve ``CampoSugerido`` NÃO salvos — uma linha por
folha editável (objeto com ``normalized``), mais as linhas estruturais de
ato (``/acts/{i}``, normalized = rótulo) e de parte
(``/acts/{i}/partes/{j}``, normalized = papel), mais placeholders dos
destinos obrigatórios ausentes (inclusive os exigidos pelo tipo efetivo).
Com a extração já salva, resolve as configurações de ``LancamentoTipo``
numa única query; nenhuma gravação: quem persiste é o chamador.

Toda pendência vira motivo estável em ``motivos_revisao`` com
``requer_revisao=True`` — nunca silêncio:

- ``normalizacao_invalida`` — ``normalized`` de data/decimal/área fora do
  canônico (vira ``normalized=None``; o raw é preservado);
- ``unidade_area`` — área de ato em unidade ≠ ha (conversão é decisão
  humana, nunca silenciosa);
- ``baixa_confianca`` — confiança < 0.70 (força revisão mesmo com o
  payload dizendo ``requer_revisao=False``);
- ``closure`` — qualquer linha ``/closure/*`` (classificação de fim de
  cadeia é SEMPRE decisão humana);
- ``evidencia_invalida`` — página da evidência fora das páginas do job;
- ``trecho_ausente`` — trecho não é substring do texto vigente da página
  (o ``texto_corrigido`` devolvido pelo serviço — decisão #290 — ou, na
  falta dele, o ``texto_ocr`` puro como fallback).

O módulo também hospeda o matching determinístico do I-5 (executado por
esta camada Python, nunca pelo modelo): ``IndicePessoas`` e
``IndiceCartorios`` (UMA query cada, matching em memória) e
``enriquecer_payload``, que escreve ``match_sugerido``/``match_pessoa_id``
(do A3) e ``match_pessoa_candidatos`` (extensão local) numa CÓPIA do
payload A3 — sem mutar o original.
"""

from .estruturas import (AtoRevisado, CAMPOS_DA_ORIGEM,
    CAMPOS_DA_TRANSMISSAO, DadosRevisados, DocumentoRevisado,
    EscolhaIncompativel, EscolhaInvalida, LIMIAR_CONFIANCA,
    LINHAS_IGNORADAS, MATCH_PESSOA_CANDIDATOS, MOTIVO_BAIXA_CONFIANCA,
    MOTIVO_CLOSURE, MOTIVO_CRIAR_NOVO_SEM_NOME, MOTIVO_EVIDENCIA_INVALIDA,
    MOTIVO_NORMALIZACAO_INVALIDA, MOTIVO_TRECHO_AUSENTE,
    MOTIVO_UNIDADE_AREA, ParteRevisada, RevisaoInvalidada, _AREA_DE_ATO,
    _CHAVE_OBRIGATORIA_ATO, _LINHA_IGNORADA, _NAO_DIGITO, _OBRIGATORIOS_ATO,
    _OBRIGATORIOS_DOCUMENTO, _TIPOS_NORMALIZAVEIS, _eh_folha,
    _normalizar_nome, _so_digitos, linha_ignorada)

from .linhas import (_campo_ausente, _cartorio_id_da_linha,
    _contexto_revisao, _destino_da_linha, _valor_efetivo, _valor_explicito,
    _valor_para_limite, aplicar_linha, identidade_parte, versao_linha)

from .obrigatorio import (CAMPOS_DO_FORMULARIO_ATO,
    CAMPOS_DO_FORMULARIO_DOCUMENTO, ROTULOS_CAMPO, _ACAO_OBRIGATORIO,
    _ACAO_PENDENCIA, _CHAVE_ATO_LOCAL, _CHAVE_PARTE_LOCAL,
    _ESTRUTURAL_NUMERADO, _LOCAL_ATO, _LOCAL_DOCUMENTO, _ORDEM_ATO,
    _ORDEM_DOCUMENTO, _ORDEM_ORIGEM, _ORDEM_PARTE, _PARTE_NUMERADA,
    _ROTULO_PENDENCIA, _TEXTO_LONGO, _TEXTO_NAO_RECONHECIDO,
    _local_da_chave, _local_de_ato, _ordem_no_formulario_do_ato,
    _rotulo_fallback, campo_obrigatorio, descrever_pendencia,
    rotulo_de_campo, rotulo_efetivo)

from .tipos import (_TIPO_DA_ORIGEM, _caminhos_do_tipo,
    _resolver_tipo_do_ato, _rotulo_do_payload, _tem_folha,
    _tipo_da_origem_sem_leitura, _tipo_do_rotulo_do_ato, _tipos_efetivos,
    resolucoes_de_tipo, tipo_da_origem, tipos_efetivos)

from .pendencias import (_pendencias_de_linhas, pendencias,
    pendencias_sem_atos)

from .avisos import (MOTIVOS_NAO_CONSTA, MOTIVO_FOLHA_ORIGEM_NAO_CONSTA,
    MOTIVO_LIVRO_ORIGEM_NAO_CONSTA, MOTIVO_ORIGEM_HOMONIMA,
    TEXTO_NAO_CONSTA, _ROTULO_AVISO, _ROTULO_AVISO_PADRAO,
    _origem_nao_consta, _origens_homonimas, avisos, descrever_aviso)

from .dados import (_montar_dados, dados_revisados)

from .tela import (secoes_da_tela)

from .campos_payload import (_bbox_valido, _candidatos_do_match,
    _checar_confianca, _de_ato, _de_campo, _de_parte, _id_valido,
    _placeholder, _resolver_evidencia, _valor_do_payload)

from .desnormalizacao import (_ato, _ato_tem_origem,
    _configuracoes_do_payload, _folhas, _origem_do_payload, _parte,
    _placeholders_documento, desnormalizar,
    garantir_placeholders_obrigatorios)

from .indices import (IndiceCartorios, IndicePessoas, _cpf_utilizavel)

from .comarca import (Comarca, LIMITE_CANDIDATOS_FALLBACK,
    TAMANHO_CABECALHO, _COMARCA, _SIGLAS, _UFS,
    candidatos_cartorio_fallback, comarca_do_documento, fallback_cartorio)

from .enriquecimento import (_CARTORIOS_DO_ATO, _CARTORIOS_DO_DOCUMENTO,
    _normalized, _sugerir_cartorio, _sugerir_pessoa, enriquecer_payload)

__all__ = [
    'AtoRevisado', 'CAMPOS_DA_ORIGEM', 'CAMPOS_DA_TRANSMISSAO',
    'CAMPOS_DO_FORMULARIO_ATO', 'CAMPOS_DO_FORMULARIO_DOCUMENTO', 'Comarca',
    'DadosRevisados', 'DocumentoRevisado', 'EscolhaIncompativel',
    'EscolhaInvalida', 'IndiceCartorios', 'IndicePessoas',
    'LIMIAR_CONFIANCA', 'LIMITE_CANDIDATOS_FALLBACK', 'LINHAS_IGNORADAS',
    'MATCH_PESSOA_CANDIDATOS', 'MOTIVOS_NAO_CONSTA',
    'MOTIVO_BAIXA_CONFIANCA', 'MOTIVO_CLOSURE',
    'MOTIVO_CRIAR_NOVO_SEM_NOME', 'MOTIVO_EVIDENCIA_INVALIDA',
    'MOTIVO_FOLHA_ORIGEM_NAO_CONSTA', 'MOTIVO_LIVRO_ORIGEM_NAO_CONSTA',
    'MOTIVO_NORMALIZACAO_INVALIDA', 'MOTIVO_ORIGEM_HOMONIMA',
    'MOTIVO_TRECHO_AUSENTE', 'MOTIVO_UNIDADE_AREA', 'ParteRevisada',
    'ROTULOS_CAMPO', 'RevisaoInvalidada', 'TAMANHO_CABECALHO',
    'TEXTO_NAO_CONSTA', '_ACAO_OBRIGATORIO', '_ACAO_PENDENCIA',
    '_AREA_DE_ATO', '_CARTORIOS_DO_ATO', '_CARTORIOS_DO_DOCUMENTO',
    '_CHAVE_ATO_LOCAL', '_CHAVE_OBRIGATORIA_ATO', '_CHAVE_PARTE_LOCAL',
    '_COMARCA', '_ESTRUTURAL_NUMERADO', '_LINHA_IGNORADA', '_LOCAL_ATO',
    '_LOCAL_DOCUMENTO', '_NAO_DIGITO', '_OBRIGATORIOS_ATO',
    '_OBRIGATORIOS_DOCUMENTO', '_ORDEM_ATO', '_ORDEM_DOCUMENTO',
    '_ORDEM_ORIGEM', '_ORDEM_PARTE', '_PARTE_NUMERADA', '_ROTULO_AVISO',
    '_ROTULO_AVISO_PADRAO', '_ROTULO_PENDENCIA', '_SIGLAS', '_TEXTO_LONGO',
    '_TEXTO_NAO_RECONHECIDO', '_TIPOS_NORMALIZAVEIS', '_TIPO_DA_ORIGEM',
    '_UFS', '_ato', '_ato_tem_origem', '_bbox_valido', '_caminhos_do_tipo',
    '_campo_ausente', '_candidatos_do_match', '_cartorio_id_da_linha',
    '_checar_confianca', '_configuracoes_do_payload', '_contexto_revisao',
    '_cpf_utilizavel', '_de_ato', '_de_campo', '_de_parte',
    '_destino_da_linha', '_eh_folha', '_folhas', '_id_valido',
    '_local_da_chave', '_local_de_ato', '_montar_dados', '_normalizar_nome',
    '_normalized', '_ordem_no_formulario_do_ato', '_origem_do_payload',
    '_origem_nao_consta', '_origens_homonimas', '_parte',
    '_pendencias_de_linhas', '_placeholder', '_placeholders_documento',
    '_resolver_evidencia', '_resolver_tipo_do_ato', '_rotulo_do_payload',
    '_rotulo_fallback', '_so_digitos', '_sugerir_cartorio',
    '_sugerir_pessoa', '_tem_folha', '_tipo_da_origem_sem_leitura',
    '_tipo_do_rotulo_do_ato', '_tipos_efetivos', '_valor_do_payload',
    '_valor_efetivo', '_valor_explicito', '_valor_para_limite',
    'aplicar_linha', 'avisos', 'campo_obrigatorio',
    'candidatos_cartorio_fallback', 'comarca_do_documento',
    'dados_revisados', 'descrever_aviso', 'descrever_pendencia',
    'desnormalizar', 'enriquecer_payload', 'fallback_cartorio',
    'garantir_placeholders_obrigatorios', 'identidade_parte',
    'linha_ignorada', 'pendencias', 'pendencias_sem_atos',
    'resolucoes_de_tipo', 'rotulo_de_campo', 'rotulo_efetivo',
    'secoes_da_tela', 'tipo_da_origem', 'tipos_efetivos', 'versao_linha',
]
