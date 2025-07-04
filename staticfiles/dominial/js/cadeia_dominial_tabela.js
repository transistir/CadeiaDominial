// JavaScript para visualização de tabela da cadeia dominial

document.addEventListener('DOMContentLoaded', function() {
    // Inicializar funcionalidades
    initializeCadeiaTabela();
});

function initializeCadeiaTabela() {
    // Adicionar event listeners para botões de expandir
    const expandButtons = document.querySelectorAll('.expand-btn');
    expandButtons.forEach(button => {
        button.addEventListener('click', function() {
            const documentoId = this.closest('tr').dataset.documentoId;
            toggleLancamentos(documentoId);
        });
    });
}

function toggleLancamentos(documentoId) {
    const lancamentosRow = document.getElementById(`lancamentos-${documentoId}`);
    const expandBtn = document.querySelector(`[data-documento-id="${documentoId}"] .expand-btn`);
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
    // Função para escolher origem no nível do documento
    console.log(`Escolhendo origem ${origemNumero} para documento ${documentoId}`);
    
    // Atualizar visual dos botões
    const origemButtons = document.querySelectorAll(`[data-documento-id="${documentoId}"] .origem-btn`);
    origemButtons.forEach(btn => {
        btn.classList.remove('ativo');
        if (btn.textContent.trim().includes(origemNumero)) {
            btn.classList.add('ativo');
        }
    });
    
    // TODO: Implementar chamada AJAX para salvar escolha
    // salvarEscolhaOrigem(documentoId, origemNumero);
}

function escolherOrigemLancamento(lancamentoId, origemNumero) {
    // Função para escolher origem no nível do lançamento
    console.log(`Escolhendo origem ${origemNumero} para lançamento ${lancamentoId}`);
    
    // Atualizar visual dos botões
    const origemButtons = document.querySelectorAll(`[data-lancamento-id="${lancamentoId}"] .origem-btn-mini`);
    origemButtons.forEach(btn => {
        btn.classList.remove('ativo');
        if (btn.textContent.trim().includes(origemNumero)) {
            btn.classList.add('ativo');
        }
    });
    
    // TODO: Implementar chamada AJAX para salvar escolha
    // salvarEscolhaOrigemLancamento(lancamentoId, origemNumero);
}

// Função para expandir todos os documentos
function expandirTodos() {
    const expandButtons = document.querySelectorAll('.expand-btn');
    expandButtons.forEach(button => {
        const documentoId = button.closest('tr').dataset.documentoId;
        const lancamentosRow = document.getElementById(`lancamentos-${documentoId}`);
        
        if (lancamentosRow.style.display === 'none' || !lancamentosRow.style.display) {
            toggleLancamentos(documentoId);
        }
    });
}

// Função para colapsar todos os documentos
function colapsarTodos() {
    const expandButtons = document.querySelectorAll('.expand-btn');
    expandButtons.forEach(button => {
        const documentoId = button.closest('tr').dataset.documentoId;
        const lancamentosRow = document.getElementById(`lancamentos-${documentoId}`);
        
        if (lancamentosRow.style.display !== 'none') {
            toggleLancamentos(documentoId);
        }
    });
}

// Função para salvar escolha de origem via AJAX
function salvarEscolhaOrigem(documentoId, origemNumero) {
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    
    fetch('/api/escolher-origem/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify({
            documento_id: documentoId,
            origem_numero: origemNumero
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log('Escolha salva com sucesso');
            // Recarregar a página ou atualizar a visualização
            // location.reload();
        } else {
            console.error('Erro ao salvar escolha:', data.error);
        }
    })
    .catch(error => {
        console.error('Erro na requisição:', error);
    });
}

// Função para salvar escolha de origem de lançamento via AJAX
function salvarEscolhaOrigemLancamento(lancamentoId, origemNumero) {
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    
    fetch('/api/escolher-origem-lancamento/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify({
            lancamento_id: lancamentoId,
            origem_numero: origemNumero
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log('Escolha de lançamento salva com sucesso');
            // Recarregar a página ou atualizar a visualização
            // location.reload();
        } else {
            console.error('Erro ao salvar escolha de lançamento:', data.error);
        }
    })
    .catch(error => {
        console.error('Erro na requisição:', error);
    });
}

// Função para exportar dados da cadeia dominial
function exportarCadeiaDominial() {
    // TODO: Implementar exportação para PDF ou Excel
    console.log('Exportando cadeia dominial...');
}

// Função para imprimir cadeia dominial
function imprimirCadeiaDominial() {
    window.print();
}

// Adicionar funcionalidades de teclado
document.addEventListener('keydown', function(event) {
    // Ctrl/Cmd + E para expandir todos
    if ((event.ctrlKey || event.metaKey) && event.key === 'e') {
        event.preventDefault();
        expandirTodos();
    }
    
    // Ctrl/Cmd + C para colapsar todos
    if ((event.ctrlKey || event.metaKey) && event.key === 'c') {
        event.preventDefault();
        colapsarTodos();
    }
});

// Função para mostrar tooltips informativos
function mostrarTooltip(elemento, mensagem) {
    const tooltip = document.createElement('div');
    tooltip.className = 'tooltip';
    tooltip.textContent = mensagem;
    tooltip.style.cssText = `
        position: absolute;
        background: #333;
        color: white;
        padding: 5px 10px;
        border-radius: 4px;
        font-size: 12px;
        z-index: 1000;
        pointer-events: none;
    `;
    
    document.body.appendChild(tooltip);
    
    const rect = elemento.getBoundingClientRect();
    tooltip.style.left = rect.left + 'px';
    tooltip.style.top = (rect.bottom + 5) + 'px';
    
    setTimeout(() => {
        document.body.removeChild(tooltip);
    }, 2000);
}

// Função para melhorar acessibilidade
function melhorarAcessibilidade() {
    // Adicionar atributos ARIA
    const expandButtons = document.querySelectorAll('.expand-btn');
    expandButtons.forEach(button => {
        button.setAttribute('aria-expanded', 'false');
        button.setAttribute('aria-label', 'Expandir lançamentos');
    });
    
    const origemButtons = document.querySelectorAll('.origem-btn, .origem-btn-mini');
    origemButtons.forEach(button => {
        button.setAttribute('aria-label', `Escolher origem ${button.textContent.trim()}`);
    });
}

// Inicializar melhorias de acessibilidade
document.addEventListener('DOMContentLoaded', function() {
    melhorarAcessibilidade();
}); 