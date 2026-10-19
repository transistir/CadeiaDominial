/**
 * Testes do card "Extrair texto com IA" (static/dominial/js/ocr_card.js).
 *
 * Node puro, sem dependências novas: o JS é lido com fs.readFileSync e
 * avaliado com vm.runInNewContext num sandbox com DOM/fetch/timers mockados
 * à mão. Fecha o P2 "Polling lacks automated tests" do Greptile no PR #279.
 * Casos 6–8 (issue #261 / I-4): "Revisar texto" vira link com o job concluído.
 *
 * Uso: node ia_ocr/tests/js/ocr_card.test.js   (exit 1 se algum caso falhar)
 */
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const CAMINHO_JS = path.resolve(__dirname, '..', '..', '..', 'static', 'dominial', 'js', 'ocr_card.js');

// ---------- asserções mínimas ----------

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

function correspondeSeletor(el, seletor) {
  let m = seletor.match(/^\[([^\]=]+)\]$/);
  if (m) return Object.prototype.hasOwnProperty.call(el.attributes, m[1]);
  m = seletor.match(/^([a-zA-Z][a-zA-Z0-9]*)\[([^=\]]+)="([^"]*)"\]$/);
  if (m) return el.tagName === m[1].toLowerCase() && el.attributes[m[2]] === m[3];
  return false;
}

function buscarDescendentes(no, seletor, todos) {
  const achados = [];
  (function passeia(atual) {
    for (const filho of atual.children) {
      if (correspondeSeletor(filho, seletor)) {
        achados.push(filho);
        if (!todos) return;
      }
      passeia(filho);
    }
  })(no);
  return todos ? achados : achados[0] || null;
}

function criarElemento(tagName, atributos) {
  const el = {
    tagName: (tagName || 'div').toLowerCase(),
    attributes: Object.assign({}, atributos || {}),
    children: [],
    hidden: false,
    disabled: false,
    className: '',
    textContent: '',
    listeners: {},
    getAttribute(nome) {
      return Object.prototype.hasOwnProperty.call(this.attributes, nome) ? this.attributes[nome] : null;
    },
    setAttribute(nome, valor) {
      this.attributes[nome] = String(valor);
    },
    addEventListener(evento, fn) {
      (this.listeners[evento] = this.listeners[evento] || []).push(fn);
    },
    click() {
      // Fiel ao navegador: elemento desabilitado não dispara click.
      if (this.disabled) return;
      (this.listeners.click || []).slice().forEach((fn) => fn({ preventDefault() {} }));
    },
    appendChild(filho) {
      this.children.push(filho);
      return filho;
    },
    querySelector(seletor) {
      return buscarDescendentes(this, seletor, false);
    },
    querySelectorAll(seletor) {
      return buscarDescendentes(this, seletor, true);
    },
  };
  return el;
}

function criarCard(atributos) {
  const card = criarElemento('div', Object.assign({ 'data-ocr-card': '' }, atributos || {}));
  const badge = criarElemento('span', { 'data-ocr-badge': '', class: 'badge bg-light text-dark' });
  badge.textContent = 'OCR não iniciado';
  const erro = criarElemento('small', { 'data-ocr-erro': '', class: 'text-danger' });
  erro.hidden = true;
  const disparo = criarElemento('button', { 'data-ocr-disparo': '', class: 'btn btn-primary btn-sm' });
  disparo.textContent = '▶ Extrair texto com IA';
  const retry = criarElemento('button', { 'data-ocr-retry': '', class: 'btn btn-outline-danger btn-sm' });
  retry.textContent = 'Tentar novamente';
  retry.hidden = true;
  const revisar = criarElemento('button', { 'data-ocr-revisar': '', class: 'btn btn-success btn-sm' });
  revisar.textContent = 'Revisar texto';
  revisar.hidden = true;
  const atualizar = criarElemento('button', { 'data-ocr-atualizar': '', class: 'btn btn-outline-secondary btn-sm' });
  atualizar.textContent = 'Atualizar status';
  atualizar.hidden = true;
  const motivo = criarElemento('small', { 'data-ocr-revisar-motivo': '', class: 'text-muted' });
  motivo.textContent = 'Texto já confirmado: a revisão só fica disponível até a extração dos campos.';
  motivo.hidden = true;
  // I-4 (#261): com o OCR concluído, "Revisar texto" é um link para a tela
  // de confirmação; o botão desabilitado fica para os estados já confirmados.
  const link = criarElemento('a', { 'data-ocr-revisar-link': '', href: '/texto/', class: 'btn btn-success btn-sm' });
  link.textContent = 'Revisar texto';
  link.hidden = true;
  [badge, erro, disparo, retry, link, revisar, atualizar, motivo].forEach((filho) => card.appendChild(filho));
  return { card, badge, erro, disparo, retry, revisar, atualizar, motivo, link };
}

