// JavaScript extraído do template cadeia_dominial_arvore.html
// (Conteúdo transferido do bloco <script> para este arquivo)

let arvoreData = null;
let zoomLevel = 1;
let isDragging = false;
let dragStart = { x: 0, y: 0 };
let panOffset = { x: 0, y: 0 };

// Carregar dados da árvore
async function carregarDadosArvore() {
    try {
        const url = `/dominial/cadeia-dominial/${window.tisId}/${window.imovelId}/arvore/`;
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`Erro HTTP: ${response.status} ${response.statusText}`);
        }
        const data = await response.json();
        arvoreData = data;
        renderizarArvore();
    } catch (error) {
        console.error('Erro ao carregar dados da árvore:', error);
        document.getElementById('arvore-container').innerHTML = 
            `<div class="error">Erro ao carregar dados da árvore: ${error.message}</div>`;
    }
}

// Carregar dados quando a página carregar
document.addEventListener('DOMContentLoaded', function() {
    carregarDadosArvore();
    configurarPan();
});

function renderizarArvore() {
    const container = document.getElementById('arvore-container');
    const zoomContent = document.getElementById('arvore-zoom-content');
    if (!container || !zoomContent || !arvoreData) return;
    zoomContent.innerHTML = '';
    const posicoes = renderizarDocumentos(zoomContent);
    renderizarOrigensIdentificadas(zoomContent);
}

