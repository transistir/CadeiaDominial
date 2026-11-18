'use strict';
// Harness Node puro (sem dependências) do JS da revisão no formulário (#341).
// O módulo exporta a API quando carregado fora do navegador; o DOM é um
// punhado de objetos à mão — só o que o JS toca.
const assert = require('node:assert/strict');
const path = require('node:path');

const api = require(path.join(
    __dirname, '..', '..', '..', 'static', 'dominial', 'js', 'ocr_revisao_formulario.js',
));

class Falso {
    constructor(atributos = {}) {
        Object.assign(this, { value: '', id: '', textContent: '', hidden: false, className: '' }, atributos);
        this.filhos = [];
        this.parentNode = null;
        this.consultas = {};
        this.attrs = {};
        this.ouvintes = {};
        const eu = this;
        this.classes = new Set();
        this.classList = {
            add: (nome) => eu.classes.add(nome),
            remove: (nome) => eu.classes.delete(nome),
            contains: (nome) => eu.classes.has(nome),
        };
    }
    setAttribute(nome, valor) { this.attrs[nome] = String(valor); }
    getAttribute(nome) { return nome in this.attrs ? this.attrs[nome] : null; }
    appendChild(filho) { filho.parentNode = this; this.filhos.push(filho); return filho; }
    insertBefore(novo, referencia) {
        novo.parentNode = this;
        const posicao = referencia ? this.filhos.indexOf(referencia) : -1;
        if (posicao < 0) this.filhos.push(novo); else this.filhos.splice(posicao, 0, novo);
        return novo;
    }
    get nextSibling() {
        const irmaos = this.parentNode.filhos;
        return irmaos[irmaos.indexOf(this) + 1] || null;
    }
    addEventListener(tipo, funcao) { (this.ouvintes[tipo] = this.ouvintes[tipo] || []).push(funcao); }
    disparar(tipo, evento = {}) { (this.ouvintes[tipo] || []).forEach((f) => f(evento)); }
    querySelectorAll(seletor) { return this.consultas[seletor] || []; }
    querySelector(seletor) { return this.querySelectorAll(seletor)[0] || null; }
}

const documentoFalso = () => ({
    createElement: () => new Falso(),
    getElementById: () => null,
});

let casos = 0;
function caso(nome, funcao) {
    funcao();
    casos += 1;
    console.log('ok -', nome);
}

caso('o número da origem volta inteiro depois do JS do formulário manual', () => {
    const oculto = new Falso({ value: 'M42.718' });
    const numero = new Falso({ value: '42' });  // o que o migrarDadosExistentes deixou
    const item = new Falso();
    item.consultas = {
        'input[name="origem_completa[]"]': [oculto], '.origem-numero-input': [numero],
    };
    const doc = { querySelectorAll: () => [item] };

    api.restaurarNumerosDeOrigem(doc);

    assert.equal(numero.value, '42.718');
});

caso('origem sem ponto, vazia ou de fim de cadeia não é tocada', () => {
    for (const [texto, numeroAntes] of [['T366', '366'], ['', ''], ['Sem Origem::origem_lidima', '']]) {
        const oculto = new Falso({ value: texto });
        const numero = new Falso({ value: numeroAntes });
        const item = new Falso();
        item.consultas = {
            'input[name="origem_completa[]"]': [oculto], '.origem-numero-input': [numero],
        };
        api.restaurarNumerosDeOrigem({ querySelectorAll: () => [item] });
        assert.equal(numero.value, numeroAntes);
    }
});

caso('digitar no número da origem mantém o ponto depois do filtro só-dígitos do formulário manual', () => {
    const alvo = new Falso({ value: '42.7x18', id: 'numero_origem_2' });
    alvo.classes.add('origem-numero-input');
    const atualizadas = [];
    const janela = { atualizarOrigemCompleta: (indice) => atualizadas.push(indice) };
    const evento = { target: alvo };

    api.lembrarDigitacaoDaOrigem(evento);                  // captura
    alvo.value = alvo.value.replace(/[^0-9]/g, '');        // handler do origem_simples.js
    assert.equal(alvo.value, '42718');
    api.reaplicarDigitacaoDaOrigem(evento, janela);        // bolha

    assert.equal(alvo.value, '42.718');
    assert.deepEqual(atualizadas, [2]);                    // texto oculto refeito
});

