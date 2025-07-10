// JavaScript para visualização de tabela da cadeia dominial com navegação dinâmica

// Variáveis globais
let tisId, imovelId;
let isLoading = false;

// Inicializar quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', function() {
    // Extrair IDs da URL
    extractIdsFromUrl();
    
    // Inicializar funcionalidades
    initializeCadeiaTabela();
});

function extractIdsFromUrl() {
    // Extrair TIS ID e Imóvel ID da URL
    const urlParts = window.location.pathname.split('/');
    
    // Posições fixas para a URL /dominial/tis/<tisId>/imovel/<imovelId>/ver-cadeia-dominial/
    const tisIdStr = urlParts[3];
    const imovelIdStr = urlParts[5];
    tisId = parseInt(tisIdStr);
    imovelId = parseInt(imovelIdStr);
    
    // Verificar se os IDs são válidos
    if (isNaN(tisId) || isNaN(imovelId)) {
        console.error('IDs inválidos extraídos da URL:', { tisId, imovelId });
    }
}

function initializeCadeiaTabela() {
    // Adicionar event listeners para botões de expandir
    const expandButtons = document.querySelectorAll('.expand-btn');
    expandButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const documentoId = this.dataset.documentoId;
            toggleLancamentos(documentoId);
        });
    });
    
    // Adicionar event listeners para botões de origem
    const origemButtons = document.querySelectorAll('.origem-btn');
    origemButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            if (isLoading) return;
            
            const documentoId = this.dataset.documentoId;
            const origemNumero = this.dataset.origemNumero;
            escolherOrigem(documentoId, origemNumero);
        });
    });
}

function toggleLancamentos(documentoId) {
    const lancamentosRow = document.getElementById(`lancamentos-${documentoId}`);
    const expandBtn = document.querySelector(`[data-documento-id="${documentoId}"] .expand-btn`);
    
    if (!lancamentosRow || !expandBtn) {
        console.warn('Elementos não encontrados para documento:', documentoId);
        return;
    }
    
    const expandIcon = expandBtn.querySelector('.expand-icon');
    
    if (lancamentosRow.style.display === 'none' || !lancamentosRow.style.display) {
        // Expandir
        lancamentosRow.style.display = 'table-row';
        lancamentosRow.classList.add('show');
        expandIcon.classList.add('expanded');
        
        // Animar a expansão
        lancamentosRow.style.opacity = '0';
        lancamentosRow.style.transform = 'translateY(-10px)';
        
        setTimeout(() => {
            lancamentosRow.style.transition = 'all 0.3s ease';
            lancamentosRow.style.opacity = '1';
            lancamentosRow.style.transform = 'translateY(0)';
        }, 10);
    } else {
        // Colapsar
        lancamentosRow.style.transition = 'all 0.3s ease';
        lancamentosRow.style.opacity = '0';
        lancamentosRow.style.transform = 'translateY(-10px)';
        
        setTimeout(() => {
            lancamentosRow.style.display = 'none';
            lancamentosRow.classList.remove('show');
        }, 300);
        
        expandIcon.classList.remove('expanded');
    }
}

function escolherOrigem(documentoId, origemNumero) {
    if (isLoading) {
        return;
    }
    
    // Verificar se os IDs são válidos
    if (!tisId || !imovelId || isNaN(tisId) || isNaN(imovelId)) {
        console.error('IDs inválidos para fazer a requisição:', { tisId, imovelId });
        mostrarNotificacao('Erro: IDs inválidos', 'error');
        return;
    }
    
    isLoading = true;
    
    // Mostrar loading no botão
    const origemButtons = document.querySelectorAll(`[data-documento-id="${documentoId}"].origem-btn`);
    origemButtons.forEach(btn => {
        btn.classList.add('loading');
        btn.disabled = true;
    });
    
    // Fazer chamada AJAX para salvar a escolha
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    
    fetch('/dominial/api/escolher-origem-documento/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify({
            documento_id: documentoId,
            origem_numero: origemNumero,
            tis_id: tisId,
            imovel_id: imovelId
        })
    })
    .then(response => {
        return response.json();
    })
    .then(data => {
        if (data.success) {
            // Atualizar visual dos botões
            origemButtons.forEach(btn => {
                btn.classList.remove('ativo', 'loading');
                btn.disabled = false;
                if (btn.dataset.origemNumero === origemNumero) {
                    btn.classList.add('ativo');
                }
            });
            
            // Mostrar mensagem de sucesso
            mostrarNotificacao('Escolha salva com sucesso!', 'success');
            
            // Fazer nova requisição para obter a cadeia atualizada
            return fetch(`/dominial/api/cadeia-dominial-atualizada/${tisId}/${imovelId}/`);
        } else {
            throw new Error(data.error || 'Erro ao salvar escolha');
        }
    })
    .then(response => {
        if (response) {
            return response.json();
        }
    })
    .then(cadeiaData => {
        if (cadeiaData && cadeiaData.success && cadeiaData.cadeia) {
            // Atualizar a tabela com os novos dados (sempre expandido)
            atualizarTabelaCadeia(cadeiaData.cadeia);
            
            // Mostrar mensagem de sucesso
            mostrarNotificacao('Cadeia atualizada com sucesso!', 'success');
        }
    })
    .catch(error => {
        console.error('Erro na requisição:', error);
        mostrarNotificacao('Erro ao salvar escolha: ' + error.message, 'error');
        
        // Remover loading dos botões
        origemButtons.forEach(btn => {
            btn.classList.remove('loading');
            btn.disabled = false;
        });
    })
    .finally(() => {
        isLoading = false;
    });
}

