// Modal de aviso do "Baixar certidões" (#334 — decisão do dono, 21/11/2026).
//
// O ZIP baixa a cadeia inteira (a mesma lista do XLSX); a escolha de origem
// da tela não filtra. Antes de baixar, consulta o endpoint de verificação:
// sem perdas, baixa direto; com perdas (PDF indisponível ou documento sem
// PDF), abre o modal listando os indisponíveis e a contagem de "sem PDF".
// Sem JS, o link baixa direto — degradação aceitável.
(function () {
    'use strict';

    var botao = document.getElementById('botao-baixar-certidoes');
    var modal = document.getElementById('modal-certidoes');
    if (!botao || !modal) {
        return;
    }

    var lista = document.getElementById('modal-certidoes-lista');
    var avisoSemPdf = document.getElementById('modal-certidoes-sem-pdf');
    var confirmar = document.getElementById('modal-certidoes-confirmar');
    var cancelar = document.getElementById('modal-certidoes-cancelar');
    var gatilho = null; // quem abriu o modal, para devolver o foco

    function abrir() {
        gatilho = document.activeElement;
        modal.style.display = 'block'; // mesmo padrão do modalSelecaoSequencia
        confirmar.focus();
    }

    function fechar() {
        modal.style.display = 'none';
        if (gatilho && typeof gatilho.focus === 'function') {
            gatilho.focus();
        }
    }

    function listarPerdas(dados) {
        lista.innerHTML = '';
        dados.indisponiveis.forEach(function (item) {
            var li = document.createElement('li');
            li.textContent =
                item.ordem + '. ' + item.tipo + ' ' + item.numero +
                ' — "' + item.nome_original + '" não encontrado no armazenamento';
            lista.appendChild(li);
        });
        if (dados.sem_pdf > 0) {
            avisoSemPdf.textContent =
                dados.sem_pdf + (dados.sem_pdf === 1
                    ? ' documento sem PDF anexado'
                    : ' documentos sem PDF anexado');
            avisoSemPdf.hidden = false;
        } else {
            avisoSemPdf.hidden = true;
        }
    }

    botao.addEventListener('click', function (evento) {
        evento.preventDefault();
        fetch(botao.dataset.verificarUrl, {
            headers: { Accept: 'application/json' },
            credentials: 'same-origin',
        })
            .then(function (resposta) {
                if (!resposta.ok) {
                    throw new Error('verificação falhou: ' + resposta.status);
                }
                return resposta.json();
            })
            .then(function (dados) {
                if (dados.indisponiveis.length === 0 && dados.sem_pdf === 0) {
                    // Nada a avisar: baixa direto, sem modal.
                    window.location.href = botao.href;
                    return;
                }
                listarPerdas(dados);
                abrir();
            })
            .catch(function () {
                // A verificação não pode travar o download: segue o fluxo
                // sem JS (mesma degradação de um link puro).
                window.location.href = botao.href;
            });
    });

    cancelar.addEventListener('click', fechar);
    // Download com attachment não navega fora da página: fecha o modal.
    confirmar.addEventListener('click', fechar);
    // Clique no fundo escuro (fora do .modal-content) fecha.
    modal.addEventListener('click', function (evento) {
        if (evento.target === modal) {
            fechar();
        }
    });
    document.addEventListener('keydown', function (evento) {
        if (evento.key === 'Escape' && modal.style.display === 'block') {
            fechar();
        }
    });
})();
