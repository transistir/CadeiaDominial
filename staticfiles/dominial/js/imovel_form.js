// Formulário de Imóvel - Funcionalidades
class ImovelForm {
    constructor() {
        this.estadoSelect = document.getElementById('estado');
        this.cidadeSelect = document.getElementById('cidade_select');
        this.cartorioSelect = document.getElementById('cartorio');
        this.form = document.getElementById('imovel-form');
        
        this.init();
    }

    init() {
        this.bindEvents();
        this.setupFormValidation();
    }

    bindEvents() {
        // Controle de estado/cidade
        if (this.estadoSelect && this.cidadeSelect) {
            this.estadoSelect.addEventListener('change', (e) => {
                this.handleEstadoChange(e.target.value);
            });
        }
        
        // Controle de cidade/cartório
        if (this.cidadeSelect) {
            this.cidadeSelect.addEventListener('change', (e) => {
                const estado = this.estadoSelect.value;
                const cidade = e.target.value;
                this.handleCidadeChange(estado, cidade);
            });
        }
        
        // Controle de seleção de cartório
        if (this.cartorioSelect) {
            this.cartorioSelect.addEventListener('change', (e) => {
                this.handleCartorioChange(e.target.value);
            });
        }
        
        // Listener para evento de cartórios importados
        document.addEventListener('cartoriosImportados', (event) => {
            const estado = event.detail.estado;
            if (typeof this.carregarCidades === 'function') {
                this.carregarCidades(estado);
            }
        });
    }

    handleEstadoChange(estado) {
        if (estado) {
            // Usar o serviço modularizado para verificar cartórios
            if (typeof verificarCartoriosEstado === 'function') {
                verificarCartoriosEstado(estado);
            }
        } else {
            this.resetCidadeSelect();
            this.resetCartorioSelect();
        }
    }

    handleCidadeChange(estado, cidade) {
        console.log('Cidade selecionada:', cidade);
        
        if (estado && cidade) {
            this.carregarCartorios(estado, cidade);
        } else {
            this.resetCartorioSelect();
        }
    }

    handleCartorioChange(value) {
        if (value === 'novo') {
            // O modal será aberto pelo cartorio_modal.js
        } else if (value) {
            this.mostrarDetalhesCartorio(value);
        } else {
            const detalhesDiv = document.getElementById('cartorio-detalhes');
            if (detalhesDiv) {
                detalhesDiv.innerHTML = '';
            }
        }
    }

    resetCidadeSelect() {
        if (this.cidadeSelect) {
            this.cidadeSelect.disabled = true;
            this.cidadeSelect.innerHTML = '<option value="">Selecione uma cidade</option>';
        }
    }

    resetCartorioSelect() {
        if (this.cartorioSelect) {
            this.cartorioSelect.disabled = true;
            this.cartorioSelect.innerHTML = '<option value="">Selecione um cartório</option>';
        }
    }

    setupFormValidation() {
        if (this.form) {
            this.form.addEventListener('submit', (e) => {
                e.preventDefault();
                this.validateAndSubmit();
            });
        }
    }

    validateAndSubmit() {
        // Validar campos obrigatórios
        const nomeImovel = document.getElementById('id_nome').value;
        const nomeProprietario = document.getElementById('nome_proprietario').value;
        const matricula = document.getElementById('id_matricula').value;
        const estado = this.estadoSelect.value;
        const cidade = this.cidadeSelect.value;
        const cartorio = this.cartorioSelect.value;
        
        if (!nomeImovel || !nomeProprietario || !matricula || !estado || !cidade || !cartorio) {
            alert('Por favor, preencha todos os campos obrigatórios.');
            return;
        }
        
        // Preencher campos hidden
        document.getElementById('id_cidade').value = cidade;
        document.getElementById('cartorio_id').value = cartorio;
        document.getElementById('id_estado').value = estado;
        
        // Enviar formulário
        this.form.submit();
    }

