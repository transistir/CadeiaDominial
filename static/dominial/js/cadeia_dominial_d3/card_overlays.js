// card_overlays.js — Badges, ícones de importação/compartilhamento e
// botão de novo lançamento sobre os cards já renderizados.

function renderizarCardOverlays(node) {
  // Badge de documento importado (laranja)
  node
    .filter((d) => d.data.is_importado)
    .append("circle")
    .attr("cx", 55)
    .attr("cy", -25)
    .attr("r", 8)
    .attr("fill", "#ff8c00") // Laranja
    .attr("stroke", "white")
    .attr("stroke-width", 2)
    .attr("title", (d) => {
      let tooltip = d.data.tooltip_importacao || "Documento importado";
      if (d.data.cadeias_dominiais && d.data.cadeias_dominiais.length > 0) {
        tooltip += "\n\n🌐 Presente em múltiplas cadeias dominiais:";
        d.data.cadeias_dominiais.forEach((cadeia) => {
          tooltip += `\n• ${cadeia.imovel_matricula} (${cadeia.imovel_nome})`;
        });
      }
      return tooltip;
    });

  // Ícone de check para documentos importados
  node
    .filter((d) => d.data.is_importado)
    .append("text")
    .attr("x", 55)
    .attr("y", -21)
    .attr("text-anchor", "middle")
    .attr("fill", "white")
    .attr("font-size", 9)
    .attr("font-weight", "bold")
    .text("✓")
    .attr("title", (d) => {
      let tooltip = d.data.tooltip_importacao || "Documento importado";
      if (d.data.cadeias_dominiais && d.data.cadeias_dominiais.length > 0) {
        tooltip += "\n\n🌐 Presente em múltiplas cadeias dominiais:";
        d.data.cadeias_dominiais.forEach((cadeia) => {
          tooltip += `\n• ${cadeia.imovel_matricula} (${cadeia.imovel_nome})`;
        });
      }
      return tooltip;
    });

  // Badge de keyword de alerta (ATENÇÃO/PENDENTE)
  // Cores alinhadas com o sistema de alerta do app (lancamentos.css, etc.)
  const KEYWORD_CORES = {
    "alerta-atencao": "#fd7e14", // laranja (canônico)
    "alerta-pendente": "#ffc107", // amarelo (canônico)
  };

  const KEYWORD_LETRAS = {
    "alerta-atencao": "A",
    "alerta-pendente": "P",
  };

  // Círculo do badge
  node
    .filter(
      (d) =>
        d.data.keyword_encontrada &&
        d.data.keyword_encontrada.css_class,
    )
    .append("circle")
    .attr("cx", (d) =>
      d.data.is_importado || d.data.is_compartilhado ? 35 : 55,
    )
    .attr("cy", -25)
    .attr("r", 8)
    .attr(
      "fill",
      (d) =>
        KEYWORD_CORES[d.data.keyword_encontrada.css_class] || "#6c757d",
    )
    .attr("stroke", "white")
    .attr("stroke-width", 2)
    .attr(
      "title",
      (d) => `Keyword: ${d.data.keyword_encontrada.label}`,
    );

  // Letra dentro do badge
  node
    .filter(
      (d) =>
        d.data.keyword_encontrada &&
        d.data.keyword_encontrada.css_class,
    )
    .append("text")
    .attr("x", (d) =>
      d.data.is_importado || d.data.is_compartilhado ? 35 : 55,
    )
    .attr("y", -21)
    .attr("text-anchor", "middle")
    .attr("fill", "white")
    .attr("font-size", 9)
    .attr("font-weight", "bold")
    .text(
      (d) =>
        KEYWORD_LETRAS[d.data.keyword_encontrada.css_class] || "?",
    );

  // Badge de documento compartilhado (verde)
  node
    .filter((d) => d.data.is_compartilhado && !d.data.is_importado)
    .append("circle")
    .attr("cx", 55)
    .attr("cy", -25)
    .attr("r", 8)
    .attr("fill", "#28a745") // Verde
    .attr("stroke", "white")
    .attr("stroke-width", 2)
    .attr("title", (d) => {
      let tooltip = `Documento compartilhado\nCompartilhado em: ${d.data.imoveis_compartilhando.join(", ")}`;
      return tooltip;
    });

  // Ícone de compartilhamento para documentos compartilhados
  node
    .filter((d) => d.data.is_compartilhado && !d.data.is_importado)
    .append("text")
    .attr("x", 55)
    .attr("y", -21)
    .attr("text-anchor", "middle")
    .attr("fill", "white")
    .attr("font-size", 9)
    .attr("font-weight", "bold")
    .text("↔")
    .attr("title", (d) => {
      let tooltip = `Documento compartilhado\nCompartilhado em: ${d.data.imoveis_compartilhando.join(", ")}`;
      return tooltip;
    });

  // Botões SVG (não mostrar para cards de fim de cadeia)
  const btnGroup = node
    .filter((d) => !d.data.is_fim_cadeia)
    .append("g")
    .attr("class", "card-buttons")
    .attr("transform", "translate(0,35)");

  // ➕ Novo lançamento - Centralizado e com melhor contraste
  btnGroup
    .append("text")
    .attr("x", 0)
    .attr("y", 0)
    .attr("font-size", 14)
    .attr("cursor", "pointer")
    .attr("opacity", 0.9)
    .attr("text-anchor", "middle")
    .attr("fill", "white")
    .attr("font-weight", "bold")
    .text("➕")
    .on("click", (event, d) => {
      event.stopPropagation();
      window.location.href = `/dominial/tis/${window.tisId}/imovel/${window.imovelId}/novo-lancamento/${d.data.id}/`;
    })
    .on("mouseover", function () {
      d3.select(this).attr("opacity", 1).attr("font-size", 16);
    })
    .on("mouseout", function () {
      d3.select(this).attr("opacity", 0.9).attr("font-size", 14);
    });
}
