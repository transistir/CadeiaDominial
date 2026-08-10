// layout_spacing.js — Pós-processamento de posições: nível manual,
// fim de cadeia, sobreposições e espaçamento vertical adicional.

// Corrigir sobreposições mantendo o layout natural da D3
function corrigirSobreposicoes(root) {
  // Agrupar nós pela coluna horizontal real
  const colunas = {};
  root.descendants().forEach((node) => {
    const coluna = Math.round(node.y);
    if (!colunas[coluna]) colunas[coluna] = [];
    colunas[coluna].push(node);
  });

  console.log(
    `DEBUG: Verificando sobreposições em ${Object.keys(colunas).length} colunas`,
  );

  // Para cada coluna, verificar e corrigir apenas sobreposições
  Object.keys(colunas).forEach((coluna) => {
    const nosColuna = colunas[coluna];
    if (nosColuna.length > 1) {
      // Ordenar por posição X (vertical no layout horizontal)
      nosColuna.sort((a, b) => a.x - b.x);

      const alturaCard = 90;
      const margemMinima = 40;

      // Verificar se há documentos importados na coluna
      const importadosColuna = nosColuna.filter(
        (node) => node.data.is_importado,
      ).length;
      let margemAjustada = margemMinima;

      // Aumentar margem se há documentos importados
      if (importadosColuna > 0) {
        margemAjustada = margemMinima * 1.2; // 20% mais margem vertical
        console.log(
          `DEBUG: Coluna Y ${coluna} - Aumentando margem vertical de ${margemMinima} para ${margemAjustada} devido a ${importadosColuna} documentos importados`,
        );
      }

      const espacamentoMinimo = alturaCard + margemAjustada;

      // Verificar se há sobreposições
      let temSobreposicao = false;
      for (let i = 0; i < nosColuna.length - 1; i++) {
        const distancia = Math.abs(nosColuna[i + 1].x - nosColuna[i].x);
        if (distancia < espacamentoMinimo) {
          temSobreposicao = true;
          break;
        }
      }

      // Só corrigir se houver sobreposição
      if (temSobreposicao) {
        const larguraTotal = (nosColuna.length - 1) * espacamentoMinimo;
        const inicio =
          (nosColuna[0].x + nosColuna[nosColuna.length - 1].x) / 2 -
          larguraTotal / 2;

        nosColuna.forEach((node, index) => {
          node.x = inicio + index * espacamentoMinimo;
        });

        console.log(
          `DEBUG: Coluna Y ${coluna} - Corrigidas sobreposições para ${nosColuna.length} nós`,
        );
      }
    }
  });
}

// Ajustar posições horizontais por nível e manter fins de cadeia à direita
function ajustarPosicoesPorNivel(root) {
  // Primeiro posicionar os documentos pela profundidade real da árvore,
  // preservando o nível escolhido manualmente quando houver. Depois, usar a
  // posição final real do documento mais à direita para colocar todos os fins
  // de cadeia na mesma coluna, sem depender do nível calculado pelo backend.
  const nodes = root.descendants();
  const documentNodes = [];
  nodes.forEach((node) => {
    if (node.data.is_fim_cadeia) return;

    if (node.data.nivel_manual != null) {
      const nivel = node.data.nivel ?? node.depth;
      node.y = nivel * 220 + 120;
    } else {
      node.y = node.depth * 220 + 120;
    }

    documentNodes.push(node);
  });

  const finiteDocumentYs = documentNodes
    .map((node) => node.y)
    .filter(Number.isFinite);
  const maxDocumentY =
    finiteDocumentYs.length > 0 ? Math.max(...finiteDocumentYs) : null;

  nodes.forEach((node) => {
    if (!node.data.is_fim_cadeia) return;

    const nivelBackend = node.data.nivel;
    node.y =
      maxDocumentY !== null ? maxDocumentY + 220 : node.depth * 220 + 120;
    console.log(
      `DEBUG POSIÇÃO FIM CADEIA: ${node.data.numero} - nível backend: ${nivelBackend}, maxDocumentY: ${maxDocumentY}, posição final Y: ${node.y}`,
    );
  });
}

function aplicarEspacamentoAdicional(root) {
  // Agrupar nós pela coluna horizontal real
  const colunas = {};
  root.descendants().forEach((node) => {
    const coluna = Math.round(node.y);
    if (!colunas[coluna]) colunas[coluna] = [];
    colunas[coluna].push(node);
  });

  console.log(
    `DEBUG: Verificando espaçamento adicional para ${Object.keys(colunas).length} colunas`,
  );

  // Para cada coluna, aplicar espaçamento adicional se necessário
  Object.keys(colunas).forEach((coluna) => {
    const nosColuna = colunas[coluna];
    if (nosColuna.length > 1) {
      // Ordenar por posição X (vertical no layout horizontal)
      nosColuna.sort((a, b) => a.x - b.x);

      // Verificar se há documentos importados na coluna
      const importadosColuna = nosColuna.filter(
        (node) => node.data.is_importado,
      ).length;
      let espacamentoMinimo = 120; // espaçamento base

      // Aumentar espaçamento se há documentos importados
      if (importadosColuna > 0) {
        espacamentoMinimo = 150; // 25% mais espaçamento vertical
        console.log(
          `DEBUG: Coluna Y ${coluna} - Aumentando espaçamento vertical adicional de 120 para ${espacamentoMinimo} devido a ${importadosColuna} documentos importados`,
        );
      }

      // Verificar o menor espaçamento entre nós adjacentes (uma média mascara
      // sobreposições quando um gap grande "esconde" outros gaps pequenos)
      let minGap = Infinity;
      for (let i = 0; i < nosColuna.length - 1; i++) {
        minGap = Math.min(minGap, nosColuna[i + 1].x - nosColuna[i].x);
      }

      // Só aplicar espaçamento adicional se o menor espaçamento for muito pequeno
      if (minGap < espacamentoMinimo) {
        const larguraTotal = (nosColuna.length - 1) * espacamentoMinimo;
        const inicio =
          (nosColuna[0].x + nosColuna[nosColuna.length - 1].x) / 2 -
          larguraTotal / 2;

        nosColuna.forEach((node, index) => {
          node.x = inicio + index * espacamentoMinimo;
        });

        console.log(
          `DEBUG: Coluna Y ${coluna} - Espaçamento adicional aplicado (mínimo atual: ${minGap.toFixed(1)}px -> mínimo desejado: ${espacamentoMinimo}px)`,
        );
      }
    }
  });
}
