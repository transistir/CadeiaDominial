// data.js — Conversão do grafo recebido do backend em hierarquia D3

function ordenarFilhosPorNumeroDesc(nodo) {
  if (nodo.children && nodo.children.length > 0) {
    nodo.children.sort((a, b) => {
      // Matrículas sempre antes de transcrições; dentro do mesmo tipo, maior número primeiro
      const tipoA = a.tipo_documento === "matricula" ? 0 : 1;
      const tipoB = b.tipo_documento === "matricula" ? 0 : 1;
      if (tipoA !== tipoB) return tipoA - tipoB;

      const numA = parseInt((a.numero || "").replace(/\D/g, ""), 10) || 0;
      const numB = parseInt((b.numero || "").replace(/\D/g, ""), 10) || 0;
      return numB - numA;
    });
    nodo.children.forEach(ordenarFilhosPorNumeroDesc);
  }
}

function converterParaArvoreD3(data) {
  console.log(
    `DEBUG: Iniciando conversão - Backend enviou ${data.documentos.length} documentos únicos`,
  );

  // IDs são a identidade técnica; número permanece apenas como rótulo.
  const docMap = {};
  data.documentos.forEach((doc) => {
    doc.children = [];
    docMap[doc.id] = doc;
  });

  // Encontrar a matrícula principal (raiz)
  let raiz = data.documentos.find(
    (doc) => doc.nivel === 0 || doc.origem === "" || doc.origem == null,
  );
  if (!raiz) raiz = data.documentos[0];

  console.log(`DEBUG: Raiz identificada: ${raiz.numero}`);

  // CORREÇÃO: um documento pode ser citado como origem por mais de um
  // documento (grafo, não árvore). Quando isso acontece, o documento deve
  // pertencer ao citante MAIS PROFUNDO (mais distante da raiz) -- senão a
  // citação do citante mais raso vira uma linha secundária cruzando
  // verticalmente irmãos da mesma coluna. Calculamos o caminho mais longo
  // a partir da raiz (relaxamento iterativo, não BFS de caminho mais
  // curto) e usamos o citante que produz esse caminho como pai primário;
  // qualquer outra citação vira conexão secundária (linha tracejada), que
  // assim sempre "avança" para uma coluna mais profunda, nunca cruza a
  // mesma coluna.
  const conexoesPorFrom = new Map();
  data.conexoes.forEach((con) => {
    if (!conexoesPorFrom.has(con.from)) conexoesPorFrom.set(con.from, []);
    conexoesPorFrom.get(con.from).push(con);
  });

  const profundidade = new Map([[raiz.id, 0]]);
  const paiPrimario = new Map();
  const fila = [raiz.id];
  let iteracoes = 0;
  const limiteIteracoes =
    data.documentos.length * data.conexoes.length + data.documentos.length;

  // Impede que uma citação cíclica (ex.: A cita B e B cita A, direta ou
  // indiretamente) vire uma aresta primária -- senão docMap[X].children
  // pode acabar contendo, direta ou indiretamente, o próprio X, e a
  // recursão em ordenarFilhosPorNumeroDesc/d3.hierarchy nunca termina.
  function criariCiclo(candidatoPai, alvo) {
    let atual = candidatoPai;
    let passos = 0;
    while (atual !== undefined) {
      if (atual === alvo) return true;
      if (++passos > data.documentos.length) return true;
      atual = paiPrimario.get(atual);
    }
    return false;
  }

  while (fila.length > 0) {
    if (++iteracoes > limiteIteracoes) {
      console.warn(
        "DEBUG: possível ciclo nas conexões, interrompendo cálculo de profundidade",
      );
      break;
    }
    const atual = fila.shift();
    (conexoesPorFrom.get(atual) || []).forEach((con) => {
      if (!docMap[con.to]) return;
      if (con.to === raiz.id) return; // a raiz nunca recebe pai primário
      if (criariCiclo(atual, con.to)) return;
      const novaProfundidade = profundidade.get(atual) + 1;
      if (
        !profundidade.has(con.to) ||
        novaProfundidade > profundidade.get(con.to)
      ) {
        profundidade.set(con.to, novaProfundidade);
        paiPrimario.set(con.to, atual);
        fila.push(con.to);
      }
    });
  }

  const conexoesSecundarias = [];
  data.conexoes.forEach((con) => {
    if (!docMap[con.to] || !docMap[con.from]) return;
    if (!profundidade.has(con.to)) return;

    if (paiPrimario.get(con.to) === con.from) {
      docMap[con.from].children.push(docMap[con.to]);
    } else {
      // Documento já pertence a outro nó da árvore: conecta sem duplicar o card
      console.log(`DEBUG: Conexão secundária: ${con.from} -> ${con.to}`);
      conexoesSecundarias.push({
        from: con.from,
        to: con.to,
        tipo: "conexao_secundaria",
      });
    }
  });

  console.log(
    `DEBUG: Documentos na árvore: ${profundidade.size}, conexões secundárias: ${conexoesSecundarias.length}`,
  );

  // Adicionar conexões secundárias à raiz
  raiz.conexoesExtras = conexoesSecundarias;

  // Ordenar filhos recursivamente
  ordenarFilhosPorNumeroDesc(raiz);

  return raiz;
}
