// print.js — IMPRESSÃO (#49) — beforeprint / afterprint
// CUIDADO: Greptile T-Rex reproduziu 2 bugs na implementação anterior:
//   (a) fitTreeToViewport aplica zoom transform + viewBox juntos → árvore em 8.7%×11.5%
//   (b) width="100%" no beforeprint quebra zoom no afterprint (NaN)
// Fix: usar SÓ viewBox (limpar transform d3 primeiro), restaurar dimensões no afterprint.
(function () {
  let _printSavedTransform = null;
  let _printSavedWidth = null;
  let _printSavedHeight = null;
  let _printSavedViewBox = null;

  window.addEventListener("beforeprint", () => {
    const svg = window._d3svg;
    if (!svg || !window._zoomGroup) return;

    // Salvar estado atual
    _printSavedTransform = window._zoomTransform;
    _printSavedWidth = svg.attr("width");
    _printSavedHeight = svg.attr("height");

    // Calcular bounds da árvore a partir das posições reais dos nós
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

    // Salvar viewBox original ANTES de resetar
    const svgNode = svg.node();
    _printSavedViewBox = svgNode.getAttribute("viewBox");

    // Interromper transições ativas para evitar reaplicação de transform
    svg.interrupt();

    // Resetar zoom d3 — viewBox será o ÚNICO mecanismo de enquadramento
    svg.call(window._d3zoom.transform, d3.zoomIdentity);
    window._zoomTransform = d3.zoomIdentity;

    // Aplicar viewBox para capturar a árvore inteira
    const extraMargin = 40;
    svgNode.setAttribute("viewBox", [
      minX - extraMargin, minY - extraMargin,
      maxX - minX + 2 * extraMargin, maxY - minY + 2 * extraMargin,
    ].join(" "));
    // NÃO sobrescrever width/height — CSS @media print cuida do layout
  });

  window.addEventListener("afterprint", () => {
    const svg = window._d3svg;
    if (!svg) return;

    // Remover viewBox ou restaurar original
    const svgNode = svg.node();
    if (svgNode) {
      if (_printSavedViewBox != null) {
        svgNode.setAttribute("viewBox", _printSavedViewBox);
      } else {
        svgNode.removeAttribute("viewBox");
      }
      // Restaurar dimensões originais para d3 zoom funcionar
      if (_printSavedWidth != null) svgNode.setAttribute("width", _printSavedWidth);
      if (_printSavedHeight != null) svgNode.setAttribute("height", _printSavedHeight);
    }

    // Restaurar zoom
    if (_printSavedTransform) {
      svg.call(window._d3zoom.transform, _printSavedTransform);
      window._zoomTransform = _printSavedTransform;
      _printSavedTransform = null;
      _printSavedWidth = null;
      _printSavedHeight = null;
      _printSavedViewBox = null;
    }
  });
})();
