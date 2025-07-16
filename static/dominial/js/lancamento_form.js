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
        
        // Desabilitar campos hidden para evitar validação HTML
        averbacaoFields.querySelectorAll('input, select, textarea').forEach(field => field.disabled = true);
        registroFields.querySelectorAll('input, select, textarea').forEach(field => field.disabled = true);
        inicioMatriculaFields.querySelectorAll('input, select, textarea').forEach(field => field.disabled = true);
        transacaoFields.querySelectorAll('input, select, textarea').forEach(field => field.disabled = true);
        
        // Controlar visibilidade do campo de número simples (input)
        const numeroSimplesField = document.querySelector('.numero-simples-field');
        if (numeroSimplesField) {
            if (selectedTipo === 'inicio_matricula') {
                // Ocultar o campo de número simples para início de matrícula
                numeroSimplesField.style.display = 'none';
            } else {
                // Mostrar o campo para outros tipos
                numeroSimplesField.style.display = 'block';
                
                // Apenas adicionar indicador visual de obrigatório (sem destacar em vermelho)
                if (selectedTipo === 'registro' || selectedTipo === 'averbacao') {
                    // Adicionar indicador visual de obrigatório
                    const label = numeroSimplesField.querySelector('label') || numeroSimplesField.previousElementSibling;
                    if (label && !label.querySelector('.required-indicator')) {
                        const indicator = document.createElement('span');
                        indicator.className = 'required-indicator';
                        indicator.textContent = ' *';
                        indicator.style.color = '#ff6b6b';
                        indicator.style.fontWeight = 'bold';
                        label.appendChild(indicator);
                    }
                } else {
                    // Remover indicador visual
                    const label = numeroSimplesField.querySelector('label') || numeroSimplesField.previousElementSibling;
                    if (label) {
                        const indicator = label.querySelector('.required-indicator');
                        if (indicator) {
                            indicator.remove();
                        }
                    }
                }
            }
        }
        
        // Mostrar campos baseado no tipo selecionado
        if (selectedTipo === 'averbacao') {
            averbacaoFields.classList.remove('hidden');
            averbacaoFields.querySelectorAll('input, select, textarea').forEach(field => field.disabled = false);
        } else if (selectedTipo === 'registro') {
            registroFields.classList.remove('hidden');
            transacaoFields.classList.remove('hidden');
            registroFields.querySelectorAll('input, select, textarea').forEach(field => field.disabled = false);
            transacaoFields.querySelectorAll('input, select, textarea').forEach(field => field.disabled = false);
        } else if (selectedTipo === 'inicio_matricula') {
            inicioMatriculaFields.classList.remove('hidden');
            inicioMatriculaFields.querySelectorAll('input, select, textarea').forEach(field => field.disabled = false);
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
        
        // Verificar se há erro de número duplicado e destacar o campo
        const numeroLancamentoError = document.querySelector('input[name="numero_lancamento_simples"]');
        const form = document.getElementById('lancamento-form');
        if (numeroLancamentoError && form && form.dataset.numeroLancamentoError === 'true') {
            numeroLancamentoError.style.border = '2px solid #ff6b6b';
            numeroLancamentoError.style.backgroundColor = '#fff5f5';
        }
        
        // Preencher automaticamente o número do lançamento com a sigla da matrícula
        const siglaMatriculaInput = document.querySelector('input[name="sigla_matricula"]');
        const numeroCompletoInput = document.getElementById('numero_lancamento');
        
        if (siglaMatriculaInput && numeroCompletoInput && !numeroCompletoInput.value) {
            let siglaMatricula = siglaMatriculaInput.value;
            // Garantir que a sigla tenha o prefixo M se não tiver
            if (siglaMatricula && !siglaMatricula.startsWith('M')) {
                siglaMatricula = 'M' + siglaMatricula;
            }
            numeroCompletoInput.value = siglaMatricula;
        }
        
        // Extrair número do lançamento no modo de edição
        if (document.body.classList.contains('modo-edicao')) {
            const numeroSimplesInput = document.getElementById('numero_lancamento_simples');
            const numeroCompletoInput = document.getElementById('numero_lancamento');
            const tipoSelect = document.getElementById('tipo_lancamento');
            
            if (numeroSimplesInput && numeroCompletoInput && tipoSelect) {
                const siglaCompleta = numeroCompletoInput.value;
                const selectedOption = tipoSelect.options[tipoSelect.selectedIndex];
                const selectedTipo = selectedOption ? selectedOption.getAttribute('data-tipo') : '';
                
                if (siglaCompleta && selectedTipo) {
                    let numero = '';
                    if (selectedTipo === 'averbacao' && siglaCompleta.startsWith('AV')) {
                        // Para averbação: AV + número + sigla_matricula
                        numero = siglaCompleta.substring(2);
                        // Remover a sigla da matrícula do final (assumindo que começa com M)
                        const indexM = numero.indexOf('M');
                        if (indexM > 0) {
                            numero = numero.substring(0, indexM);
                        }
                    } else if (selectedTipo === 'registro' && siglaCompleta.startsWith('R')) {
                        // Para registro: R + número + sigla_matricula
                        numero = siglaCompleta.substring(1);
                        // Remover a sigla da matrícula do final (assumindo que começa com M)
                        const indexM = numero.indexOf('M');
                        if (indexM > 0) {
                            numero = numero.substring(0, indexM);
                        }
                    }
                    numeroSimplesInput.value = numero;
                }
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
            } else if (selectedTipo && siglaMatricula) {
                // Se não há número simples mas há tipo selecionado, deixar vazio para o usuário preencher
                numeroCompletoInput.value = '';
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
            const cartorioTransacaoInput = document.getElementById('cartorio_transmissao_nome');
        const cartorioTransacaoHidden = document.getElementById('cartorio_transmissao');
            const cartorioTransacaoSuggestions = document.querySelector('.cartorio-transmissao-suggestions');
    
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
    
    // Debug: Adicionar listener para capturar envio do formulário
    const form = document.getElementById('lancamento-form');
    if (form) {
        form.addEventListener('submit', function(e) {
            console.log('Formulário sendo enviado...');
            console.log('Tipo selecionado:', tipoSelect.value);
            console.log('Número do lançamento:', document.getElementById('numero_lancamento').value);
            console.log('Data:', document.getElementById('data').value);
            console.log('Cartório:', document.getElementById('cartorio').value);
            console.log('Cartório nome:', document.getElementById('cartorio_nome').value);
            
            // Verificar se todos os campos obrigatórios estão preenchidos
            const requiredFields = form.querySelectorAll('[required]');
            let hasError = false;
            
            requiredFields.forEach(field => {
                if (!field.value.trim()) {
                    console.error('Campo obrigatório vazio:', field.name);
                    hasError = true;
                }
            });
            
            // Validação específica para número simples em registro e averbação
            const selectedOption = tipoSelect.options[tipoSelect.selectedIndex];
            const selectedTipo = selectedOption ? selectedOption.getAttribute('data-tipo') : '';
            const numeroSimplesValue = numeroSimplesInput ? numeroSimplesInput.value.trim() : '';
            
            if ((selectedTipo === 'registro' || selectedTipo === 'averbacao') && !numeroSimplesValue) {
                console.error('Número simples é obrigatório para registro e averbação');
                hasError = true;
                
                // Mostrar mensagem de erro
                alert('Para lançamentos do tipo "Registro" e "Averbação", é obrigatório preencher o campo "Número" (ex: 1, 5, etc.)');
                
                // Destacar o campo
                if (numeroSimplesInput) {
                    numeroSimplesInput.style.borderColor = 'red';
                    numeroSimplesInput.focus();
                }
                
                e.preventDefault();
                return false;
            }
            
            if (hasError) {
                console.error('Formulário tem campos obrigatórios vazios!');
                e.preventDefault();
                return false;
            }
            
            console.log('Formulário válido, enviando...');
        });
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
        container = document.getElementById('transmitentes-container-averbacao');
    }
    if (!container) {
        container = document.getElementById('transmitentes-container-inicio');
    }
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
    let container = document.getElementById('adquirentes-container-registro');
    if (!container) {
        container = document.getElementById('adquirentes-container-averbacao');
    }
    if (!container) {
        container = document.getElementById('adquirentes-container-inicio');
    }
    if (!container) {
        container = document.getElementById('adquirentes-container');
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
    
    // Contar quantas origens já existem para gerar IDs únicos
    const existingOrigins = container.querySelectorAll('.origem-item');
    const newIndex = existingOrigins.length;
    
    const origemDiv = document.createElement('div');
    origemDiv.className = 'origem-item';
    origemDiv.innerHTML = `
        <div class="form-group origem-field">
            <input type="text" name="origem_completa[]" id="origem_completa_${newIndex}" class="origem-texto" 
                   placeholder="Ex: Número do registro anterior, descrição, etc." required>
        </div>
        <div class="form-group cartorio-field">
            <div class="autocomplete-container">
                <input type="text" name="cartorio_origem_nome[]" id="cartorio_origem_nome_${newIndex}" class="cartorio-origem-nome" 
                       placeholder="Digite o nome do cartório" autocomplete="off" required>
                <input type="hidden" name="cartorio_origem[]" id="cartorio_origem_${newIndex}" class="cartorio-origem-id">
                <div class="autocomplete-suggestions cartorio-origem-suggestions"></div>
            </div>
        </div>
        <div class="form-group livro-field">
            <input type="text" name="livro_origem[]" id="livro_origem_${newIndex}" class="livro-origem" 
                   placeholder="Ex: 1, 2, A, etc.">
        </div>
        <div class="form-group folha-field">
            <input type="text" name="folha_origem[]" id="folha_origem_${newIndex}" class="folha-origem" 
                   placeholder="Ex: 1, 2, A, etc.">
        </div>
        <button type="button" class="btn btn-sm btn-danger remove-origem" onclick="removeOrigem(this)" title="Remover origem">×</button>
    `;
    container.appendChild(origemDiv);
    
    // Configurar autocomplete para o novo campo de cartório
    const newInput = origemDiv.querySelector(`#cartorio_origem_nome_${newIndex}`);
    const newHidden = origemDiv.querySelector(`#cartorio_origem_${newIndex}`);
    const newSuggestions = origemDiv.querySelector('.cartorio-origem-suggestions');
    setupCartorioAutocomplete(newInput, newHidden, newSuggestions);
}

// Função para configurar autocomplete geral de origens
function setupOrigemAutocomplete() {
    console.log('Configurando autocomplete para origens...');
    
    // Configurar autocomplete para todos os campos de cartório de origem
    const cartorioOrigemInputs = document.querySelectorAll('.cartorio-origem-nome');
    console.log('Encontrados', cartorioOrigemInputs.length, 'campos de cartório de origem');
    
    cartorioOrigemInputs.forEach((input, index) => {
        console.log(`Configurando campo ${index}:`, input.id);
        
        // Buscar o campo hidden correspondente
        const hidden = input.closest('.autocomplete-container').querySelector('.cartorio-origem-id');
        const suggestions = input.closest('.autocomplete-container').querySelector('.cartorio-origem-suggestions');
    
        console.log('Hidden field:', hidden ? hidden.id : 'não encontrado');
        console.log('Suggestions:', suggestions ? 'encontrado' : 'não encontrado');
        
        if (input && hidden && suggestions) {
            setupCartorioAutocomplete(input, hidden, suggestions);
            console.log(`Autocomplete configurado para campo ${index}`);
        } else {
            console.error(`Erro ao configurar autocomplete para campo ${index}:`, {
                input: !!input,
                hidden: !!hidden,
                suggestions: !!suggestions
            });
    }
    });
} 