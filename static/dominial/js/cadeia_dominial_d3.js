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

// Definir função expandirArvore globalmente imediatamente
window.expandirArvore = debounce(function() {
    const svg = window._d3svg;
    const zoomGroup = window._zoomGroup;
    if (!svg || !zoomGroup) {
        console.warn('Árvore ainda não foi inicializada');
        return;
    }
    
    const width = svg.attr('width');
    const height = svg.attr('height');
    
    // Pegar todos os nós
    const nodes = zoomGroup.selectAll('.node');
    if (nodes.size() === 0) return;
    
    // Calcular bounding box atual
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    nodes.each(function() {
        const transform = this.getAttribute('transform');
        const match = transform.match(/translate\(([^,]+),([^)]+)\)/);
        if (match) {
            const x = parseFloat(match[1]);
            const y = parseFloat(match[2]);
            minX = Math.min(minX, x);
            maxX = Math.max(maxX, x);
            minY = Math.min(minY, y);
            maxY = Math.max(maxY, y);
        }
    });
    
    // Adicionar margem para os cards (140x80)
    minX -= 70; // metade da largura do card
    maxX += 70;
    minY -= 40; // metade da altura do card
    maxY += 40;
    
    const treeWidth = maxX - minX;
    const treeHeight = maxY - minY;
    
    // Calcular escala para caber tudo com margem extra
    const scale = Math.min((width - 120) / treeWidth, (height - 120) / treeHeight, 1);
    
    // Centralizar com margem extra
    const tx = (width - treeWidth * scale) / 2 - minX * scale;
    const ty = (height - treeHeight * scale) / 2 - minY * scale;
    
    const t = d3.zoomIdentity.translate(tx, ty).scale(scale);
    svg.transition().duration(600).call(window._d3zoom.transform, t);
    window._zoomTransform = t;
}, 300); // Debounce de 300ms

