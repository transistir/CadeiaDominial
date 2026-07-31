/* ── Salvar SVG do Organograma Completo ── */
window.salvarArvoreSVG = function () {
  const svg = window._d3svg;
  if (!svg || !window._zoomGroup) return;

  // Calcular bounds a partir das posições reais dos nós
  const nodes = window._zoomGroup.selectAll(".node");
  if (nodes.size() === 0) return;

  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  nodes.each(function () {
    const t = this.getAttribute("transform");
    const m = t && t.match(/translate\(([^,]+),([^)]+)\)/);
    if (m) {
      const x = parseFloat(m[1]), y = parseFloat(m[2]);
      if (isFinite(x) && isFinite(y)) {
        minX = Math.min(minX, x - 75);
        maxX = Math.max(maxX, x + 75);
        minY = Math.min(minY, y - 45);
        maxY = Math.max(maxY, y + 45);
      }
    }
  });
  if (!isFinite(minX)) return;

  const extraMargin = 40;
  const w = maxX - minX + 2 * extraMargin;
  const h = maxY - minY + 2 * extraMargin;

  // Clonar o SVG para não interferir na visualização atual
  const svgNode = svg.node();
  const clone = svgNode.cloneNode(true);

  // Remover indicadores temporários adicionados diretamente ao SVG
  clone.querySelectorAll(":scope > text").forEach((text) => text.remove());

  // Encontrar e limpar transform da zoomGroup no clone
  const zoomGroupClone = clone.querySelector('#zoom-group, [id="zoom-group"]');
  if (zoomGroupClone) {
    zoomGroupClone.removeAttribute('transform');
  }

  // Embedar estilos essenciais que vêm do CSS externo
  const styleEl = document.createElementNS("http://www.w3.org/2000/svg", "style");
  styleEl.textContent = [
    ".link { fill: none; stroke: #28a745; stroke-width: 2; }",
    ".link-extra { fill: none; stroke: #28a745; stroke-width: 2; stroke-dasharray: 5,5; }",
    ".card-buttons text { filter: drop-shadow(0 1px 2px rgba(0,0,0,0.3)); }",
  ].join("\n");
  clone.insertBefore(styleEl, clone.firstChild);

  // Aplicar viewBox e dimensões fixas no clone
  clone.setAttribute("viewBox", `${minX - extraMargin} ${minY - extraMargin} ${w} ${h}`);
  clone.setAttribute("width", w);
  clone.setAttribute("height", h);
  clone.removeAttribute("style");

  // Se o SVG ficar muito grande, limitar altura e usar preserveAspectRatio
  if (h > 2000) {
    clone.setAttribute('height', '2000');
    clone.setAttribute('preserveAspectRatio', 'xMidYMin meet');
  }

  // Serializar
  const serializer = new XMLSerializer();
  const svgString = serializer.serializeToString(clone);

  // Download
  const blob = new Blob([svgString], { type: "image/svg+xml" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `cadeia-dominial-${new Date().toISOString().slice(0, 10)}.svg`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
};
