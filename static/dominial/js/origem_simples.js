/**
 * JavaScript simples para select M/T + campo numérico
 * Funcionalidades:
 * - Junta automaticamente M/T + número
 * - Navegação otimizada com Tab
 * - Validação simples
 * - Compatibilidade total com backend
 */

// Inicializar quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', function() {
    inicializarOrigensSimples();
});

function inicializarOrigensSimples() {
    console.log('Inicializando origens simples...');
    
    // Configurar primeira origem
    configurarOrigem(0);
    
    // Configurar eventos globais
    configurarEventosGlobais();
}

function configurarOrigem(index) {
    const tipoSelect = document.getElementById(`tipo_origem_${index}`);
    const numeroInput = document.getElementById(`numero_origem_${index}`);
    const hiddenInput = document.getElementById(`origem_completa_hidden_${index}`);
    
    if (!tipoSelect || !numeroInput || !hiddenInput) return;
    
    // Inicializar estado do campo número (bloqueado por padrão)
    numeroInput.disabled = !tipoSelect.value;
    
    // Configurar validação para início de matrícula
    configurarValidacaoInicioMatricula(index);
    
    // Event listener para mudança no select
    tipoSelect.addEventListener('change', function() {
        atualizarOrigemCompleta(index);
        // Habilitar/desabilitar campo numérico
        numeroInput.disabled = !this.value;
        if (this.value) {
            numeroInput.focus();
        } else {
            // Limpar número se tipo for desmarcado
            numeroInput.value = '';
            atualizarOrigemCompleta(index);
        }
    });
    
    // Event listener para mudança no número
    numeroInput.addEventListener('input', function() {
        // Permitir apenas números
        this.value = this.value.replace(/[^0-9]/g, '');
        atualizarOrigemCompleta(index);
    });
    
    // Event listener para navegação com Tab
    numeroInput.addEventListener('keydown', function(e) {
        if (e.key === 'Tab' && !e.shiftKey) {
            // Tab normal - ir para próximo campo ou adicionar origem
            const proximoCampo = encontrarProximoCampo(index);
            if (proximoCampo) {
                e.preventDefault();
                proximoCampo.focus();
            } else {
                // Se não há próximo campo, adicionar nova origem
                e.preventDefault();
                adicionarOrigemSimples();
            }
        }
    });
    
    // Migrar dados existentes se houver
    migrarDadosExistentes(index);
}

function configurarEventosGlobais() {
    // Interceptar função de adicionar origem existente
    const botaoAdicionar = document.querySelector('button[onclick="adicionarOrigem()"]');
    if (botaoAdicionar) {
        botaoAdicionar.onclick = adicionarOrigemSimples;
    }
}

function atualizarOrigemCompleta(index) {
    const tipoSelect = document.getElementById(`tipo_origem_${index}`);
    const numeroInput = document.getElementById(`numero_origem_${index}`);
    const hiddenInput = document.getElementById(`origem_completa_hidden_${index}`);
    const fimCadeiaToggle = document.getElementById(`fim_cadeia_${index}`);
    
    if (!hiddenInput) return;
    
    // Verificar se fim de cadeia está marcado
    if (fimCadeiaToggle && fimCadeiaToggle.checked) {
        // Buscar tipo e classificação do fim de cadeia
        const tipoFimCadeia = document.getElementById(`tipo_fim_cadeia_${index}`);
        const classificacaoFimCadeia = document.getElementById(`classificacao_fim_cadeia_${index}`);
        
        const tipoFimCadeiaValue = tipoFimCadeia ? tipoFimCadeia.value : '';
        const classificacao = classificacaoFimCadeia ? classificacaoFimCadeia.value : '';
        
        // Se o usuário selecionou um tipo de origem (M ou T), usar esse tipo
        // Caso contrário, usar o tipo de fim de cadeia
        let tipoOrigem = '';
        let numeroOrigem = '';
        
        if (tipoSelect && tipoSelect.value && numeroInput && numeroInput.value.trim()) {
            tipoOrigem = tipoSelect.value; // M ou T
            numeroOrigem = numeroInput.value.trim(); // Número digitado pelo usuário
        } else {
            // Se não selecionou tipo de origem, usar o tipo de fim de cadeia
            tipoOrigem = tipoFimCadeiaValue;
            numeroOrigem = '';
        }
        
        // Criar origem com tipo de origem, número, tipo de fim de cadeia e classificação
        const origemCompleta = `FIM_CADEIA:${tipoOrigem}:${numeroOrigem}:${tipoFimCadeiaValue}:${classificacao}`;
        hiddenInput.value = origemCompleta;
        console.log(`Origem ${index} atualizada: ${origemCompleta} (fim de cadeia marcado)`);
        return;
    }
    
    // Processamento normal para M/T + número
    if (!tipoSelect || !numeroInput) return;
    
    const tipo = tipoSelect.value;
    const numero = numeroInput.value.trim();
    
    if (tipo && numero) {
        // Juntar M/T + número
        const origemCompleta = tipo + numero;
        hiddenInput.value = origemCompleta;
        console.log(`Origem ${index} atualizada: ${origemCompleta}`);
    } else {
        hiddenInput.value = '';
    }
}

