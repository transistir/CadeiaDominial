// Formulário de Lançamento - Funcionalidades
document.addEventListener('DOMContentLoaded', function() {
    // Elementos do formulário
    const tipoSelect = document.getElementById('tipo_lancamento');
    const averbacaoFields = document.getElementById('campos-averbacao');
    const registroFields = document.getElementById('campos-registro');
    const inicioMatriculaFields = document.getElementById('campos-inicio-matricula');
    const transacaoFields = document.getElementById('campos-transacao');
    
    // Função para alternar campos baseado no tipo selecionado
    function toggleFields() {
        const selectedOption = tipoSelect.options[tipoSelect.selectedIndex];
        const selectedTipo = selectedOption ? selectedOption.getAttribute('data-tipo') : '';
        const modoEdicao = document.body.classList.contains('modo-edicao');
        
        // Esconder todos os campos primeiro
        averbacaoFields.classList.add('hidden');
        registroFields.classList.add('hidden');
        inicioMatriculaFields.classList.add('hidden');
        transacaoFields.classList.add('hidden');
        
        // Controlar visibilidade do campo de número simples (input)
        const numeroSimplesField = document.querySelector('.form-group:has(#numero_lancamento_simples)');
        if (numeroSimplesField) {
            if (selectedTipo === 'inicio_matricula') {
                // Ocultar apenas o campo de input, mantendo o campo readonly visível
                const numeroSimplesInput = document.getElementById('numero_lancamento_simples');
                const numeroSimplesLabel = numeroSimplesField.querySelector('label[for="numero_lancamento_simples"]');
                const numeroSimplesSmall = numeroSimplesField.querySelector('small');
                
                if (numeroSimplesInput) numeroSimplesInput.style.display = 'none';
                if (numeroSimplesLabel) numeroSimplesLabel.style.display = 'none';
                if (numeroSimplesSmall) numeroSimplesSmall.style.display = 'none';
            } else {
                // Mostrar todos os elementos do campo
                const numeroSimplesInput = document.getElementById('numero_lancamento_simples');
                const numeroSimplesLabel = numeroSimplesField.querySelector('label[for="numero_lancamento_simples"]');
                const numeroSimplesSmall = numeroSimplesField.querySelector('small');
                
                if (numeroSimplesInput) numeroSimplesInput.style.display = 'block';
                if (numeroSimplesLabel) numeroSimplesLabel.style.display = 'block';
                if (numeroSimplesSmall) numeroSimplesSmall.style.display = 'block';
            }
        }
        
        // Mostrar campos baseado no tipo selecionado
        if (selectedTipo === 'averbacao') {
            averbacaoFields.classList.remove('hidden');
        } else if (selectedTipo === 'registro') {
            registroFields.classList.remove('hidden');
            transacaoFields.classList.remove('hidden');
        } else if (selectedTipo === 'inicio_matricula') {
            inicioMatriculaFields.classList.remove('hidden');
            // Não exibir bloco de transação para início de matrícula
            // Aplicar automaticamente a sigla da matrícula
            if (typeof gerarNumeroLancamento === 'function') {
                gerarNumeroLancamento();
            }
        }
    }
    
    // Inicializar campos após um pequeno delay para garantir que o DOM está pronto
    setTimeout(() => {
        toggleFields();
        
        // Carregar dados de pessoas existentes se estiver em modo de edição
        if (document.body.classList.contains('modo-edicao')) {
            // Carregar transmitentes existentes
            const transmitentesContainer = document.getElementById('transmitentes-container');
            if (transmitentesContainer && transmitentesContainer.children.length > 1) {
                transmitentesContainer.removeChild(transmitentesContainer.firstElementChild);
            }
            
            // Carregar adquirentes existentes
            const adquirentesContainer = document.getElementById('adquirentes-container');
            if (adquirentesContainer && adquirentesContainer.children.length > 1) {
                adquirentesContainer.removeChild(adquirentesContainer.firstElementChild);
            }
        }
    }, 100);
    
    // Adicionar listener para mudanças no tipo
    if (tipoSelect) {
        tipoSelect.addEventListener('change', toggleFields);
    }
    
    // Configurar geração automática do número do lançamento
    const numeroSimplesInput = document.getElementById('numero_lancamento_simples');
    const numeroCompletoInput = document.getElementById('numero_lancamento');
    
    if (numeroSimplesInput && numeroCompletoInput) {
        // Função para gerar a sigla completa
        window.gerarNumeroLancamento = function() {
            const numero = numeroSimplesInput.value.trim();
            const selectedOption = tipoSelect.options[tipoSelect.selectedIndex];
            const selectedTipo = selectedOption ? selectedOption.getAttribute('data-tipo') : '';
            
            // Obter a sigla da matrícula/transcrição do imóvel
            const siglaMatriculaInput = document.querySelector('input[name="sigla_matricula"]');
            let siglaMatricula = siglaMatriculaInput ? siglaMatriculaInput.value : '';
            
            // Garantir que a sigla tenha o prefixo M se não tiver
            if (siglaMatricula && !siglaMatricula.startsWith('M')) {
                siglaMatricula = 'M' + siglaMatricula;
            }
            
            if (selectedTipo === 'inicio_matricula') {
                // Para início de matrícula, aplicar automaticamente a sigla da matrícula
                numeroCompletoInput.value = siglaMatricula;
            } else if (numero && selectedTipo) {
                let sigla = '';
                
                if (selectedTipo === 'averbacao') {
                    sigla = `AV${numero}${siglaMatricula}`;
                } else if (selectedTipo === 'registro') {
                    sigla = `R${numero}${siglaMatricula}`;
                }
                
                numeroCompletoInput.value = sigla;
            } else {
                numeroCompletoInput.value = '';
            }
        };
        
        // Adicionar listeners
        numeroSimplesInput.addEventListener('input', window.gerarNumeroLancamento);
        if (tipoSelect) {
            tipoSelect.addEventListener('change', window.gerarNumeroLancamento);
        }
    }
    
    // Configurar autocomplete para pessoas existentes e adicionar listeners para novos campos
    setupPessoaAutocomplete();
    
    // Configurar autocomplete para origens existentes
    setupOrigemAutocomplete();
    
    // Autocomplete para cartório principal
    const cartorioInput = document.getElementById('cartorio_nome');
    const cartorioHidden = document.getElementById('cartorio');
    const cartorioSuggestions = document.querySelector('.cartorio-suggestions');
    
    if (cartorioInput && cartorioHidden && cartorioSuggestions) {
        setupCartorioAutocomplete(cartorioInput, cartorioHidden, cartorioSuggestions);
    }
    
    // Autocomplete para cartório de transação
    const cartorioTransacaoInput = document.getElementById('cartorio_transacao_nome');
    const cartorioTransacaoHidden = document.getElementById('cartorio_transacao');
    const cartorioTransacaoSuggestions = document.querySelector('.cartorio-transacao-suggestions');
    
    if (cartorioTransacaoInput && cartorioTransacaoHidden && cartorioTransacaoSuggestions) {
        setupCartorioAutocomplete(cartorioTransacaoInput, cartorioTransacaoHidden, cartorioTransacaoSuggestions);
    }
    
    // Autocomplete para cartório da origem (início de matrícula)
    const cartorioOrigemInicioInput = document.getElementById('cartorio_origem_nome_inicio');
    const cartorioOrigemInicioHidden = document.getElementById('cartorio_origem_inicio');
    const cartorioOrigemInicioSuggestions = document.querySelector('.cartorio-origem-inicio-suggestions');
    
    if (cartorioOrigemInicioInput && cartorioOrigemInicioHidden && cartorioOrigemInicioSuggestions) {
        setupCartorioAutocomplete(cartorioOrigemInicioInput, cartorioOrigemInicioHidden, cartorioOrigemInicioSuggestions);
    }
});

