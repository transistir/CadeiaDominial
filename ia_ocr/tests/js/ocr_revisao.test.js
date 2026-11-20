/**
 * Testes do "Finalizar revisão sem atos" (static/dominial/js/ocr_revisao.js,
 * issue #262 / I-5).
 *
 * Node puro, sem dependências novas: o JS é lido com fs.readFileSync e
 * avaliado com vm.runInNewContext num sandbox com DOM/fetch/timers mockados à
 * mão (mesmo padrão de ocr_card.test.js). Cobre só o modo atrás da flag
 * OCR_PERMITIR_FINALIZAR_SEM_ATOS:
 *
 * - o botão só habilita com o checkbox de confirmação marcado;
 * - o contador continua mostrando 1 pendência (a pendência não é escondida);
 * - o corpo do POST inclui ``sem_atos: true`` só quando o checkbox está
 *   marcado; sem o modo, o corpo continua igual ao de hoje.
 *
 * Também cobre (#324, PR #343) o redesenho dos avisos depois do save: lista,
 * contagem do cabeçalho e selos "não consta no documento" vêm da resposta.
 *
 * Harness em ocr_revisao_harness.js; casos em ocr_revisao_casos_parte*.js.
 * Uso: node ia_ocr/tests/js/ocr_revisao.test.js   (exit 1 se algum caso falhar)
 */
'use strict';

const { casos } = require('./ocr_revisao_harness');
require('./ocr_revisao_casos_parte1');
require('./ocr_revisao_casos_parte2');

(async () => {
  let falhas = 0;
  for (const item of casos) {
    try {
      await item.fn();
      console.log('ok - ' + item.nome);
    } catch (erro) {
      falhas += 1;
      console.error('FALHOU - ' + item.nome);
      console.error('  ' + (erro && erro.message ? erro.message : erro));
    }
  }
  if (falhas) {
    console.error('\n' + falhas + ' caso(s) falharam');
    process.exit(1);
  }
  console.log('\n' + casos.length + ' caso(s) passaram');
})();