function criarInputCsrf() {
  const input = criarElemento('input', { name: 'csrfmiddlewaretoken' });
  input.value = 'token-teste';
  return input;
}

function criarDocumento(filhos) {
  const raiz = criarElemento('body');
  (filhos || []).forEach((filho) => raiz.appendChild(filho));
  return {
    listeners: {},
    addEventListener(evento, fn) {
      (this.listeners[evento] = this.listeners[evento] || []).push(fn);
    },
    querySelector(seletor) {
      return buscarDescendentes(raiz, seletor, false);
    },
    querySelectorAll(seletor) {
      return buscarDescendentes(raiz, seletor, true);
    },
  };
}

function dispararDomContentLoaded(documento) {
  (documento.listeners['DOMContentLoaded'] || []).forEach((fn) => fn());
}

// ---------- mock de timers (window.setTimeout enfileira) ----------

let filaTimers = [];

function resetarTimers() {
  filaTimers = [];
}

function setTimeoutMock(fn) {
  filaTimers.push({ fn });
  return filaTimers.length;
}

function executarTimers() {
  let guarda = 0;
  while (filaTimers.length && guarda++ < 2000) filaTimers.shift().fn();
}

async function aguardarMicrotarefas() {
  for (let i = 0; i < 10; i++) await new Promise((r) => setImmediate(r));
}

// ---------- sandbox (fetch configurável, reload registrado) ----------

function criarAmbiente(opcoes) {
  const op = opcoes || {};
  const chamadasFetch = [];
  const recargas = [];
  const pendentes = [];
  const respostas = (op.respostas || []).slice();

  const fetchMock = function (url, opts) {
    chamadasFetch.push({ url: String(url), metodo: (opts && opts.method) || 'GET', opts: opts });
    const r = respostas.length
      ? respostas.shift()
      : { status: 500, corpo: { error: 'sem resposta configurada no harness' } };
    if (r.pendente) {
      return new Promise((resolve) => pendentes.push({ resolve: resolve, resposta: r }));
    }
    if (r.erroRede) return Promise.reject(new Error(r.erroRede));
    return Promise.resolve({
      ok: r.status >= 200 && r.status < 300,
      status: r.status,
      json() {
        return Promise.resolve(r.corpo);
      },
    });
  };

  const documento = criarDocumento(op.filhos);
  const sandbox = {
    document: documento,
    fetch: fetchMock,
    window: {
      setTimeout: setTimeoutMock,
      location: {
        reload() {
          recargas.push(1);
        },
      },
    },
  };
  return { sandbox, documento, chamadasFetch, recargas, pendentes, respostas };
}

function carregarScript(sandbox) {
  const codigo = fs.readFileSync(CAMINHO_JS, 'utf8');
  vm.runInNewContext(codigo, sandbox, { filename: 'ocr_card.js' });
}

// ---------- casos ----------

const casos = [];

function caso(nome, fn) {
  casos.push({ nome: nome, fn: fn });
}

