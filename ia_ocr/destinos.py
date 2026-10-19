"""Mapa do I-5 (§2.A): JSON Pointer editável → destino Django.

Toda linha editável do formulário de revisão resolve o seu destino por
``destino_de(chave, *valores_efetivos)``. O destino diz:

- **para onde vai** (``modelo``/``campo``, ex.: ``dominial.Lancamento`` +
  ``valor_transacao``), ou ``SEM_DESTINO`` — linha editável, mas só
  conferência (``DadosRevisados.conferencia``), nunca campo importável;
- **o tipo canônico** do valor (``tipo_valor``, mesmo vocabulário do
  ``CampoSugerido.tipo_valor``);
- **os limites** (``max_length``/``max_digits``/``decimal_places``), lidos
  do ``_meta`` do modelo real — resolvido LAZILY, dentro da função, para
  que o mapa não importe models no módulo-level.

Casos que dependem do valor efetivo (§2.A):

- ``/acts/*/partes/*``: é ``parte`` só se o papel efetivo ∈
  {transmitente, adquirente}; cônjuge/representante → ``SEM_DESTINO``
  (contexto de pessoa, sem exigência de escolha);
- ``/acts/*/partes/*/documento_identificacao/valor``: CPF com 11 dígitos
  → ``Pessoas.cpf``; RG → ``Pessoas.rg``; CPF mascarado, CNPJ, CGC,
  OUTRO → ``SEM_DESTINO`` + aviso (nunca bloqueio);
- ``/acts/*/area``: o destino é ``Lancamento.area``; a pendência de
  unidade (≠ ha sem conversão confirmada) é do motor de revisão (§18).

Chave fora da tabela levanta ``ChaveDesconhecida`` — o motor de revisão
converte em revisão; nunca silencia.
"""

import re
from dataclasses import dataclass
from typing import Optional, Union

from django.apps import apps

MAX_DIGITS_SEM_DESTINO = 20
DECIMAL_PLACES_SEM_DESTINO = 4
MAX_LENGTH_SEM_DESTINO = 10_000

_TIPO_VALOR_SEM_DESTINO = 'texto'

# papéis que casam com LancamentoPessoa.TIPO_CHOICES
PAPEIS_COM_DESTINO = frozenset({'transmitente', 'adquirente'})

# tipos de documento de identificação do enum do A3
TIPOS_DOCUMENTO = frozenset({'CPF', 'CNPJ', 'CGC', 'RG', 'OUTRO'})

# sem máscara visível (§party.normalized): o A3 só remove espaço/máscara
# visível, então a quantidade TOTAL de dígitos decide se cabe no CPF.
_so_digitos = re.compile(r'\D')


@dataclass(frozen=True)
class Destino:
    """Alvo (ou não-alvo) de uma linha editável atualizada com limites."""

    modelo: Optional[str]
    campo: Optional[str]
    tipo_valor: Optional[str]
    max_length: Optional[int] = None
    max_digits: Optional[int] = None
    decimal_places: Optional[int] = None
    choices: tuple[tuple[str, str], ...] = ()

    @property
    def campo_modelo(self):
        """``'dominial.Lancamento.valor_transacao'``; ``None`` p/ SEM."""
        if self.modelo is None:
            return None
        if self.campo is None:
            return self.modelo
        return f'{self.modelo}.{self.campo}'

    def get_modelo_object(self):
        """O modelo real, por ``apps.get_model`` — LAZY."""
        return apps.get_model(self.modelo)

    def get_field(self):
        """O Field do alvo — LAZY: só com ``modelo``+``campo`` definidos."""
        if self.modelo is None or self.campo is None:
            return None
        return self.get_modelo_object()._meta.get_field(self.campo)


# Sentinela: linha editável (fica em conferência), sem campo importável.
# Texto: 10 000 anti-lixo. Decimal genérico: (20, 4) - nunca conflita com
# um destino real (máx. atual é 12,4).
SEM_DESTINO = Destino(
    modelo=None,
    campo=None,
    tipo_valor=_TIPO_VALOR_SEM_DESTINO,
    max_length=MAX_LENGTH_SEM_DESTINO,
    max_digits=MAX_DIGITS_SEM_DESTINO,
    decimal_places=DECIMAL_PLACES_SEM_DESTINO,
)


class ChaveDesconhecida(LookupError):
    """Chave não mapeada — o motor de revisão converte em revisão."""


