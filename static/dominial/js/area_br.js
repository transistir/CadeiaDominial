(function (global) {
  'use strict';

  // #396 — mesma regra do backend (dominial/utils/area_br.py), só para avisar
  // antes do submit. O backend continua sendo a autoridade; nada aqui converte
  // valor: apenas descreve o problema (ou devolve string vazia).
  var CASAS = 4;

  function problemaAreaPtBr(valor) {
    var texto = String(valor == null ? '' : valor).trim().replace(/\u00a0/g, ' ');
    if (!texto) return '';
    if (/\s/.test(texto)) return 'Área inválida: não use espaços.';
    if (!/^[0-9.,]+$/.test(texto)) {
      return 'Área inválida: use apenas números e vírgula decimal (ex.: 150,5000).';
    }

    var inteiro, decimais, partes;
    var temVirgula = texto.indexOf(',') !== -1;
    var temPonto = texto.indexOf('.') !== -1;

    if (temVirgula && temPonto) {
      if (texto.lastIndexOf('.') > texto.lastIndexOf(',')) {
        return 'Área inválida: formato com ponto depois da vírgula não é aceito.';
      }
      partes = texto.split(',');
      if (partes.length !== 2) return 'Área inválida: mais de uma vírgula.';
      inteiro = partes[0];
      decimais = partes[1];
      if (!/^[0-9]{1,3}(\.[0-9]{3})+$/.test(inteiro)) {
        return 'Área inválida: separador de milhar fora de grupos de 3.';
      }
    } else if (temPonto) {
      partes = texto.split('.');
      if (partes.length !== 2) {
        if (!/^[0-9]{1,3}(\.[0-9]{3})+$/.test(texto)) {
          return 'Área inválida: separador de milhar fora de grupos de 3.';
        }
        if (texto.replace(/\./g, '').replace(/^0+/, '').length > 8) {
          return 'Área inválida: valor acima do limite da coluna de área.';
        }
        return '';
      }
      inteiro = partes[0];
      decimais = partes[1];
    } else if (temVirgula) {
      partes = texto.split(',');
      if (partes.length !== 2) return 'Área inválida: mais de uma vírgula.';
      inteiro = partes[0];
      decimais = partes[1];
    } else {
      if (((inteiro === undefined ? texto : inteiro).replace(/^0+/, '') || '0').length > 8) {
        return 'Área inválida: valor acima do limite da coluna de área.';
      }
      return '';
    }

    if (!inteiro) return 'Área inválida: falta a parte inteira.';
    if (decimais.length > CASAS) return 'Área inválida: máximo de 4 casas decimais.';
    if ((inteiro.replace(/^0+/, '') || '0').length > 8) {
      return 'Área inválida: valor acima do limite da coluna de área.';
    }
    // `0.012` não é ambíguo: zero à esquerda não abre grupo de milhar.
    if (decimais.length === 3 && inteiro.length >= 1 && inteiro.length <= 3 &&
        inteiro.charAt(0) !== '0') {
      var comoDecimal = Number(inteiro + '.' + decimais).toFixed(CASAS);
      var comoMilhar = String(Number(inteiro + decimais));
      return 'Área ambígua: ' + texto + ' pode ser ' + comoDecimal +
        ' ha (decimal) ou ' + comoMilhar + ' ha (milhar). Digite ' +
        comoDecimal + ' ou ' + comoMilhar + ' para confirmar.';
    }
    return '';
  }

  global.problemaAreaPtBr = problemaAreaPtBr;
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { problemaAreaPtBr: problemaAreaPtBr };
  }
})(typeof window !== 'undefined' ? window : globalThis);