function encontrarProximoCampo(index) {
    // Buscar próximo campo na mesma origem
    const campos = [
        `cartorio_origem_nome_${index}`,
        `cartorio_origem_nome`, // fallback para primeira origem
        `livro_origem_${index}`,
        `livro_origem`, // fallback
        `folha_origem_${index}`,
        `folha_origem` // fallback
    ];
    
    for (const campoId of campos) {
        const campo = document.getElementById(campoId);
        if (campo && campo.offsetParent !== null) { // campo visível
            return campo;
        }
    }
    
    return null;
}

function adicionarOrigemSimples() {
    // Encontrar próximo índice disponível
    let proximoIndex = 0;
    while (document.getElementById(`tipo_origem_${proximoIndex}`)) {
        proximoIndex++;
    }
    
    // Clonar estrutura da primeira origem
    const primeiraOrigem = document.querySelector('[data-origem-index="0"]');
    if (!primeiraOrigem) return;
    
    const novaOrigem = primeiraOrigem.cloneNode(true);
    
    // Atualizar IDs e names para o novo índice
    atualizarIdsOrigem(novaOrigem, proximoIndex);
    
    // Inserir após a última origem
    const container = document.getElementById('origens-container');
    if (container) {
        container.insertBefore(novaOrigem, container.lastElementChild);
        
        // Configurar nova origem
        configurarOrigem(proximoIndex);
        
        // Focar no select da nova origem
        const tipoSelect = document.getElementById(`tipo_origem_${proximoIndex}`);
        if (tipoSelect) {
            tipoSelect.focus();
        }
        
        console.log(`Nova origem ${proximoIndex} adicionada`);
    }
}

function atualizarIdsOrigem(elemento, novoIndex) {
    // Atualizar data-origem-index
    elemento.setAttribute('data-origem-index', novoIndex);
    
    // Atualizar todos os IDs e names
    const elementos = elemento.querySelectorAll('[id], [name]');
    elementos.forEach(el => {
        // Atualizar ID
        if (el.id) {
            el.id = el.id.replace(/_0$/, `_${novoIndex}`).replace(/^origem_completa$/, `origem_completa_${novoIndex}`);
        }
        
        // Atualizar name
        if (el.name) {
            if (el.name.includes('[]')) {
                // Manter array para compatibilidade
                el.name = el.name.replace(/_0$/, `_${novoIndex}`);
            }
        }
    });
    
    // Atualizar labels e for
    const labels = elemento.querySelectorAll('label[for]');
    labels.forEach(label => {
        const forAttr = label.getAttribute('for');
        if (forAttr) {
            label.setAttribute('for', forAttr.replace(/_0$/, `_${novoIndex}`));
        }
    });
}

function migrarDadosExistentes(index) {
    const hiddenInput = document.getElementById(`origem_completa_hidden_${index}`);
    const tipoSelect = document.getElementById(`tipo_origem_${index}`);
    const numeroInput = document.getElementById(`numero_origem_${index}`);
    
    if (!hiddenInput || !hiddenInput.value || !tipoSelect || !numeroInput) return;
    
    const origemExistente = hiddenInput.value.trim();
    
    // Tentar extrair M/T + número
    const match = origemExistente.match(/^([MT])(\d+)/);
    if (match) {
        const tipo = match[1];
        const numero = match[2];
        
        // Definir valores
        tipoSelect.value = tipo;
        numeroInput.value = numero;
        numeroInput.disabled = false;
        
        console.log(`Dados migrados para origem ${index}: ${origemExistente} -> ${tipo} + ${numero}`);
    }
}

