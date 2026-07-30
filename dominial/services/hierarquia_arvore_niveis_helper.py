"""Helper para recálculo de níveis da árvore hierárquica D3.

Extraído de ``hierarquia_arvore_service.py`` para manter o service abaixo
do limite de 400 linhas, permitindo a adição dos nós de fim de cadeia
(issue #85) sem inflar o arquivo principal.
"""

from collections import deque


def recalcular_niveis(arvore, documento_principal_id):
    """
    Recalcula níveis baseado na hierarquia real
    Mantém apenas conexões diretas pai-filho
    """
    # Mapear conexões diretas
    filhos_por_pai = {}  # pai -> [filhos]
    pais_por_filho = {}  # filho -> [pais]

    for conexao in arvore['conexoes']:
        filho = conexao['from']
        pai = conexao['to']

        if pai not in filhos_por_pai:
            filhos_por_pai[pai] = []
        filhos_por_pai[pai].append(filho)

        if filho not in pais_por_filho:
            pais_por_filho[filho] = []
        pais_por_filho[filho].append(pai)

    # Calcular níveis usando busca em largura a partir do documento principal
    niveis = {}
    fila = deque([(documento_principal_id, 0)])
    visitados = set()

    while fila:
        documento_id, nivel = fila.popleft()

        if documento_id in visitados:
            continue
        visitados.add(documento_id)

        niveis[documento_id] = nivel

        # Adicionar pais diretos à fila (nível + 1)
        if documento_id in pais_por_filho:
            for pai in pais_por_filho[documento_id]:
                if pai not in visitados:
                    fila.append((pai, nivel + 1))

    # Aplicar níveis aos documentos
    for doc_node in arvore['documentos']:
        nivel_calculado = niveis.get(doc_node['id'], 0)
        doc_node['nivel'] = doc_node['nivel_manual'] if doc_node['nivel_manual'] is not None else nivel_calculado

    # Calcular nível do fim de cadeia (nível máximo + 1)
    if arvore['documentos']:
        nivel_maximo = max(doc['nivel'] for doc in arvore['documentos'])
        nivel_fim_cadeia = nivel_maximo + 1

        # Aplicar nível do fim de cadeia aos nós de fim de cadeia
        for doc_node in arvore['documentos']:
            if doc_node.get('is_fim_cadeia'):
                doc_node['nivel'] = nivel_fim_cadeia
