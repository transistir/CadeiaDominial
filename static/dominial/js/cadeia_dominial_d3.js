// JS para visualização D3 da cadeia dominial
// Busca os dados da árvore e renderiza usando d3.tree()

// Definir função expandirArvore globalmente imediatamente
window.expandirArvore = function() {
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
};

document.addEventListener('DOMContentLoaded', function() {
    const svg = d3.select('#arvore-d3-svg');
    const width = document.getElementById('arvore-d3-svg').clientWidth || 1000;
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

    // Buscar dados da árvore (corrigido)
    fetch(`/dominial/cadeia-dominial/${window.tisId}/${window.imovelId}/arvore/`)
        .then(response => response.json())
        .then(data => {
            // Converter para formato de árvore
            const arvore = converterParaArvoreD3(data);
            renderArvoreD3(arvore, zoomGroup, width, height);
            // Enquadrar após renderizar
            setTimeout(() => enquadrarArvoreNoSVG(svg, zoomGroup, width, height), 100);
        })
        .catch(err => {
            svg.append('text')
                .attr('x', width/2)
                .attr('y', height/2)
                .attr('text-anchor', 'middle')
                .attr('fill', 'red')
                .text('Erro ao carregar dados da árvore');
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
    let espacamentoHorizontal = 200; // padrão
    if (maxNos > 20) {
        espacamentoHorizontal = 400; // muito espaçado para muitos nós
    } else if (maxNos > 15) {
        espacamentoHorizontal = 350; // muito espaçado para muitos nós
    } else if (maxNos > 10) {
        espacamentoHorizontal = 300; // espaçado para muitos nós
    } else if (maxNos > 6) {
        espacamentoHorizontal = 250; // moderadamente espaçado
    }
    
    return espacamentoHorizontal;
}

// Corrigir sobreposições pós-processamento - VERSÃO MELHORADA
function corrigirSobreposicoes(root) {
    // Agrupar nós por profundidade (nível)
    const niveis = {};
    root.descendants().forEach(node => {
        if (!niveis[node.depth]) niveis[node.depth] = [];
        niveis[node.depth].push(node);
    });
    
    // Para cada nível, ajustar posições se necessário
    Object.keys(niveis).forEach(depth => {
        const nosNivel = niveis[depth];
        if (nosNivel.length > 1) {
            // Ordenar por posição Y
            nosNivel.sort((a, b) => a.x - b.x);
            
            // Calcular espaçamento mínimo necessário baseado no tamanho real dos cards
            const alturaCard = 80; // altura do card
            const margemVertical = 40; // margem entre cards
            const espacamentoMinimo = alturaCard + margemVertical;
            
            // Verificar se há sobreposição
            let temSobreposicao = false;
            for (let i = 0; i < nosNivel.length - 1; i++) {
                const distancia = nosNivel[i + 1].x - nosNivel[i].x;
                if (distancia < espacamentoMinimo) {
                    temSobreposicao = true;
                    break;
                }
            }
            
            // Se há sobreposição, redistribuir os nós
            if (temSobreposicao) {
                const larguraTotal = (nosNivel.length - 1) * espacamentoMinimo;
                const inicio = nosNivel[0].x - (larguraTotal / 2);
                
                nosNivel.forEach((node, index) => {
                    node.x = inicio + (index * espacamentoMinimo);
                });
            }
        }
    });
}

// NOVA FUNÇÃO: Aplicar espaçamento adicional para evitar sobreposições
function aplicarEspacamentoAdicional(root) {
    // Agrupar nós por profundidade
    const niveis = {};
    root.descendants().forEach(node => {
        if (!niveis[node.depth]) niveis[node.depth] = [];
        niveis[node.depth].push(node);
    });
    
    // Para cada nível, verificar se precisa de mais espaçamento
    Object.keys(niveis).forEach(depth => {
        const nosNivel = niveis[depth];
        if (nosNivel.length > 1) {
            // Ordenar por posição X
            nosNivel.sort((a, b) => a.x - b.x);
            
            // Calcular espaçamento atual
            const espacamentoAtual = (nosNivel[nosNivel.length - 1].x - nosNivel[0].x) / (nosNivel.length - 1);
            const espacamentoMinimo = 120; // altura do card + margem
            
            // Se o espaçamento atual é muito pequeno, expandir
            if (espacamentoAtual < espacamentoMinimo) {
                const fatorExpansao = espacamentoMinimo / espacamentoAtual;
                const larguraTotal = (nosNivel.length - 1) * espacamentoMinimo;
                const inicio = nosNivel[0].x - (larguraTotal / 2);
                
                nosNivel.forEach((node, index) => {
                    node.x = inicio + (index * espacamentoMinimo);
                });
            }
        }
    });
}



function renderArvoreD3(data, svgGroup, width, height) {
    // Converter para d3.hierarchy
    const root = d3.hierarchy(data);
    
    // Calcular espaçamento adaptativo
    const espacamentoHorizontal = calcularEspacamentoAdaptativo(root);
    
    // Configurar layout da árvore com espaçamento adaptativo melhorado
    const treeLayout = d3.tree()
        .size([height * 2.0, width - 280]) // Aumentar altura disponível
        .separation((a, b) => {
            // Aumentar separação entre nós irmãos quando há muitos
            const irmaos = a.parent ? a.parent.children.length : 1;
            if (irmaos > 15) {
                return 3.0; // Triplicar a separação para muitos nós
            } else if (irmaos > 10) {
                return 2.0; // Dobrar a separação
            } else if (irmaos > 6) {
                return 1.5; // Aumentar 50%
            }
            return 1.0; // Separação padrão
        });
    
    treeLayout(root);
    
    // Aplicar correção de sobreposições melhorada
    corrigirSobreposicoes(root);
    
    // Aplicar espaçamento adicional se necessário
    aplicarEspacamentoAdicional(root);

    // Desenhar links da árvore principal
    svgGroup.selectAll('path.link')
        .data(root.links())
        .enter()
        .append('path')
        .attr('class', 'link')
        .attr('fill', 'none')
        .attr('stroke', '#28a745')
        .attr('stroke-width', 2)
        .attr('d', d3.linkHorizontal()
            .x(d => d.y + 120)
            .y(d => d.x + 20)
        );
    
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
        
        // Desenhar conexões extras com estilo diferente
        svgGroup.selectAll('path.link-extra')
            .data(conexoesExtras)
            .enter()
            .append('path')
            .attr('class', 'link-extra')
            .attr('fill', 'none')
            .attr('stroke', '#28a745') // Mesma cor verde das conexões principais
            .attr('stroke-width', 2) // Mesma espessura
            .attr('stroke-dasharray', '5,5') // Linha tracejada para distinguir
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
            });
    }

    // Desenhar nós (cards)
    const node = svgGroup.selectAll('g.node')
        .data(root.descendants())
        .enter()
        .append('g')
        .attr('class', 'node')
        .attr('transform', d => `translate(${d.y + 120},${d.x + 20})`)
        .style('cursor', 'pointer');

    // Card base
    node.append('rect')
        .attr('width', 140)
        .attr('height', 80)
        .attr('x', -70)
        .attr('y', -40)
        .attr('rx', 12)
        .attr('fill', d => d.data.tipo === 'transcricao' ? '#6f42c1' : '#007bff')
        .attr('stroke', d => {
            // Documentos importados têm borda laranja tracejada
            if (d.data.is_importado) {
                return '#ff8c00'; // Laranja
            }
            // Documentos compartilhados têm borda verde tracejada
            if (d.data.is_compartilhado) {
                return '#28a745'; // Verde
            }
            return d.data.tipo === 'transcricao' ? '#5a32a3' : '#0056b3';
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
            window.location.href = `/dominial/tis/${window.tisId}/imovel/${window.imovelId}/documento/${d.data.id}/detalhado/`;
        });

    // Número do documento
    node.append('text')
        .attr('text-anchor', 'middle')
        .attr('y', -6)
        .attr('fill', 'white')
        .attr('font-size', 20)
        .attr('font-weight', 700)
        .text(d => d.data.numero || d.data.name || '');

    // Total de lançamentos
    node.append('text')
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

    // Botões SVG
    const btnGroup = node.append('g')
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
    centralizarArvore(svg.attr('width'), svg.attr('height'));
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
    
    // Calcular escala para caber tudo com margem extra
    const scale = Math.min((width - 120) / treeWidth, (height - 120) / treeHeight, 1);
    
    // Centralizar com margem extra
    const tx = (width - treeWidth * scale) / 2 - minX * scale;
    const ty = (height - treeHeight * scale) / 2 - minY * scale;
    const t = d3.zoomIdentity.translate(tx, ty).scale(scale);
    svg.transition().duration(400).call(window._d3zoom.transform, t);
    window._zoomTransform = t;
} 