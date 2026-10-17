/**
 * Card "Extrair texto com IA" do upload digital (templates/dominial/
 * upload_documento_digital.html). Extraído do template para estático em
 * versão testável sem navegador (ia_ocr/tests/js/ocr_card.test.js, PR #279).
 * Fonte única dos estados: ia_ocr.estados, espelhado nos data-* do card.
 */
(function () {
    'use strict';
    var INTERVALO_MS = 3000;
    var MAX_FALHAS_SEGUIDAS = 5;

    // Fonte única dos estados: ia_ocr.estados, injetado pela view em
    // data-* em JSON no container do card (review #260-F).
    function listaDeEstados(card, atributo) {
        try {
            var lista = JSON.parse(card.getAttribute(atributo));
            return lista instanceof Array ? lista : [];
        } catch (e) {
            return [];
        }
    }

    function statusAtivos(card) {
        return listaDeEstados(card, 'data-status-ativos');
    }

    function statusComTexto(card) {
        return listaDeEstados(card, 'data-status-com-texto');
    }

    // Estados em que o texto ainda pode ser revisado (tela da I-4, #261).
    function statusRevisaveis(card) {
        return listaDeEstados(card, 'data-status-revisaveis');
    }

    function emLista(status, lista) {
        return lista.indexOf(status) !== -1;
    }

    function csrfToken() {
        var input = document.querySelector('input[name="csrfmiddlewaretoken"]');
        return input ? input.value : '';
    }

    function classeBadge(card, status) {
        if (status === 'falhou') {
            return 'badge bg-danger';
        }
        if (emLista(status, statusAtivos(card))) {
            return 'badge bg-warning text-dark';
        }
        if (emLista(status, statusComTexto(card))) {
            return 'badge bg-success';
        }
        return 'badge bg-secondary';
    }

    // Escreve texto só quando muda: reatribuir o textContent de um
    // role="status" sem alteração faz alguns leitores de tela re-anunciarem
    // o estado a cada consulta (review #260-D).
    function definirTexto(elemento, texto) {
        if (elemento.textContent !== texto) elemento.textContent = texto;
    }

    // Repinta o card a partir do payload de status_job_ocr.
    function pintar(card, data) {
        var badge = card.querySelector('[data-ocr-badge]');
        var erro = card.querySelector('[data-ocr-erro]');
        var disparo = card.querySelector('[data-ocr-disparo]');
        var retry = card.querySelector('[data-ocr-retry]');
        var revisar = card.querySelector('[data-ocr-revisar]');
        var linkRevisar = card.querySelector('[data-ocr-revisar-link]');
        var motivo = card.querySelector('[data-ocr-revisar-motivo]');

        badge.className = classeBadge(card, data.status);
        definirTexto(badge, data.progresso
            ? data.status_display + ' — ' + data.progresso.texto
            : data.status_display);

        erro.hidden = data.status !== 'falhou';
        if (data.status === 'falhou') {
            definirTexto(erro, (data.erro && data.erro.mensagem) || 'Falha no processamento OCR.');
        }

        // Com job em andamento o disparo fica visível e desabilitado; nos
        // estados terminais ele sai e entra a ação correspondente.
        disparo.hidden = !emLista(data.status, statusAtivos(card));
        disparo.disabled = emLista(data.status, statusAtivos(card));
        retry.hidden = data.status !== 'falhou';
        // "Revisar texto": link para a tela de confirmação enquanto o texto é
        // revisável; nos demais estados com texto (já confirmado), o botão
        // desabilitado. Sem o link no card (renderizado sem job), cai para o botão.
        var revisavel = !!linkRevisar && emLista(data.status, statusRevisaveis(card));
        if (linkRevisar) linkRevisar.hidden = !revisavel;
        revisar.hidden = !emLista(data.status, statusComTexto(card)) || revisavel;
        // O motivo do revisar desabilitado acompanha o botão.
        if (motivo) motivo.hidden = revisar.hidden;
    }

    function consultar(card, statusUrl, falhas) {
        fetch(statusUrl, { credentials: 'same-origin' })
            .then(function (response) {
                if (!response.ok) throw new Error('status ' + response.status);
                return response.json();
            })
            .then(function (data) {
                var atualizar = card.querySelector('[data-ocr-atualizar]');
                if (atualizar) atualizar.hidden = true;
                pintar(card, data);
                if (emLista(data.status, statusAtivos(card))) {
                    window.setTimeout(function () { consultar(card, statusUrl, 0); }, INTERVALO_MS);
                }
            })
            .catch(function () {
                // Erro de rede/serviço é tratado como transiente; após várias
                // falhas seguidas, desiste e devolve o controle ao usuário —
                // que pode retomar pelo botão "Atualizar status" (#260-C).
                if (falhas + 1 >= MAX_FALHAS_SEGUIDAS) {
                    var erro = card.querySelector('[data-ocr-erro]');
                    erro.hidden = false;
                    erro.textContent = 'Não foi possível consultar o status do OCR.';
                    var atualizar = card.querySelector('[data-ocr-atualizar]');
                    if (atualizar) atualizar.hidden = false;
                    return;
                }
                window.setTimeout(function () { consultar(card, statusUrl, falhas + 1); }, INTERVALO_MS);
            });
    }

    // 201 (criado) e 409 (job ativo): recarrega para o servidor redesenhar o
    // card já em polling — o job está persistido. Demais respostas: mensagem
    // inline no próprio card.
    function disparar(card) {
        var disparo = card.querySelector('[data-ocr-disparo]');
        var retry = card.querySelector('[data-ocr-retry]');
        var erro = card.querySelector('[data-ocr-erro]');

        // Retry usa o mesmo handler; sem desabilitá-lo também, um 2º clique
        // durante o POST dispara outra requisição (review Greptile PR #279).
        function desabilitarGatilhos() {
            disparo.disabled = true;
            if (retry) retry.disabled = true;
        }

        function reabilitarGatilhos() {
            disparo.disabled = false;
            if (retry) retry.disabled = false;
        }

        desabilitarGatilhos();
        erro.hidden = true;
        fetch(card.getAttribute('data-criar-url'), {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'X-CSRFToken': csrfToken() }
        })
            .then(function (response) {
                if (response.status === 201 || response.status === 409) {
                    window.location.reload();
                    return null;
                }
                return response.json().then(function (data) {
                    erro.hidden = false;
                    erro.textContent = data.error || 'Não foi possível iniciar o OCR.';
                    reabilitarGatilhos();
                });
            })
            .catch(function () {
                erro.hidden = false;
                erro.textContent = 'Não foi possível iniciar o OCR.';
                reabilitarGatilhos();
            });
    }

    document.addEventListener('DOMContentLoaded', function () {
        Array.prototype.forEach.call(
            document.querySelectorAll('[data-ocr-card]'),
            function (card) {
                var statusUrl = card.getAttribute('data-status-url');
                var disparo = card.querySelector('[data-ocr-disparo]');
                var retry = card.querySelector('[data-ocr-retry]');
                var atualizar = card.querySelector('[data-ocr-atualizar]');
                var aoClicar = function () { disparar(card); };
                if (disparo) disparo.addEventListener('click', aoClicar);
                if (retry) retry.addEventListener('click', aoClicar);
                // Retoma o polling do mesmo job quando o corte de falhas
                // desistiu; esconde-se ao ser usado (#260-C).
                if (atualizar) {
                    atualizar.addEventListener('click', function () {
                        atualizar.hidden = true;
                        if (statusUrl) consultar(card, statusUrl, 0);
                    });
                }

                var status = card.getAttribute('data-ocr-status');
                if (statusUrl && emLista(status, statusAtivos(card))) {
                    consultar(card, statusUrl, 0);
                }
            }
        );
    });
})();
