// Formulário de Imóvel - Versão Simplificada
class ImovelForm {
    constructor() {
        this.estadoSelect = document.getElementById('id_estado');
        this.cidadeSelect = document.getElementById('id_cidade');
        this.cartorioSelect = document.getElementById('id_cartorio');
        this.form = document.getElementById('imovel-form');
        this.cartorioInfo = document.getElementById('cartorio-info');
        this.cartorioDetalhes = document.getElementById('cartorio-detalhes');
        // Verificar se os elementos essenciais existem
        if (!this.estadoSelect || !this.cidadeSelect || !this.cartorioSelect) {
            return;
        }
        this.init();
    }

    init() {
        this.bindEvents();
    }

    bindEvents() {
        // Verificar se os elementos existem antes de adicionar event listeners
        if (!this.estadoSelect || !this.cidadeSelect || !this.cartorioSelect) {
            return;
        }
        
        // Carregar cidades quando estado for selecionado
        this.estadoSelect.addEventListener('change', (e) => {
            this.carregarCidades(e.target.value);
        });
        
        // Carregar cartórios quando cidade for selecionada
        this.cidadeSelect.addEventListener('change', (e) => {
            this.carregarCartorios(this.estadoSelect.value, e.target.value);
        });
        
        // Mostrar detalhes do cartório quando selecionado
        this.cartorioSelect.addEventListener('change', (e) => {
            if (e.target.value === 'novo') {
                // Abrir modal para novo cartório
                const modal = document.getElementById('modal-novo-cartorio');
                if (modal) {
                    modal.style.display = 'flex';
                    
                    // Copiar estado e cidade do formulário principal para o modal
                    const modalEstadoInput = document.getElementById('novo-cartorio-estado');
                    const modalCidadeInput = document.getElementById('novo-cartorio-cidade');
                    const estadoPrincipal = document.getElementById('id_estado');
                    const cidadePrincipal = document.getElementById('id_cidade');
                    
                    // Obter o texto do estado selecionado
                    const estadoText = estadoPrincipal.options[estadoPrincipal.selectedIndex]?.text || '';
                    const cidadeText = cidadePrincipal.options[cidadePrincipal.selectedIndex]?.text || '';
                    
                    modalEstadoInput.value = estadoText;
                    modalCidadeInput.value = cidadeText;
                }
                return;
            }
            this.mostrarDetalhesCartorio(e.target.value);
        });
    }

    async carregarCidades(estado) {
        if (!estado) {
            this.resetCidadeSelect();
            // Não resetar o cartório aqui, deixar as opções disponíveis
            return;
        }

        this.cidadeSelect.innerHTML = '<option value="">Carregando cidades...</option>';
        this.cidadeSelect.disabled = true;
        // Não resetar o cartório aqui, deixar as opções disponíveis

        try {
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
            
            const response = await fetch('/dominial/buscar-cidades/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-CSRFToken': csrfToken,
                },
                body: `estado=${encodeURIComponent(estado)}`
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const cidades = await response.json();
            
            this.cidadeSelect.innerHTML = '<option value="">Selecione uma cidade</option>';
            
            if (cidades && cidades.length > 0) {
                cidades.forEach(cidade => {
                    const option = document.createElement('option');
                    option.value = cidade.value;
                    option.textContent = cidade.label;
                    this.cidadeSelect.appendChild(option);
                });
            } else {
                this.cidadeSelect.innerHTML = '<option value="">Nenhuma cidade encontrada</option>';
            }
            
            this.cidadeSelect.disabled = false;
        } catch (error) {
            this.cidadeSelect.innerHTML = '<option value="">Erro ao carregar cidades</option>';
            this.cidadeSelect.disabled = false;
        }
    }

