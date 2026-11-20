'use strict';

const { afirmar, afirmarIgual, criarCenario, esperar, caso } = require('./ocr_revisao_harness');

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
    ui.lista.children[0].childNodes[0].textContent,
    'Ato 1 — folha: Folha da origem não consta no documento',
    'texto inicial do item: local + rótulo, como no template'
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
    item.childNodes[0].textContent,
    'Ato 1 — livro: Livro da origem não consta no documento',
    'texto inicial do item'
  );
  afirmarIgual(item.childNodes[0].nodeType, 3, 'texto inicial é nó de texto');
  const detalhe = item.children[0];
  afirmarIgual(detalhe.tagName, 'DETAILS', 'detalhe técnico em <details>');
  afirmarIgual(
    detalhe.children.map((filho) => filho.tagName + ':' + filho.textContent).join('|'),
    'SUMMARY:Detalhe técnico|CODE:' + AVISO_LIVRO.chave + '|CODE:' + AVISO_LIVRO.motivo,
    'children contém apenas os elementos do detalhe técnico'
  );
  afirmarIgual(detalhe.childNodes[2].nodeType, 3, 'separador é nó de texto');
  afirmarIgual(detalhe.childNodes[2].textContent, ' — ', 'texto do separador técnico');

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
  afirmarIgual(
    item.childNodes[0].textContent,
    '<b>Ato 1</b>: <img src=x onerror=1>',
    'vai como nó de texto, sem virar tag'
  );
  afirmarIgual(item.childNodes[0].nodeType, 3, 'conteúdo hostil é nó de texto');
  afirmarIgual(
    item.children.map((filho) => filho.tagName).join(','), 'DETAILS',
    'só o <details> técnico é elemento filho'
  );
});

