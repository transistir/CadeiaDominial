// layout_spacing.js — Pós-processamento de posições: nível manual,
// fim de cadeia, sobreposições e espaçamento vertical adicional.

// Corrigir sobreposições mantendo o layout natural da D3
function corrigirSobreposicoes(root) {
  // Agrupar nós por profundidade (nível)
  const niveis = {};
  root.descendants().forEach((node) => {
    if (!niveis[node.depth]) niveis[node.depth] = [];
    niveis[node.depth].push(node);
  });

  console.log(
    `DEBUG: Verificando sobreposições em ${Object.keys(niveis).length} níveis`,
  );

  // Para cada nível, verificar e corrigir apenas sobreposições
  Object.keys(niveis).forEach((depth) => {
    const nosNivel = niveis[depth];
    if (nosNivel.length > 1) {
      // Ordenar por posição X (vertical no layout horizontal)
      nosNivel.sort((a, b) => a.x - b.x);

      const alturaCard = 90;
      const margemMinima = 40;

      // Verificar se há documentos importados no nível
      const importadosNivel = nosNivel.filter(
        (node) => node.data.is_importado,
      ).length;
      let margemAjustada = margemMinima;

      // Aumentar margem se há documentos importados
      if (importadosNivel > 0) {
        margemAjustada = margemMinima * 1.2; // 20% mais margem vertical
        console.log(
          `DEBUG: Nível ${depth} - Aumentando margem vertical de ${margemMinima} para ${margemAjustada} devido a ${importadosNivel} documentos importados`,
        );
      }

      const espacamentoMinimo = alturaCard + margemAjustada;

      // Verificar se há sobreposições
      let temSobreposicao = false;
      for (let i = 0; i < nosNivel.length - 1; i++) {
        const distancia = Math.abs(nosNivel[i + 1].x - nosNivel[i].x);
        if (distancia < espacamentoMinimo) {
          temSobreposicao = true;
          break;
        }
      }

      // Só corrigir se houver sobreposição
      if (temSobreposicao) {
        const larguraTotal = (nosNivel.length - 1) * espacamentoMinimo;
        const inicio = nosNivel[0].x - larguraTotal / 2;

        nosNivel.forEach((node, index) => {
          node.x = inicio + index * espacamentoMinimo;
        });

        console.log(
          `DEBUG: Nível ${depth} - Corrigidas sobreposições para ${nosNivel.length} nós`,
        );
      }
    }
  });
}

// Função otimizada: Aplicar espaçamento adicional para evitar sobreposições
function ajustarPosicoesPorNivel(root) {
  // Cards de fim de cadeia continuam usando o nível calculado pelo backend.
  // Um documento com nível ajustado manualmente (nivel_manual, endpoint
  // ajustar-nivel) também respeita a escolha do usuário. Os demais nós
  // usam node.depth (profundidade calculada pelo d3.hierarchy a partir da
  // estrutura de árvore que converterParaArvoreD3 já monta corretamente)
  // -- usar node.data.nivel para todo mundo prenderia a posição X ao nível
  // antigo do backend, ignorando o pai primário escolhido acima.
  root.descendants().forEach((node) => {
    if (node.data.is_fim_cadeia) {
      const nivel = node.data.nivel || 0;
      node.y = nivel * 220 + 120;
      console.log(
        `DEBUG POSIÇÃO FIM CADEIA: ${node.data.numero} - nível backend: ${nivel}, posição Y: ${node.y}`,
      );
      return;
    }

    if (node.data.nivel_manual != null) {
      const nivel = node.data.nivel ?? node.depth;
      node.y = nivel * 220 + 120;
      return;
    }

    node.y = node.depth * 220 + 120;
  });
}

function aplicarEspacamentoAdicional(root) {
  // Agrupar nós por profundidade
  const niveis = {};
  root.descendants().forEach((node) => {
    if (!niveis[node.depth]) niveis[node.depth] = [];
    niveis[node.depth].push(node);
  });

  console.log(
    `DEBUG: Verificando espaçamento adicional para ${Object.keys(niveis).length} níveis`,
  );

  // Para cada nível, aplicar espaçamento adicional se necessário
  Object.keys(niveis).forEach((depth) => {
    const nosNivel = niveis[depth];
    if (nosNivel.length > 1) {
      // Ordenar por posição X (vertical no layout horizontal)
      nosNivel.sort((a, b) => a.x - b.x);

      // Verificar se há documentos importados no nível
      const importadosNivel = nosNivel.filter(
        (node) => node.data.is_importado,
      ).length;
      let espacamentoMinimo = 120; // espaçamento base

      // Aumentar espaçamento se há documentos importados
      if (importadosNivel > 0) {
        espacamentoMinimo = 150; // 25% mais espaçamento vertical
        console.log(
          `DEBUG: Nível ${depth} - Aumentando espaçamento vertical adicional de 120 para ${espacamentoMinimo} devido a ${importadosNivel} documentos importados`,
        );
      }

      // Verificar se o espaçamento atual é suficiente
      let espacamentoAtual = 0;
      for (let i = 0; i < nosNivel.length - 1; i++) {
        espacamentoAtual += nosNivel[i + 1].x - nosNivel[i].x;
      }
      espacamentoAtual = espacamentoAtual / (nosNivel.length - 1);

      // Só aplicar espaçamento adicional se o atual for muito pequeno
      if (espacamentoAtual < espacamentoMinimo) {
        const larguraTotal = (nosNivel.length - 1) * espacamentoMinimo;
        const inicio = nosNivel[0].x - larguraTotal / 2;

        nosNivel.forEach((node, index) => {
          node.x = inicio + index * espacamentoMinimo;
        });

        console.log(
          `DEBUG: Nível ${depth} - Espaçamento adicional aplicado (atual: ${espacamentoAtual.toFixed(1)}px -> mínimo: ${espacamentoMinimo}px)`,
        );
      }
    }
  });
}