    async carregarCartorios(estado, cidade) {
        if (!estado || !cidade) {
            // Não resetar o cartório aqui, deixar as opções originais
            return;
        }

        this.cartorioSelect.innerHTML = '<option value="">Carregando cartórios...</option>';
        this.cartorioSelect.disabled = true;

        try {
            const response = await fetch('/dominial/buscar-cartorios/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                },
                body: `estado=${encodeURIComponent(estado)}&cidade=${encodeURIComponent(cidade)}`
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const cartorios = await response.json();
            this.cartorioSelect.innerHTML = '<option value="">Selecione um cartório</option>';

            if (cartorios && cartorios.length > 0) {
                cartorios.forEach(cartorio => {
                    const option = document.createElement('option');
                    option.value = cartorio.id;
                    option.textContent = cartorio.nome;
                    option.setAttribute('data-cartorio', JSON.stringify(cartorio));
                    this.cartorioSelect.appendChild(option);
                });
            } else {
                this.cartorioSelect.innerHTML = '<option value="">Nenhum cartório encontrado</option>';
            }
            // Sempre adicionar a opção de novo cartório
            const novoOption = document.createElement('option');
            novoOption.value = 'novo';
            novoOption.textContent = 'Adicionar novo cartório';
            this.cartorioSelect.appendChild(novoOption);

            this.cartorioSelect.disabled = false;
        } catch (error) {
            this.cartorioSelect.innerHTML = '<option value="">Erro ao carregar cartórios</option>';
            this.cartorioSelect.disabled = false;
        }
    }

    mostrarDetalhesCartorio(cartorioId) {
        if (!cartorioId) {
            this.cartorioInfo.style.display = 'none';
            return;
        }

        const cartorioOption = this.cartorioSelect.querySelector(`option[value="${cartorioId}"]`);
        
        if (cartorioOption && cartorioOption.hasAttribute('data-cartorio')) {
            const cartorio = JSON.parse(cartorioOption.getAttribute('data-cartorio'));
            
            this.cartorioDetalhes.innerHTML = `
                <p><strong>Nome:</strong> ${cartorio.nome}</p>
                <p><strong>CNS:</strong> ${cartorio.cns || 'Não informado'}</p>
                <p><strong>Endereço:</strong> ${cartorio.endereco || 'Não informado'}</p>
                <p><strong>Telefone:</strong> ${cartorio.telefone || 'Não informado'}</p>
                <p><strong>E-mail:</strong> ${cartorio.email || 'Não informado'}</p>
            `;
            
            this.cartorioInfo.style.display = 'block';
        } else {
            this.cartorioInfo.style.display = 'none';
        }
    }

    resetCidadeSelect() {
        this.cidadeSelect.innerHTML = '<option value="">Selecione uma cidade</option>';
        this.cidadeSelect.disabled = true;
    }

    resetCartorioSelect() {
        this.cartorioSelect.innerHTML = '<option value="">Selecione um cartório</option>';
        this.cartorioSelect.disabled = true;
        this.cartorioInfo.style.display = 'none';
    }
}

// Validação do campo nome do proprietário
function validarNomeProprietario() {
    const nomeInput = document.getElementById('id_proprietario_nome');
    if (nomeInput) {
        nomeInput.addEventListener('input', function() {
            const maxLength = 255;
            const currentLength = this.value.length;
            
            // Criar ou atualizar contador de caracteres
            let counter = document.getElementById('nome-counter');
            if (!counter) {
                counter = document.createElement('div');
                counter.id = 'nome-counter';
                counter.style.fontSize = '12px';
                counter.style.color = '#666';
                counter.style.marginTop = '5px';
                this.parentNode.appendChild(counter);
            }
            
            counter.textContent = `${currentLength}/${maxLength} caracteres`;
            
            // Mudar cor se estiver próximo do limite
            if (currentLength > maxLength * 0.9) {
                counter.style.color = currentLength >= maxLength ? '#d32f2f' : '#f57c00';
            } else {
                counter.style.color = '#666';
            }
            
            // Truncar se exceder o limite
            if (currentLength > maxLength) {
                this.value = this.value.substring(0, maxLength);
                counter.textContent = `${maxLength}/${maxLength} caracteres`;
                counter.style.color = '#d32f2f';
            }
        });
    }
}

// Inicializar quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', function() {
    new ImovelForm();
    validarNomeProprietario();
});

// Configurar modal de novo cartório
function setupNovoCartorioModal() {
    const modal = document.getElementById('modal-novo-cartorio');
    const fecharBtn = document.getElementById('fechar-modal-cartorio');
    const cancelarBtn = document.getElementById('cancelar-novo-cartorio');
    const form = document.getElementById('form-novo-cartorio');
    const cartorioSelect = document.getElementById('id_cartorio');

    // Só ativa se o modal e o form existem
    if (!modal || !fecharBtn || !cancelarBtn || !form || !cartorioSelect) {
        return;
    }
    
    // Fechar modal
    fecharBtn.onclick = function() {
        modal.style.display = 'none';
        form.reset();
        // Limpar campos de estado e cidade
        document.getElementById('novo-cartorio-estado').value = '';
        document.getElementById('novo-cartorio-cidade').value = '';
        // Voltar o select para vazio
        cartorioSelect.value = '';
    };
    
    cancelarBtn.onclick = function() {
        modal.style.display = 'none';
        form.reset();
        // Limpar campos de estado e cidade
        document.getElementById('novo-cartorio-estado').value = '';
        document.getElementById('novo-cartorio-cidade').value = '';
        // Voltar o select para vazio
        cartorioSelect.value = '';
    };

    // Submeter novo cartório via AJAX
    form.onsubmit = async function(e) {
        e.preventDefault();
        e.stopPropagation(); // Impedir que o evento se propague para o formulário principal
        
        const data = {
            nome: document.getElementById('novo-cartorio-nome').value,
            cns: document.getElementById('novo-cartorio-cns').value,
            estado: document.getElementById('id_estado').value, // Usar o código do estado do formulário principal
            cidade: document.getElementById('id_cidade').value, // Usar o código da cidade do formulário principal
            endereco: '',
            telefone: '',
            email: ''
        };
        try {
            const resp = await fetch('/dominial/criar-cartorio/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                },
                body: JSON.stringify(data)
            });
            const result = await resp.json();
            if (result.success) {
                // Adicionar ao select e selecionar
                const option = document.createElement('option');
                option.value = result.cartorio.id;
                option.textContent = result.cartorio.nome;
                option.setAttribute('data-cartorio', JSON.stringify(result.cartorio));
                cartorioSelect.appendChild(option);
                cartorioSelect.value = result.cartorio.id;
                // Fechar modal
                modal.style.display = 'none';
                form.reset();
                // Disparar evento para mostrar detalhes
                cartorioSelect.dispatchEvent(new Event('change'));
            } else {
                alert(result.error || 'Erro ao criar cartório.');
            }
        } catch (err) {
            alert('Erro ao criar cartório.');
        }
    };
}

// Inicializar modal quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', function() {
    setupNovoCartorioModal();
}); 