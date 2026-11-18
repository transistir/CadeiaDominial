'use strict';
// Executa os JS REAIS do formulário de lançamento — lancamento_form.js e, na
// revisão, ocr_revisao_formulario.js, na ordem em que o template os carrega —
// contra um DOM mínimo semeado com o que o servidor renderizou. Prova o que os
// DOIS scripts, juntos, deixam nos campos de número antes do POST (#341, M1).
//
// Dois usos, sem dependências:
//   - require('./formulario_real.js').executar(seed)   (harness Node dos casos)
//   - node formulario_real.js < seed.json               (testes Python: o seed
//     sai do HTML renderizado e o resultado volta para o POST)
//
// seed: {tipo, simples, composto, sigla, modoEdicao, revisao, digitacoes}
//   tipo       data-tipo da opção selecionada (registro|averbacao|inicio_matricula)
//   simples    value de numero_lancamento_simples como o servidor renderizou
//   composto   value de numero_lancamento como o servidor renderizou
//   sigla      value de sigla_matricula (a sigla da matrícula)
//   modoEdicao o template pôs a classe `modo-edicao` no body
//   revisao    carregar também ocr_revisao_formulario.js
//   digitacoes [{campo: 'simples'|'composto'|'sigla', valor}] — depois do
//              load (timer do formulário manual incluso), o revisor digita:
//              value trocado + evento `input` (o que dispara o recomputo).
// resultado: {simples, composto, erros} — o que o POST do navegador levaria.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const RAIZ_JS = path.join(__dirname, '..', '..', '..', 'static', 'dominial', 'js');
const LIMITE_DO_RELOGIO_MS = 5000;

class No {
    constructor(atributos = {}) {
        this.value = '';
        this.id = '';
        this.name = '';
        this.textContent = '';
        this.className = '';
        this.hidden = false;
        this.parentNode = null;
        this.filhos = [];
        this.style = {};
        this.dataset = {};
        this.attrs = {};
        this.ouvintes = {};
        this.options = [];
        this.selectedIndex = 0;
        this.disabled = false;
        this.classes = new Set();
        this.classList = {
            add: (nome) => this.classes.add(nome),
            remove: (nome) => this.classes.delete(nome),
            contains: (nome) => this.classes.has(nome),
        };
        Object.assign(this, atributos);
    }
    setAttribute(nome, valor) { this.attrs[nome] = String(valor); }
    getAttribute(nome) { return nome in this.attrs ? this.attrs[nome] : null; }
    appendChild(filho) {
        filho.parentNode = this;
        this.filhos.push(filho);
        return filho;
    }
    insertBefore(novo, referencia) {
        novo.parentNode = this;
        const posicao = referencia ? this.filhos.indexOf(referencia) : -1;
        if (posicao < 0) this.filhos.push(novo);
        else this.filhos.splice(posicao, 0, novo);
        return novo;
    }
    get nextSibling() {
        if (!this.parentNode) return null;
        return this.parentNode.filhos[this.parentNode.filhos.indexOf(this) + 1] || null;
    }
    addEventListener(tipo, funcao) { (this.ouvintes[tipo] = this.ouvintes[tipo] || []).push(funcao); }
    disparar(tipo) {
        (this.ouvintes[tipo] || []).slice().forEach((funcao) => funcao({ target: this }));
    }
    querySelector() { return null; }
    querySelectorAll() { return []; }
}

