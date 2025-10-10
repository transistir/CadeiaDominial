// ========================================
// CADEIA DOMINIAL D3 - VERSÃO SIMPLES
// ========================================
// Arquivo limpo e simples para visualização da cadeia dominial
// Sem cálculos complexos - foco na simplicidade e usabilidade

console.log('🌳 Carregando Cadeia Dominial D3 - Versão Simples');

// ========================================
// CONFIGURAÇÕES GLOBAIS
// ========================================
const CONFIG = {
    // Dimensões
    width: 2000,
    height: 800,
    
    // Espaçamentos (ajustáveis pelo usuário)
    spacing: {
        horizontal: 200,  // Entre níveis
        vertical: 120     // Entre nós do mesmo nível
    },
    
    // Cores
    colors: {
        matricula: '#007bff',      // Azul
        transcricao: '#6f42c1',    // Roxo
        importado: '#ff8c00',      // Laranja
        compartilhado: '#28a745'   // Verde
    },
    
    // Tamanhos
    card: {
        width: 140,
        height: 80
    },
    
    // Modo de edição
    edit: {
        enabled: false,
        connectionMode: false,
        selectedNodes: new Set()
    }
};

// ========================================
// VARIÁVEIS GLOBAIS
// ========================================
let svg, zoomGroup, zoom, root, nodes, links;

// ========================================
// INICIALIZAÇÃO
// ========================================
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Inicializando visualização...');
    
    // Criar controles de configuração
    criarControles();
    
    // Inicializar SVG
    inicializarSVG();
    
    // Carregar dados
    carregarDados();
});

// ========================================
// CONTROLES DE CONFIGURAÇÃO
// ========================================
function criarControles() {
    console.log('⚙️ Criando controles...');
    
    // Criar painel de controles
    const controlsPanel = document.createElement('div');
    controlsPanel.id = 'controls-panel';
    controlsPanel.style.cssText = `
        position: fixed;
        top: 10px;
        right: 10px;
        background: white;
        border: 1px solid #ddd;
        border-radius: 8px;
        padding: 15px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        z-index: 1000;
        min-width: 250px;
    `;
    
    controlsPanel.innerHTML = `
        <h4 style="margin: 0 0 15px 0; color: #333;">🎛️ Controles da Árvore</h4>
        
        <div style="margin-bottom: 10px;">
            <label>Espaçamento Horizontal:</label>
            <input type="range" id="spacing-horizontal" min="100" max="400" value="${CONFIG.spacing.horizontal}" 
                   style="width: 100%; margin-top: 5px;">
            <span id="spacing-horizontal-value">${CONFIG.spacing.horizontal}px</span>
        </div>
        
        <div style="margin-bottom: 10px;">
            <label>Espaçamento Vertical:</label>
            <input type="range" id="spacing-vertical" min="80" max="200" value="${CONFIG.spacing.vertical}" 
                   style="width: 100%; margin-top: 5px;">
            <span id="spacing-vertical-value">${CONFIG.spacing.vertical}px</span>
        </div>
        
        <div style="margin-bottom: 15px;">
            <button onclick="renderizarArvore()" style="width: 100%; padding: 8px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer;">
                🔄 Renderizar Árvore
            </button>
        </div>
        
        <div style="margin-bottom: 15px; padding: 10px; background: #f8f9fa; border-radius: 4px;">
            <h5 style="margin: 0 0 10px 0; color: #333;">✏️ Modo de Edição</h5>
            <button id="toggle-edit" onclick="toggleEditMode()" style="width: 100%; padding: 8px; background: #6c757d; color: white; border: none; border-radius: 4px; cursor: pointer; margin-bottom: 8px;">
                🔧 Ativar Edição
            </button>
            <button id="toggle-connection" onclick="toggleConnectionMode()" style="width: 100%; padding: 6px; background: #17a2b8; color: white; border: none; border-radius: 4px; cursor: pointer; margin-bottom: 8px; display: none;">
                🔗 Modo Conexão
            </button>
            <button onclick="exportSVG()" style="width: 100%; padding: 6px; background: #28a745; color: white; border: none; border-radius: 4px; cursor: pointer;">
                💾 Exportar SVG
            </button>
        </div>
        
        <div style="margin-bottom: 10px;">
            <button onclick="centralizarArvore()" style="width: 48%; padding: 6px; background: #28a745; color: white; border: none; border-radius: 4px; cursor: pointer; margin-right: 2%;">
                🎯 Centralizar
            </button>
            <button onclick="resetZoom()" style="width: 48%; padding: 6px; background: #6c757d; color: white; border: none; border-radius: 4px; cursor: pointer;">
                🔍 Reset Zoom
            </button>
        </div>
        
        <div style="font-size: 12px; color: #666; margin-top: 10px;">
            💡 Ajuste os controles e clique em "Renderizar" para aplicar
        </div>
        
        <div id="tree-info" style="font-size: 11px; color: #666; margin-top: 10px; padding: 8px; background: #f8f9fa; border-radius: 4px;">
            📊 Carregando informações...
        </div>
        
    `;
    
    document.body.appendChild(controlsPanel);
    
    // Event listeners para os controles
    document.getElementById('spacing-horizontal').addEventListener('input', function(e) {
        CONFIG.spacing.horizontal = parseInt(e.target.value);
        document.getElementById('spacing-horizontal-value').textContent = e.target.value + 'px';
    });
    
    document.getElementById('spacing-vertical').addEventListener('input', function(e) {
        CONFIG.spacing.vertical = parseInt(e.target.value);
        document.getElementById('spacing-vertical-value').textContent = e.target.value + 'px';
    });
}

