// bootstrap.js — Inicializa a página, busca os dados, mostra indicadores,
// renderiza e dispara o auto-fit. Carregado por último.

document.addEventListener("DOMContentLoaded", function () {
  const svg = d3.select("#arvore-d3-svg");
  const containerWidth =
    document.getElementById("arvore-d3-svg").clientWidth || 1000;
  const width = Math.max(containerWidth, 2000); // Permitir largura maior para árvores extensas
  // Altura dinâmica: usar 80% da viewport height, mínimo 500px
  const height = Math.max(500, window.innerHeight * 0.8);
  svg.attr("width", width).attr("height", height);

  // Limpar SVG
  svg.selectAll("*").remove();

  // Grupo para zoom/pan
  const zoomGroup = svg.append("g").attr("id", "zoom-group");

  // Configurar zoom/pan e preencher globais D3
  configurarZoom(svg, zoomGroup);

  // Adicionar indicador de carregamento
  const loadingIndicator = svg
    .append("text")
    .attr("x", width / 2)
    .attr("y", height / 2)
    .attr("text-anchor", "middle")
    .style("fill", "#6c757d")
    .style("font-size", "16px")
    .text("Carregando árvore...");

  // Buscar dados da árvore (corrigido)
  const timestamp = new Date().getTime();
  fetch(
    `/dominial/cadeia-dominial/${window.tisId}/${window.imovelId}/arvore/?t=${timestamp}`,
  )
    .then((response) => response.json())
    .then((data) => {
      // Remover indicador de carregamento
      loadingIndicator.remove();

      // Adicionar indicador de processamento
      const processingIndicator = svg
        .append("text")
        .attr("x", width / 2)
        .attr("y", height / 2)
        .attr("text-anchor", "middle")
        .style("fill", "#17a2b8")
        .style("font-size", "14px")
        .text("Processando dados...");

      // Converter para formato de árvore
      const arvore = converterParaArvoreD3(data);

      // Remover indicador de processamento
      processingIndicator.remove();

      renderArvoreD3(arvore, zoomGroup, width, height);

      // Adicionar indicador de sucesso temporário
      const successIndicator = svg
        .append("text")
        .attr("x", 20)
        .attr("y", 30)
        .attr("text-anchor", "start")
        .style("fill", "#28a745")
        .style("font-size", "12px")
        .style("opacity", "0")
        .text("✓ Árvore carregada com sucesso");

      successIndicator
        .transition()
        .duration(500)
        .style("opacity", "1")
        .transition()
        .delay(2000)
        .duration(500)
        .style("opacity", "0")
        .remove();

      // Enquadrar após renderizar (usa requestAnimationFrame,
      // não setTimeout frágil)
      requestAnimationFrame(() => {
        fitTreeToViewport();
      });

      // Habilitar botão de salvar SVG (estava disabled durante carga)
      const btnSalvar = document.getElementById("btn-salvar-svg");
      if (btnSalvar) {
        btnSalvar.disabled = false;
        btnSalvar.style.opacity = "1";
        btnSalvar.style.cursor = "pointer";
      }
    })
    .catch((err) => {
      loadingIndicator.remove();
      svg
        .append("text")
        .attr("x", width / 2)
        .attr("y", height / 2)
        .attr("text-anchor", "middle")
        .style("fill", "#dc3545")
        .text("Erro ao carregar árvore: " + err.message);
    });
});