function executar(seed) {
    const erros = [];
    const aoCarregar = [];
    const fila = [];
    let agora = 0;
    let ordem = 0;

    const corpo = new No();
    if (seed.modoEdicao) corpo.classList.add('modo-edicao');

    // Primeira opção é o "Selecione o tipo..." (sem data-tipo), como no template.
    const tipo = new No({ id: 'tipo_lancamento' });
    tipo.options = [
        new No({ value: '' }),
        new No({ value: '1', attrs: { 'data-tipo': 'averbacao' } }),
        new No({ value: '2', attrs: { 'data-tipo': 'registro' } }),
        new No({ value: '3', attrs: { 'data-tipo': 'inicio_matricula' } }),
    ];
    tipo.selectedIndex = {
        averbacao: 1, registro: 2, inicio_matricula: 3,
    }[seed.tipo] || 0;
    const simples = new No({ id: 'numero_lancamento_simples', value: seed.simples });
    const composto = new No({ id: 'numero_lancamento', value: seed.composto });
    const sigla = new No({ value: seed.sigla });
    const campoSimples = new No();
    const formulario = new No({ id: 'lancamento-form' });

    const secaoAverbacao = new No({ id: 'campos-averbacao' });
    const secaoRegistro = new No({ id: 'campos-registro' });
    const secaoInicio = new No({ id: 'campos-inicio-matricula' });
    const secaoTransacao = new No({ id: 'campos-transacao' });
    const transmitir = (secao, valor) => {
        const pai = secao.appendChild(new No());
        const campo = pai.appendChild(new No({
            name: 'transmitente_nome[]', value: valor,
        }));
        secao.querySelectorAll = (seletor) => (
            seletor === 'input, select, textarea' ? [campo] : []
        );
        return { campo, pai };
    };
    const transmitenteAverbacao = transmitir(secaoAverbacao, 'JOÃO NO BLOCO AVERBAÇÃO');
    const transmitenteRegistro = transmitir(secaoRegistro, 'JOÃO NO BLOCO REGISTRO');
    const transmitenteInicio = transmitir(secaoInicio, 'JOÃO NO BLOCO INÍCIO');
    secaoTransacao.querySelectorAll = () => [];

    // A origem comum do template usa índice no id/name, não `name="...[]"`.
    const paiDaOrigem = formulario.appendChild(new No());
    const tipoOrigem = paiDaOrigem.appendChild(new No({
        id: 'tipo_origem_0', name: 'tipo_origem_0', value: 'M',
    }));
    const numeroOrigem = paiDaOrigem.appendChild(new No({
        id: 'numero_origem_0', name: 'numero_origem_0', value: '42',
    }));
    numeroOrigem.classList.add('origem-numero-input');
    const origemCompleta = paiDaOrigem.appendChild(new No({ value: 'M42.718' }));
    const itemOrigem = new No();
    itemOrigem.querySelector = (seletor) => ({
        'input[name="origem_completa[]"]': origemCompleta,
        '.origem-numero-input': numeroOrigem,
    }[seletor] || null);

    const evidencias = new No({
        id: 'ia-evidencias', textContent: JSON.stringify(seed.evidencias || {}),
    });
    const porId = {
        tipo_lancamento: tipo,
        'campos-averbacao': secaoAverbacao,
        'campos-registro': secaoRegistro,
        'campos-inicio-matricula': secaoInicio,
        'campos-transacao': secaoTransacao,
        numero_lancamento_simples: simples,
        numero_lancamento: composto,
        numero_origem_0: numeroOrigem,
        tipo_origem_0: tipoOrigem,
        'lancamento-form': formulario,
        'ia-evidencias': evidencias,
    };
    const porSeletor = {
        'input[name="numero_lancamento_simples"]': simples,
        'input[name="sigla_matricula"]': sigla,
        '.numero-simples-field': campoSimples,
    };
    const camposPorNome = {
        'transmitente_nome[]': [
            transmitenteAverbacao.campo,
            transmitenteRegistro.campo,
            transmitenteInicio.campo,
        ],
    };
    formulario.querySelectorAll = (seletor) => {
        const nome = /^\[name="([^"]+)"\]$/.exec(seletor);
        if (nome) return camposPorNome[nome[1]] || [];
        return [];
    };
    formulario.querySelector = (seletor) => {
        const id = /^#([a-z0-9_-]+)$/.exec(seletor);
        if (id) return porId[id[1]] || null;
        const lista = formulario.querySelectorAll(seletor);
        return lista[0] || null;
    };
    const documento = {
        readyState: 'loading',
        body: corpo,
        addEventListener: (nome, funcao) => {
            if (nome === 'DOMContentLoaded') aoCarregar.push(funcao);
        },
        getElementById: (id) => porId[id] || null,
        querySelector: (seletor) => porSeletor[seletor] || null,
        querySelectorAll: (seletor) => seletor === '.origem-item' ? [itemOrigem] : [],
        createElement: () => new No(),
    };

    // Relógio virtual: o timer de 100 ms do formulário manual roda de verdade.
    const contexto = {
        document: documento,
        console: { log() {}, warn() {}, error() {} },
        setTimeout: (funcao, ms) => {
            ordem += 1;
            fila.push({ quando: agora + (ms || 0), ordem, funcao });
            return ordem;
        },
        clearTimeout() {},
        alert() {},
        Event: class { constructor(nome) { this.type = nome; } },
        isTranscricao: false,
    };
    contexto.window = contexto;
    vm.createContext(contexto);

    const scripts = ['lancamento_form.js'];
    if (seed.revisao) scripts.push('ocr_revisao_formulario.js');
    for (const nome of scripts) {
        vm.runInContext(
            fs.readFileSync(path.join(RAIZ_JS, nome), 'utf8'), contexto, { filename: nome },
        );
    }

    const rodar = (funcao) => {
        try {
            funcao();
        } catch (erro) {
            erros.push(String((erro && erro.stack) || erro));
        }
    };
    aoCarregar.forEach(rodar);
    while (fila.length && agora <= LIMITE_DO_RELOGIO_MS) {
        fila.sort((a, b) => a.quando - b.quando || a.ordem - b.ordem);
        const proximo = fila.shift();
        agora = proximo.quando;
        rodar(proximo.funcao);
    }

    if (seed.tipoDepois) {
        tipo.selectedIndex = {
            averbacao: 1, registro: 2, inicio_matricula: 3,
        }[seed.tipoDepois] || 0;
        tipo.disparar('change');
    }

    // O revisor digita DEPOIS do load: o valor troca e o evento `input`
    // dispara o recomputo do número completo.
    const digitaveis = { simples: simples, composto: composto, sigla: sigla };
    (seed.digitacoes || []).forEach(function (digitacao) {
        const campo = digitaveis[digitacao.campo];
        if (!campo) return;
        campo.value = String(digitacao.valor);
        campo.disparar('input');
    });

    const resultado = { simples: simples.value, composto: composto.value, erros };
    if (seed.evidencias) {
        const textosDosSelos = (pai) => pai.filhos
            .filter((filho) => /(?:^| )ia-evidencia-selo(?: |$)/.test(filho.className))
            .map((filho) => filho.textContent);
        const seloOrigem = paiDaOrigem.filhos.find(
            (filho) => /(?:^| )ia-evidencia-selo(?: |$)/.test(filho.className),
        );
        const indiceSeloOrigem = paiDaOrigem.filhos.indexOf(seloOrigem);
        resultado.evidencias = {
            transmitenteAverbacao: textosDosSelos(transmitenteAverbacao.pai),
            transmitenteRegistro: textosDosSelos(transmitenteRegistro.pai),
            transmitenteInicio: textosDosSelos(transmitenteInicio.pai),
            origemNumero: textosDosSelos(paiDaOrigem),
            origemSeloDepoisDe: indiceSeloOrigem > 0
                ? paiDaOrigem.filhos[indiceSeloOrigem - 1].id : null,
        };
    }
    return resultado;
}

module.exports = { executar };

if (require.main === module) {
    let entrada = '';
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', (pedaco) => { entrada += pedaco; });
    process.stdin.on('end', () => {
        process.stdout.write(JSON.stringify(executar(JSON.parse(entrada))));
    });
}