// ========================================
// INICIALIZAÇÃO DO SVG
// ========================================
function inicializarSVG() {
    console.log('🎨 Inicializando SVG...');
    
    // Selecionar ou criar SVG
    svg = d3.select('#arvore-d3-svg');
    if (svg.empty()) {
        console.error('❌ SVG não encontrado!');
        return;
    }
    
    // Configurar dimensões
    svg.attr('width', CONFIG.width).attr('height', CONFIG.height);
    
    // Limpar SVG
    svg.selectAll('*').remove();
    
    // Criar grupo para zoom
    zoomGroup = svg.append('g').attr('id', 'zoom-group');
    
    // Configurar zoom
    zoom = d3.zoom()
        .scaleExtent([0.1, 5.0])
        .on('zoom', (event) => {
            zoomGroup.attr('transform', event.transform);
        });
    
    svg.call(zoom);
    
    // Adicionar indicador de carregamento
    zoomGroup.append('text')
        .attr('x', CONFIG.width / 2)
        .attr('y', CONFIG.height / 2)
        .attr('text-anchor', 'middle')
        .style('fill', '#6c757d')
        .style('font-size', '18px')
        .text('Carregando dados...');
}

// ========================================
// CARREGAMENTO DE DADOS
// ========================================
function carregarDados() {
    console.log('📊 Carregando dados do backend...');
    
    const timestamp = new Date().getTime();
    const url = `/dominial/cadeia-dominial/${window.tisId}/${window.imovelId}/arvore/?t=${timestamp}`;
    
    fetch(url)
        .then(response => response.json())
        .then(data => {
            console.log('✅ Dados carregados:', data);
            processarDados(data);
        })
        .catch(error => {
            console.error('❌ Erro ao carregar dados:', error);
            mostrarErro('Erro ao carregar dados: ' + error.message);
        });
}

// ========================================
// PROCESSAMENTO DE DADOS
// ========================================
function processarDados(data) {
    console.log('🔄 Processando dados...');
    
    // Limpar indicador de carregamento
    zoomGroup.selectAll('text').remove();
    
    // DEBUG: Log básico dos dados
    console.log(`📊 ${data.documentos.length} documentos, ${data.conexoes.length} conexões`);
    
    // Construir árvore simples
    root = construirArvoreSimples(data);
    
    // Renderizar árvore inicial
    renderizarArvore();
}


// ========================================
// CONSTRUÇÃO DA ÁRVORE SIMPLES
// ========================================
function construirArvoreSimples(data) {
    console.log('🌳 Construindo árvore simples...');
    
    // Mapear documentos
    const docMap = {};
    data.documentos.forEach(doc => {
        doc.children = [];
        doc.nivel_calculado = doc.nivel || 0; // Nível inicial
        docMap[doc.numero] = doc;
    });
    
    // Encontrar raiz (documento sem origem ou nível 0)
    let raiz = data.documentos.find(doc => doc.nivel === 0 || !doc.origem);
    if (!raiz) raiz = data.documentos[0];
    
    console.log('📍 Raiz encontrada:', raiz.numero, 'nível:', raiz.nivel_calculado);
    
    // Construir árvore usando conexões
    const visitados = new Set();
    const documentosNaArvore = new Set();
    
    function construirRecursivo(node) {
        if (!node || visitados.has(node.numero)) return;
        
        visitados.add(node.numero);
        documentosNaArvore.add(node.numero);
        
        // Buscar filhos (documentos que têm este como origem)
        const filhos = data.conexoes
            .filter(con => con.from === node.numero)
            .map(con => docMap[con.to])
            .filter(doc => doc);
        
        // Adicionar filhos e recalcular níveis
        filhos.forEach(filho => {
            if (!documentosNaArvore.has(filho.numero)) {
                // Recalcular nível: filho sempre tem nível maior que o pai
                const novoNivel = Math.max(filho.nivel_calculado, node.nivel_calculado + 1);
                filho.nivel_calculado = novoNivel;
                
                node.children.push(filho);
                documentosNaArvore.add(filho.numero);
            }
        });
        
        // Processar filhos recursivamente
        node.children.forEach(filho => {
            if (!visitados.has(filho.numero)) {
                construirRecursivo(filho);
            }
        });
    }
    
    construirRecursivo(raiz);
    
    // Verificar se há documentos não visitados
    const documentosNaoVisitados = data.documentos.filter(doc => !visitados.has(doc.numero));
    console.log('✅ Árvore construída com', visitados.size, 'documentos');
    console.log('⚠️ Documentos não visitados:', documentosNaoVisitados.length);
    
    // Conectar documentos órfãos de forma mais simples
    if (documentosNaoVisitados.length > 0) {
        console.log(`\n🔗 Conectando ${documentosNaoVisitados.length} documentos órfãos...`);
        
        documentosNaoVisitados.forEach(doc => {
            let conectado = false;
            
            // 1. Buscar conexão nas conexões do backend
            const conexaoOrigem = data.conexoes.find(con => con.to === doc.numero);
            if (conexaoOrigem) {
                const pai = docMap[conexaoOrigem.from];
                if (pai && documentosNaArvore.has(pai.numero)) {
                    const noPai = encontrarNoNaArvore(raiz, pai.numero);
                    if (noPai) {
                        doc.nivel_calculado = Math.max(doc.nivel_calculado, pai.nivel_calculado + 1);
                        noPai.children.push(doc);
                        documentosNaArvore.add(doc.numero);
                        visitados.add(doc.numero);
                        console.log(`✅ Conectado ${doc.numero} ao pai ${pai.numero} (via conexão backend)`);
                        conectado = true;
                    }
                }
            }
            
            // 2. Se não conectou, tentar pelo campo 'origem'
            if (!conectado && doc.origem && doc.origem.trim()) {
                const docOrigem = docMap[doc.origem];
                if (docOrigem && documentosNaArvore.has(doc.origem)) {
                    const noPai = encontrarNoNaArvore(raiz, doc.origem);
                    if (noPai) {
                        doc.nivel_calculado = Math.max(doc.nivel_calculado, noPai.data.nivel_calculado + 1);
                        noPai.children.push(doc);
                        documentosNaArvore.add(doc.numero);
                        visitados.add(doc.numero);
                        console.log(`✅ Conectado ${doc.numero} ao pai ${doc.origem} (via campo origem)`);
                        conectado = true;
                    }
                }
            }
            
            // 3. Se ainda não conectou, log para debug
            if (!conectado) {
                console.log(`❌ Não foi possível conectar ${doc.numero} - origem: ${doc.origem || 'N/A'}`);
            }
        });
    }
    
    // Segunda passada: tentar conectar documentos que ainda não foram conectados
    const documentosAindaOrfaos = data.documentos.filter(doc => !visitados.has(doc.numero));
    if (documentosAindaOrfaos.length > 0) {
        console.log(`\n🔗 Segunda passada: ${documentosAindaOrfaos.length} documentos ainda órfãos...`);
        
        documentosAindaOrfaos.forEach(doc => {
            if (doc.origem && doc.origem.trim()) {
                const docOrigem = docMap[doc.origem];
                if (docOrigem && documentosNaArvore.has(doc.origem)) {
                    const noPai = encontrarNoNaArvore(raiz, doc.origem);
                    if (noPai) {
                        doc.nivel_calculado = Math.max(doc.nivel_calculado, noPai.data.nivel_calculado + 1);
                        noPai.children.push(doc);
                        documentosNaArvore.add(doc.numero);
                        visitados.add(doc.numero);
                        console.log(`✅ Segunda passada: Conectado ${doc.numero} ao pai ${doc.origem}`);
                    }
                }
            }
        });
    }
    
    // Log final
    const totalConectados = visitados.size;
    const totalDocumentos = data.documentos.length;
    console.log(`\n📊 RESULTADO FINAL: ${totalConectados}/${totalDocumentos} documentos conectados`);
    
    if (totalConectados < totalDocumentos) {
        const aindaOrfaos = data.documentos.filter(doc => !visitados.has(doc.numero));
        console.log(`⚠️ Ainda órfãos: ${aindaOrfaos.map(d => d.numero).join(', ')}`);
    }
    
    return raiz;
}

