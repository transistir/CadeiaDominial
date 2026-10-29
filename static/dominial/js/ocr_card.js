/**
 * Card "Extrair texto com IA" do upload digital (templates/dominial/
 * upload_documento_digital.html). Extraído do template para estático em
 * versão testável sem navegador (ia_ocr/tests/js/ocr_card.test.js, PR #279).
 * Fonte única dos estados: ia_ocr.estados, espelhado nos data-* do card.
 *
 * #307 (I-9): o OCR em GPU pode levar minutos — o card mostra uma expectativa
 * com o tempo decorrido, não exibe "página 0 de N" e tolera falha de rede com
 * backoff ("Reconectando…") sem nunca declarar falha do OCR por rede.
 * Rodada 2: o tempo saiu do badge (aria-live anunciava a cada consulta),
 * respostas em voo são descartadas por geração (terminal não reabre o card),
 * o corte de 10 min para polling e contador com aviso próprio, "Reconectando…"
 * tem região viva sempre no DOM e erros permanentes (404/redirect) cortam em
 * vez de entrar em backoff.
 * Rodada 3: o corte por erro permanente tem texto próprio (o servidor
 * respondeu, mas o status não está disponível ≠ rede fora) e o clique em
 * "Atualizar status" limpa a região viva antes de retomar.
 */
