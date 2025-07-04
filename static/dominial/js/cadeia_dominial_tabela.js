// JavaScript para visualização de tabela da cadeia dominial

// Função para expandir/colapsar lançamentos
function toggleLancamentos(documentoId) {
    const lancamentosRow = document.getElementById(`lancamentos-${documentoId}`);
    const expandBtn = document.querySelector(`[data-documento-id="${documentoId}"] .expand-btn`);
    const expandIcon = expandBtn.querySelector('.expand-icon');
    
    if (lancamentosRow.style.display === 'none') {
        lancamentosRow.style.display = 'table-row';
        expandIcon.classList.add('expanded');
    } else {
        lancamentosRow.style.display = 'none';
        expandIcon.classList.remove('expanded');
    }
}

// Função para escolher origem (placeholder para futuras implementações)
function escolherOrigem(documentoId, origem) {
    console.log(`Escolhendo origem ${origem} para documento ${documentoId}`);
    // TODO: Implementar lógica de escolha de origem
    alert(`Funcionalidade de escolha de origem será implementada na próxima fase.\nDocumento: ${documentoId}\nOrigem escolhida: ${origem}`);
}

// Função para escolher origem no nível do lançamento
function escolherOrigemLancamento(lancamentoId, origem) {
    console.log(`Escolhendo origem ${origem} para lançamento ${lancamentoId}`);
    // TODO: Implementar lógica de escolha de origem no nível do lançamento
    alert(`Funcionalidade de escolha de origem no lançamento será implementada na próxima fase.\nLançamento: ${lancamentoId}\nOrigem escolhida: ${origem}`);
}

// Inicialização quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', function() {
    console.log('Cadeia Dominial Tabela inicializada');
    
    // Adicionar listeners para melhorar a experiência do usuário
    document.querySelectorAll('.expand-btn').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            const documentoId = this.closest('.documento-row').dataset.documentoId;
            toggleLancamentos(documentoId);
        });
    });
    
    // Adicionar tooltips para botões de origem
    document.querySelectorAll('.origem-btn, .origem-btn-mini').forEach(btn => {
        btn.title = 'Clique para escolher esta origem';
    });
}); 