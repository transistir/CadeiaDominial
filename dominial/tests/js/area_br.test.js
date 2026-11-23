// #396 — espelho JS da regra do backend (dominial/utils/area_br.py).
// Não converte valor: só descreve o problema para o usuário antes do submit.
const assert = require('node:assert');
const { problemaAreaPtBr } = require('../../../static/dominial/js/area_br.js');

function ok(valor, rotulo) {
  assert.strictEqual(problemaAreaPtBr(valor), '', rotulo + ': ' + valor);
}

function erro(valor, trecho, rotulo) {
  const msg = problemaAreaPtBr(valor);
  assert.ok(msg, rotulo + ': esperava erro para ' + valor);
  assert.ok(
    msg.toLowerCase().includes(trecho.toLowerCase()),
    rotulo + ': "' + msg + '" não contém "' + trecho + '"',
  );
}

ok('', 'vazio');
ok('   ', 'só espaço');
ok('150,5', 'vírgula decimal');
ok('150.5', 'ponto decimal');
ok('74.6755', 'canônico da revisão OCR');
ok('1.234,5678', 'milhar com vírgula');
ok('1234,5678', 'sem milhar');
ok('1.234.567', 'dois pontos');
ok('1,2345', 'quatro casas com vírgula');
ok('1.2345', 'quatro casas com ponto');
ok('0', 'zero');
ok('0.012', 'zero à esquerda não é milhar');
ok('0,012', 'idem com vírgula');

erro('1.000', 'ambígua', 'ponto + 3 casas');
erro('1,000', 'ambígua', 'vírgula + 3 casas');
erro('12.345', 'ambígua', 'dois dígitos + 3 casas');
erro('150,500', 'ambígua', '150,500');
erro('1.000', '1000', 'mensagem traz a leitura de milhar');
erro('1.000', '1.0000', 'mensagem traz a leitura decimal');

erro('abc', 'números', 'texto');
erro('-1', 'números', 'negativo');
erro(',5', 'parte inteira', 'sem parte inteira');
erro('1 2', 'espaços', 'espaço interno');
erro('1..2', 'milhar', 'dois pontos inválidos');
erro('1,2,3', 'vírgula', 'duas vírgulas');
erro('1,23456', '4 casas', 'cinco casas');
erro('1,234.56', 'ponto depois da vírgula', 'convenção en-US');
erro('123456789', 'limite', '9 dígitos inteiros (limite da coluna)');
erro('1.234.567.890', 'limite', 'milhar acima de 8 dígitos');

console.log('area_br.test.js: OK');