// Função para remover pessoa
function removePessoa(button) {
    const pessoaItem = button.closest('.pessoa-item');
    if (pessoaItem) {
        pessoaItem.remove();
    }
}

// Função para adicionar transmitente
function adicionarTransmitente() {
    // Tentar encontrar o container correto baseado no contexto
    let container = document.getElementById('transmitentes-container-registro');
    if (!container) {
        container = document.getElementById('transmitentes-container');
    }
    if (!container) {
        return;
    }
    const pessoaDiv = document.createElement('div');
    pessoaDiv.className = 'pessoa-item';
    pessoaDiv.innerHTML = `
        <div class="pessoa-input-group">
            <div class="autocomplete-container">
                <input type="text" name="transmitente_nome[]" class="transmitente-nome" placeholder="Digite o nome do transmitente" autocomplete="off">
                <input type="hidden" name="transmitente[]" class="transmitente-id">
                <div class="autocomplete-suggestions transmitente-suggestions"></div>
            </div>
            <button type="button" class="btn btn-sm btn-danger remove-pessoa" onclick="removePessoa(this)">×</button>
        </div>
    `;
    container.appendChild(pessoaDiv);
    
    // Configurar autocomplete para o novo campo
    const newInput = pessoaDiv.querySelector('.transmitente-nome');
    const newHidden = pessoaDiv.querySelector('.transmitente-id');
    const newSuggestions = pessoaDiv.querySelector('.transmitente-suggestions');
    setupPessoaAutocompleteField(newInput, newHidden, newSuggestions, 'transmitente');
}