function atualizarTabelaCadeia(cadeia) {
    const tbody = document.querySelector('.cadeia-tabela-principal tbody');
    if (!tbody) {
        console.error('Tbody não encontrado');
        return;
    }
    
    // Limpar tbody atual
    tbody.innerHTML = '';
    
    // Reconstruir a tabela com os novos dados
    cadeia.forEach(item => {
        // Criar linha do documento
        const documentoRow = document.createElement('tr');
        documentoRow.className = 'documento-row';
        documentoRow.setAttribute('data-documento-id', item.documento.id);
        
        documentoRow.innerHTML = `
            <td>
                <button class="expand-btn" data-documento-id="${item.documento.id}">
                    <svg class="expand-icon expanded" width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M9 18L15 12L9 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                    ${item.documento.tipo_display}: ${item.documento.numero}
                </button>
            </td>
            <td>${item.documento.data}</td>
            <td>${item.documento.cartorio_nome}</td>
            <td>${item.lancamentos.length} lanç.</td>
            <td>
                <!-- Ações podem ser adicionadas aqui no futuro -->
            </td>
        `;
        
        tbody.appendChild(documentoRow);
        
        // Criar linha expandível dos lançamentos
        const lancamentosRow = document.createElement('tr');
        lancamentosRow.className = 'lancamentos-row';
        lancamentosRow.id = `lancamentos-${item.documento.id}`;
        
        // Todos os documentos expandidos por padrão
        lancamentosRow.style.display = 'table-row';
        lancamentosRow.classList.add('show');
        
        // Criar conteúdo dos lançamentos
        const lancamentosContent = criarConteudoLancamentos(item);
        lancamentosRow.innerHTML = `<td colspan="5">${lancamentosContent}</td>`;
        
        tbody.appendChild(lancamentosRow);
    });
    
    // Re-adicionar event listeners
    initializeCadeiaTabela();
}

function criarConteudoLancamentos(item) {
    let lancamentosHtml = `
        <div class="lancamentos-table-container">
            <h5>
                <svg class="section-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M14 2H6C5.46957 2 4.96086 2.21071 4.58579 2.58579C4.21071 2.96086 4 3.46957 4 4V20C4 20.5304 4.21071 21.0391 4.58579 21.4142C4.96086 21.7893 5.46957 22 6 22H18C18.5304 22 19.0391 21.7893 19.4142 21.4142C19.7893 21.0391 20 20.5304 20 20V8L14 2Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    <path d="M14 2V8H20" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    <path d="M16 13H8" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    <path d="M16 17H8" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    <path d="M10 9H8" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                Lançamentos do ${item.documento.tipo_display} ${item.documento.numero}
            </h5>
            <table class="cadeia-tabela-planilha">
                <thead>
                    <tr>
                        <th colspan="5" class="agrupamento">MATRÍCULA</th>
                        <th colspan="2" class="agrupamento">&nbsp;</th>
                        <th colspan="6" class="agrupamento">TRANSMISSÃO</th>
                        <th rowspan="2">Área (ha)</th>
                        <th rowspan="2">Origem</th>
                        <th rowspan="2">Observações</th>
                    </tr>
                    <tr>
                        <!-- Matrícula -->
                        <th>Nº</th>
                        <th>L</th>
                        <th>Fls.</th>
                        <th>Cartório</th>
                        <th>Data</th>
                        <!-- Transmitente/Adquirente -->
                        <th>Transmitente</th>
                        <th>Adquirente</th>
                        <!-- Transmissão -->
                        <th>Forma</th>
                        <th>Título</th>
                        <th>Cartório</th>
                        <th>L</th>
                        <th>Fls.</th>
                        <th>Data</th>
                    </tr>
                </thead>
                <tbody>
    `;
    
    item.lancamentos.forEach((lancamento, index) => {
        const rowClass = index % 2 === 0 ? 'linha-par' : 'linha-impar';
        lancamentosHtml += criarLinhaLancamentoPlanilha(lancamento, item.documento, rowClass);
    });
    
    lancamentosHtml += `
                </tbody>
            </table>
    `;
    
    // Adicionar botões de origem se houver múltiplas origens
    if (item.tem_multiplas_origens && item.origens_disponiveis) {
        lancamentosHtml += `
            <div class="origem-controls">
                <div class="origem-buttons">
                    <span class="origem-label">Escolher origem:</span>
        `;
        
        item.origens_disponiveis.forEach(origem => {
            const ativoClass = origem.escolhida ? 'ativo' : '';
            lancamentosHtml += `
                <button class="origem-btn ${ativoClass}" 
                        data-documento-id="${item.documento.id}"
                        data-origem-numero="${origem.numero}"
                        title="Escolher origem ${origem.numero}">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M9 18L15 12L9 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                    ${origem.numero}
                </button>
            `;
        });
        
        lancamentosHtml += `
                </div>
            </div>
        `;
    }
    
    lancamentosHtml += `
        </div>
    `;
    
    return lancamentosHtml;
}