# modelo → str 'dominial.<Modelo>' | campo → o campo do modelo | None quando
# SEM_DESTINO já cobre o ponteiro na tabela.
DESTINOS = {
    '/document/tipo': ('dominial.Documento', 'tipo', 'enum'),
    '/document/numero': ('dominial.Documento', 'numero', 'texto'),
    '/document/data': ('dominial.Documento', 'data', 'data'),
    '/document/cartorio': ('dominial.Documento', 'cartorio', 'cartorio'),
    '/document/cri_atual': ('dominial.Documento', 'cri_atual', 'cartorio'),
    '/document/livro': ('dominial.Documento', 'livro', 'texto'),
    '/document/folha': ('dominial.Documento', 'folha', 'texto'),
    '/document/imovel_descricao': SEM_DESTINO,
    '/document/area': SEM_DESTINO,
    '/acts/*': ('dominial.Lancamento', None, 'ato'),
    '/acts/*/rotulo': SEM_DESTINO,
    '/acts/*/tipo_sugerido': ('dominial.Lancamento', 'tipo', 'enum'),
    '/acts/*/numero_lancamento': (
        'dominial.Lancamento', 'numero_lancamento', 'texto',
    ),
    '/acts/*/data': ('dominial.Lancamento', 'data', 'data'),
    '/acts/*/valor_transacao': (
        'dominial.Lancamento', 'valor_transacao', 'decimal',
    ),
    '/acts/*/area': ('dominial.Lancamento', 'area', 'area'),
    '/acts/*/titulo': ('dominial.Lancamento', 'titulo', 'texto'),
    '/acts/*/forma': ('dominial.Lancamento', 'forma', 'texto'),
    '/acts/*/descricao': ('dominial.Lancamento', 'descricao', 'texto'),
    '/acts/*/detalhes': ('dominial.Lancamento', 'detalhes', 'texto'),
    '/acts/*/observacoes': ('dominial.Lancamento', 'observacoes', 'texto'),
    '/acts/*/origem/tipo_documento': (
        'dominial.LancamentoOrigem', 'tipo_documento', 'enum',
    ),
    '/acts/*/origem/numero': ('dominial.LancamentoOrigem', 'numero', 'texto'),
    '/acts/*/origem/cartorio': (
        'dominial.LancamentoOrigem', 'cartorio', 'cartorio',
    ),
    '/acts/*/origem/livro': ('dominial.Lancamento', 'livro_origem', 'texto'),
    '/acts/*/origem/folha': ('dominial.Lancamento', 'folha_origem', 'texto'),
    '/acts/*/origem/data': ('dominial.Lancamento', 'data_origem', 'data'),
    '/acts/*/cartorio_transmissao': (
        'dominial.Lancamento', 'cartorio_transmissao', 'cartorio',
    ),
    '/acts/*/eh_inicio_matricula': (
        'dominial.Lancamento', 'eh_inicio_matricula', 'booleano',
    ),
    '/acts/*/partes/*': ('dominial.LancamentoPessoa', 'tipo', 'enum'),
    '/acts/*/partes/*/nome': (
        'dominial.LancamentoPessoa', 'nome_digitado', 'texto',
    ),
    '/acts/*/partes/*/documento_identificacao/tipo': SEM_DESTINO,
    '/acts/*/partes/*/documento_identificacao/valor': None,  # por valor efetivo
    '/closure/indicio_fim_cadeia': SEM_DESTINO,
    '/closure/origem_publica_sugerida': SEM_DESTINO,
    '/closure/classificacao_sugerida': SEM_DESTINO,
}


def destino_de(chave, *valores_efetivos):
    """Responde o destino de uma chave de linha editável (§2.A).

    ``chave`` é um ponteiro de linha (o índice pode ser ``*`` ou o número
    real). ``valores_efetivos``: o valor efetivo das linhas de contexto
    do ato/parte que o chamador já leu (ex.: o ``papel`` da linha
    ``/acts/N/partes/N`` e o ``tipo`` de documento_identificacao para a
    de valor) — só os casos dependentes de valor os usam.

    ``SEM_DESTINO`` é resposta válida (linha fica só em conferência).
    Chave fora da tabela → ``ChaveDesconhecida``.
    """
    padrao = _normalizar(chave)
    if padrao not in DESTINOS:
        raise ChaveDesconhecida(
            f'chave de editável fora do mapa: {padrao}'
        )

    if padrao == '/acts/*/partes/*':
        return _destino_parte(padrao, valores_efetivos)
    if padrao == '/acts/*/partes/*/documento_identificacao/valor':
        return _destino_documento_identificacao(valores_efetivos)

    entrada = DESTINOS[padrao]
    if isinstance(entrada, Destino):
        return entrada  # SEM_DESTINO fixo do mapa
    return _do_campo(entrada[0], entrada[1], entrada[2])


