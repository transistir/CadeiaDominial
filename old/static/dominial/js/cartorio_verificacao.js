/**
 * Serviço JavaScript para verificação e importação de cartórios
 * Segue o padrão de modularização do projeto
 */

class CartorioVerificacaoService {
    constructor() {
        this.csrfToken = this.getCsrfToken();
    }

    /**
     * Obtém o token CSRF do formulário
     */
    getCsrfToken() {
        const token = document.querySelector('[name=csrfmiddlewaretoken]');
        return token ? token.value : null;
    }

    /**
     * Verifica se existem cartórios para um estado
     */
    async verificarCartoriosEstado(estado) {
        try {
            const response = await fetch('/dominial/verificar-cartorios/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-CSRFToken': this.csrfToken,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: `estado=${encodeURIComponent(estado)}`,
                credentials: 'same-origin'
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Erro ao verificar cartórios:', error);
            throw error;
        }
    }

    /**
     * Importa cartórios de um estado
     */
    async importarCartoriosEstado(estado) {
        try {
            const response = await fetch('/dominial/importar-cartorios/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-CSRFToken': this.csrfToken,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: `estado=${encodeURIComponent(estado)}`,
                credentials: 'same-origin'
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Erro ao importar cartórios:', error);
            throw error;
        }
    }
}

class CartorioModalService {
    constructor() {
        this.modalId = 'modal-importacao-cartorios';
        this.modal = null;
        this.progressInterval = null;
        this.startTime = null;
    }

    /**
     * Cria ou atualiza o modal de importação
     */
    criarModal(estado) {
        if (!this.modal) {
            this.modal = document.createElement('div');
            this.modal.id = this.modalId;
            this.modal.className = 'modal';
            document.body.appendChild(this.modal);
        }

        this.modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h3>Importar Cartórios</h3>
                    <span class="close" onclick="cartorioModalService.fecharModal()">&times;</span>
                </div>
                <div class="modal-body">
                    <p>Não foram encontrados cartórios para o estado <strong>${estado}</strong>.</p>
                    <p>Deseja importar automaticamente os cartórios deste estado?</p>
                    <div class="modal-buttons">
                        <button type="button" onclick="cartorioModalService.fecharModal()" class="btn btn-secondary">Cancelar</button>
                        <button type="button" onclick="cartorioModalService.importarCartorios('${estado}')" class="btn btn-primary">Importar Cartórios</button>
                    </div>
                </div>
            </div>
        `;

        this.modal.classList.add('show');
    }

    /**
     * Atualiza o modal para mostrar progresso
     */
    mostrarProgresso(estado) {
        if (!this.modal) return;

        this.startTime = Date.now();

        this.modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h3>Importando Cartórios</h3>
                </div>
                <div class="modal-body">
                    <p>Importando cartórios do estado <strong>${estado}</strong>...</p>
                    <p>Este processo pode levar alguns minutos. Por favor, aguarde.</p>
                    
                    <div class="progress-container">
                        <div class="progress-bar">
                            <div class="progress-fill" id="progress-fill"></div>
                        </div>
                        <div class="progress-text" id="progress-text">Iniciando importação...</div>
                    </div>
                    
                    <div class="progress-details" id="progress-details">
                        <p><strong>Status:</strong> <span id="status-text">Conectando ao servidor...</span></p>
                        <p><strong>Tempo decorrido:</strong> <span id="tempo-decorrido">0s</span></p>
                        <p><strong>Observação:</strong> A importação está sendo processada no servidor. O progresso será atualizado quando concluído.</p>
                    </div>
                </div>
            </div>
        `;

        // Iniciar animação de progresso realista
        this.iniciarAnimacaoProgresso();
    }

    /**
     * Inicia animação de progresso realista
     */
    iniciarAnimacaoProgresso() {
        const progressFill = document.getElementById('progress-fill');
        const progressText = document.getElementById('progress-text');
        const statusText = document.getElementById('status-text');
        const tempoDecorrido = document.getElementById('tempo-decorrido');
        
        let progress = 0;
        
        // Tempo estimado total para a importação (baseado em testes reais)
        const tempoEstimadoTotal = 180000; // 3 minutos em milissegundos
        
        // Fases do processo com tempos proporcionais
        const phases = [
            { name: 'Iniciando importação...', duration: 5000, progress: 5, color: '#007bff' },
            { name: 'Conectando ao servidor de dados...', duration: 8000, progress: 15, color: '#17a2b8' },
            { name: 'Buscando informações de cidades...', duration: 15000, progress: 30, color: '#28a745' },
            { name: 'Processando dados dos cartórios...', duration: 30000, progress: 50, color: '#ffc107' },
            { name: 'Salvando cartórios no banco...', duration: 25000, progress: 70, color: '#fd7e14' },
            { name: 'Finalizando importação...', duration: 10000, progress: 85, color: '#6f42c1' },
            { name: 'Aguardando conclusão...', duration: 97000, progress: 98, color: '#e83e8c' }
        ];

        // Adicionar animação de pulso à barra
        progressFill.style.animation = 'progressPulse 2s ease-in-out infinite';

        this.progressInterval = setInterval(() => {
            const elapsed = Date.now() - this.startTime;
            const elapsedSeconds = Math.floor(elapsed / 1000);
            tempoDecorrido.textContent = `${elapsedSeconds}s`;

            // Calcular progresso baseado no tempo decorrido real
            let targetProgress = 0;
            let currentPhase = phases[0];
            let totalDuration = 0;
            
            // Calcular progresso proporcional ao tempo total estimado
            const progressoTempo = Math.min(98, (elapsed / tempoEstimadoTotal) * 100);
            
            // Determinar fase atual baseada no tempo
            for (let i = 0; i < phases.length; i++) {
                totalDuration += phases[i].duration;
                if (elapsed <= totalDuration) {
                    const phaseProgress = (elapsed - (totalDuration - phases[i].duration)) / phases[i].duration;
                    targetProgress = phases[i].progress + (phaseProgress * (phases[i + 1] ? phases[i + 1].progress - phases[i].progress : 3));
                    currentPhase = phases[i];
                    statusText.textContent = phases[i].name;
                    break;
                }
            }
            
            // Usar o menor entre progresso baseado em fases e progresso baseado em tempo
            // Isso garante que o progresso não pareça travado
            targetProgress = Math.min(targetProgress, progressoTempo);
            
            // Suavizar transição do progresso
            if (targetProgress > progress) {
                progress += Math.min(0.8, targetProgress - progress);
            }
            
            // Limitar progresso a 98% até receber resposta do servidor
            progress = Math.min(98, progress);
            
            // Atualizar barra de progresso com animação
            progressFill.style.width = `${progress}%`;
            progressFill.style.background = `linear-gradient(90deg, ${currentPhase.color} 0%, ${this.getNextColor(currentPhase.color)} 100%)`;
            
            // Adicionar efeito de brilho
            progressFill.style.boxShadow = `0 0 10px ${currentPhase.color}40`;
            
            // Atualizar texto com indicador de atividade
            const activityIndicator = progress < 98 ? '⏳' : '✅';
            progressText.innerHTML = `${activityIndicator} Progresso: ${Math.round(progress)}%`;
            
            // Adicionar informação de tempo estimado restante
            if (progress < 98) {
                const tempoRestante = Math.max(0, Math.ceil((tempoEstimadoTotal - elapsed) / 1000));
                if (tempoRestante > 0) {
                    progressText.innerHTML += ` (${tempoRestante}s restantes)`;
                }
            }
            
        }, 100);
    }

    /**
     * Obtém a próxima cor para gradiente
     */
    getNextColor(currentColor) {
        const colors = ['#007bff', '#17a2b8', '#28a745', '#ffc107', '#fd7e14', '#6f42c1'];
        const currentIndex = colors.indexOf(currentColor);
        const nextIndex = (currentIndex + 1) % colors.length;
        return colors[nextIndex];
    }

    /**
     * Para a animação de progresso
     */
    pararAnimacaoProgresso() {
        if (this.progressInterval) {
            clearInterval(this.progressInterval);
            this.progressInterval = null;
        }
    }

    /**
     * Mostra conclusão da importação
     */
    mostrarConclusao(estado, totalCartorios) {
        if (!this.modal) return;

        this.pararAnimacaoProgresso();

        const elapsed = Date.now() - this.startTime;
        const elapsedSeconds = Math.floor(elapsed / 1000);

        this.modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h3>✅ Importação Concluída</h3>
                </div>
                <div class="modal-body">
                    <div class="success-message">
                        <p><strong>Importação concluída com sucesso!</strong></p>
                        <p>Foram importados <strong>${totalCartorios}</strong> cartórios do estado <strong>${estado}</strong>.</p>
                        <p>Tempo total: <strong>${elapsedSeconds} segundos</strong></p>
                        <p>O formulário será atualizado automaticamente.</p>
                    </div>
                    
                    <div class="progress-container">
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: 100%; background-color: #28a745;"></div>
                        </div>
                        <div class="progress-text">Importação concluída!</div>
                    </div>
                    
                    <div class="modal-buttons">
                        <button type="button" onclick="cartorioModalService.finalizarImportacao('${estado}')" class="btn btn-success">Continuar</button>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Fecha o modal
     */
    fecharModal() {
        this.pararAnimacaoProgresso();
        if (this.modal) {
            this.modal.classList.remove('show');
        }
    }

    /**
     * Importa cartórios e gerencia o estado do modal
     */
    async importarCartorios(estado) {
        if (!confirm(`Deseja importar automaticamente os cartórios do estado ${estado}? Isso pode levar alguns minutos.`)) {
            return;
        }

        try {
            // Mostrar progresso
            this.mostrarProgresso(estado);

            // Fazer a importação
            const resultado = await cartorioVerificacaoService.importarCartoriosEstado(estado);

            if (resultado.success) {
                // Mostrar conclusão
                this.mostrarConclusao(estado, resultado.total_cartorios);
            } else {
                this.mostrarErro('Erro na importação: ' + (resultado.error || 'Erro desconhecido'));
            }
        } catch (error) {
            console.error('Erro na importação:', error);
            this.mostrarErro('Erro na importação: ' + error.message);
        }
    }

    /**
     * Mostra erro na importação
     */
    mostrarErro(mensagem) {
        if (!this.modal) return;

        this.pararAnimacaoProgresso();

        const elapsed = Date.now() - this.startTime;
        const elapsedSeconds = Math.floor(elapsed / 1000);

        this.modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h3>❌ Erro na Importação</h3>
                </div>
                <div class="modal-body">
                    <div class="error-message">
                        <p><strong>Erro:</strong> ${mensagem}</p>
                        <p>Tempo decorrido: <strong>${elapsedSeconds} segundos</strong></p>
                        <p>Tente novamente ou entre em contato com o suporte.</p>
                    </div>
                    
                    <div class="modal-buttons">
                        <button type="button" onclick="cartorioModalService.fecharModal()" class="btn btn-secondary">Fechar</button>
                        <button type="button" onclick="cartorioModalService.importarCartorios('${estado}')" class="btn btn-primary">Tentar Novamente</button>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Finaliza a importação e atualiza o formulário
     */
    finalizarImportacao(estado) {
        this.fecharModal();
        
        // Preservar dados preenchidos
        const dadosFormulario = this.preservarDadosFormulario();
        
        // Recarregar cidades
        if (typeof carregarCidades === 'function') {
            carregarCidades(estado).then(() => {
                // Restaurar dados após carregar cidades
                this.restaurarDadosFormulario(dadosFormulario);
                
                // Mostrar notificação de sucesso
                this.mostrarNotificacaoSucesso(estado);
            });
        }
    }

    /**
     * Preserva dados preenchidos no formulário
     */
    preservarDadosFormulario() {
        const dados = {};
        
        // Preservar campos básicos
        const campos = [
            'nome', 'matricula', 'sncr', 'area', 'observacoes',
            'id_proprietario', 'novo_proprietario_nome', 'novo_proprietario_cpf',
            'novo_proprietario_email', 'novo_proprietario_telefone'
        ];
        
        campos.forEach(campo => {
            const elemento = document.getElementById(campo);
            if (elemento) {
                dados[campo] = elemento.value;
            }
        });
        
        // Preservar estado selecionado
        const estadoSelect = document.getElementById('estado');
        if (estadoSelect) {
            dados.estado = estadoSelect.value;
        }
        
        return dados;
    }

    /**
     * Restaura dados preenchidos no formulário
     */
    restaurarDadosFormulario(dados) {
        Object.keys(dados).forEach(campo => {
            const elemento = document.getElementById(campo);
            if (elemento && dados[campo]) {
                elemento.value = dados[campo];
            }
        });
        
        // Restaurar estado
        const estadoSelect = document.getElementById('estado');
        if (estadoSelect && dados.estado) {
            estadoSelect.value = dados.estado;
        }
    }

    /**
     * Mostra notificação de sucesso
     */
    mostrarNotificacaoSucesso(estado) {
        // Criar notificação
        const notificacao = document.createElement('div');
        notificacao.className = 'notificacao-sucesso';
        notificacao.innerHTML = `
            <div class="notificacao-content">
                <span class="notificacao-icon">✅</span>
                <span class="notificacao-text">Cartórios do estado ${estado} importados com sucesso! As cidades estão disponíveis no formulário.</span>
                <button class="notificacao-close" onclick="this.parentElement.parentElement.remove()">×</button>
            </div>
        `;
        
        // Adicionar ao DOM
        document.body.appendChild(notificacao);
        
        // Remover automaticamente após 5 segundos
        setTimeout(() => {
            if (notificacao.parentElement) {
                notificacao.remove();
            }
        }, 5000);
    }

    /**
     * Dispara evento para recarregar cidades
     */
    dispararEventoRecarregamento(estado) {
        const event = new CustomEvent('cartoriosImportados', {
            detail: { estado: estado }
        });
        document.dispatchEvent(event);
    }
}

// Instâncias globais dos serviços
const cartorioVerificacaoService = new CartorioVerificacaoService();
const cartorioModalService = new CartorioModalService();

// Funções globais para compatibilidade com o código existente
window.verificarCartoriosEstado = async function(estado) {
    try {
        const resultado = await cartorioVerificacaoService.verificarCartoriosEstado(estado);
        
        if (resultado.existem_cartorios) {
            // Se existem cartórios, carregar cidades normalmente
            if (typeof carregarCidades === 'function') {
                carregarCidades(estado);
            }
        } else {
            // Se não existem cartórios, mostrar modal de importação
            cartorioModalService.criarModal(estado);
        }
    } catch (error) {
        console.error('Erro ao verificar cartórios:', error);
        // Em caso de erro, tentar carregar cidades normalmente
        if (typeof carregarCidades === 'function') {
            carregarCidades(estado);
        }
    }
};

window.fecharModalImportacao = function() {
    cartorioModalService.fecharModal();
    
    // Limpar o select de estado
    const estadoSelect = document.getElementById('estado');
    if (estadoSelect) {
        estadoSelect.value = '';
    }
    
    // Limpar o select de cidade
    const cidadeSelect = document.getElementById('cidade_select');
    if (cidadeSelect) {
        cidadeSelect.innerHTML = '<option value="">Selecione uma cidade</option>';
    }
}; 