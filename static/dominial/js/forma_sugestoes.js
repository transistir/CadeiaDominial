/**
 * Issue #271 — "memória" de Forma e Título da transmissão.
 *
 * Preenche os datalists `formas-transacao` e `titulos-transacao` com os
 * valores mais usados nos lançamentos visíveis ao usuário
 * (`/dominial/forma-autocomplete/`). As opções são criadas com
 * `document.createElement` + `option.value` (nunca HTML montado com dado do
 * banco — lição do #196/#227). Falha de rede/JSON é silenciosa: o campo
 * continua um input de texto livre.
 */
(function () {
    'use strict';

    if (window.__formaSugestoesIniciado) {
        return;
    }
    window.__formaSugestoesIniciado = true;

    var ENDPOINT = '/dominial/forma-autocomplete/';
    var DEBOUNCE_MS = 250;
    var PARES = [
        { input: 'forma_transacao', lista: 'formas-transacao', campo: 'forma' },
        { input: 'titulo_transacao', lista: 'titulos-transacao', campo: 'titulo' }
    ];

    function preencher(datalist, results) {
        while (datalist.firstChild) {
            datalist.removeChild(datalist.firstChild);
        }
        results.forEach(function (item) {
            if (!item || typeof item.valor !== 'string') {
                return;
            }
            var option = document.createElement('option');
            option.value = item.valor;
            datalist.appendChild(option);
        });
    }

    function ligar(par) {
        var input = document.getElementById(par.input);
        var datalist = document.getElementById(par.lista);
        if (!input || !datalist || input.dataset.formaSugestoes === '1') {
            return;
        }
        input.dataset.formaSugestoes = '1';

        var controller = null;
        var timer = null;

        function buscar() {
            if (controller) {
                controller.abort();
            }
            var atual = new AbortController();
            controller = atual;
            var params = new URLSearchParams({ campo: par.campo });
            var q = input.value.trim();
            if (q) {
                params.set('q', q);
            }
            fetch(ENDPOINT + '?' + params.toString(), {
                credentials: 'same-origin',
                signal: atual.signal
            })
                .then(function (r) { return r.ok ? r.json() : null; })
                .then(function (data) {
                    if (controller !== atual || !data || !Array.isArray(data.results)) {
                        return;
                    }
                    preencher(datalist, data.results);
                })
                .catch(function () { /* silencioso: campo segue utilizável */ });
        }

        input.addEventListener('focus', buscar);
        input.addEventListener('input', function () {
            clearTimeout(timer);
            timer = setTimeout(buscar, DEBOUNCE_MS);
        });
    }

    function iniciar() {
        PARES.forEach(ligar);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', iniciar);
    } else {
        iniciar();
    }
})();