function configurarValidacaoInicioMatricula(index) {
    // Verificar se é início de matrícula
    const tipoLancamentoSelect = document.querySelector('select[name="tipo_lancamento"]');
    if (!tipoLancamentoSelect) return;
    
    // Função para verificar se é início de matrícula
    function isInicioMatricula() {
        const opcaoSelecionada = tipoLancamentoSelect.options[tipoLancamentoSelect.selectedIndex];
        const dataTipo = opcaoSelecionada ? opcaoSelecionada.getAttribute('data-tipo') : null;
        return dataTipo === 'inicio_matricula';
    }
    
    // Função para verificar se fim de cadeia está preenchido
    function isFimCadeiaPreenchido() {
        const fimCadeiaToggle = document.getElementById(`fim_cadeia_${index}`);
        if (!fimCadeiaToggle || !fimCadeiaToggle.checked) return false;
        
        const tipoFimCadeia = document.getElementById(`tipo_fim_cadeia_${index}`);
        const classificacaoFimCadeia = document.getElementById(`classificacao_fim_cadeia_${index}`);
        
        return tipoFimCadeia && tipoFimCadeia.value && 
               classificacaoFimCadeia && classificacaoFimCadeia.value;
    }
    
    // Função para aplicar validação
    function aplicarValidacao() {
        const tipoSelect = document.getElementById(`tipo_origem_${index}`);
        const numeroInput = document.getElementById(`numero_origem_${index}`);
        
        if (!tipoSelect || !numeroInput) return;
        
        const isInicio = isInicioMatricula();
        const fimCadeiaPreenchido = isFimCadeiaPreenchido();
        
        if (isInicio && !fimCadeiaPreenchido) {
            // Para início de matrícula sem fim de cadeia, origem é obrigatória
            tipoSelect.required = true;
            numeroInput.required = true;
            
            // Adicionar classe de erro se vazio
            if (!tipoSelect.value || !numeroInput.value) {
                tipoSelect.classList.add('error');
                numeroInput.classList.add('error');
            } else {
                tipoSelect.classList.remove('error');
                numeroInput.classList.remove('error');
            }
        } else {
            // Para outros casos, origem não é obrigatória
            tipoSelect.required = false;
            numeroInput.required = false;
            tipoSelect.classList.remove('error');
            numeroInput.classList.remove('error');
        }
    }
    
    // Aplicar validação quando tipo de lançamento muda
    tipoLancamentoSelect.addEventListener('change', function() {
        // Delay para permitir que outras funções sejam executadas primeiro
        setTimeout(aplicarValidacao, 100);
    });
    
    // Aplicar validação quando campos de origem mudam
    const tipoSelect = document.getElementById(`tipo_origem_${index}`);
    const numeroInput = document.getElementById(`numero_origem_${index}`);
    
    if (tipoSelect) {
        tipoSelect.addEventListener('change', aplicarValidacao);
    }
    if (numeroInput) {
        numeroInput.addEventListener('input', aplicarValidacao);
    }
    
    // Aplicar validação quando fim de cadeia muda
    const fimCadeiaToggle = document.getElementById(`fim_cadeia_${index}`);
    if (fimCadeiaToggle) {
        fimCadeiaToggle.addEventListener('change', function() {
            setTimeout(aplicarValidacao, 100); // Delay para permitir que outros eventos sejam processados
            atualizarOrigemCompleta(index); // Atualizar origem quando checkbox muda
        });
    }
    
    // Atualizar origem quando tipo e classificação de fim de cadeia mudam
    const tipoFimCadeia = document.getElementById(`tipo_fim_cadeia_${index}`);
    if (tipoFimCadeia) {
        tipoFimCadeia.addEventListener('change', function() {
            // Controlar exibição dos campos baseado no tipo selecionado
            const especificacaoContainer = document.getElementById(`especificacao-container_${index}`);
            
            if (especificacaoContainer) {
                especificacaoContainer.style.display = this.value === 'outra' ? 'block' : 'none';
            }
            
            atualizarOrigemCompleta(index);
            aplicarValidacao();
        });
    }
    
    const classificacaoFimCadeia = document.getElementById(`classificacao_fim_cadeia_${index}`);
    if (classificacaoFimCadeia) {
        classificacaoFimCadeia.addEventListener('change', function() {
            atualizarOrigemCompleta(index);
            aplicarValidacao();
        });
    }
    
    // Aplicar validação inicial
    aplicarValidacao();
}

// Exportar funções para uso global
window.adicionarOrigemSimples = adicionarOrigemSimples;