function criarLinhaLancamentoPlanilha(lancamento, documento, rowClass) {
    // Separar transmitentes e adquirentes
    const transmitentes = lancamento.pessoas ? lancamento.pessoas.filter(p => p.tipo === 'transmitente').map(p => p.pessoa_nome) : [];
    const adquirentes = lancamento.pessoas ? lancamento.pessoas.filter(p => p.tipo === 'adquirente').map(p => p.pessoa_nome) : [];
    
    // Função para formatar descrição longa
    const formatarDescricao = (descricao) => {
        if (!descricao) return '-';
        if (descricao.length > 100) {
            return `
                <span class="descricao-curta">${descricao.substring(0, 100)}...</span>
                <span class="descricao-completa" style="display:none;">${descricao}</span>
                <a href="#" class="ler-mais" onclick="toggleDescricao(this); return false;">Ler mais</a>
            `;
        }
        return descricao;
    };
    
    // Verificar se é averbação
    const isAverbacao = lancamento.tipo_tipo === 'averbacao';
    
    const html = `
        <tr class="planilha-row ${rowClass}">
            <!-- Matrícula -->
            <td>${lancamento.numero_lancamento || '-'}</td>
            <td>${documento.livro || '-'}</td>
            <td>${documento.folha || '-'}</td>
            <td>${documento.cartorio_nome || '-'}</td>
            <td>${documento.data || '-'}</td>
            <!-- Transmitente -->
            <td>${transmitentes.length > 0 ? transmitentes.join(', ') : '-'}</td>
            <!-- Adquirente -->
            <td>${adquirentes.length > 0 ? adquirentes.join(', ') : '-'}</td>
            <!-- Transmissão -->
            ${isAverbacao ? 
                `<td colspan="6">${formatarDescricao(lancamento.descricao)}</td>` :
                `<td>${lancamento.forma || '-'}</td>
                 <td>${lancamento.titulo || '-'}</td>
                 <td>${lancamento.cartorio_transmissao_nome || '-'}</td>
                 <td>${lancamento.livro_transacao || '-'}</td>
                 <td>${lancamento.folha_transacao || '-'}</td>
                 <td>${lancamento.data_transacao || '-'}</td>`
            }
            <!-- Restante -->
            <td>${lancamento.area || '-'}</td>
            <td>${lancamento.origem || '-'}</td>
            <td>${lancamento.observacoes || '-'}</td>
        </tr>
    `;
    
    return html;
}

