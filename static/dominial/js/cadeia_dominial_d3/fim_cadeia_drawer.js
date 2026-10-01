// fim_cadeia_drawer.js — Painel lateral (drawer) com detalhes do card de
// fim de cadeia: abertura/fechamento, backdrop, focus trap e tecla Escape.

let cardFimCadeiaComFoco = null;

const fecharPainelFimCadeia = () => {
  const drawer = document.getElementById("fim-cadeia-drawer");
  const backdrop = document.getElementById("fim-cadeia-drawer-backdrop");
  if (!drawer || !backdrop) return;

  drawer.classList.remove("is-open");
  backdrop.classList.remove("is-open");
  drawer.setAttribute("aria-hidden", "true");
  document.removeEventListener("keydown", manejarTecladoPainelFimCadeia);

  if (cardFimCadeiaComFoco) {
    cardFimCadeiaComFoco.focus();
    cardFimCadeiaComFoco = null;
  }
};

const manejarTecladoPainelFimCadeia = (event) => {
  if (event.key === "Escape") {
    fecharPainelFimCadeia();
    return;
  }

  if (event.key !== "Tab") return;

  const drawer = document.getElementById("fim-cadeia-drawer");
  if (!drawer) return;

  const elementosFocaveis = Array.from(
    drawer.querySelectorAll(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
    ),
  ).filter((elemento) => !elemento.disabled);
  if (!elementosFocaveis.length) return;

  const primeiroElemento = elementosFocaveis[0];
  const ultimoElemento = elementosFocaveis[elementosFocaveis.length - 1];

  if (event.shiftKey && document.activeElement === primeiroElemento) {
    event.preventDefault();
    ultimoElemento.focus();
  } else if (!event.shiftKey && document.activeElement === ultimoElemento) {
    event.preventDefault();
    primeiroElemento.focus();
  }
};

const abrirPainelFimCadeia = (d) => {
  const drawer = document.getElementById("fim-cadeia-drawer");
  const backdrop = document.getElementById("fim-cadeia-drawer-backdrop");
  const botaoFechar = document.getElementById("fim-cadeia-drawer-fechar");
  const detalheTipo = document.getElementById("fim-cadeia-detalhe-tipo");
  const detalheClassificacao = document.getElementById(
    "fim-cadeia-detalhe-classificacao",
  );
  const detalheNome = document.getElementById("fim-cadeia-detalhe-nome");
  const detalheInfoAdicional = document.getElementById(
    "fim-cadeia-detalhe-info-adicional",
  );
  const detalheTitulo = document.getElementById("fim-cadeia-detalhe-titulo");
  const detalheDocumento = document.getElementById(
    "fim-cadeia-detalhe-documento",
  );
  if (
    !drawer ||
    !backdrop ||
    !botaoFechar ||
    !detalheTipo ||
    !detalheClassificacao ||
    !detalheNome ||
    !detalheInfoAdicional ||
    !detalheTitulo ||
    !detalheDocumento
  )
    return;

  const tipos = {
    destacamento_publico: "Destacamento do Patrimônio Público",
    outra: "Outra",
    sem_origem: "Sem Origem",
  };
  const classificacoes = {
    origem_lidima: { texto: "Origem Lídima", classe: "origem-lidima" },
    inconclusa: { texto: "Inconclusa", classe: "inconclusa" },
    sem_origem: { texto: "Sem Origem", classe: "sem-origem" },
  };
  const classificacao = classificacoes[d.data.classificacao_fim_cadeia] || {
    texto: "Não informada",
    classe: "nao-informada",
  };
  const textoOuTraco = (valor) =>
    typeof valor === "string" && valor.trim() ? valor : "—";

  detalheTipo.textContent = tipos[d.data.tipo_fim_cadeia] || "—";
  detalheClassificacao.textContent = classificacao.texto;
  detalheClassificacao.className = `fim-cadeia-classificacao-badge ${classificacao.classe}`;
  detalheNome.textContent = textoOuTraco(d.data.sigla_patrimonio_publico);
  detalheInfoAdicional.textContent = textoOuTraco(
    d.data.info_adicional_fim_cadeia,
  );
  detalheTitulo.textContent = textoOuTraco(d.data.titulo_fim_cadeia);
  detalheDocumento.textContent = d.data.documento_origem_id ?? "—";

  cardFimCadeiaComFoco = cardFimCadeiaComFoco || document.activeElement;
  drawer.classList.add("is-open");
  backdrop.classList.add("is-open");
  drawer.setAttribute("aria-hidden", "false");
  document.addEventListener("keydown", manejarTecladoPainelFimCadeia);
  botaoFechar.focus();
};

document.addEventListener("DOMContentLoaded", function () {
  document
    .getElementById("fim-cadeia-drawer-fechar")
    ?.addEventListener("click", fecharPainelFimCadeia);
  document
    .getElementById("fim-cadeia-drawer-backdrop")
    ?.addEventListener("click", fecharPainelFimCadeia);
});
