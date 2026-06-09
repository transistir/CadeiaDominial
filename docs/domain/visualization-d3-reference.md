# Documentação Técnica: Visualização da Cadeia Dominial com D3.js

Esta documentação consolida a análise do fluxo de dados e a lógica de visualização da Cadeia Dominial, abrangendo desde a extração no backend até a renderização no frontend.

---

## 1. Visão Geral
O sistema de visualização transforma uma estrutura relacional de banco de dados (Matrículas e Transcrições) em um grafo hierárquico (árvore). Isso permite que o usuário rastreie a história de um imóvel através de seus antecessores (origens) e sucessores (destinos).

---

## 2. Fluxo de Dados (Backend)

O processamento principal ocorre na camada de serviços do Django, especificamente no `CadeiaDominialService`.

### A. Algoritmo de Extração Recursiva
Para montar a árvore, o backend realiza uma busca em duas direções a partir de um "Nó Raiz" (o imóvel selecionado):

1.  **Traversal Ascendente (Ancestrais):** Busca recursivamente as `origens` do imóvel para identificar de onde ele veio.
2.  **Traversal Descendente (Descendentes):** Busca recursivamente os `destinos` (subdivisões, desmembramentos) para onde o imóvel foi.

### B. Estrutura do JSON de Retorno
O backend fornece um JSON estruturado para ser consumido diretamente pelo `d3.hierarchy`.

```json
{
  "id": 10,
  "label": "M-123",
  "tipo": "MATRICULA",
  "metadata": {
    "cartorio": "1º Ofício",
    "area": "500m²",
    "status": "ATIVA"
  },
  "children": [
    {
      "id": 11,
      "label": "M-124",
      "tipo": "MATRICULA",
      "children": []
    }
  ],
  "parents": [
    {
      "id": 5,
      "label": "T-456",
      "tipo": "TRANSCRICAO"
    }
  ]
}
```

---

## 3. Lógica de Visualização (Frontend - D3.js)

O componente de visualização utiliza a biblioteca D3.js para criar um gráfico interativo.

### A. Componentes do D3 Utilizados
*   **d3.hierarchy:** Processa o JSON aninhado e calcula a estrutura de nós e links.
*   **d3.tree:** Define o layout da árvore (calcula coordenadas x, y para cada nó).
*   **d3.zoom:** Implementa funcionalidades de zoom e pan (arrastar).
*   **d3.linkHorizontal:** Gera as curvas de Bézier que conectam os imóveis.

### B. Implementação Técnica
A renderização segue estas etapas:

1.  **Inicialização do SVG:** Criação do container e aplicação do comportamento de zoom.
2.  **Cálculo do Layout:**
    ```javascript
    const root = d3.hierarchy(data);
    const treeLayout = d3.tree().nodeSize([50, 200]); // Espaçamento vertical e horizontal
    treeLayout(root);
    ```
3.  **Desenho dos Links (Conexões):**
    ```javascript
    svg.selectAll(".link")
      .data(root.links())
      .enter()
      .append("path")
      .attr("class", "link")
      .attr("d", d3.linkHorizontal()
        .x(d => d.y)
        .y(d => d.x));
    ```
4.  **Desenho dos Nós:** Cada nó é um grupo SVG (`<g>`) contendo um círculo (ou retângulo) e o texto identificador.

---

## 4. Análise de Performance e Problemas Identificados

De acordo com a análise técnica (`ANALISE_FLUXO_D3`), foram observados os seguintes pontos:

### Problemas Atuais
1.  **Recursividade Infinita:** Risco de loops caso haja erros de digitação nos dados (ex: Matrícula A aponta para B, e B aponta para A).
    *   *Solução:* Implementado um `visited_set` no backend e limite de profundidade.
2.  **Carga de Dados:** Chains muito longas (mais de 500 nós) podem tornar o SVG lento.
    *   *Solução:* Implementar renderização sob demanda (expand/collapse) ou Canvas para volumes massivos.
3.  **Complexidade Visual:** Cruzamento de linhas em casos de fusão de matrículas (múltiplos pais para um único filho).
    *   *Nota:* O `d3.tree` é otimizado para árvores simples. Grafos complexos (DAGs) exigem `d3-force` ou layouts customizados.

### Sugestões de Melhoria
*   **Destaque de Status:** Colorir nós de forma distinta para imóveis "Encerrados" vs "Ativos".
*   **Filtros Temporais:** Permitir visualizar a cadeia em um ponto específico no tempo.
*   **Mini-mapa:** Adicionar um navegador de canto para facilitar a localização em grandes diagramas.

---

## 5. Resumo do Fluxo de Execução

1.  **Usuário** solicita visualização de uma Matrícula.
2.  **View Django** recebe o ID e invoca o `CadeiaDominialService`.
3.  **Service** monta o grafo recursivamente consultando as tabelas de Origens/Destinos.
4.  **Frontend** recebe o JSON e limpa o container SVG.
5.  **D3.js** calcula as posições, desenha as curvas de conexão e os nós.
6.  **Interação:** O usuário pode clicar em um nó para ver detalhes no painel lateral ou expandir ramos ocultos.