// Renderizar documentos
function renderizarDocumentos(zoomContent) {
    const container = document.getElementById('arvore-container');
    const posicoes = {};
    
    // Ordenar documentos por nível (matrícula primeiro, depois transcrições)
    const documentosOrdenados = [...arvoreData.documentos].sort((a, b) => {
        if (a.tipo === 'matricula' && b.tipo !== 'matricula') return -1;
        if (a.tipo !== 'matricula' && b.tipo === 'matricula') return 1;
        return 0;
    });
    
    // Calcular tamanho dos cards baseado na quantidade de documentos
    const totalDocumentos = documentosOrdenados.length;
    let cardSize = 'medium'; // padrão
    let espacamentoX = 160; // espaçamento padrão (aumentado de 140 para 160)
    
    if (totalDocumentos <= 3) {
        cardSize = 'large';
        espacamentoX = 180; // aumentado de 160 para 180
    } else if (totalDocumentos <= 6) {
        cardSize = 'medium';
        espacamentoX = 160; // aumentado de 140 para 160
    } else {
        cardSize = 'small';
        espacamentoX = 140; // aumentado de 120 para 140
    }
    
    // Aplicar tamanho aos documentos
    documentosOrdenados.forEach(doc => {
        doc.size = cardSize;
    });
    
    // Posicionar documentos baseado nos níveis calculados pelo backend
    const documentosPorNivel = {};
    documentosOrdenados.forEach(doc => {
        const nivel = doc.nivel || 0;
        if (!documentosPorNivel[nivel]) {
            documentosPorNivel[nivel] = [];
        }
        documentosPorNivel[nivel].push(doc);
    });
    
    // Posicionar documentos nível por nível
    Object.keys(documentosPorNivel).sort((a, b) => parseInt(a) - parseInt(b)).forEach(nivel => {
        const documentosNivel = documentosPorNivel[nivel];
        const y = 10 + parseInt(nivel) * 150; // 10px do topo + 150px por nível
        
        // Ordenar documentos do nível: matrículas primeiro, depois transcrições, ambos do maior para o menor
        documentosNivel.sort((a, b) => {
            // Primeiro: priorizar matrículas sobre transcrições
            if (a.tipo === 'matricula' && b.tipo !== 'matricula') return -1;
            if (a.tipo !== 'matricula' && b.tipo === 'matricula') return 1;
            
            // Segundo: ordenar por número (maior primeiro)
            const numA = parseInt(a.numero.replace(/[MT]/g, ''));
            const numB = parseInt(b.numero.replace(/[MT]/g, ''));
            return numB - numA; // Maior primeiro
        });
        
        documentosNivel.forEach((doc, index) => {
            const card = criarCardDocumento(doc);
            const centerX = container.offsetWidth / 2 || 600;
            const cardWidth = cardSize === 'large' ? 70 : cardSize === 'medium' ? 60 : 50;
            
            // Distribuir horizontalmente no nível
            const totalWidth = documentosNivel.length * espacamentoX;
            const startX = centerX - (totalWidth / 2) + (espacamentoX / 2);
            const x = startX + index * espacamentoX;
            
            card.style.left = `${x}px`;
            card.style.top = `${y}px`;
            zoomContent.appendChild(card);
            posicoes[doc.numero] = { x, y };
        });
    });
    
    // Criar conexões visuais entre documentos
    if (arvoreData.conexoes && arvoreData.conexoes.length > 0) {
        arvoreData.conexoes.forEach(conexao => {
            const fromPos = posicoes[conexao.from];
            const toPos = posicoes[conexao.to];
            
            if (fromPos && toPos) {
                const conexaoEl = document.createElement('div');
                conexaoEl.className = 'conexao';
                conexaoEl.style.zIndex = '1';
                
                // Calcular posição e ângulo da conexão
                const cardWidth = cardSize === 'large' ? 70 : cardSize === 'medium' ? 60 : 50;
                const cardHeight = cardSize === 'large' ? 90 : cardSize === 'medium' ? 80 : 70;
                
                // Posições nas bordas dos cards
                const fromX = fromPos.x + cardWidth; // Borda direita do card origem
                const fromY = fromPos.y + (cardHeight / 2); // Centro vertical do card origem
                const toX = toPos.x; // Borda esquerda do card destino
                const toY = toPos.y + (cardHeight / 2); // Centro vertical do card destino
                
                const dx = toX - fromX;
                const dy = toY - fromY;
                const distancia = Math.sqrt(dx * dx + dy * dy);
                const angulo = Math.atan2(dy, dx) * 180 / Math.PI;
                
                // Posicionar a linha
                conexaoEl.style.width = `${distancia}px`;
                conexaoEl.style.left = `${fromX}px`;
                conexaoEl.style.top = `${fromY}px`;
                conexaoEl.style.transform = `rotate(${angulo}deg)`;
                conexaoEl.style.transformOrigin = 'left center';
                
                zoomContent.appendChild(conexaoEl);
            }
        });
    }
    
    return posicoes;
}

// Criar card de documento
function criarCardDocumento(doc) {
    const card = document.createElement('div');
    card.className = `documento-card ${doc.tipo} size-${doc.size}`;
    card.setAttribute('data-documento-id', doc.id);
    card.setAttribute('data-documento-numero', doc.numero);
    
    // Adicionar tooltip
    card.setAttribute('title', `Clique para ver lançamentos ${doc.tipo_display === 'Matrícula' ? '' : `do ${doc.tipo_display}`} ${doc.numero}`);
    
    // Adicionar eventos
    card.addEventListener('click', (e) => {
        e.stopPropagation();
        abrirDocumento(doc.id);
    });
    
    card.addEventListener('mouseenter', () => {
        card.style.transform = 'scale(1.05)';
        card.style.zIndex = '10';
    });
    
    card.addEventListener('mouseleave', () => {
        card.style.transform = 'scale(1)';
        card.style.zIndex = '1';
    });
    
    // Adicionar menu de contexto
    card.addEventListener('contextmenu', (e) => {
        e.preventDefault();
        mostrarMenuContexto(e, doc);
    });
    
    card.innerHTML = `
        <div class="numero">${doc.numero}</div>
        <div class="tipo">${doc.tipo_display === 'Matrícula' ? '' : doc.tipo_display}</div>
        <div class="lancamentos">${doc.total_lancamentos} lançamentos</div>
        <div class="card-actions">
            <button class="btn-action" onclick="event.stopPropagation(); abrirDocumento(${doc.id})" title="Ver Lançamentos">
                👁️
            </button>
            <button class="btn-action" onclick="event.stopPropagation(); novoLancamentoDocumento(${doc.id})" title="Novo Lançamento">
                ➕
            </button>
            <button class="btn-action nivel-selector" onclick="event.stopPropagation(); mostrarSeletorNivel(event, ${doc.id}, ${doc.nivel})" title="Ajustar Nível">
                ⚙️
            </button>
        </div>
    `;
    
    return card;
}

