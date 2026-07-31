# Plano de Refatoração D3 — Módulos

**Modelo:** Codex GPT-5.6-sol (xhigh reasoning)  
**Data:** 2026-07-31  
**Arquivo:** static/dominial/js/cadeia_dominial_d3.js (1482 linhas)

## 1. Premissas

- Responsabilidade única por arquivo
- Máximo de 249 linhas físicas por módulo, incluindo comentários
- Mesmas funções e variáveis globais
- Mesma ordem de renderização e animações
- Mesmos seletores, classes CSS, URLs e estruturas SVG
- Bootstrap carregado por último
- O monólito e os módulos nunca podem ser carregados simultaneamente

## 2. Observações encontradas no código atual

A estrutura real difere parcialmente do resumo inicial:

- As linhas 1321–1404 contêm o IIFE de impressão, não inicialização ou auto-fit
- A configuração do zoom está dentro do `DOMContentLoaded`
- `renderArvoreD3` também constrói a hierarquia e calcula o layout, além de renderizar
- Existem funções e variáveis atualmente sem uso aparente:
  - `centralizarArvoreInteligente`
  - `aplicarLayoutResponsivo`
  - `applyZoom`
  - `zoomStep`
  - resultado de `calcularEspacamentoAdaptativo`
- Existem quatro cálculos de bounds parecidos, mas não equivalentes:
  - `fitTreeToViewport`
  - `resetZoom`/`fimDaArvore`
  - impressão
  - exportação SVG

Essas duplicações e funções não utilizadas devem ser preservadas nesta refatoração. Limpeza e consolidação seriam uma mudança funcional separada.

## 3. Estrutura proposta

Diretório:

```text
static/dominial/js/cadeia_dominial_d3/
├── data.js
├── layout_spacing.js
├── layout.js
├── edges.js
├── cards.js
├── card_overlays.js
├── render.js
├── viewport_fit.js
├── zoom_controls.js
├── print.js
├── svg_export.js
└── bootstrap.js
```

### Lista de módulos

| Módulo | Linhas estimadas | Código atual | Responsabilidade |
|---|---:|---|---|
| `data.js` | 150–175 | L226–353 | Converter o grafo recebido do backend em hierarquia D3, escolher pai primário, impedir ciclos, criar conexões secundárias e ordenar filhos. |
| `layout_spacing.js` | 165–190 | L459–608 | Pós-processar posições: nível manual, fim de cadeia, sobreposições e espaçamento vertical. |
| `layout.js` | 210–235 | L355–457 e L689–790 | Criar `d3.hierarchy`, configurar `d3.tree`, calcular métricas, executar o pipeline de layout e retornar a raiz posicionada. |
| `edges.js` | 180–205 | L610–687 e L791–881 | Calcular paths e renderizar arestas principais e secundárias. |
| `cards.js` | 200–225 | L888–1067 | Criar grupos `.node`, retângulos, textos principais, tooltips e interações do card. |
| `card_overlays.js` | 120–145 | L1069–1171 | Adicionar badges, ícones de importação/compartilhamento e botão de novo lançamento. |
| `render.js` | 30–50 | Orquestração extraída de `renderArvoreD3` | Preservar `renderArvoreD3` como fachada: layout → arestas → cards → overlays. |
| `viewport_fit.js` | 110–125 | L4–105 | `debounce`, enquadramento automático e `expandirArvore`. |
| `zoom_controls.js` | 180–210 | L122–139 e L1174–1312 | Configurar zoom/pan, preencher os globais D3 e implementar zoom, reset e navegação para o fim. |
| `print.js` | 100–115 | L1314–1404 | Isolar e restaurar o estado durante `beforeprint`/`afterprint`. |
| `svg_export.js` | 90–105 | L1405–1482 | Clonar, normalizar, serializar e baixar a árvore como SVG. |
| `bootstrap.js` | 105–125 | L107–224, menos configuração do zoom | Inicializar a página, buscar os dados, mostrar indicadores, renderizar e disparar o auto-fit. |

O limite deve ser validado com `wc -l`. Se qualquer arquivo atingir 250 linhas, ele deve ser dividido antes do merge.

## 4. APIs internas extraídas

As novas funções auxiliares devem apenas mover blocos existentes:

