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
  if (m) return el.tagName.toUpperCase() === m[1].toUpperCase();
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
function criarNoTexto(texto) {
  const no = {
    nodeType: 3,
    nodeName: '#text',
    parent: null,
    data: String(texto),
    get parentNode() { return this.parent; },
    get textContent() { return this.data; },
    set textContent(valor) { this.data = String(valor); },
    get nextSibling() {
      if (!this.parent) return null;
      const irmaos = this.parent.childNodes;
      return irmaos[irmaos.indexOf(this) + 1] || null;
    },
  };
  return no;
}
function criarElemento(tagName, atributos, pai) {
  const el = {
    nodeType: 1,
    nodeName: (tagName || 'div').toUpperCase(),
    attributes: Object.assign({}, atributos || {}),
    childNodes: [],
    parent: null,
    hidden: false,
    disabled: false,
    checked: false,
    value: '',
    type: '',
    listeners: {},
    classes: new Set(),
    get children() { return this.childNodes.filter((no) => no.nodeType === 1); },
    get textContent() { return this.childNodes.map((no) => no.textContent).join(''); },
    set textContent(valor) {
      this.childNodes.forEach((no) => { no.parent = null; });
      this.childNodes.length = 0;
      const texto = String(valor);
      if (texto) this.appendChild(criarNoTexto(texto));
    },
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
    appendChild(filho) {
      if (filho.parent) filho.parent.removeChild(filho);
      filho.parent = this;
      this.childNodes.push(filho);
      return filho;
    },
    removeChild(filho) {
      const indice = this.childNodes.indexOf(filho);
      if (indice !== -1) this.childNodes.splice(indice, 1);
      filho.parent = null;
      return filho;
    },
    insertBefore(novo, referencia) {
      if (novo.parent) novo.parent.removeChild(novo);
      const indice = referencia ? this.childNodes.indexOf(referencia) : -1;
      novo.parent = this;
      if (indice === -1) this.childNodes.push(novo); else this.childNodes.splice(indice, 0, novo);
      return novo;
    },
    get parentNode() { return this.parent; },
    get firstChild() { return this.childNodes[0] || null; },
    get nextSibling() {
      if (!this.parent) return null;
      const irmaos = this.parent.childNodes;
      return irmaos[irmaos.indexOf(this) + 1] || null;
    },
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
    value: (tagName || 'div').toUpperCase(),
    writable: false,
  });
  if (pai) pai.appendChild(el);
  return el;
}
function criarCenario(opcoes) {
  const semAtos = !!opcoes.semAtos;
  const pendenciasSalvas = opcoes.pendenciasSalvas
    || [{ chave: '/acts', motivo: 'nenhum_ato' }];
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
  let incluir = null;
  if (!opcoes.obrigatorio) {
    incluir = criarElemento('input', { 'data-campo-incluir': '' }, card);
    incluir.type = 'checkbox';
    incluir.checked = true;
  }
  const conferido = criarElemento('input', { 'data-campo-conferido': '' }, card);
  conferido.type = 'checkbox';
  conferido.checked = true;
  const atos = (opcoes.atos || []).map((desc) => {
    const chaveAto = desc.chaveAto;
    const secao = criarElemento('section', {
      'data-secao': 'ato', 'data-chave-ato': chaveAto,
    }, raiz);
    if (desc.descartado) secao.classList.add('descartado');
    const meta = criarElemento('p', { class: 'secao-meta' }, secao);
    const descartadoAlvo = criarElemento('span', { 'data-secao-descartado': '' }, meta);
    descartadoAlvo.textContent = 'Ato descartado · ';
    descartadoAlvo.hidden = !desc.descartado;
    const tipoAlvo = criarElemento('span', { 'data-secao-tipo': '' }, meta);
    tipoAlvo.hidden = !desc.tipoDisplay;
    tipoAlvo.textContent = desc.tipoDisplay ? desc.tipoDisplay + ' · ' : '';
    const pendenciasAlvo = criarElemento('span', { 'data-secao-pendencias': '' }, meta);
    const totalInicial = desc.pendenciasIniciais || 0;
    pendenciasAlvo.textContent = totalInicial + ' '
      + (totalInicial === 1 ? 'pendência' : 'pendências') + ' do ato';
    const cardAto = criarElemento('article', {
      'data-campo': '', 'data-chave': chaveAto, 'data-versao': 'v1',
    }, secao);
    const incluirAto = criarElemento('input', { 'data-campo-incluir': '' }, cardAto);
    incluirAto.type = 'checkbox';
    incluirAto.checked = !desc.descartado;
    let cardTipo = null;
    let selectTipo = null;
    if (!desc.semTipo) {
      cardTipo = criarElemento('article', {
        'data-campo': '', 'data-chave': chaveAto + '/tipo_sugerido', 'data-versao': 'v1',
      }, secao);
      selectTipo = criarElemento('select', { 'data-campo-valor': '', 'data-tipo': 'enum' }, cardTipo);
      [['averbacao', 'Averbação'], ['registro', 'Registro']].forEach((dupla) => {
        const opt = criarElemento('option', { value: dupla[0] }, selectTipo);
        opt.textContent = dupla[1];
      });
      selectTipo.value = desc.tipoCodigo || 'averbacao';
    }
    return {
      chaveAto, secao, pendenciasAlvo, descartadoAlvo, tipoAlvo,
      cardAto, incluirAto, cardTipo, selectTipo,
    };
  });
  let avisosUi = null;
  if (opcoes.avisos) {
    const iniciais = opcoes.avisos.iniciais || [];
    const contadorAvisos = criarElemento('strong', { 'data-ocr-contador-avisos': '' }, raiz);
    contadorAvisos.textContent = String(iniciais.length);
    const rotuloAvisos = criarElemento('span', { 'data-ocr-contador-avisos-texto': '' }, raiz);
    rotuloAvisos.textContent = iniciais.length === 1 ? 'aviso' : 'avisos';
    const blocoAvisos = criarElemento('section', { 'data-ocr-avisos': '' }, raiz);
    blocoAvisos.hidden = iniciais.length === 0;
    const listaAvisos = criarElemento('ul', { 'data-ocr-avisos-lista': '' }, blocoAvisos);
    iniciais.forEach((texto) => {
      criarElemento('li', {}, listaAvisos).textContent = texto;
    });
    const cardsOrigem = (opcoes.avisos.cardsOrigem || []).map((desc) => {
      const slug = desc.chave.replace(/[^a-z0-9]/g, '');
      const card = criarElemento('article', {
        'data-campo': '', 'data-chave': desc.chave, 'data-versao': 'v1',
      }, raiz);
      const linha = criarElemento('div', { class: 'campo-linha' }, card);
      criarElemento('label', { 'data-campo-rotulo': '', for: 'campo-' + slug }, linha)
        .textContent = 'Livro';
      if (desc.comSelo) {
        criarElemento('span', {
          'data-campo-nao-consta': '', id: 'nao-consta-' + slug,
        }, linha).textContent = 'não consta no documento';
      }
      const entrada = criarElemento('input', {
        id: 'campo-' + slug, 'data-campo-valor': '', 'data-tipo': 'texto',
      }, linha);
      entrada.type = 'text';
      if (desc.comSelo) entrada.setAttribute('aria-describedby', 'nao-consta-' + slug);
      return { chave: desc.chave, slug, card, linha, entrada };
    });
    avisosUi = {
      contador: contadorAvisos, rotulo: rotuloAvisos, bloco: blocoAvisos,
      lista: listaAvisos, cards: cardsOrigem,
    };
  }
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
      createElement(tag) { return criarElemento(tag); },
      createTextNode(texto) { return criarNoTexto(texto); },
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
    raiz, form, botao, msg, contador, rotulo, checkbox, card, valor, conferido,
    timeouts, alertas, navegacoes, chamadas, atos, avisosUi,
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
module.exports = { afirmar, afirmarIgual, criarCenario, esperar, casos, caso };
