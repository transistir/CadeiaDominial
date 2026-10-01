// viewport_fit.js — debounce, enquadramento automático e expandirArvore.

// Função de debouncing para melhorar performance
function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

// ========================================================
// fitTreeToViewport — função única de enquadramento da árvore
// ========================================================
// Substitui as antigas enquadrarArvoreNoSVG, expandirArvore e
// centralizarArvore. Usa requestAnimationFrame internamente
// quando chamada sem options.animate.
//
// Edge cases tratados:
//   - Árvore vazia (sem nós) → retorna sem erro
//   - Nó único → limita zoom máximo a 1.5x
//   - Árvore muito grande → aplica zoom out mínimo (0.1)
//   - Erro de fetch → nunca chamada (catch não tenta fit)
// ========================================================
function fitTreeToViewport(options = {}) {
  const svg = window._d3svg;
  const zoomGroup = window._zoomGroup;
  if (!svg || !zoomGroup) return;

  const svgNode = svg.node();
  if (!svgNode) return;

  // Dimensões reais do container via getBoundingClientRect
  const rect = svgNode.getBoundingClientRect();
  const width = (rect.width > 0 ? rect.width : +svg.attr("width")) || 1000;
  const height = (rect.height > 0 ? rect.height : +svg.attr("height")) || 600;

  const nodes = zoomGroup.selectAll(".node");
  if (nodes.size() === 0) return;

  // Calcular bounding box de todos os nós
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  nodes.each(function () {
    const transform = this.getAttribute("transform");
    const match = transform && transform.match(/translate\(([^,]+),([^)]+)\)/);
    if (match) {
      const x = parseFloat(match[1]);
      const y = parseFloat(match[2]);
      // Cards têm 150x90 px — considerar bounding box completo
      minX = Math.min(minX, x - 75);
      maxX = Math.max(maxX, x + 75);
      minY = Math.min(minY, y - 45);
      maxY = Math.max(maxY, y + 45);
    }
  });

  // Edge case: nenhum nó com posição válida
  if (!isFinite(minX)) return;

  const treeWidth = maxX - minX;
  const treeHeight = maxY - minY;

  const minScale = options.minScale ?? 0.1;
  const maxScale = options.maxScale ?? 3.0;
  const margin = options.margin ?? 60;

  let scale = Math.min(
    (width - 2 * margin) / treeWidth,
    (height - 2 * margin) / treeHeight,
  );

  // Edge case: nó único — não aplicar zoom extremo
  if (nodes.size() === 1) {
    scale = Math.min(scale, 1.5);
  }

  // Edge case: árvore muito grande — respeitar zoom mínimo
  scale = Math.max(scale, minScale);
  scale = Math.min(scale, maxScale);

  const tx = (width - treeWidth * scale) / 2 - minX * scale;
  const ty = (height - treeHeight * scale) / 2 - minY * scale;

  const t = d3.zoomIdentity.translate(tx, ty).scale(scale);
  window._zoomTransform = t;

  const duration = options.duration ?? 400;
  if (options.animate !== false) {
    svg.transition().duration(duration).call(window._d3zoom.transform, t);
  } else {
    svg.call(window._d3zoom.transform, t);
  }

  return { scale, tx, ty, minX, minY, maxX, maxY };
}

// Botão "Expandir Árvore" — debounced para evitar múltiplas chamadas
window.expandirArvore = debounce(function () {
  fitTreeToViewport();
}, 300);