```text
prepararLayoutArvore(data, width, height) → root
renderizarArestas(data, root, svgGroup)
renderizarCards(root, svgGroup) → seleção D3 de nodes
renderizarCardOverlays(node)
configurarZoom(svg, zoomGroup)
```

`renderArvoreD3` permanece disponível e passa a ser uma fachada:

```text
renderArvoreD3
  ├── prepararLayoutArvore
  ├── renderizarArestas
  ├── renderizarCards
  └── renderizarCardOverlays
```

A sequência é importante: arestas continuam sendo inseridas antes dos cards para permanecerem visualmente atrás deles.

## 5. Compatibilidade global

Os arquivos continuarão sendo scripts clássicos síncronos. Não adicionar `type="module"`, `async` ou `defer`.

Devem permanecer disponíveis:

### Entradas fornecidas pelo template

- `window.tisId`
- `window.imovelId`
- `window.imovelTipoDocumentoPrincipal`

### Estado D3

- `window._d3svg`
- `window._d3zoom`
- `window._zoomGroup`
- `window._zoomTransform`

### Callbacks usados pelo HTML

- `window.zoomIn`
- `window.zoomOut`
- `window.resetZoom`
- `window.fimDaArvore`
- `window.salvarArvoreSVG`
- `window.expandirArvore`

### Funções globais existentes

Para minimizar risco com testes, console ou código externo, manter também os nomes atuais:

- `debounce`
- `fitTreeToViewport`
- `ordenarFilhosPorNumeroDesc`
- `converterParaArvoreD3`
- `centralizarArvoreInteligente`
- `calcularEspacamentoAdaptativo`
- `aplicarLayoutResponsivo`
- `corrigirSobreposicoes`
- `ajustarPosicoesPorNivel`
- `aplicarEspacamentoAdicional`
- `customEdgePath`
- `renderArvoreD3`
- `applyZoom`

Não introduzir namespace ou alterar escopo nesta etapa. Isso mudaria a semântica global dos scripts clássicos.

## 6. Ordem de carregamento no template

Substituir o último `<script>` em `templates/dominial/cadeia_dominial_d3.html` por:

```html
<script src="https://d3js.org/d3.v7.min.js"></script>
<script>
    document.documentElement.classList.add("d3-active");

    window.tisId = {{ tis.id|safe }};
    window.imovelId = {{ imovel.id|safe }};
    window.imovelTipoDocumentoPrincipal =
        "{{ imovel.tipo_documento_principal }}";
</script>

<script src="{% static 'dominial/js/cadeia_dominial_d3/data.js' %}"></script>
<script src="{% static 'dominial/js/cadeia_dominial_d3/layout_spacing.js' %}"></script>
<script src="{% static 'dominial/js/cadeia_dominial_d3/layout.js' %}"></script>
<script src="{% static 'dominial/js/cadeia_dominial_d3/edges.js' %}"></script>
<script src="{% static 'dominial/js/cadeia_dominial_d3/cards.js' %}"></script>
<script src="{% static 'dominial/js/cadeia_dominial_d3/card_overlays.js' %}"></script>
<script src="{% static 'dominial/js/cadeia_dominial_d3/render.js' %}"></script>
<script src="{% static 'dominial/js/cadeia_dominial_d3/viewport_fit.js' %}"></script>
<script src="{% static 'dominial/js/cadeia_dominial_d3/zoom_controls.js' %}"></script>
<script src="{% static 'dominial/js/cadeia_dominial_d3/print.js' %}"></script>
<script src="{% static 'dominial/js/cadeia_dominial_d3/svg_export.js' %}"></script>
<script src="{% static 'dominial/js/cadeia_dominial_d3/bootstrap.js' %}"></script>
```

O monólito antigo deve ser removido da carga. Depois da validação, deve ser excluído para evitar duas fontes de verdade.

## 7. Dependências