// Função para adicionar adquirente
function adicionarAdquirente() {
    // Tentar encontrar o container correto baseado no contexto
    let container = document.getElementById('adquirentes-container');
    if (!container) {
        container = document.getElementById('adquirentes-container-registro');
    }
    if (!container) {
        return;
    }
    const pessoaDiv = document.createElement('div');
    pessoaDiv.className = 'pessoa-item';
    pessoaDiv.innerHTML = `
        <div class="pessoa-input-group">
            <div class="autocomplete-container">
                <input type="text" name="adquirente_nome[]" class="adquirente-nome" placeholder="Digite o nome do adquirente" autocomplete="off">
                <input type="hidden" name="adquirente[]" class="adquirente-id">
                <div class="autocomplete-suggestions adquirente-suggestions"></div>
            </div>
            <button type="button" class="btn btn-sm btn-danger remove-pessoa" onclick="removePessoa(this)">×</button>
        </div>
    `;
    container.appendChild(pessoaDiv);
    
    // Configurar autocomplete para o novo campo
    const newInput = pessoaDiv.querySelector('.adquirente-nome');
    const newHidden = pessoaDiv.querySelector('.adquirente-id');
    const newSuggestions = pessoaDiv.querySelector('.adquirente-suggestions');
    setupPessoaAutocompleteField(newInput, newHidden, newSuggestions, 'adquirente');
}

// Função para configurar autocomplete de pessoa
function setupPessoaAutocompleteField(input, hidden, suggestions, tipo) {
    input.addEventListener('input', function() {
        const query = this.value.trim();
        if (query.length < 2) {
            suggestions.style.display = 'none';
            return;
        }
        
        fetch(`/dominial/pessoa-autocomplete/?q=${encodeURIComponent(query)}`)
            .then(response => response.json())
            .then(data => {
                suggestions.innerHTML = '';
                if (data.results && data.results.length > 0) {
                    data.results.forEach(pessoa => {
                        const div = document.createElement('div');
                        div.className = 'autocomplete-suggestion';
                        div.textContent = pessoa.nome;
                        div.addEventListener('click', function() {
                            input.value = pessoa.nome;
                            hidden.value = pessoa.id;
                            suggestions.style.display = 'none';
                        });
                        suggestions.appendChild(div);
                    });
                    suggestions.style.display = 'block';
                } else {
                    suggestions.style.display = 'none';
                }
            })
            .catch(error => {
                console.error('Erro ao buscar pessoas:', error);
                suggestions.style.display = 'none';
            });
    });
    
    // Esconder sugestões quando clicar fora
    document.addEventListener('click', function(e) {
        if (!input.contains(e.target) && !suggestions.contains(e.target)) {
            suggestions.style.display = 'none';
        }
    });
}