    // Função para carregar cidades via API
    async carregarCidades(estado) {
        return new Promise((resolve, reject) => {
            if (!this.cidadeSelect) {
                reject(new Error('Select de cidade não encontrado'));
                return;
            }
            
            // Mostrar loading
            this.cidadeSelect.innerHTML = '<option value="">Carregando cidades...</option>';
            this.cidadeSelect.disabled = true;
            
            // Obter token CSRF
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
            if (!csrfToken) {
                console.error('Token CSRF não encontrado');
                this.cidadeSelect.innerHTML = '<option value="">Erro: Token CSRF não encontrado</option>';
                this.cidadeSelect.disabled = false;
                reject(new Error('Token CSRF não encontrado'));
                return;
            }
            
            console.log('Fazendo requisição para buscar cidades do estado:', estado);
            
            // Fazer requisição para a API
            fetch('/dominial/buscar-cidades/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-CSRFToken': csrfToken.value,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: `estado=${encodeURIComponent(estado)}`,
                credentials: 'same-origin'
            })
            .then(response => {
                console.log('Status da resposta:', response.status);
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                return response.json();
            })
            .then(data => {
                console.log('Dados recebidos:', data);
                this.cidadeSelect.innerHTML = '<option value="">Selecione uma cidade</option>';
                
                if (data && data.length > 0) {
                    data.forEach(cidade => {
                        const option = document.createElement('option');
                        option.value = cidade.value;
                        option.textContent = cidade.label;
                        this.cidadeSelect.appendChild(option);
                    });
                } else {
                    this.cidadeSelect.innerHTML = '<option value="">Nenhuma cidade encontrada</option>';
                }
                
                this.cidadeSelect.disabled = false;
                resolve(data);
            })
            .catch(error => {
                console.error('Erro ao carregar cidades:', error);
                this.cidadeSelect.innerHTML = '<option value="">Erro ao carregar cidades: ' + error.message + '</option>';
                this.cidadeSelect.disabled = false;
                reject(error);
            });
        });
    }

    // Função para carregar cartórios via API
    async carregarCartorios(estado, cidade) {
        if (!this.cartorioSelect) {
            console.error('Select de cartório não encontrado');
            return;
        }
        
        // Mostrar loading
        this.cartorioSelect.innerHTML = '<option value="">Carregando cartórios...</option>';
        this.cartorioSelect.disabled = true;
        
        // Obter token CSRF
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
        if (!csrfToken) {
            console.error('Token CSRF não encontrado');
            this.cartorioSelect.innerHTML = '<option value="">Erro: Token CSRF não encontrado</option>';
            this.cartorioSelect.disabled = false;
            return;
        }
        
        console.log('Fazendo requisição para buscar cartórios:', estado, cidade);
        
        try {
            const response = await fetch('/dominial/buscar-cartorios/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-CSRFToken': csrfToken.value,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: `estado=${encodeURIComponent(estado)}&cidade=${encodeURIComponent(cidade)}`,
                credentials: 'same-origin'
            });
            
            console.log('Status da resposta:', response.status);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            console.log('Dados recebidos:', data);
            this.cartorioSelect.innerHTML = '<option value="">Selecione um cartório</option>';
            
            if (data && data.length > 0) {
                data.forEach(cartorio => {
                    const option = document.createElement('option');
                    option.value = cartorio.id;
                    option.textContent = cartorio.nome;
                    option.setAttribute('data-cartorio', JSON.stringify(cartorio));
                    this.cartorioSelect.appendChild(option);
                });
            } else {
                this.cartorioSelect.innerHTML = '<option value="">Nenhum cartório encontrado</option>';
            }
            
            // Adicionar a opção de novo cartório
            const novoOption = document.createElement('option');
            novoOption.value = 'novo';
            novoOption.textContent = 'Adicionar novo cartório';
            this.cartorioSelect.appendChild(novoOption);
            
            this.cartorioSelect.disabled = false;
        } catch (error) {
            console.error('Erro ao carregar cartórios:', error);
            this.cartorioSelect.innerHTML = '<option value="">Erro ao carregar cartórios: ' + error.message + '</option>';
            this.cartorioSelect.disabled = false;
        }
    }

    // Função para mostrar detalhes do cartório
    mostrarDetalhesCartorio(cartorioId) {
        const cartorioOption = this.cartorioSelect.querySelector(`option[value="${cartorioId}"]`);
        const detalhesDiv = document.getElementById('cartorio-detalhes');
        
        if (cartorioOption && cartorioOption.hasAttribute('data-cartorio')) {
            const cartorio = JSON.parse(cartorioOption.getAttribute('data-cartorio'));
            
            detalhesDiv.innerHTML = `
                <div class="cartorio-info">
                    <p><strong>Nome:</strong> ${cartorio.nome}</p>
                    <p><strong>CNS:</strong> ${cartorio.cns || 'Não informado'}</p>
                    <p><strong>Endereço:</strong> ${cartorio.endereco || 'Não informado'}</p>
                    <p><strong>Telefone:</strong> ${cartorio.telefone || 'Não informado'}</p>
                    <p><strong>E-mail:</strong> ${cartorio.email || 'Não informado'}</p>
                </div>
            `;
            
            // Definir o ID do cartório no campo hidden
            document.getElementById('cartorio_id').value = cartorioId;
        }
    }
}

// Inicializar formulário quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', function() {
    window.imovelForm = new ImovelForm();
}); 