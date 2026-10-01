// render.js — renderArvoreD3 como fachada: layout → arestas → cards → overlays.
// A ordem importa: arestas são inseridas antes dos cards para permanecerem
// visualmente atrás deles.

function renderArvoreD3(data, svgGroup, width, height) {
  const root = prepararLayoutArvore(data, width, height);
  renderizarArestas(data, root, svgGroup);
  const node = renderizarCards(root, svgGroup);
  renderizarCardOverlays(node);
  window._d3root = root;
  return { root, node };
}