caso('outros inputs não são tocados e a bolha sem captura não faz nada', () => {
    const outro = new Falso({ value: 'abc', id: 'livro_origem_0' });
    const numero = new Falso({ value: '12', id: 'numero_origem_0' });
    numero.classes.add('origem-numero-input');
    const atualizadas = [];
    const janela = { atualizarOrigemCompleta: (indice) => atualizadas.push(indice) };

    api.lembrarDigitacaoDaOrigem({ target: outro });
    api.reaplicarDigitacaoDaOrigem({ target: outro }, janela);
    api.reaplicarDigitacaoDaOrigem({ target: numero }, janela);

    assert.equal(outro.value, 'abc');
    assert.equal(numero.value, '12');
    assert.deepEqual(atualizadas, []);
});

caso('nome de input vira o campo certo: lista por posição, área visível, nome inválido recusado', () => {
    const form = new Falso();
    const nomes = [new Falso(), new Falso()];
    const areaVisivel = new Falso();
    const simples = new Falso();
    form.consultas = {
        '[name="transmitente_nome[]"]': nomes,
        '[name^="area_area_"]': [areaVisivel],
        '[name="data"]': [simples],
    };

    assert.deepEqual(api.camposDoInput(form, 'transmitente_nome[1]'), [nomes[1]]);
    assert.deepEqual(api.camposDoInput(form, 'transmitente_nome[5]'), []);
    assert.deepEqual(api.camposDoInput(form, 'area'), [areaVisivel]);
    assert.deepEqual(api.camposDoInput(form, 'data'), [simples]);
    assert.deepEqual(api.camposDoInput(form, 'data"] , [name="x'), []);
});

caso('o selo mostra a página, abre o trecho por textContent e linka a página', () => {
    const pai = new Falso();
    const campo = new Falso();
    pai.appendChild(campo);
    const form = new Falso();
    form.consultas = { '[name="data"]': [campo] };
    const doc = documentoFalso();
    const evidencias = {
        data: { pagina: 3, trecho: '<b>15 de fevereiro</b>', confianca_baixa: true },
    };

    api.anexarEvidencias(doc, form, evidencias, '/dominial/texto/');

    const [, selo, detalhe] = pai.filhos;
    assert.equal(selo.textContent, 'p. 3');
    assert.match(selo.className, /ia-evidencia-baixa/);
    assert.equal(detalhe.hidden, true);
    const [trecho, link] = detalhe.filhos;
    assert.equal(trecho.textContent, '<b>15 de fevereiro</b>');  // texto, nunca HTML
    assert.equal(link.href, '/dominial/texto/?pagina=3');
    assert.equal(link.rel, 'noopener');

    selo.disparar('click');
    assert.equal(detalhe.hidden, false);
    assert.equal(selo.attrs['aria-expanded'], 'true');
    selo.disparar('click');
    assert.equal(detalhe.hidden, true);

    campo.disparar('focus');
    assert.equal(selo.classes.has('ia-evidencia-foco'), true);
    campo.disparar('blur');
    assert.equal(selo.classes.has('ia-evidencia-foco'), false);
});

