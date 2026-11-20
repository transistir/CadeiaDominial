"""Testes do parser de rótulos de lançamento (I-11b / #322).

As regras vêm da decisão do cliente (Hiure, 09/11): lançamento SEMPRE
começa com ``R`` (registro) ou ``Av`` (averbação); ``M`` é número de
matrícula — rótulo válido, mas nunca um lançamento; ``"R: 1-237"`` traz
número de ato ``1`` e matrícula ``237``, e o texto depois do carimbo é
ignorado. ``classificar_atos`` consome o payload da extração
(``document`` + ``acts``) e devolve o cabeçalho do início de matrícula,
os lançamentos em ordem REVERSA e os rótulos não reconhecidos.
"""


def _campo(normalized=None, raw=None):
    """Campo de valor A3 no formato mínimo que o parser lê."""
    return {'raw': raw, 'normalized': normalized}


def _ato(ordem, rotulo, tipo_sugerido=None, **extras):
    """Ato A3 mínimo: rótulo + tipo_sugerido + data.

    Sem tipo explícito, o sugerido acompanha o prefixo do rótulo (a roda
    que o serviço real acerta no dia a dia).
    """
    if tipo_sugerido is None:
        tipo_sugerido = 'averbacao' if rotulo[:2].lower() == 'av' else 'registro'
    ato = {
        'ordem': ordem,
        'rotulo': _campo(rotulo, rotulo),
        'tipo_sugerido': _campo(tipo_sugerido, rotulo),
        'data': _campo('2020-02-15', '15 de fevereiro de 2020'),
        'partes': [],
    }
    ato.update(extras)
    return ato


# Payload real: campos críticos do cabeçalho chegam com ``normalized=None``
# e o texto de OCR no ``raw`` (extração id 10, umbelino-extracao-v1.1).
DOCUMENTO_REAL = {
    'tipo': _campo('matricula', 'Matrícula'),
    'numero': _campo(None, '42.718'),
    'livro': _campo('2-RG', 'Livro 2-RG'),
    'cartorio': _campo(None, 'CRI de Itamaraju'),
    'area': _campo(None, '12,5 ha'),
    'data': _campo(None, '06 de maio de 2002'),
    'imovel_descricao': _campo(None, 'O imóvel rural denominado Sítio Boa Vista'),
}




class RotulosBase:
    """Base comum mantida por último na MRO das fachadas."""