// Função auxiliar para encontrar um nó na árvore
function encontrarNoNaArvore(node, numero) {
    if (node.numero === numero) return node;
    
    for (let filho of node.children) {
        const encontrado = encontrarNoNaArvore(filho, numero);
        if (encontrado) return encontrado;
    }
    
    return null;
}

// ========================================
// RENDERIZAÇÃO DA ÁRVORE
// ========================================
function renderizarArvore() {
    console.log('🎨 Renderizando árvore...');
    
    if (!root) {
        console.error('❌ Nenhuma árvore para renderizar');
        return;
    }
    
    // Limpar árvore anterior
    zoomGroup.selectAll('.node, .link').remove();
    
    // Converter para hierarquia D3
    const hierarchy = d3.hierarchy(root);
    
    // Aplicar layout simples
    aplicarLayoutSimples(hierarchy);
    
    // Desenhar links
    desenharLinks(hierarchy);
    
    // Adicionar conexões para documentos órfãos conectados
    adicionarConexoesOrfaos(hierarchy);
    
    // Desenhar nós
    desenharNos(hierarchy);
    
    console.log('✅ Árvore renderizada!');
    
    // Atualizar informações da árvore
    atualizarInformacoesArvore(hierarchy);
}

// ========================================
// ATUALIZAR INFORMAÇÕES DA ÁRVORE
// ========================================
function atualizarInformacoesArvore(hierarchy) {
    const nodeData = hierarchy.descendants();
    const niveis = {};
    
    nodeData.forEach(node => {
        const nivel = node.data.nivel_calculado || 0;
        if (!niveis[nivel]) niveis[nivel] = 0;
        niveis[nivel]++;
    });
    
    const totalDocumentos = nodeData.length;
    const totalNiveis = Object.keys(niveis).length;
    const nivelMaximo = Math.max(...Object.keys(niveis).map(Number));
    
    let infoHtml = `
        <strong>📊 Estatísticas da Árvore:</strong><br>
        📄 Total: ${totalDocumentos} documentos<br>
        📐 Níveis: ${totalNiveis} (máximo: ${nivelMaximo})<br>
    `;
    
    // Mostrar distribuição por níveis (apenas os primeiros 5)
    const niveisOrdenados = Object.keys(niveis).sort((a, b) => Number(a) - Number(b));
    niveisOrdenados.slice(0, 5).forEach(nivel => {
        infoHtml += `📊 Nível ${nivel}: ${niveis[nivel]} docs<br>`;
    });
    
    if (niveisOrdenados.length > 5) {
        infoHtml += `... e mais ${niveisOrdenados.length - 5} níveis<br>`;
    }
    
    const infoElement = document.getElementById('tree-info');
    if (infoElement) {
        infoElement.innerHTML = infoHtml;
    }
}

