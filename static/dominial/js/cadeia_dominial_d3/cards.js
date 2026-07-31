// cards.js — Grupos .node, retângulos, textos principais, tooltips e
// interações do card.

function renderizarCards(root, svgGroup) {
  // Desenhar nós (cards) com animações suaves
  const node = svgGroup
    .selectAll("g.node")
    .data(root.descendants(), (d) => d.data.id)
    .join("g")
    .attr("class", "node")
    .style("cursor", "pointer")
    .attr("transform", (d) => `translate(${d.y + 120},${d.x + 20})`) // Posicionar imediatamente
    .style("opacity", "0") // Começar invisível para animação de entrada
    .on("mouseover", function (event, d) {
      // Destacar o nó atual
      d3.select(this)
        .select("rect")
        .transition()
        .duration(200)
        .attr("stroke-width", 4)
        .attr("filter", "drop-shadow(0 8px 25px rgba(0,0,0,0.3))");
    })
    .on("mouseout", function (event, d) {
      // Restaurar o nó
      d3.select(this)
        .select("rect")
        .transition()
        .duration(200)
        .attr("stroke-width", (d) =>
          d.data.is_importado || d.data.is_compartilhado ? 3 : 2,
        )
        .attr("filter", "drop-shadow(0 2px 8px rgba(0,0,0,0.10))");
    });

  // Aplicar apenas transição de opacidade (sem mover posição)
  node.transition().duration(600).ease(d3.easeQuadInOut).style("opacity", "1");

  // Card base
  node
    .append("rect")
    .attr("width", 150)
    .attr("height", 90)
    .attr("x", -75)
    .attr("y", -45)
    .attr("rx", 12)
    .attr("fill", (d) => {
      // Cards especiais de fim de cadeia
      if (d.data.is_fim_cadeia) {
        if (d.data.classificacao_fim_cadeia === "origem_lidima") {
          return "#28a745"; // Verde para origem lídima
        } else if (d.data.classificacao_fim_cadeia === "inconclusa") {
          return "#ffc107"; // Amarelo para situação inconclusa
        } else {
          return "#dc3545"; // Vermelho para sem origem
        }
      } else if (d.data.tipo_documento === "transcricao") {
        return "#6f42c1"; // Roxo para transcrição
      } else {
        return "#007bff"; // Azul para matrícula
      }
    })
    .attr("stroke", (d) => {
      // Cards especiais de fim de cadeia
      if (d.data.is_fim_cadeia) {
        if (d.data.classificacao_fim_cadeia === "origem_lidima") {
          return "#1e7e34"; // Verde escuro para origem lídima
        } else if (d.data.classificacao_fim_cadeia === "inconclusa") {
          return "#e0a800"; // Amarelo escuro para situação inconclusa
        } else {
          return "#b02a37"; // Vermelho escuro para sem origem
        }
      }
      // Documentos importados têm borda laranja tracejada
      if (d.data.is_importado) {
        return "#ff8c00"; // Laranja
      }
      // Documentos compartilhados têm borda verde tracejada
      if (d.data.is_compartilhado) {
        return "#28a745"; // Verde
      }
      if (d.data.tipo_documento === "transcricao") {
        return "#5a32a3"; // Roxo escuro para transcrição
      } else {
        return "#0056b3"; // Azul escuro para matrícula
      }
    })
    .attr("stroke-width", (d) =>
      d.data.is_importado || d.data.is_compartilhado ? 3 : 2,
    )
    .attr("stroke-dasharray", (d) => {
      // Bordas tracejadas para documentos importados e compartilhados
      if (d.data.is_importado || d.data.is_compartilhado) {
        return "5,5"; // Padrão tracejado
      }
      return "none"; // Linha sólida
    })
    .attr("filter", "drop-shadow(0 2px 8px rgba(0,0,0,0.10))")
    .attr("title", (d) => {
      // Tooltip especial para cards de fim de cadeia
      if (d.data.is_fim_cadeia) {
        let tipo = "";
        if (
          d.data.tipo_fim_cadeia === "destacamento_publico" &&
          d.data.sigla_patrimonio_publico
        ) {
          tipo = `Destacamento Público: ${d.data.sigla_patrimonio_publico}`;
        } else if (d.data.tipo_fim_cadeia === "outra") {
          tipo = "Outra Origem";
        } else if (d.data.tipo_fim_cadeia === "sem_origem") {
          tipo = "Sem Origem";
        } else {
          tipo = "Tipo não classificado";
        }

        let classificacao = "";
        if (d.data.classificacao_fim_cadeia === "origem_lidima") {
          classificacao = "Origem Lídima";
        } else if (d.data.classificacao_fim_cadeia === "sem_origem") {
          classificacao = "Sem Origem";
        } else if (d.data.classificacao_fim_cadeia === "inconclusa") {
          classificacao = "Situação Inconclusa";
        }

        return `Fim de Cadeia\nTipo: ${tipo}\nClassificação: ${classificacao}\n\nVisualização organizada exclusivamente a partir dos dados cadastrados. Não constitui parecer jurídico nem validação registral.`;
      }

      // Tooltip normal para documentos
      return `${d.data.tipo_display} ${d.data.numero}\n${d.data.cartorio}\nLivro: ${d.data.livro}, Folha: ${d.data.folha}\nData: ${d.data.data}\n${d.data.total_lancamentos} lançamentos`;
    })
    .on("mouseover", function () {
      d3.select(this)
        .transition()
        .duration(120)
        .attr("stroke-width", 3)
        .attr("filter", "drop-shadow(0 6px 20px rgba(0,0,0,0.25))")
        .attr("transform", "scale(1.06)");
    })
    .on("mouseout", function () {
      d3.select(this)
        .transition()
        .duration(120)
        .attr("stroke-width", 2)
        .attr("filter", "drop-shadow(0 2px 8px rgba(0,0,0,0.10))")
        .attr("transform", "scale(1)");
    })
    .on("click", (event, d) => {
      event.stopPropagation();
      // Cards de fim de cadeia não redirecionam
      if (d.data.is_fim_cadeia) return;
      
      // Disparar evento customizado para permitir interceptação (ex: painel lateral)
      const customEvent = new CustomEvent("d3:node-click", {
        detail: { node: d, event: event },
        bubbles: true,
        cancelable: true
      });
      const allowed = window.dispatchEvent(customEvent);
      
      // Se o evento foi cancelado (preventDefault), não navegar
      if (!allowed) return;
      
      window.location.href = `/dominial/tis/${window.tisId}/imovel/${window.imovelId}/documento/${d.data.id}/detalhado/`;
    });

  // Número do documento
  node
    .append("text")
    .attr("text-anchor", "middle")
    .attr("y", -6)
    .attr("fill", "white")
    .attr("font-size", 15)
    .attr("font-weight", 700)
    .text((d) => {
      // Cards especiais de fim de cadeia
      if (d.data.is_fim_cadeia) {
        return d.data.numero || "FIM";
      }
      // Se for destacamento público e tiver sigla, exibir a sigla
      if (
        d.data.sigla_patrimonio_publico &&
        d.data.sigla_patrimonio_publico.trim()
      ) {
        return d.data.sigla_patrimonio_publico;
      }
      return d.data.numero || d.data.name || "";
    });

  // Total de lançamentos (não mostrar para cards de fim de cadeia)
  node
    .filter((d) => !d.data.is_fim_cadeia)
    .append("text")
    .attr("text-anchor", "middle")
    .attr("y", 14)
    .attr("fill", "white")
    .attr("font-size", 10)
    .attr("opacity", 0.7)
    .text((d) =>
      d.data.total_lancamentos !== undefined
        ? `${d.data.total_lancamentos} lançamentos`
        : "",
    );

  return node;
}
