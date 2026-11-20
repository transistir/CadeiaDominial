'use strict';

const { afirmar, afirmarIgual, criarCard, criarInputCsrf, dispararDomContentLoaded, resetarTimers, avancarTempo, timersDePolling, aguardarMicrotarefas, isoAtrasado, criarAmbiente, carregarScript, filaTimers, caso } = require('./ocr_card_harness');

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