// 1. ativo → terminal
caso('ativo → terminal: polling consulta, pinta badge e para os timers', async () => {
  resetarTimers();
  const partes = criarCard({
    'data-status-ativos': '["pendente","processando"]',
    'data-status-com-texto': '["concluido"]',
    'data-criar-url': '/criar',
    'data-status-url': '/status',
    'data-ocr-status': 'pendente',
  });
  partes.disparo.disabled = true; // job ativo: botão visível mas desabilitado
  const amb = criarAmbiente({
    filhos: [partes.card, criarInputCsrf()],
    respostas: [
      { status: 200, corpo: { status: 'pendente', status_display: 'Na fila', progresso: { texto: 'aguardando' } } },
      { status: 200, corpo: { status: 'concluido', status_display: 'Concluído' } },
    ],
  });
  carregarScript(amb.sandbox);
  dispararDomContentLoaded(amb.documento);
  await aguardarMicrotarefas();
  afirmarIgual(amb.chamadasFetch.length, 1, '1º GET de status dispara no DOMContentLoaded');
  executarTimers();
  await aguardarMicrotarefas();
  afirmarIgual(amb.chamadasFetch.length, 2, '2º GET de status via polling');
  afirmar(amb.chamadasFetch.every((c) => c.url === '/status'), 'GETs de status vão para a data-status-url');
  afirmar(filaTimers.length === 0, 'timers param quando o status vira terminal');
  afirmarIgual(partes.badge.textContent, 'Concluído', 'badge mostra o status_display');
  afirmarIgual(partes.badge.className, 'badge bg-success', 'badge verde para status com texto');
  afirmarIgual(partes.disparo.hidden, true, 'disparo escondido no estado terminal');
  afirmarIgual(partes.revisar.hidden, false, 'botão Revisar texto visível no estado terminal');
  afirmarIgual(partes.motivo.hidden, false, 'motivo do revisar acompanha o botão');
  afirmarIgual(partes.atualizar.hidden, true, 'Atualizar status continua escondido');
});

// 2. 5 falhas seguidas → retomada
caso('5 falhas seguidas → erro visível + retomada pelo "Atualizar status"', async () => {
  resetarTimers();
  const partes = criarCard({
    'data-status-ativos': '["pendente"]',
    'data-status-com-texto': '["concluido"]',
    'data-status-url': '/status',
    'data-ocr-status': 'pendente',
  });
  const respostas = [];
  for (let i = 0; i < 5; i++) respostas.push({ erroRede: 'conexão recusada' });
  respostas.push({ status: 200, corpo: { status: 'concluido', status_display: 'Concluído' } });
  const amb = criarAmbiente({ filhos: [partes.card], respostas: respostas });
  carregarScript(amb.sandbox);
  dispararDomContentLoaded(amb.documento);
  for (let i = 0; i < 7; i++) {
    await aguardarMicrotarefas();
    executarTimers();
  }
  await aguardarMicrotarefas();
  afirmarIgual(amb.chamadasFetch.length, 5, 'desiste após 5 GETs que falharam');
  afirmarIgual(partes.erro.hidden, false, 'erro visível após o corte de falhas');
  afirmar(partes.erro.textContent.indexOf('Não foi possível consultar') !== -1, 'mensagem de erro é a da consulta de status');
  afirmarIgual(partes.atualizar.hidden, false, 'botão Atualizar status aparece para retomar');

  const antes = amb.chamadasFetch.length;
  partes.atualizar.click();
  afirmarIgual(partes.atualizar.hidden, true, 'Atualizar status se esconde ao ser usado');
  await aguardarMicrotarefas();
  afirmarIgual(amb.chamadasFetch.length, antes + 1, 'clique no Atualizar refaz a consulta');
  afirmarIgual(partes.badge.textContent, 'Concluído', 'badge atualizado após a retomada');
  afirmarIgual(partes.atualizar.hidden, true, 'Atualizar status permanece escondido após o sucesso');
  afirmar(filaTimers.length === 0, 'sem timer pendente após a retomada com sucesso');
});

// 3. 201 e 409 → reload
caso('POST 201 e 409 recarregam a página', async () => {
  for (const status of [201, 409]) {
    resetarTimers();
    const partes = criarCard({
      'data-criar-url': '/criar',
      'data-status-ativos': '[]',
      'data-status-com-texto': '["concluido"]',
    });
    const amb = criarAmbiente({
      filhos: [partes.card, criarInputCsrf()],
      respostas: [{ status: status, corpo: {} }],
    });
    carregarScript(amb.sandbox);
    dispararDomContentLoaded(amb.documento);
    partes.disparo.click();
    await aguardarMicrotarefas();
    afirmarIgual(amb.recargas.length, 1, 'POST ' + status + ' recarrega a página');
    afirmarIgual(amb.chamadasFetch.length, 1, 'POST ' + status + ' faz exatamente 1 fetch');
    afirmarIgual(amb.chamadasFetch[0].metodo, 'POST', 'requisição é POST');
    afirmarIgual(amb.chamadasFetch[0].url, '/criar', 'POST vai para a data-criar-url');
    afirmar(amb.chamadasFetch[0].opts.headers['X-CSRFToken'] === 'token-teste', 'POST leva o X-CSRFToken do formulário');
  }
});