// ========================================
// LAYOUT SIMPLES
// ========================================
function aplicarLayoutSimples(hierarchy) {
    console.log('📐 Aplicando layout simples...');
    
    // Agrupar por nível calculado (não por depth do D3)
    const niveis = {};
    hierarchy.descendants().forEach(node => {
        const nivel = node.data.nivel_calculado || 0;
        if (!niveis[nivel]) niveis[nivel] = [];
        niveis[nivel].push(node);
    });
    
    // Função para ordenar documentos
    function ordenarDocumentos(a, b) {
        const numeroA = a.data.numero;
        const numeroB = b.data.numero;
        
        // Extrair número e tipo
        const matchA = numeroA.match(/^([MT])(\d+)$/);
        const matchB = numeroB.match(/^([MT])(\d+)$/);
        
        if (matchA && matchB) {
            const tipoA = matchA[1];
            const tipoB = matchB[1];
            const numA = parseInt(matchA[2]);
            const numB = parseInt(matchB[2]);
            
            // Priorizar matrículas (M) sobre transcrições (T)
            if (tipoA !== tipoB) {
                if (tipoA === 'M' && tipoB === 'T') return -1; // M vem antes
                if (tipoA === 'T' && tipoB === 'M') return 1;  // M vem antes
            }
            
            // Se mesmo tipo, ordenar por número (maior primeiro)
            return numB - numA;
        }
        
        // Fallback: ordenação alfabética reversa
        return numeroB.localeCompare(numeroA);
    }
    
    // Posicionar nós baseado no nível calculado
    Object.keys(niveis).forEach(nivel => {
        const nosNivel = niveis[nivel];
        
        // Ordenar documentos no nível (maior número primeiro, matrículas antes de transcrições)
        nosNivel.sort(ordenarDocumentos);
        
        const totalNos = nosNivel.length;
        
        nosNivel.forEach((node, index) => {
            // Posição X: baseada no índice no nível
            node.x = (index - (totalNos - 1) / 2) * CONFIG.spacing.vertical;
            
            // Posição Y: baseada no nível calculado
            node.y = nivel * CONFIG.spacing.horizontal;
        });
        
        console.log(`📊 Nível ${nivel}: ${totalNos} documentos`);
    });
    
    console.log('✅ Layout aplicado para', Object.keys(niveis).length, 'níveis calculados');
}

// ========================================
// ADICIONAR CONEXÕES PARA DOCUMENTOS ÓRFÃOS
// ========================================
function adicionarConexoesOrfaos(hierarchy) {
    console.log('🔗 Adicionando conexões para documentos órfãos...');
    
    // Coletar todos os nós da hierarquia
    const todosNos = [];
    hierarchy.each(d => todosNos.push(d));
    
    // Encontrar nós que têm filhos mas não têm links visuais
    const linksExistentes = new Set();
    svg.selectAll('.link').each(function(d) {
        if (d.source && d.target) {
            const chave = `${d.source.data.numero}-${d.target.data.numero}`;
            linksExistentes.add(chave);
        }
    });
    
    // Adicionar links para conexões órfãs
    todosNos.forEach(no => {
        if (no.children && no.children.length > 0) {
            no.children.forEach(filho => {
                const chave = `${no.data.numero}-${filho.data.numero}`;
                if (!linksExistentes.has(chave)) {
                    // Criar link para conexão órfã
                    const link = svg.append('path')
                        .attr('class', 'link')
                        .attr('fill', 'none')
                        .attr('stroke', '#28a745')
                        .attr('stroke-width', 3)
                        .attr('stroke-linecap', 'round')
                        .attr('d', d3.linkHorizontal()
                            .x(d => d.y)
                            .y(d => d.x)
                            .source({
                                x: no.x,
                                y: no.y + CONFIG.card.width / 2
                            })
                            .target({
                                x: filho.x,
                                y: filho.y - CONFIG.card.width / 2
                            })
                        )
                        .on('mouseover', function(event, d) {
                            d3.select(this)
                                .transition().duration(200)
                                .attr('stroke-width', 5)
                                .attr('stroke', '#ff6b35');
                        })
                        .on('mouseout', function(event, d) {
                            d3.select(this)
                                .transition().duration(200)
                                .attr('stroke-width', 3)
                                .attr('stroke', '#28a745');
                        });
                    
                    console.log(`✅ Link órfão criado: ${no.data.numero} -> ${filho.data.numero}`);
                }
            });
        }
    });
}

// ========================================
// DESENHAR LINKS
// ========================================
function desenharLinks(hierarchy) {
    console.log('🔗 Desenhando links...');
    
    const linkData = hierarchy.links();
    
    links = zoomGroup.selectAll('.link')
        .data(linkData)
        .enter()
        .append('path')
        .attr('class', 'link')
        .attr('fill', 'none')
        .attr('stroke', '#28a745')
        .attr('stroke-width', 3)
        .attr('stroke-linecap', 'round')
        .attr('d', d3.linkHorizontal()
            .x(d => d.y)  // Posição Y (horizontal no layout)
            .y(d => d.x)  // Posição X (vertical no layout)
            .source(d => ({
                x: d.source.x,
                y: d.source.y + CONFIG.card.width / 2  // Meio direito do card pai
            }))
            .target(d => ({
                x: d.target.x,
                y: d.target.y - CONFIG.card.width / 2  // Meio esquerdo do card filho
            }))
        )
        .on('mouseover', function(event, d) {
            d3.select(this)
                .transition().duration(200)
                .attr('stroke-width', 5)
                .attr('stroke', '#ff6b35');
        })
        .on('mouseout', function(event, d) {
            d3.select(this)
                .transition().duration(200)
                .attr('stroke-width', 3)
                .attr('stroke', '#28a745');
        });
    
    console.log('✅', linkData.length, 'links desenhados');
}

