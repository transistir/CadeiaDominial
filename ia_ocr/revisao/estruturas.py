"""Constantes, exceções e dataclasses compartilhados da revisão."""

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import Decimal


LIMIAR_CONFIANCA = 0.70

MOTIVO_NORMALIZACAO_INVALIDA = 'normalizacao_invalida'
MOTIVO_UNIDADE_AREA = 'unidade_area'
MOTIVO_BAIXA_CONFIANCA = 'baixa_confianca'
MOTIVO_CLOSURE = 'closure'
MOTIVO_EVIDENCIA_INVALIDA = 'evidencia_invalida'
MOTIVO_TRECHO_AUSENTE = 'trecho_ausente'
MOTIVO_CRIAR_NOVO_SEM_NOME = 'criar_novo_sem_nome'

# Destinos obrigatórios (§2.A): ausentes no payload → placeholder em revisão.
_OBRIGATORIOS_DOCUMENTO = ('tipo', 'data', 'cartorio')
_OBRIGATORIOS_ATO = ('tipo_sugerido', 'data')
_CHAVE_OBRIGATORIA_ATO = re.compile(r'/acts/\d+/(.+)')

# Opcionais no formulário, inclusive quando o payload não resolve o tipo.
CAMPOS_DA_TRANSMISSAO = ('livro_transacao', 'folha_transacao', 'data_transacao')

# #324 (I-11d): campos da origem do ato que o formulário de lançamento tem e
# o revisor precisa poder preencher mesmo quando o documento não os traz —
# "não consta no documento" é uma informação, não um buraco sem controle.
# O cartório fica de fora: quem o exige é o tipo (``_caminhos_do_tipo``).
# Só viram linha vazia quando o ato TEM origem (``_ato_tem_origem``) ou o
# tipo exige ``origem/cartorio`` — no desmonte inicial (``_ato``) e também ao
# trocar o tipo na revisão (``garantir_placeholders_obrigatorios``);
# averbação sem origem não ganha origem vazia.
CAMPOS_DA_ORIGEM = ('tipo_documento', 'numero', 'livro', 'folha', 'data')

# Tarefa C (#322/PR #327) e #328 (regra do Hiure, 11/11): o formulário de
# lançamento manda — ``valor_transacao`` e ``detalhes`` não existem nele,
# então não existem na revisão nem na importação. O schema A3 do Umbelino
# (v1.1) continua mandando as folhas; o payload segue com elas, mas nenhuma
# linha é criada (payload novo) e linhas antigas já salvas são ignoradas na
# leitura (_contexto_revisao) e na tela.
LINHAS_IGNORADAS = frozenset({'valor_transacao', 'detalhes'})

# Revisão Opus (nit #322): o nome só ignora a FOLHA do A3 —
# ``/acts/N/valor_transacao`` etc. (e o ponteiro de padrão ``/acts/*/…``
# que a cobertura §25 compara) —, não qualquer folha homônima em outra
# profundidade (``/document/detalhes``, ``/acts/0/partes/0/…``).
# Rodada 2 (Opus N-3): os nomes saem de ``LINHAS_IGNORADAS`` (fonte única,
# sem repetir a lista aqui); as fronteiras acima seguem provadas em
# ``DesnormalizarTest.test_fronteiras_da_linha_ignorada``.
_LINHA_IGNORADA = re.compile(
    r'/acts/(?:\d+|\*)/(?:%s)'
    % '|'.join(re.escape(nome) for nome in sorted(LINHAS_IGNORADAS))
)


def linha_ignorada(chave) -> bool:
    """A chave é exatamente a folha ignorada (índice real ou padrão ``*``)."""
    return isinstance(chave, str) and bool(
        _LINHA_IGNORADA.fullmatch(chave)
    )

_TIPOS_NORMALIZAVEIS = ('data', 'decimal', 'area')

_AREA_DE_ATO = re.compile(r'/acts/\d+/area')


class RevisaoInvalidada(Exception):
    """A extração não pode mais ser consumida como uma revisão concluída."""

    code = 'revisao_invalida'


class EscolhaIncompativel(Exception):
    """A escolha de cadastro não corresponde ao tipo da linha (HTTP 422)."""

    code = 'escolha_incompativel'

    def __init__(self, chave):
        self.chave = chave
        super().__init__(self.code)


class EscolhaInvalida(EscolhaIncompativel):
    """O id escolhido não está entre os candidatos recomputados (HTTP 422).

    A tela só oferece ``match_candidatos``; um id fora da lista veio de um
    estado antigo (reload diferido) e não pode regravar a escolha.
    """

    code = 'escolha_invalida'


@dataclass(frozen=True)
class ParteRevisada:
    papel: str
    nome: str | None
    cpf: str | None
    rg: str | None
    pessoa_id: int | None
    criar_novo: bool
    # Chave da linha estrutural da parte (``/acts/N/partes/M``): a importação
    # usa para ancorar erros por campo e vínculos de auditoria.
    chave: str | None = None


@dataclass(frozen=True)
class AtoRevisado:
    ordem: int
    tipo: str
    numero_lancamento: str | None
    data: date
    area: Decimal | None
    titulo: str | None
    forma: str | None
    descricao: str | None
    observacoes: str | None
    cartorio_origem_id: int | None
    cartorio_transmissao_id: int | None
    cartorio_origem_criar_novo: bool
    cartorio_transmissao_criar_novo: bool
    eh_inicio_matricula: bool | None
    origem: dict | None
    partes: tuple[ParteRevisada, ...]
    cartorio_origem_nome: str | None = None
    cartorio_transmissao_nome: str | None = None
    # Chave da linha estrutural do ato (``/acts/N``): a importação usa para
    # responder os atos marcados no POST e vincular a auditoria.
    chave: str | None = None
    tipo_explicito: str | None = None
    tipo_sugerido: str | None = None
    livro_transacao: str | None = None
    folha_transacao: str | None = None
    data_transacao: date | None = None


@dataclass(frozen=True)
class DocumentoRevisado:
    tipo: str
    numero: str | None
    data: date
    cartorio_id: int | None
    cri_atual_id: int | None
    cartorio_criar_novo: bool
    cri_atual_criar_novo: bool
    livro: str | None
    folha: str | None
    cartorio_nome: str | None = None
    cri_atual_nome: str | None = None


@dataclass(frozen=True)
class DadosRevisados:
    documento: DocumentoRevisado
    atos: tuple[AtoRevisado, ...]
    conferencia: dict

def _eh_folha(no):
    """Folha editável do A3: objeto com a chave ``normalized``."""
    return isinstance(no, dict) and 'normalized' in no

_NAO_DIGITO = re.compile(r'\D')

MATCH_PESSOA_CANDIDATOS = 'match_pessoa_candidatos'

def _normalizar_nome(texto):
    """Forma canônica para comparação: NFKD sem acentos, sem caixa,
    espaços colapsados. Não-string (None, lixo) → ``''``."""
    if not isinstance(texto, str):
        return ''
    decomposto = unicodedata.normalize('NFKD', texto)
    sem_acentos = ''.join(
        caractere for caractere in decomposto
        if not unicodedata.combining(caractere)
    )
    return ' '.join(sem_acentos.casefold().split())


def _so_digitos(texto):
    if not isinstance(texto, str):
        return ''
    return _NAO_DIGITO.sub('', texto)
