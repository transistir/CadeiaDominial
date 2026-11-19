"""Tipo, número e duplicata do ato: rótulo efetivo × tipo_sugerido (#322)."""
import re

from django.urls import reverse

from dominial.models import Lancamento, LancamentoTipo

from .. import revisao
from ..rotulos import (
    analisar_rotulo, compor_numero_lancamento, normalizar_numero_lancamento,
    resolver_tipo, tipo_do_rotulo,
)


PREFIXO_TIPO_DOCUMENTO = {'matricula': 'M', 'transcricao': 'T'}

# Número puro, já sem prefixo ('5', '12.345') — a mesma forma que o parser
# de rótulos reconhece e preserva como veio (#322 rodada 5).
_NUMERO_SIMPLES = re.compile(r'\d+(?:\.\d+)*')


def _resolver_tipo_e_numero(ato, rotulo, documento):
    """Tipo e número que a gravação gravará — e a prévia mostra (#322 r4–5).

    A MESMA resolução nos dois caminhos (P2-2): a escolha EXPLÍCITA do
    revisor (``ato.tipo_explicito``, P1 da #322/PR #327) vence; sem ela, o
    tipo do RÓTULO reconhecido (R/Av) prevalece sobre o ``tipo_sugerido``
    divergente — a regra do ``classificar_atos`` — e o número é o composto
    canônico do V1 ('R5
    M237', P1-1 da rodada 3). Rótulo de MATRÍCULA (``M-3-14511``) não é
    lançamento (P2-1): não define tipo (o ``tipo_sugerido`` decide) e o
    número da matrícula NUNCA vira número de ato — compor com ele gravaria
    ``'RM-3-14511 M237'``. O rótulo ``M`` só descarta o número que VEIO da
    referência de matrícula: o ``/numero_lancamento`` (já efetivo/revisado)
    que traz um número de ato válido (rótulo R/Av ou número puro) é
    preservado e composto normalmente (P2, rodada 5 — antes a rodada 4
    zerava também o número corrigido).
    Devolve ``(LancamentoTipo | None, numero | None, avisos)``; sem tipo
    configurado o número vem None e o chamador trata o
    ``tipo_inexistente``.

    Os avisos nunca bloqueiam a gravação:

    - rótulo × ``tipo_sugerido`` válidos e diferentes: o rótulo venceu
      (P2-3, rodada 3) — o mesmo texto da gravação, para a prévia expor o
      conflito antes de o usuário confirmar;
    - rótulo de matrícula sem número de ato válido no campo: sem número
      extraído (P2-1) — o item segue sendo tratado pela UI (#321), nada
      vira exceção;
    - rótulo de matrícula com número válido no campo: o número preservado
      veio do campo revisado, não do rótulo (P2, rodada 5).
    """
    # P1 (Greptile, #322/PR #327): a fonte da escolha EXPLÍCITA é o
    # ``AtoRevisado.tipo_explicito`` (revisao._valor_explicito — edição em
    # ``valor_final`` OU sugestão confirmada na flag ``escolha_explicita``).
    # O fallback antigo tratava ``ato.tipo`` divergente como escolha — mas
    # ``ato.tipo`` é o valor EFETIVO (revisado ou, na falta, o do próprio
    # rótulo): com ele na frente, um rótulo disfarçado de decisão vencia a
    # si mesmo e a confirmação do revisor continuava perdendo para o
    # rótulo. Linha de tipo vazia (estado antigo/re-extração — a pendência
    # da I-5 impede ``importar`` de chegar aqui) não decide nada.
    tipo_explicito = ato.tipo_explicito
    tipo_sugerido = ato.tipo_sugerido
    if ato.tipo == '':
        tipo_explicito = None
        tipo_sugerido = None

    tipo_nome, divergencia, _origem = resolver_tipo(
        tipo_explicito, rotulo, tipo_sugerido,
    )
    tipo = (
        LancamentoTipo.objects.filter(tipo=tipo_nome).order_by('pk').first()
        if tipo_nome is not None else None
    )
    avisos = []
    if divergencia:
        tipo_rotulo = (
            rotulo.tipo if rotulo.reconhecido and not rotulo.eh_matricula else None
        )
        avisos.append(
            f'O rótulo indica {tipo_rotulo}; o tipo sugerido '
            f'({tipo_sugerido}) foi ignorado.'
        )
    if rotulo.eh_matricula:
        # P2 (#322 rodada 5): a matrícula do rótulo não vira número de
        # ato, mas o número de /numero_lancamento que É um número de ato
        # válido continua valendo — o aviso reflete o que aconteceu.
        numero_do_ato = _numero_de_ato_do_campo(ato.numero_lancamento)
        componivel = numero_do_ato is not None
        avisos.append(
            'O rótulo é referência de matrícula (prefixo M), não de '
            'lançamento; o número de ato preservado veio do campo '
            'revisado, não do rótulo.'
            if numero_do_ato is not None else
            'O rótulo é referência de matrícula (prefixo M), não de '
            'lançamento; nenhum número de ato foi extraído dele.'
        )
    else:
        numero_do_ato, componivel = _numero_do_campo(ato.numero_lancamento)
    if tipo is None:
        numero = None
    elif numero_do_ato is None:
        # Sem número o composto canônico só muda o início de matrícula
        # (a sigla); registro/averbação gravam sem número, como antes.
        numero = compor_numero_lancamento(tipo.tipo, None, documento.numero)
    elif componivel:
        numero = compor_numero_lancamento(
            tipo.tipo, numero_do_ato, documento.numero,
        )
    else:
        # P1-1 (#322 rodada 7): texto que NÃO é número de ato ('X-1',
        # 'Av. Brasil') é preservado como veio (trim), sem prefixo nem
        # sigla. Compor gravava 'RX-1 M237' e a duplicata contra o 'X-1'
        # gravado não casava — a base comparava texto com texto.
        numero = numero_do_ato
    return tipo, numero, avisos


