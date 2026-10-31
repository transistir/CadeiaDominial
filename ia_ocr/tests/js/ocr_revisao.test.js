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
 * Uso: node ia_ocr/tests/js/ocr_revisao.test.js   (exit 1 se algum caso falhar)
 */
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const CAMINHO_JS = path.resolve(
  __dirname, '..', '..', '..', 'static', 'dominial', 'js', 'ocr_revisao.js'
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

// ---------- mock de DOM ----------

function corresponde(el, seletor) {
  const sel = seletor.trim();
  if (!sel || sel.indexOf(':') !== -1) return false;
  let m = sel.match(/^\[([^\]=]+)(?:=(?:"([^"]*)"|([^"\]]+)))?\]$/);
  if (m) {
    const nome = m[1];
    if (!Object.prototype.hasOwnProperty.call(el.attributes, nome)) return false;
    const esperado = m[2] !== undefined ? m[2] : m[3];
    return esperado === undefined || el.attributes[nome] === esperado;
  }
  m = sel.match(/^([a-zA-Z][a-zA-Z0-9]*)$/);
  if (m) return el.tagName === m[1].toLowerCase();
  return false;
}

function buscar(no, seletor, todos) {
  const seletores = seletor.split(',').map((parte) => parte.trim());
  const achados = [];
  (function passeia(atual) {
    for (const filho of atual.children) {
      const casou = seletores.some((sel) => corresponde(filho, sel));
      if (casou) {
        achados.push(filho);
        if (!todos) return;
      }
      passeia(filho);
      if (achados.length && !todos) return;
    }
  })(no);
  return todos ? achados : achados[0] || null;
}

function criarElemento(tagName, atributos, pai) {
  const el = {
    tagName: (tagName || 'div').toLowerCase(),
    attributes: Object.assign({}, atributos || {}),
    children: [],
    parent: pai || null,
    hidden: false,
    disabled: false,
    checked: false,
    value: '',
    type: '',
    textContent: '',
    listeners: {},
    classes: new Set(),
    get className() { return Array.from(this.classes).join(' '); },
    classList: {
      add(classe) { el.classes.add(classe); },
      remove(classe) { el.classes.delete(classe); },
      contains(classe) { return el.classes.has(classe); },
      toggle(classe, ativo) {
        const ligar = ativo === undefined ? !el.classes.has(classe) : !!ativo;
        if (ligar) el.classes.add(classe); else el.classes.delete(classe);
        return ligar;
      },
    },
    getAttribute(nome) {
      return Object.prototype.hasOwnProperty.call(this.attributes, nome) ? this.attributes[nome] : null;
    },
    get action() { return this.attributes.action || ''; },
    set action(valor) { this.attributes.action = String(valor); },
    setAttribute(nome, valor) { this.attributes[nome] = String(valor); },
    removeAttribute(nome) { delete this.attributes[nome]; },
    addEventListener(evento, fn) {
      (this.listeners[evento] = this.listeners[evento] || []).push(fn);
    },
    click() {
      if (this.disabled) return;
      (this.listeners.click || []).slice().forEach((fn) => fn({ preventDefault() {} }));
    },
    dispatchEvent(evento) {
      (this.listeners[evento.type] || []).slice().forEach((fn) => fn(evento));
    },
    appendChild(filho) { filho.parent = this; this.children.push(filho); return filho; },
    querySelector(seletor) { return buscar(this, seletor, false); },
    querySelectorAll(seletor) { return buscar(this, seletor, true); },
    closest(seletor) {
      let atual = this;
      while (atual) {
        if (corresponde(atual, seletor)) return atual;
        atual = atual.parent;
      }
      return null;
    },
    closestElement() { return this; },
    focus() {},
    scrollIntoView() {},
    get parentElement() { return this.parent; },
    get tagNameUpper() { return this.tagName.toUpperCase(); },
  };
  Object.defineProperty(el, 'tagName', {
    value: (tagName || 'div').toLowerCase(),
    writable: false,
  });
  if (pai) pai.children.push(el);
  return el;
}