function criarLinhaLancamento(lancamento) {
    const tipoIcon = lancamento.tipo === 'averbacao' ? '📋' : 
                    lancamento.tipo === 'registro' ? '📋' : 
                    lancamento.tipo === 'inicio_matricula' ? '🚀' : '📄';
    
    let html = `
        <tr>
            <td class="td-tipo">
                <div class="tipo-badge tipo-${lancamento.tipo}">
                    ${tipoIcon}
                    ${lancamento.tipo_display}
                </div>
            </td>
            <td class="td-numero">
                <span class="numero-value">${lancamento.numero_lancamento || '-'}</span>
            </td>
            <td class="td-data">
                <span class="data-value">${lancamento.data}</span>
            </td>
            <td class="td-detalhes">
    `;
    
    // Adicionar detalhes baseado no tipo
    if (lancamento.forma) {
        html += `
            <div class="detalhe-item">
                <span class="detalhe-label">Forma:</span>
                <span class="detalhe-valor">${lancamento.forma}</span>
            </div>
        `;
    }
    
    if (lancamento.titulo) {
        html += `
            <div class="detalhe-item">
                <span class="detalhe-label">Título:</span>
                <span class="detalhe-valor">${lancamento.titulo}</span>
            </div>
        `;
    }
    
    if (lancamento.descricao) {
        html += `
            <div class="detalhe-item">
                <span class="detalhe-label">Descrição:</span>
                <span class="detalhe-valor">${lancamento.descricao}</span>
            </div>
        `;
    }
    
    if (lancamento.area) {
        html += `
            <div class="detalhe-item">
                <span class="detalhe-label">Área:</span>
                <span class="detalhe-valor">${lancamento.area} ha</span>
            </div>
        `;
    }
    
    if (lancamento.origem) {
        html += `
            <div class="detalhe-item">
                <span class="detalhe-label">Origem:</span>
                <span class="detalhe-valor">${lancamento.origem}</span>
            </div>
        `;
    }
    
    if (lancamento.observacoes) {
        html += `
            <div class="observacoes-item">
                <span class="obs-label">📝 Obs:</span>
                <span class="obs-valor">${lancamento.observacoes}</span>
            </div>
        `;
    }
    
    html += `
            </td>
            <td class="td-pessoas">
    `;
    
    // Adicionar pessoas
    if (lancamento.pessoas && lancamento.pessoas.length > 0) {
        const pessoas = lancamento.pessoas.slice(0, 2);
        const pessoaTipo = lancamento.tipo === 'registro' ? 'Transmitente:' : 
                          lancamento.tipo === 'inicio_matricula' ? 'Adquirente:' : 'Pessoas:';
        const destacadoClass = (lancamento.tipo === 'registro' || lancamento.tipo === 'inicio_matricula') ? 'destacado' : '';
        
        html += `
            <div class="pessoas-item">
                <small class="pessoa-tipo ${destacadoClass}">${pessoaTipo}</small> 
                ${pessoas.map(p => p.pessoa_nome).join(', ')}
                ${lancamento.pessoas.length > 2 ? `<span class="mais-pessoas">+${lancamento.pessoas.length - 2}</span>` : ''}
            </div>
        `;
    }
    
    html += `
            </td>
        </tr>
    `;
    
    return html;
}

function toggleDescricao(element) {
    const row = element.closest('tr');
    const descricaoCurta = row.querySelector('.descricao-curta');
    const descricaoCompleta = row.querySelector('.descricao-completa');
    
    if (descricaoCurta.style.display !== 'none') {
        // Mostrar descrição completa
        descricaoCurta.style.display = 'none';
        descricaoCompleta.style.display = 'inline';
        element.textContent = 'Ler menos';
    } else {
        // Mostrar descrição curta
        descricaoCurta.style.display = 'inline';
        descricaoCompleta.style.display = 'none';
        element.textContent = 'Ler mais';
    }
}

function mostrarNotificacao(mensagem, tipo = 'info') {
    // Criar elemento de notificação
    const notificacao = document.createElement('div');
    notificacao.className = `notificacao notificacao-${tipo}`;
    notificacao.innerHTML = `
        <div class="notificacao-conteudo">
            <span class="notificacao-mensagem">${mensagem}</span>
            <button class="notificacao-fechar" onclick="this.parentElement.parentElement.remove()">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M18 6L6 18" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    <path d="M6 6L18 18" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
            </button>
        </div>
    `;
    
    // Adicionar estilos
    notificacao.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${tipo === 'success' ? '#4CAF50' : tipo === 'error' ? '#f44336' : '#2196F3'};
        color: white;
        padding: 15px 20px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 10000;
        max-width: 400px;
        animation: slideIn 0.3s ease;
    `;
    
    // Adicionar ao DOM
    document.body.appendChild(notificacao);
    
    // Remover automaticamente após 5 segundos
    setTimeout(() => {
        if (notificacao.parentElement) {
            notificacao.remove();
        }
    }, 5000);
}

// Adicionar estilos CSS para animações
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    .origem-btn.loading {
        opacity: 0.6;
        pointer-events: none;
        position: relative;
    }
    
    .origem-btn.ativo {
        background-color: #4CAF50;
        color: white;
    }
    
    .expand-icon.expanded {
        transform: rotate(90deg);
    }
    
    .expand-icon {
        transition: transform 0.3s ease;
    }
`;
document.head.appendChild(style); 