// Abrir documento
function abrirDocumento(documentoId) {
    const url = `/dominial/documento/${documentoId}/lancamentos/${window.tisId}/${window.imovelId}/`;
    window.location.href = url;
}

// Novo lançamento em documento específico
function novoLancamentoDocumento(documentoId) {
    const url = `/dominial/tis/${window.tisId}/imovel/${window.imovelId}/novo-lancamento/${documentoId}/`;
    window.location.href = url;
}

// Mostrar menu de contexto
function mostrarMenuContexto(event, documento) {
    // Remover menu anterior se existir
    const menuAnterior = document.querySelector('.context-menu');
    if (menuAnterior) {
        menuAnterior.remove();
    }
    
    const menu = document.createElement('div');
    menu.className = 'context-menu';
    menu.style.position = 'fixed';
    menu.style.left = event.clientX + 'px';
    menu.style.top = event.clientY + 'px';
    menu.style.background = 'white';
    menu.style.border = '1px solid #ddd';
    menu.style.borderRadius = '4px';
    menu.style.boxShadow = '0 2px 10px rgba(0,0,0,0.1)';
    menu.style.zIndex = '1000';
    menu.style.minWidth = '200px';
    
    menu.innerHTML = `
        <div class="menu-header" style="padding: 10px; background: #f8f9fa; border-bottom: 1px solid #ddd; font-weight: bold;">
            ${documento.tipo_display === 'Matrícula' ? '' : documento.tipo_display}: ${documento.numero}
        </div>
        <div class="menu-item" onclick="abrirDocumento(${documento.id})" style="padding: 10px; cursor: pointer; border-bottom: 1px solid #eee;">
            👁️ Ver Lançamentos
        </div>
        <div class="menu-item" onclick="novoLancamentoDocumento(${documento.id})" style="padding: 10px; cursor: pointer; border-bottom: 1px solid #eee;">
            ➕ Novo Lançamento
        </div>
        <div class="menu-item" onclick="copiarNumeroDocumento('${documento.numero}')" style="padding: 10px; cursor: pointer;">
            📋 Copiar Número
        </div>
    `;
    
    document.body.appendChild(menu);
    
    // Fechar menu ao clicar fora
    document.addEventListener('click', function fecharMenu() {
        menu.remove();
        document.removeEventListener('click', fecharMenu);
    });
}

// Copiar número do documento
function copiarNumeroDocumento(numero) {
    navigator.clipboard.writeText(numero).then(() => {
        mostrarNotificacao('Número copiado para a área de transferência!', 'success');
    }).catch(() => {
        mostrarNotificacao('Erro ao copiar número', 'error');
    });
}

// Mostrar notificação
function mostrarNotificacao(mensagem, tipo = 'info') {
    const notificacao = document.createElement('div');
    notificacao.className = `notificacao ${tipo}`;
    notificacao.style.position = 'fixed';
    notificacao.style.top = '20px';
    notificacao.style.right = '20px';
    notificacao.style.padding = '15px 20px';
    notificacao.style.borderRadius = '4px';
    notificacao.style.color = 'white';
    notificacao.style.zIndex = '1001';
    notificacao.style.animation = 'slideIn 0.3s ease';
    
    if (tipo === 'success') {
        notificacao.style.background = '#28a745';
    } else if (tipo === 'error') {
        notificacao.style.background = '#dc3545';
    } else {
        notificacao.style.background = '#17a2b8';
    }
    
    notificacao.textContent = mensagem;
    document.body.appendChild(notificacao);
    
    setTimeout(() => {
        notificacao.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notificacao.remove(), 300);
    }, 3000);
}

