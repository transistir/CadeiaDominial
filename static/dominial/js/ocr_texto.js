/**
 * Tela de confirmação do texto OCR (templates/ia_ocr/confirmacao_texto.html,
 * issue #261 / I-4): protege a edição do textarea que ainda não foi salva.
 *
 * Com o texto alterado: mostra "Alterações não salvas", desabilita as ações
 * gerais (Confirmar todas / Reprocessar / Extrair campos — elas ignoram o
 * textarea e recarregam a página) e avisa antes de sair da página. Ao voltar
 * ao texto original, ou ao enviar o formulário (Salvar edição / Confirmar
 * página), tudo volta ao que o servidor renderizou. Testes em Node:
 * ia_ocr/tests/js/ocr_texto.test.js.
 */
(function () {
    'use strict';

    function iniciar(area, form) {
        var aviso = document.querySelector('[data-ocr-nao-salvo]');
        var acoes = Array.prototype.slice.call(
            document.querySelectorAll('[data-ocr-acao-global]')
        );
        // O que o servidor já desabilitou (ex.: "Extrair campos" com páginas
        // pendentes) continua assim mesmo sem edição pendente.
        var desabilitadoNoServidor = acoes.map(function (botao) {
            return !!botao.disabled;
        });
        var enviando = false;

        // defaultValue é o texto renderizado pelo servidor; o navegador pode
        // restaurar uma edição antiga ao reabrir a página, e isso já conta.
        function alterado() {
            return area.value !== area.defaultValue;
        }

        function atualizar() {
            var sujo = alterado();
            if (aviso) aviso.hidden = !sujo;
            acoes.forEach(function (botao, indice) {
                botao.disabled = sujo || desabilitadoNoServidor[indice];
            });
        }

        area.addEventListener('input', atualizar);
        form.addEventListener('submit', function () {
            enviando = true;
        });
        window.addEventListener('beforeunload', function (evento) {
            if (!alterado() || enviando) return undefined;
            evento.preventDefault();
            evento.returnValue = '';
            return '';
        });
        atualizar();
    }

    document.addEventListener('DOMContentLoaded', function () {
        var area = document.querySelector('[data-ocr-texto-area]');
        var form = document.querySelector('[data-ocr-texto-form]');
        if (area && form) iniciar(area, form);
    });
})();
