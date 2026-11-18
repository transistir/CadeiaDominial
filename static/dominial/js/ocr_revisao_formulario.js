/**
 * Revisão da extração dentro do formulário de lançamento (I-14 / #341).
 *
 * Carregado SÓ na tela de revisão, depois de lancamento_form.js e
 * origem_simples.js — que continuam intocados e valendo para o formulário
 * manual. Faz três coisas, todas aditivas:
 *
 * 1. Evidência por campo: lê o JSON de #ia-evidencias ({input: {pagina,
 *    trecho, confianca_baixa}}) e põe um selo "p. N" ao lado do input; o
 *    clique abre o trecho lido (já mascarado pelo servidor) e o link da página.
 * 2. Navegação entre atos sem perder a digitação: o clique numa aba pendente
 *    envia o formulário com `_ir_para`, e o servidor guarda o rascunho na
 *    sessão. Sem JS a aba é um link comum (GET).
 * 3. Número da origem com ponto de milhar ("42.718"): o formulário manual só
 *    aceita dígitos e, ao carregar, reduzia "M42.718" a "42" no campo
 *    visível. Aqui o campo volta a mostrar o número inteiro e, ao digitar, o
 *    ponto é devolvido depois do filtro do formulário manual (que segue
 *    rodando) — só nesta tela.
 */
