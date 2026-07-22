// JS para visualização D3 da cadeia dominial
// Busca os dados da árvore e renderiza usando d3.tree()

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

document.addEventListener("DOMContentLoaded", function () {
  const svg = d3.select("#arvore-d3-svg");
  const containerWidth =
    document.getElementById("arvore-d3-svg").clientWidth || 1000;
  const width = Math.max(containerWidth, 2000); // Permitir largura maior para árvores extensas
  const height = 600;
  svg.attr("width", width).attr("height", height);

  // Limpar SVG
  svg.selectAll("*").remove();

  // Grupo para zoom/pan
  const zoomGroup = svg.append("g").attr("id", "zoom-group");

  // Comportamento de zoom/pan
  const zoom = d3
    .zoom()
    .scaleExtent([0.2, 3.0]) // Limites mais amplos para zoom
    .wheelDelta((event) => -event.deltaY * 0.002) // Velocidade do scroll
    .on("zoom", (event) => {
      zoomGroup.attr("transform", event.transform);
      // Atualizar transformação global
      window._zoomTransform = event.transform;
    });
  svg.call(zoom);

  // Guardar zoom para botões
  window._d3zoom = zoom;
  window._d3svg = svg;
  window._zoomGroup = zoomGroup;
  window._zoomTransform = d3.zoomIdentity;
  // Removido: svg.on('wheel.zoom', null); // Desabilitar zoom na roda do mouse se quiser

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

      // Habilitar botão de impressão (estava disabled durante carga)
      const btnImprimir = document.getElementById("btn-imprimir-arvore");
      if (btnImprimir) {
        btnImprimir.disabled = false;
        btnImprimir.style.opacity = "1";
        btnImprimir.style.cursor = "pointer";
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

function ordenarFilhosPorNumeroDesc(nodo) {
  if (nodo.children && nodo.children.length > 0) {
    nodo.children.sort((a, b) => {
      // Matrículas sempre antes de transcrições; dentro do mesmo tipo, maior número primeiro
      const tipoA = a.tipo_documento === "matricula" ? 0 : 1;
      const tipoB = b.tipo_documento === "matricula" ? 0 : 1;
      if (tipoA !== tipoB) return tipoA - tipoB;

      const numA = parseInt((a.numero || "").replace(/\D/g, ""), 10) || 0;
      const numB = parseInt((b.numero || "").replace(/\D/g, ""), 10) || 0;
      return numB - numA;
    });
    nodo.children.forEach(ordenarFilhosPorNumeroDesc);
  }
}

function converterParaArvoreD3(data) {
  console.log(
    `DEBUG: Iniciando conversão - Backend enviou ${data.documentos.length} documentos únicos`,
  );

  // IDs são a identidade técnica; número permanece apenas como rótulo.
  const docMap = {};
  data.documentos.forEach((doc) => {
    doc.children = [];
    docMap[doc.id] = doc;
  });

  // Encontrar a matrícula principal (raiz)
  let raiz = data.documentos.find(
    (doc) => doc.nivel === 0 || doc.origem === "" || doc.origem == null,
  );
  if (!raiz) raiz = data.documentos[0];

  console.log(`DEBUG: Raiz identificada: ${raiz.numero}`);

  // CORREÇÃO: um documento pode ser citado como origem por mais de um
  // documento (grafo, não árvore). Quando isso acontece, o documento deve
  // pertencer ao citante MAIS PROFUNDO (mais distante da raiz) -- senão a
  // citação do citante mais raso vira uma linha secundária cruzando
  // verticalmente irmãos da mesma coluna. Calculamos o caminho mais longo
  // a partir da raiz (relaxamento iterativo, não BFS de caminho mais
  // curto) e usamos o citante que produz esse caminho como pai primário;
  // qualquer outra citação vira conexão secundária (linha tracejada), que
  // assim sempre "avança" para uma coluna mais profunda, nunca cruza a
  // mesma coluna.
  const conexoesPorFrom = new Map();
  data.conexoes.forEach((con) => {
    if (!conexoesPorFrom.has(con.from)) conexoesPorFrom.set(con.from, []);
    conexoesPorFrom.get(con.from).push(con);
  });

  const profundidade = new Map([[raiz.id, 0]]);
  const paiPrimario = new Map();
  const fila = [raiz.id];
  let iteracoes = 0;
  const limiteIteracoes =
    data.documentos.length * data.conexoes.length + data.documentos.length;

  // Impede que uma citação cíclica (ex.: A cita B e B cita A, direta ou
  // indiretamente) vire uma aresta primária -- senão docMap[X].children
  // pode acabar contendo, direta ou indiretamente, o próprio X, e a
  // recursão em ordenarFilhosPorNumeroDesc/d3.hierarchy nunca termina.
  function criariCiclo(candidatoPai, alvo) {
    let atual = candidatoPai;
    let passos = 0;
    while (atual !== undefined) {
      if (atual === alvo) return true;
      if (++passos > data.documentos.length) return true;
      atual = paiPrimario.get(atual);
    }
    return false;
  }

  while (fila.length > 0) {
    if (++iteracoes > limiteIteracoes) {
      console.warn(
        "DEBUG: possível ciclo nas conexões, interrompendo cálculo de profundidade",
      );
      break;
    }
    const atual = fila.shift();
    (conexoesPorFrom.get(atual) || []).forEach((con) => {
      if (!docMap[con.to]) return;
      if (con.to === raiz.id) return; // a raiz nunca recebe pai primário
      if (criariCiclo(atual, con.to)) return;
      const novaProfundidade = profundidade.get(atual) + 1;
      if (
        !profundidade.has(con.to) ||
        novaProfundidade > profundidade.get(con.to)
      ) {
        profundidade.set(con.to, novaProfundidade);
        paiPrimario.set(con.to, atual);
        fila.push(con.to);
      }
    });
  }

  const conexoesSecundarias = [];
  data.conexoes.forEach((con) => {
    if (!docMap[con.to] || !docMap[con.from]) return;
    if (!profundidade.has(con.to)) return;

    if (paiPrimario.get(con.to) === con.from) {
      docMap[con.from].children.push(docMap[con.to]);
    } else {
      // Documento já pertence a outro nó da árvore: conecta sem duplicar o card
      console.log(`DEBUG: Conexão secundária: ${con.from} -> ${con.to}`);
      conexoesSecundarias.push({
        from: con.from,
        to: con.to,
        tipo: "conexao_secundaria",
      });
    }
  });

  console.log(
    `DEBUG: Documentos na árvore: ${profundidade.size}, conexões secundárias: ${conexoesSecundarias.length}`,
  );

  // Adicionar conexões secundárias à raiz
  raiz.conexoesExtras = conexoesSecundarias;

  // Ordenar filhos recursivamente
  ordenarFilhosPorNumeroDesc(raiz);

  return raiz;
}

function centralizarArvoreInteligente(root, height) {
  // Centralizar baseado no bounding box real da árvore
  const nodes = root.descendants();
  if (nodes.length === 0) return;

  // Calcular bounding box real
  let minX = Infinity,
    maxX = -Infinity;
  nodes.forEach((node) => {
    minX = Math.min(minX, node.x);
    maxX = Math.max(maxX, node.x);
  });

  // Calcular centro da árvore e centro desejado
  const centroArvore = (minX + maxX) / 2;
  const centroDesejado = height / 2;

  // Aplicar translação para centralizar
  const offset = centroDesejado - centroArvore;
  nodes.forEach((node) => {
    node.x += offset;
  });

  console.log(
    `DEBUG: Centralização - minX: ${minX}, maxX: ${maxX}, centro: ${centroArvore} -> ${centroDesejado} (offset: ${offset}px)`,
  );
  console.log(`DEBUG: Altura do container: ${height}px`);

  // Verificar alguns nós após centralização
  const primeirosNos = nodes.slice(0, 3);
  primeirosNos.forEach((node, i) => {
    console.log(
      `DEBUG: Nó ${i + 1} após centralização - x: ${node.x}, y: ${node.y}`,
    );
  });
}

// Calcular espaçamento adaptativo baseado na quantidade de nós
function calcularEspacamentoAdaptativo(root) {
  // Encontrar o nível com mais nós
  const niveis = {};
  root.descendants().forEach((node) => {
    const nivel = node.depth;
    if (!niveis[nivel]) niveis[nivel] = 0;
    niveis[nivel]++;
  });

  // Encontrar o nível com mais nós
  let maxNos = 0;
  Object.values(niveis).forEach((count) => {
    if (count > maxNos) maxNos = count;
  });

  // Calcular espaçamento baseado na quantidade máxima de nós
  // Considerando que cada card tem 150px de largura e 90px de altura
  let espacamentoHorizontal = 220; // padrão equilibrado
  if (maxNos > 20) {
    espacamentoHorizontal = 350; // bem espaçado para muitos nós
  } else if (maxNos > 15) {
    espacamentoHorizontal = 300; // bem espaçado para muitos nós
  } else if (maxNos > 10) {
    espacamentoHorizontal = 250; // espaçado para muitos nós
  } else if (maxNos > 6) {
    espacamentoHorizontal = 220; // moderadamente espaçado
  }

  return espacamentoHorizontal;
}

function aplicarLayoutResponsivo(root, width, height) {
  // Aplicar layout responsivo baseado na quantidade de nós
  const totalNos = root.descendants().length;
  const maxNosPorNivel = Math.max(
    ...Object.values(
      root.descendants().reduce((acc, node) => {
        acc[node.depth] = (acc[node.depth] || 0) + 1;
        return acc;
      }, {}),
    ),
  );

  // Configurações responsivas
  const config = {
    alturaMultiplicador:
      totalNos > 50 ? 4.0 : totalNos > 30 ? 3.5 : totalNos > 15 ? 3.0 : 2.5,
    separacaoBase:
      maxNosPorNivel > 20
        ? 3.5
        : maxNosPorNivel > 15
          ? 3.0
          : maxNosPorNivel > 10
            ? 2.5
            : 2.0,
    margemVertical: maxNosPorNivel > 15 ? 150 : maxNosPorNivel > 10 ? 120 : 100,
  };

  console.log(
    `DEBUG: Layout responsivo - Total: ${totalNos}, Máximo/ nível: ${maxNosPorNivel}, Altura: ${config.alturaMultiplicador}x, Separação: ${config.separacaoBase}x`,
  );

  return config;
}

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

function renderArvoreD3(data, svgGroup, width, height) {
  // Converter para d3.hierarchy
  const root = d3.hierarchy(data);

  // DEBUG: Analisar estrutura da árvore para documentos importados
  const totalNos = root.descendants().length;
  const documentosImportados = root
    .descendants()
    .filter((node) => node.data.is_importado).length;
  const documentosCompartilhados = root
    .descendants()
    .filter((node) => node.data.is_compartilhado).length;

  console.log(
    `DEBUG: Estrutura da árvore - Total: ${totalNos}, Importados: ${documentosImportados}, Compartilhados: ${documentosCompartilhados}`,
  );

  // DEBUG: Verificar dados dos documentos importados
  const docsImportados = root
    .descendants()
    .filter((node) => node.data.is_importado);
  docsImportados.forEach((node, index) => {
    console.log(
      `DEBUG: Documento importado ${index + 1}: ${node.data.numero} (nível ${node.depth})`,
    );
  });

  // Analisar distribuição por níveis
  const niveis = {};
  root.descendants().forEach((node) => {
    if (!niveis[node.depth]) niveis[node.depth] = [];
    niveis[node.depth].push(node);
  });

  Object.keys(niveis).forEach((depth) => {
    const nosNivel = niveis[depth];
    const importadosNivel = nosNivel.filter(
      (node) => node.data.is_importado,
    ).length;
    console.log(
      `DEBUG: Nível ${depth} - Total: ${nosNivel.length}, Importados: ${importadosNivel}`,
    );
  });

  // Calcular espaçamento adaptativo
  const espacamentoHorizontal = calcularEspacamentoAdaptativo(root);

  // Configurar layout da árvore para layout horizontal correto
  const treeLayout = d3
    .tree()
    .size([height, width - 20]) // Reduzir ao máximo a margem para mais espaço horizontal
    .nodeSize([90, 220]) // [altura, largura] - 220px entre níveis
    .separation((a, b) => {
      // Separação baseada na quantidade de irmãos - AUMENTADA
      const irmaos = a.parent ? a.parent.children.length : 1;

      // DEBUG: Verificar se há documentos importados no nível
      const nivel = a.depth;
      const nosNivel = a.parent ? a.parent.children : [a];
      const importadosNivel = nosNivel.filter(
        (node) => node.data.is_importado,
      ).length;

      if (importadosNivel > 0) {
        console.log(
          `DEBUG: Nível ${nivel} tem ${importadosNivel} documentos importados de ${nosNivel.length} total`,
        );
      }

      // Aumentar separação se há muitos documentos importados
      let separacaoBase = 2.0; // Base aumentada
      if (irmaos > 15) separacaoBase = 4.0;
      else if (irmaos > 10) separacaoBase = 3.5;
      else if (irmaos > 6) separacaoBase = 3.0;
      else if (irmaos > 3) separacaoBase = 2.5;

      // Aumentar separação horizontal para níveis com documentos importados
      if (importadosNivel > 0) {
        // Ser muito mais agressivo no espaçamento horizontal para ver as linhas
        if (irmaos > 6)
          separacaoBase = 8.0; // Separação muito maior para muitos irmãos
        else if (irmaos > 3) separacaoBase = 6.0;
        else separacaoBase = 5.0;
        console.log(
          `DEBUG: Aumentando separação horizontal para ${separacaoBase} devido a documentos importados`,
        );
      }

      return separacaoBase;
    });

  treeLayout(root);

  // Ajustar posições baseado no campo 'nivel' dos dados
  ajustarPosicoesPorNivel(root);

  // Aplicar correção de sobreposições melhorada
  corrigirSobreposicoes(root);

  // Aplicar espaçamento adicional se necessário
  aplicarEspacamentoAdicional(root);

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
    .attr(
      "d",
      d3
        .linkHorizontal()
        .x((d) => d.y + 120)
        .y((d) => d.x + 20),
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
        const fromNode = nodesMap.get(d.from);
        const toNode = nodesMap.get(d.to);
        if (fromNode && toNode) {
          return d3
            .linkHorizontal()
            .x((d) => d.y + 120)
            .y((d) => d.x + 20)
            .source(() => fromNode)
            .target(() => toNode)();
        }
        return "";
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
        } else {
          return "#dc3545"; // Vermelho para sem origem ou inconclusa
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
        } else {
          return "#b02a37"; // Vermelho escuro para sem origem ou inconclusa
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
        } else {
          tipo = "Sem Origem";
        }

        let classificacao = "";
        if (d.data.classificacao_fim_cadeia === "origem_lidima") {
          classificacao = "Origem Lídima";
        } else if (d.data.classificacao_fim_cadeia === "sem_origem") {
          classificacao = "Sem Origem";
        } else if (d.data.classificacao_fim_cadeia === "inconclusa") {
          classificacao = "Situação Inconclusa";
        }

        return `Fim de Cadeia\nTipo: ${tipo}\nClassificação: ${classificacao}`;
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
      if (!d.data.is_fim_cadeia) {
        window.location.href = `/dominial/tis/${window.tisId}/imovel/${window.imovelId}/documento/${d.data.id}/detalhado/`;
      }
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

// Controle de zoom para o SVG D3
let currentZoom = 1;
const minZoom = 0.3;
const maxZoom = 2.5;
const zoomStep = 0.2;

function applyZoom() {
  const svg = window._d3svg;
  const zoom = window._d3zoom;
  const t = window._zoomTransform.rescaleY
    ? window._zoomTransform
    : d3.zoomTransform(svg.node());
  svg
    .transition()
    .duration(200)
    .call(zoom.scaleBy, currentZoom / t.k);
}

window.zoomIn = function () {
  const svg = window._d3svg;
  const zoom = window._d3zoom;
  svg.transition().duration(200).call(zoom.scaleBy, 1.2);
  currentZoom = Math.min(currentZoom * 1.2, maxZoom);
};

window.zoomOut = function () {
  const svg = window._d3svg;
  const zoom = window._d3zoom;
  svg.transition().duration(200).call(zoom.scaleBy, 0.8);
  currentZoom = Math.max(currentZoom * 0.8, minZoom);
};

window.resetZoom = function () {
  const svg = window._d3svg;
  const zoomGroup = window._zoomGroup;
  const width = +svg.attr("width");
  const height = +svg.attr("height");

  // Pegar o bounding box do grupo de nós
  const nodes = zoomGroup.selectAll(".node");
  if (nodes.size() === 0) return;

  let minX = Infinity,
    maxX = -Infinity,
    minY = Infinity,
    maxY = -Infinity;
  nodes.each(function () {
    const bbox = this.getBBox();
    const x = +this.getAttribute("transform").split("(")[1].split(",")[0];
    const y = +this.getAttribute("transform").split(",")[1].split(")")[0];
    minX = Math.min(minX, x + bbox.x);
    maxX = Math.max(maxX, x + bbox.x + bbox.width);
    minY = Math.min(minY, y + bbox.y);
    maxY = Math.max(maxY, y + bbox.y + bbox.height);
  });

  // Adicionar margem extra para os cards
  minX -= 75;
  maxX += 75;
  minY -= 45;
  maxY += 45;

  const treeWidth = maxX - minX;
  const treeHeight = maxY - minY;

  // Calcular escala para caber TUDO na div com margem
  const scaleX = (width - 100) / treeWidth;
  const scaleY = (height - 100) / treeHeight;
  const finalScale = Math.min(scaleX, scaleY, 1); // Não aumentar além do tamanho original

  // Posicionar o primeiro card na extrema esquerda da div
  const tx = 50 - minX * finalScale; // Margem de 50px da esquerda
  const ty = (height - treeHeight * finalScale) / 2 - minY * finalScale; // Centralizar verticalmente

  console.log(
    `DEBUG: Reset - Árvore: ${treeWidth}x${treeHeight}, Container: ${width}x${height}, Escala: ${finalScale}`,
  );

  const t = d3.zoomIdentity.translate(tx, ty).scale(finalScale);
  svg.transition().duration(400).call(window._d3zoom.transform, t);
  window._zoomTransform = t;
  currentZoom = 1;
};

window.fimDaArvore = function () {
  const svg = window._d3svg;
  const zoomGroup = window._zoomGroup;
  const width = +svg.attr("width");
  const height = +svg.attr("height");

  // Pegar o bounding box do grupo de nós
  const nodes = zoomGroup.selectAll(".node");
  if (nodes.size() === 0) return;

  let minX = Infinity,
    maxX = -Infinity,
    minY = Infinity,
    maxY = -Infinity;
  nodes.each(function () {
    const bbox = this.getBBox();
    const x = +this.getAttribute("transform").split("(")[1].split(",")[0];
    const y = +this.getAttribute("transform").split(",")[1].split(")")[0];
    minX = Math.min(minX, x + bbox.x);
    maxX = Math.max(maxX, x + bbox.x + bbox.width);
    minY = Math.min(minY, y + bbox.y);
    maxY = Math.max(maxY, y + bbox.y + bbox.height);
  });

  // Adicionar margem extra para os cards
  minX -= 75;
  maxX += 75;
  minY -= 45;
  maxY += 45;

  const treeWidth = maxX - minX;
  const treeHeight = maxY - minY;

  // Calcular escala para focar no último nível (mais à direita)
  const ultimoNivelWidth = 300; // Largura estimada do último nível
  const finalScale = Math.min(
    (width - 100) / ultimoNivelWidth,
    (height - 100) / treeHeight,
    2.0,
  ); // Escala maior para zoom

  // Posicionar o último nível no centro da div
  const centroUltimoNivel = maxX - ultimoNivelWidth / 2;
  const tx = width / 2 - centroUltimoNivel * finalScale;
  const ty = (height - treeHeight * finalScale) / 2 - minY * finalScale; // Centralizar verticalmente

  console.log(
    `DEBUG: Fim da Árvore - Último nível no centro, Escala: ${finalScale}`,
  );

  const t = d3.zoomIdentity.translate(tx, ty).scale(finalScale);
  svg.transition().duration(400).call(window._d3zoom.transform, t);
  window._zoomTransform = t;
  currentZoom = 1;
};

// ========================================================
// IMPRESSÃO (#49) — beforeprint / afterprint
// IMPRESSÃO (#49) — beforeprint / afterprint
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
