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

    // Restaurar as siglas gravadas em todos os selects renderizados (issue #104)
    document.querySelectorAll('.sigla-patrimonio-publico-select').forEach(select => {
        const match = select.id.match(/sigla_patrimonio_publico_(\d+)/);
        if (match) aplicarSiglaSelecionada(parseInt(match[1]));
    });

    // Configurar eventos globais
    configurarEventosGlobais();
}

/**
 * Siglas de destacamento do patrimônio público publicadas pela view (issue #104)
 */
function obterOpcoesFimCadeia() {
    const dados = document.getElementById('fim-cadeia-opcoes-data');
    if (!dados) return [];
    try {
        return JSON.parse(dados.textContent) || [];
    } catch (erro) {
        console.warn('Não foi possível ler as siglas de fim de cadeia:', erro);
        return [];
    }
}

function escaparHtml(valor) {
    const elemento = document.createElement('span');
    elemento.textContent = valor == null ? '' : String(valor);
    return elemento.innerHTML.replace(/"/g, '&quot;');
}

/**
 * Monta o bloco "Informação adicional" + "Estado" do destacamento (issue #104).
 * Espelha templates/dominial/components/_fim_cadeia_destacamento_fields.html
 */
function montarBlocoDestacamento(index, visivel) {
    const opcoes = obterOpcoesFimCadeia()
        .map(opcao => {
            const sigla = escaparHtml(opcao.sigla);
            const nome = escaparHtml(opcao.nome);
            return `<option value="${sigla}" title="${nome}">${sigla} — ${nome}</option>`;
        })
        .join('');

    return `
        <div class="form-group sigla-patrimonio-container" id="sigla-patrimonio-container_${index}" style="display: ${visivel ? 'block' : 'none'};">
            <div class="destacamento-grid">
                <div class="form-group">
                    <label for="info_adicional_fim_cadeia_${index}">Informação adicional</label>
                    <input type="text" name="info_adicional_fim_cadeia[]" id="info_adicional_fim_cadeia_${index}"
                           class="form-control info-adicional-fim-cadeia-input"
                           placeholder="Ex: secretaria que concedeu o título">
                </div>
                <div class="form-group">
                    <label for="sigla_patrimonio_publico_${index}">Estado *</label>
                    <select name="sigla_patrimonio_publico[]" id="sigla_patrimonio_publico_${index}"
                            class="form-control sigla-patrimonio-publico-select" data-sigla-selecionada="">
                        <option value="">Selecione...</option>
                        ${opcoes}
                    </select>
                </div>
            </div>
        </div>
    `;
}

/**
 * Garante que a sigla gravada apareça no select, mesmo quando for texto livre
 * de lançamentos antigos que não corresponde a nenhum FimCadeia (issue #104)
 */
function aplicarSiglaSelecionada(index) {
    const select = document.getElementById(`sigla_patrimonio_publico_${index}`);
    if (!select || select.tagName !== 'SELECT') return;

    const siglaGravada = (select.dataset.siglaSelecionada || '').trim();
    if (!siglaGravada) return;

    select.value = siglaGravada;
    if (select.value !== siglaGravada) {
        // Valor legado sem correspondência no cadastro: preservar como opção própria
        const opcaoLegada = new Option(`${siglaGravada} (cadastro anterior)`, siglaGravada);
        select.add(opcaoLegada, 1);
        select.value = siglaGravada;
    }
}

function configurarOrigem(index) {
    const tipoSelect = document.getElementById(`tipo_origem_${index}`);
    const numeroInput = document.getElementById(`numero_origem_${index}`);
    const hiddenInput = document.getElementById(`origem_completa_hidden_${index}`);
    
    if (!tipoSelect || !numeroInput || !hiddenInput) return;

    // Restaurar a sigla gravada no select de destacamento (issue #104)
    aplicarSiglaSelecionada(index);

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

    // M anterior vinculada (issue #167)
    configurarMAnterior(index);
}

/* ------------------------------------------------------------------ *
 * M anterior vinculada (issue #167)
 * Ao informar uma origem do tipo Matrícula (M) + CRI, consulta o acervo pela
 * matrícula anterior que essa origem referencia. Não encontrar a M anterior
 * é o caso comum (documento novo, ainda não cadastrado) — não é indício de
 * quebra de cadeia, então o badge correspondente fica neutro.
 * ------------------------------------------------------------------ */
/* Issue #167 (Codex review P2): manter o controle de requests em voo
 * por linha de origem. Debounce só evita iniciar novas chamadas; sem
 * cancelar a anterior, a resposta mais lenta pode chegar depois de uma
 * nova digitação e renderizar um badge com dados da busca antiga.
 */
const _mAnteriorAbort = {};
const _mAnteriorDebounce = {};

function garantirDivMAnterior(index) {
    let div = document.getElementById(`m-anterior-info-${index}`);
    if (div) return div;

    const origemItem = document.querySelector(`[data-origem-index="${index}"]`);
    if (!origemItem) return null;

    // Origens adicionadas dinamicamente não trazem a div do template.
    div = document.createElement('div');
    div.className = 'm-anterior-info';
    div.id = `m-anterior-info-${index}`;
    const modelo = document.querySelector('.m-anterior-info[data-tis-id]');
    div.dataset.tisId = modelo ? (modelo.dataset.tisId || '') : '';
    div.style.display = 'none';
    origemItem.parentNode.insertBefore(div, origemItem.nextSibling);
    return div;
}

function renderMAnterior(div, dados, numeroDigitado) {
    if (dados.encontrado && dados.mesma_ti) {
        div.className = 'm-anterior-info m-anterior-match';
        div.textContent = `M anterior: ${dados.matricula} (Imóvel: ${dados.imovel_nome})`;
    } else if (dados.encontrado && dados.outra_ti) {
        div.className = 'm-anterior-info m-anterior-other-ti';
        div.textContent = `⚠ M anterior ${dados.matricula} está em outra TI (Imóvel: ${dados.imovel_nome})`;
    } else {
        div.className = 'm-anterior-info m-anterior-missing';
        div.textContent = numeroDigitado
            ? `M ${numeroDigitado} ainda não consta no acervo (documento novo)`
            : 'M anterior ainda não consta no acervo (documento novo)';
    }
    div.style.display = 'block';
}

function atualizarMAnterior(index) {
    const div = garantirDivMAnterior(index);
    if (!div) return;

    const tipoSelect = document.getElementById(`tipo_origem_${index}`);
    const numeroInput = document.getElementById(`numero_origem_${index}`);
    const cartorioHidden = document.getElementById(`cartorio_origem_${index}`);

    const tipo = tipoSelect ? tipoSelect.value : '';
    const numero = numeroInput ? numeroInput.value.trim() : '';
    const cartorioId = cartorioHidden ? cartorioHidden.value.trim() : '';

    // Só faz sentido para origem do tipo Matrícula (M) já identificada por CRI.
    if (tipo !== 'M' || !numero || !cartorioId) {
        // P2 do Greptile no #185: abortar fetch em voo antes de esconder o
        // badge. Caso contrário, a resposta atrasada resolve depois do
        // operador limpar/alterar o número/cartório/tipo e o renderMAnterior
        // dentro do .then repopula o badge stale.
        if (_mAnteriorAbort[index]) {
            _mAnteriorAbort[index].abort();
            _mAnteriorAbort[index] = null;
        }
        div.textContent = '';
        div.style.display = 'none';
        return;
    }

    // Cancelar request anterior em voo, se houver — Code rev P2.
    if (_mAnteriorAbort[index]) {
        _mAnteriorAbort[index].abort();
    }
    const controller = new AbortController();
    _mAnteriorAbort[index] = controller;

    const params = new URLSearchParams({ numero: numero, cartorio_id: cartorioId });
    if (div.dataset.tisId) params.set('tis_id', div.dataset.tisId);

    fetch(`/dominial/buscar-m-anterior/?${params.toString()}`, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        signal: controller.signal,
    })
        .then(resposta => (resposta.ok ? resposta.json() : null))
        .then(dados => {
            if (dados) renderMAnterior(div, dados, numero);
        })
        .catch(err => {
            // Ignore os aborts intencionais; outros erros ficam silenciosos
            // (o badge é apenas auxiliar ao operador).
            if (err && err.name !== 'AbortError') {
                /* noop */
            }
        })
        .finally(() => {
            if (_mAnteriorAbort[index] === controller) {
                _mAnteriorAbort[index] = null;
            }
        });
}

