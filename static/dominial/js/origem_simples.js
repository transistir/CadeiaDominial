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
    
    // CORREÇÃO: Processar todas as origens existentes (modo de edição)
    processarTodasOrigensExistentes();
    
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
    console.log(`Origem ${index}: tipoSelect.value = "${tipoSelect.value}", numeroInput.disabled = ${numeroInput.disabled}`);
    
    // Configurar validação para início de matrícula
    configurarValidacaoInicioMatricula(index);
    
    // Configurar estado inicial dos campos de fim de cadeia
    controlarCamposFimCadeia(index);
    
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
    
    // Event listener para toggle de fim de cadeia
    const fimCadeiaToggle = document.getElementById(`fim_cadeia_${index}`);
    if (fimCadeiaToggle) {
        fimCadeiaToggle.addEventListener('change', function() {
            controlarCamposFimCadeia(index);
            atualizarOrigemCompleta(index);
        });
    }
    
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

function processarTodasOrigensExistentes() {
    console.log('Processando todas as origens existentes...');
    
    // Buscar todos os campos hidden de origem completa
    const hiddenInputs = document.querySelectorAll('input[id^="origem_completa_hidden_"]');
    console.log(`Encontrados ${hiddenInputs.length} campos de origem`);
    
    // Processar cada origem existente
    hiddenInputs.forEach((hiddenInput, index) => {
        const inputId = hiddenInput.id;
        const match = inputId.match(/origem_completa_hidden_(\d+)/);
        if (match) {
            const origemIndex = parseInt(match[1]);
            console.log(`Processando origem ${origemIndex}: ${hiddenInput.value}`);
            
            // Configurar a origem se ainda não foi configurada
            const tipoSelect = document.getElementById(`tipo_origem_${origemIndex}`);
            const numeroInput = document.getElementById(`numero_origem_${origemIndex}`);
            
            if (tipoSelect && numeroInput && hiddenInput.value) {
                // Migrar dados existentes
                migrarDadosExistentes(origemIndex);
                
                // Configurar eventos se ainda não foram configurados
                if (!tipoSelect.hasAttribute('data-configured')) {
                    configurarOrigem(origemIndex);
                    tipoSelect.setAttribute('data-configured', 'true');
                }
            }
        }
    });
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
        const siglaPatrimonioPublico = document.getElementById(`sigla_patrimonio_publico_${index}`);
        
        const tipoFimCadeiaValue = tipoFimCadeia ? tipoFimCadeia.value : '';
        const classificacao = classificacaoFimCadeia ? classificacaoFimCadeia.value : '';
        const siglaPatrimonio = siglaPatrimonioPublico ? siglaPatrimonioPublico.value.trim() : '';
        
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
        
        // Criar origem no formato novo: Tipo:Sigla:Classificação
        let origemCompleta;
        
        if (tipoFimCadeiaValue === 'destacamento_publico' && siglaPatrimonio) {
            // Formato: Destacamento Público:Sigla:Classificação
            origemCompleta = `Destacamento Público:${siglaPatrimonio}:${classificacao}`;
        } else if (tipoFimCadeiaValue === 'outra') {
            // Formato: Outra:Especificação:Classificação
            const especificacao = document.getElementById(`especificacao_fim_cadeia_${index}`);
            const especificacaoValue = especificacao ? especificacao.value.trim() : '';
            origemCompleta = `Outra:${especificacaoValue}:${classificacao}`;
        } else if (tipoFimCadeiaValue === 'sem_origem') {
            // Formato: Sem Origem::Classificação
            origemCompleta = `Sem Origem::${classificacao}`;
        } else {
            // Fallback para formato antigo se não conseguir determinar o tipo
            origemCompleta = `FIM_CADEIA:${tipoOrigem}:${numeroOrigem}:${tipoFimCadeiaValue}:${classificacao}:${siglaPatrimonio}`;
        }
        
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
    
    // Inserir no final do container
    const container = document.getElementById('origens-container');
    if (container) {
        container.appendChild(novaOrigem);
        
        // Limpar campos da nova origem
        limparCamposNovaOrigem(novaOrigem);
        
        // Criar container de fim de cadeia para esta origem
        criarContainerFimCadeia(proximoIndex);
        
        // Configurar nova origem
        configurarOrigem(proximoIndex);
        
        // Focar no select da nova origem
        const tipoSelect = document.getElementById(`tipo_origem_${proximoIndex}`);
        if (tipoSelect) {
            tipoSelect.focus();
        }
        
        console.log(`Nova origem ${proximoIndex} adicionada`);
        
        // Reativar sugestões se for início de matrícula
        if (typeof ativarSugestoesCartorioOrigem === 'function') {
            ativarSugestoesCartorioOrigem();
        }
    }
}