def _tipo_documento_da_origem(origem, numero):
    """Tipo documental da origem: o revisado, ou inferido do prefixo M/T.

    A regra mora em ``revisao.tipo_da_origem`` — a revisão (aviso de
    homônimo, #267) e a importação não podem divergir no tipo da origem.
    """
    return revisao.tipo_da_origem(origem.get('tipo_documento'), numero)


def _lancamento_duplicado(documento, tipo, data, numero, lancamentos=None):
    """Lançamento existente que colide com o ato, ou None.

    O número é comparado com a MESMA função dos DOIS lados — o parser de
    rótulos, que é também o que grava: 'R5 M237' (formato do fluxo
    manual), 'R-5' e 'Av: 6-237' (legado do importador) e '5' normalizam
    para o número do ato e casam entre si (#322); ' R-1 ' é duplicata de
    'R-1' (#263 rodada 6, Codex P2) e o ``'\\n'`` que texto de OCR deixa
    na borda do número também escapava sob o ``TRIM()`` do SQL da rodada
    7 (#263 rodada 8, review Opus P2). A tupla (documento, tipo, data,
    número) — com número nulo casando null e gravado vazio (null, '' e só
    espaços) — e ainda o número sozinho dentro do documento, mudando tipo
    ou data.

    O número sozinho (#322 rodada 3, P2-1) exige rótulos COMPATÍVEIS: os
    DOIS lados com prefixo R/Av reconhecido e tipos DIFERENTES ('R-5' ×
    'AV5 M237') NÃO são duplicata — a numeração é por tipo (transcrição,
    numeração antiga, erro de OCR passam a importar). Lado sem rótulo
    reconhecido (número puro, texto comum) mantém a comparação antiga de
    texto, incluindo o ' R-1 ' × 'R-1' do #263. ``lancamentos`` restringe
    onde procurar (padrão: todos).
    """
    tipo_recebido = tipo_do_rotulo(numero)
    numero = normalizar_numero_lancamento(numero)
    if lancamentos is None:
        lancamentos = Lancamento.objects.all()
    # A busca é por documento (poucas linhas) e a decisão é no Python:
    # além da normalização igual à que grava, TRIM com outro caractere não
    # é portátil entre SQLite e Postgres. ``order_by('pk')`` mantém o
    # determinismo que o ``.first()`` anterior dava.
    candidatos = (
        lancamentos.filter(documento=documento)
        .select_related('documento__imovel')
        .order_by('pk')
    )
    mesmo_numero = None
    for lancamento in candidatos:
        gravado = normalizar_numero_lancamento(
            lancamento.numero_lancamento,
        ) or ''
        if numero:
            if gravado != numero:
                continue
            # P2-1: os dois lados com rótulo R/Av conhecido e tipos
            # DIFERENTES não colidem no fallback do número sozinho.
            tipo_gravado = tipo_do_rotulo(lancamento.numero_lancamento)
            if (
                tipo_recebido is not None and tipo_gravado is not None
                and tipo_recebido != tipo_gravado
            ):
                continue
            # (b) número sozinho dentro do documento, mudando tipo/data —
            # fallback: a tupla completa (a) tem prioridade.
            mesmo_numero = mesmo_numero or lancamento
            if lancamento.tipo_id == tipo.pk and lancamento.data == data:
                return lancamento
        elif not gravado and lancamento.tipo_id == tipo.pk and (
            lancamento.data == data
        ):
            # null, '' e só-espaços casam como vazio — gravado só com
            # espaços faz o strip virar '', como um ''.
            return lancamento
    return mesmo_numero


