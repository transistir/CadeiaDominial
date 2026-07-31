// layout.js — d3.hierarchy, configuração do d3.tree, métricas e pipeline
// de layout completo. Depende das funções de layout_spacing.js.

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

function prepararLayoutArvore(data, width, height) {
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

  return root;
}