function limparCamposNovaOrigem(origemElement) {
    // Limpar todos os campos da nova origem
    const inputs = origemElement.querySelectorAll('input, select, textarea');
    inputs.forEach(input => {
        if (input.type === 'checkbox') {
            input.checked = false;
        } else if (input.type === 'hidden') {
            input.value = '';
        } else {
            input.value = '';
        }
    });
    
    // Desabilitar campo número por padrão
    const numeroInput = origemElement.querySelector('.origem-numero-input');
    if (numeroInput) {
        numeroInput.disabled = true;
    }
    
    console.log('Campos da nova origem limpos');
}

function criarContainerFimCadeia(index) {
    // Criar container de fim de cadeia para esta origem
    const fimCadeiaContainer = document.createElement('div');
    fimCadeiaContainer.className = 'fim-cadeia-origem-container';
    fimCadeiaContainer.id = `fim-cadeia-origem-container_${index}`;
    fimCadeiaContainer.style.display = 'none';
    
    fimCadeiaContainer.innerHTML = `
        <div class="grid-2">
            <div class="form-group">
                <label for="tipo_fim_cadeia_${index}">Tipo do Fim de Cadeia *</label>
                <select name="tipo_fim_cadeia[]" id="tipo_fim_cadeia_${index}" class="form-control tipo-fim-cadeia-select">
                    <option value="">Selecione o tipo...</option>
                    <option value="destacamento_publico">Destacamento do Patrimônio Público</option>
                    <option value="outra">Outra</option>
                    <option value="sem_origem">Sem Origem</option>
                </select>
            </div>
            
            <div class="form-group">
                <label for="classificacao_fim_cadeia_${index}">Classificação do Fim de Cadeia *</label>
                <select name="classificacao_fim_cadeia[]" id="classificacao_fim_cadeia_${index}" class="form-control classificacao-fim-cadeia-select">
                    <option value="">Selecione a classificação...</option>
                    <option value="origem_lidima">Imóvel com Origem Lídima</option>
                    <option value="sem_origem">Imóvel sem Origem</option>
                    <option value="inconclusa">Situação Inconclusa</option>
                </select>
            </div>
        </div>
        
        <!-- Campo de sigla do patrimônio público (aparece quando tipo = 'destacamento_publico') -->
        <div class="form-group sigla-patrimonio-container" id="sigla-patrimonio-container_${index}" style="display: none;">
            <label for="sigla_patrimonio_publico_${index}">Sigla do Patrimônio Público *</label>
            <input type="text" name="sigla_patrimonio_publico[]" id="sigla_patrimonio_publico_${index}" 
                   class="form-control sigla-patrimonio-publico-input" 
                   placeholder="Ex: INCRA, Estado, União, etc.">
        </div>
        
        <!-- Campo de especificação (aparece quando tipo = 'outra') -->
        <div class="form-group especificacao-container" id="especificacao-container_${index}" style="display: none;">
            <label for="especificacao_fim_cadeia_${index}">Especificação *</label>
            <textarea name="especificacao_fim_cadeia[]" id="especificacao_fim_cadeia_${index}" class="form-control especificacao-fim-cadeia" 
                      placeholder="Detalhe a especificação..."></textarea>
        </div>
    `;
    
    // Inserir o container após a origem correspondente
    const origemItem = document.querySelector(`[data-origem-index="${index}"]`);
    if (origemItem) {
        origemItem.parentNode.insertBefore(fimCadeiaContainer, origemItem.nextSibling);
    }
    
    console.log(`Container de fim de cadeia criado para origem ${index}`);
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
            // Controlar exibição do container de fim de cadeia
            const container = document.getElementById(`fim-cadeia-origem-container_${index}`);
            if (container) {
                container.style.display = this.checked ? 'block' : 'none';
            }
            
            // Controlar exibição do campo de sigla do patrimônio público
            const siglaContainer = document.getElementById(`sigla-patrimonio-container_${index}`);
            if (siglaContainer) {
                siglaContainer.style.display = this.checked ? 'block' : 'none';
            }
            
            setTimeout(aplicarValidacao, 100); // Delay para permitir que outros eventos sejam processados
            atualizarOrigemCompleta(index); // Atualizar origem quando checkbox muda
        });
    }
    
    // Atualizar origem quando tipo e classificação de fim de cadeia mudam
    const tipoFimCadeia = document.getElementById(`tipo_fim_cadeia_${index}`);
    if (tipoFimCadeia) {
        tipoFimCadeia.addEventListener('change', function() {
            // Controlar exibição dos campos baseado no tipo selecionado
            controlarExibicaoCamposFimCadeia(index);
            
            // Criar campo de sigla do patrimônio público dinamicamente se não existir
            if (this.value === 'destacamento_publico') {
                criarCampoSiglaPatrimonio(index);
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
    
    const siglaPatrimonioPublico = document.getElementById(`sigla_patrimonio_publico_${index}`);
    if (siglaPatrimonioPublico) {
        siglaPatrimonioPublico.addEventListener('input', function() {
            atualizarOrigemCompleta(index);
        });
    }
    
    // Controlar exibição inicial dos campos de fim de cadeia
    controlarExibicaoCamposFimCadeia(index);
    
    // Aplicar validação inicial
    aplicarValidacao();
}

/**
 * Controla a exibição dos campos de fim de cadeia baseado no tipo selecionado
 */
function controlarExibicaoCamposFimCadeia(index) {
    const tipoFimCadeia = document.getElementById(`tipo_fim_cadeia_${index}`);
    const especificacaoContainer = document.getElementById(`especificacao-container_${index}`);
    const siglaPatrimonioContainer = document.getElementById(`sigla-patrimonio-container_${index}`);
    
    console.log(`DEBUG: Controlar exibição - index: ${index}`);
    console.log(`DEBUG: tipoFimCadeia:`, tipoFimCadeia);
    console.log(`DEBUG: especificacaoContainer:`, especificacaoContainer);
    console.log(`DEBUG: siglaPatrimonioContainer:`, siglaPatrimonioContainer);
    
    if (tipoFimCadeia && especificacaoContainer && siglaPatrimonioContainer) {
        const tipoSelecionado = tipoFimCadeia.value;
        console.log(`DEBUG: Tipo selecionado: ${tipoSelecionado}`);
        
        // Controlar exibição do campo de especificação
        especificacaoContainer.style.display = tipoSelecionado === 'outra' ? 'block' : 'none';
        
        // Controlar exibição do campo de sigla do patrimônio público
        siglaPatrimonioContainer.style.display = tipoSelecionado === 'destacamento_publico' ? 'block' : 'none';
        
        console.log(`DEBUG: Especificação display: ${especificacaoContainer.style.display}`);
        console.log(`DEBUG: Sigla patrimônio display: ${siglaPatrimonioContainer.style.display}`);
    } else {
        console.log(`DEBUG: Algum elemento não foi encontrado para index ${index}`);
    }
}

/**
 * Controla se os campos de cartório devem ser desabilitados para fim de cadeia
 */
function controlarCamposFimCadeia(index) {
    const fimCadeiaToggle = document.getElementById(`fim_cadeia_${index}`);
    const numeroField = document.getElementById(`numero_origem_${index}`);
    const cartorioField = document.getElementById(`cartorio_origem_nome_${index}`);
    const livroField = document.getElementById(`livro_origem_${index}`);
    const folhaField = document.getElementById(`folha_origem_${index}`);
    
    if (fimCadeiaToggle && cartorioField && livroField && folhaField) {
        if (fimCadeiaToggle.checked) {
            // Fim de cadeia: desabilitar campos de número e cartório
            if (numeroField) {
                numeroField.disabled = true;
                numeroField.classList.remove('campo-obrigatorio');
                numeroField.value = '';
            }
            cartorioField.disabled = true;
            livroField.disabled = true;
            folhaField.disabled = true;
            
            // Remover validação obrigatória
            cartorioField.classList.remove('campo-obrigatorio');
            livroField.classList.remove('campo-obrigatorio');
            folhaField.classList.remove('campo-obrigatorio');
            
            // Limpar valores
            cartorioField.value = '';
            livroField.value = '';
            folhaField.value = '';
        } else {
            // Origem normal: habilitar campos
            if (numeroField) {
                numeroField.disabled = false;
            }
            cartorioField.disabled = false;
            livroField.disabled = false;
            folhaField.disabled = false;
            
            // Aplicar validação obrigatória se for início de matrícula
            const tipoLancamento = document.querySelector('input[name="tipo"]:checked')?.value;
            if (tipoLancamento === 'inicio_matricula') {
                cartorioField.classList.add('campo-obrigatorio');
            }
        }
    }
}

/**
 * Cria o campo de sigla do patrimônio público dinamicamente
 */
function criarCampoSiglaPatrimonio(index) {
    // Verificar se o campo já existe
    let siglaContainer = document.getElementById(`sigla-patrimonio-container_${index}`);
    
    if (!siglaContainer) {
        // Buscar o container de fim de cadeia
        const fimCadeiaContainer = document.getElementById(`fim-cadeia-origem-container_${index}`);
        
        if (fimCadeiaContainer) {
            // Criar o campo de sigla do patrimônio público
            const siglaHTML = `
                <div class="form-group sigla-patrimonio-container" id="sigla-patrimonio-container_${index}" style="display: block;">
                    <label for="sigla_patrimonio_publico_${index}">Sigla do Patrimônio Público *</label>
                    <input type="text" name="sigla_patrimonio_publico[]" id="sigla_patrimonio_publico_${index}" 
                           class="form-control sigla-patrimonio-publico-input" 
                           placeholder="Ex: INCRA, Estado, União, etc.">
                </div>
            `;
            
            // Inserir o campo após o grid-2
            const grid2 = fimCadeiaContainer.querySelector('.grid-2');
            if (grid2) {
                grid2.insertAdjacentHTML('afterend', siglaHTML);
                
                // Adicionar event listener para o novo campo
                const siglaInput = document.getElementById(`sigla_patrimonio_publico_${index}`);
                if (siglaInput) {
                    siglaInput.addEventListener('input', function() {
                        atualizarOrigemCompleta(index);
                    });
                }
            }
        }
    } else {
        // Se o campo já existe, apenas exibir
        siglaContainer.style.display = 'block';
    }
}

// Exportar funções para uso global
window.adicionarOrigemSimples = adicionarOrigemSimples;
window.controlarExibicaoCamposFimCadeia = controlarExibicaoCamposFimCadeia;
window.controlarCamposFimCadeia = controlarCamposFimCadeia;
window.criarCampoSiglaPatrimonio = criarCampoSiglaPatrimonio;