| Módulo | Dependências |
|---|---|
| `data.js` | APIs nativas de JavaScript. |
| `layout_spacing.js` | Objetos de hierarquia recebidos por parâmetro. |
| `layout.js` | D3 e funções de `layout_spacing.js`. |
| `edges.js` | D3 e raiz já posicionada pelo layout. |
| `cards.js` | D3 e `window.tisId`/`window.imovelId` nos clicks. |
| `card_overlays.js` | D3 e IDs globais para o botão de lançamento. |
| `render.js` | `layout.js`, `edges.js`, `cards.js` e `card_overlays.js`. |
| `viewport_fit.js` | D3 e estado `_d3*`, disponível no momento da chamada. |
| `zoom_controls.js` | D3 e SVG criado pelo bootstrap. |
| `print.js` | D3 e estado `_d3*`, lido somente nos eventos de impressão. |
| `svg_export.js` | DOM, `XMLSerializer`, `Blob` e estado `_d3*`. |
| `bootstrap.js` | D3, dados, render, viewport e configuração do zoom. |

Embora `viewport_fit.js`, `print.js` e `svg_export.js` sejam avaliados antes da criação do SVG, eles só acessam o estado D3 quando suas funções ou eventos são executados.

## 8. Invariantes que não podem mudar

### Transformação do grafo

- Usar `doc.id` como identidade técnica; `numero` continua apenas como rótulo
- A raiz nunca recebe pai primário
- O pai primário continua sendo o citante que produz o caminho mais profundo
- `criariCiclo` permanece dentro da conversão
- Cada documento alcançável gera no máximo um card
- Citações não primárias continuam em `raiz.conexoesExtras`
- Matrículas continuam antes de transcrições; números em ordem decrescente

### Layout

- Ordem obrigatória:
  1. `treeLayout(root)`
  2. `ajustarPosicoesPorNivel`
  3. `corrigirSobreposicoes`
  4. `aplicarEspacamentoAdicional`
- Nó normal usa `node.depth`
- `nivel_manual` usa o nível recebido do backend
- Fim de cadeia continua usando `data.nivel`
- Preservar todos os valores `90`, `120`, `150`, `220` e demais constantes

### Arestas

- Saída pela direita da origem e entrada pela esquerda do destino
- Gap mínimo de avanço continua `24`
- Rotas reversas/coincidentes continuam usando bypass local
- Não reintroduzir roteamento baseado no bounding box global
- Arestas secundárias permanecem tracejadas e sem duplicação de cards

### Cards e interações

- Preservar ordem dos elementos SVG
- Preservar classes `.node`, `.link`, `.link-extra` e `.card-buttons`
- Preservar cores, bordas, badges, tooltips e durações
- Cards de fim de cadeia não navegam e não recebem botão `➕`
- Preservar exatamente as URLs de detalhe e novo lançamento

### Viewport, impressão e exportação

- Auto-fit continua dentro de `requestAnimationFrame`
- Nó único continua limitado a `1.5x`
- Impressão continua usando somente `viewBox` após zerar o transform D3
- `afterprint` restaura dimensões, `viewBox` e zoom
- Exportação opera sobre clone e não modifica o SVG visível
- Não consolidar os diferentes algoritmos de bounds nesta etapa

## 9. Sequência de implementação

1. Criar fixtures de regressão antes de mover código
2. Extrair `data.js`, `layout_spacing.js` e `viewport_fit.js` por blocos praticamente literais
3. Extrair o pipeline de layout para `layout.js`
4. Dividir a renderização em `edges.js`, `cards.js` e `card_overlays.js`
5. Reduzir `renderArvoreD3` à fachada em `render.js`
6. Mover configuração e controles para `zoom_controls.js`
7. Mover impressão e exportação sem compartilhar ou "melhorar" os cálculos
8. Criar `bootstrap.js` e mantê-lo como único `DOMContentLoaded`
9. Atualizar o template de forma atômica
10. Excluir o monólito somente após todos os módulos existirem
11. Executar verificação automatizada e regressão visual

Em nenhum commit intermediário o template deve carregar simultaneamente o monólito e os módulos.

## 10. Checklist de verificação

### Verificação estática

- [ ] Todos os módulos têm menos de 250 linhas
- [ ] `node --check` passa em cada arquivo
- [ ] Não há funções preexistentes duplicadas ou ausentes
- [ ] Existe apenas um `DOMContentLoaded`
- [ ] Existe apenas um registro de `beforeprint` e `afterprint`
- [ ] O template não referencia mais o monólito
- [ ] Todos os arquivos estáticos retornam HTTP 200
- [ ] Console sem `ReferenceError`, redeclarações ou erros de ordem
- [ ] `python manage.py check` passa
- [ ] Testes Django existentes passam
- [ ] `collectstatic --dry-run` encontra os 12 arquivos

