'use strict';

const { afirmar, afirmarIgual, criarCenario, esperar, caso } = require('./ocr_revisao_harness');

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