def caminhos_editaveis(schema):
    """Todos os ponteiros editáveis do A3 — folhas com ``normalized``.

    Percorre o schema vendorizado (resolvendo ``$ref``/``allOf`` contra
    ``$defs``) e devolve os ponteiros dos campos editáveis, com ``*``
    na posição de índice de array — a base do teste de cobertura (§25).
    """
    defs = schema.get('$defs', {})
    editaveis = set()

    def _resolver(no):
        while isinstance(no, dict) and '$ref' in no:
            no = defs[no['$ref'].rsplit('/', 1)[-1]]
        return no

    def _caminhar(no, caminho):
        no = _resolver(no)
        if not isinstance(no, dict):
            return
        if 'normalized' in no.get('properties', {}):
            editaveis.add(caminho)
        for chave, propriedade in no.get('properties', {}).items():
            _caminhar(propriedade, f'{caminho}/{chave}')
        if 'items' in no:
            _caminhar(no['items'], f'{caminho}/*')
        for sub in no.get('allOf', []):
            _caminhar(sub, caminho)

    _caminhar(schema, '')
    return sorted(editaveis)


def _normalizar(chave):
    tokens = []
    for token in str(chave).strip('/').split('/'):
        tokens.append('*' if token.isdigit() else token)
    return '/' + '/'.join(tokens)


def _do_campo(modelo, campo, tipo_valor):
    """Lê os limites do ``_meta`` do modelo real — dentro da função.

    ``tipo`` da linha e os ``SEM_DESTINO`` não têm campo: mantêm os
    limites da sentinela já passada.
    """
    if campo is None:
        SEM = SEM_DESTINO
        return Destino(
            modelo=modelo,
            campo=None,
            tipo_valor=tipo_valor,
            max_length=SEM.max_length,
            max_digits=SEM.max_digits,
            decimal_places=SEM.decimal_places,
        )
    field = apps.get_model(modelo)._meta.get_field(campo)
    # O formulário revisa o código do tipo, não o PK do ForeignKey.
    # Lancamento.tipo não tem choices; o enum pertence a LancamentoTipo.
    choices = (
        tuple(apps.get_model('dominial.LancamentoTipo').TIPO_CHOICES)
        if (modelo, campo) == ('dominial.Lancamento', 'tipo') else ()
    )
    return Destino(
        modelo=modelo,
        campo=campo,
        tipo_valor=tipo_valor,
        max_length=getattr(field, 'max_length', None),
        max_digits=getattr(field, 'max_digits', None),
        decimal_places=getattr(field, 'decimal_places', None),
        choices=choices,
    )


def _destino_parte(padrao, valores_efetivos):
    """Papel efetivo ∈ {transmitente, adquirente} → LancamentoPessoa.

    ``valores_efetivos`` pode trazer o papel em qualquer posição; o
    primeiro string reconhecido como papel decide. Sem papel conhecido,
    considera SEM_DESTINO (não-bloqueante, §2.A).
    """
    papel = _primeiro_string(valores_efetivos)
    if papel is None or papel not in PAPEIS_COM_DESTINO:
        return SEM_DESTINO
    return _do_campo(*DESTINOS[padrao])


def _destino_documento_identificacao(valores_efetivos):
    """CPF 11 dígitos → Pessoas.cpf; RG → Pessoas.rg; resto → SEM.

``valores_efetivos`` traz o ``tipo`` efetivo e o ``valor`` efetivo
    (qualquer ordem em ``valores_efetivos``). Tipo desconhecido nunca
    levanta — ``SEM_DESTINO`` com aviso é a resposta (§2.A, item 18).
    """
    tipo = None
    valor = None
    for item in valores_efetivos:
        if isinstance(item, str) and item in TIPOS_DOCUMENTO and tipo is None:
            tipo = item
        elif isinstance(item, str):
            valor = valor if valor is not None else item

    if tipo == 'CPF':
        digitos = _so_digitos.sub('', valor or '')
        if len(digitos) == 11:
            return _do_campo('dominial.Pessoas', 'cpf', 'texto')
    elif tipo == 'RG':
        return _do_campo('dominial.Pessoas', 'rg', 'texto')

    return SEM_DESTINO


def _primeiro_string(valores):
    for item in valores:
        if isinstance(item, str):
            return item
    return None
