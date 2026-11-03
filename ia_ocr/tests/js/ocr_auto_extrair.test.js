/**
 * Testes da extração automática (static/dominial/js/ocr_auto_extrair.js,
 * issue #314). Node puro: o JS é avaliado com vm.runInNewContext num sandbox
 * com DOM/sessionStorage mockados (mesmo padrão de ocr_revisao.test.js).
 *
 * Uso: node ia_ocr/tests/js/ocr_auto_extrair.test.js   (exit 1 se falhar)
 */
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const CAMINHO_JS = path.resolve(
  __dirname, '..', '..', '..', 'static', 'dominial', 'js', 'ocr_auto_extrair.js'
);

function afirmar(condicao, mensagem) {
  if (!condicao) throw new Error(mensagem);
}

function afirmarIgual(atual, esperado, mensagem) {
  afirmar(
    atual === esperado,
    mensagem + ' (esperado=' + JSON.stringify(esperado) + ', atual=' + JSON.stringify(atual) + ')'
  );
}

function criarElemento(atributos) {
  return {
    attributes: Object.assign({}, atributos || {}),
    disabled: false,
    textContent: '',
    getAttribute(nome) {
      return Object.prototype.hasOwnProperty.call(this.attributes, nome) ? this.attributes[nome] : null;
    },
  };
}

function criarStorage(inicial) {
  const dados = Object.assign({}, inicial || {});
  return {
    dados,
    getItem(chave) { return Object.prototype.hasOwnProperty.call(dados, chave) ? dados[chave] : null; },
    setItem(chave, valor) { dados[chave] = String(valor); },
  };
}

// Inputs injetados pelo JS no form (mesmo padrão de ocr_revisao.test.js).
function marcasNoForm(form) {
  return (form.filhos || []).filter((el) => el.name === 'extrair_auto');
}

// opcoes: { storage, comMarca (default true), botaoDesabilitado, adiarInicio }
// Com adiarInicio o script carrega mas DOMContentLoaded só dispara em c.iniciar().
function criarCenario(opcoes) {
  opcoes = opcoes || {};
  const storage = opcoes.storage || criarStorage();
  const envios = [];
  const form = criarElemento(
    opcoes.comMarca === false ? {} : { 'data-ocr-auto-extrair': '', 'data-ocr-auto-extrair-job': 'job-1' }
  );
  const botao = criarElemento({ 'data-ocr-extrair-campos': '' });
  botao.disabled = !!opcoes.botaoDesabilitado;
  const progresso = criarElemento({ 'data-ocr-auto-extrair-progresso': '' });
  progresso.hidden = true;
  const aviso = criarElemento({
    'data-ocr-auto-extrair-aviso': '', role: 'status', 'aria-live': 'polite',
  });
  form.filhos = [];
  form.appendChild = (filho) => { filho.parentNode = form; form.filhos.push(filho); return filho; };
  form.removeChild = (filho) => {
    const i = form.filhos.indexOf(filho);
    if (i !== -1) form.filhos.splice(i, 1);
    filho.parentNode = null;
    return filho;
  };
  form.submit = () => { envios.push('auto'); };
  form.querySelector = (sel) => {
    if (sel === '[data-ocr-extrair-campos]') return botao;
    if (sel === '[data-ocr-auto-extrair-aviso]') return aviso;
    if (sel === '[data-ocr-auto-extrair-progresso]') return progresso;
    return null;
  };
  const docOuvintes = {};
  const winOuvintes = {};
  const sandbox = {
    console,
    Date,
    parseInt,
    isNaN,
    String,
    document: {
      addEventListener(evento, fn) { (docOuvintes[evento] = docOuvintes[evento] || []).push(fn); },
      createElement(nome) { return criarElemento({}); },
      querySelector(sel) {
        return sel === '[data-ocr-auto-extrair]' && opcoes.comMarca !== false ? form : null;
      },
    },
    window: {
      sessionStorage: storage,
      addEventListener(evento, fn) { (winOuvintes[evento] = winOuvintes[evento] || []).push(fn); },
    },
  };
  sandbox.window.window = sandbox.window;
  vm.runInNewContext(fs.readFileSync(CAMINHO_JS, 'utf8'), sandbox, { filename: CAMINHO_JS });
  const cenario = {
    form, botao, aviso, progresso, storage, envios,
    iniciar() { (docOuvintes.DOMContentLoaded || []).forEach((fn) => fn()); },
    cliqueManual() {
      envios.push('manual');
      (docOuvintes.submit || []).forEach((fn) => fn({ target: form }));
    },
    pageshow(persisted) {
      (winOuvintes.pageshow || []).forEach((fn) => fn({ persisted }));
    },
  };
  if (!opcoes.adiarInicio) cenario.iniciar();
  return cenario;
}