function criarCenario(opcoes) {
  const semAtos = !!opcoes.semAtos;
  const pendenciasSalvas = opcoes.pendenciasSalvas
    || [{ chave: '/acts', motivo: 'nenhum_ato' }];
  // Respostas extras do save, consumidas em ordem; a última se repete.
  const respostasSalvar = (opcoes.respostasSalvar || []).slice();
  let indiceRespostaSalvar = 0;
  const respostaFinalizar = opcoes.respostaFinalizar || {
    status: 200, dados: { ok: true, redirect: '/documento/' },
  };
  const raiz = criarElemento('div', Object.assign({
    'data-ocr-revisao': '',
    'data-url-salvar': '/salvar/',
  }, semAtos ? { 'data-permitir-sem-atos': '1' } : {}));

  const toolbar = criarElemento('div', { 'data-ocr-toolbar': '', 'data-versao': 'v1' }, raiz);
  const form = criarElemento('form', { 'data-ocr-finalizar-form': '', action: '/finalizar/' }, raiz);
  const csrf = criarElemento('input', { name: 'csrfmiddlewaretoken' }, form);
  csrf.type = 'hidden';
  csrf.value = 'token-csrf';
  const versao = criarElemento('input', { 'data-ocr-versao': '' }, form);
  versao.type = 'hidden';
  versao.value = 'v1';
  const botao = criarElemento('button', { 'data-ocr-finalizar': '' }, form);
  botao.type = 'submit';
  botao.textContent = 'Finalizar revisão';
  botao.disabled = true;
  const msg = criarElemento('small', { 'data-ocr-finalizar-msg': '' }, form);
  const contador = criarElemento('strong', { 'data-ocr-contador-pendencias': '' }, raiz);
  contador.textContent = '1';
  const rotulo = criarElemento('span', { 'data-ocr-contador-pendencias-texto': '' }, raiz);
  rotulo.textContent = 'pendência';

  let checkbox = null;
  if (semAtos) {
    checkbox = criarElemento('input', { 'data-ocr-sem-atos': '' }, raiz);
    checkbox.type = 'checkbox';
    checkbox.checked = false;
  }

  const card = criarElemento('article', {
    'data-campo': '', 'data-chave': '/document/data', 'data-versao': 'v1',
  }, raiz);
  const valor = criarElemento('input', { 'data-campo-valor': '', 'data-tipo': 'texto' }, card);
  valor.type = 'text';
  valor.value = 'original';
  const incluir = criarElemento('input', { 'data-campo-incluir': '' }, card);
  incluir.type = 'checkbox';
  incluir.checked = true;
  const conferido = criarElemento('input', { 'data-campo-conferido': '' }, card);
  conferido.type = 'checkbox';
  conferido.checked = true;

  const timeouts = [];
  const alertas = [];
  const navegacoes = [];
  const chamadas = [];
  let idTimer = 0;

  const sandbox = {
    console,
    document: {
      activeElement: null,
      listeners: {},
      addEventListener(evento, fn) {
        (this.listeners[evento] = this.listeners[evento] || []).push(fn);
      },
      querySelector(seletor) { return corresponde(raiz, seletor) ? raiz : null; },
    },
    window: {
      setTimeout(fn, atraso) {
        idTimer += 1;
        timeouts.push({ id: idTimer, fn, atraso });
        return idTimer;
      },
      clearTimeout(id) {
        const indice = timeouts.findIndex((item) => item.id === id);
        if (indice !== -1) timeouts.splice(indice, 1);
      },
      alert(mensagem) { alertas.push(mensagem); },
      location: {
        assign(url) { navegacoes.push(url); },
        reload() { navegacoes.push('reload'); },
      },
    },
    fetch(url, init) {
      chamadas.push({ url, init, corpo: init && init.body ? JSON.parse(init.body) : null });
      const resposta = {};
      if (url === '/salvar/') {
        const extra = respostasSalvar.length
          ? respostasSalvar[Math.min(indiceRespostaSalvar++, respostasSalvar.length - 1)]
          : {};
        resposta.status = 200;
        resposta.json = () => Promise.resolve(Object.assign({
          ok: true,
          versao: 'v2',
          pendencias: pendenciasSalvas,
        }, extra));
      } else {
        resposta.status = respostaFinalizar.status;
        resposta.json = () => Promise.resolve(respostaFinalizar.dados);
      }
      return Promise.resolve(resposta);
    },
    Map,
    Set,
    Promise,
    JSON,
    Array,
    Object,
  };
  sandbox.window.window = sandbox.window;
  sandbox.globalThis = sandbox;

  vm.runInNewContext(fs.readFileSync(CAMINHO_JS, 'utf8'), sandbox, { filename: CAMINHO_JS });
  (sandbox.document.listeners.DOMContentLoaded || []).forEach((fn) => fn());

  return {
    raiz, form, botao, msg, contador, rotulo, checkbox, card, valor,
    timeouts, alertas, navegacoes, chamadas,
    dispararInput() {
      (raiz.listeners.input || []).forEach((fn) => fn({ target: valor }));
    },
    dispararChange(alvo) {
      (raiz.listeners.change || []).forEach((fn) => fn({ target: alvo }));
    },
    dispararFocusout() {
      sandbox.document.activeElement = null;
      (raiz.listeners.focusout || []).forEach((fn) => fn({ relatedTarget: null }));
    },
    enviarFormulario() {
      (form.listeners.submit || []).forEach((fn) => fn({ preventDefault() {} }));
    },
    executarTimeout(indice) {
      const item = timeouts[indice || 0];
      afirmar(!!item, 'nenhum timer de debounce agendado');
      timeouts.splice(timeouts.indexOf(item), 1);
      item.fn();
    },
  };
}