// Renderizar cards de origens identificadas
function renderizarOrigensIdentificadas(zoomContent) {
    if (!arvoreData.origens_identificadas || arvoreData.origens_identificadas.length === 0) {
        return;
    }
    
    // Ordenar origens por número (maior primeiro)
    const origensOrdenadas = [...arvoreData.origens_identificadas].sort((a, b) => {
        const numA = parseInt(a.codigo.replace(/[MT]/g, ''));
        const numB = parseInt(b.codigo.replace(/[MT]/g, ''));
        return numB - numA; // Maior primeiro
    });
    
    // Calcular tamanho dos cards baseado na quantidade de origens
    const totalOrigens = origensOrdenadas.length;
    let cardSize = 'medium';
    let espacamentoX = 140; // aumentado de 120 para 140
    
    if (totalOrigens <= 3) {
        cardSize = 'large';
        espacamentoX = 160; // aumentado de 140 para 160
    } else if (totalOrigens <= 6) {
        cardSize = 'medium';
        espacamentoX = 140; // aumentado de 120 para 140
    } else {
        cardSize = 'small';
        espacamentoX = 120; // aumentado de 100 para 120
    }
    
    // Calcular posições para criar uma linha horizontal de origens
    const container = document.getElementById('arvore-container');
    const centerX = container.offsetWidth / 2 || 600; // Centro da div
    const y = 120; // Posição Y (mesma linha das transcrições)
    
    // Calcular posição inicial para centralizar a linha
    const totalWidth = origensOrdenadas.length * espacamentoX;
    const startX = centerX - (totalWidth / 2) + (espacamentoX / 2);
    
    // Renderizar cada origem na linha horizontal
    origensOrdenadas.forEach((origem, index) => {
        const card = document.createElement('div');
        
        // Se o documento já foi criado, usar estilo de documento normal
        if (origem.ja_criado) {
            card.className = `documento-card origem-criada ${origem.tipo} size-${cardSize}`;
            card.onclick = () => abrirDocumento(origem.documento_id);
        } else {
            // Se não foi criado, usar estilo de origem identificada
            card.className = `origem-card origem-identificada ${origem.tipo} size-${cardSize}`;
            card.onclick = () => criarDocumentoAutomatico(origem.codigo);
        }
        
        const x = startX + index * espacamentoX;
        card.style.left = `${x}px`;
        card.style.top = `${y}px`;
        
        // Conteúdo mais compacto para cards menores
        if (origem.ja_criado) {
            card.innerHTML = `
                <div class="numero">${origem.codigo}</div>
                <div class="tipo">${origem.tipo_display === 'Matrícula' ? '' : origem.tipo_display}</div>
                <div class="edit-button" onclick="event.stopPropagation(); editarDocumento(${origem.documento_id})">Editar</div>
            `;
        } else {
            card.innerHTML = `
                <div class="codigo">${origem.codigo}</div>
                <div class="tipo">${origem.tipo_display === 'Matrícula' ? '' : origem.tipo_display}</div>
                <div class="info">Origem: ${origem.documento_origem}</div>
            `;
        }
        
        zoomContent.appendChild(card);
        
        // Criar conexão com a matrícula atual (no topo)
        const matriculaAtual = arvoreData.documentos.find(doc => doc.tipo === 'matricula');
        if (matriculaAtual) {
            const conexaoEl = document.createElement('div');
            conexaoEl.className = 'conexao';
            conexaoEl.style.border = '2px dashed #28a745';
            conexaoEl.style.background = 'transparent';
            conexaoEl.style.opacity = '0.6';
            conexaoEl.style.zIndex = '1';
            
            // Calcular posição e ângulo da conexão
            const cardWidth = cardSize === 'large' ? 70 : cardSize === 'medium' ? 60 : 50;
            const cardHeight = cardSize === 'large' ? 90 : cardSize === 'medium' ? 80 : 70;
            
            // Posições nas bordas dos cards
            const fromX = x + cardWidth; // Borda direita do card origem
            const fromY = y + (cardHeight / 2); // Centro vertical do card origem
            const toX = matriculaAtual.x; // Borda esquerda do card destino
            const toY = matriculaAtual.y + (cardHeight / 2); // Centro vertical do card destino
            
            const dx = toX - fromX;
            const dy = toY - fromY;
            const distancia = Math.sqrt(dx * dx + dy * dy);
            const angulo = Math.atan2(dy, dx) * 180 / Math.PI;
            
            // Posicionar a linha
            conexaoEl.style.width = `${distancia}px`;
            conexaoEl.style.left = `${fromX}px`;
            conexaoEl.style.top = `${fromY}px`;
            conexaoEl.style.transform = `rotate(${angulo}deg)`;
            conexaoEl.style.transformOrigin = 'left center';
            
            zoomContent.appendChild(conexaoEl);
        }
    });
}