caso('partes: a posição vale DENTRO da seção — o selo acompanha o campo de cada uma (#341, M5)', () => {
    // O formulário repete o bloco de partes nas três seções de tipo; a
    // primeira cópia da página é a da AVERBAÇÃO mesmo revisando um Registro.
    const secoes = {
        'campos-averbacao': new Falso({ id: 'campos-averbacao' }),
        'campos-registro': new Falso({ id: 'campos-registro' }),
        'campos-inicio-matricula': new Falso({ id: 'campos-inicio-matricula' }),
    };
    const nomeDaAverbacao = new Falso();
    const nomeDoRegistro = new Falso();
    secoes['campos-averbacao'].appendChild(nomeDaAverbacao);
    secoes['campos-registro'].appendChild(nomeDoRegistro);
    const form = new Falso();
    form.consultas = { '[name="transmitente_nome[]"]': [nomeDaAverbacao, nomeDoRegistro] };

    // Um campo por seção (o da posição pedida) — não só o da Averbação.
    const alvos = api.camposDoInput(form, 'transmitente_nome[0]');
    assert.deepEqual(alvos, [nomeDaAverbacao, nomeDoRegistro]);

    // O selo entra ao lado do campo de CADA seção: trocar o tipo do ato
    // não deixa a evidência para trás.
    api.anexarEvidencias(documentoFalso(), form, {
        'transmitente_nome[0]': { pagina: 4, trecho: 'Transmitente: JOÃO', confianca_baixa: false },
    }, '');
    for (const nome of [nomeDaAverbacao, nomeDoRegistro]) {
        const [, selo] = nome.parentNode.filhos;
        assert.equal(selo.textContent, 'p. 4');
    }
    // A segunda transmitente da página inteira não existe em seção nenhuma.
    assert.deepEqual(api.camposDoInput(form, 'transmitente_nome[1]'), []);
});

caso('origem: evidência pelo id real (numero_origem_0), não pelo name com [] (#341, M5)', () => {
    // Os inputs da origem são numero_origem_0/tipo_origem_0 — o índice vem
    // no id, o name não tem "[]".
    const paiDoNumero = new Falso();
    const numero = new Falso({ id: 'numero_origem_0' });
    paiDoNumero.appendChild(numero);
    const paiDoTipo = new Falso();
    const tipo = new Falso({ id: 'tipo_origem_0' });
    paiDoTipo.appendChild(tipo);
    const form = new Falso();
    form.consultas = { '#numero_origem_0': [numero], '#tipo_origem_0': [tipo] };

    assert.deepEqual(api.camposDoInput(form, 'numero_origem[0]'), [numero]);
    assert.deepEqual(api.camposDoInput(form, 'tipo_origem[0]'), [tipo]);
    assert.deepEqual(api.camposDoInput(form, 'numero_origem[9]'), []);

    api.anexarEvidencias(documentoFalso(), form, {
        'numero_origem[0]': { pagina: 2, trecho: 'origem M42.718', confianca_baixa: false },
    }, '');

    const [, selo] = paiDoNumero.filhos;
    assert.equal(selo.textContent, 'p. 2');  // selo no input do número
    assert.equal(paiDoTipo.filhos.length, 1);  // e só nele
});

caso('navegar para outro ato dispara os handlers de envio, silencia o alert e envia pelo submit()', () => {
    const form = new Falso();
    const ordem = [];
    form.dispatchEvent = (evento) => {
        ordem.push(['dispatch', evento.type, janela.alert === alertaOriginal]);
        janela.alert('validação do formulário manual');  // não pode aparecer
        return false;  // handler manual chamou preventDefault
    };
    form.submit = () => ordem.push(['submit', form.campoIrPara.value]);
    const alertas = [];
    const alertaOriginal = (texto) => alertas.push(texto);
    class Evento { constructor(tipo) { this.type = tipo; } }
    const janela = { alert: alertaOriginal, Event: Evento };
    const doc = {
        createElement: () => { form.campoIrPara = new Falso(); return form.campoIrPara; },
    };

    api.navegarPara(doc, janela, form, '2');

    assert.deepEqual(ordem, [['dispatch', 'submit', false], ['submit', '2']]);
    assert.equal(form.campoIrPara.name, '_ir_para');
    assert.equal(form.campoIrPara.type, 'hidden');
    assert.deepEqual(alertas, []);
    assert.equal(janela.alert, alertaOriginal);  // restaurado
});

console.log(`${casos} casos ok`);
