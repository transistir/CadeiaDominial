'use strict';

const { afirmar, afirmarIgual, criarCard, criarInputCsrf, dispararDomContentLoaded, resetarTimers, avancarTempo, timersDePolling, aguardarMicrotarefas, isoAtrasado, criarAmbiente, carregarScript, filaTimers, caso } = require('./ocr_card_harness');

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

