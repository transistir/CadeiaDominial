"""Classificação do payload da extração: lançamentos e não reconhecidos."""

from .analise import analisar_rotulo, resolver_tipo
from .numeros import _ordem_ordenavel, _valor_do_campo
from .tipos import Classificacao

# Campos do cabeçalho (``/document/*``) que formam o início de matrícula.
CAMPOS_INICIO_MATRICULA = (
    'livro', 'numero', 'cartorio', 'area', 'data', 'imovel_descricao',
)


def classificar_atos(payload) -> Classificacao:
    """Classifica os atos do payload da extração; nunca levanta exceção.

    - ``inicio_matricula``: os campos do cabeçalho ``/document/*`` (que
      NÃO é um ato); ``None`` sem ``document``.
    - ``lancamentos``: só o que é R/Av com número, em ordem REVERSA; o tipo
      resolvido prefere o RÓTULO — ``tipo_sugerido.normalized`` presente e
      válido é usado quando concorda; divergindo, prevalece o rótulo e o
      item sai com ``divergencia=True`` (não é erro fatal).
    - ``nao_reconhecidos``: rótulos que o parser não entendeu (rotulo
      ``M`` com número não entra em nenhuma das duas listas — é referência
      de matrícula, não lançamento, e não é erro).

    ``ordem``: a chave de ordenação é a ``ordem`` válida do ato ou, sem
    ela, o índice do payload + 1 (``revisao.py`` idem — P1-2, #322 rodada
    3); o campo ``ordem`` exposto no item segue COMO VEIO (índice + 1
    quando a chave não veio). ``acts`` que não é lista e ``ordem``
    NaN/Infinity não levantam exceção: caem em vazio/índice (P2-6).
    """
    document = payload.get('document') if isinstance(payload, dict) else None
    inicio = None
    if isinstance(document, dict) and document:
        inicio = {
            nome: _valor_do_campo(document.get(nome))
            for nome in CAMPOS_INICIO_MATRICULA
        }

    ordenaveis = []
    nao_reconhecidos = []
    atos = payload.get('acts') if isinstance(payload, dict) else None
    if not isinstance(atos, list):
        # ``acts`` que não é lista (número, bool, texto) não é iterável de
        # atos: sem lançamentos e sem não reconhecidos — e sem TypeError
        # (#322 rodada 3, P2-6).
        atos = []
    for indice, ato in enumerate(atos):
        if not isinstance(ato, dict):
            continue
        ordem = ato['ordem'] if 'ordem' in ato else indice + 1
        rotulo = _valor_do_campo(ato.get('rotulo'))
        analisado = analisar_rotulo(rotulo)
        if not analisado.reconhecido:
            nao_reconhecidos.append({
                'ordem': ordem,
                'rotulo': rotulo,
                'motivo': analisado.motivo,
                'ato': ato,
            })
            continue
        if analisado.eh_matricula:
            continue
        sugerido = _valor_do_campo(ato.get('tipo_sugerido'))
        tipo, divergencia, _origem = resolver_tipo(
            tipo_explicito=None,
            rotulo_texto=analisado,
            tipo_sugerido=sugerido,
        )
        ordenaveis.append((
            _ordem_ordenavel(ato.get('ordem'), indice),
            {
                'ordem': ordem,
                'tipo': tipo,
                'numero': analisado.numero,
                'matricula': analisado.matricula,
                'ato': ato,
                'divergencia': divergencia,
            },
        ))
    # Chave inteira (``ordem`` vem como string no payload real, #322) com
    # fallback no índice do payload; o campo exposto segue como veio.
    ordenaveis.sort(key=lambda par: par[0], reverse=True)
    return Classificacao(
        inicio_matricula=inicio,
        lancamentos=[item for _, item in ordenaveis],
        nao_reconhecidos=nao_reconhecidos,
    )