function agendarMAnterior(index) {
    clearTimeout(_mAnteriorDebounce[index]);
    _mAnteriorDebounce[index] = setTimeout(() => atualizarMAnterior(index), 300);
}

function configurarMAnterior(index) {
    const tipoSelect = document.getElementById(`tipo_origem_${index}`);
    const numeroInput = document.getElementById(`numero_origem_${index}`);
    const cartorioNome = document.getElementById(`cartorio_origem_nome_${index}`);

    if (tipoSelect) tipoSelect.addEventListener('change', () => agendarMAnterior(index));
    if (numeroInput) numeroInput.addEventListener('keyup', () => agendarMAnterior(index));
    if (cartorioNome) {
        cartorioNome.addEventListener('keyup', () => agendarMAnterior(index));
        cartorioNome.addEventListener('blur', () => agendarMAnterior(index));
    }

    // Estado inicial (edição / re-render de erro já trazem número + CRI).
    atualizarMAnterior(index);
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

        // Realinhar os `value` dos checkboxes `fim_cadeia[]` com a posição atual
        // de cada linha. `proximoIndex` é um índice de ID (busca gap em
        // `tipo_origem_N`) e pode colidir com o `value` de uma linha
        // sobrevivente depois de um remover+adicionar — sem renumerar, o POST
        // sai com `fim_cadeia[]` duplicado e o servidor marca a linha errada
        // (issue #162 rodada 3).
        renumerarCheckboxesFimCadeia();

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
        
        <!-- Campos de destacamento do patrimônio público (aparecem quando tipo = 'destacamento_publico') -->
        ${montarBlocoDestacamento(index, false)}

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

    // O checkbox `fim_cadeia[]` identifica a linha pelo `value` (o servidor
    // compara com a posição da origem). O clone mantinha `value="0"` em todas
    // as linhas, quebrando o re-render de erro (issue #162 rodada 2).
    const fimCadeiaCheckbox = elemento.querySelector('.fim-cadeia-toggle');
    if (fimCadeiaCheckbox) {
        fimCadeiaCheckbox.value = String(novoIndex);
    }
}