// Criar documento automaticamente
async function criarDocumentoAutomatico(codigo) {
    try {
        const url = `/tis/${window.tisId}/imovel/${window.imovelId}/criar-documento/${codigo}/`;
        
        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        });
        
        if (response.ok) {
            mostrarNotificacao(`Documento "${codigo}" criado com sucesso!`, 'success');
            // Recarregar a árvore para mostrar o novo documento
            setTimeout(() => {
                carregarDadosArvore();
            }, 1000);
        } else {
            const data = await response.json();
            mostrarNotificacao(data.error || 'Erro ao criar documento', 'error');
        }
    } catch (error) {
        console.error('Erro:', error);
        mostrarNotificacao('Erro ao criar documento', 'error');
    }
}

// Configurar pan
function configurarPan() {
    const container = document.getElementById('arvore-container');
    const zoomContent = document.getElementById('arvore-zoom-content');
    
    container.addEventListener('mousedown', (e) => {
        if (e.target.closest('.documento-card') || e.target.closest('.btn-action')) {
            return; // Não iniciar pan se clicou em um card ou botão
        }
        
        isDragging = true;
        dragStart = { x: e.clientX - panOffset.x, y: e.clientY - panOffset.y };
        container.style.cursor = 'grabbing';
    });
    
    document.addEventListener('mousemove', (e) => {
        if (!isDragging) return;
        
        panOffset.x = e.clientX - dragStart.x;
        panOffset.y = e.clientY - dragStart.y;
        
        aplicarZoom();
    });
    
    document.addEventListener('mouseup', () => {
        isDragging = false;
        container.style.cursor = 'grab';
    });
}

// Controles de zoom
function zoomIn() {
    zoomLevel = Math.min(zoomLevel * 1.2, 3);
    aplicarZoom();
}

function zoomOut() {
    zoomLevel = Math.max(zoomLevel / 1.2, 0.3);
    aplicarZoom();
}

function resetZoom() {
    zoomLevel = 1;
    panOffset = { x: 0, y: 0 };
    aplicarZoom();
}

function aplicarZoom() {
    const zoomContent = document.getElementById('arvore-zoom-content');
    zoomContent.style.transform = `translate(${panOffset.x}px, ${panOffset.y}px) scale(${zoomLevel})`;
}

// Editar documento
function editarDocumento(documentoId) {
    const url = `/dominial/documento/${documentoId}/editar/${window.tisId}/${window.imovelId}/`;
    window.location.href = url;
}