document.addEventListener('DOMContentLoaded', function() {
    const svg = d3.select('#arvore-d3-svg');
    const containerWidth = document.getElementById('arvore-d3-svg').clientWidth || 1000;
    const width = Math.max(containerWidth, 2000); // Permitir largura maior para árvores extensas
    const height = 600;
    svg.attr('width', width).attr('height', height);

    // Limpar SVG
    svg.selectAll('*').remove();

    // Grupo para zoom/pan
    const zoomGroup = svg.append('g').attr('id', 'zoom-group');

    // Comportamento de zoom/pan
    const zoom = d3.zoom()
        .scaleExtent([0.2, 3.0]) // Limites mais amplos para zoom
        .wheelDelta(event => -event.deltaY * 0.002) // Velocidade do scroll
        .on('zoom', (event) => {
            zoomGroup.attr('transform', event.transform);
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
    const loadingIndicator = svg.append('text')
        .attr('x', width/2)
        .attr('y', height/2)
        .attr('text-anchor', 'middle')
        .style('fill', '#6c757d')
        .style('font-size', '16px')
        .text('Carregando árvore...');

    // Buscar dados da árvore (corrigido)
    const timestamp = new Date().getTime();
    fetch(`/dominial/cadeia-dominial/${window.tisId}/${window.imovelId}/arvore/?t=${timestamp}`)
        .then(response => response.json())
        .then(data => {
            // Remover indicador de carregamento
            loadingIndicator.remove();
            
            // Adicionar indicador de processamento
            const processingIndicator = svg.append('text')
                .attr('x', width/2)
                .attr('y', height/2)
                .attr('text-anchor', 'middle')
                .style('fill', '#17a2b8')
                .style('font-size', '14px')
                .text('Processando dados...');
            
            // Converter para formato de árvore
            const arvore = converterParaArvoreD3(data);
            
            // Remover indicador de processamento
            processingIndicator.remove();
            
            renderArvoreD3(arvore, zoomGroup, width, height);
            
            // Adicionar indicador de sucesso temporário
            const successIndicator = svg.append('text')
                .attr('x', 20)
                .attr('y', 30)
                .attr('text-anchor', 'start')
                .style('fill', '#28a745')
                .style('font-size', '12px')
                .style('opacity', '0')
                .text('✓ Árvore carregada com sucesso');
            
            successIndicator.transition()
                .duration(500)
                .style('opacity', '1')
                .transition()
                .delay(2000)
                .duration(500)
                .style('opacity', '0')
                .remove();
            
            // Enquadrar após renderizar
            setTimeout(() => enquadrarArvoreNoSVG(svg, zoomGroup, width, height), 100);
        })
        .catch(err => {
            loadingIndicator.remove();
            svg.append('text')
                .attr('x', width/2)
                .attr('y', height/2)
                .attr('text-anchor', 'middle')
                .style('fill', '#dc3545')
                .text('Erro ao carregar árvore: ' + err.message);
        });
});

function ordenarFilhosPorNumeroDesc(nodo) {
    if (nodo.children && nodo.children.length > 0) {
        nodo.children.sort((a, b) => {
            // Extrair número ignorando prefixos não numéricos
            const numA = parseInt((a.numero || '').replace(/\D/g, ''));
            const numB = parseInt((b.numero || '').replace(/\D/g, ''));
            return numB - numA;
        });
        nodo.children.forEach(ordenarFilhosPorNumeroDesc);
    }
}

function converterParaArvoreD3(data) {
    // Mapear documentos por número
    const docMap = {};
    data.documentos.forEach(doc => {
        doc.children = [];
        docMap[doc.numero] = doc;
    });
    
    // CORREÇÃO: Construir árvore sem duplicação e armazenar conexões extras
    // Primeiro, identificar todas as conexões pai-filho
    const conexoesPaiFilho = new Map(); // pai -> [filhos]
    
    data.conexoes.forEach(con => {
        const from = docMap[con.from];
        const to = docMap[con.to];
        if (to && from) {
            // Armazenar a relação pai-filho
            if (!conexoesPaiFilho.has(to.numero)) {
                conexoesPaiFilho.set(to.numero, []);
            }
            conexoesPaiFilho.get(to.numero).push(from.numero);
        }
    });
    
    // Construir a árvore evitando duplicação
    const visitados = new Set();
    const fila = [];
    
    // Encontrar a matrícula principal (raiz)
    let raiz = data.documentos.find(doc => doc.nivel === 0 || doc.origem === '' || doc.origem == null);
    if (!raiz) raiz = data.documentos[0];
    
    // Iniciar a fila com a raiz
    fila.push(raiz.numero);
    visitados.add(raiz.numero);
    
    // Processar a fila - construir árvore sem duplicação
    while (fila.length > 0) {
        const docAtual = fila.shift();
        const docNode = docMap[docAtual];
        
        // Adicionar apenas filhos únicos que ainda não foram visitados
        const filhos = conexoesPaiFilho.get(docAtual) || [];
        for (const filhoNumero of filhos) {
            if (!visitados.has(filhoNumero)) {
                docNode.children.push(docMap[filhoNumero]);
                visitados.add(filhoNumero);
                fila.push(filhoNumero);
            }
        }
    }
    
    // Adicionar documentos isolados (que não foram conectados)
    data.documentos.forEach(doc => {
        if (!visitados.has(doc.numero)) {
            // Adicionar como filho da raiz para garantir que apareça
            if (!raiz.children) raiz.children = [];
            raiz.children.push(doc);
        }
    });
    
    // Armazenar todas as conexões originais para renderização extra
    raiz.conexoesExtras = data.conexoes;
    
    // Ordenar filhos recursivamente
    ordenarFilhosPorNumeroDesc(raiz);
    return raiz;
}

function centralizarArvore(width, height) {
    // Centraliza o grupo na tela
    const svg = window._d3svg;
    const zoom = window._d3zoom;
    const zoomGroup = window._zoomGroup;
    // Centralizar em (width/2, height/2)
    const t = d3.zoomIdentity.translate(width/2, 60).scale(1);
    svg.transition().duration(400).call(zoom.transform, t);
    window._zoomTransform = t;
}

function centralizarArvoreInteligente(root, height) {
    // Centralizar baseado no bounding box real da árvore
    const nodes = root.descendants();
    if (nodes.length === 0) return;
    
    // Calcular bounding box real
    let minX = Infinity, maxX = -Infinity;
    nodes.forEach(node => {
        minX = Math.min(minX, node.x);
        maxX = Math.max(maxX, node.x);
    });
    
    // Calcular centro da árvore e centro desejado
    const centroArvore = (minX + maxX) / 2;
    const centroDesejado = height / 2;
    
    // Aplicar translação para centralizar
    const offset = centroDesejado - centroArvore;
    nodes.forEach(node => {
        node.x += offset;
    });
    
    console.log(`DEBUG: Centralização - minX: ${minX}, maxX: ${maxX}, centro: ${centroArvore} -> ${centroDesejado} (offset: ${offset}px)`);
    console.log(`DEBUG: Altura do container: ${height}px`);
    
    // Verificar alguns nós após centralização
    const primeirosNos = nodes.slice(0, 3);
    primeirosNos.forEach((node, i) => {
        console.log(`DEBUG: Nó ${i + 1} após centralização - x: ${node.x}, y: ${node.y}`);
    });
}

// Calcular espaçamento adaptativo baseado na quantidade de nós
function calcularEspacamentoAdaptativo(root) {
    // Encontrar o nível com mais nós
    const niveis = {};
    root.descendants().forEach(node => {
        const nivel = node.depth;
        if (!niveis[nivel]) niveis[nivel] = 0;
        niveis[nivel]++;
    });
    
    // Encontrar o nível com mais nós
    let maxNos = 0;
    Object.values(niveis).forEach(count => {
        if (count > maxNos) maxNos = count;
    });
    
    // Calcular espaçamento baseado na quantidade máxima de nós
    // Considerando que cada card tem 140px de largura e 80px de altura
    let espacamentoHorizontal = 200; // padrão equilibrado
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
    const maxNosPorNivel = Math.max(...Object.values(
        root.descendants().reduce((acc, node) => {
            acc[node.depth] = (acc[node.depth] || 0) + 1;
            return acc;
        }, {})
    ));
    
    // Configurações responsivas
    const config = {
        alturaMultiplicador: totalNos > 50 ? 4.0 : totalNos > 30 ? 3.5 : totalNos > 15 ? 3.0 : 2.5,
        separacaoBase: maxNosPorNivel > 20 ? 3.5 : maxNosPorNivel > 15 ? 3.0 : maxNosPorNivel > 10 ? 2.5 : 2.0,
        margemVertical: maxNosPorNivel > 15 ? 150 : maxNosPorNivel > 10 ? 120 : 100
    };
    
    console.log(`DEBUG: Layout responsivo - Total: ${totalNos}, Máximo/ nível: ${maxNosPorNivel}, Altura: ${config.alturaMultiplicador}x, Separação: ${config.separacaoBase}x`);
    
    return config;
}

// Corrigir sobreposições mantendo o layout natural da D3
function corrigirSobreposicoes(root) {
    // Agrupar nós por profundidade (nível)
    const niveis = {};
    root.descendants().forEach(node => {
        if (!niveis[node.depth]) niveis[node.depth] = [];
        niveis[node.depth].push(node);
    });
    
    console.log(`DEBUG: Verificando sobreposições em ${Object.keys(niveis).length} níveis`);
    
    // Para cada nível, verificar e corrigir apenas sobreposições
    Object.keys(niveis).forEach(depth => {
        const nosNivel = niveis[depth];
        if (nosNivel.length > 1) {
            // Ordenar por posição X (vertical no layout horizontal)
            nosNivel.sort((a, b) => a.x - b.x);
            
            const alturaCard = 80;
            const margemMinima = 40;
            
            // Verificar se há documentos importados no nível
            const importadosNivel = nosNivel.filter(node => node.data.is_importado).length;
            let margemAjustada = margemMinima;
            
            // Aumentar margem se há documentos importados
            if (importadosNivel > 0) {
                margemAjustada = margemMinima * 1.2; // 20% mais margem vertical
                console.log(`DEBUG: Nível ${depth} - Aumentando margem vertical de ${margemMinima} para ${margemAjustada} devido a ${importadosNivel} documentos importados`);
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
                const inicio = nosNivel[0].x - (larguraTotal / 2);
                
                nosNivel.forEach((node, index) => {
                    node.x = inicio + (index * espacamentoMinimo);
                });
                
                console.log(`DEBUG: Nível ${depth} - Corrigidas sobreposições para ${nosNivel.length} nós`);
            }
        }
    });
}

// Função otimizada: Aplicar espaçamento adicional para evitar sobreposições
function ajustarPosicoesPorNivel(root) {
    // Ajustar posições horizontais baseado no campo 'nivel' dos dados
    root.descendants().forEach(node => {
        const nivel = node.data.nivel || 0;
        
        // Cards de fim de cadeia usam o nível do backend para posicionamento
        if (node.data.is_fim_cadeia) {
            // Usar o nível do backend para posicionar corretamente
            node.y = nivel * 200 + 120;
            console.log(`DEBUG POSIÇÃO FIM CADEIA: ${node.data.numero} - nível backend: ${nivel}, posição Y: ${node.y}`);
            return;
        }
        
        // Posicionar horizontalmente baseado no nível (200px por nível)
        node.y = nivel * 200 + 120;
    });
}

function aplicarEspacamentoAdicional(root) {
    // Agrupar nós por profundidade
    const niveis = {};
    root.descendants().forEach(node => {
        if (!niveis[node.depth]) niveis[node.depth] = [];
        niveis[node.depth].push(node);
    });
    
    console.log(`DEBUG: Verificando espaçamento adicional para ${Object.keys(niveis).length} níveis`);
    
    // Para cada nível, aplicar espaçamento adicional se necessário
    Object.keys(niveis).forEach(depth => {
        const nosNivel = niveis[depth];
        if (nosNivel.length > 1) {
            // Ordenar por posição X (vertical no layout horizontal)
            nosNivel.sort((a, b) => a.x - b.x);
            
            // Verificar se há documentos importados no nível
            const importadosNivel = nosNivel.filter(node => node.data.is_importado).length;
            let espacamentoMinimo = 120; // espaçamento base
            
            // Aumentar espaçamento se há documentos importados
            if (importadosNivel > 0) {
                espacamentoMinimo = 150; // 25% mais espaçamento vertical
                console.log(`DEBUG: Nível ${depth} - Aumentando espaçamento vertical adicional de 120 para ${espacamentoMinimo} devido a ${importadosNivel} documentos importados`);
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
                const inicio = nosNivel[0].x - (larguraTotal / 2);
                
                nosNivel.forEach((node, index) => {
                    node.x = inicio + (index * espacamentoMinimo);
                });
                
                console.log(`DEBUG: Nível ${depth} - Espaçamento adicional aplicado (atual: ${espacamentoAtual.toFixed(1)}px -> mínimo: ${espacamentoMinimo}px)`);
            }
        }
    });
}



function renderArvoreD3(data, svgGroup, width, height) {
    // Converter para d3.hierarchy
    const root = d3.hierarchy(data);
    
    // DEBUG: Analisar estrutura da árvore para documentos importados
    const totalNos = root.descendants().length;
    const documentosImportados = root.descendants().filter(node => node.data.is_importado).length;
    const documentosCompartilhados = root.descendants().filter(node => node.data.is_compartilhado).length;
    
    console.log(`DEBUG: Estrutura da árvore - Total: ${totalNos}, Importados: ${documentosImportados}, Compartilhados: ${documentosCompartilhados}`);
    
    // DEBUG: Verificar dados dos documentos importados
    const docsImportados = root.descendants().filter(node => node.data.is_importado);
    docsImportados.forEach((node, index) => {
        console.log(`DEBUG: Documento importado ${index + 1}: ${node.data.numero} (nível ${node.depth})`);
    });
    
    // Analisar distribuição por níveis
    const niveis = {};
    root.descendants().forEach(node => {
        if (!niveis[node.depth]) niveis[node.depth] = [];
        niveis[node.depth].push(node);
    });
    
    Object.keys(niveis).forEach(depth => {
        const nosNivel = niveis[depth];
        const importadosNivel = nosNivel.filter(node => node.data.is_importado).length;
        console.log(`DEBUG: Nível ${depth} - Total: ${nosNivel.length}, Importados: ${importadosNivel}`);
    });
    
    // Calcular espaçamento adaptativo
    const espacamentoHorizontal = calcularEspacamentoAdaptativo(root);
    
    // Configurar layout da árvore para layout horizontal correto
    const treeLayout = d3.tree()
        .size([height, width - 20]) // Reduzir ao máximo a margem para mais espaço horizontal
        .nodeSize([80, 200]) // [altura, largura] - 200px entre níveis
        .separation((a, b) => {
            // Separação baseada na quantidade de irmãos - AUMENTADA
            const irmaos = a.parent ? a.parent.children.length : 1;
            
            // DEBUG: Verificar se há documentos importados no nível
            const nivel = a.depth;
            const nosNivel = a.parent ? a.parent.children : [a];
            const importadosNivel = nosNivel.filter(node => node.data.is_importado).length;
            
            if (importadosNivel > 0) {
                console.log(`DEBUG: Nível ${nivel} tem ${importadosNivel} documentos importados de ${nosNivel.length} total`);
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
                if (irmaos > 6) separacaoBase = 8.0; // Separação muito maior para muitos irmãos
                else if (irmaos > 3) separacaoBase = 6.0;
                else separacaoBase = 5.0;
                console.log(`DEBUG: Aumentando separação horizontal para ${separacaoBase} devido a documentos importados`);
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
    const links = svgGroup.selectAll('path.link')
        .data(root.links(), d => d.target.id)
        .join('path')
        .attr('class', 'link')
        .attr('fill', 'none')
        .attr('stroke', '#28a745')
        .attr('stroke-width', 2)
        .attr('stroke-linecap', 'round')
        .style('opacity', '0')
        .attr('d', d3.linkHorizontal()
            .x(d => d.y + 120)
            .y(d => d.x + 20)
        )
        .on('mouseover', function(event, d) {
            d3.select(this)
                .transition().duration(200)
                .style('stroke-width', '4')
                .style('opacity', '1');
        })
        .on('mouseout', function(event, d) {
            d3.select(this)
                .transition().duration(200)
                .style('stroke-width', '2')
                .style('opacity', '0.8');
        });

    // Aplicar apenas transição de opacidade para links (sem mover posição)
    links.transition()
        .duration(600)
        .ease(d3.easeQuadInOut)
        .style('opacity', '0.8');
    
    // CORREÇÃO: Desenhar conexões extras (múltiplas conexões para o mesmo documento)
    if (data.conexoesExtras) {
        const nodesMap = new Map();
        root.descendants().forEach(node => {
            nodesMap.set(node.data.numero, node);
        });
        
        // Filtrar conexões que não estão na árvore principal
        const conexoesExtras = data.conexoesExtras.filter(con => {
            const fromNode = nodesMap.get(con.from);
            const toNode = nodesMap.get(con.to);
            return fromNode && toNode;
        });
        
        // Desenhar conexões extras com estilo diferente e animações
        const linksExtras = svgGroup.selectAll('path.link-extra')
            .data(conexoesExtras, d => `${d.from}-${d.to}`)
            .join('path')
            .attr('class', 'link-extra')
            .attr('fill', 'none')
            .attr('stroke', '#6c757d') // Cor cinza para distinguir
            .attr('stroke-width', 2)
            .attr('stroke-dasharray', '5,5')
            .attr('stroke-linecap', 'round')
            .style('opacity', '0')
            .attr('d', d => {
                const fromNode = nodesMap.get(d.from);
                const toNode = nodesMap.get(d.to);
                if (fromNode && toNode) {
                    return d3.linkHorizontal()
                        .x(d => d.y + 120)
                        .y(d => d.x + 20)
                        .source(() => fromNode)
                        .target(() => toNode)();
                }
                return '';
            })
            .on('mouseover', function(event, d) {
                d3.select(this)
                    .transition().duration(200)
                    .style('stroke-width', '3')
                    .style('opacity', '1');
            })
            .on('mouseout', function(event, d) {
                d3.select(this)
                    .transition().duration(200)
                    .style('stroke-width', '2')
                    .style('opacity', '0.6');
            });

        // Aplicar apenas transição de opacidade para links extras (sem mover posição)
        linksExtras.transition()
            .duration(600)
            .ease(d3.easeQuadInOut)
            .style('opacity', '0.6');
    }
    
    // Desenhar linhas especiais para cards de fim de cadeia
    const fimCadeiaNodes = root.descendants().filter(d => d.data.is_fim_cadeia);
    if (fimCadeiaNodes.length > 0) {
        const linksFimCadeia = svgGroup.selectAll('path.link-fim-cadeia')
            .data(fimCadeiaNodes, d => d.id)
            .join('path')
            .attr('class', 'link-fim-cadeia')
            .attr('fill', 'none')
            .attr('stroke', d => {
                if (d.data.classificacao_fim_cadeia === 'origem_lidima') {
                    return '#28a745'; // Verde para origem lídima
                } else {
                    return '#dc3545'; // Vermelho para sem origem ou inconclusa
                }
            })
            .attr('stroke-width', 3)
            .attr('stroke-dasharray', '8,4')
            .attr('stroke-linecap', 'round')
            .style('opacity', '0')
            .attr('d', d => {
                const docOrigemId = d.data.documento_origem_id;
                if (docOrigemId) {
                    const docOrigem = root.descendants().find(n => n.data.id === docOrigemId);
                    if (docOrigem) {
                        // Linha horizontal conectando o documento origem ao card de fim de cadeia
                        const x1 = docOrigem.y + 120 + 70; // Lado direito do documento origem
                        const y1 = docOrigem.x + 20; // Centro vertical do documento origem
                        const x2 = d.y + 120 - 70; // Lado esquerdo do card de fim de cadeia
                        const y2 = d.x + 20; // Centro vertical do card de fim de cadeia
                        
                        return `M ${x1} ${y1} L ${x2} ${y2}`;
                    }
                }
                return '';
            })
            .on('mouseover', function(event, d) {
                d3.select(this)
                    .transition().duration(200)
                    .style('stroke-width', '5')
                    .style('opacity', '1');
            })
            .on('mouseout', function(event, d) {
                d3.select(this)
                    .transition().duration(200)
                    .style('stroke-width', '3')
                    .style('opacity', '0.8');
            });

        // Aplicar transição de opacidade para links de fim de cadeia
        linksFimCadeia.transition()
            .duration(600)
            .ease(d3.easeQuadInOut)
            .style('opacity', '0.8');
    }

    // Desenhar nós (cards) com animações suaves
    const node = svgGroup.selectAll('g.node')
        .data(root.descendants(), d => d.id)
        .join('g')
        .attr('class', 'node')
        .style('cursor', 'pointer')
        .attr('transform', d => `translate(${d.y + 120},${d.x + 20})`) // Posicionar imediatamente
        .style('opacity', '0') // Começar invisível para animação de entrada
        .on('mouseover', function(event, d) {
            // Destacar o nó atual
            d3.select(this).select('rect')
                .transition().duration(200)
                .attr('stroke-width', 4)
                .attr('filter', 'drop-shadow(0 8px 25px rgba(0,0,0,0.3))');
        })
        .on('mouseout', function(event, d) {
            // Restaurar o nó
            d3.select(this).select('rect')
                .transition().duration(200)
                .attr('stroke-width', d => (d.data.is_importado || d.data.is_compartilhado) ? 3 : 2)
                .attr('filter', 'drop-shadow(0 2px 8px rgba(0,0,0,0.10))');
        });

    // Aplicar apenas transição de opacidade (sem mover posição)
    node.transition()
        .duration(600)
        .ease(d3.easeQuadInOut)
        .style('opacity', '1');

    // Card base
    node.append('rect')
        .attr('width', 140)
        .attr('height', 80)
        .attr('x', -70)
        .attr('y', -40)
        .attr('rx', 12)
        .attr('fill', d => {
            // Cards especiais de fim de cadeia
            if (d.data.is_fim_cadeia) {
                if (d.data.classificacao_fim_cadeia === 'origem_lidima') {
                    return '#28a745'; // Verde para origem lídima
                } else {
                    return '#dc3545'; // Vermelho para sem origem ou inconclusa
                }
            } else if (d.data.tipo_documento === 'transcricao') {
                return '#6f42c1'; // Roxo para transcrição
            } else {
                return '#007bff'; // Azul para matrícula
            }
        })
        .attr('stroke', d => {
            // Cards especiais de fim de cadeia
            if (d.data.is_fim_cadeia) {
                if (d.data.classificacao_fim_cadeia === 'origem_lidima') {
                    return '#1e7e34'; // Verde escuro para origem lídima
                } else {
                    return '#b02a37'; // Vermelho escuro para sem origem ou inconclusa
                }
            }
            // Documentos importados têm borda laranja tracejada
            if (d.data.is_importado) {
                return '#ff8c00'; // Laranja
            }
            // Documentos compartilhados têm borda verde tracejada
            if (d.data.is_compartilhado) {
                return '#28a745'; // Verde
            }
            if (d.data.tipo_documento === 'transcricao') {
                return '#5a32a3'; // Roxo escuro para transcrição
            } else {
                return '#0056b3'; // Azul escuro para matrícula
            }
        })
        .attr('stroke-width', d => (d.data.is_importado || d.data.is_compartilhado) ? 3 : 2)
        .attr('stroke-dasharray', d => {
            // Bordas tracejadas para documentos importados e compartilhados
            if (d.data.is_importado || d.data.is_compartilhado) {
                return '5,5'; // Padrão tracejado
            }
            return 'none'; // Linha sólida
        })
        .attr('filter', 'drop-shadow(0 2px 8px rgba(0,0,0,0.10))')
        .attr('title', d => {
            // Tooltip especial para cards de fim de cadeia
            if (d.data.is_fim_cadeia) {
                let tipo = '';
                if (d.data.tipo_fim_cadeia === 'destacamento_publico' && d.data.sigla_patrimonio_publico) {
                    tipo = `Destacamento Público: ${d.data.sigla_patrimonio_publico}`;
                } else if (d.data.tipo_fim_cadeia === 'outra') {
                    tipo = 'Outra Origem';
                } else {
                    tipo = 'Sem Origem';
                }
                
                let classificacao = '';
                if (d.data.classificacao_fim_cadeia === 'origem_lidima') {
                    classificacao = 'Origem Lídima';
                } else if (d.data.classificacao_fim_cadeia === 'sem_origem') {
                    classificacao = 'Sem Origem';
                } else if (d.data.classificacao_fim_cadeia === 'inconclusa') {
                    classificacao = 'Situação Inconclusa';
                }
                
                return `Fim de Cadeia\nTipo: ${tipo}\nClassificação: ${classificacao}`;
            }
            
            // Tooltip normal para documentos
            return `${d.data.tipo_display} ${d.data.numero}\n${d.data.cartorio}\nLivro: ${d.data.livro}, Folha: ${d.data.folha}\nData: ${d.data.data}\n${d.data.total_lancamentos} lançamentos`;
        })
        .on('mouseover', function() {
            d3.select(this)
                .transition().duration(120)
                .attr('stroke-width', 3)
                .attr('filter', 'drop-shadow(0 6px 20px rgba(0,0,0,0.25))')
                .attr('transform', 'scale(1.06)');
        })
        .on('mouseout', function() {
            d3.select(this)
                .transition().duration(120)
                .attr('stroke-width', 2)
                .attr('filter', 'drop-shadow(0 2px 8px rgba(0,0,0,0.10))')
                .attr('transform', 'scale(1)');
        })
        .on('click', (event, d) => {
            event.stopPropagation();
            // Cards de fim de cadeia não redirecionam
            if (!d.data.is_fim_cadeia) {
                window.location.href = `/dominial/tis/${window.tisId}/imovel/${window.imovelId}/documento/${d.data.id}/detalhado/`;
            }
        });

    // Número do documento
    node.append('text')
        .attr('text-anchor', 'middle')
        .attr('y', -6)
        .attr('fill', 'white')
        .attr('font-size', 20)
        .attr('font-weight', 700)
        .text(d => {
            // Cards especiais de fim de cadeia
            if (d.data.is_fim_cadeia) {
                return d.data.numero || 'FIM';
            }
            // Se for destacamento público e tiver sigla, exibir a sigla
            if (d.data.sigla_patrimonio_publico && d.data.sigla_patrimonio_publico.trim()) {
                return d.data.sigla_patrimonio_publico;
            }
            return d.data.numero || d.data.name || '';
        });

    // Total de lançamentos (não mostrar para cards de fim de cadeia)
    node.filter(d => !d.data.is_fim_cadeia)
        .append('text')
        .attr('text-anchor', 'middle')
        .attr('y', 14)
        .attr('fill', 'white')
        .attr('font-size', 11)
        .attr('opacity', 0.7)
        .text(d => d.data.total_lancamentos !== undefined ? `${d.data.total_lancamentos} lançamentos` : '');

    // Badge de documento importado (laranja)
    node.filter(d => d.data.is_importado)
        .append('circle')
        .attr('cx', 55)
        .attr('cy', -25)
        .attr('r', 8)
        .attr('fill', '#ff8c00') // Laranja
        .attr('stroke', 'white')
        .attr('stroke-width', 2)
        .attr('title', d => {
            let tooltip = d.data.tooltip_importacao || 'Documento importado';
            if (d.data.cadeias_dominiais && d.data.cadeias_dominiais.length > 0) {
                tooltip += '\n\n🌐 Presente em múltiplas cadeias dominiais:';
                d.data.cadeias_dominiais.forEach(cadeia => {
                    tooltip += `\n• ${cadeia.imovel_matricula} (${cadeia.imovel_nome})`;
                });
            }
            return tooltip;
        });

    // Ícone de check para documentos importados
    node.filter(d => d.data.is_importado)
        .append('text')
        .attr('x', 55)
        .attr('y', -21)
        .attr('text-anchor', 'middle')
        .attr('fill', 'white')
        .attr('font-size', 10)
        .attr('font-weight', 'bold')
        .text('✓')
        .attr('title', d => {
            let tooltip = d.data.tooltip_importacao || 'Documento importado';
            if (d.data.cadeias_dominiais && d.data.cadeias_dominiais.length > 0) {
                tooltip += '\n\n🌐 Presente em múltiplas cadeias dominiais:';
                d.data.cadeias_dominiais.forEach(cadeia => {
                    tooltip += `\n• ${cadeia.imovel_matricula} (${cadeia.imovel_nome})`;
                });
            }
            return tooltip;
        });

    // Badge de documento compartilhado (verde)
    node.filter(d => d.data.is_compartilhado && !d.data.is_importado)
        .append('circle')
        .attr('cx', 55)
        .attr('cy', -25)
        .attr('r', 8)
        .attr('fill', '#28a745') // Verde
        .attr('stroke', 'white')
        .attr('stroke-width', 2)
        .attr('title', d => {
            let tooltip = `Documento compartilhado\nCompartilhado em: ${d.data.imoveis_compartilhando.join(', ')}`;
            return tooltip;
        });

    // Ícone de compartilhamento para documentos compartilhados
    node.filter(d => d.data.is_compartilhado && !d.data.is_importado)
        .append('text')
        .attr('x', 55)
        .attr('y', -21)
        .attr('text-anchor', 'middle')
        .attr('fill', 'white')
        .attr('font-size', 10)
        .attr('font-weight', 'bold')
        .text('↔')
        .attr('title', d => {
            let tooltip = `Documento compartilhado\nCompartilhado em: ${d.data.imoveis_compartilhando.join(', ')}`;
            return tooltip;
        });


    // Botões SVG (não mostrar para cards de fim de cadeia)
    const btnGroup = node.filter(d => !d.data.is_fim_cadeia)
        .append('g')
        .attr('class', 'card-buttons')
        .attr('transform', 'translate(0,35)');

    // ➕ Novo lançamento - Centralizado e com melhor contraste
    btnGroup.append('text')
        .attr('x', 0)
        .attr('y', 0)
        .attr('font-size', 16)
        .attr('cursor', 'pointer')
        .attr('opacity', 0.9)
        .attr('text-anchor', 'middle')
        .attr('fill', 'white')
        .attr('font-weight', 'bold')
        .text('➕')
        .on('click', (event, d) => {
            event.stopPropagation();
            window.location.href = `/dominial/tis/${window.tisId}/imovel/${window.imovelId}/novo-lancamento/${d.data.id}/`;
        })
        .on('mouseover', function() {
            d3.select(this)
                .attr('opacity', 1)
                .attr('font-size', 18);
        })
        .on('mouseout', function() {
            d3.select(this)
                .attr('opacity', 0.9)
                .attr('font-size', 16);
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
    const t = window._zoomTransform.rescaleY ? window._zoomTransform : d3.zoomTransform(svg.node());
    svg.transition().duration(200).call(zoom.scaleBy, currentZoom / t.k);
}

window.zoomIn = function() {
    const svg = window._d3svg;
    const zoom = window._d3zoom;
    svg.transition().duration(200).call(zoom.scaleBy, 1.2);
    currentZoom = Math.min(currentZoom * 1.2, maxZoom);
}

window.zoomOut = function() {
    const svg = window._d3svg;
    const zoom = window._d3zoom;
    svg.transition().duration(200).call(zoom.scaleBy, 0.8);
    currentZoom = Math.max(currentZoom * 0.8, minZoom);
}

window.resetZoom = function() {
    const svg = window._d3svg;
    const zoomGroup = window._zoomGroup;
    const width = +svg.attr('width');
    const height = +svg.attr('height');
    
    // Pegar o bounding box do grupo de nós
    const nodes = zoomGroup.selectAll('.node');
    if (nodes.size() === 0) return;
    
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    nodes.each(function() {
        const bbox = this.getBBox();
        const x = +this.getAttribute('transform').split('(')[1].split(',')[0];
        const y = +this.getAttribute('transform').split(',')[1].split(')')[0];
        minX = Math.min(minX, x + bbox.x);
        maxX = Math.max(maxX, x + bbox.x + bbox.width);
        minY = Math.min(minY, y + bbox.y);
        maxY = Math.max(maxY, y + bbox.y + bbox.height);
    });
    
    // Adicionar margem extra para os cards
    minX -= 70;
    maxX += 70;
    minY -= 40;
    maxY += 40;
    
    const treeWidth = maxX - minX;
    const treeHeight = maxY - minY;
    
    // Calcular escala para caber TUDO na div com margem
    const scaleX = (width - 100) / treeWidth;
    const scaleY = (height - 100) / treeHeight;
    const finalScale = Math.min(scaleX, scaleY, 1); // Não aumentar além do tamanho original
    
    // Posicionar o primeiro card na extrema esquerda da div
    const tx = 50 - minX * finalScale; // Margem de 50px da esquerda
    const ty = (height - treeHeight * finalScale) / 2 - minY * finalScale; // Centralizar verticalmente
    
    console.log(`DEBUG: Reset - Árvore: ${treeWidth}x${treeHeight}, Container: ${width}x${height}, Escala: ${finalScale}`);
    
    const t = d3.zoomIdentity.translate(tx, ty).scale(finalScale);
    svg.transition().duration(400).call(window._d3zoom.transform, t);
    window._zoomTransform = t;
    currentZoom = 1;
}

window.fimDaArvore = function() {
    const svg = window._d3svg;
    const zoomGroup = window._zoomGroup;
    const width = +svg.attr('width');
    const height = +svg.attr('height');
    
    // Pegar o bounding box do grupo de nós
    const nodes = zoomGroup.selectAll('.node');
    if (nodes.size() === 0) return;
    
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    nodes.each(function() {
        const bbox = this.getBBox();
        const x = +this.getAttribute('transform').split('(')[1].split(',')[0];
        const y = +this.getAttribute('transform').split(',')[1].split(')')[0];
        minX = Math.min(minX, x + bbox.x);
        maxX = Math.max(maxX, x + bbox.x + bbox.width);
        minY = Math.min(minY, y + bbox.y);
        maxY = Math.max(maxY, y + bbox.y + bbox.height);
    });
    
    // Adicionar margem extra para os cards
    minX -= 70;
    maxX += 70;
    minY -= 40;
    maxY += 40;
    
    const treeWidth = maxX - minX;
    const treeHeight = maxY - minY;
    
    // Calcular escala para focar no último nível (mais à direita)
    const ultimoNivelWidth = 300; // Largura estimada do último nível
    const finalScale = Math.min((width - 100) / ultimoNivelWidth, (height - 100) / treeHeight, 2.0); // Escala maior para zoom
    
    // Posicionar o último nível no centro da div
    const centroUltimoNivel = maxX - (ultimoNivelWidth / 2);
    const tx = (width / 2) - centroUltimoNivel * finalScale;
    const ty = (height - treeHeight * finalScale) / 2 - minY * finalScale; // Centralizar verticalmente
    
    console.log(`DEBUG: Fim da Árvore - Último nível no centro, Escala: ${finalScale}`);
    
    const t = d3.zoomIdentity.translate(tx, ty).scale(finalScale);
    svg.transition().duration(400).call(window._d3zoom.transform, t);
    window._zoomTransform = t;
    currentZoom = 1;
}



function enquadrarArvoreNoSVG(svg, zoomGroup, width, height) {
    // Pega o bounding box do grupo de nós
    const nodes = zoomGroup.selectAll('.node');
    if (nodes.size() === 0) return;
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    nodes.each(function() {
        const bbox = this.getBBox();
        const x = +this.getAttribute('transform').split('(')[1].split(',')[0];
        const y = +this.getAttribute('transform').split(',')[1].split(')')[0];
        minX = Math.min(minX, x + bbox.x);
        maxX = Math.max(maxX, x + bbox.x + bbox.width);
        minY = Math.min(minY, y + bbox.y);
        maxY = Math.max(maxY, y + bbox.y + bbox.height);
    });
    
    // Adicionar margem extra para os cards
    minX -= 70; // metade da largura do card
    maxX += 70;
    minY -= 40; // metade da altura do card
    maxY += 40;
    
    const treeWidth = maxX - minX;
    const treeHeight = maxY - minY;
    
    console.log(`DEBUG: Enquadramento - Árvore: ${treeWidth}x${treeHeight}, Container: ${width}x${height}`);
    console.log(`DEBUG: Enquadramento - minY: ${minY}, maxY: ${maxY}, centro Y: ${(minY + maxY) / 2}`);
    
    // Calcular escala para caber tudo com margem extra
    // Se a árvore for muito grande, não forçar o enquadramento completo
    const scale = Math.min((width - 120) / treeWidth, (height - 120) / treeHeight, 1);
    
    // Para árvores muito grandes, usar uma escala mínima para não ficar muito pequena
    const finalScale = Math.max(scale, 0.3);
    
    // Centralizar a árvore verticalmente na div (não apenas o centro)
    const centroDivX = width / 2;
    const centroDivY = height / 2;
    
    // Calcular translação para centralizar toda a árvore na div
    const tx = centroDivX - (minX + treeWidth / 2) * finalScale;
    const ty = centroDivY - (minY + treeHeight / 2) * finalScale;
    
    console.log(`DEBUG: Centralizando centro da árvore - Centro árvore: (${minX + treeWidth / 2}, ${minY + treeHeight / 2}) -> Centro div: (${centroDivX}, ${centroDivY})`);
    console.log(`DEBUG: Translação calculada - tx: ${tx}, ty: ${ty}, escala: ${finalScale}`);
    
    console.log(`DEBUG: Enquadramento - Escala: ${finalScale}, tx: ${tx}, ty: ${ty}`);
    
    const t = d3.zoomIdentity.translate(tx, ty).scale(finalScale);
    svg.transition().duration(400).call(window._d3zoom.transform, t);
    window._zoomTransform = t;
} 