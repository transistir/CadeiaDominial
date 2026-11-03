/**
 * Extração automática (issue #314): na tela de confirmação do texto, quando
 * ainda não há extração, submete sozinho o formulário "Extrair campos" — do
 * upload ao formulário em um clique. O servidor não muda: é o mesmo POST do
 * botão manual, que continua na tela como fallback.
 *
 * Anti-duplo-disparo: trava em memória + sessionStorage
 * `ocr-auto-extrair:<job_id>` (instante do disparo, validade 10 min). Regras:
 *  - sem conseguir persistir a marca (storage lança/bloqueado) NÃO há autoenvio;
 *  - o submit manual é capturado já no carregamento do script e sempre vence;
 *  - o campo `extrair_auto=1` (critério do servidor p/ `somente_se_inexistente`)
 *    NÃO está no HTML: é injetado só no disparo automático — o clique manual
 *    nunca o carrega e continua podendo reextrair (PR #319, tarefa 2);
 *  - o bloco de progresso nasce `hidden` e só aparece quando o envio sai;
 *  - voltar pelo histórico (bfcache) não deixa spinner preso nem marca residual.
 * Testes em Node: ia_ocr/tests/js/ocr_auto_extrair.test.js.
 */
(function () {
    'use strict';

    var VALIDADE_MS = 10 * 60 * 1000;
    var PREFIXO = 'ocr-auto-extrair:';
    var MSG_PREPARANDO = 'Preparando o formulário com os campos reconhecidos…';
    var MSG_DEMORA = 'Uma extração pode ter sido iniciada há pouco. Se o formulário não abrir, clique em Extrair campos.';
    var MSG_ESTATICO = 'Clique em Extrair campos para continuar.';

    var travado = false;          // manual ou automático já ocorreu nesta página
    var desabilitouBotao = false; // fomos nós que desabilitamos o botão
    var marcaAuto = null;         // input `extrair_auto` injetado no disparo

    function chaveDe(form) {
        return PREFIXO + (form.getAttribute('data-ocr-auto-extrair-job') || '');
    }

    function ehFormAuto(el) {
        return !!(el && el.getAttribute && el.getAttribute('data-ocr-auto-extrair') !== null);
    }

    // Devolve o valor lido ou `undefined` se o storage não está acessível.
    function lerStorage(chave) {
        try { return window.sessionStorage.getItem(chave); } catch (e) { return undefined; }
    }

    // true só se a marca ficou realmente persistida.
    function gravarStorage(chave) {
        var valor = String(Date.now());
        try {
            window.sessionStorage.setItem(chave, valor);
            return window.sessionStorage.getItem(chave) === valor;
        } catch (e) {
            return false;
        }
    }

    function marcaRecente(chave) {
        var valor = parseInt(lerStorage(chave), 10);
        return !isNaN(valor) && Date.now() - valor < VALIDADE_MS;
    }

    function partes(form) {
        return {
            botao: form.querySelector('[data-ocr-extrair-campos]'),
            aviso: form.querySelector('[data-ocr-auto-extrair-aviso]'),
            progresso: form.querySelector('[data-ocr-auto-extrair-progresso]'),
        };
    }

    // PR #319 tarefa 2: a marca de auto-extração não vive no HTML do form —
    // se vivesse, o clique manual do mesmo form a carregaria e deixaria de
    // reextrair ("Os campos já foram extraídos."). Ela entra aqui, só no
    // disparo automático, imediatamente antes do submit.
    function marcarAuto(form) {
        if (marcaAuto) return;
        marcaAuto = document.createElement('input');
        marcaAuto.type = 'hidden';
        marcaAuto.name = 'extrair_auto';
        marcaAuto.value = '1';
        form.appendChild(marcaAuto);
    }

    // A página restaurada pelo bfcache ainda teria o input injetado: sem
    // removê-lo, o clique manual seguinte herdaria o flag de automático.
    function desmarcarAuto(form) {
        if (marcaAuto && marcaAuto.parentNode === form) form.removeChild(marcaAuto);
        marcaAuto = null;
    }

    // Captura imediata: um submit manual (antes ou depois do DOMContentLoaded)
    // trava o automático e grava a marca para os reloads seguintes.
    document.addEventListener('submit', function (ev) {
        var form = ev && ev.target;
        if (!ehFormAuto(form)) return;
        travado = true;
        gravarStorage(chaveDe(form));
    }, true);

    function iniciar(form) {
        var p = partes(form);
        var chave = chaveDe(form);

        function avisar(texto) { if (p.aviso) p.aviso.textContent = texto; }

        if (travado) return; // submit manual já saiu
        if (lerStorage(chave) === undefined) { avisar(MSG_ESTATICO); return; }
        if (marcaRecente(chave)) { travado = true; avisar(MSG_DEMORA); return; }
        // Botão desabilitado (texto editado e não salvo, p.ex.): não força.
        if (!p.botao || p.botao.disabled) { avisar(MSG_ESTATICO); return; }
        // Sem persistir a marca um reload reenviaria em loop: fica manual.
        if (!gravarStorage(chave)) { avisar(MSG_ESTATICO); return; }

        travado = true;
        p.botao.disabled = true;
        desabilitouBotao = true;
        if (p.progresso) p.progresso.hidden = false;
        avisar(MSG_PREPARANDO);
        marcarAuto(form);
        form.submit();
    }

    function restaurar(form) {
        var p = partes(form);
        desmarcarAuto(form);
        if (p.progresso) p.progresso.hidden = true;
        if (p.botao && desabilitouBotao) {
            p.botao.disabled = false;
            desabilitouBotao = false;
        }
        if (p.aviso) p.aviso.textContent = travado || marcaRecente(chaveDe(form)) ? MSG_DEMORA : '';
    }

    document.addEventListener('DOMContentLoaded', function () {
        var form = document.querySelector('[data-ocr-auto-extrair]');
        if (form) iniciar(form);
    });

    window.addEventListener('pageshow', function (ev) {
        if (!ev || !ev.persisted) return;
        var form = document.querySelector('[data-ocr-auto-extrair]');
        if (form) restaurar(form);
    });
}());