// Mostrar seletor de nível
function mostrarSeletorNivel(event, documentoId, nivelAtual) {
    // Remover seletor anterior se existir
    const seletorAnterior = document.querySelector('.nivel-selector-popup');
    if (seletorAnterior) {
        seletorAnterior.remove();
    }
    
    const seletor = document.createElement('div');
    seletor.className = 'nivel-selector-popup';
    seletor.style.position = 'fixed';
    seletor.style.left = event.clientX + 'px';
    seletor.style.top = event.clientY + 'px';
    seletor.style.background = 'white';
    seletor.style.border = '1px solid #ddd';
    seletor.style.borderRadius = '4px';
    seletor.style.boxShadow = '0 2px 10px rgba(0,0,0,0.1)';
    seletor.style.zIndex = '1000';
    seletor.style.minWidth = '200px';
    seletor.style.padding = '10px';
    
    // Criar opções de nível (0 a 10)
    const opcoesNivel = [];
    for (let i = 0; i <= 10; i++) {
        opcoesNivel.push(`<option value="${i}" ${i === nivelAtual ? 'selected' : ''}>Nível ${i}</option>`);
    }
    
    seletor.innerHTML = `
        <div style="margin-bottom: 10px; font-weight: bold; color: #333;">
            Ajustar Nível do Documento
        </div>
        <select id="nivel-select-${documentoId}" style="width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px; margin-bottom: 10px;">
            ${opcoesNivel.join('')}
        </select>
        <div style="display: flex; gap: 10px;">
            <button onclick="salvarNivelManual(${documentoId})" style="flex: 1; padding: 8px; background: #28a745; color: white; border: none; border-radius: 4px; cursor: pointer;">
                Salvar
            </button>
            <button onclick="removerNivelManual(${documentoId})" style="flex: 1; padding: 8px; background: #6c757d; color: white; border: none; border-radius: 4px; cursor: pointer;">
                Remover Manual
            </button>
        </div>
    `;
    
    document.body.appendChild(seletor);
    
    // Fechar seletor ao clicar fora
    document.addEventListener('click', function fecharSeletor(e) {
        if (!seletor.contains(e.target)) {
            seletor.remove();
            document.removeEventListener('click', fecharSeletor);
        }
    });
}

// Salvar nível manual
async function salvarNivelManual(documentoId) {
    const select = document.getElementById(`nivel-select-${documentoId}`);
    const novoNivel = parseInt(select.value);
    
    try {
        const response = await fetch(`/dominial/documento/${documentoId}/ajustar-nivel/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
            },
            body: JSON.stringify({
                nivel_manual: novoNivel
            })
        });
        
        if (response.ok) {
            mostrarNotificacao('Nível ajustado com sucesso!', 'success');
            // Recarregar a árvore para refletir as mudanças
            carregarDadosArvore();
        } else {
            mostrarNotificacao('Erro ao ajustar nível', 'error');
        }
    } catch (error) {
        console.error('Erro ao salvar nível:', error);
        mostrarNotificacao('Erro ao ajustar nível', 'error');
    }
    
    // Fechar seletor
    const seletor = document.querySelector('.nivel-selector-popup');
    if (seletor) {
        seletor.remove();
    }
}

// Remover nível manual (voltar ao automático)
async function removerNivelManual(documentoId) {
    try {
        const response = await fetch(`/dominial/documento/${documentoId}/ajustar-nivel/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
            },
            body: JSON.stringify({
                nivel_manual: null
            })
        });
        
        if (response.ok) {
            mostrarNotificacao('Nível manual removido!', 'success');
            // Recarregar a árvore para refletir as mudanças
            carregarDadosArvore();
        } else {
            mostrarNotificacao('Erro ao remover nível manual', 'error');
        }
    } catch (error) {
        console.error('Erro ao remover nível manual:', error);
        mostrarNotificacao('Erro ao remover nível manual', 'error');
    }
    
    // Fechar seletor
    const seletor = document.querySelector('.nivel-selector-popup');
    if (seletor) {
        seletor.remove();
    }
} 