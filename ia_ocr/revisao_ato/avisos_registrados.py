"""Snapshot dos avisos informativos do ato para correção posterior (#332).

"Importar e corrigir depois": o painel da edição do lançamento precisa do que
o revisor viu na revisão. Recalcular na hora seria instável (o descarte da área
não fica na linha, o prefill depende do cadastro atual e excluir o PDF apaga a
extração), então o conjunto é gravado em ``ImportacaoIA.avisos`` no MESMO
momento da importação.

Só entram avisos INFORMATIVOS e só ``motivo/rotulo/texto``: nada de CPF/RG,
nomes de partes ou chave de linha (``/acts/...``).
"""

from .. import formulario
from ..models import ImportacaoIA
from .banner import MOTIVO_AREA_DESCARTADA, avisos_do_formulario

# Texto fixo por motivo que interpolava texto livre do OCR (forma, título,
# datas). O banner continua detalhado; o snapshot persistido, não: CPF/nome
# no campo errado não podem virar histórico.
TEXTO_CONTROLADO = {
    'forma_ajustada_vocabulario': (
        'Forma lida ajustada ao vocabulário; confira o valor antes de salvar.'
    ),
    'forma_titulo_reinterpretados': (
        'Forma e título foram reinterpretados; confira os dois campos.'
    ),
    'data_transacao_do_instrumento': (
        'Data da transação derivada do instrumento; confira o valor.'
    ),
}


def avisos_para_registrar(extracao, indice, documento, post):
    """Avisos informativos do ato ``indice`` + o descarte explícito da área.

    Chamar ANTES do service: ele escreve livro/folha no ``documento`` em
    memória. Sem ato (índice descartado no meio do caminho), devolve vazio.
    """
    indice = int(indice)
    try:
        prefill = formulario.prefill_do_ato(extracao, indice, documento)
    except formulario.AtoInexistente:
        return []
    avisos = avisos_do_formulario(prefill, extracao, indice, post=post)
    if (
        post.get('descartar_area') == '1'
        and not (post.get('area') or '').strip()
    ):
        area = next(
            (item for item in prefill.get('pendencias', ())
             if item['motivo'] == 'unidade_area'),
            None,
        )
        if area is not None:
            avisos.append({
                'motivo': MOTIVO_AREA_DESCARTADA,
                'rotulo': area.get('rotulo', ''),
                'texto': area.get('rotulo_descarte', ''),
            })
    return [_somente_texto(aviso) for aviso in avisos]


def avisos_do_lancamento(lancamento):
    """Avisos gravados na importação assistida do lançamento; ``[]`` sem eles.

    Lê só o banco: sobrevive à exclusão do PDF (as FKs do vínculo são
    ``SET_NULL``) e não recalcula nada.
    """
    if lancamento is None or lancamento.pk is None:
        return []
    avisos = ImportacaoIA.objects.filter(
        modelo='Lancamento', objeto_id=lancamento.pk,
    ).values_list('avisos', flat=True).first()
    return list(avisos or [])


def _somente_texto(aviso):
    motivo = aviso.get('motivo')
    return {
        'motivo': motivo or '',
        'rotulo': aviso.get('rotulo') or '',
        'texto': TEXTO_CONTROLADO.get(motivo, aviso.get('texto') or ''),
    }