const casos = [];
function caso(nome, fn) { casos.push({ nome, fn }); }

caso('primeiro load submete uma vez, desabilita o botão e grava a chave', () => {
  const c = criarCenario();
  afirmarIgual(c.envios.length, 1, 'deve submeter exatamente uma vez');
  afirmarIgual(c.botao.disabled, true, 'botão deve ficar desabilitado');
  afirmar('ocr-auto-extrair:job-1' in c.storage.dados, 'deve gravar a chave por job');
});

caso('segundo load com a chave recente não submete e orienta o fallback', () => {
  const c = criarCenario({ storage: criarStorage({ 'ocr-auto-extrair:job-1': String(Date.now()) }) });
  afirmarIgual(c.envios.length, 0, 'não pode reenviar');
  afirmarIgual(c.botao.disabled, false, 'botão manual segue disponível');
  afirmar(c.aviso.textContent.indexOf('clique em Extrair campos') !== -1, 'aviso deve orientar o clique');
});

caso('chave expirada (>10 min) permite novo disparo', () => {
  const velha = String(Date.now() - 11 * 60 * 1000);
  const c = criarCenario({ storage: criarStorage({ 'ocr-auto-extrair:job-1': velha }) });
  afirmarIgual(c.envios.length, 1, 'chave vencida deve disparar de novo');
});

caso('chave de outro job não bloqueia', () => {
  const c = criarCenario({ storage: criarStorage({ 'ocr-auto-extrair:outro': String(Date.now()) }) });
  afirmarIgual(c.envios.length, 1, 'outro job não interfere');
});

caso('clique manual marca a chave e não gera segundo envio no reload', () => {
  const c = criarCenario({ botaoDesabilitado: true });
  afirmarIgual(c.envios.length, 0, 'botão desabilitado: sem auto-envio');
  c.cliqueManual();
  afirmar('ocr-auto-extrair:job-1' in c.storage.dados, 'clique manual deve gravar a chave');
  const recarregado = criarCenario({ storage: c.storage });
  afirmarIgual(recarregado.envios.length, 0, 'reload após o clique não reenvia');
});

caso('botão desabilitado pelo servidor/edição não é forçado', () => {
  const c = criarCenario({ botaoDesabilitado: true });
  afirmarIgual(c.envios.length, 0, 'não pode submeter');
  afirmarIgual(Object.keys(c.storage.dados).length, 0, 'não grava a chave sem disparar');
});

caso('sem a marca data-ocr-auto-extrair nada acontece', () => {
  const c = criarCenario({ comMarca: false });
  afirmarIgual(c.envios.length, 0, 'sem marca, sem envio');
});

caso('aviso é região viva polida e nasce vazia', () => {
  const c = criarCenario({ adiarInicio: true });
  afirmarIgual(c.aviso.getAttribute('aria-live'), 'polite', 'aria-live=polite');
  afirmarIgual(c.aviso.textContent, '', 'região viva vazia até o disparo');
});

caso('clique manual antes de DOMContentLoaded impede o envio automático', () => {
  const c = criarCenario({ adiarInicio: true });
  c.cliqueManual();
  c.iniciar();
  afirmarIgual(c.envios.join(','), 'manual', 'só o manual; nenhum POST automático');
  afirmar('ocr-auto-extrair:job-1' in c.storage.dados, 'manual grava a chave');
});

caso('sessionStorage que lança: sem autoenvio e aviso estático', () => {
  const lancando = {
    getItem() { throw new Error('bloqueado'); },
    setItem() { throw new Error('quota'); },
  };
  const c = criarCenario({ storage: lancando });
  afirmarIgual(c.envios.length, 0, 'sem persistir a marca não há autoenvio');
  afirmarIgual(c.botao.disabled, false, 'botão manual segue habilitado');
  afirmarIgual(c.progresso.hidden, true, 'progresso segue escondido');
  afirmar(c.aviso.textContent.indexOf('Clique em Extrair campos') !== -1, 'aviso estático');
});

