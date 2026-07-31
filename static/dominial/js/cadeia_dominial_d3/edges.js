// edges.js — Edge routing e renderização das arestas principais e secundárias.
// Saída sempre pela DIREITA da origem, entrada sempre pela ESQUERDA do destino.

const EDGE_GEOMETRY = Object.freeze({
  nodeOffsetX: 120,
  nodeOffsetY: 20,
  cardHalfWidth: 75,
  minForwardGap: 24,
  minControlOffset: 16,
  maxControlOffset: 150,
  bypassExtraSpan: 200,
  maxBypassControlOffset: 200,
});

/**
 * Gera path SVG para aresta que:
 * - sai da borda DIREITA da origem
 * - entra na borda ESQUERDA do destino
 * - usa Bézier monotônica para rotas normais
 * - usa Bézier de bypass local para rotas reversas/coincidentes
 *   (sem depender do bounding box da árvore)
 */
function customEdgePath(source, target) {
  if (!source || !target) return "";
  const coords = [source.x, source.y, target.x, target.y];
  if (!coords.every(Number.isFinite)) return "";

  const sx =
    source.y + EDGE_GEOMETRY.nodeOffsetX + EDGE_GEOMETRY.cardHalfWidth;
  const sy = source.x + EDGE_GEOMETRY.nodeOffsetY;
  const tx =
    target.y + EDGE_GEOMETRY.nodeOffsetX - EDGE_GEOMETRY.cardHalfWidth;
  const ty = target.x + EDGE_GEOMETRY.nodeOffsetY;

  const forwardGap = tx - sx;
  const verticalDistance = Math.abs(ty - sy);
  const verticalFactor = Math.min(verticalDistance / 500, 1);

  // Rota normal: source está à esquerda do target.
  if (forwardGap >= EDGE_GEOMETRY.minForwardGap) {
    if (verticalDistance < 0.001) {
      return `M${sx},${sy} H${tx}`;
    }

    const controlRatio = 0.4 + verticalFactor * 0.1;
    const offset = Math.min(
      EDGE_GEOMETRY.maxControlOffset,
      forwardGap / 2,
      Math.max(EDGE_GEOMETRY.minControlOffset, forwardGap * controlRatio),
    );

    return [
      `M${sx},${sy}`,
      `C${sx + offset},${sy}`,
      `${tx - offset},${ty}`,
      `${tx},${ty}`,
    ].join(" ");
  }

  // Rota reversa/coincidente: bypass local.
  // Os controles avançam para a direita da origem e ficam à esquerda
  // do destino, sem depender do bounding box global da árvore.
  const bypassSpan =
    Math.abs(forwardGap) + EDGE_GEOMETRY.bypassExtraSpan;
  const bypassRatio = 0.4 + verticalFactor * 0.1;
  const offset = Math.min(
    EDGE_GEOMETRY.maxBypassControlOffset,
    bypassSpan * bypassRatio,
  );

  return [
    `M${sx},${sy}`,
    `C${sx + offset},${sy}`,
    `${tx - offset},${ty}`,
    `${tx},${ty}`,
  ].join(" ");
}

function renderizarArestas(data, root, svgGroup) {
  // Desenhar links da árvore principal com animações suaves
  const links = svgGroup
    .selectAll("path.link")
    .data(root.links(), (d) => d.target.data.id)
    .join("path")
    .attr("class", "link")
    .attr("fill", "none")
    .attr("stroke", "#28a745")
    .attr("stroke-width", 2)
    .attr("stroke-linecap", "round")
    .style("opacity", "0")
    .attr("d", (d) =>
      customEdgePath(d.source, d.target),
    )
    .on("mouseover", function (event, d) {
      d3.select(this)
        .transition()
        .duration(200)
        .style("stroke-width", "4")
        .style("opacity", "1");
    })
    .on("mouseout", function (event, d) {
      d3.select(this)
        .transition()
        .duration(200)
        .style("stroke-width", "2")
        .style("opacity", "0.8");
    });

  // Aplicar apenas transição de opacidade para links (sem mover posição)
  links
    .transition()
    .duration(600)
    .ease(d3.easeQuadInOut)
    .style("opacity", "0.8");

  // CORREÇÃO: Desenhar conexões extras (múltiplas conexões para o mesmo documento)
  if (data.conexoesExtras) {
    const nodesMap = new Map();
    root.descendants().forEach((node) => {
      nodesMap.set(node.data.id, node);
    });

    // Filtrar conexões que não estão na árvore principal
    const conexoesExtras = data.conexoesExtras.filter((con) => {
      const fromNode = nodesMap.get(con.from);
      const toNode = nodesMap.get(con.to);
      return fromNode && toNode;
    });

    // Desenhar conexões extras com estilo diferente e animações
    const linksExtras = svgGroup
      .selectAll("path.link-extra")
      .data(conexoesExtras, (d) => `${d.from}-${d.to}`)
      .join("path")
      .attr("class", "link-extra")
      .attr("fill", "none")
      .attr("stroke", "#6c757d") // Cor cinza para distinguir
      .attr("stroke-width", 2)
      .attr("stroke-dasharray", "5,5")
      .attr("stroke-linecap", "round")
      .style("opacity", "0")
      .attr("d", (d) => {
        const source = nodesMap.get(d.from);
        const target = nodesMap.get(d.to);
        return source && target
          ? customEdgePath(source, target)
          : "";
      })
      .on("mouseover", function (event, d) {
        d3.select(this)
          .transition()
          .duration(200)
          .style("stroke-width", "3")
          .style("opacity", "1");
      })
      .on("mouseout", function (event, d) {
        d3.select(this)
          .transition()
          .duration(200)
          .style("stroke-width", "2")
          .style("opacity", "0.6");
      });

    // Aplicar apenas transição de opacidade para links extras (sem mover posição)
    linksExtras
      .transition()
      .duration(600)
      .ease(d3.easeQuadInOut)
      .style("opacity", "0.6");
  }

  // CORREÇÃO: Remover lógica de criação de linhas de fim de cadeia
  // As conexões de fim de cadeia já são criadas pelo backend e processadas
  // pelas conexões extras (link-extra) com tipo 'fim_cadeia'
  // Não precisamos criar linhas adicionais baseadas em documento_origem_id
}