def _existente(lancamento):
    """``{id, url}`` do lançamento duplicado, sem expor outros dados."""
    return {
        'id': lancamento.pk,
        'url': _url_lancamento(lancamento),
    }


def _url_lancamento(lancamento):
    # O FK do Imovel se chama literalmente ``terra_indigena_id``: o attname
    # do id é ``terra_indigena_id_id`` (herança de nomes do schema legado).
    imovel = lancamento.documento.imovel
    return reverse('editar_lancamento', kwargs={
        'tis_id': imovel.terra_indigena_id_id,
        'imovel_id': imovel.pk,
        'lancamento_id': lancamento.pk,
    })


def _numero_do_campo(texto):
    """``(número a gravar, pode ser composto no formato canônico do V1)``.

    P1-1 (#322 rodada 7): só é número de ato — e só aceita a composição
    ``'R5 M237'``/``'AV6 M237'`` — o rótulo R/Av reconhecido ('R-5' → '5',
    o normalizador devolve o número puro) ou o número puro já sem prefixo
    ('5', '12.345'). Qualquer outro texto ('X-1', 'Av. Brasil', a
    referência 'M-3-14511') é preservado como veio (trim), sem prefixo e
    sem sigla do documento: a duplicata compara texto com texto, como a
    base fazia. Compor qualquer texto gravava 'RX-1 M237' e a duplicata
    contra o 'X-1' gravado passava.
    """
    analisado = analisar_rotulo(texto)
    if analisado.reconhecido and not analisado.eh_matricula:
        return analisado.numero, True
    normalizado = normalizar_numero_lancamento(texto)
    if normalizado is None:
        return None, False
    return normalizado, bool(_NUMERO_SIMPLES.fullmatch(normalizado))


def _numero_de_ato_do_campo(texto):
    """Número de ato válido em ``/numero_lancamento`` (já efetivo/revisado).

    P2 (#322 rodada 5): sob rótulo de MATRÍCULA, o que não pode virar
    número de ato é a REFERÊNCIA de matrícula ('M-3-14511') — o número
    corrigido no campo é preservado e composto. Vale como número de ato:

    - rótulo R/Av reconhecido ('R-5', 'Av: 2-237'): o número do ato
      ('5', '2'), nunca o texto como veio (o normalizador devolvendo o
      número do ato);
    - número puro já sem prefixo ('5', '12.345'): como veio, a MESMA
      leitura do ``normalizar_numero_lancamento`` no caminho normal.

    O resto (a própria referência 'M-3-14511', prefixo desconhecido
    'X-9', texto comum) continua descartado: compô-lo é o que a rodada 4
    corrigiu ('RM-3-14511 M237').
    """
    numero, componivel = _numero_do_campo(texto)
    return numero if componivel else None
