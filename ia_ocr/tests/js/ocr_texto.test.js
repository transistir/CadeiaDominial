/**
 * Testes do JS da tela de confirmação do texto OCR
 * (static/dominial/js/ocr_texto.js, issue #261 / I-4).
 *
 * Node puro, sem dependências novas, no mesmo estilo de ocr_card.test.js: o JS
 * é lido com fs.readFileSync e avaliado com vm.runInNewContext num sandbox com
 * DOM mínimo mockado à mão.
 *
 * Uso: node ia_ocr/tests/js/ocr_texto.test.js   (exit 1 se algum caso falhar)
 */
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const CAMINHO_JS = path.resolve(__dirname, '..', '..', '..', 'static', 'dominial', 'js', 'ocr_texto.js');

function afirmar(condicao, mensagem) {
  if (!condicao) throw new Error(mensagem);
}

function afirmarIgual(atual, esperado, mensagem) {
  afirmar(
    atual === esperado,
    mensagem + ' (esperado=' + JSON.stringify(esperado) + ', atual=' + JSON.stringify(atual) + ')'
  );
}

// ---------- DOM mínimo: elementos com listeners, seletor [atributo] ----------

function criarElemento(atributo, propriedades) {
  const el = Object.assign(
    {
      atributo: atributo,
      hidden: false,
      disabled: false,
      listeners: {},
      addEventListener(evento, fn) {
        (this.listeners[evento] = this.listeners[evento] || []).push(fn);
      },
      emitir(evento, objeto) {
        const e = objeto || { preventDefault() { this.padraoPrevenido = true; } };
        (this.listeners[evento] || []).forEach((fn) => fn(e));
        return e;
      },
    },
    propriedades || {}
  );
  return el;
}

function criarTela(opcoes) {
  const op = opcoes || {};
  const area = criarElemento('[data-ocr-texto-area]', {
    defaultValue: 'texto do OCR',
    value: op.valorInicial !== undefined ? op.valorInicial : 'texto do OCR',
  });
  const form = criarElemento('[data-ocr-texto-form]');
  const aviso = criarElemento('[data-ocr-nao-salvo]', { hidden: true });
  // O servidor pode já ter desabilitado ações (ex.: "Extrair campos" com pendentes).
  const confirmarTodas = criarElemento('[data-ocr-acao-global]', { id: 'todas' });
  const reprocessar = criarElemento('[data-ocr-acao-global]', { id: 'reprocessar' });
  const extrair = criarElemento('[data-ocr-acao-global]', { id: 'extrair', disabled: true });
  const acoes = [confirmarTodas, reprocessar, extrair];
  const elementos = [area, form, aviso].concat(acoes);

  const listenersJanela = {};
  const documento = criarElemento('document');
  documento.querySelector = function (seletor) {
    return op.semFormulario && seletor !== '[data-ocr-nao-salvo]'
      ? null
      : elementos.find((el) => el.atributo === seletor) || null;
  };
  documento.querySelectorAll = function (seletor) {
    return elementos.filter((el) => el.atributo === seletor);
  };
  const janela = {
    addEventListener(evento, fn) {
      (listenersJanela[evento] = listenersJanela[evento] || []).push(fn);
    },
  };

  const sandbox = { document: documento, window: janela };
  vm.runInNewContext(fs.readFileSync(CAMINHO_JS, 'utf8'), sandbox, { filename: 'ocr_texto.js' });
  documento.emitir('DOMContentLoaded');

  return {
    area, form, aviso, acoes, confirmarTodas, reprocessar, extrair,
    sairDaPagina() {
      const e = { padraoPrevenido: false, preventDefault() { this.padraoPrevenido = true; } };
      (listenersJanela.beforeunload || []).forEach((fn) => fn(e));
      return e;
    },
  };
}

function digitar(tela, texto) {
  tela.area.value = texto;
  tela.area.emitir('input');
}

// ---------- casos ----------

const casos = [];

function caso(nome, fn) {
  casos.push({ nome: nome, fn: fn });
}

caso('texto inalterado: sem aviso, ações como o servidor deixou e sair sem prompt', () => {
  const tela = criarTela();
  afirmarIgual(tela.aviso.hidden, true, 'aviso de alterações escondido');
  afirmarIgual(tela.confirmarTodas.disabled, false, 'Confirmar todas segue habilitado');
  afirmarIgual(tela.reprocessar.disabled, false, 'Reprocessar segue habilitado');
  afirmarIgual(tela.extrair.disabled, true, 'Extrair campos segue desabilitado pelo servidor');
  afirmarIgual(tela.sairDaPagina().padraoPrevenido, false, 'sair da página não pede confirmação');
});

caso('digitar: mostra o aviso, desabilita as ações gerais e pede confirmação ao sair', () => {
  const tela = criarTela();
  digitar(tela, 'texto do OCR corrigido');
  afirmarIgual(tela.aviso.hidden, false, 'aviso "Alterações não salvas" aparece');
  tela.acoes.forEach((botao) => afirmarIgual(botao.disabled, true, 'ação geral ' + botao.id + ' desabilitada com edição pendente'));
  afirmarIgual(tela.sairDaPagina().padraoPrevenido, true, 'sair da página com edição não salva pede confirmação');
});

caso('voltar ao texto original: libera o que o servidor liberou e mantém o que ele bloqueou', () => {
  const tela = criarTela();
  digitar(tela, 'texto do OCR corrigido');
  digitar(tela, 'texto do OCR');
  afirmarIgual(tela.aviso.hidden, true, 'aviso some quando o texto volta ao original');
  afirmarIgual(tela.confirmarTodas.disabled, false, 'Confirmar todas volta a habilitar');
  afirmarIgual(tela.reprocessar.disabled, false, 'Reprocessar volta a habilitar');
  afirmarIgual(tela.extrair.disabled, true, 'Extrair campos continua desabilitado pelo servidor');
  afirmarIgual(tela.sairDaPagina().padraoPrevenido, false, 'sem edição, sair não pede confirmação');
});

caso('enviar o formulário (Salvar edição / Confirmar página) não dispara o prompt de saída', () => {
  const tela = criarTela();
  digitar(tela, 'texto do OCR corrigido');
  tela.form.emitir('submit');
  afirmarIgual(tela.sairDaPagina().padraoPrevenido, false, 'salvar não pode pedir confirmação para sair');
});

caso('página reaberta com texto restaurado pelo navegador já nasce com aviso', () => {
  const tela = criarTela({ valorInicial: 'texto restaurado e alterado' });
  afirmarIgual(tela.aviso.hidden, false, 'aviso visível desde o carregamento');
  afirmarIgual(tela.confirmarTodas.disabled, true, 'ações gerais desabilitadas desde o carregamento');
  afirmarIgual(tela.sairDaPagina().padraoPrevenido, true, 'sair pede confirmação');
});

caso('sem o formulário (texto somente leitura): o script não quebra nem registra nada', () => {
  const tela = criarTela({ semFormulario: true });
  afirmarIgual(tela.sairDaPagina().padraoPrevenido, false, 'sem textarea editável, sair não pede confirmação');
  afirmarIgual(tela.confirmarTodas.disabled, false, 'ações não são mexidas');
});

// ---------- runner ----------

let falhas = 0;
for (const c of casos) {
  try {
    c.fn();
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
