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
        
        // Verificar se o documento é do tipo transcrição
        // Método 1: Verificar se há uma variável global definida no template
        const isTranscricaoGlobal = window.isTranscricao === true;
        
        // Método 2: Verificar pelo número do documento (fallback)
        const documentoNumero = document.querySelector('input[name="sigla_matricula"]');
        const isTranscricaoByNumber = documentoNumero && documentoNumero.value && (
            documentoNumero.value.startsWith('T') || 
            documentoNumero.value.toUpperCase().includes('TRANS')
        );
        
        // Método 3: Verificar se há um elemento com classe indicando transcrição
        const isTranscricaoByClass = document.body.classList.contains('documento-transcricao');
        
        const isTranscricao = isTranscricaoGlobal || isTranscricaoByNumber || isTranscricaoByClass;
        

        
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
            
            // Para transcrições, sempre mostrar bloco de transmissão
            if (isTranscricao) {
                transacaoFields.classList.remove('hidden');
                transacaoFields.querySelectorAll('input, select, textarea').forEach(field => field.disabled = false);
            }
        } else if (selectedTipo === 'registro') {
            registroFields.classList.remove('hidden');
            transacaoFields.classList.remove('hidden');
            registroFields.querySelectorAll('input, select, textarea').forEach(field => field.disabled = false);
            transacaoFields.querySelectorAll('input, select, textarea').forEach(field => field.disabled = false);
        } else if (selectedTipo === 'inicio_matricula') {
            inicioMatriculaFields.classList.remove('hidden');
            inicioMatriculaFields.querySelectorAll('input, select, textarea').forEach(field => field.disabled = false);
            
            // Para transcrições, sempre mostrar bloco de transmissão
            if (isTranscricao) {
                transacaoFields.classList.remove('hidden');
                transacaoFields.querySelectorAll('input, select, textarea').forEach(field => field.disabled = false);
            }
            
            // Não exibir bloco de transação para início de matrícula de matrícula
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
            // Não adicionar prefixo automaticamente - usar o que já está no documento
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
                        // Remover a sigla da matrícula/transcrição do final (pode começar com M ou T)
                        const indexM = numero.indexOf('M');
                        const indexT = numero.indexOf('T');
                        if (indexM > 0 && (indexT === -1 || indexM < indexT)) {
                            numero = numero.substring(0, indexM);
                        } else if (indexT > 0 && (indexM === -1 || indexT < indexM)) {
                            numero = numero.substring(0, indexT);
                        }
                    } else if (selectedTipo === 'registro' && siglaCompleta.startsWith('R')) {
                        // Para registro: R + número + sigla_matricula
                        numero = siglaCompleta.substring(1);
                        // Remover a sigla da matrícula/transcrição do final (pode começar com M ou T)
                        const indexM = numero.indexOf('M');
                        const indexT = numero.indexOf('T');
                        if (indexM > 0 && (indexT === -1 || indexM < indexT)) {
                            numero = numero.substring(0, indexM);
                        } else if (indexT > 0 && (indexM === -1 || indexT < indexM)) {
                            numero = numero.substring(0, indexT);
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
            
            // Usar a sigla como está no documento (não adicionar prefixo automaticamente)
            
            if (selectedTipo === 'inicio_matricula') {
                // Para início de matrícula, aplicar automaticamente a sigla da matrícula
                numeroCompletoInput.value = siglaMatricula;
            } else if (numero && selectedTipo) {
                let sigla = '';
                
                if (selectedTipo === 'averbacao') {
                    sigla = `AV${numero} ${siglaMatricula}`;
                } else if (selectedTipo === 'registro') {
                    sigla = `R${numero} ${siglaMatricula}`;
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
    
    // Adicionar listener para capturar envio do formulário
    const form = document.getElementById('lancamento-form');
    if (form) {
        form.addEventListener('submit', function(e) {
            // Verificar se todos os campos obrigatórios estão preenchidos
            const requiredFields = form.querySelectorAll('[required]');
            let hasError = false;
            
            requiredFields.forEach(field => {
                if (!field.value.trim()) {
                    hasError = true;
                }
            });
            
            // CORREÇÃO: Validar cartórios das origens
            const cartorioOrigemInputs = document.querySelectorAll('.cartorio-origem-nome');
            const cartorioOrigemHiddens = document.querySelectorAll('.cartorio-origem-id');
            
            for (let i = 0; i < cartorioOrigemInputs.length; i++) {
                const input = cartorioOrigemInputs[i];
                const hidden = cartorioOrigemHiddens[i];
                
                if (input.value.trim() && !hidden.value.trim()) {
                    // Usuário digitou um nome mas não selecionou da lista
                    hasError = true;
                    input.classList.add('error');
                    input.focus();
                    
                    // Mostrar mensagem de erro
                    alert(`❌ Cartório inválido na origem ${i+1}: "${input.value}". Selecione um cartório da lista. Não é possível criar novos cartórios.`);
                    
                    e.preventDefault();
                    return false;
                }
            }
            
            // Validação específica para número simples em registro e averbação
            const selectedOption = tipoSelect.options[tipoSelect.selectedIndex];
            const selectedTipo = selectedOption ? selectedOption.getAttribute('data-tipo') : '';
            const numeroSimplesValue = numeroSimplesInput ? numeroSimplesInput.value.trim() : '';
            
            if ((selectedTipo === 'registro' || selectedTipo === 'averbacao') && !numeroSimplesValue) {
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
                e.preventDefault();
                return false;
            }
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
    // Procurar por todos os containers possíveis e usar o primeiro que estiver visível
    const containers = [
        'transmitentes-container-registro',
        'transmitentes-container-averbacao', 
        'transmitentes-container-inicio',
        'transmitentes-container'
    ];
    
    let container = null;
    for (const containerId of containers) {
        const element = document.getElementById(containerId);
        if (element && !element.closest('.hidden')) {
            container = element;
            break;
        }
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
    // Procurar por todos os containers possíveis e usar o primeiro que estiver visível
    const containers = [
        'adquirentes-container-registro',
        'adquirentes-container-averbacao', 
        'adquirentes-container-inicio',
        'adquirentes-container'
    ];
    
    let container = null;
    for (const containerId of containers) {
        const element = document.getElementById(containerId);
        if (element && !element.closest('.hidden')) {
            container = element;
            break;
        }
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
            // Limpar campo hidden se não há seleção válida
            hidden.value = '';
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
                            // Remover classe de erro se existir
                            input.classList.remove('error');
                        });
                        suggestions.appendChild(div);
                    });
                    suggestions.style.display = 'block';
                } else {
                    suggestions.style.display = 'none';
                    // Mostrar mensagem de "Nenhum cartório encontrado"
                    const noResultsDiv = document.createElement('div');
                    noResultsDiv.className = 'autocomplete-suggestion no-results';
                    noResultsDiv.textContent = 'Nenhum cartório encontrado. Digite para buscar...';
                    suggestions.appendChild(noResultsDiv);
                    suggestions.style.display = 'block';
                }
            })
            .catch(error => {
                console.error('Erro ao buscar cartórios:', error);
                suggestions.style.display = 'none';
            });
    });
    
    // Validar quando o usuário terminar de digitar
    input.addEventListener('blur', function() {
        setTimeout(() => {
            if (this.value.trim() && !hidden.value) {
                // Usuário digitou algo mas não selecionou da lista
                this.classList.add('error');
                this.setAttribute('title', 'Selecione um cartório da lista. Não é possível criar novos cartórios.');
            } else {
                this.classList.remove('error');
                this.removeAttribute('title');
            }
        }, 200);
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
    const origemIndex = origemItem.getAttribute('data-origem-index');
    const fimCadeiaContainer = document.getElementById(`fim-cadeia-origem-container_${origemIndex}`);
    
    // Remover o item de origem
    origemItem.remove();
    
    // Remover o container de fim de cadeia se existir
    if (fimCadeiaContainer) {
        fimCadeiaContainer.remove();
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
        <div class="form-group fim-cadeia-field">
            <div class="fim-cadeia-toggle-container">
                <input type="checkbox" name="fim_cadeia[]" id="fim_cadeia_${newIndex}" 
                       class="fim-cadeia-toggle" value="${newIndex}">
                <label for="fim_cadeia_${newIndex}" class="fim-cadeia-label">
                </label>
            </div>
        </div>
        <button type="button" class="btn btn-sm btn-danger remove-origem" onclick="removeOrigem(this)" title="Remover origem">×</button>
    `;
    container.appendChild(origemDiv);
    
    // Adicionar container de fim de cadeia para esta origem
    const fimCadeiaContainer = document.createElement('div');
    fimCadeiaContainer.className = 'fim-cadeia-origem-container';
    fimCadeiaContainer.id = `fim-cadeia-origem-container_${newIndex}`;
    fimCadeiaContainer.style.display = 'none';
    
    fimCadeiaContainer.innerHTML = `
        <div class="grid-2">
            <div class="form-group">
                <label for="tipo_fim_cadeia_${newIndex}">Tipo do Fim de Cadeia *</label>
                <select name="tipo_fim_cadeia[]" id="tipo_fim_cadeia_${newIndex}" class="form-control tipo-fim-cadeia-select">
                    <option value="">Selecione o tipo...</option>
                    <option value="destacamento_publico">Destacamento do Patrimônio Público</option>
                    <option value="outra">Outra</option>
                    <option value="sem_origem">Sem Origem</option>
                </select>
            </div>
            
            <div class="form-group">
                <label for="classificacao_fim_cadeia_${newIndex}">Classificação do Fim de Cadeia *</label>
                <select name="classificacao_fim_cadeia[]" id="classificacao_fim_cadeia_${newIndex}" class="form-control classificacao-fim-cadeia-select">
                    <option value="">Selecione a classificação...</option>
                    <option value="origem_lidima">Imóvel com Origem Lídima</option>
                    <option value="sem_origem">Imóvel sem Origem</option>
                    <option value="inconclusa">Situação Inconclusa</option>
                </select>
            </div>
        </div>
        
        <!-- Campo de especificação (aparece quando tipo = 'outra') -->
        <div class="form-group especificacao-container" id="especificacao-container_${newIndex}" style="display: none;">
            <label for="especificacao_fim_cadeia_${newIndex}">Especificação *</label>
            <textarea name="especificacao_fim_cadeia[]" id="especificacao_fim_cadeia_${newIndex}" class="form-control especificacao-fim-cadeia" 
                      placeholder="Detalhe a especificação..."></textarea>
        </div>
    `;
    
    container.appendChild(fimCadeiaContainer);
    
    // Configurar autocomplete para o novo campo de cartório
    const newInput = origemDiv.querySelector(`#cartorio_origem_nome_${newIndex}`);
    const newHidden = origemDiv.querySelector(`#cartorio_origem_${newIndex}`);
    const newSuggestions = origemDiv.querySelector('.cartorio-origem-suggestions');
    setupCartorioAutocomplete(newInput, newHidden, newSuggestions);
    
    // Configurar toggle de fim de cadeia para a nova origem
    const newToggle = origemDiv.querySelector(`#fim_cadeia_${newIndex}`);
    setupFimCadeiaTogglePorOrigem(newToggle);
    
    // Configurar select de tipo para a nova origem
    const newTipoSelect = fimCadeiaContainer.querySelector(`#tipo_fim_cadeia_${newIndex}`);
    setupTipoFimCadeiaSelectPorOrigem(newTipoSelect);
}

// Função para configurar autocomplete geral de origens
function setupOrigemAutocomplete() {
    // Configurar autocomplete para todos os campos de cartório de origem
    const cartorioOrigemInputs = document.querySelectorAll('.cartorio-origem-nome');
    
    cartorioOrigemInputs.forEach((input, index) => {
        // Buscar o campo hidden correspondente
        const hidden = input.closest('.autocomplete-container').querySelector('.cartorio-origem-id');
        const suggestions = input.closest('.autocomplete-container').querySelector('.cartorio-origem-suggestions');
        
        if (input && hidden && suggestions) {
            setupCartorioAutocomplete(input, hidden, suggestions);
        }
    });
}

// ========================================
// FUNÇÕES PARA CAMPOS DE FIM DE CADEIA
// ========================================

// Função para controlar a visibilidade dos campos de fim de cadeia
function setupFimCadeiaToggle() {
    const fimCadeiaToggle = document.getElementById('fim_cadeia');
    const fimCadeiaContainer = document.getElementById('fim-cadeia-container');
    
    if (fimCadeiaToggle && fimCadeiaContainer) {
        // Função para alternar visibilidade
        function toggleFimCadeiaFields() {
            if (fimCadeiaToggle.checked) {
                fimCadeiaContainer.style.display = 'block';
            } else {
                fimCadeiaContainer.style.display = 'none';
            }
        }
        
        // Adicionar listener
        fimCadeiaToggle.addEventListener('change', toggleFimCadeiaFields);
        
        // Executar uma vez para definir estado inicial
        toggleFimCadeiaFields();
    }
}

// Função para controlar a visibilidade do campo de especificação
function setupTipoFimCadeiaSelect() {
    const tipoFimCadeiaSelect = document.getElementById('tipo_fim_cadeia');
    const especificacaoContainer = document.getElementById('especificacao-container');
    
    if (tipoFimCadeiaSelect && especificacaoContainer) {
        // Função para alternar visibilidade
        function toggleEspecificacaoField() {
            if (tipoFimCadeiaSelect.value === 'outra') {
                especificacaoContainer.style.display = 'block';
            } else {
                especificacaoContainer.style.display = 'none';
            }
        }
        
        // Adicionar listener
        tipoFimCadeiaSelect.addEventListener('change', toggleEspecificacaoField);
        
        // Executar uma vez para definir estado inicial
        toggleEspecificacaoField();
    }
}

// Inicializar campos de fim de cadeia quando a página carregar
document.addEventListener('DOMContentLoaded', function() {
    setupFimCadeiaToggle();
    setupTipoFimCadeiaSelect();
    setupFimCadeiaPorOrigem(); // Nova função para toggles por origem
});

// ========================================
// FUNÇÕES PARA CAMPOS DE FIM DE CADEIA POR ORIGEM
// ========================================

// Função para configurar toggles de fim de cadeia por origem
function setupFimCadeiaPorOrigem() {
    // Configurar todos os toggles existentes
    const toggles = document.querySelectorAll('.fim-cadeia-toggle');
    toggles.forEach(toggle => {
        setupFimCadeiaTogglePorOrigem(toggle);
    });
}

// Função para configurar um toggle específico por origem
function setupFimCadeiaTogglePorOrigem(toggle) {
    const origemIndex = toggle.value;
    const container = document.getElementById(`fim-cadeia-origem-container_${origemIndex}`);
    
    if (toggle && container) {
        function toggleFimCadeiaFields() {
            if (toggle.checked) {
                container.style.display = 'block';
            } else {
                container.style.display = 'none';
                // Limpar campos quando desmarcar
                const tipoSelect = container.querySelector('.tipo-fim-cadeia-select');
                const classificacaoSelect = container.querySelector('.classificacao-fim-cadeia-select');
                const especificacaoContainer = container.querySelector('.especificacao-container');
                const especificacaoTextarea = container.querySelector('.especificacao-fim-cadeia');
                
                if (tipoSelect) tipoSelect.value = '';
                if (classificacaoSelect) classificacaoSelect.value = '';
                if (especificacaoContainer) especificacaoContainer.style.display = 'none';
                if (especificacaoTextarea) especificacaoTextarea.value = '';
            }
        }
        
        toggle.addEventListener('change', toggleFimCadeiaFields);
        toggleFimCadeiaFields(); // Estado inicial
    }
}

// Função para configurar selects de tipo de fim de cadeia por origem
function setupTipoFimCadeiaSelectPorOrigem(select) {
    const origemIndex = select.id.replace('tipo_fim_cadeia_', '');
    const especificacaoContainer = document.getElementById(`especificacao-container_${origemIndex}`);
    
    if (select && especificacaoContainer) {
        function toggleEspecificacaoField() {
            if (select.value === 'outra') {
                especificacaoContainer.style.display = 'block';
            } else {
                especificacaoContainer.style.display = 'none';
                // Limpar especificação quando não for 'outra'
                const especificacaoTextarea = especificacaoContainer.querySelector('.especificacao-fim-cadeia');
                if (especificacaoTextarea) especificacaoTextarea.value = '';
            }
        }
        
        select.addEventListener('change', toggleEspecificacaoField);
        toggleEspecificacaoField(); // Estado inicial
    }
} 