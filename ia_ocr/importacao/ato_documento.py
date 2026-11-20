"""Tipo e número do ato: rótulo efetivo × tipo_sugerido (#322).

A duplicata do ato (``_lancamento_duplicado``/``_existente``/``_url_lancamento``)
servia ao motor em lote e ao ``resumo`` — aposentados na fase 4 da #341; a
colisão agora é do service manual (``LancamentoDuplicataService``).
"""
import re

from dominial.models import LancamentoTipo

from .. import revisao
from ..rotulos import (
    analisar_rotulo, compor_numero_lancamento, normalizar_numero_lancamento,
    resolver_tipo,
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
