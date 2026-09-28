"""
Utilitários para operações com cartórios.

Issue #227: Helper compartilhado para filtrar CRI (Cartórios de Registro de Imóveis)
por padrão de nome. Usado por cartorio_autocomplete (com somente_cri=true) e
cartorio_imoveis_autocomplete.

O filtro é por NOME (não por campo tipo) porque o campo `tipo` não é confiável
até a issue #150 ser resolvida.

É um filtro de INCLUSÃO por termos de imóveis, não de exclusão por
"tabelionato/notas". Serventias mistas como "Serviço de Registro de Imóveis,
Títulos e Documentos… e Tabelionato de Protestos" são CRI.

NOTA: icontains é sensível a acento em SQLite (UPPER ASCII-only). A lista
inclui ambas as grafias (com e sem acento) para cobrir o máximo de casos.
Maiúsculas com acento (CARTÓRIO) não casam em SQLite; isso é coberto no QA
em Postgres (T5 do plano).

As cópias do mesmo filtro em api_views.buscar_cidades/buscar_cartorios devem
ficar em sincronia (follow-up).
"""
from django.db.models import Q


def q_nome_cri():
    """
    Retorna um Q object que filtra cartórios CRI por padrão de nome.

    Critério de inclusão (icontains, case-insensitive onde o banco suporta):
    - 'imovel' / 'imoveis' (sem acento)
    - 'imóveis' (com acento)
    - 'imobiliario' / 'imobiliária'
    - 'Registro de Imóveis' (frase completa, captura variações compostas)

    Devolve um Q novo a cada chamada (Q objects não são thread-safe para
    composição incremental).

    Com order_by('nome', 'id'), garante ordem determinística mesmo com nomes
    duplicados em dados reais.
    """
    return (
        Q(nome__icontains='imovel') |
        Q(nome__icontains='imoveis') |
        Q(nome__icontains='imóveis') |
        Q(nome__icontains='imobiliario') |
        Q(nome__icontains='imobiliária') |
        Q(nome__icontains='Registro de Imóveis')
    )
