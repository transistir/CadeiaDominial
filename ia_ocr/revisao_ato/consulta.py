"""As abas da revisão: estado de cada ato e ordem de navegação."""

from dataclasses import dataclass, field

from .. import importacao, revisao
from ..models import ImportacaoIA
from ..rotulos import analisar_rotulo

ESTADO_PENDENTE = 'pendente'
ESTADO_IMPORTADO = 'importado'

_PREFIXO_DA_ABA = {'registro': 'R', 'averbacao': 'Av'}


@dataclass
class Resultado:
    """O que aconteceu com o POST de salvar o ato.

    ``situacao``: ``salvo`` | ``invalido`` (o service recusou; nada gravado) |
    ``duplicata`` (origem já existe em outra cadeia; nada gravado) |
    ``ja_salvo`` | ``recusado`` (job/ato fora da revisão).
    """

    situacao: str
    mensagem: str = ''
    mensagem_origens: str | None = None
    duplicata_info: dict | None = None
    lancamento: object = None
    lancamento_id: int | None = None
    # Índices dos atos que continuam pendentes depois deste POST, na ordem
    # da revisão. Vazio com ``salvo`` = a revisão acabou.
    restantes: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Atos e abas
# ---------------------------------------------------------------------------

def atos_da_revisao(extracao, dados=None, linhas=None):
    """As abas da revisão, na ordem do A3: ``[{indice, chave, posicao, rotulo,
    estado, lancamento_id}]``.

    ``importado`` = existe ``ImportacaoIA`` de um lançamento ATUAL (não
    excluído) para a linha do ato NESTA extração. Lançamento excluído depois
    deixa o rastro mas volta o ato a ``pendente`` — o revisor pode salvá-lo
    de novo. Só lê o banco.
    """
    dados = dados if dados is not None else revisao._montar_dados(extracao)
    linhas = linhas if linhas is not None else importacao._linhas_por_chave(extracao)
    salvos = dict(
        ImportacaoIA.objects.filter(
            ocr_job_id=extracao.ocr_job_id, modelo='Lancamento',
            campo__extracao_id=extracao.pk, lancamento__isnull=False,
        ).values_list('campo__chave', 'lancamento_id')
    )
    atos = []
    for posicao, ato in enumerate(dados.atos, start=1):
        indice = int(ato.chave.rsplit('/', 1)[1])
        lancamento_id = salvos.get(ato.chave)
        atos.append({
            'indice': indice,
            'chave': ato.chave,
            'posicao': posicao,
            'rotulo': _rotulo_da_aba(ato, linhas, indice),
            'estado': ESTADO_IMPORTADO if lancamento_id else ESTADO_PENDENTE,
            'lancamento_id': lancamento_id,
        })
    return atos


def _rotulo_da_aba(ato, linhas, indice):
    """``R5``/``Av3``/``Abertura`` — o mesmo rótulo efetivo que decide o tipo."""
    analisado = analisar_rotulo(
        (revisao.rotulo_efetivo(ato.chave, linhas) or '').strip(),
    )
    if analisado.reconhecido and not analisado.eh_matricula and analisado.numero:
        prefixo = _PREFIXO_DA_ABA.get(analisado.tipo)
        if prefixo:
            return f'{prefixo}{analisado.numero}'
    if 'inicio_matricula' in (ato.tipo, analisado.tipo):
        return 'Abertura'
    return f'Ato {indice + 1}'


def proximo_pendente(atos, depois_de=None):
    """Primeiro ato pendente depois do ``depois_de`` (índice), com volta ao início.

    ``None`` quando não resta nenhum. Sem ``depois_de``, o primeiro pendente.
    """
    pendentes = [ato for ato in atos if ato['estado'] == ESTADO_PENDENTE]
    if not pendentes:
        return None
    if depois_de is not None:
        posicoes = {ato['indice']: ato['posicao'] for ato in atos}
        a_partir = posicoes.get(depois_de)
        if a_partir is not None:
            for ato in pendentes:
                if ato['posicao'] > a_partir:
                    return ato
    return pendentes[0]
