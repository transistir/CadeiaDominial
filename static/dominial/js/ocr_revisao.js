/**
 * Tela de revisão de campos extraídos (templates/ia_ocr/revisao_campos.html,
 * issue #262 / I-5): salva cada card por JSON com controle otimista de versão.
 *
 * Cada alteração num card (valor, incluir, conferido, escolha de cadastro,
 * conversão de área) agenda, com debounce de 300 ms, um POST só daquele card
 * para url_salvar. 200 atualiza a versão; 409 recarrega a página (outra aba
 * ou usuário mudou a revisão); 422 mostra o erro no próprio card. O finalizar
 * também vai em JSON, porque o endpoint não aceita formulário.
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
    var TIPOS_SEM_VALOR = ['parte', 'cartorio', 'ato'];
    var MENSAGENS_ERRO = {
        valor_invalido: 'Valor inválido para este campo.',
        conversao_incompleta: 'Informe a área em hectares e confirme a conversão.',
        escolha_invalida: 'Escolha de cadastro inválida.',
        decisao_invalida: 'Decisão inválida para este campo.',
        sem_extracao: 'Extração indisponível.'
    };

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
        var recarregando = false;

        function rotular(card) {
            var rotulo = card.querySelector('[data-campo-rotulo]');
            if (!rotulo) return;
            var partes = card.getAttribute('data-chave').split('/').filter(Boolean);
            var ultimo = partes.length ? partes[partes.length - 1] : '';
            if (ultimo) rotulo.textContent = ultimo.replace(/_/g, ' ');
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

        function marcarEstado(card, texto) {
            var estado = card.querySelector('[data-campo-estado]');
            if (estado) estado.textContent = texto;
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

        function recarregar() {
            if (recarregando) return;
            recarregando = true;
            window.alert('A revisão foi alterada em outro lugar. A página será atualizada.');
            window.location.reload();
        }

        function salvar(card) {
            timers.delete(card);
            marcarEstado(card, 'Salvando…');
            return fetch(urlSalvar, {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
                body: JSON.stringify({ versao: versaoAtual, decisoes: [decisao(card)] })
            }).then(function (resposta) {
                return resposta.json().catch(function () { return {}; }).then(function (dados) {
                    if (resposta.status === 200) {
                        definirVersao(dados.versao);
                        card.classList.remove('alterado');
                        card.classList.add('salvo');
                        mostrarErro(card, '');
                        marcarEstado(card, 'Salvo');
                    } else if (resposta.status === 409) {
                        recarregar();
                    } else if (resposta.status === 422) {
                        marcarEstado(card, '');
                        mostrarErro(card, MENSAGENS_ERRO[dados.erro] || 'Não foi possível salvar este campo.');
                    } else {
                        marcarEstado(card, '');
                        mostrarErro(card, 'Erro ao salvar (HTTP ' + resposta.status + ').');
                    }
                });
            }).catch(function () {
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
            if (card && evento.target.type !== 'checkbox') agendar(card);
        });
        raiz.addEventListener('change', function (evento) {
            var card = cardDe(evento.target);
            var alvo = evento.target;
            if (card && (alvo.type === 'checkbox' || alvo.tagName === 'SELECT')) {
                card.classList.toggle('descartado', !(card.querySelector('[data-campo-incluir]') || {}).checked);
                agendar(card);
            }
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

        if (form) {
            form.addEventListener('submit', function (evento) {
                evento.preventDefault();
                var botao = form.querySelector('[data-ocr-finalizar]');
                if (botao && botao.disabled) return;
                if (timers.size) {
                    msgFinalizar.textContent = 'Aguarde o salvamento dos campos alterados.';
                    return;
                }
                if (botao) botao.disabled = true;
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
                            if (botao) botao.disabled = false;
                            msgFinalizar.textContent = dados.erro === 'revisao_incompleta'
                                ? 'Ainda há pendências. Atualize a página para vê-las.'
                                : 'Não foi possível finalizar a revisão.';
                        }
                    });
                }).catch(function () {
                    if (botao) botao.disabled = false;
                    msgFinalizar.textContent = 'Sem conexão com o servidor. Tente de novo.';
                });
            });
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        var raiz = document.querySelector('[data-ocr-revisao]');
        if (raiz) iniciar(raiz);
    });
})();