// Função para configurar autocomplete de cartório
function setupCartorioAutocomplete(input, hidden, suggestions) {
    input.addEventListener('input', function() {
        const query = this.value.trim();
        if (query.length < 2) {
            suggestions.style.display = 'none';
            return;
        }
        
        fetch(`/dominial/cartorio-autocomplete/?q=${encodeURIComponent(query)}`)
            .then(response => response.json())
            .then(data => {
                suggestions.innerHTML = '';
                if (data.results && data.results.length > 0) {
                    data.results.forEach(cartorio => {
                        const div = document.createElement('div');
                        div.className = 'autocomplete-suggestion';
                        div.textContent = cartorio.nome;
                        div.addEventListener('click', function() {
                            input.value = cartorio.nome;
                            hidden.value = cartorio.id;
                            suggestions.style.display = 'none';
                        });
                        suggestions.appendChild(div);
                    });
                    suggestions.style.display = 'block';
                } else {
                    suggestions.style.display = 'none';
                }
            })
            .catch(error => {
                console.error('Erro ao buscar cartórios:', error);
                suggestions.style.display = 'none';
            });
    });
    
    // Esconder sugestões quando clicar fora
    document.addEventListener('click', function(e) {
        if (!input.contains(e.target) && !suggestions.contains(e.target)) {
            suggestions.style.display = 'none';
        }
    });
}

// Função para remover origem
function removeOrigem(button) {
    const origemItem = button.closest('.origem-item');
    if (origemItem) {
        origemItem.remove();
    }
}

// Função para adicionar origem
function adicionarOrigem() {
    const container = document.getElementById('origens-container');
    if (!container) {
        return;
    }
    
    const origemDiv = document.createElement('div');
    origemDiv.className = 'origem-item';
    origemDiv.innerHTML = `
        <div class="origem-input-group">
            <div class="grid-2">
                <div class="form-group">
                    <label>Origem *</label>
                    <input type="text" name="origem[]" class="origem-texto" 
                           placeholder="Ex: Número do registro anterior, descrição, etc." required>
                </div>
                <div class="form-group">
                    <label>Cartório de Registro da Origem *</label>
                    <div class="autocomplete-container">
                        <input type="text" name="cartorio_origem_nome[]" class="cartorio-origem-nome" 
                               placeholder="Digite o nome do cartório" autocomplete="off" required>
                        <input type="hidden" name="cartorio_origem[]" class="cartorio-origem-id">
                        <div class="autocomplete-suggestions cartorio-origem-suggestions"></div>
                    </div>
                </div>
            </div>
            <button type="button" class="btn btn-sm btn-danger remove-origem" onclick="removeOrigem(this)" title="Remover origem">×</button>
        </div>
    `;
    container.appendChild(origemDiv);
    
    // Configurar autocomplete para o novo campo de cartório
    const newInput = origemDiv.querySelector('.cartorio-origem-nome');
    const newHidden = origemDiv.querySelector('.cartorio-origem-id');
    const newSuggestions = origemDiv.querySelector('.cartorio-origem-suggestions');
    setupCartorioAutocomplete(newInput, newHidden, newSuggestions);
}

// Função para configurar autocomplete geral de pessoas
function setupPessoaAutocomplete() {
    const transmitenteInputs = document.querySelectorAll('.transmitente-nome');
    const adquirenteInputs = document.querySelectorAll('.adquirente-nome');
    
    transmitenteInputs.forEach((input, index) => {
        const hidden = document.querySelectorAll('.transmitente-id')[index];
        const suggestions = document.querySelectorAll('.transmitente-suggestions')[index];
        if (input && hidden && suggestions) {
            setupPessoaAutocompleteField(input, hidden, suggestions, 'transmitente');
        }
    });
    
    adquirenteInputs.forEach((input, index) => {
        const hidden = document.querySelectorAll('.adquirente-id')[index];
        const suggestions = document.querySelectorAll('.adquirente-suggestions')[index];
        if (input && hidden && suggestions) {
            setupPessoaAutocompleteField(input, hidden, suggestions, 'adquirente');
        }
    });
}

// Função para configurar autocomplete geral de origens
function setupOrigemAutocomplete() {
    const cartorioOrigemInputs = document.querySelectorAll('.cartorio-origem-nome');
    
    cartorioOrigemInputs.forEach((input, index) => {
        const hidden = document.querySelectorAll('.cartorio-origem-id')[index];
        const suggestions = document.querySelectorAll('.cartorio-origem-suggestions')[index];
        if (input && hidden && suggestions) {
            setupCartorioAutocomplete(input, hidden, suggestions);
        }
    });
} 