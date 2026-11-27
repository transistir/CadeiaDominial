"""Classe única de cada motivo de pendência (#332).

Módulo-folha: não importa nada de ``ia_ocr`` (evita ciclo). É a fonte única
que separa o que BLOQUEIA a gravação do ato do que é apenas INFORMATIVO.
Motivo desconhecido falha fechado: bloqueante.
"""

BLOQUEANTE = True
INFORMATIVO = False

# Bloqueantes do ato (formulário de lançamento) + bloqueantes do motor
# legado (as mesmas linhas que ``revisao.pendencias`` já devolve).
CLASSE_DO_MOTIVO = {
    # Ato
    'unidade_area': BLOQUEANTE,
    'inicio_sem_origem': BLOQUEANTE,
    'inicio_sem_data': BLOQUEANTE,
    'cartorio_transmissao_nao_cadastrado': BLOQUEANTE,
    'cartorio_origem_nao_cadastrado': BLOQUEANTE,
    # Motor legado
    'nenhum_ato': BLOQUEANTE,
    'revisao_pendente': BLOQUEANTE,
    'escolha_pendente': BLOQUEANTE,
    'decisao_perdida': BLOQUEANTE,
    'criar_novo_sem_nome': BLOQUEANTE,
    'match_invalidado': BLOQUEANTE,
    'obrigatorio_ausente': BLOQUEANTE,
    'valor_incompativel_destino': BLOQUEANTE,
    'valor_acima_do_limite_destino': BLOQUEANTE,
    # Informativos do ato
    'lido_sem_campo': INFORMATIVO,
    'forma_ajustada_vocabulario': INFORMATIVO,
    'forma_titulo_reinterpretados': INFORMATIVO,
    'data_transacao_do_instrumento': INFORMATIVO,
    'area_descartada': INFORMATIVO,
    # Informativos de ``revisao.avisos``
    'livro_origem_nao_consta': INFORMATIVO,
    'folha_origem_nao_consta': INFORMATIVO,
    'origem_homonimo_outro_tipo': INFORMATIVO,
    'requer_forma': INFORMATIVO,
    'requer_observacao': INFORMATIVO,
    'requer_livro_origem': INFORMATIVO,
    'requer_folha_origem': INFORMATIVO,
    'requer_data_origem': INFORMATIVO,
    'requer_transmissao': INFORMATIVO,
}


def eh_bloqueante(motivo):
    """Classe do motivo; desconhecido bloqueia (falha fechada)."""
    return CLASSE_DO_MOTIVO.get(motivo, BLOQUEANTE)
