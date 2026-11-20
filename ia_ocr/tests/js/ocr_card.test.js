'use strict';

const { CAMINHO_JS, casos } = require('./ocr_card_harness');
require('./ocr_card_casos_parte1');
require('./ocr_card_casos_parte2');
require('./ocr_card_casos_parte3');

// ---------- runner ----------

(async function rodar() {
  let falhas = 0;
  for (const c of casos) {
    try {
      await c.fn();
      console.log('  OK      ' + c.nome);
    } catch (e) {
      falhas++;
      console.log('  FALHOU  ' + c.nome);
      console.log('          ' + (e && e.message));
    }
  }
  console.log('');
  console.log('resumo: ' + (casos.length - falhas) + '/' + casos.length + ' casos OK — ' + CAMINHO_JS);
  if (falhas) process.exit(1);
})();