async function esperar() {
  for (let i = 0; i < 8; i += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
}

const casos = [];

function caso(nome, fn) {
  casos.push({ nome, fn });
}

// 1. O botão só habilita com o checkbox marcado, e o contador continua 1.
caso('modo sem atos: botão só habilita com confirmação e contador fica em 1', async () => {
  const c = criarCenario({ semAtos: true });
  afirmarIgual(c.botao.disabled, true, 'botão deve começar desabilitado');

  // Um save devolve a pendência nenhum_ato: a lista NÃO é zerada.
  c.dispararInput();
  c.executarTimeout(0);
  await esperar();

  afirmarIgual(c.contador.textContent, '1', 'contador deve continuar mostrando 1 pendência');
  afirmarIgual(c.rotulo.textContent, 'pendência', 'rótulo deve continuar no singular');
  afirmarIgual(c.botao.disabled, true, 'sem confirmação o botão continua desabilitado');

  c.checkbox.checked = true;
  c.dispararChange(c.checkbox);
  afirmarIgual(c.botao.disabled, false, 'checkbox marcado deve habilitar o botão');
  afirmarIgual(c.botao.getAttribute('title'), null, 'modo sem atos não mostra title de pendências');

  c.checkbox.checked = false;
  c.dispararChange(c.checkbox);
  afirmarIgual(c.botao.disabled, true, 'desmarcar deve desabilitar de novo');
});

// 2. O POST inclui sem_atos: true apenas quando o checkbox está marcado.
caso('modo sem atos: finalizar envia sem_atos true com confirmação', async () => {
  const c = criarCenario({ semAtos: true });
  c.checkbox.checked = true;
  c.dispararChange(c.checkbox);
  c.enviarFormulario();
  await esperar();

  const chamada = c.chamadas.find((item) => item.url === '/finalizar/');
  afirmar(!!chamada, 'finalizar deve chamar o endpoint do formulário');
  afirmarIgual(chamada.corpo.sem_atos, true, 'corpo deve conter sem_atos: true');
  afirmarIgual(chamada.corpo.versao, 'v1', 'corpo deve manter a versão');
  afirmarIgual(c.navegacoes[c.navegacoes.length - 1], '/documento/', 'deve navegar para o redirect');
});

// 3. Sem o modo, o corpo continua exatamente como hoje.
caso('sem o modo: finalizar não envia sem_atos', async () => {
  const c = criarCenario({ semAtos: false });
  c.botao.disabled = false; // template habilita quando não há pendências
  c.enviarFormulario();
  await esperar();

  const chamada = c.chamadas.find((item) => item.url === '/finalizar/');
  afirmar(!!chamada, 'finalizar deve chamar o endpoint do formulário');
  afirmarIgual(Object.keys(chamada.corpo).join(','), 'versao', 'corpo deve ter só a versão');
});

// 4. Um save posterior com outra pendência mantém o botão bloqueado mesmo
//    quando o checkbox de confirmação é marcado.
caso('modo sem atos: outra pendência do save mantém o botão bloqueado', async () => {
  const c = criarCenario({
    semAtos: true,
    pendenciasSalvas: [{ chave: '/document/data', motivo: 'obrigatorio_ausente' }],
  });

  c.dispararInput();
  c.executarTimeout(0);
  await esperar();

  afirmarIgual(c.contador.textContent, '1', 'contador deve refletir a pendência nova');
  afirmarIgual(c.botao.disabled, true, 'sem confirmação o botão continua desabilitado');

  c.checkbox.checked = true;
  c.dispararChange(c.checkbox);

  afirmarIgual(c.botao.disabled, true, 'marcar o checkbox não pode ignorar a pendência nova');
  afirmarIgual(
    c.botao.title,
    'Resolva as pendências antes de finalizar.',
    'deve manter o title de pendências'
  );
});

// 5. Antes do primeiro save a pendência inicial já conta: desmarcar bloqueia.
caso('modo sem atos: sem save, marcar habilita e desmarcar desabilita', async () => {
  const c = criarCenario({ semAtos: true });
  afirmarIgual(c.botao.disabled, true, 'botão deve começar desabilitado');

  c.checkbox.checked = true;
  c.dispararChange(c.checkbox);
  afirmarIgual(c.botao.disabled, false, 'marcar antes do primeiro save deve habilitar');

  c.checkbox.checked = false;
  c.dispararChange(c.checkbox);
  afirmarIgual(c.botao.disabled, true, 'desmarcar antes do primeiro save deve desabilitar');
  afirmarIgual(c.contador.textContent, '1', 'contador deve permanecer em 1');
});

// 6. Um save que cria bloqueio de campo devolve sem_atos_elegivel false e
//    desabilita o botão; o save seguinte com true volta a habilitar.
caso('modo sem atos: save inelegível desabilita e save elegível reabilita', async () => {
  const c = criarCenario({
    semAtos: true,
    respostasSalvar: [
      { sem_atos_elegivel: false },
      { sem_atos_elegivel: true },
    ],
  });
  c.checkbox.checked = true;
  c.dispararChange(c.checkbox);
  afirmarIgual(c.botao.disabled, false, 'checkbox marcado habilita antes do save');

  c.dispararInput();
  c.executarTimeout(0);
  await esperar();
  afirmarIgual(
    c.botao.disabled, true,
    'save com sem_atos_elegivel false deve desabilitar mesmo com checkbox marcado'
  );

  c.dispararInput();
  c.executarTimeout(0);
  await esperar();
  afirmarIgual(
    c.botao.disabled, false,
    'save com sem_atos_elegivel true deve reabilitar com checkbox marcado'
  );
});

// 7. O 422 do finalizar re-bloqueia a tela: pendências novas desabilitam o
//    botão mesmo com a confirmação sem atos marcada.
caso('modo sem atos: 422 revisao_incompleta re-bloqueia o botão', async () => {
  const c = criarCenario({
    semAtos: true,
    respostaFinalizar: {
      status: 422,
      dados: {
        erro: 'revisao_incompleta',
        pendencias: [
          { chave: '/acts', motivo: 'nenhum_ato', bloqueante: true },
          { chave: '/document/data', motivo: 'obrigatorio_ausente', bloqueante: true },
        ],
      },
    },
  });
  c.checkbox.checked = true;
  c.dispararChange(c.checkbox);
  afirmarIgual(c.botao.disabled, false, 'checkbox marcado habilita antes de finalizar');

  c.enviarFormulario();
  await esperar();

  const chamada = c.chamadas.find((item) => item.url === '/finalizar/');
  afirmar(!!chamada, 'finalizar deve chamar o endpoint do formulário');
  afirmarIgual(c.botao.disabled, true, '422 deve deixar o botão desabilitado');
  afirmarIgual(c.contador.textContent, '2', 'contador deve refletir as pendências do 422');
  afirmarIgual(
    c.botao.title,
    'Resolva as pendências antes de finalizar.',
    '422 deve restaurar o title de pendências'
  );
});

// 8. A tela nasceu sem o modo (sem checkbox) e o save a torna elegível: o
//    botão continua bloqueado, mas o aviso é o de liberar o finalizar sem
//    atos (o reload é que cria os controles), não o de identidade.
caso('sem o modo: save elegível pede reload para liberar o finalizar sem atos', async () => {
  const c = criarCenario({
    semAtos: false,
    respostasSalvar: [{ sem_atos_elegivel: true }],
  });
  afirmarIgual(c.checkbox, null, 'a tela não deve ter checkbox sem o modo');

  c.dispararInput();
  c.executarTimeout(0);
  await esperar();

  afirmarIgual(c.botao.disabled, true, 'sem o modo o botão continua desabilitado');
  afirmar(
    c.msg.textContent.indexOf('sem atos') !== -1,
    'aviso deve liberar o finalizar sem atos (atual=' + JSON.stringify(c.msg.textContent) + ')'
  );

  // O reload diferido dispara no focusout (mesmo gatilho do harness real):
  // é ele que recria a tela já com o checkbox de finalizar sem atos.
  c.dispararFocusout();
  c.executarTimeout(0);
  afirmar(
    c.navegacoes.indexOf('reload') !== -1,
    'save elegível sem o modo deve recarregar para criar os controles'
  );
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