(function () {
    'use strict';
    var INTERVALO_MS = 3000;
    var INTERVALO_CONTADOR_MS = 1000;
    // Rede de segurança: após 10 min de falhas consecutivas o polling para —
    // timer e contador cancelados, aviso trocado e o botão Atualizar status
    // devolve o controle ao usuário.
    var LIMITE_RECONEXAO_MS = 600000;
    var ATRASO_SEGUNDA_FALHA_MS = 5000;
    var ATRASO_FALHA_LONGA_MS = 10000;
    // Texto neutro: vale para pendente e em_execucao; o tempo entra na linha
    // de expectativa (fora de aria-live), nunca no badge.
    var TEXTO_EXPECTATIVA = 'O processamento pode levar alguns minutos. Tempo decorrido: ';
    var TEXTO_RECONECTANDO = 'Reconectando…';
    var TEXTO_SEM_CONEXAO = 'Sem conexão com o servidor. Use "Atualizar status" para tentar de novo.';
    // O servidor respondeu, mas o status não está disponível (4xx sem volta,
    // redirect para o login): "tentar de novo" repetiria o erro — mandar
    // recarregar é o que resta ao usuário (rodada 3, #307).
    var TEXTO_CONSULTA_INDISPONIVEL = 'Não foi possível consultar o status. Recarregue a página.';

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

    // ---------- tempo decorrido (R1, #307) ----------

    function agora() {
        return new Date().getTime();
    }

    // '45 s' / '1 min 24 s' / '3 h 5 min 3 s'.
    function formatarDuracao(segundos) {
        var horas = Math.floor(segundos / 3600);
        var minutos = Math.floor((segundos % 3600) / 60);
        var pedacos = [];
        if (horas) pedacos.push(horas + ' h');
        if (horas || minutos) pedacos.push(minutos + ' min');
        pedacos.push((segundos % 60) + ' s');
        return pedacos.join(' ');
    }

    function formatarDecorrido(inicioMs) {
        var segundos = Math.max(0, Math.floor((agora() - inicioMs) / 1000));
        return formatarDuracao(segundos);
    }

    // Início da contagem: criado_em do payload, senão o atributo do template,
    // senão o momento em que o polling começou (guardado no estado do card).
    function inicioDaContagem(estado) {
        if (estado.inicioMs === null) estado.inicioMs = agora();
        return estado.inicioMs;
    }

    // ---------- estado do card (um único loop de polling/contador) ----------

    // `geracao` invalida respostas em voo: cada ciclo novo de consulta (carga
    // da página ou clique em Atualizar status) avança o contador e qualquer
    // resposta da geração anterior é descartada (rodada 2, #307).
    function novoEstado() {
        return { timer: null, contador: null, falhas: 0, falhaDesde: null, inicioMs: null, geracao: 0 };
    }

    function cancelarTimer(estado) {
        if (estado.timer !== null) {
            window.clearTimeout(estado.timer);
            estado.timer = null;
        }
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
        // R2 (#307): job ativo sem página processada (progresso ausente — a
        // view só monta `progresso` quando `page_count` existe, gravado no
        // finalizar, então job ativo vem com progresso: null — ou página 0)
        // nunca vira "página 0 de N". Rodada 2: sem tempo no badge — ele é
        // role="status"/aria-live e anunciaria a cada consulta; o tempo fica
        // só na linha de expectativa.
        var pagina = data.progresso ? data.progresso.pagina : null;
        if (emLista(data.status, statusAtivos(card)) && !(pagina > 0)) {
            var situacao = data.status === 'pendente' ? 'na fila' : 'processando…';
            definirTexto(badge, data.status_display + ' — ' + situacao);
        } else {
            definirTexto(badge, data.progresso
                ? data.status_display + ' — ' + data.progresso.texto
                : data.status_display);
        }

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

    // ---------- contador de 1 s (fora de aria-live: só a linha muda) ----------

    function pintarContador(card, estado) {
        var expectativa = card.querySelector('[data-ocr-expectativa]');
        if (!expectativa) return;
        expectativa.hidden = false;
        definirTexto(
            expectativa,
            TEXTO_EXPECTATIVA + formatarDecorrido(inicioDaContagem(estado))
        );
    }

    function iniciarContador(card, estado) {
        pintarContador(card, estado);
        if (estado.contador === null) {
            estado.contador = window.setInterval(function () {
                pintarContador(card, estado);
            }, INTERVALO_CONTADOR_MS);
        }
    }

    // Estado terminal: para o contador e esconde a expectativa — nenhum
    // timer/interval órfão depois do fim do job (R1, #307).
    function pararContador(card, estado) {
        if (estado.contador !== null) {
            window.clearInterval(estado.contador);
            estado.contador = null;
        }
        var expectativa = card.querySelector('[data-ocr-expectativa]');
        if (expectativa) expectativa.hidden = true;
    }

    // ---------- polling tolerante a falha de rede (R3, #307) ----------

    // Backoff: 1ª falha → 3 s, 2ª → 5 s, da 3ª em diante → 10 s.
    function atrasoReconexao(falhas) {
        if (falhas <= 1) return INTERVALO_MS;
        if (falhas === 2) return ATRASO_SEGUNDA_FALHA_MS;
        return ATRASO_FALHA_LONGA_MS;
    }

    // "Reconectando…" tem região viva própria, sempre no DOM e vazia no
    // template (rodada 2, #307): alternar hidden não é anunciado de forma
    // confiável, então o estado é o texto.
    function escreverReconectando(card, texto) {
        var aviso = card.querySelector('[data-ocr-reconectando]');
        if (aviso) definirTexto(aviso, texto);
    }

    // Corte (rede de segurança de 10 min ou erro permanente): para polling e
    // contador, anuncia o texto do corte na região viva e revela o botão que
    // devolve o controle ao usuário.
    function cortarConsultas(card, estado, texto) {
        cancelarTimer(estado);
        pararContador(card, estado);
        escreverReconectando(card, texto);
        var atualizar = card.querySelector('[data-ocr-atualizar]');
        if (atualizar) atualizar.hidden = false;
    }

    // 4xx sem volta (arquivo apagado em outra aba) e redirect para o login
    // (HTML → response.json() lançaria) não melhoram sozinhos: cortam em vez
    // de queimar 10 min de "Reconectando…" (rodada 2, #307). 408 e 429 são
    // transitórios e seguem no backoff.
    function respostaSemVolta(response) {
        if (response.redirected) return true;
        return response.status >= 400 && response.status < 500 &&
            response.status !== 408 && response.status !== 429;
    }

    // Nunca há mais de um timeout de consulta pendente por card: agendar
    // cancela o timer anterior. (Corridas de cliques em "Atualizar status"
    // são descartadas pela geração, em consultar.)
    function agendarConsulta(card, statusUrl, atraso, estado) {
        cancelarTimer(estado);
        estado.timer = window.setTimeout(function () {
            estado.timer = null;
            consultar(card, statusUrl, estado);
        }, atraso);
    }

    function consultar(card, statusUrl, estado) {
        var geracao = estado.geracao;
        fetch(statusUrl, { credentials: 'same-origin' })
            .then(function (response) {
                if (geracao !== estado.geracao) return null;
                if (respostaSemVolta(response)) {
                    cortarConsultas(card, estado, TEXTO_CONSULTA_INDISPONIVEL);
                    return null;
                }
                if (!response.ok) throw new Error('status ' + response.status);
                return response.json();
            })
            .then(function (data) {
                if (!data || geracao !== estado.geracao) return;
                var atualizar = card.querySelector('[data-ocr-atualizar]');
                if (atualizar) atualizar.hidden = true;
                estado.falhas = 0;
                estado.falhaDesde = null;
                escreverReconectando(card, '');
                if (data.criado_em) {
                    var ms = new Date(data.criado_em).getTime();
                    if (!isNaN(ms)) estado.inicioMs = ms;
                }
                var ativo = emLista(data.status, statusAtivos(card));
                pintar(card, data);
                if (ativo) {
                    iniciarContador(card, estado);
                    agendarConsulta(card, statusUrl, INTERVALO_MS, estado);
                } else {
                    // Terminal (concluido/falhou/…): para tudo — inclusive um
                    // timeout agendado por outra resposta em voo. O estado
                    // `falhou` só pode vir daqui, do payload do backend.
                    pararContador(card, estado);
                    cancelarTimer(estado);
                }
            })
            .catch(function () {
                if (geracao !== estado.geracao) return;
                // Erro de rede/serviço é transitório: backoff com o aviso
                // "Reconectando…" — nunca [data-ocr-erro] e nunca parada do
                // polling por rede (R3, #307); só a rede de segurança de
                // 10 min devolve o controle ao usuário.
                if (estado.falhaDesde === null) estado.falhaDesde = agora();
                estado.falhas += 1;
                escreverReconectando(card, TEXTO_RECONECTANDO);
                if (agora() - estado.falhaDesde >= LIMITE_RECONEXAO_MS) {
                    cortarConsultas(card, estado, TEXTO_SEM_CONEXAO);
                    return;
                }
                agendarConsulta(card, statusUrl, atrasoReconexao(estado.falhas), estado);
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
                var estado = novoEstado();
                var aoClicar = function () { disparar(card); };
                if (disparo) disparo.addEventListener('click', aoClicar);
                if (retry) retry.addEventListener('click', aoClicar);

                // Primeiro render (sem fetch): criado_em vem do template; sem
                // ele, a contagem começa no início do polling (R1, #307).
                var criadoEm = card.getAttribute('data-ocr-criado-em');
                if (criadoEm) {
                    var ms = new Date(criadoEm).getTime();
                    if (!isNaN(ms)) estado.inicioMs = ms;
                }

                // Retoma o polling do mesmo job depois de o corte desistir;
                // a nova geração descarta respostas em voo do ciclo antigo e
                // o timer pendente é cancelado para não nascer um segundo
                // loop (#260-C, #307-R3).
                if (atualizar) {
                    atualizar.addEventListener('click', function () {
                        atualizar.hidden = true;
                        cancelarTimer(estado);
                        estado.geracao += 1;
                        estado.falhas = 0;
                        estado.falhaDesde = null;
                        // Limpa a região viva antes de consultar: repetindo o
                        // mesmo texto, definirTexto não reescreveria e o
                        // leitor de tela não anunciaria o resultado (rodada
                        // 3, #307).
                        escreverReconectando(card, '');
                        if (statusUrl) consultar(card, statusUrl, estado);
                    });
                }

                var status = card.getAttribute('data-ocr-status');
                if (statusUrl && emLista(status, statusAtivos(card))) {
                    estado.geracao += 1;
                    iniciarContador(card, estado);
                    consultar(card, statusUrl, estado);
                }
            }
        );
    });
})();
