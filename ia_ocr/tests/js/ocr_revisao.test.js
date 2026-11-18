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

function criarElemento(tagName, atributos, pai) {
  const el = {
    tagName: (tagName || 'div').toUpperCase(),
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
    // #324 (PR #343): o save redesenha a lista de avisos e os selos.
    removeChild(filho) {
      const indice = this.children.indexOf(filho);
      if (indice !== -1) this.children.splice(indice, 1);
      filho.parent = null;
      return filho;
    },
    insertBefore(novo, referencia) {
      const indice = referencia ? this.children.indexOf(referencia) : -1;
      novo.parent = this;
      if (indice === -1) this.children.push(novo); else this.children.splice(indice, 0, novo);
      return novo;
    },
    get parentNode() { return this.parent; },
    get firstChild() { return this.children[0] || null; },
    get nextSibling() {
      if (!this.parent) return null;
      return this.parent.children[this.parent.children.indexOf(this) + 1] || null;
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
  // Campo obrigatório (tipo/data/cartório) não renderiza o checkbox de incluir.
  let incluir = null;
  if (!opcoes.obrigatorio) {
    incluir = criarElemento('input', { 'data-campo-incluir': '' }, card);
    incluir.type = 'checkbox';
    incluir.checked = true;
  }
  const conferido = criarElemento('input', { 'data-campo-conferido': '' }, card);
  conferido.type = 'checkbox';
  conferido.checked = true;

  // I-11a (PR #336): blocos de ato opcionais com seção, marcador, contagem e
  // select de tipo — os MESMOS alvos estáveis do template (data-secao-*).
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

  // #324 (PR #343): os MESMOS alvos estáveis do template — contagem do
  // cabeçalho, seção/lista de avisos e os cards de livro/folha da origem
  // (rótulo, selo "não consta no documento" opcional e o campo, nessa ordem).
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
      createTextNode(texto) {
        const no = criarElemento('#text');
        no.textContent = texto;
        return no;
      },
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

// 9. Campo obrigatório não tem checkbox de incluir: o payload manda
//    incluir true e o change não marca o card como descartado.
caso('obrigatório sem checkbox: payload incluir true e card não descartado', async () => {
  const c = criarCenario({ semAtos: false, obrigatorio: true });
  afirmarIgual(c.card.querySelector('[data-campo-incluir]'), null, 'card não deve ter checkbox de incluir');

  c.conferido.checked = false;
  c.dispararChange(c.conferido);
  afirmarIgual(c.card.classList.contains('descartado'), false, 'change não pode descartar obrigatório');

  c.executarTimeout(0);
  await esperar();
  const salvar = c.chamadas.find((item) => item.url === '/salvar/');
  afirmar(!!salvar, 'change deve agendar o save');
  afirmarIgual(salvar.corpo.decisoes[0].incluir, true, 'payload do obrigatório deve ter incluir true');
});

// 10. I-11a (PR #336): um save que devolve ``pendencias`` sem a chave do ato
//     zera o contador da seção (recalculado do array, não do DOM).
caso('seção do ato: save sem a chave do ato zera o contador da seção', async () => {
  const c = criarCenario({
    semAtos: false,
    atos: [{ chaveAto: '/acts/0', descartado: false, tipoDisplay: 'Averbação', pendenciasIniciais: 1 }],
    pendenciasSalvas: [{ chave: '/document/data', motivo: 'obrigatorio_ausente' }],
  });
  const ato = c.atos[0];
  afirmarIgual(ato.pendenciasAlvo.textContent, '1 pendência do ato', 'seção começa com 1 pendência');

  c.dispararInput();
  c.executarTimeout(0);
  await esperar();

  afirmarIgual(
    ato.pendenciasAlvo.textContent,
    '0 pendências do ato',
    'save sem a chave do ato deve zerar o contador da seção'
  );
});

// 11. I-11a (PR #336): reincluir o ato (marcar o Incluir da linha /acts/N)
//     remove o marcador "Ato descartado" e a classe da seção após o save.
caso('seção do ato: reincluir o ato remove o marcador "Ato descartado"', async () => {
  const c = criarCenario({
    semAtos: false,
    atos: [{ chaveAto: '/acts/0', descartado: true, semTipo: true, pendenciasIniciais: 1 }],
    pendenciasSalvas: [],
  });
  const ato = c.atos[0];
  afirmar(ato.secao.classList.contains('descartado'), 'seção começa descartada');
  afirmarIgual(ato.descartadoAlvo.hidden, false, 'marcador visível no início');
  afirmarIgual(ato.incluirAto.checked, false, 'Incluir começa desmarcado');

  ato.incluirAto.checked = true;
  c.dispararChange(ato.incluirAto);
  c.executarTimeout(0);
  await esperar();

  afirmar(
    !ato.secao.classList.contains('descartado'),
    'seção deve perder a classe descartado após reincluir'
  );
  afirmarIgual(ato.descartadoAlvo.hidden, true, 'marcador deve sumir após reincluir');
});

// 12. I-11a (PR #336): trocar o tipo no <select> do ato atualiza o tipo exibido
//     no cabeçalho da seção, a partir do texto da opção selecionada.
caso('seção do ato: trocar o tipo atualiza o cabeçalho', async () => {
  const c = criarCenario({
    semAtos: false,
    atos: [{ chaveAto: '/acts/0', descartado: false, tipoDisplay: 'Averbação', pendenciasIniciais: 1 }],
    pendenciasSalvas: [],
  });
  const ato = c.atos[0];
  afirmarIgual(ato.tipoAlvo.textContent, 'Averbação · ', 'cabeçalho começa com o tipo atual');

  ato.selectTipo.value = 'registro';
  c.dispararChange(ato.selectTipo);
  c.executarTimeout(0);
  await esperar();

  afirmarIgual(
    ato.tipoAlvo.textContent,
    'Registro · ',
    'tipo do cabeçalho deve acompanhar a opção selecionada'
  );
  afirmarIgual(ato.tipoAlvo.hidden, false, 'tipo deve ficar visível');
});

// ---------- #324 (PR #343): avisos e selos recalculados pelo save ----------

const AVISO_LIVRO = {
  chave: '/acts/0/origem/livro',
  motivo: 'livro_origem_nao_consta',
  local: 'Ato 1 — livro',
  rotulo: 'Livro da origem não consta no documento',
  nao_consta: true,
};
const AVISO_FOLHA = {
  chave: '/acts/0/origem/folha',
  motivo: 'folha_origem_nao_consta',
  local: 'Ato 1 — folha',
  rotulo: 'Folha da origem não consta no documento',
  nao_consta: true,
};

function cenarioDeAvisos(opcoes) {
  return criarCenario({
    semAtos: false,
    pendenciasSalvas: [],
    avisos: opcoes.avisos,
    respostasSalvar: opcoes.respostasSalvar,
  });
}

async function salvarUmaVez(c) {
  c.dispararInput();
  c.executarTimeout(0);
  await esperar();
}

function selosDoCard(item) {
  return item.linha.querySelectorAll('[data-campo-nao-consta]');
}

// 13. O save que zera os avisos limpa a lista, a contagem e os selos.
caso('avisos: o save sem avisos limpa lista, contagem e selos', async () => {
  const c = cenarioDeAvisos({
    avisos: {
      iniciais: [
        'Ato 1 — livro: Livro da origem não consta no documento',
        'Ato 1 — folha: Folha da origem não consta no documento',
      ],
      cardsOrigem: [
        { chave: AVISO_LIVRO.chave, comSelo: true },
        { chave: AVISO_FOLHA.chave, comSelo: true },
      ],
    },
    respostasSalvar: [{ avisos: [] }],
  });
  const ui = c.avisosUi;
  afirmarIgual(ui.contador.textContent, '2', 'premissa: dois avisos na abertura');

  await salvarUmaVez(c);

  afirmarIgual(ui.contador.textContent, '0', 'contagem deve zerar');
  afirmarIgual(ui.rotulo.textContent, 'avisos', 'zero é plural, como o pluralize do template');
  afirmarIgual(ui.lista.children.length, 0, 'lista deve esvaziar');
  afirmarIgual(ui.bloco.hidden, true, 'seção sem avisos fica oculta');
  ui.cards.forEach((item) => {
    afirmarIgual(selosDoCard(item).length, 0, 'selo de ' + item.chave + ' deve sair');
    afirmarIgual(
      item.entrada.getAttribute('aria-describedby'), null,
      'campo não aponta mais para o selo removido (' + item.chave + ')'
    );
  });
});

// 14. Preencher só o livro: o aviso da folha e o selo da folha ficam.
caso('avisos: preencher só o livro tira só o aviso e o selo do livro', async () => {
  const c = cenarioDeAvisos({
    avisos: {
      iniciais: ['livro', 'folha'],
      cardsOrigem: [
        { chave: AVISO_LIVRO.chave, comSelo: true },
        { chave: AVISO_FOLHA.chave, comSelo: true },
      ],
    },
    respostasSalvar: [{ avisos: [AVISO_FOLHA] }],
  });
  const ui = c.avisosUi;
  const [livro, folha] = ui.cards;

  await salvarUmaVez(c);

  afirmarIgual(ui.contador.textContent, '1', 'contagem deve refletir um aviso');
  afirmarIgual(ui.rotulo.textContent, 'aviso', 'um é singular');
  afirmarIgual(ui.bloco.hidden, false, 'seção segue visível');
  afirmarIgual(ui.lista.children.length, 1, 'só o aviso da folha sobra na lista');
  afirmarIgual(
    ui.lista.children[0].textContent,
    'Ato 1 — folha: Folha da origem não consta no documento',
    'texto do item: local + rótulo, como no template'
  );
  afirmarIgual(selosDoCard(livro).length, 0, 'selo do livro sai');
  afirmarIgual(livro.entrada.getAttribute('aria-describedby'), null, 'livro sem aria-describedby');
  afirmarIgual(selosDoCard(folha).length, 1, 'selo da folha fica (uma vez só)');
  afirmarIgual(
    folha.entrada.getAttribute('aria-describedby'), 'nao-consta-' + folha.slug,
    'folha continua apontando para o próprio selo'
  );
});

// 15. Um aviso NOVO (ex.: o número da origem foi preenchido) mostra a seção,
//     desenha o item e cria o selo logo depois do rótulo do card.
caso('avisos: aviso novo mostra a seção, desenha o item e cria o selo', async () => {
  const c = cenarioDeAvisos({
    avisos: {
      iniciais: [],
      cardsOrigem: [
        { chave: AVISO_LIVRO.chave, comSelo: false },
        { chave: AVISO_FOLHA.chave, comSelo: false },
      ],
    },
    respostasSalvar: [{ avisos: [AVISO_LIVRO, AVISO_FOLHA] }],
  });
  const ui = c.avisosUi;
  afirmarIgual(ui.bloco.hidden, true, 'premissa: seção oculta sem avisos');

  await salvarUmaVez(c);

  afirmarIgual(ui.contador.textContent, '2', 'contagem deve subir para 2');
  afirmarIgual(ui.rotulo.textContent, 'avisos', 'dois é plural');
  afirmarIgual(ui.bloco.hidden, false, 'seção deve aparecer');
  afirmarIgual(ui.lista.children.length, 2, 'dois itens na lista');

  // O item tem o mesmo desenho do template: texto + <details> técnico.
  const item = ui.lista.children[0];
  afirmarIgual(item.tagName, 'LI', 'item é <li>');
  afirmar(item.classList.contains('aviso'), 'item leva a classe aviso');
  afirmarIgual(
    item.textContent, 'Ato 1 — livro: Livro da origem não consta no documento',
    'texto do item'
  );
  const detalhe = item.children[0];
  afirmarIgual(detalhe.tagName, 'DETAILS', 'detalhe técnico em <details>');
  afirmarIgual(
    detalhe.children.map((filho) => filho.tagName + ':' + filho.textContent).join('|'),
    'SUMMARY:Detalhe técnico|CODE:' + AVISO_LIVRO.chave + '|#TEXT: — |CODE:' + AVISO_LIVRO.motivo,
    'detalhe técnico: resumo, chave, separador e motivo'
  );

  ui.cards.forEach((card) => {
    const selos = selosDoCard(card);
    afirmarIgual(selos.length, 1, 'um selo para ' + card.chave);
    const selo = selos[0];
    afirmarIgual(selo.textContent, 'não consta no documento', 'texto do selo');
    afirmarIgual(selo.getAttribute('id'), 'nao-consta-' + card.slug, 'id do selo sai do id do campo');
    afirmar(selo.classList.contains('badge-motivo'), 'selo leva a classe badge-motivo');
    afirmarIgual(
      card.linha.children.map((filho) => filho.tagName).join(','),
      'LABEL,SPAN,INPUT',
      'selo entra logo depois do rótulo, antes do campo'
    );
    afirmarIgual(
      card.entrada.getAttribute('aria-describedby'), 'nao-consta-' + card.slug,
      'campo aponta para o selo'
    );
  });
});

// 16. Aviso que continua não duplica o selo; aviso que não é de "não consta"
//     entra na lista mas não ganha selo.
caso('avisos: selo existente não duplica e aviso comum não ganha selo', async () => {
  const comum = {
    chave: AVISO_FOLHA.chave, motivo: 'requer_folha_origem',
    local: 'Ato 1 — folha', rotulo: 'Campo recomendado não preenchido',
    nao_consta: false,
  };
  const c = cenarioDeAvisos({
    avisos: {
      iniciais: ['livro'],
      cardsOrigem: [
        { chave: AVISO_LIVRO.chave, comSelo: true },
        { chave: AVISO_FOLHA.chave, comSelo: false },
      ],
    },
    respostasSalvar: [{ avisos: [AVISO_LIVRO, comum] }],
  });
  const [livro, folha] = c.avisosUi.cards;

  await salvarUmaVez(c);

  afirmarIgual(selosDoCard(livro).length, 1, 'o selo que já existia não duplica');
  afirmarIgual(selosDoCard(folha).length, 0, 'aviso comum não ganha selo');
  afirmarIgual(folha.entrada.getAttribute('aria-describedby'), null, 'sem aria-describedby');
  afirmarIgual(c.avisosUi.lista.children.length, 2, 'os dois avisos entram na lista');
  afirmarIgual(c.avisosUi.contador.textContent, '2', 'contagem acompanha a lista');
});

// 17. Resposta sem a chave avisos (outro endpoint, versão antiga do servidor)
//     não mexe nos avisos que a tela já mostra.
caso('avisos: resposta sem a lista não mexe na tela', async () => {
  const c = cenarioDeAvisos({
    avisos: {
      iniciais: ['livro'],
      cardsOrigem: [{ chave: AVISO_LIVRO.chave, comSelo: true }],
    },
    respostasSalvar: [{}],
  });
  const ui = c.avisosUi;

  await salvarUmaVez(c);

  afirmarIgual(ui.contador.textContent, '1', 'contagem intacta');
  afirmarIgual(ui.lista.children.length, 1, 'lista intacta');
  afirmarIgual(selosDoCard(ui.cards[0]).length, 1, 'selo intacto');
});

// 18. Texto do servidor entra como texto: o rótulo vai para textContent.
caso('avisos: texto do servidor entra por textContent', async () => {
  const hostil = {
    chave: '/acts/0/forma', motivo: 'requer_forma', local: '<b>Ato 1</b>',
    rotulo: '<img src=x onerror=1>', nao_consta: false,
  };
  const c = cenarioDeAvisos({
    avisos: { iniciais: [], cardsOrigem: [] },
    respostasSalvar: [{ avisos: [hostil] }],
  });

  await salvarUmaVez(c);

  const item = c.avisosUi.lista.children[0];
  afirmarIgual(item.textContent, '<b>Ato 1</b>: <img src=x onerror=1>', 'vai como texto, sem virar tag');
  afirmarIgual(
    item.children.map((filho) => filho.tagName).join(','), 'DETAILS',
    'só o <details> técnico é elemento filho'
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