/**
 * Renumera o `value` dos checkboxes `fim_cadeia[]` para a posição atual da
 * linha depois de remover uma origem, mantendo o array do POST alinhado com a
 * ordem das origens (issue #162 rodada 2). Mexe só no `value` — ids, names e
 * listeners continuam intactos.
 */
function renumerarCheckboxesFimCadeia() {
    const container = document.getElementById('origens-container');
    if (!container) return;

    container.querySelectorAll('.origem-item').forEach((origem, posicao) => {
        const checkbox = origem.querySelector('.fim-cadeia-toggle');
        if (checkbox) {
            checkbox.value = String(posicao);
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
            
            // Os campos de destacamento não seguem o toggle: só aparecem quando
            // o tipo escolhido é 'destacamento_publico' (issue #104)
            controlarExibicaoCamposFimCadeia(index);

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
        siglaPatrimonioPublico.addEventListener('change', function() {
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
    if (!tipoFimCadeia) return;

    const tipoSelecionado = tipoFimCadeia.value;

    // Cada bloco é opcional: a ausência de um não pode impedir a exibição do
    // outro, então checar um a um em vez de exigir os dois (issue #104)
    const especificacaoContainer = document.getElementById(`especificacao-container_${index}`);
    if (especificacaoContainer) {
        especificacaoContainer.style.display = tipoSelecionado === 'outra' ? 'block' : 'none';
    }

    const siglaPatrimonioContainer = document.getElementById(`sigla-patrimonio-container_${index}`);
    if (siglaPatrimonioContainer) {
        siglaPatrimonioContainer.style.display = tipoSelecionado === 'destacamento_publico' ? 'block' : 'none';
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
            // Fim de cadeia: bloquear número e cartório/livro/folha.
            // Usar `readonly` (não `disabled`) nos campos de texto: campo
            // desabilitado NÃO vai no POST e os arrays `*_origem[]` são
            // posicionais — a linha some e desalinha as seguintes no
            // re-render de erro (issue #159 rodada 2).
            if (numeroField) {
                numeroField.disabled = true;
                numeroField.classList.remove('campo-obrigatorio');
                numeroField.value = '';
            }
            cartorioField.readOnly = true;
            livroField.readOnly = true;
            folhaField.readOnly = true;

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
            cartorioField.readOnly = false;
            livroField.readOnly = false;
            folhaField.readOnly = false;
            
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
            // Criar os campos de destacamento do patrimônio público
            const siglaHTML = montarBlocoDestacamento(index, true);

            // Inserir o campo após o grid-2
            const grid2 = fimCadeiaContainer.querySelector('.grid-2');
            if (grid2) {
                grid2.insertAdjacentHTML('afterend', siglaHTML);

                // Adicionar event listener para o novo campo
                const siglaSelect = document.getElementById(`sigla_patrimonio_publico_${index}`);
                if (siglaSelect) {
                    siglaSelect.addEventListener('change', function() {
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
window.renumerarCheckboxesFimCadeia = renumerarCheckboxesFimCadeia;
window.montarBlocoDestacamento = montarBlocoDestacamento;
window.controlarExibicaoCamposFimCadeia = controlarExibicaoCamposFimCadeia;
window.controlarCamposFimCadeia = controlarCamposFimCadeia;
window.criarCampoSiglaPatrimonio = criarCampoSiglaPatrimonio;
window.atualizarMAnterior = atualizarMAnterior;