// ========================================
// DESENHAR NÓS
// ========================================
function desenharNos(hierarchy) {
    console.log('🎯 Desenhando nós...');
    
    let nodeData = hierarchy.descendants();
    
    // Verificar duplicatas
    const numeros = nodeData.map(d => d.data.numero);
    const duplicatas = numeros.filter((numero, index) => numeros.indexOf(numero) !== index);
    
    if (duplicatas.length > 0) {
        console.error('❌ DUPLICATAS ENCONTRADAS:', duplicatas);
        // Remover duplicatas mantendo apenas a primeira ocorrência
        const numerosUnicos = [...new Set(numeros)];
        const nodeDataUnicos = numerosUnicos.map(numero => 
            nodeData.find(d => d.data.numero === numero)
        );
        console.log('🔧 Removendo duplicatas, mantendo', nodeDataUnicos.length, 'nós únicos');
        nodeData = nodeDataUnicos;
    }
    
    nodes = zoomGroup.selectAll('.node')
        .data(nodeData)
        .enter()
        .append('g')
        .attr('class', 'node')
        .attr('transform', d => `translate(${d.y},${d.x})`)
        .style('cursor', d => CONFIG.edit.enabled ? 'move' : 'pointer');
    
    // Desenhar cards
    nodes.append('rect')
        .attr('width', CONFIG.card.width)
        .attr('height', CONFIG.card.height)
        .attr('x', -CONFIG.card.width / 2)
        .attr('y', -CONFIG.card.height / 2)
        .attr('rx', 8)
        .attr('fill', d => {
            if (d.data.tipo_documento === 'transcricao') {
                return CONFIG.colors.transcricao;
            }
            return CONFIG.colors.matricula;
        })
        .attr('stroke', '#333')
        .attr('stroke-width', 2)
        .attr('filter', 'drop-shadow(0 2px 8px rgba(0,0,0,0.15))')
        .on('click', function(event, d) {
            if (CONFIG.edit.enabled) {
                // Modo edição: selecionar nó
                toggleNodeSelection.call(this, d);
            } else if (!d.data.is_fim_cadeia) {
                // Modo visualização: navegar para documento
                window.location.href = `/dominial/tis/${window.tisId}/imovel/${window.imovelId}/documento/${d.data.id}/detalhado/`;
            }
        })
        .on('mouseover', function(event, d) {
            d3.select(this)
                .transition().duration(200)
                .attr('filter', 'drop-shadow(0 4px 12px rgba(0,0,0,0.25))')
                .attr('transform', 'scale(1.05)');
        })
        .on('mouseout', function(event, d) {
            d3.select(this)
                .transition().duration(200)
                .attr('filter', 'drop-shadow(0 2px 8px rgba(0,0,0,0.15))')
                .attr('transform', 'scale(1)');
        });
    
    // Desenhar texto
    nodes.append('text')
        .attr('text-anchor', 'middle')
        .attr('y', 5)
        .attr('fill', 'white')
        .attr('font-size', 16)
        .attr('font-weight', 'bold')
        .text(d => d.data.numero);
    
    // Desenhar total de lançamentos
    nodes.append('text')
        .attr('text-anchor', 'middle')
        .attr('y', 25)
        .attr('fill', 'white')
        .attr('font-size', 12)
        .text(d => `${d.data.total_lancamentos || 0} lançamentos`);
    
    // Desenhar contador de conexões (documentos originados)
    nodes.append('text')
        .attr('text-anchor', 'middle')
        .attr('y', 35)
        .attr('fill', 'white')
        .attr('font-size', 10)
        .attr('opacity', 0.8)
        .text(d => {
            const numConexoes = d.children ? d.children.length : 0;
            return numConexoes > 0 ? `→ ${numConexoes} docs` : '';
        });
    
    // Adicionar drag & drop se modo edição estiver ativo
    if (CONFIG.edit.enabled) {
        addDragAndDrop(nodes);
    }
    
    console.log('✅', nodeData.length, 'nós desenhados');
}

// ========================================
// FUNÇÕES DE CONTROLE
// ========================================
function centralizarArvore() {
    console.log('🎯 Centralizando árvore...');
    
    if (!nodes || nodes.empty()) return;
    
    // Calcular bounding box
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
    
    // Calcular centro
    const centroX = (minX + maxX) / 2;
    const centroY = (minY + maxY) / 2;
    
    // Centralizar
    const tx = CONFIG.width / 2 - centroX;
    const ty = CONFIG.height / 2 - centroY;
    
    const t = d3.zoomIdentity.translate(tx, ty);
    svg.transition().duration(500).call(zoom.transform, t);
    
    console.log('✅ Árvore centralizada');
}

function resetZoom() {
    console.log('🔍 Resetando zoom...');
    
    const t = d3.zoomIdentity;
    svg.transition().duration(500).call(zoom.transform, t);
    
    console.log('✅ Zoom resetado');
}

// ========================================
// FUNÇÕES AUXILIARES
// ========================================
function mostrarErro(mensagem) {
    zoomGroup.selectAll('*').remove();
    zoomGroup.append('text')
        .attr('x', CONFIG.width / 2)
        .attr('y', CONFIG.height / 2)
        .attr('text-anchor', 'middle')
        .style('fill', '#dc3545')
        .style('font-size', '16px')
        .text(mensagem);
}