// 4. guarda de duplo clique (P2 "Retry stays clickable")
caso('guarda de duplo clique: retry com POST pendente não dispara 2º POST; falha reabilita os dois', async () => {
  resetarTimers();
  const partes = criarCard({
    'data-criar-url': '/criar',
    'data-status-ativos': '[]',
    'data-status-com-texto': '["concluido"]',
  });
  const amb = criarAmbiente({
    filhos: [partes.card, criarInputCsrf()],
    respostas: [{ pendente: true }],
  });
  carregarScript(amb.sandbox);
  dispararDomContentLoaded(amb.documento);

  partes.disparo.click();
  afirmarIgual(amb.chamadasFetch.length, 1, '1º clique dispara o POST');
  afirmarIgual(partes.disparo.disabled, true, 'disparo desabilita durante o POST');
  afirmarIgual(partes.retry.disabled, true, 'retry também desabilita durante o POST');

  partes.retry.click(); // resposta do POST ainda pendente
  afirmarIgual(amb.chamadasFetch.length, 1, 'retry clicado com POST pendente NÃO dispara 2º POST');

  partes.disparo.click();
  afirmarIgual(amb.chamadasFetch.length, 1, 'disparo clicado de novo com POST pendente NÃO dispara 2º POST');

  // servidor responde 500 → os dois botões voltam, sem reload
  amb.pendentes[0].resolve({ ok: false, status: 500, json: () => Promise.resolve({ error: 'boom' }) });
  await aguardarMicrotarefas();
  afirmarIgual(amb.recargas.length, 0, '500 não recarrega a página');
  afirmarIgual(partes.disparo.disabled, false, 'disparo reabilitado após 500');
  afirmarIgual(partes.retry.disabled, false, 'retry reabilitado após 500');
  afirmarIgual(partes.erro.hidden, false, 'erro visível após 500');
  afirmar(partes.erro.textContent.indexOf('boom') !== -1, 'mensagem do servidor aparece no erro');

  // segunda tentativa falha na rede → também reabilita os dois
  amb.respostas.push({ erroRede: 'offline' });
  partes.disparo.click();
  afirmarIgual(amb.chamadasFetch.length, 2, 'após reabilitar, novo POST parte');
  await aguardarMicrotarefas();
  afirmarIgual(partes.disparo.disabled, false, 'disparo reabilitado após falha de rede');
  afirmarIgual(partes.retry.disabled, false, 'retry reabilitado após falha de rede');
  afirmarIgual(amb.recargas.length, 0, 'falha de rede não recarrega a página');
});

// 5. card sem job (sem data-status-url)
caso('sem data-status-url: nenhum GET de status e botão de retomada escondido', async () => {
  resetarTimers();
  const partes = criarCard({
    'data-criar-url': '/criar',
    'data-status-ativos': '["pendente"]',
    'data-status-com-texto': '["concluido"]',
  });
  const amb = criarAmbiente({ filhos: [partes.card] });
  carregarScript(amb.sandbox);
  dispararDomContentLoaded(amb.documento);
  await aguardarMicrotarefas();
  afirmarIgual(amb.chamadasFetch.length, 0, 'nenhum fetch de status sem data-status-url');
  afirmar(filaTimers.length === 0, 'nenhum polling agendado');
  afirmarIgual(partes.atualizar.hidden, true, 'botão de retomada continua escondido');
});

