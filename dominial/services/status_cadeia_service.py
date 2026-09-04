"""Issue #174 — service de status de cadeia finalizada por imóvel da TI.

Correção do P1 do Greptile (round-2 do PR #184):

O service original agregava por `lancamento__documento__imovel`, então um
fim de cadeia em um documento compartilhado (apontado como origem por um
doc pertencente a outro imóvel da MESMA TI) era creditado ao imóvel dono
do documento, não ao imóvel cuja árvore o alcançava — e o imóvel dono
do documento desconectado herdava a classificação desse fim isolado.

Correção: derivar o status pela ÁRVORE alcançável de cada imóvel, usando o
mesmo construtor da UI (`HierarquiaArvoreService.construir_arvore_cadeia_dominial`).
Cada imóvel recebe a pior classificação entre os fins visitados na sua
própria árvore.

Custo: O(n_imóveis * nós_da_árvore). O painel `tis_detail` raramente tem
muitos imóveis, e a árvore tem tipicamente ≤10 nós. Aceitável.

Trade-off consciente: uma única query agregada é mais rápida mas produz
resultado incorreto quando há documentos compartilhados. A correção
privilegia correção sobre velocidade.
"""
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Classificações conhecidas (issue #174) — desconhecidas caem para None
_CLASSIFICACOES_VALIDAS = ('origem_lidima', 'inconclusa', 'sem_origem')

# Prioridade "pior situação" (issue #174 — decisão de escopo do cliente):
# sem_origem > inconclusa > origem_lidima. Imóvel sem fim de cadeia
# finalizada fica fora do dict (template renderiza "—" para cadeia em
# andamento).
_PRIORIDADE = {
    'sem_origem': 3,
    'inconclusa': 2,
    'origem_lidima': 1,
}


def _normalizar_classificacao(valor):
    """Normaliza classificação para uma das válidas ou None.

    Aceita valores legados e edge cases (None, string vazia, valor
    desconhecido) e devolve None — não há regra explícita do cliente
    sobre classificação inválida, então optamos pelo conservador:
    não classificar, deixando o imóvel renderizar "—" (em andamento).
    """
    if not valor:
        return None
    v = str(valor).strip().lower()
    return v if v in _CLASSIFICACOES_VALIDAS else None


def _pior_classificacao(classificacoes):
    """Devolve a classificação de maior prioridade (pior situação)."""
    rank = max(
        (_PRIORIDADE.get(c, 0) for c in classificacoes),
        default=0,
    )
    for c, r in _PRIORIDADE.items():
        if r == rank:
            return c
    return None


class StatusCadeiaService:
    """Service para status de cadeia finalizada por imóvel de uma TI."""

    @staticmethod
    def status_por_imovel(tis_id: int) -> Dict[int, Optional[str]]:
        """Devolve {imovel_id: classificacao} para imóveis com cadeia
        finalizada.

        Implementação: para cada imóvel da TI,
          1) constrói a árvore alcançável (mesma construção da UI,
             HierarquiaArvoreService.construir_arvore_cadeia_dominial);
          2) coleta o conjunto de IDs de Documento alcançados;
          3) busca todos os ``OrigemFimCadeia`` cujos ``lancamento.documento``
             esteja nesse conjunto (qualquer dono do doc);
          4) normaliza cada ``classificacao_fim_cadeia`` (None/legado/
             desconhecido -> None) e aplica a regra "pior situação".

        P1 do Greptile (PR #184 round-2): creditar a classificação
        ao imóvel dono do documento fazia com que docs compartilhados
        contaminassem imóveis que não os alcançam. Por isso derivamos
        o status pela ÁRVORE alcançável de cada imóvel.
        """
        from dominial.models import Imovel, Documento, OrigemFimCadeia
        from dominial.services.hierarquia_arvore_service import (
            HierarquiaArvoreService,
        )

        # 1) Pré-construir árvores de todos os imóveis da TI e cachear
        #    o conjunto de IDs de Documento alcançáveis por cada um.
        docs_alcancaveis_por_imovel: Dict[int, set] = {}
        for imovel in Imovel.objects.filter(terra_indigena_id_id=tis_id):
            try:
                arvore = HierarquiaArvoreService.construir_arvore_cadeia_dominial(
                    imovel, criar_documentos_automaticos=False,
                )
            except Exception as exc:  # pragma: no cover — defensivo
                logger.warning(
                    "Falha ao construir árvore do imóvel %s: %s",
                    imovel.id, exc,
                )
                continue

            ids_docs: set = set()
            for doc in (arvore.get('documentos') or []):
                # nós sintéticos de fim_cadeia não têm 'id' numérico de
                # Documento; só nos interessam os reais.
                if isinstance(doc.get('id'), int):
                    ids_docs.add(doc['id'])
            docs_alcancaveis_por_imovel[imovel.id] = ids_docs

        # 2) Coletar todos os IDs de documento alcançáveis em toda a TI
        #    (para carregar os OrigemFimCadeia em uma query só).
        todos_docs = set().union(*docs_alcancaveis_por_imovel.values())
        if not todos_docs:
            return {}

        classif_por_doc: Dict[int, list] = {d: [] for d in todos_docs}
        # P2 do Greptile (PR #184 round-3): select_related('lancamento')
        # evita N+1 — antes, cada OrigemFimCadeia disparava um SELECT extra
        # em Lancamento quando o código acessava ofc.lancamento.documento_id.
        for ofc in OrigemFimCadeia.objects.filter(
            lancamento__documento_id__in=todos_docs,
            fim_cadeia=True,
        ).select_related('lancamento').only(
            'lancamento__documento_id', 'classificacao_fim_cadeia',
        ):
            cls = _normalizar_classificacao(ofc.classificacao_fim_cadeia)
            if cls is not None:
                classif_por_doc[ofc.lancamento.documento_id].append(cls)

        # 3) Agregar por imóvel: o status de cada imóvel é a pior
        #    classificação entre os fins de cadeia alcançáveis por ele.
        status_map: Dict[int, Optional[str]] = {}
        for imovel_id, ids_docs in docs_alcancaveis_por_imovel.items():
            classificacoes: list = []
            for d in ids_docs:
                classificacoes.extend(classif_por_doc.get(d, []))
            if classificacoes:
                status_map[imovel_id] = _pior_classificacao(classificacoes)
            # Sem fins alcançáveis: omitido (template renderiza "—")

        return status_map