// ========================================
// FUNÇÕES DE EDIÇÃO
// ========================================
function toggleEditMode() {
    CONFIG.edit.enabled = !CONFIG.edit.enabled;
    const button = document.getElementById('toggle-edit');
    const connectionButton = document.getElementById('toggle-connection');
    
    if (CONFIG.edit.enabled) {
        button.textContent = '🔧 Desativar Edição';
        button.style.background = '#dc3545';
        connectionButton.style.display = 'block';
        console.log('✏️ Modo de edição ATIVADO');
    } else {
        button.textContent = '🔧 Ativar Edição';
        button.style.background = '#6c757d';
        connectionButton.style.display = 'none';
        CONFIG.edit.connectionMode = false;
        CONFIG.edit.selectedNodes.clear();
        console.log('👁️ Modo de visualização ATIVADO');
    }
    
    // Re-renderizar para aplicar mudanças
    if (root) {
        renderizarArvore();
    }
}

function toggleConnectionMode() {
    CONFIG.edit.connectionMode = !CONFIG.edit.connectionMode;
    const button = document.getElementById('toggle-connection');
    
    if (CONFIG.edit.connectionMode) {
        button.textContent = '🔗 Cancelar Conexão';
        button.style.background = '#dc3545';
        console.log('🔗 Modo de conexão ATIVADO - clique em dois nós para conectar');
        
        // Mostrar instrução visual
        showConnectionInstructions();
    } else {
        button.textContent = '🔗 Modo Conexão';
        button.style.background = '#17a2b8';
        CONFIG.edit.selectedNodes.clear();
        console.log('🔗 Modo de conexão DESATIVADO');
        
        // Limpar instruções e seleções
        hideConnectionInstructions();
        d3.selectAll('.node rect').attr('stroke', '#333').attr('stroke-width', 2);
    }
}

function toggleNodeSelection(d) {
    if (!CONFIG.edit.enabled) return;
    
    console.log('🖱️ Clicando no documento:', d.data.numero, 'Modo conexão:', CONFIG.edit.connectionMode);
    
    // Usar o elemento atual (this) que é o grupo do nó
    const nodeElement = d3.select(this);
    console.log('🎯 Elemento encontrado:', !nodeElement.empty());
    
    if (CONFIG.edit.connectionMode) {
        // Modo conexão: selecionar nós para conectar
        if (CONFIG.edit.selectedNodes.has(d.data.numero)) {
            // Deselecionar
            console.log('🔄 Deselecionando documento:', d.data.numero);
            CONFIG.edit.selectedNodes.delete(d.data.numero);
            if (!nodeElement.empty()) {
                nodeElement.select('rect').attr('stroke', '#333').attr('stroke-width', 2);
            }
            updateConnectionInstructions();
        } else {
            // Selecionar
            console.log('✅ Selecionando documento:', d.data.numero);
            CONFIG.edit.selectedNodes.add(d.data.numero);
            if (!nodeElement.empty()) {
                nodeElement.select('rect').attr('stroke', '#ff6b35').attr('stroke-width', 4);
            }
            updateConnectionInstructions();
            
            console.log('📊 Total selecionados:', CONFIG.edit.selectedNodes.size);
            if (CONFIG.edit.selectedNodes.size === 2) {
                console.log('🔗 Dois documentos selecionados, criando conexão...');
                // Criar conexão entre os dois nós selecionados
                createConnection();
            }
        }
    } else {
        // Modo normal: apenas selecionar
        if (CONFIG.edit.selectedNodes.has(d.data.numero)) {
            CONFIG.edit.selectedNodes.delete(d.data.numero);
            if (!nodeElement.empty()) {
                nodeElement.select('rect').attr('stroke', '#333').attr('stroke-width', 2);
            }
        } else {
            CONFIG.edit.selectedNodes.clear();
            CONFIG.edit.selectedNodes.add(d.data.numero);
            // Limpar seleções anteriores
            d3.selectAll('.node rect').attr('stroke', '#333').attr('stroke-width', 2);
            // Selecionar atual
            if (!nodeElement.empty()) {
                nodeElement.select('rect').attr('stroke', '#ff6b35').attr('stroke-width', 4);
            }
        }
    }
}

function createConnection() {
    console.log('🚀 createConnection() chamada!');
    const selectedArray = Array.from(CONFIG.edit.selectedNodes);
    console.log('📋 Documentos selecionados:', selectedArray);
    
    if (selectedArray.length !== 2) {
        console.log('❌ Número incorreto de documentos selecionados:', selectedArray.length);
        return;
    }
    
    const [from, to] = selectedArray;
    console.log(`🔗 Criando conexão: ${from} -> ${to}`);
    
    // Encontrar os nós na árvore
    const fromNode = findNodeInTree(root, from);
    const toNode = findNodeInTree(root, to);
    
    console.log('🔍 Nós encontrados:', { fromNode: !!fromNode, toNode: !!toNode });
    
    if (fromNode && toNode) {
        // Adicionar conexão na estrutura de dados
        if (!fromNode.children) fromNode.children = [];
        if (!fromNode.children.find(child => child.numero === to)) {
            // Criar uma referência ao nó existente, não duplicar
            fromNode.children.push(toNode);
            console.log(`✅ Conexão adicionada na estrutura: ${from} -> ${to}`);
        }
        
        // Criar link visual
        createSimpleLink(from, to);
        
        // Mostrar feedback
        alert(`Conexão criada: ${from} -> ${to}`);
    } else {
        console.error('❌ Não foi possível encontrar os nós:', from, to);
        alert('Erro: Não foi possível criar a conexão');
    }
    
    // Limpar seleção
    CONFIG.edit.selectedNodes.clear();
    d3.selectAll('.node rect').attr('stroke', '#333').attr('stroke-width', 2);
    toggleConnectionMode();
}

