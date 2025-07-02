// Modal de Cartório - Funcionalidades
class CartorioModal {
    constructor() {
        this.modal = document.getElementById('modal-novo-cartorio');
        this.form = document.getElementById('form-novo-cartorio');
        this.cartorioSelect = document.getElementById('cartorio');
        this.cartorioInfo = document.getElementById('cartorio-info');
        
        this.init();
    }

    init() {
        this.bindEvents();
        this.setupFormSubmission();
    }

    bindEvents() {
        // Fechar modal ao clicar fora dele
        window.addEventListener('click', (event) => {
            if (event.target === this.modal) {
                this.fecharModal();
            }
        });

        // Listener para mudança no select de cartório
        if (this.cartorioSelect) {
            this.cartorioSelect.addEventListener('change', (e) => {
                if (e.target.value === 'novo') {
                    this.abrirModal();
                }
            });
        }

        // Listener para botão de fechar modal
        const closeButton = this.modal?.querySelector('.close');
        if (closeButton) {
            closeButton.addEventListener('click', () => {
                this.fecharModal();
            });
        }

        // Listener para botão cancelar
        const cancelButton = this.modal?.querySelector('.btn-secondary');
        if (cancelButton) {
            cancelButton.addEventListener('click', () => {
                this.fecharModal();
            });
        }
    }

    abrirModal() {
        console.log('Abrindo modal de novo cartório');
        if (this.modal) {
            this.modal.style.display = 'block';
            this.preencherCamposAutomaticamente();
        }
    }

    fecharModal() {
        if (this.modal) {
            this.modal.style.display = 'none';
        }
        this.resetarSelect();
    }

    preencherCamposAutomaticamente() {
        // Preencher estado e cidade automaticamente se já selecionados
        const estadoSelecionado = document.getElementById('estado');
        const cidadeSelecionada = document.getElementById('cidade_select');
        
        if (estadoSelecionado && estadoSelecionado.value) {
            const novoEstado = document.getElementById('novo-cartorio-estado');
            if (novoEstado) {
                novoEstado.value = estadoSelecionado.value;
            }
        }
        if (cidadeSelecionada && cidadeSelecionada.value) {
            const novaCidade = document.getElementById('novo-cartorio-cidade');
            if (novaCidade) {
                novaCidade.value = cidadeSelecionada.value;
            }
        }
    }

    resetarSelect() {
        if (this.cartorioSelect) {
            this.cartorioSelect.value = '';
        }
        
        const cartorioId = document.getElementById('cartorio_id');
        if (cartorioId) {
            cartorioId.value = '';
        }
        
        if (this.cartorioInfo) {
            this.cartorioInfo.style.display = 'none';
        }
    }

    setupFormSubmission() {
        if (this.form) {
            this.form.addEventListener('submit', (e) => {
                e.preventDefault();
                this.criarNovoCartorio();
            });
        }
    }

    async criarNovoCartorio() {
        const formData = new FormData(this.form);
        const cartorioData = {
            nome: formData.get('nome'),
            cns: formData.get('cns'),
            endereco: formData.get('endereco'),
            telefone: formData.get('telefone'),
            email: formData.get('email'),
            estado: formData.get('estado'),
            cidade: formData.get('cidade')
        };

        try {
            const response = await this.enviarDadosCartorio(cartorioData);
            
            if (response.success) {
                this.adicionarCartorioAoSelect(response.cartorio);
                this.fecharModal();
                this.mostrarMensagemSucesso('Cartório criado com sucesso!');
            } else {
                this.mostrarMensagemErro('Erro ao criar cartório: ' + response.error);
            }
        } catch (error) {
            console.error('Erro:', error);
            this.mostrarMensagemErro('Erro ao criar cartório. Tente novamente.');
        }
    }

    async enviarDadosCartorio(cartorioData) {
        const csrf_token = document.querySelector('input[name="csrfmiddlewaretoken"]').value;
        
        const response = await fetch('/dominial/criar-cartorio/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrf_token
            },
            body: JSON.stringify(cartorioData)
        });
        
        return response.json();
    }

    adicionarCartorioAoSelect(cartorioData) {
        if (this.cartorioSelect) {
            const option = document.createElement('option');
            option.value = cartorioData.id;
            option.textContent = cartorioData.nome;
            option.dataset.info = JSON.stringify(cartorioData);
            this.cartorioSelect.appendChild(option);
            
            // Selecionar o novo cartório
            this.cartorioSelect.value = cartorioData.id;
        }
        
        const cartorioId = document.getElementById('cartorio_id');
        if (cartorioId) {
            cartorioId.value = cartorioData.id;
        }
        
        this.mostrarInformacoesCartorio(cartorioData);
    }

    mostrarInformacoesCartorio(cartorioData) {
        const responsavel = document.getElementById('cartorio-responsavel');
        const endereco = document.getElementById('cartorio-endereco');
        const telefone = document.getElementById('cartorio-telefone');
        const email = document.getElementById('cartorio-email');
        const cns = document.getElementById('cartorio-cns');
        
        if (responsavel) {
            responsavel.textContent = cartorioData.responsavel || 'Não informado';
        }
        if (endereco) {
            endereco.textContent = cartorioData.endereco || 'Não informado';
        }
        if (telefone) {
            telefone.textContent = cartorioData.telefone || 'Não informado';
        }
        if (email) {
            email.textContent = cartorioData.email || 'Não informado';
        }
        if (cns) {
            cns.textContent = cartorioData.cns || 'Não informado';
        }
        
        if (this.cartorioInfo) {
            this.cartorioInfo.style.display = 'block';
        }
    }

    mostrarMensagemSucesso(mensagem) {
        alert(mensagem);
    }

    mostrarMensagemErro(mensagem) {
        alert(mensagem);
    }
}



// Inicializar modal quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', function() {
    window.cartorioModal = new CartorioModal();
}); 