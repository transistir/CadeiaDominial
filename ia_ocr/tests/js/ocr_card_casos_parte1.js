'use strict';

const { afirmar, afirmarIgual, criarCard, criarInputCsrf, dispararDomContentLoaded, resetarTimers, avancarTempo, timersDePolling, aguardarMicrotarefas, isoAtrasado, criarAmbiente, carregarScript, filaTimers, caso } = require('./ocr_card_harness');

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