function addDragAndDrop(nodes) {
    const drag = d3.drag()
        .on('start', function(event, d) {
            console.log('🖱️ Iniciando drag:', d.data.numero);
            d3.select(this).raise();
            
            // Armazenar offset inicial para manter posição relativa ao mouse
            d.dragOffset = {
                x: event.x - d.y,
                y: event.y - d.x
            };
        })
        .on('drag', function(event, d) {
            // Calcular nova posição considerando o offset
            const newX = event.y - d.dragOffset.y;
            const newY = event.x - d.dragOffset.x;
            
            // Atualizar posição do nó
            d.x = newX;
            d.y = newY;
            
            // Atualizar transform
            d3.select(this)
                .attr('transform', `translate(${d.y},${d.x})`);
            
            // Atualizar links conectados
            updateConnectedLinks(d);
        })
        .on('end', function(event, d) {
            console.log('✅ Drag finalizado:', d.data.numero, 'posição:', d.x, d.y);
            // Limpar offset
            delete d.dragOffset;
        });
    
    nodes.call(drag);
}

function updateConnectedLinks(node) {
    // Atualizar links que conectam a este nó
    d3.selectAll('.link').each(function(d) {
        // Verificar se d existe e tem as propriedades necessárias
        if (d && d.source && d.target && d.source.data && d.target.data) {
            if (d.source.data.numero === node.data.numero || d.target.data.numero === node.data.numero) {
                d3.select(this)
                    .attr('d', d3.linkHorizontal()
                        .x(d => d.y)
                        .y(d => d.x)
                        .source(d => ({
                            x: d.source.x,
                            y: d.source.y + CONFIG.card.width / 2
                        }))
                        .target(d => ({
                            x: d.target.x,
                            y: d.target.y - CONFIG.card.width / 2
                        }))
                    );
            }
        }
    });
    
    // Atualizar links manuais também
    d3.selectAll('.manual-link').each(function(d) {
        if (d && d.source && d.target) {
            // Encontrar os elementos dos nós conectados
            const fromElement = d3.selectAll('.node').filter(function() {
                const nodeData = d3.select(this).datum();
                return nodeData && nodeData.data && nodeData.data.numero === d.source.numero;
            });
            
            const toElement = d3.selectAll('.node').filter(function() {
                const nodeData = d3.select(this).datum();
                return nodeData && nodeData.data && nodeData.data.numero === d.target.numero;
            });
            
            if (!fromElement.empty() && !toElement.empty()) {
                // Obter posições atuais dos elementos
                const fromTransform = fromElement.attr('transform');
                const toTransform = toElement.attr('transform');
                
                const fromMatch = fromTransform.match(/translate\(([^,]+),([^)]+)\)/);
                const toMatch = toTransform.match(/translate\(([^,]+),([^)]+)\)/);
                
                if (fromMatch && toMatch) {
                    const fromX = parseFloat(fromMatch[2]);
                    const fromY = parseFloat(fromMatch[1]);
                    const toX = parseFloat(toMatch[2]);
                    const toY = parseFloat(toMatch[1]);
                    
                    // Atualizar dados do link com posições atuais
                    d.source.x = fromX;
                    d.source.y = fromY + CONFIG.card.width / 2;
                    d.target.x = toX;
                    d.target.y = toY - CONFIG.card.width / 2;
                    
                    // Redesenhar o link
                    d3.select(this)
                        .attr('d', d3.linkHorizontal()
                            .x(d => d.y)
                            .y(d => d.x)
                            .source(d => d.source)
                            .target(d => d.target)
                        );
                }
            }
        }
    });
}

function showConnectionInstructions() {
    // Remover instruções anteriores se existirem
    hideConnectionInstructions();
    
    // Criar div de instruções
    const instructions = document.createElement('div');
    instructions.id = 'connection-instructions';
    instructions.style.cssText = `
        position: fixed;
        top: 20px;
        left: 20px;
        background: rgba(0, 0, 0, 0.9);
        color: white;
        padding: 15px;
        border-radius: 8px;
        z-index: 2000;
        text-align: left;
        font-size: 14px;
        max-width: 300px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    `;
    
    instructions.innerHTML = `
        <h3 style="margin: 0 0 15px 0;">🔗 Modo de Conexão</h3>
        <p style="margin: 0 0 10px 0;">Clique em <strong>dois documentos</strong> para criar uma conexão</p>
        <p style="margin: 0 0 15px 0; font-size: 14px; opacity: 0.8;">Os documentos selecionados ficarão com borda laranja</p>
        <button onclick="toggleConnectionMode()" style="padding: 8px 16px; background: #dc3545; color: white; border: none; border-radius: 4px; cursor: pointer;">
            Cancelar
        </button>
    `;
    
    document.body.appendChild(instructions);
}

function hideConnectionInstructions() {
    const instructions = document.getElementById('connection-instructions');
    if (instructions) {
        instructions.remove();
    }
}

