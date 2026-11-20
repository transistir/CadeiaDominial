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
