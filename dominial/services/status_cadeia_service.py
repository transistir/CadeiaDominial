from ..models import OrigemFimCadeia

# Prioridade quando um imóvel tem múltiplas origens de fim de cadeia com
# classificações diferentes: prevalece a "pior" situação.
_PRIORIDADE = {
    'sem_origem': 3,
    'inconclusa': 2,
    'origem_lidima': 1,
}

# Classificação ausente é tratada como "sem_origem" (mesmo fallback usado na
# árvore da cadeia dominial).
_CLASSIFICACAO_PADRAO = 'sem_origem'


class StatusCadeiaService:
    @staticmethod
    def status_por_imovel(tis_id):
        """Retorna {imovel_id: status} para os imóveis da TI com cadeia finalizada.

        status = 'origem_lidima' | 'sem_origem' | 'inconclusa'

        Imóveis sem nenhuma origem ``fim_cadeia=True`` ficam ausentes do dict
        (equivalente a status ``None`` / cadeia em andamento).
        """
        linhas = (
            OrigemFimCadeia.objects
            .filter(
                fim_cadeia=True,
                lancamento__documento__imovel__terra_indigena_id=tis_id,
            )
            .values_list(
                'lancamento__documento__imovel_id',
                'classificacao_fim_cadeia',
            )
        )

        status_map = {}
        for imovel_id, classificacao in linhas:
            classificacao = classificacao or _CLASSIFICACAO_PADRAO
            atual = status_map.get(imovel_id)
            if atual is None or _PRIORIDADE[classificacao] > _PRIORIDADE[atual]:
                status_map[imovel_id] = classificacao
        return status_map