function updateConnectionInstructions() {
    const instructions = document.getElementById('connection-instructions');
    if (instructions) {
        const selectedCount = CONFIG.edit.selectedNodes.size;
        const statusText = instructions.querySelector('p');
        
        console.log('🔗 Atualizando instruções - selecionados:', selectedCount);
        
        if (selectedCount === 0) {
            statusText.textContent = 'Clique em dois documentos para criar uma conexão';
        } else if (selectedCount === 1) {
            const selectedDoc = Array.from(CONFIG.edit.selectedNodes)[0];
            statusText.textContent = `Selecionado: ${selectedDoc}. Clique em outro documento para conectar`;
        } else {
            statusText.textContent = 'Criando conexão...';
        }
    }
}

function findNodeInTree(node, numero) {
    if (node.numero === numero) return node;
    
    if (node.children) {
        for (let child of node.children) {
            const found = findNodeInTree(child, numero);
            if (found) return found;
        }
    }
    
    return null;
}

function createSimpleLink(fromNumero, toNumero) {
    console.log('🎨 Criando link simples:', fromNumero, '->', toNumero);
    
    // Verificar se já existe uma conexão entre estes dois documentos
    const linkId = `manual-link-${fromNumero}-${toNumero}`;
    const reverseLinkId = `manual-link-${toNumero}-${fromNumero}`;
    
    if (d3.select(`#${linkId}`).size() > 0 || d3.select(`#${reverseLinkId}`).size() > 0) {
        console.log('⚠️ Conexão já existe entre', fromNumero, 'e', toNumero);
        return;
    }
    
    // Encontrar os elementos SVG dos nós
    const fromElement = d3.selectAll('.node').filter(function() {
        return d3.select(this).datum().data.numero === fromNumero;
    });
    
    const toElement = d3.selectAll('.node').filter(function() {
        return d3.select(this).datum().data.numero === toNumero;
    });
    
    if (!fromElement.empty() && !toElement.empty()) {
        // Obter posições atuais dos elementos
        const fromTransform = fromElement.attr('transform');
        const toTransform = toElement.attr('transform');
        
        // Extrair coordenadas do transform
        const fromMatch = fromTransform.match(/translate\(([^,]+),([^)]+)\)/);
        const toMatch = toTransform.match(/translate\(([^,]+),([^)]+)\)/);
        
        if (fromMatch && toMatch) {
            const fromX = parseFloat(fromMatch[2]);
            const fromY = parseFloat(fromMatch[1]);
            const toX = parseFloat(toMatch[2]);
            const toY = parseFloat(toMatch[1]);
            
            console.log('📍 Posições:', { fromX, fromY, toX, toY });
            
            // Calcular pontos de conexão corretos
            const fromCenterX = fromX;
            const fromCenterY = fromY + CONFIG.card.width / 2;
            const toCenterX = toX;
            const toCenterY = toY - CONFIG.card.width / 2;
            
            console.log('🎯 Pontos de conexão:', { 
                from: { x: fromCenterX, y: fromCenterY }, 
                to: { x: toCenterX, y: toCenterY } 
            });
            
            // Criar linha bezier que acompanha os cards
            const linkData = {
                source: { x: fromCenterX, y: fromCenterY, numero: fromNumero },
                target: { x: toCenterX, y: toCenterY, numero: toNumero }
            };
            
            const link = zoomGroup.append('path')
                .attr('class', 'manual-link')
                .attr('id', linkId)
                .datum(linkData)
                .attr('fill', 'none')
                .attr('stroke', '#28a745')  // VERDE igual às outras conexões
                .attr('stroke-width', 3)    // Mesma espessura das outras
                .attr('stroke-linecap', 'round')
                .attr('d', d3.linkHorizontal()
                    .x(d => d.y)
                    .y(d => d.x)
                    .source(d => d.source)
                    .target(d => d.target)
                )
                .style('z-index', '1000')
                .on('mouseover', function() {
                    d3.select(this)
                        .transition().duration(200)
                        .attr('stroke-width', 5)
                        .attr('stroke', '#ff6b35');
                })
                .on('mouseout', function() {
                    d3.select(this)
                        .transition().duration(200)
                        .attr('stroke-width', 3)
                        .attr('stroke', '#28a745');
                });
            
            console.log('✅ Link simples criado com sucesso!');
        } else {
            console.error('❌ Não foi possível extrair coordenadas dos transforms');
        }
    } else {
        console.error('❌ Não foi possível encontrar elementos SVG dos nós');
    }
}

function exportSVG() {
    console.log('💾 Exportando SVG...');
    
    // Obter o SVG como string
    const svgElement = document.getElementById('arvore-d3-svg');
    const svgData = new XMLSerializer().serializeToString(svgElement);
    
    // Criar blob e download
    const blob = new Blob([svgData], { type: 'image/svg+xml' });
    const url = URL.createObjectURL(blob);
    
    const link = document.createElement('a');
    link.href = url;
    link.download = `cadeia-dominial-${window.imovelId}-${new Date().toISOString().split('T')[0]}.svg`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    URL.revokeObjectURL(url);
    console.log('✅ SVG exportado com sucesso!');
}

// ========================================
// EXPORTAR FUNÇÕES GLOBAIS
// ========================================
window.renderizarArvore = renderizarArvore;
window.centralizarArvore = centralizarArvore;
window.resetZoom = resetZoom;
window.toggleEditMode = toggleEditMode;
window.toggleConnectionMode = toggleConnectionMode;
window.exportSVG = exportSVG;
window.showConnectionInstructions = showConnectionInstructions;
window.hideConnectionInstructions = hideConnectionInstructions;

console.log('✅ Cadeia Dominial D3 - Versão Simples com Edição carregada!');
