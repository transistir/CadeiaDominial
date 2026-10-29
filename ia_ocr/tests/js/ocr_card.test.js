/**
 * Testes do card "Extrair texto com IA" (static/dominial/js/ocr_card.js).
 *
 * Node puro, sem dependências novas: o JS é lido com fs.readFileSync e
 * avaliado com vm.runInNewContext num sandbox com DOM/fetch/timers mockados
 * à mão. Fecha o P2 "Polling lacks automated tests" do Greptile no PR #279.
 * Casos I-4 (#261): "Revisar texto" vira link com o job concluído.
 * Casos #307 (I-9): expectativa com tempo decorrido, progresso zerado sem
 * "página 0 de N" e backoff de reconexão — com relógio controlável (agoraMs),
 * sem esperar tempo real. Rodada 2 (#307): tempo fora do badge (P1), geração
 * contra corrida de respostas em voo, corte de 10 min coerente, região viva
 * própria do "Reconectando…", erros permanentes (404/redirect) e cobertura do
 * reset do backoff. Rodada 3 (#307): texto próprio do erro permanente
 * (404/redirect), região viva limpa na retomada, rejeição órfã sem escrita nem
 * agendamento e escrita única do aviso.
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
  // #307 (rodada 2): expectativa (tempo decorrido, sem aria-live) nasce
  // escondida e VAZIA, como no template — o texto é da constante do JS.
  // Reconectando é região viva própria: sempre no DOM, vazia e sem hidden.
  const expectativa = criarElemento('small', { 'data-ocr-expectativa': '', class: 'text-muted d-block mt-1' });
  expectativa.hidden = true;
  const reconectando = criarElemento('small', {
    'data-ocr-reconectando': '', role: 'status', 'aria-live': 'polite', class: 'text-muted d-block mt-1',
  });
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
  [badge, erro, expectativa, reconectando, disparo, retry, link, revisar, atualizar, motivo].forEach(
    (filho) => card.appendChild(filho)
  );
  return { card, badge, erro, expectativa, reconectando, disparo, retry, revisar, atualizar, motivo, link };
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

// ---------- mock de timers com relógio controlável (#307) ----------
//
// setTimeout/setInterval enfileiram com o vencimento no relógio virtual
// (agoraMs); avancarTempo(ms) executa os vencidos em ordem. Nenhum caso
// espera tempo real.

const EPOCA = Date.parse('2026-10-29T12:00:00Z');
let agoraMs = EPOCA;
let filaTimers = [];
let proximoIdTimer = 1;

function resetarTimers() {
  agoraMs = EPOCA;
  filaTimers = [];
  proximoIdTimer = 1;
}

function agendar(id, fn, atraso, passo) {
  filaTimers.push({ id: id, fn: fn, quando: agoraMs + (atraso || 0), passo: passo || 0 });
  return id;
}

function setTimeoutMock(fn, atraso) {
  return agendar(proximoIdTimer++, fn, atraso, 0);
}

function setIntervalMock(fn, atraso) {
  return agendar(proximoIdTimer++, fn, atraso, atraso || 0);
}

function limparTimer(id) {
  filaTimers = filaTimers.filter((t) => t.id !== id);
}

function avancarTempo(ms) {
  const fim = agoraMs + ms;
  let eventos = 0;
  for (;;) {
    const vencidos = filaTimers.filter((t) => t.quando <= fim);
    if (!vencidos.length) break;
    let proximo = vencidos[0];
    for (const t of vencidos) if (t.quando < proximo.quando) proximo = t;
    limparTimer(proximo.id);
    agoraMs = Math.max(agoraMs, proximo.quando);
    // Intervalo se reagenda a partir do disparo; timeout não.
    if (proximo.passo) agendar(proximo.id, proximo.fn, proximo.passo, proximo.passo);
    if (++eventos > 10000) throw new Error('mais de 10000 eventos de timer ao avançar ' + ms + ' ms');
    proximo.fn();
  }
  agoraMs = fim;
}

// Timers de polling (setTimeout); passo > 0 marca os intervalos do contador.
function timersDePolling() {
  return filaTimers.filter((t) => !t.passo);
}

async function aguardarMicrotarefas() {
  for (let i = 0; i < 10; i++) await new Promise((r) => setImmediate(r));
}

// criado_em em ISO, `segundos` no passado do relógio virtual.
function isoAtrasado(segundos) {
  return new Date(agoraMs - segundos * 1000).toISOString();
}

// ---------- sandbox (fetch configurável, reload registrado, Date controlável) ----------

function criarClasseDate() {
  const HostDate = Date;
  function DateMock(valor) {
    if (!(this instanceof DateMock)) return String(agoraMs);
    if (valor === undefined) this._ms = agoraMs;
    else if (typeof valor === 'string') this._ms = HostDate.parse(valor);
    else this._ms = Number(valor);
  }
  DateMock.prototype.getTime = function () {
    return this._ms;
  };
  DateMock.now = function () {
    return agoraMs;
  };
  DateMock.parse = function (iso) {
    return HostDate.parse(iso);
  };
  return DateMock;
}

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
      return new Promise((resolve, reject) => pendentes.push({ resolve: resolve, reject: reject, resposta: r }));
    }
    if (r.erroRede) return Promise.reject(new Error(r.erroRede));
    return Promise.resolve({
      ok: r.status >= 200 && r.status < 300,
      status: r.status,
      redirected: !!r.redirected,
      json() {
        return Promise.resolve(r.corpo);
      },
    });
  };

  const documento = criarDocumento(op.filhos);
  const sandbox = {
    document: documento,
    fetch: fetchMock,
    Date: criarClasseDate(),
    window: {
      setTimeout: setTimeoutMock,
      clearTimeout: limparTimer,
      setInterval: setIntervalMock,
      clearInterval: limparTimer,
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
caso('ativo → terminal: polling consulta, pinta badge, esconde a expectativa e para os timers', async () => {
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
  afirmarIgual(partes.expectativa.hidden, false, 'job ativo mostra a linha de expectativa');
  avancarTempo(3000);
  await aguardarMicrotarefas();
  afirmarIgual(amb.chamadasFetch.length, 2, '2º GET de status via polling');
  afirmar(amb.chamadasFetch.every((c) => c.url === '/status'), 'GETs de status vão para a data-status-url');
  afirmarIgual(filaTimers.length, 0, 'timers (e contador) param quando o status vira terminal');
  afirmarIgual(partes.badge.textContent, 'Concluído', 'badge mostra o status_display');
  afirmarIgual(partes.badge.className, 'badge bg-success', 'badge verde para status com texto');
  afirmarIgual(partes.disparo.hidden, true, 'disparo escondido no estado terminal');
  afirmarIgual(partes.revisar.hidden, false, 'botão Revisar texto visível no estado terminal');
  afirmarIgual(partes.motivo.hidden, false, 'motivo do revisar acompanha o botão');
  afirmarIgual(partes.atualizar.hidden, true, 'Atualizar status continua escondido');
  afirmarIgual(partes.expectativa.hidden, true, 'expectativa escondida no estado terminal');
  afirmarIgual(partes.reconectando.textContent, '', 'Reconectando segue vazio sem falha de rede');
});

// 2. R1 (#307): expectativa com o tempo decorrido, atualizando a cada 1 s
caso('R1: expectativa mostra o tempo desde criado_em e anda a cada 1 s', async () => {
  resetarTimers();
  const partes = criarCard({
    'data-status-ativos': '["pendente","em_execucao"]',
    'data-status-com-texto': '["concluido"]',
    'data-status-url': '/status',
    'data-ocr-status': 'pendente',
    'data-ocr-criado-em': isoAtrasado(90),
  });
  const amb = criarAmbiente({ filhos: [partes.card], respostas: [{ pendente: true }] });
  carregarScript(amb.sandbox);
  dispararDomContentLoaded(amb.documento);
  await aguardarMicrotarefas();
  afirmarIgual(partes.expectativa.hidden, false, 'linha de expectativa visível com job ativo');
  afirmarIgual(
    partes.expectativa.textContent,
    'O processamento pode levar alguns minutos. Tempo decorrido: 1 min 30 s',
    'texto inteiro da expectativa com o tempo desde criado_em'
  );
  avancarTempo(1000);
  await aguardarMicrotarefas();
  afirmarIgual(
    partes.expectativa.textContent,
    'O processamento pode levar alguns minutos. Tempo decorrido: 1 min 31 s',
    '+1 s no relógio → texto inteiro substituído (indexOf não casaria "11 min" com "1 min")'
  );
});

// 3. R2 (#307): progresso zerado não vira "página 0 de N"
caso('R2: em_execucao com progresso.pagina 0 → badge "processando…", nunca "página 0 de"', async () => {
  resetarTimers();
  const partes = criarCard({
    'data-status-ativos': '["pendente","em_execucao"]',
    'data-status-com-texto': '["concluido"]',
    'data-status-url': '/status',
    'data-ocr-status': 'pendente',
    'data-ocr-criado-em': isoAtrasado(84),
  });
  const amb = criarAmbiente({
    filhos: [partes.card],
    respostas: [
      {
        status: 200,
        corpo: {
          status: 'em_execucao',
          status_display: 'Em execução',
          progresso: { pagina: 0, total: 2, texto: 'página 0 de 2' },
        },
      },
    ],
  });
  carregarScript(amb.sandbox);
  dispararDomContentLoaded(amb.documento);
  await aguardarMicrotarefas();
  afirmarIgual(
    partes.badge.textContent,
    'Em execução — processando…',
    'badge mostra processando…, sem tempo (o tempo é da expectativa, fora do aria-live)'
  );
  afirmar(partes.badge.textContent.indexOf('página 0 de') === -1, 'nunca exibe "página 0 de N"');
});

// 4. R2 (#307): com página > 0, mantém o comportamento atual
caso('R2: em_execucao com progresso.pagina 2 de 3 → badge "Em execução — página 2 de 3"', async () => {
  resetarTimers();
  const partes = criarCard({
    'data-status-ativos': '["pendente","em_execucao"]',
    'data-status-com-texto': '["concluido"]',
    'data-status-url': '/status',
    'data-ocr-status': 'pendente',
  });
  const amb = criarAmbiente({
    filhos: [partes.card],
    respostas: [
      {
        status: 200,
        corpo: {
          status: 'em_execucao',
          status_display: 'Em execução',
          progresso: { pagina: 2, total: 3, texto: 'página 2 de 3' },
        },
      },
    ],
  });
  carregarScript(amb.sandbox);
  dispararDomContentLoaded(amb.documento);
  await aguardarMicrotarefas();
  afirmarIgual(partes.badge.textContent, 'Em execução — página 2 de 3', 'com página > 0 o badge não muda');
});

// 5. R3 (#307): backoff de reconexão 3 s → 5 s → 10 s
caso('R3: falhas consecutivas entram em backoff 3 s, 5 s, 10 s com "Reconectando…" visível', async () => {
  resetarTimers();
  const partes = criarCard({
    'data-status-ativos': '["pendente","em_execucao"]',
    'data-status-com-texto': '["concluido"]',
    'data-status-url': '/status',
    'data-ocr-status': 'pendente',
  });
  const falha = { erroRede: 'conexão recusada' };
  const amb = criarAmbiente({
    filhos: [partes.card],
    respostas: [falha, falha, falha, { status: 200, corpo: { status: 'pendente', status_display: 'Pendente' } }],
  });
  carregarScript(amb.sandbox);
  dispararDomContentLoaded(amb.documento);
  await aguardarMicrotarefas();
  afirmarIgual(amb.chamadasFetch.length, 1, '1º GET parte no DOMContentLoaded');
  afirmarIgual(partes.reconectando.textContent, 'Reconectando…', 'região viva recebe o aviso já na 1ª falha');
  afirmarIgual(partes.erro.hidden, true, '[data-ocr-erro] continua escondido na falha de rede');

  avancarTempo(2500);
  await aguardarMicrotarefas();
  afirmarIgual(amb.chamadasFetch.length, 1, '1ª falha → próxima consulta só em 3 s');
  avancarTempo(500);
  await aguardarMicrotarefas();
  afirmarIgual(amb.chamadasFetch.length, 2, '2ª consulta acontece após os 3 s');
  afirmarIgual(partes.reconectando.textContent, 'Reconectando…', 'texto do reconectando');

  avancarTempo(4000);
  await aguardarMicrotarefas();
  afirmarIgual(amb.chamadasFetch.length, 2, '2ª falha → próxima consulta só em 5 s');
  avancarTempo(1000);
  await aguardarMicrotarefas();
  afirmarIgual(amb.chamadasFetch.length, 3, '3ª consulta acontece após os 5 s');

  avancarTempo(9000);
  await aguardarMicrotarefas();
  afirmarIgual(amb.chamadasFetch.length, 3, '3ª falha → próxima consulta só em 10 s');
  avancarTempo(1000);
  await aguardarMicrotarefas();
  afirmarIgual(amb.chamadasFetch.length, 4, '4ª consulta acontece após os 10 s');
  afirmarIgual(partes.erro.hidden, true, 'erro do OCR continua escondido durante as falhas');
  afirmarIgual(
    partes.badge.textContent,
    'Pendente — na fila',
    'badge de pendente ganha a situação, sem tempo (pintado na 4ª consulta, t=18 s)'
  );
});

// 6. R3 (#307): sucesso depois de falhas
caso('R3: sucesso após falhas limpa o texto "Reconectando…" e o polling volta ao intervalo de 3 s', async () => {
  resetarTimers();
  const partes = criarCard({
    'data-status-ativos': '["pendente","em_execucao"]',
    'data-status-com-texto': '["concluido"]',
    'data-status-url': '/status',
    'data-ocr-status': 'pendente',
  });
  const amb = criarAmbiente({
    filhos: [partes.card],
    respostas: [
      { erroRede: 'conexão recusada' },
      { erroRede: 'conexão recusada' },
      { status: 200, corpo: { status: 'pendente', status_display: 'Pendente' } },
      { status: 200, corpo: { status: 'concluido', status_display: 'Concluído' } },
    ],
  });
  carregarScript(amb.sandbox);
  dispararDomContentLoaded(amb.documento);
  await aguardarMicrotarefas();
  avancarTempo(3000); // 2ª consulta: falha
  await aguardarMicrotarefas();
  afirmarIgual(partes.reconectando.textContent, 'Reconectando…', 'aviso escrito durante as falhas');
  avancarTempo(5000); // 3ª consulta: sucesso
  await aguardarMicrotarefas();
  afirmarIgual(partes.reconectando.textContent, '', 'sucesso limpa o Reconectando…');
  afirmarIgual(partes.erro.hidden, true, 'nenhum erro de OCR por falha de rede');
  afirmarIgual(partes.badge.textContent, 'Pendente — na fila', 'badge repinta com a situação, sem tempo');

  avancarTempo(2500); // sucesso → volta ao intervalo normal de 3 s
  await aguardarMicrotarefas();
  afirmarIgual(amb.chamadasFetch.length, 3, 'após o sucesso, nada antes de 3 s');
  avancarTempo(500);
  await aguardarMicrotarefas();
  afirmarIgual(amb.chamadasFetch.length, 4, '4ª consulta após os 3 s do sucesso');
  afirmarIgual(filaTimers.length, 0, 'terminal chega e para tudo');
});

// 7. R3 (#307): falhas de rede nunca viram falha do OCR nem param o polling
caso('R3: 6 falhas seguidas não mostram erro de OCR e não param o polling', async () => {
  resetarTimers();
  const partes = criarCard({
    'data-status-ativos': '["pendente","em_execucao"]',
    'data-status-com-texto': '["concluido"]',
    'data-status-url': '/status',
    'data-ocr-status': 'pendente',
  });
  const respostas = [];
  for (let i = 0; i < 6; i++) respostas.push({ erroRede: 'conexão recusada' });
  respostas.push({ status: 200, corpo: { status: 'concluido', status_display: 'Concluído' } });
  const amb = criarAmbiente({ filhos: [partes.card], respostas });
  carregarScript(amb.sandbox);
  dispararDomContentLoaded(amb.documento);
  await aguardarMicrotarefas();
  for (let i = 0; i < 8; i++) {
    avancarTempo(10000);
    await aguardarMicrotarefas();
  }
  afirmarIgual(amb.chamadasFetch.length, 7, 'as 6 falhas não param o polling: a 7ª consulta acontece');
  afirmarIgual(partes.erro.hidden, true, '[data-ocr-erro] continua escondido');
  afirmar(partes.erro.textContent.indexOf('Falha no processamento') === -1, 'texto de falha do OCR não aparece');
  afirmar(
    partes.erro.textContent.indexOf('Não foi possível consultar') === -1,
    'texto de falha de consulta não aparece'
  );
  afirmarIgual(partes.badge.textContent, 'Concluído', 'o payload do backend continua mandando no estado');
  afirmarIgual(filaTimers.length, 0, 'ao chegar o terminal, para de vez');
});

// 8. R3 (#307): rede de segurança de 10 min + retomada pelo "Atualizar status"
caso('R3: 10 min de falhas cortam tudo (aviso novo, sem timers) e a retomada funciona', async () => {
  resetarTimers();
  const partes = criarCard({
    'data-status-ativos': '["pendente","em_execucao"]',
    'data-status-com-texto': '["concluido"]',
    'data-status-url': '/status',
    'data-ocr-status': 'pendente',
    'data-ocr-criado-em': isoAtrasado(60),
  });
  const falha = { erroRede: 'conexão recusada' };
  const respostas = [];
  for (let i = 0; i < 70; i++) respostas.push(falha);
  const amb = criarAmbiente({ filhos: [partes.card], respostas });
  carregarScript(amb.sandbox);
  dispararDomContentLoaded(amb.documento);
  await aguardarMicrotarefas();
  for (let i = 0; i < 80; i++) {
    avancarTempo(10000);
    await aguardarMicrotarefas();
  }
  // Determinístico no harness: 1ª consulta (e 1ª falha) em t=0 e uma por
  // janela de 10 s (o catch roda no fim da janela de avancarTempo) — o catch
  // da 61ª, em t=600 s, atinge os 10 min desde a 1ª falha e corta.
  afirmarIgual(amb.chamadasFetch.length, 61, 'backoff 3 s → 5 s → 10 s até o corte de 10 min');
  avancarTempo(60000);
  await aguardarMicrotarefas();
  afirmarIgual(amb.chamadasFetch.length, 61, 'depois do corte, nenhuma nova consulta');
  afirmarIgual(
    partes.reconectando.textContent,
    'Sem conexão com o servidor. Use "Atualizar status" para tentar de novo.',
    'corte troca o "Reconectando…" pela mensagem de sem conexão'
  );
  afirmarIgual(filaTimers.length, 0, 'corte cancela o polling E o contador (nenhum timer vivo)');
  afirmarIgual(partes.expectativa.hidden, true, 'contador para de vez no corte');
  afirmarIgual(partes.atualizar.hidden, false, 'botão Atualizar status revelado');
  afirmarIgual(partes.erro.hidden, true, 'sem texto de falha do OCR na rede de segurança');

  amb.respostas.unshift(
    { status: 200, corpo: { status: 'pendente', status_display: 'Pendente' } },
    { status: 200, corpo: { status: 'pendente', status_display: 'Pendente' } }
  );
  partes.atualizar.click();
  await aguardarMicrotarefas();
  afirmarIgual(amb.chamadasFetch.length, 62, 'Atualizar status retoma a consulta');
  afirmarIgual(partes.reconectando.textContent, '', 'sucesso na retomada limpa o aviso');
  afirmarIgual(partes.atualizar.hidden, true, 'Atualizar status se esconde ao ser usado');
  afirmarIgual(partes.expectativa.hidden, false, 'contador volta com o estado ativo');
  avancarTempo(3000);
  await aguardarMicrotarefas();
  afirmarIgual(amb.chamadasFetch.length, 63, 'polling retomado volta ao intervalo de 3 s');
});

// 9. R1 (#307): terminal esconde a expectativa e para o contador
caso('R1: estado concluido esconde a expectativa e não deixa timer pendente', async () => {
  resetarTimers();
  const partes = criarCard({
    'data-status-ativos': '["pendente","em_execucao"]',
    'data-status-com-texto': '["concluido"]',
    'data-status-url': '/status',
    'data-ocr-status': 'pendente',
    'data-ocr-criado-em': isoAtrasado(30),
  });
  const amb = criarAmbiente({
    filhos: [partes.card],
    respostas: [{ status: 200, corpo: { status: 'concluido', status_display: 'Concluído' } }],
  });
  carregarScript(amb.sandbox);
  dispararDomContentLoaded(amb.documento);
  await aguardarMicrotarefas();
  afirmarIgual(partes.expectativa.hidden, true, 'expectativa escondida já no 1º payload terminal');
  afirmarIgual(filaTimers.length, 0, 'nenhum timer pendente já no 1º payload terminal');
  avancarTempo(60000);
  await aguardarMicrotarefas();
  afirmarIgual(amb.chamadasFetch.length, 1, 'nenhuma nova consulta depois do terminal');
  afirmarIgual(filaTimers.length, 0, 'nenhum timer/interval novo após o terminal');
});

// 10. R3 (#307): dois cliques não criam um segundo loop
caso('R3: dois cliques em "Atualizar status" deixam um só loop de polling', async () => {
  resetarTimers();
  const partes = criarCard({
    'data-status-ativos': '["pendente","em_execucao"]',
    'data-status-com-texto': '["concluido"]',
    'data-status-url': '/status',
    'data-ocr-status': 'em_execucao',
    'data-ocr-criado-em': isoAtrasado(120),
  });
  const emExecucao = {
    status: 200,
    corpo: { status: 'em_execucao', status_display: 'Em execução', progresso: { pagina: 1, total: 3, texto: 'página 1 de 3' } },
  };
  const amb = criarAmbiente({
    filhos: [partes.card],
    respostas: [emExecucao, emExecucao, emExecucao, emExecucao],
  });
  carregarScript(amb.sandbox);
  dispararDomContentLoaded(amb.documento);
  await aguardarMicrotarefas();
  afirmarIgual(amb.chamadasFetch.length, 1, 'consulta inicial no DOMContentLoaded');
  afirmarIgual(timersDePolling().length, 1, 'um timer de polling agendado');

  // Dois cliques em sequência, com resposta do 1º ainda em voo: cada clique
  // faz exatamente uma consulta e só um loop de polling sobrevive.
  partes.atualizar.hidden = false;
  partes.atualizar.click();
  partes.atualizar.click();
  await aguardarMicrotarefas();
  afirmarIgual(amb.chamadasFetch.length, 3, 'cada clique faz exatamente uma consulta');
  afirmarIgual(timersDePolling().length, 1, 'só um timer de polling pendente após os dois cliques');

  avancarTempo(3000);
  await aguardarMicrotarefas();
  afirmarIgual(amb.chamadasFetch.length, 4, 'um único GET por tick de 3 s');
  afirmarIgual(timersDePolling().length, 1, 'loop único segue, sem timer órfão');
});

// 11. POST 201 e 409 → reload
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

// 12. guarda de duplo clique (P2 "Retry stays clickable")
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

// 13. card sem job (sem data-status-url)
caso('sem data-status-url: nenhum GET de status, contador parado e botão de retomada escondido', async () => {
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
  afirmarIgual(filaTimers.length, 0, 'nenhum polling nem contador agendados');
  afirmarIgual(partes.expectativa.hidden, true, 'sem job ativo, a expectativa fica escondida');
  afirmarIgual(partes.atualizar.hidden, true, 'botão de retomada continua escondido');
});

// 14. I-4: ativo → concluido libera o link "Revisar texto"
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
  avancarTempo(3000);
  await aguardarMicrotarefas();
  afirmarIgual(partes.link.hidden, false, 'link Revisar texto visível com o job concluído');
  afirmarIgual(partes.link.getAttribute('href'), '/texto/', 'o link mantém o href da tela de confirmação');
  afirmarIgual(partes.revisar.hidden, true, 'botão desabilitado some quando o texto é revisável');
  afirmarIgual(partes.motivo.hidden, true, 'motivo some junto do botão desabilitado');
  afirmarIgual(partes.disparo.hidden, true, 'disparo escondido no estado terminal');
  afirmarIgual(filaTimers.length, 0, 'timers param no estado terminal');
});

// 15. I-4: texto já confirmado → botão desabilitado com a explicação
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

// 16. cards sem o link (renderizados sem job) e sem a lista de revisáveis
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

// 17. P1 (rodada 2): o tempo saiu do badge — polls consecutivos não o reescrevem
caso('P1: polls ativos consecutivos não reescrevem o badge (sem tempo no aria-live)', async () => {
  resetarTimers();
  const partes = criarCard({
    'data-status-ativos': '["pendente","em_execucao"]',
    'data-status-com-texto': '["concluido"]',
    'data-status-url': '/status',
    'data-ocr-status': 'pendente',
  });
  const pendente = { status: 200, corpo: { status: 'pendente', status_display: 'Pendente' } };
  const amb = criarAmbiente({ filhos: [partes.card], respostas: [pendente, pendente] });
  carregarScript(amb.sandbox);
  let escritas = 0;
  let valorBadge = partes.badge.textContent;
  Object.defineProperty(partes.badge, 'textContent', {
    get() {
      return valorBadge;
    },
    set(novo) {
      escritas += 1;
      valorBadge = novo;
    },
  });
  dispararDomContentLoaded(amb.documento);
  await aguardarMicrotarefas();
  avancarTempo(3000);
  await aguardarMicrotarefas();
  afirmarIgual(amb.chamadasFetch.length, 2, 'dois polls ativos aconteceram');
  afirmarIgual(escritas, 1, 'só a 1ª repintura escreve no badge; a 2ª é guardada pelo definirTexto');
  afirmarIgual(partes.badge.textContent, 'Pendente — na fila', 'badge com a situação, sem tempo');
  afirmarIgual(filaTimers.length, 2, 'polling e contador seguem ativos');
});

// 18. P2 (rodada 2): corrida de resposta em voo contra o terminal
caso('P2: resposta ativa atrasada resolvida depois do terminal não religa polling nem contador', async () => {
  resetarTimers();
  const partes = criarCard({
    'data-status-ativos': '["pendente","em_execucao"]',
    'data-status-com-texto': '["concluido"]',
    'data-status-url': '/status',
    'data-ocr-status': 'em_execucao',
    'data-ocr-criado-em': isoAtrasado(30),
  });
  const amb = criarAmbiente({
    filhos: [partes.card],
    respostas: [
      { pendente: true },
      { status: 200, corpo: { status: 'concluido', status_display: 'Concluído' } },
    ],
  });
  carregarScript(amb.sandbox);
  dispararDomContentLoaded(amb.documento);
  await aguardarMicrotarefas();
  afirmarIgual(amb.chamadasFetch.length, 1, '1º GET em voo (pendente no harness)');

  // O usuário força nova consulta: a geração avança e o 1º GET, ainda em
  // voo, vira órfão. A resposta nova chega primeiro — e é terminal.
  partes.atualizar.hidden = false;
  partes.atualizar.click();
  await aguardarMicrotarefas();
  afirmarIgual(amb.chamadasFetch.length, 2, 'clique no Atualizar dispara o 2º GET');
  afirmarIgual(partes.badge.textContent, 'Concluído', 'terminal pinta o badge');
  afirmarIgual(filaTimers.length, 0, 'terminal cancela polling e contador');

  // Só depois chega a resposta ativa atrasada — deve ser descartada.
  amb.pendentes[0].resolve({
    ok: true,
    status: 200,
    json: () => Promise.resolve({ status: 'em_execucao', status_display: 'Em execução', progresso: null }),
  });
  await aguardarMicrotarefas();
  afirmarIgual(amb.chamadasFetch.length, 2, 'resposta órfã não agenda nova consulta');
  afirmarIgual(filaTimers.length, 0, 'resposta órfã não religa contador nem polling');
  afirmarIgual(partes.badge.textContent, 'Concluído', 'badge permanece no estado terminal');
  afirmarIgual(partes.expectativa.hidden, true, 'expectativa permanece escondida');
  afirmarIgual(partes.reconectando.textContent, '', 'sem aviso de reconexão');
});

// 19. P2 (rodada 2): sucesso resetando o backoff
caso('P2: falha, falha, sucesso, falha → backoff resetado, próxima consulta em 3 s', async () => {
  resetarTimers();
  const partes = criarCard({
    'data-status-ativos': '["pendente","em_execucao"]',
    'data-status-com-texto': '["concluido"]',
    'data-status-url': '/status',
    'data-ocr-status': 'pendente',
  });
  const falha = { erroRede: 'conexão recusada' };
  const amb = criarAmbiente({
    filhos: [partes.card],
    respostas: [falha, falha, { status: 200, corpo: { status: 'pendente', status_display: 'Pendente' } }, falha],
  });
  carregarScript(amb.sandbox);
  dispararDomContentLoaded(amb.documento);
  await aguardarMicrotarefas();
  avancarTempo(3000); // #2: falha
  await aguardarMicrotarefas();
  avancarTempo(5000); // #3: sucesso — reseta falhas/falhaDesde
  await aguardarMicrotarefas();
  afirmarIgual(amb.chamadasFetch.length, 3, 'sucesso após duas falhas');
  afirmarIgual(partes.reconectando.textContent, '', 'sucesso limpa o aviso');
  avancarTempo(3000); // #4: falha de novo
  await aguardarMicrotarefas();
  afirmarIgual(amb.chamadasFetch.length, 4, '4ª consulta 3 s após o sucesso');
  afirmarIgual(partes.reconectando.textContent, 'Reconectando…', 'falha seguinte reabre o aviso');
  avancarTempo(2500);
  await aguardarMicrotarefas();
  afirmarIgual(amb.chamadasFetch.length, 4, '1ª falha pós-reset → próxima só em 3 s');
  avancarTempo(500);
  await aguardarMicrotarefas();
  afirmarIgual(amb.chamadasFetch.length, 5, 'volta ao intervalo curto, não ao de 10 s');
});

// 20. P2 (rodada 2): sucesso no fim da janela resetando falhaDesde
caso('P2: 9 min de falhas, sucesso, falha → falhaDesde resetado, sem corte imediato', async () => {
  resetarTimers();
  const partes = criarCard({
    'data-status-ativos': '["pendente","em_execucao"]',
    'data-status-com-texto': '["concluido"]',
    'data-status-url': '/status',
    'data-ocr-status': 'pendente',
  });
  const falha = { erroRede: 'conexão recusada' };
  const respostas = [];
  // A 1ª falha marca falhaDesde em t=0 (o catch roda no await anterior ao
  // loop) e daí em diante há uma consulta por janela de 10 s: 59 janelas
  // (t=590 s) deixam o card a 10 s do corte, sem cruzá-lo.
  for (let i = 0; i < 59; i++) respostas.push(falha);
  const amb = criarAmbiente({ filhos: [partes.card], respostas });
  carregarScript(amb.sandbox);
  dispararDomContentLoaded(amb.documento);
  await aguardarMicrotarefas();
  for (let i = 0; i < 59; i++) {
    avancarTempo(10000);
    await aguardarMicrotarefas();
  }
  afirmarIgual(amb.chamadasFetch.length, 60, '9 min 50 s de falhas (t=590 s), sem chegar ao corte');
  afirmarIgual(partes.atualizar.hidden, true, 'ainda sem corte antes do sucesso');
  avancarTempo(2000); // t=592 s: nada — a 61ª só em t=600 s
  await aguardarMicrotarefas();

  amb.respostas.push(
    { status: 200, corpo: { status: 'pendente', status_display: 'Pendente' } }, // #61: sucesso
    falha // #62: falha logo após o sucesso
  );
  avancarTempo(12000); // t=604 s: #61 dispara (t=600 s) e o catch roda em t=604 s
  await aguardarMicrotarefas();
  afirmarIgual(amb.chamadasFetch.length, 61, 'sucesso chega depois de ~10 min de falhas');
  afirmarIgual(partes.reconectando.textContent, '', 'sucesso limpa o aviso');
  avancarTempo(3000); // t=607 s: a falha pós-sucesso
  await aguardarMicrotarefas();
  afirmarIgual(amb.chamadasFetch.length, 62, 'falha pós-sucesso consulta de novo');
  afirmarIgual(partes.reconectando.textContent, 'Reconectando…', 'falha pós-sucesso reabre o aviso');
  afirmarIgual(partes.atualizar.hidden, true, 'falhaDesde resetado: a falha seguinte NÃO corta na hora');
  avancarTempo(2500); // t=609,5 s: backoff resetado, nada antes de 3 s
  await aguardarMicrotarefas();
  afirmarIgual(amb.chamadasFetch.length, 62, 'backoff resetado: próxima consulta só em 3 s');
  avancarTempo(500); // t=610 s
  await aguardarMicrotarefas();
  afirmarIgual(amb.chamadasFetch.length, 63, 'e as falhas também: volta ao intervalo curto, não ao de 10 s');
});

// 21. P3 (rodada 2): criado_em do payload + horas na duração
caso('P3: criado_em no payload restaura a contagem; duração ganha horas', async () => {
  resetarTimers();
  const partes = criarCard({
    'data-status-ativos': '["pendente","em_execucao"]',
    'data-status-com-texto': '["concluido"]',
    'data-status-url': '/status',
    'data-ocr-status': 'pendente',
    // sem data-ocr-criado-em: o 1º render conta do momento do polling
  });
  const amb = criarAmbiente({ filhos: [partes.card], respostas: [{ pendente: true }] });
  carregarScript(amb.sandbox);
  dispararDomContentLoaded(amb.documento);
  await aguardarMicrotarefas();
  afirmarIgual(
    partes.expectativa.textContent,
    'O processamento pode levar alguns minutos. Tempo decorrido: 0 s',
    'sem criado_em no template, a contagem começa no início do polling'
  );
  amb.pendentes[0].resolve({
    ok: true,
    status: 200,
    json: () => Promise.resolve({
      status: 'pendente',
      status_display: 'Pendente',
      criado_em: isoAtrasado(11103),
    }),
  });
  await aguardarMicrotarefas();
  afirmarIgual(
    partes.expectativa.textContent,
    'O processamento pode levar alguns minutos. Tempo decorrido: 3 h 5 min 3 s',
    'criado_em do payload restaura o início (11103 s → com horas, não "185 min 3 s")'
  );
  afirmarIgual(partes.badge.textContent, 'Pendente — na fila', 'badge segue sem tempo');
});

// 22. P3 (rodada 2): progresso ausente é o formato real do job frio
caso('P3: em_execucao com progresso null (formato real) → badge "processando…", sem página', async () => {
  resetarTimers();
  const partes = criarCard({
    'data-status-ativos': '["pendente","em_execucao"]',
    'data-status-com-texto': '["concluido"]',
    'data-status-url': '/status',
    'data-ocr-status': 'pendente',
  });
  const amb = criarAmbiente({
    filhos: [partes.card],
    respostas: [
      { status: 200, corpo: { status: 'em_execucao', status_display: 'Em execução', progresso: null } },
    ],
  });
  carregarScript(amb.sandbox);
  dispararDomContentLoaded(amb.documento);
  await aguardarMicrotarefas();
  afirmarIgual(partes.badge.textContent, 'Em execução — processando…', 'badge sem progresso vira "processando…"');
  afirmar(partes.badge.textContent.indexOf('página') === -1, 'progresso ausente não inventa página');
  afirmarIgual(partes.expectativa.hidden, false, 'contador segue com o job ativo');
});

// 23. P3 (rodada 2): erro permanente 404 corta com o botão, não em backoff
caso('P3: 404 (arquivo apagado em outra aba) corta com a mensagem e o botão Atualizar', async () => {
  resetarTimers();
  const partes = criarCard({
    'data-status-ativos': '["pendente","em_execucao"]',
    'data-status-com-texto': '["concluido"]',
    'data-status-url': '/status',
    'data-ocr-status': 'pendente',
  });
  const amb = criarAmbiente({
    filhos: [partes.card],
    respostas: [{ status: 404, corpo: { detalhe: 'não encontrado' } }],
  });
  carregarScript(amb.sandbox);
  dispararDomContentLoaded(amb.documento);
  await aguardarMicrotarefas();
  avancarTempo(60000);
  await aguardarMicrotarefas();
  afirmarIgual(amb.chamadasFetch.length, 1, '404 não entra em backoff: nenhuma nova consulta');
  afirmarIgual(filaTimers.length, 0, 'corte cancela polling e contador');
  afirmarIgual(
    partes.reconectando.textContent,
    'Não foi possível consultar o status. Recarregue a página.',
    'mensagem própria do erro permanente, não a de rede'
  );
  afirmarIgual(partes.atualizar.hidden, false, 'botão Atualizar status revelado');
  afirmarIgual(partes.erro.hidden, true, 'nunca vira texto de falha do OCR');
  afirmarIgual(partes.expectativa.hidden, true, 'contador para no corte');
});

// 24. P3 (rodada 2): redirect para o login corta igual ao 404
caso('P3: sessão expirada (response.redirected para o login) corta igual ao 404', async () => {
  resetarTimers();
  const partes = criarCard({
    'data-status-ativos': '["pendente","em_execucao"]',
    'data-status-com-texto': '["concluido"]',
    'data-status-url': '/status',
    'data-ocr-status': 'pendente',
  });
  const amb = criarAmbiente({
    filhos: [partes.card],
    respostas: [{ status: 200, corpo: '<html>login…</html>', redirected: true }],
  });
  carregarScript(amb.sandbox);
  dispararDomContentLoaded(amb.documento);
  await aguardarMicrotarefas();
  avancarTempo(60000);
  await aguardarMicrotarefas();
  afirmarIgual(amb.chamadasFetch.length, 1, 'redirect não entra em backoff: nenhuma nova consulta');
  afirmarIgual(filaTimers.length, 0, 'corte cancela polling e contador');
  afirmarIgual(
    partes.reconectando.textContent,
    'Não foi possível consultar o status. Recarregue a página.',
    'mensagem própria do erro permanente, sem o HTML do login no card'
  );
  afirmarIgual(partes.atualizar.hidden, false, 'botão Atualizar status revelado');
  afirmarIgual(partes.badge.textContent, 'OCR não iniciado', 'payload de redirect não pinta o card');
  afirmarIgual(partes.erro.hidden, true, 'nunca vira texto de falha do OCR');
});

// 25. P3 (rodada 3): retomada após erro permanente limpa a região viva
caso('P3: após 404, clique em Atualizar status limpa a região viva antes de consultar', async () => {
  resetarTimers();
  const partes = criarCard({
    'data-status-ativos': '["pendente","em_execucao"]',
    'data-status-com-texto': '["concluido"]',
    'data-status-url': '/status',
    'data-ocr-status': 'pendente',
  });
  const amb = criarAmbiente({
    filhos: [partes.card],
    respostas: [
      { status: 404, corpo: { detalhe: 'não encontrado' } },
      { status: 404, corpo: { detalhe: 'não encontrado' } },
    ],
  });
  carregarScript(amb.sandbox);
  dispararDomContentLoaded(amb.documento);
  await aguardarMicrotarefas();
  afirmarIgual(
    partes.reconectando.textContent,
    'Não foi possível consultar o status. Recarregue a página.',
    'erro permanente recebe o texto próprio, não o de rede'
  );
  afirmarIgual(partes.atualizar.hidden, false, 'botão Atualizar status revelado');

  // A região é limpa já no clique: se a nova consulta repetir o mesmo texto,
  // definirTexto reescreve de fato e o leitor de tela anuncia o resultado.
  partes.atualizar.click();
  afirmarIgual(partes.reconectando.textContent, '', 'clique limpa a região viva antes da consulta');
  afirmarIgual(amb.chamadasFetch.length, 2, 'clique dispara a consulta de retomada');
  await aguardarMicrotarefas();
  afirmarIgual(
    partes.reconectando.textContent,
    'Não foi possível consultar o status. Recarregue a página.',
    '404 repetido reescreve o texto (agora anunciável)'
  );
  afirmarIgual(amb.chamadasFetch.length, 2, '404 repetido não volta ao backoff');
  afirmarIgual(filaTimers.length, 0, 'sem polling nem contador após o 2º 404');
});

// 26. P3 (rodada 3): rejeição tardia de resposta órfã, depois do terminal
caso('P3: rejeição tardia de resposta em voo órfã não escreve "Reconectando…" nem agenda consulta', async () => {
  resetarTimers();
  const partes = criarCard({
    'data-status-ativos': '["pendente","em_execucao"]',
    'data-status-com-texto': '["concluido"]',
    'data-status-url': '/status',
    'data-ocr-status': 'em_execucao',
    'data-ocr-criado-em': isoAtrasado(30),
  });
  const amb = criarAmbiente({
    filhos: [partes.card],
    respostas: [
      { pendente: true },
      { status: 200, corpo: { status: 'concluido', status_display: 'Concluído' } },
    ],
  });
  carregarScript(amb.sandbox);
  dispararDomContentLoaded(amb.documento);
  await aguardarMicrotarefas();
  afirmarIgual(amb.chamadasFetch.length, 1, '1º GET fica em voo (pendente no harness)');

  // A geração avança no clique; o terminal chega e fecha o card. Só depois
  // a resposta órfã rejeita — o catch deve descartá-la pela geração.
  partes.atualizar.hidden = false;
  partes.atualizar.click();
  await aguardarMicrotarefas();
  afirmarIgual(partes.badge.textContent, 'Concluído', 'terminal pinta o card');
  afirmarIgual(filaTimers.length, 0, 'terminal parou polling e contador');
  afirmarIgual(partes.reconectando.textContent, '', 'região viva vazia após a retomada');

  amb.pendentes[0].reject(new Error('conexão recusada'));
  await aguardarMicrotarefas();
  afirmarIgual(partes.reconectando.textContent, '', 'rejeição órfã não escreve na região viva');
  afirmarIgual(filaTimers.length, 0, 'rejeição órfã não agenda consulta');
  afirmarIgual(amb.chamadasFetch.length, 2, 'nenhuma consulta nova após a rejeição órfã');
  afirmarIgual(partes.badge.textContent, 'Concluído', 'card permanece no terminal');
  afirmarIgual(partes.expectativa.hidden, true, 'contador permanece parado');
});

// 27. P3 (rodada 3): o aviso de reconexão só é escrito quando o texto muda
caso('P3: duas falhas seguidas escrevem na região viva uma única vez', async () => {
  resetarTimers();
  const partes = criarCard({
    'data-status-ativos': '["pendente","em_execucao"]',
    'data-status-com-texto': '["concluido"]',
    'data-status-url': '/status',
    'data-ocr-status': 'pendente',
  });
  const falha = { erroRede: 'conexão recusada' };
  const amb = criarAmbiente({ filhos: [partes.card], respostas: [falha, falha] });
  carregarScript(amb.sandbox);
  let escritas = 0;
  let valorAviso = partes.reconectando.textContent;
  Object.defineProperty(partes.reconectando, 'textContent', {
    get() {
      return valorAviso;
    },
    set(novo) {
      escritas += 1;
      valorAviso = novo;
    },
  });
  dispararDomContentLoaded(amb.documento);
  await aguardarMicrotarefas();
  avancarTempo(3000);
  await aguardarMicrotarefas();
  afirmarIgual(amb.chamadasFetch.length, 2, 'duas consultas, duas falhas');
  afirmarIgual(escritas, 1, '2ª falha com o mesmo texto não reescreve a região (definirTexto)');
  afirmarIgual(partes.reconectando.textContent, 'Reconectando…', 'o texto segue o da falha');
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
