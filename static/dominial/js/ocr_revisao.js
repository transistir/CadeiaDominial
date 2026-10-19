/**
 * Tela de revisão de campos extraídos (templates/ia_ocr/revisao_campos.html,
 * issue #262 / I-5): salva cada card por JSON com controle otimista de versão.
 *
 * Cada alteração num card (valor, incluir, conferido, escolha de cadastro,
 * conversão de área) agenda, com debounce de 300 ms, um POST só daquele card
 * para url_salvar. Os POSTs saem em fila, um por vez, cada um com a versão
 * devolvida pelo anterior. 200 atualiza a versão e o contador/botão de
 * pendências; 409 recarrega a página (outra aba ou usuário mudou a revisão);
 * 422 mostra o erro no próprio card. Cards cujo último envio falhou ficam
 * registrados e são reenviados antes de finalizar. O finalizar também vai em
 * JSON, porque o endpoint não aceita formulário.
 *
 * Teclado (fora de campos de texto): j/k próximo/anterior, x alterna incluir.
 * Enter num input marca o card como conferido e avança.
 *
 * Dado do servidor só entra no DOM por textContent, nunca como HTML.
 */
(function () {
    'use strict';

    var ATRASO_MS = 300;
    // Tipos sem conversor de formulário no servidor: o valor não é editável.
    // Cartório é texto (nome para criar cadastro) e por isso envia valor.
    var TIPOS_SEM_VALOR = ['parte', 'ato'];
    var MENSAGENS_ERRO = {
        valor_invalido: 'Valor inválido para este campo.',
        conversao_incompleta: 'Informe a área em hectares e confirme a conversão.',
        escolha_invalida: 'Escolha de cadastro inválida.',
        escolha_incompativel: 'Escolha de cadastro incompatível com este campo.',
        decisao_invalida: 'Decisão inválida para este campo.',
        sem_extracao: 'Extração indisponível.'
    };
    var AVISO_RECARGA = 'Identidade alterada: a tela será atualizada quando você sair dos campos.';

    function iniciar(raiz) {
        var urlSalvar = raiz.getAttribute('data-url-salvar');
        var toolbar = raiz.querySelector('[data-ocr-toolbar]');
        var form = raiz.querySelector('[data-ocr-finalizar-form]');
        var inputVersao = raiz.querySelector('[data-ocr-versao]');
        var msgFinalizar = raiz.querySelector('[data-ocr-finalizar-msg]');
        var csrfInput = form && form.querySelector('[name=csrfmiddlewaretoken]');
        var csrf = csrfInput ? csrfInput.value : '';
        var versaoAtual = toolbar ? toolbar.getAttribute('data-versao') : '';
        var cards = Array.prototype.slice.call(raiz.querySelectorAll('[data-campo]'));
        var timers = new Map();
        var fila = Promise.resolve();
        var emFila = 0;
        var recarregando = false;
        var recargaPendente = false;
        var finalizando = false;
        // Último envio de cada card falhou: finalizar não pode ignorá-los.
        var falhas = new Set();
        // Chaves de atos distintos na mesma tela: sem o prefixo, "tipo" ou
        // "data" de atos diferentes ficam com o mesmo rótulo.
        var atosNaTela = new Set();
        cards.forEach(function (card) {
            var ato = /\/acts\/(\d+)(?:\/|$)/.exec(card.getAttribute('data-chave') || '');
            if (ato) atosNaTela.add(ato[1]);
        });

        function rotular(card) {
            var rotulo = card.querySelector('[data-campo-rotulo]');
            if (!rotulo) return;
            var chave = card.getAttribute('data-chave') || '';
            var partes = chave.split('/').filter(Boolean);
            var ultimo = partes.length ? partes[partes.length - 1] : '';
            if (!ultimo) return;
            var texto = ultimo.replace(/_/g, ' ');
            var ato = /\/acts\/(\d+)(?:\/|$)/.exec(chave);
            if (ato && atosNaTela.size > 1) {
                texto = 'Ato ' + (parseInt(ato[1], 10) + 1) + ' · ' + texto;
            }
            rotulo.textContent = texto;
        }

        function controlesDaRevisao() {
            return Array.prototype.slice.call(
                raiz.querySelectorAll('input, select, textarea, button')
            ).filter(function (elemento) {
                // CSRF e versão são hidden e precisam continuar enviando.
                return !(elemento.tagName === 'INPUT' && elemento.type === 'hidden');
            });
        }

        // Guarda o estado de cada controle para restaurar exatamente o que
        // já estava desabilitado (somente leitura, pendências etc.).
        function bloquearControles() {
            return controlesDaRevisao().map(function (elemento) {
                var estado = { elemento: elemento, estavaDesabilitado: elemento.disabled };
                elemento.disabled = true;
                return estado;
            });
        }

        function restaurarControles(estados) {
            estados.forEach(function (estado) {
                estado.elemento.disabled = estado.estavaDesabilitado;
            });
        }

        function definirVersao(versao) {
            versaoAtual = versao;
            if (toolbar) toolbar.setAttribute('data-versao', versao);
            if (inputVersao) inputVersao.value = versao;
            cards.forEach(function (card) {
                card.setAttribute('data-versao', versao);
            });
        }

        function mostrarErro(card, texto) {
            var erro = card.querySelector('[data-campo-erro]');
            if (!erro) return;
            erro.textContent = texto || '';
            erro.hidden = !texto;
        }

        function cardDaChave(chave) {
            if (!chave) return null;
            for (var i = 0; i < cards.length; i += 1) {
                if (cards[i].getAttribute('data-chave') === chave) return cards[i];
            }
            return null;
        }

        function marcarEstado(card, texto) {
            var estado = card.querySelector('[data-campo-estado]');
            if (estado) estado.textContent = texto;
        }

        function atualizarPendencias(pendencias) {
            var total = pendencias.length;
            var contador = raiz.querySelector('[data-ocr-contador-pendencias]');
            var rotulo = raiz.querySelector('[data-ocr-contador-pendencias-texto]');
            var botao = form && form.querySelector('[data-ocr-finalizar]');
            if (contador) contador.textContent = String(total);
            if (rotulo) rotulo.textContent = total === 1 ? 'pendência' : 'pendências';
            if (botao) {
                var somenteLeitura = !!raiz.querySelector('[data-ocr-somente-leitura]');
                if (!total && !somenteLeitura) {
                    botao.disabled = false;
                    botao.removeAttribute('title');
                } else {
                    botao.disabled = true;
                    botao.title = somenteLeitura
                        ? 'Esta extração já foi revisada.'
                        : 'Resolva as pendências antes de finalizar.';
                }
            }
            if (msgFinalizar) {
                msgFinalizar.textContent = recargaPendente ? AVISO_RECARGA : '';
            }
        }

        function decisao(card) {
            var item = {
                chave: card.getAttribute('data-chave'),
                incluir: !!(card.querySelector('[data-campo-incluir]') || {}).checked,
                conferido: !!(card.querySelector('[data-campo-conferido]') || {}).checked
            };
            var valor = card.querySelector('[data-campo-valor]');
            if (valor && TIPOS_SEM_VALOR.indexOf(valor.getAttribute('data-tipo')) === -1) {
                item.valor = valor.value;
            }
            // Só cards de parte/cartório têm estes controles; texto/data não levam escolha.
            var select = card.querySelector('[data-ocr-escolha]');
            var criarNovo = card.querySelector('[data-ocr-criar-novo]');
            if (select || criarNovo) {
                var escolhido = select && select.value ? parseInt(select.value, 10) : null;
                var alvo = select ? select.getAttribute('data-ocr-escolha') : null;
                item.escolha = {
                    pessoa_id: alvo === 'pessoa_id' ? escolhido : null,
                    cartorio_id: alvo === 'cartorio_id' ? escolhido : null,
                    criar_novo: !!(criarNovo && criarNovo.checked)
                };
            }
            var ha = card.querySelector('[data-campo-ha]');
            if (ha) {
                var confirmo = card.querySelector('[data-campo-confirmo]');
                item.ha_convertido = ha.value === '' ? null : ha.value;
                item.confirmo_conversao = !!(confirmo && confirmo.checked);
            }
            return item;
        }

        function recarregar(mensagem) {
            if (recarregando) return;
            recarregando = true;
            window.alert(mensagem
                || 'A revisão foi alterada em outro lugar. A página será atualizada.');
            window.location.reload();
        }

        function focoDentroDeCard() {
            var ativo = document.activeElement;
            return !!(ativo && ativo.closest && ativo.closest('[data-campo]'));
        }

        function focoNaToolbar() {
            var ativo = document.activeElement;
            return !!(ativo && ativo.closest && ativo.closest('[data-ocr-toolbar]'));
        }

        // A identidade de uma parte mudou: o select e o "criar novo" do card
        // guardam uma escolha que o servidor já descartou. Limpa e desabilita
        // até o reload, senão o próximo save reenviaria o cadastro antigo.
        function invalidarEscolha(chave) {
            var card = cardDaChave(chave);
            if (!card) return;
            var select = card.querySelector('[data-ocr-escolha]');
            var criarNovo = card.querySelector('[data-ocr-criar-novo]');
            if (select) {
                select.value = '';
                select.disabled = true;
            }
            if (criarNovo) {
                criarNovo.checked = false;
                criarNovo.disabled = true;
            }
        }

        function avisarRecargaPendente() {
            if (msgFinalizar) msgFinalizar.textContent = AVISO_RECARGA;
        }

        // Reload diferido: a identidade de uma parte mudou, mas o usuário
        // pode estar digitando. Só recarrega quando não há timer de debounce,
        // nem POST em fila, nem foco dentro de um card.
        function talvezRecarregar() {
            if (!recargaPendente || recarregando) return;
            // Save falho também segura o reload: recarregar agora perderia a
            // edição e o erro mostrado no card.
            if (timers.size || emFila || falhas.size
                    || focoDentroDeCard() || focoNaToolbar()) {
                avisarRecargaPendente();
                return;
            }
            recarregando = true;
            window.location.reload();
        }

        // Um POST por vez: cada um sai com a versão devolvida pelo anterior,
        // senão dois cards salvos juntos dão 409 contra a própria tela.
        function salvar(card) {
            timers.delete(card);
            // Durante a finalização os controles estão bloqueados: um save
            // atrasado tomaria 422 estado_invalido e a edição se perderia.
            if (finalizando) return Promise.resolve();
            marcarEstado(card, 'Salvando…');
            emFila += 1;
            fila = fila.then(function () {
                return recarregando ? null : enviar(card);
            }).then(function () {
                emFila -= 1;
                talvezRecarregar();
            });
            return fila;
        }

        function enviar(card) {
            return fetch(urlSalvar, {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
                body: JSON.stringify({ versao: versaoAtual, decisoes: [decisao(card)] })
            }).then(function (resposta) {
                return resposta.json().catch(function () { return {}; }).then(function (dados) {
                    if (resposta.status === 200) {
                        falhas.delete(card);
                        definirVersao(dados.versao);
                        card.classList.remove('alterado');
                        card.classList.add('salvo');
                        mostrarErro(card, '');
                        marcarEstado(card, 'Salvo');
                        if (Array.isArray(dados.pendencias)) {
                            atualizarPendencias(dados.pendencias);
                        }
                        // A identidade de uma parte mudou e a escolha antiga
                        // foi zerada no servidor. Não recarrega no meio da
                        // digitação: marca a pendência e deixa o reload para
                        // quando não houver timer, fila nem foco em card.
                        if (Array.isArray(dados.partes_invalidadas)
                                && dados.partes_invalidadas.length) {
                            dados.partes_invalidadas.forEach(invalidarEscolha);
                            recargaPendente = true;
                            avisarRecargaPendente();
                        }
                        // O novo tipo criou linhas obrigatórias que ainda não
                        // têm card: recarrega quando a edição atual terminar.
                        if (Array.isArray(dados.campos_novos)
                                && dados.campos_novos.length) {
                            recargaPendente = true;
                            avisarRecargaPendente();
                        }
                        talvezRecarregar();
                    } else if (resposta.status === 409) {
                        falhas.add(card);
                        recarregar();
                    } else if (resposta.status === 422) {
                        falhas.add(card);
                        marcarEstado(card, '');
                        var alvo = cardDaChave(dados.chave) || card;
                        if (alvo !== card) mostrarErro(card, '');
                        mostrarErro(alvo, MENSAGENS_ERRO[dados.erro] || 'Não foi possível salvar este campo.');
                    } else {
                        falhas.add(card);
                        marcarEstado(card, '');
                        mostrarErro(card, 'Erro ao salvar (HTTP ' + resposta.status + ').');
                    }
                });
            }).catch(function () {
                falhas.add(card);
                marcarEstado(card, '');
                mostrarErro(card, 'Sem conexão com o servidor. Tente de novo.');
            });
        }

        function agendar(card) {
            card.classList.add('alterado');
            card.classList.remove('salvo');
            marcarEstado(card, 'Alterado');
            if (timers.has(card)) window.clearTimeout(timers.get(card));
            timers.set(card, window.setTimeout(function () { salvar(card); }, ATRASO_MS));
        }

        function cardDe(elemento) {
            return elemento && elemento.closest ? elemento.closest('[data-campo]') : null;
        }

        function focarCard(indice) {
            if (indice < 0 || indice >= cards.length) return;
            var card = cards[indice];
            var alvo = card.querySelector('[data-campo-valor]:not([disabled]):not([readonly])');
            (alvo || card).focus();
            card.scrollIntoView({ block: 'nearest' });
        }

        function emEdicaoDeTexto(elemento) {
            if (!elemento) return false;
            var tag = elemento.tagName;
            if (tag === 'TEXTAREA' || tag === 'SELECT') return true;
            if (tag !== 'INPUT') return false;
            return ['checkbox', 'radio', 'button', 'submit'].indexOf(elemento.type) === -1;
        }

        cards.forEach(rotular);

        raiz.addEventListener('input', function (evento) {
            var card = cardDe(evento.target);
            if (!card || evento.target.type === 'checkbox') return;
            // Nome de cartório digitado vence o match antigo: sem limpar o
            // select, o próximo save reenviaria a escolha que o texto trocou.
            if (evento.target.getAttribute('data-tipo') === 'cartorio') {
                var select = card.querySelector('[data-ocr-escolha]');
                if (select) select.value = '';
            }
            agendar(card);
        });
        raiz.addEventListener('change', function (evento) {
            var card = cardDe(evento.target);
            var alvo = evento.target;
            if (card && (alvo.type === 'checkbox' || alvo.tagName === 'SELECT')) {
                // Escolher um cadastro e "criar novo" se excluem.
                var select = card.querySelector('[data-ocr-escolha]');
                var criarNovo = card.querySelector('[data-ocr-criar-novo]');
                if (alvo === criarNovo && criarNovo.checked && select) {
                    select.value = '';
                } else if (alvo === select && select.value && criarNovo) {
                    criarNovo.checked = false;
                }
                card.classList.toggle('descartado', !(card.querySelector('[data-campo-incluir]') || {}).checked);
                agendar(card);
            }
        });
        raiz.addEventListener('focusout', function (evento) {
            var destino = evento && evento.relatedTarget;
            if (destino && destino.closest && destino.closest('[data-campo]')) {
                return;
            }
            // Espera o foco assentar: durante o focusout o activeElement
            // ainda pode ser o body mesmo indo para outro card.
            window.setTimeout(talvezRecarregar, 0);
        });

        document.addEventListener('keydown', function (evento) {
            if (evento.ctrlKey || evento.metaKey || evento.altKey) return;
            var alvo = evento.target;
            var card = cardDe(alvo);
            var indice = card ? cards.indexOf(card) : -1;

            if (evento.key === 'Enter' && alvo.tagName === 'INPUT' && card && emEdicaoDeTexto(alvo)) {
                evento.preventDefault();
                var conferido = card.querySelector('[data-campo-conferido]');
                if (conferido && !conferido.disabled && !conferido.checked) {
                    conferido.checked = true;
                    agendar(card);
                }
                focarCard(indice + 1);
                return;
            }
            if (emEdicaoDeTexto(alvo)) return;

            if (evento.key === 'j') {
                evento.preventDefault();
                focarCard(indice + 1);
            } else if (evento.key === 'k') {
                evento.preventDefault();
                focarCard(indice < 0 ? 0 : indice - 1);
            } else if (evento.key === 'x' && card) {
                var incluir = card.querySelector('[data-campo-incluir]');
                if (incluir && !incluir.disabled) {
                    evento.preventDefault();
                    incluir.checked = !incluir.checked;
                    incluir.dispatchEvent(new Event('change', { bubbles: true }));
                }
            }
        });

        function reenviarFalhas() {
            var pendentes = Array.from(falhas);
            var ultima = Promise.resolve();
            pendentes.forEach(function (card) { ultima = salvar(card); });
            return ultima;
        }

        function finalizar() {
            if (finalizando) return;
            if (timers.size || emFila) {
                msgFinalizar.textContent = 'Aguarde o salvamento dos campos alterados.';
                return;
            }
            // Save que falhou não pode ser perdido na finalização: reenvia
            // todos antes e só segue quando o registro de falhas esvaziar.
            if (falhas.size) {
                msgFinalizar.textContent = 'Há campos com erro de salvamento. Reenviando…';
                reenviarFalhas().then(function () {
                    if (!falhas.size) {
                        finalizar();
                    } else {
                        msgFinalizar.textContent = 'Ainda há campos com erro de salvamento. Corrija-os e tente de novo.';
                    }
                });
                return;
            }
            finalizando = true;
            var controles = bloquearControles();
            fetch(form.action, {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
                body: JSON.stringify({ versao: versaoAtual })
            }).then(function (resposta) {
                return resposta.json().catch(function () { return {}; }).then(function (dados) {
                    if (resposta.status === 200 && dados.redirect) {
                        window.location.assign(dados.redirect);
                    } else if (resposta.status === 409) {
                        recarregar();
                    } else {
                        finalizando = false;
                        restaurarControles(controles);
                        msgFinalizar.textContent = dados.erro === 'revisao_incompleta'
                            ? 'Ainda há pendências. Atualize a página para vê-las.'
                            : 'Não foi possível finalizar a revisão.';
                    }
                });
            }).catch(function () {
                finalizando = false;
                restaurarControles(controles);
                msgFinalizar.textContent = 'Sem conexão com o servidor. Tente de novo.';
            });
        }

        if (form) {
            form.addEventListener('submit', function (evento) {
                evento.preventDefault();
                var botao = form.querySelector('[data-ocr-finalizar]');
                if (botao && botao.disabled) return;
                finalizar();
            });
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        var raiz = document.querySelector('[data-ocr-revisao]');
        if (raiz) iniciar(raiz);
    });
})();
