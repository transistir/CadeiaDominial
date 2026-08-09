// zoom_controls.js — Configuração do zoom/pan e controles de navegação
// (zoom in/out, reset, fim da árvore).

function configurarZoom(svg, zoomGroup) {
  // Comportamento de zoom/pan
  const zoom = d3
    .zoom()
    .scaleExtent([0.1, 3.0]) // Limites mais amplos para zoom
    .wheelDelta((event) => -event.deltaY * 0.002) // Velocidade do scroll
    .on("zoom", (event) => {
      zoomGroup.attr("transform", event.transform);
      // Atualizar transformação global
      window._zoomTransform = event.transform;
    });
  svg.call(zoom);

  // Guardar zoom para botões
  window._d3zoom = zoom;
  window._d3svg = svg;
  window._zoomGroup = zoomGroup;
  window._zoomTransform = d3.zoomIdentity;
  // Removido: svg.on('wheel.zoom', null); // Desabilitar zoom na roda do mouse se quiser

  return zoom;
}

// Controle de zoom para o SVG D3
let currentZoom = 1;
const minZoom = 0.1;
const maxZoom = 2.5;
const zoomStep = 0.2;

function applyZoom() {
  const svg = window._d3svg;
  const zoom = window._d3zoom;
  const t = window._zoomTransform.rescaleY
    ? window._zoomTransform
    : d3.zoomTransform(svg.node());
  svg
    .transition()
    .duration(200)
    .call(zoom.scaleBy, currentZoom / t.k);
}

window.zoomIn = function () {
  const svg = window._d3svg;
  const zoom = window._d3zoom;
  svg.transition().duration(200).call(zoom.scaleBy, 1.2);
  currentZoom = Math.min(currentZoom * 1.2, maxZoom);
};

window.zoomOut = function () {
  const svg = window._d3svg;
  const zoom = window._d3zoom;
  svg.transition().duration(200).call(zoom.scaleBy, 0.8);
  currentZoom = Math.max(currentZoom * 0.8, minZoom);
};

window.resetZoom = function () {
  const svg = window._d3svg;
  const zoomGroup = window._zoomGroup;
  const width = +svg.attr("width");
  const height = +svg.attr("height");

  // Pegar o bounding box do grupo de nós
  const nodes = zoomGroup.selectAll(".node");
  if (nodes.size() === 0) return;

  let minX = Infinity,
    maxX = -Infinity,
    minY = Infinity,
    maxY = -Infinity;
  nodes.each(function () {
    const bbox = this.getBBox();
    const x = +this.getAttribute("transform").split("(")[1].split(",")[0];
    const y = +this.getAttribute("transform").split(",")[1].split(")")[0];
    minX = Math.min(minX, x + bbox.x);
    maxX = Math.max(maxX, x + bbox.x + bbox.width);
    minY = Math.min(minY, y + bbox.y);
    maxY = Math.max(maxY, y + bbox.y + bbox.height);
  });

  // Adicionar margem extra para os cards
  minX -= 75;
  maxX += 75;
  minY -= 45;
  maxY += 45;

  const treeWidth = maxX - minX;
  const treeHeight = maxY - minY;

  // Calcular escala para caber TUDO na div com margem
  const scaleX = (width - 100) / treeWidth;
  const scaleY = (height - 100) / treeHeight;
  const finalScale = Math.min(scaleX, scaleY, 1); // Não aumentar além do tamanho original

  // Posicionar o primeiro card na extrema esquerda da div
  const tx = 50 - minX * finalScale; // Margem de 50px da esquerda
  const ty = (height - treeHeight * finalScale) / 2 - minY * finalScale; // Centralizar verticalmente

  console.log(
    `DEBUG: Reset - Árvore: ${treeWidth}x${treeHeight}, Container: ${width}x${height}, Escala: ${finalScale}`,
  );

  const t = d3.zoomIdentity.translate(tx, ty).scale(finalScale);
  svg.transition().duration(400).call(window._d3zoom.transform, t);
  window._zoomTransform = t;
  currentZoom = 1;
};

window.fimDaArvore = function () {
  const svg = window._d3svg;
  const zoomGroup = window._zoomGroup;
  const width = +svg.attr("width");
  const height = +svg.attr("height");

  // Pegar o bounding box do grupo de nós
  const nodes = zoomGroup.selectAll(".node");
  if (nodes.size() === 0) return;

  let minX = Infinity,
    maxX = -Infinity,
    minY = Infinity,
    maxY = -Infinity;
  const limitesNos = [];
  nodes.each(function () {
    const bbox = this.getBBox();
    const x = +this.getAttribute("transform").split("(")[1].split(",")[0];
    const y = +this.getAttribute("transform").split(",")[1].split(")")[0];
    const nodeMinX = x + bbox.x;
    const nodeMaxX = nodeMinX + bbox.width;
    minX = Math.min(minX, nodeMinX);
    maxX = Math.max(maxX, nodeMaxX);
    minY = Math.min(minY, y + bbox.y);
    maxY = Math.max(maxY, y + bbox.y + bbox.height);
    limitesNos.push({
      coluna: Math.round(x),
      minX: nodeMinX,
      maxX: nodeMaxX,
    });
  });

  const ultimaColuna = Math.max(...limitesNos.map((node) => node.coluna));
  const limitesUltimaColuna = limitesNos.filter(
    (node) => node.coluna === ultimaColuna,
  );
  const minXUltimaColuna =
    Math.min(...limitesUltimaColuna.map((node) => node.minX)) - 75;
  const maxXUltimaColuna =
    Math.max(...limitesUltimaColuna.map((node) => node.maxX)) + 75;

  // Adicionar margem extra para os cards
  minX -= 75;
  maxX += 75;
  minY -= 45;
  maxY += 45;

  const treeWidth = maxX - minX;
  const treeHeight = maxY - minY;

  // Calcular escala para focar no último nível (mais à direita)
  const ultimoNivelWidth = maxXUltimaColuna - minXUltimaColuna;
  const finalScale = Math.min(
    (width - 100) / ultimoNivelWidth,
    (height - 100) / treeHeight,
    2.0,
  ); // Escala maior para zoom

  // Posicionar o último nível no centro da div
  const centroUltimoNivel = (minXUltimaColuna + maxXUltimaColuna) / 2;
  const tx = width / 2 - centroUltimoNivel * finalScale;
  const ty = (height - treeHeight * finalScale) / 2 - minY * finalScale; // Centralizar verticalmente

  console.log(
    `DEBUG: Fim da Árvore - Último nível no centro, Escala: ${finalScale}`,
  );

  const t = d3.zoomIdentity.translate(tx, ty).scale(finalScale);
  svg.transition().duration(400).call(window._d3zoom.transform, t);
  window._zoomTransform = t;
  currentZoom = 1;
};