// 6. I-4: ativo → concluido libera o link "Revisar texto"
caso('ativo → concluido: link Revisar texto aparece e o botão desabilitado sai', async () => {
  resetarTimers();
  const partes = criarCard({
    'data-status-ativos': '["pendente"]',
    'data-status-com-texto': '["concluido","texto_confirmado"]',
    'data-status-revisaveis': '["concluido"]',
    'data-status-url': '/status',
    'data-ocr-status': 'pendente',
  });
  const amb = criarAmbiente({
    filhos: [partes.card],
    respostas: [
      { status: 200, corpo: { status: 'pendente', status_display: 'Na fila' } },
      { status: 200, corpo: { status: 'concluido', status_display: 'Concluído' } },
    ],
  });
  carregarScript(amb.sandbox);
  dispararDomContentLoaded(amb.documento);
  await aguardarMicrotarefas();
  afirmarIgual(partes.link.hidden, true, 'link escondido enquanto o OCR está ativo');
  executarTimers();
  await aguardarMicrotarefas();
  afirmarIgual(partes.link.hidden, false, 'link Revisar texto visível com o job concluído');
  afirmarIgual(partes.link.getAttribute('href'), '/texto/', 'o link mantém o href da tela de confirmação');
  afirmarIgual(partes.revisar.hidden, true, 'botão desabilitado some quando o texto é revisável');
  afirmarIgual(partes.motivo.hidden, true, 'motivo some junto do botão desabilitado');
  afirmarIgual(partes.disparo.hidden, true, 'disparo escondido no estado terminal');
  afirmar(filaTimers.length === 0, 'timers param no estado terminal');
});

// 7. I-4: texto já confirmado → botão desabilitado com a explicação
caso('texto_confirmado: Revisar texto fica desabilitado com o motivo e sem link', async () => {
  resetarTimers();
  const partes = criarCard({
    'data-status-ativos': '["pendente"]',
    'data-status-com-texto': '["concluido","texto_confirmado"]',
    'data-status-revisaveis': '["concluido"]',
    'data-status-url': '/status',
    'data-ocr-status': 'pendente',
  });
  partes.link.hidden = false; // estado anterior: link visível
  const amb = criarAmbiente({
    filhos: [partes.card],
    respostas: [{ status: 200, corpo: { status: 'texto_confirmado', status_display: 'Texto confirmado' } }],
  });
  carregarScript(amb.sandbox);
  dispararDomContentLoaded(amb.documento);
  await aguardarMicrotarefas();
  afirmarIgual(partes.link.hidden, true, 'sem link depois da confirmação do texto');
  afirmarIgual(partes.revisar.hidden, false, 'botão Revisar texto visível (desabilitado)');
  afirmarIgual(partes.motivo.hidden, false, 'motivo visível junto do botão');
  afirmarIgual(partes.badge.textContent, 'Texto confirmado', 'badge mostra o status_display');
});

// 8. cards sem o link (renderizados sem job) e sem a lista de revisáveis
caso('sem data-status-revisaveis ou sem o link: mantém o botão desabilitado e não quebra', async () => {
  resetarTimers();
  const semLista = criarCard({
    'data-status-ativos': '["pendente"]',
    'data-status-com-texto': '["concluido"]',
    'data-status-url': '/status',
    'data-ocr-status': 'pendente',
  });
  const amb1 = criarAmbiente({
    filhos: [semLista.card],
    respostas: [{ status: 200, corpo: { status: 'concluido', status_display: 'Concluído' } }],
  });
  carregarScript(amb1.sandbox);
  dispararDomContentLoaded(amb1.documento);
  await aguardarMicrotarefas();
  afirmarIgual(semLista.link.hidden, true, 'sem a lista de revisáveis o link continua escondido');
  afirmarIgual(semLista.revisar.hidden, false, 'sem a lista, o botão desabilitado continua visível');

  resetarTimers();
  const semLink = criarCard({
    'data-status-ativos': '["pendente"]',
    'data-status-com-texto': '["concluido"]',
    'data-status-revisaveis': '["concluido"]',
    'data-status-url': '/status',
    'data-ocr-status': 'pendente',
  });
  semLink.card.children = semLink.card.children.filter((filho) => filho !== semLink.link);
  const amb2 = criarAmbiente({
    filhos: [semLink.card],
    respostas: [{ status: 200, corpo: { status: 'concluido', status_display: 'Concluído' } }],
  });
  carregarScript(amb2.sandbox);
  dispararDomContentLoaded(amb2.documento);
  await aguardarMicrotarefas();
  afirmarIgual(semLink.revisar.hidden, false, 'sem o elemento de link, cai para o botão desabilitado');
  afirmarIgual(semLink.badge.textContent, 'Concluído', 'a pintura do badge não é interrompida');
});

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
