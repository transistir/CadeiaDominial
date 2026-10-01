"""
Ordem canônica entre as origens de um mesmo documento (issue #201).

Regra definida pelo dono do produto:

1. A ordem das LINHAS da cadeia é a HIERARQUIA: quem é citado como origem
   aparece depois de quem o citou. Ela é a caminhada do tronco principal
   (`identificar_tronco_principal`), e esta chave NUNCA reordena as linhas.
2. Entre IRMÃOS — as várias origens de UM MESMO documento — vale a chave
   canônica, nesta precedência:
   a. matrícula antes de transcrição — prioridade absoluta, não desempate:
      qualquer matrícula vem antes de qualquer transcrição, seja qual for o
      número;
   b. número maior antes de menor, comparado como inteiro (nunca como texto).
   Com `imovel`, `chave_ordem_cadeia` ainda põe o documento do imóvel (a sua
   identidade registral) antes de todos; uma origem nunca recebe esse rank.

A data do documento não entra na regra: neste banco ela é quase sempre
fictícia ou presumida.

Este módulo é a única implementação dessa ordem. Consomem a chave:

- a origem que a caminhada do tronco segue a cada passo quando o usuário não
  escolheu nenhuma, e os botões de origem da tabela, com essa mesma origem
  destacada por padrão, sempre a primeira da lista
  (`obter_origens_resolvidas`, em `hierarquia_utils`);
- o documento inicial do tronco, quando falta o documento do imóvel
  (`identificar_tronco_principal`);
- a ordem dos documentos fora do tronco no modal de sequência
  (`organizar_documentos_hierarquicamente`).

Seguem o mesmo tronco principal, na ordem da caminhada, as superfícies que
consomem `HierarquiaService.obter_tronco_principal`: as linhas da tabela da
cadeia dominial, nas duas trilhas (`obter_cadeia_tabela` e
`get_cadeia_dominial_tabela`, que também alimenta a exportação PDF da tabela),
a exportação PDF/XLS da cadeia completa, a página da árvore e o modal de
sequência. A exportação
(`CadeiaCompletaService`) continua agrupada por troncos; esta chave decide qual
origem o tronco segue por padrão e, com isso, a sequência de documentos dentro
dele. Medido no test server: a caminhada muda em 14 de 406 imóveis, e o
conjunto de documentos exportados não muda.

As funções não consultam o banco nem importam models, para poderem ser usadas
por `hierarquia_utils` sem ciclo de importação.
"""

from .documento_identidade_utils import PREFIXOS_POR_TIPO


RANK_TIPO = {'matricula': 0, 'transcricao': 1}
# DocumentoTipo só tem matrícula e transcrição hoje. Um tipo diferente, se
# surgir, vai depois das transcrições em vez de quebrar a ordenação.
RANK_OUTRO_TIPO = 2

_TIPO_POR_PREFIXO = {prefixo: tipo for tipo, prefixo in PREFIXOS_POR_TIPO.items()}


def eh_documento_do_imovel(documento, imovel):
    """Indica se o documento é a identidade registral do imóvel: pertence ao
    imóvel e tem o tipo principal, o número canônico e o cartório dele."""
    return (
        imovel is not None
        and documento.imovel_id == imovel.id
        and documento.tipo.tipo == imovel.tipo_documento_principal
        and documento.numero_normalizado == imovel.matricula_normalizada
        and documento.cartorio_id == imovel.cartorio_id
    )


def numero_para_ordenacao(numero):
    """Valor inteiro de um número documental, formado só pelos seus dígitos.

    'M002621' e '002621' valem 2621; sem dígitos, 0. Usa `isdecimal` (e não
    `isdigit`) porque caracteres como '²' passam em `isdigit` e quebram `int`.
    """
    digitos = ''.join(c for c in str(numero or '') if c.isdecimal())
    return int(digitos) if digitos else 0


def _chave(documento_do_imovel, tipo, numero):
    return (
        0 if documento_do_imovel else 1,
        RANK_TIPO.get(str(tipo).lower(), RANK_OUTRO_TIPO),
        -numero_para_ordenacao(numero),
    )


def chave_ordem_cadeia(documento, imovel=None):
    """Chave canônica de um documento:
    (0 doc do imóvel | 1 outro, 0 matrícula | 1 transcrição | 2 outro tipo, -número).

    Sem `imovel` (ordem das origens de um documento), nenhum recebe o rank 0.
    """
    return _chave(
        eh_documento_do_imovel(documento, imovel),
        documento.tipo.tipo,
        documento.numero_normalizado or documento.numero,
    )


def chave_ordem_origem(codigo):
    """A mesma chave para um código de origem ainda não resolvido ('M123',
    'T45'): o tipo vem do prefixo, e uma origem nunca é o documento do imóvel.
    Para um documento resolvido a partir do código, coincide com
    `chave_ordem_cadeia(documento)`."""
    tipo = _TIPO_POR_PREFIXO.get(str(codigo).strip()[:1].upper())
    return _chave(False, tipo, codigo)


def chave_ordem_serializada(documento):
    """A mesma chave para um documento já serializado em dict, com 'numero' e,
    se houver, 'tipo' (como os nós da árvore usados pelo modal de sequência).

    Sem 'tipo', o tipo vem do prefixo M/T do número, como em
    `chave_ordem_origem`; um tipo que não é matrícula nem transcrição (o nó de
    fim de cadeia) vai depois das transcrições. Um documento serializado nunca
    recebe o rank de documento do imóvel. Para o dict de um documento, coincide
    com `chave_ordem_cadeia(documento)`.
    """
    tipo = documento.get('tipo')
    if not tipo:
        return chave_ordem_origem(documento['numero'])
    return _chave(False, tipo, documento['numero'])


def ordenar_cadeia(documentos, imovel=None):
    """Nova lista com os documentos na ordem canônica.

    `sorted` é estável (documentos de chave idêntica mantêm a ordem recebida) e
    não altera a lista recebida, que pode ser o valor em cache do tronco.
    """
    return sorted(
        documentos,
        key=lambda documento: chave_ordem_cadeia(documento, imovel),
    )
