from ..models import OrigemFimCadeia

# Prioridade quando um imóvel tem múltiplas origens de fim de cadeia com
# classificações diferentes: prevalece a "pior" situação.
_PRIORIDADE = {
    'sem_origem': 3,
    'inconclusa': 2,
    'origem_lidima': 1,
}


def _rank(classificacao):
    """Prioridade da classificação; ``0`` para ausente/nula/desconhecida.

    Dados criados antes da validação em ``Lancamento.clean()`` podem ter
    ``classificacao_fim_cadeia`` nula ou com valor fora do domínio esperado.
    Nesses casos tratamos como desconhecida (rank 0) em vez de derrubar a
    página.
    """
    if not classificacao:
        return 0
    return _PRIORIDADE.get(classificacao, 0)


class StatusCadeiaService:
    @staticmethod
    def status_por_imovel(tis_id):
        """Retorna {imovel_id: status} para os imóveis da TI com cadeia finalizada.

        status = 'origem_lidima' | 'sem_origem' | 'inconclusa'

        Imóveis sem nenhuma origem ``fim_cadeia=True`` ficam ausentes do dict
        (equivalente a status ``None`` / cadeia em andamento). O mesmo vale para
        imóveis cujas origens só têm classificação desconhecida/nula: melhor
        exibir "em andamento" do que confiar num dado não reconhecido.
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
            rank = _rank(classificacao)
            if rank == 0:
                continue
            atual = status_map.get(imovel_id)
            if atual is None or rank > _rank(atual):
                status_map[imovel_id] = classificacao
        return status_map
