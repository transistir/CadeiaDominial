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
  filaTimers.length = 0;
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
  const restantes = filaTimers.filter((t) => t.id !== id);
  filaTimers.splice(0, filaTimers.length, ...restantes);
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

const casos = [];

function caso(nome, fn) {
  casos.push({ nome: nome, fn: fn });
}

module.exports = {
  CAMINHO_JS, afirmar, afirmarIgual, criarCard, criarInputCsrf,
  dispararDomContentLoaded, resetarTimers, avancarTempo, timersDePolling,
  aguardarMicrotarefas, isoAtrasado, criarAmbiente, carregarScript,
  filaTimers, casos, caso,
};