caso('setItem que lança (leitura ok): sem autoenvio', () => {
  const st = criarStorage();
  st.setItem = () => { throw new Error('quota'); };
  const c = criarCenario({ storage: st });
  afirmarIgual(c.envios.length, 0, 'não persiste, não envia');
  afirmarIgual(c.progresso.hidden, true, 'progresso escondido');
});

caso('progresso começa hidden e só aparece no disparo', () => {
  const c = criarCenario({ adiarInicio: true });
  afirmarIgual(c.progresso.hidden, true, 'hidden antes do disparo');
  c.iniciar();
  afirmarIgual(c.progresso.hidden, false, 'visível ao submeter');
  afirmar(c.aviso.textContent.length > 0, 'texto inserido via JS no disparo');
});

caso('envio pulado (botão desabilitado) mantém progresso hidden', () => {
  const c = criarCenario({ botaoDesabilitado: true });
  afirmarIgual(c.progresso.hidden, true, 'segue hidden');
  afirmar(c.aviso.textContent.indexOf('Clique em Extrair campos') !== -1, 'mensagem estática');
});

caso('já disparado mantém progresso hidden', () => {
  const c = criarCenario({ storage: criarStorage({ 'ocr-auto-extrair:job-1': String(Date.now()) }) });
  afirmarIgual(c.progresso.hidden, true, 'segue hidden');
});

caso('pageshow persisted não deixa spinner preso', () => {
  const c = criarCenario();
  afirmarIgual(c.progresso.hidden, false, 'spinner visível após o disparo');
  c.pageshow(true);
  afirmarIgual(c.progresso.hidden, true, 'spinner escondido na restauração');
  afirmarIgual(c.botao.disabled, false, 'botão volta a habilitar');
  afirmar(c.aviso.textContent.indexOf('clique em Extrair campos') !== -1, 'aviso de demora');
  c.pageshow(false);
});

caso('disparo automático anexa extrair_auto=1 ao form', () => {
  // PR #319 tarefa 2: a marca não está no HTML — entra só aqui, no autoenvio.
  const c = criarCenario();
  const marcas = marcasNoForm(c.form);
  afirmarIgual(marcas.length, 1, 'exatamente uma marca no form');
  afirmarIgual(marcas[0].value, '1', 'valor da marca');
  afirmarIgual(marcas[0].type, 'hidden', 'campo escondido');
});

caso('submit manual no mesmo documento não leva extrair_auto', () => {
  // O clique manual não passa pelo caminho do autoenvio: sem marca no form.
  const c = criarCenario({ botaoDesabilitado: true });
  c.cliqueManual();
  afirmarIgual(marcasNoForm(c.form).length, 0, 'manual não injeta a marca');
  afirmarIgual(c.envios.join(','), 'manual', 'só o envio manual');
});

caso('após restaurar pelo bfcache o form volta sem a marca', () => {
  // A página restaurada ainda teria o input injetado: o clique manual
  // seguinte não pode herdar o flag de auto-extração.
  const c = criarCenario();
  afirmarIgual(marcasNoForm(c.form).length, 1, 'marca presente no disparo');
  c.pageshow(true);
  afirmarIgual(marcasNoForm(c.form).length, 0, 'marca removida na restauração');
});

caso('clique manual após autoenvio interrompido não leva extrair_auto', () => {
  // Codex MUST-FIX (PR #319): o autoenvio sai com a marca injetada; o usuário
  // edita o texto e desfaz a edição (ocr_texto.js reabilita o botão) e o
  // clique manual seguinte, no MESMO documento, não pode carregar o
  // extrair_auto=1 residual — senão o servidor recusa a reextração com
  // "Os campos já foram extraídos.".
  const c = criarCenario();
  afirmarIgual(c.envios.join(','), 'auto', 'autoenvio ocorreu');
  afirmarIgual(marcasNoForm(c.form).length, 1, 'marca injetada pelo autoenvio');
  c.botao.disabled = false; // ocr_texto.js reabilita o botão
  c.cliqueManual();
  afirmarIgual(marcasNoForm(c.form).length, 0, 'marca residual removida no submit manual');
  afirmarIgual(c.envios.join(','), 'auto,manual', 'envio manual seguiu adiante');
});

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
