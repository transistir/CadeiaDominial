'use strict';
// Casos do harness que executa os JS REAIS do formulário (lancamento_form.js +
// ocr_revisao_formulario.js) contra o DOM mínimo de `formulario_real.js`.
//
// #341, M1: o número completo ("R1 M237") tem que chegar no HTML (o prefill
// injeta pelo mesmo gerador do POST manual) e SOBREVIVER ao JS do formulário
// manual — que, com o campo vazio, colava só a sigla ("M237") e, em modo de
// edição, reescrevia o número simples a partir dele.
const assert = require('node:assert/strict');
const path = require('node:path');

const { executar } = require(path.join(__dirname, 'formulario_real.js'));

let casos = 0;
function caso(nome, funcao) {
    funcao();
    casos += 1;
    console.log('ok -', nome);
}

caso('registro: o composto do servidor chega intacto ao POST (sem edição)', () => {
    const resultado = executar({
        tipo: 'registro', simples: '1', composto: 'R1 M237', sigla: 'M237',
        modoEdicao: false, revisao: true,
    });

    assert.deepEqual(resultado, { simples: '1', composto: 'R1 M237', erros: [] });
});

caso('registro em modo de edição (herança): composto intacto e simples preservado', () => {
    // O contexto do novo_lancamento liga modo_edicao a partir do 2º
    // lançamento: o JS manual reescreve o número simples a partir do
    // composto. Com "R1 M237" ele resgata o "1"; com a sigla pura ("M237")
    // apagava o número simples.
    const resultado = executar({
        tipo: 'registro', simples: '1', composto: 'R1 M237', sigla: 'M237',
        modoEdicao: true, revisao: true,
    });

    assert.equal(resultado.composto, 'R1 M237');
    assert.equal(resultado.simples.trim(), '1');
    assert.deepEqual(resultado.erros, []);
});

caso('sem o composto no HTML o JS gruda só a sigla — é isso que a fase 1 entregava', () => {
    // Documentação do bug no harness (o guard de regressão é o teste Django
    // que renderiza a página de verdade): campo vazio no load → o JS do
    // formulário manual preenche com a sigla pura e o POST salvaria "M237".
    const resultado = executar({
        tipo: 'registro', simples: '1', composto: '', sigla: 'M237',
        modoEdicao: false, revisao: true,
    });

    assert.equal(resultado.composto, 'M237');
});

caso('averbação e início de matrícula: o composto de cada tipo também sobrevive', () => {
    const averbacao = executar({
        tipo: 'averbacao', simples: '6', composto: 'AV6 M237', sigla: 'M237',
        modoEdicao: true, revisao: true,
    });
    const inicio = executar({
        tipo: 'inicio_matricula', simples: '1', composto: 'M237', sigla: 'M237',
        modoEdicao: true, revisao: true,
    });

    assert.equal(averbacao.composto, 'AV6 M237');
    assert.equal(averbacao.simples.trim(), '6');
    // Início de matrícula: o número completo É a sigla; o simples não vale
    // (paridade com a edição manual, que o limpa).
    assert.equal(inicio.composto, 'M237');
    assert.deepEqual(averbacao.erros, []);
    assert.deepEqual(inicio.erros, []);
});

caso('revisor edita o número simples: o composto é recomputado com o novo valor', () => {
    const resultado = executar({
        tipo: 'registro', simples: '1', composto: 'R1 M237', sigla: 'M237',
        modoEdicao: false, revisao: true,
        digitacoes: [{ campo: 'simples', valor: '2' }],
    });

    assert.deepEqual(resultado, { simples: '2', composto: 'R2 M237', erros: [] });
});

caso('o formulário manual puro (sem o JS da revisão) se comporta igual', () => {
    // A revisão não muda o comportamento do formulário: os dois carregam
    // juntos e o resultado é o mesmo com ou sem o script da revisão.
    const semRevisao = executar({
        tipo: 'registro', simples: '1', composto: 'R1 M237', sigla: 'M237',
        modoEdicao: true, revisao: false,
    });

    assert.equal(semRevisao.composto, 'R1 M237');
    assert.equal(semRevisao.simples.trim(), '1');
});

caso('registro: evidências ficam no bloco certo e na origem real mesmo após trocar o tipo', () => {
    const resultado = executar({
        tipo: 'registro', simples: '1', composto: 'R1 M237', sigla: 'M237',
        modoEdicao: false, revisao: true, tipoDepois: 'averbacao',
        evidencias: {
            'transmitente_nome[0]': {
                pagina: 4, trecho: 'Transmitente: JOÃO', confianca_baixa: false,
            },
            'numero_origem[0]': {
                pagina: 2, trecho: 'Origem M42.718', confianca_baixa: false,
            },
        },
    });

    assert.deepEqual(resultado.erros, []);
    // Ao abrir Registro, o selo está na cópia do bloco de Registro, não só
    // na primeira cópia da página (Averbação). As cópias mantêm a associação
    // quando o revisor troca o tipo depois do load.
    assert.deepEqual(resultado.evidencias.transmitenteRegistro, ['p. 4']);
    assert.deepEqual(resultado.evidencias.transmitenteAverbacao, ['p. 4']);
    assert.deepEqual(resultado.evidencias.transmitenteInicio, ['p. 4']);
    // A origem usa o id real numero_origem_0; o selo foi inserido logo após
    // esse input, e não procurado pelo name inexistente numero_origem[].
    assert.deepEqual(resultado.evidencias.origemNumero, ['p. 2']);
    assert.equal(resultado.evidencias.origemSeloDepoisDe, 'numero_origem_0');
});

console.log(`${casos} casos ok`);