(function () {
    'use strict';

    var ORIGEM_COMPLETA = /^[MT](\d+(?:\.\d+)*)$/;
    var NOME_DE_INPUT = /^[a-z_]+(?:\[\d+\])?$/;

    function lerEvidencias(doc) {
        var no = doc.getElementById('ia-evidencias');
        if (!no) return {};
        try {
            var dados = JSON.parse(no.textContent);
            return dados && typeof dados === 'object' ? dados : {};
        } catch (erro) {
            return {};
        }
    }

    // --- 3. Número da origem com ponto ------------------------------------

    function restaurarNumerosDeOrigem(doc) {
        var itens = doc.querySelectorAll('.origem-item');
        for (var i = 0; i < itens.length; i++) {
            var oculto = itens[i].querySelector('input[name="origem_completa[]"]');
            var numero = itens[i].querySelector('.origem-numero-input');
            if (!oculto || !numero) continue;
            var achado = ORIGEM_COMPLETA.exec((oculto.value || '').trim());
            if (achado && numero.value !== achado[1]) numero.value = achado[1];
        }
    }

    function ehNumeroDeOrigem(alvo) {
        return !!(alvo && alvo.classList && alvo.classList.contains('origem-numero-input'));
    }

    // Os handlers do formulário manual continuam rodando (o filtro "só
    // dígitos" e a validação do início de matrícula, no próprio input): o
    // que muda é o resultado. Na captura guardo o que foi digitado, já
    // limpo de tudo que não é dígito ou ponto; na bolha — depois do filtro
    // manual ter tirado o ponto — devolvo esse texto e reconstruo o texto
    // oculto da origem.
    function lembrarDigitacaoDaOrigem(evento) {
        var alvo = evento.target;
        if (ehNumeroDeOrigem(alvo)) {
            alvo.iaDigitado = String(alvo.value).replace(/[^0-9.]/g, '');
        }
    }

    function reaplicarDigitacaoDaOrigem(evento, janela) {
        var alvo = evento.target;
        if (!ehNumeroDeOrigem(alvo) || typeof alvo.iaDigitado !== 'string') return;
        var digitado = alvo.iaDigitado;
        alvo.iaDigitado = undefined;
        if (alvo.value !== digitado) alvo.value = digitado;
        var indice = /_(\d+)$/.exec(alvo.id || '');
        if (indice && typeof janela.atualizarOrigemCompleta === 'function') {
            janela.atualizarOrigemCompleta(parseInt(indice[1], 10));
        }
    }

    // --- 1. Evidência por campo -------------------------------------------

    function camposDoInput(form, nome) {
        if (!NOME_DE_INPUT.test(nome)) return [];
        var posicao = /^(.*)\[(\d+)\]$/.exec(nome);
        if (posicao) {
            var lista = form.querySelectorAll('[name="' + posicao[1] + '[]"]');
            var campo = lista[parseInt(posicao[2], 10)];
            return campo ? [campo] : [];
        }
        // O `area` do POST é o hidden preenchido no envio; quem o usuário vê
        // são os campos area_<id> de cada seção.
        var seletor = nome === 'area' ? '[name^="area_area_"]' : '[name="' + nome + '"]';
        return Array.prototype.slice.call(form.querySelectorAll(seletor));
    }

    function criarSelo(doc, info, urlTexto) {
        var selo = doc.createElement('button');
        selo.type = 'button';
        selo.className = 'ia-evidencia-selo' + (info.confianca_baixa ? ' ia-evidencia-baixa' : '');
        selo.textContent = info.pagina ? 'p. ' + info.pagina : 'trecho';
        selo.title = info.confianca_baixa
            ? 'Leitura de baixa confiança — confira este valor'
            : 'De onde este valor foi lido';
        selo.setAttribute('aria-expanded', 'false');

        var detalhe = doc.createElement('span');
        detalhe.className = 'ia-evidencia-detalhe';
        detalhe.hidden = true;
        if (info.trecho) {
            var trecho = doc.createElement('q');
            trecho.textContent = info.trecho;  // textContent: nada vira HTML
            detalhe.appendChild(trecho);
        }
        if (info.pagina && urlTexto) {
            var link = doc.createElement('a');
            link.href = urlTexto + '?pagina=' + encodeURIComponent(info.pagina);
            link.target = '_blank';
            link.rel = 'noopener';
            link.textContent = ' ver a página ' + info.pagina;
            detalhe.appendChild(link);
        }

        selo.addEventListener('click', function () {
            var aberto = detalhe.hidden;
            detalhe.hidden = !aberto;
            selo.setAttribute('aria-expanded', aberto ? 'true' : 'false');
        });
        return { selo: selo, detalhe: detalhe };
    }

    function anexarEvidencias(doc, form, evidencias, urlTexto) {
        Object.keys(evidencias).forEach(function (nome) {
            camposDoInput(form, nome).forEach(function (campo) {
                var par = criarSelo(doc, evidencias[nome], urlTexto);
                var pai = campo.parentNode;
                pai.insertBefore(par.selo, campo.nextSibling);
                pai.insertBefore(par.detalhe, par.selo.nextSibling);
                campo.addEventListener('focus', function () {
                    par.selo.classList.add('ia-evidencia-foco');
                });
                campo.addEventListener('blur', function () {
                    par.selo.classList.remove('ia-evidencia-foco');
                });
            });
        });
    }

    // --- 2. Navegação entre atos ------------------------------------------

    function navegarPara(doc, janela, form, indice) {
        var campo = form.querySelector('input[name="_ir_para"]');
        if (!campo) {
            campo = doc.createElement('input');
            campo.type = 'hidden';
            campo.name = '_ir_para';
            form.appendChild(campo);
        }
        campo.value = String(indice);
        // Os handlers de envio do formulário manual copiam a área para o
        // hidden `area` (precisa rodar) e validam campo obrigatório (não
        // pode barrar a navegação, nem abrir alert): dispara o evento só
        // para eles rodarem e envia por form.submit(), que ignora o resultado.
        var alertaOriginal = janela.alert;
        janela.alert = function () {};
        try {
            form.dispatchEvent(new janela.Event('submit', { bubbles: true, cancelable: true }));
        } finally {
            janela.alert = alertaOriginal;
        }
        form.submit();
    }

    function ligarAbas(doc, janela, form) {
        var abas = doc.querySelectorAll('a[data-ir-para]');
        for (var i = 0; i < abas.length; i++) {
            (function (aba) {
                aba.addEventListener('click', function (evento) {
                    // Ctrl/Cmd/Shift/botão do meio: o navegador abre em outra aba (GET).
                    if (evento.button || evento.metaKey || evento.ctrlKey || evento.shiftKey) return;
                    evento.preventDefault();
                    navegarPara(doc, janela, form, aba.getAttribute('data-ir-para'));
                });
            })(abas[i]);
        }
    }

    function iniciar(doc, janela) {
        var form = doc.getElementById('lancamento-form');
        if (!form) return;
        var banner = doc.getElementById('ia-revisao-banner');
        var urlTexto = banner ? banner.getAttribute('data-url-texto') : '';
        restaurarNumerosDeOrigem(doc);
        doc.addEventListener('input', lembrarDigitacaoDaOrigem, true);
        doc.addEventListener('input', function (evento) {
            reaplicarDigitacaoDaOrigem(evento, janela);
        }, false);
        anexarEvidencias(doc, form, lerEvidencias(doc), urlTexto);
        ligarAbas(doc, janela, form);
    }

    var api = {
        iniciar: iniciar,
        restaurarNumerosDeOrigem: restaurarNumerosDeOrigem,
        lembrarDigitacaoDaOrigem: lembrarDigitacaoDaOrigem,
        reaplicarDigitacaoDaOrigem: reaplicarDigitacaoDaOrigem,
        camposDoInput: camposDoInput,
        anexarEvidencias: anexarEvidencias,
        navegarPara: navegarPara,
    };
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    if (typeof window !== 'undefined') {
        window.OcrRevisaoFormulario = api;
        // Depois do DOMContentLoaded do origem_simples.js (registrado antes
        // deste script): é ele que reduz "M42.718" a "42" no campo visível, e
        // a restauração tem que vir por cima.
        var naPagina = function () { iniciar(document, window); };
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', naPagina);
        } else {
            naPagina();
        }
    }
})();