### Regressão do grafo

- [ ] Árvore linear simples
- [ ] Um único documento
- [ ] Payload sem documentos, mantendo o comportamento atual
- [ ] DAG com documento citado por dois nós
- [ ] O card compartilhado aparece uma única vez
- [ ] O citante mais profundo vence como pai primário
- [ ] A outra citação aparece como aresta secundária
- [ ] Ciclo direto `A → B → A` termina sem `RangeError`
- [ ] Autocitação não entra em `children`
- [ ] Citação de retorno à raiz não transforma a raiz em filha
- [ ] Documentos com mesmo número e IDs diferentes continuam distintos
- [ ] Matrículas precedem transcrições
- [ ] Ordenação numérica decrescente permanece igual

### Regressão visual

- [ ] Contagem de `.node` igual à versão anterior
- [ ] Contagem de `.link` e `.link-extra` igual à versão anterior
- [ ] Cards sem sobreposição em árvores largas
- [ ] Arestas normais não atravessam os cards
- [ ] Arestas reversas usam bypass local
- [ ] Documentos importados e compartilhados mantêm badges e bordas
- [ ] Fim de cadeia mantém cor, posição e ausência do botão `➕`
- [ ] `nivel_manual` mantém a coluna escolhida
- [ ] Hover, tooltip e animações permanecem iguais
- [ ] Click no card abre o detalhe correto
- [ ] Click em `➕` abre o formulário correto

### Zoom e saída

- [ ] Auto-fit inicial ocorre depois da renderização
- [ ] Roda do mouse e pan funcionam
- [ ] Zoom `+` e `-` funcionam
- [ ] Reset mantém toda a árvore visível
- [ ] "Fim da Árvore" centraliza o último nível
- [ ] `expandirArvore()` continua acessível
- [ ] Imprimir após zoom/pan enquadra a árvore completa
- [ ] Fechar impressão restaura exatamente o zoom anterior
- [ ] Imprimir duas vezes não acumula `viewBox` ou transform
- [ ] SVG exportado contém árvore completa e não contém indicadores
- [ ] Exportar após zoom/pan não exporta o transform de viewport
- [ ] SVG com altura acima de 2000 mantém o limite atual
- [ ] Botão de salvar permanece desabilitado durante a carga e habilita no sucesso
- [ ] Erro de fetch mantém o botão desabilitado e apresenta a mensagem atual

## 11. Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Ordem incorreta dos scripts | Tags síncronas explícitas e `bootstrap.js` obrigatoriamente por último. |
| Monólito e módulos executados juntos | Troca atômica do template; nunca manter as duas referências. |
| Alteração involuntária dos fixes de DAG/ciclos | Mover `converterParaArvoreD3` inteiro para um único arquivo e validar fixtures de DAG, ciclos e IDs. |
| Mudança de ordem dos elementos SVG | Preservar links antes dos nodes e overlays depois do card base. |
| Perda do `this` nos callbacks D3 | Não trocar `function () {}` por arrow function em handlers que usam `this`. |
| Mudança nas closures | Manter estado de impressão no mesmo IIFE e estado de zoom no mesmo módulo. |
| Tentação de deduplicar bounds | Adiar; os quatro cálculos possuem semânticas diferentes. |
| Remoção de código aparentemente morto | Manter todas as funções, logs e variáveis nesta etapa. |
| Quebra dos callbacks inline do template | Preservar os nomes em `window` e testar cada botão. |
| Cache de estáticos | Os novos caminhos serão inicialmente frios; executar `collectstatic` antes de servir o template e não publicar versões parciais dos módulos. |
| Muitos requests JavaScript | Aceitável nesta fase; são arquivos pequenos e carregados via HTTP moderno. Bundling fica fora do escopo. |
| Ausência de suíte JS existente | Usar `node --check`, harness de fixtures para funções puras e comparação visual antes/depois. |

## 12. Critério de conclusão

A refatoração estará concluída quando:

- Os 12 módulos estiverem carregados na ordem definida
- Nenhum arquivo ultrapassar 249 linhas
- O monólito não for mais referenciado
- Todos os globais existentes permanecerem disponíveis
- Fixtures de duplicação, DAG, ciclos e bypass passarem
- A comparação visual, impressão e exportação forem equivalentes à versão anterior
