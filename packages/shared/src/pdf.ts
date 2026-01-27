const escapeHtml = (value: string) =>
  value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll("\"", "&quot;")
    .replaceAll("'", "&#39;");

export type PdfLancamento = {
  tipo: string;
  cartorio?: string;
  data?: string;
  descricao?: string;
};

export type PdfDocumento = {
  numero: string;
  tipo: string;
  cartorio?: string;
  data?: string;
  livro?: string;
  folha?: string;
  descricao?: string;
  lancamentos?: PdfLancamento[];
};

export type PdfChainSection = {
  titulo: string;
  documentos: PdfDocumento[];
};

export type PdfReport = {
  ti?: {
    nome?: string;
    codigo?: string;
    municipio?: string;
    estado?: string;
  };
  imovel?: {
    matricula?: string;
    descricao?: string;
    area?: string;
    endereco?: string;
    cartorio?: string;
  };
  periodo?: {
    inicio?: string;
    fim?: string;
  };
  estatisticas?: {
    documentos?: number;
    lancamentos?: number;
    registros?: number;
    averbacoes?: number;
    origens?: number;
  };
  responsavel?: {
    nome?: string;
    cargo?: string;
  };
};

export type PdfTemplateOptions = {
  title: string;
  subtitle?: string;
  body?: string;
  report?: PdfReport;
  chains?: PdfChainSection[];
};

const renderLabelValue = (label: string, value?: string) => {
  const safeValue = value ? escapeHtml(value) : "—";
  return `<div class="kv"><span>${escapeHtml(label)}</span><strong>${safeValue}</strong></div>`;
};

const renderLancamentos = (lancamentos?: PdfLancamento[]) => {
  if (!lancamentos || lancamentos.length === 0) {
    return `<p class="empty">Nenhum lançamento registrado.</p>`;
  }

  const rows = lancamentos
    .map((lancamento) => {
      return `<tr>
        <td>${escapeHtml(lancamento.tipo)}</td>
        <td>${escapeHtml(lancamento.cartorio ?? "—")}</td>
        <td>${escapeHtml(lancamento.data ?? "—")}</td>
        <td>${escapeHtml(lancamento.descricao ?? "—")}</td>
      </tr>`;
    })
    .join("");

  return `<table class="lancamentos">
      <thead>
        <tr>
          <th>Tipo</th>
          <th>Cartório</th>
          <th>Data</th>
          <th>Descrição</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>`;
};

const renderDocumentos = (documentos: PdfDocumento[]) => {
  if (documentos.length === 0) {
    return `<p class="empty">Nenhum documento nesta seção.</p>`;
  }

  return documentos
    .map((documento) => {
      const descricao = documento.descricao ? escapeHtml(documento.descricao) : "—";

      return `<article class="documento-card">
        <header>
          <h3>${escapeHtml(documento.tipo)} • ${escapeHtml(documento.numero)}</h3>
          <div class="documento-meta">
            ${renderLabelValue("Cartório", documento.cartorio)}
            ${renderLabelValue("Data", documento.data)}
            ${renderLabelValue("Livro", documento.livro)}
            ${renderLabelValue("Folha", documento.folha)}
          </div>
        </header>
        <p class="documento-descricao">${descricao}</p>
        <div class="documento-lancamentos">
          <h4>Lançamentos</h4>
          ${renderLancamentos(documento.lancamentos)}
        </div>
      </article>`;
    })
    .join("");
};

export const renderPdfTemplate = ({
  title,
  subtitle,
  body,
  report,
  chains
}: PdfTemplateOptions) => {
  const safeTitle = escapeHtml(title);
  const safeSubtitle = subtitle ? escapeHtml(subtitle) : "Relatório completo da cadeia dominial";
  const safeBody = body ? escapeHtml(body).replaceAll("\n", "<br />") : "";

  const ti = report?.ti;
  const imovel = report?.imovel;
  const periodo = report?.periodo;
  const stats = report?.estatisticas;
  const responsavel = report?.responsavel;
  const sections = chains ?? [];

  return `<!doctype html>
<html lang="pt-BR">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>${safeTitle}</title>
    <style>
      :root {
        color-scheme: light;
        --ink: #1f2933;
        --muted: #52606d;
        --paper: #ffffff;
        --accent: #1f4f5b;
        --border: #d9e2ec;
      }

      body {
        font-family: "Spectral", "Times New Roman", serif;
        margin: 0;
        color: var(--ink);
        line-height: 1.6;
        background: var(--paper);
      }

      @page {
        size: A4;
        margin: 2cm;
      }

      @page :first {
        margin-top: 3cm;
      }

      h1,
      h2,
      h3,
      h4 {
        margin: 0;
      }

      h1 {
        font-size: 28px;
      }

      h2 {
        font-size: 16px;
        font-weight: 600;
        color: var(--muted);
        margin-top: 6px;
      }

      main {
        padding: 0 0 16px;
      }

      header.report-header {
        border-bottom: 2px solid var(--accent);
        padding-bottom: 16px;
        margin-bottom: 24px;
      }

      .meta-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 12px 24px;
        margin: 16px 0 24px;
      }

      .kv {
        display: flex;
        flex-direction: column;
        font-size: 12px;
      }

      .kv span {
        text-transform: uppercase;
        font-size: 10px;
        color: var(--muted);
        letter-spacing: 0.08em;
      }

      .kv strong {
        font-size: 14px;
        font-weight: 600;
      }

      .stats {
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: 12px;
        border: 1px solid var(--border);
        padding: 12px;
        border-radius: 8px;
        margin-bottom: 24px;
      }

      .stat {
        text-align: center;
      }

      .stat span {
        font-size: 10px;
        color: var(--muted);
        text-transform: uppercase;
        letter-spacing: 0.06em;
      }

      .stat strong {
        display: block;
        font-size: 18px;
        margin-top: 4px;
      }

      .section {
        margin-bottom: 24px;
      }

      .section-title {
        font-size: 16px;
        font-weight: 600;
        margin-bottom: 12px;
      }

      .documento-card {
        border: 2px solid #000;
        background: #f5f5f5;
        padding: 12px;
        margin-bottom: 16px;
      }

      .documento-meta {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 8px 16px;
        margin-top: 8px;
      }

      .documento-descricao {
        margin: 12px 0;
        font-size: 13px;
      }

      .lancamentos {
        width: 100%;
        border-collapse: collapse;
        font-size: 12px;
      }

      .lancamentos th,
      .lancamentos td {
        border: 1px solid var(--border);
        padding: 6px 8px;
        text-align: left;
      }

      .lancamentos th {
        background: #e4e7eb;
        font-weight: 600;
      }

      .empty {
        font-size: 12px;
        color: var(--muted);
        margin: 8px 0 0;
      }

      .page-break {
        page-break-before: always;
      }

      .no-break {
        page-break-inside: avoid;
      }

      .footer {
        margin-top: 32px;
        font-size: 11px;
        color: var(--muted);
      }
    </style>
  </head>
  <body>
    <main>
      <header class="report-header">
        <h1>${safeTitle}</h1>
        <h2>${safeSubtitle}</h2>
      </header>

      <section class="section">
        <div class="meta-grid">
          ${renderLabelValue("Terra Indígena", ti?.nome)}
          ${renderLabelValue("Código TI", ti?.codigo)}
          ${renderLabelValue("Município", ti?.municipio)}
          ${renderLabelValue("Estado", ti?.estado)}
          ${renderLabelValue("Matrícula", imovel?.matricula)}
          ${renderLabelValue("Cartório", imovel?.cartorio)}
          ${renderLabelValue("Endereço", imovel?.endereco)}
          ${renderLabelValue("Área", imovel?.area)}
          ${renderLabelValue("Período Inicial", periodo?.inicio)}
          ${renderLabelValue("Período Final", periodo?.fim)}
          ${renderLabelValue("Responsável", responsavel?.nome)}
          ${renderLabelValue("Cargo", responsavel?.cargo)}
        </div>
      </section>

      <section class="section">
        <div class="stats">
          <div class="stat">
            <span>Documentos</span>
            <strong>${stats?.documentos ?? 0}</strong>
          </div>
          <div class="stat">
            <span>Lançamentos</span>
            <strong>${stats?.lancamentos ?? 0}</strong>
          </div>
          <div class="stat">
            <span>Registros</span>
            <strong>${stats?.registros ?? 0}</strong>
          </div>
          <div class="stat">
            <span>Averbações</span>
            <strong>${stats?.averbacoes ?? 0}</strong>
          </div>
          <div class="stat">
            <span>Origens</span>
            <strong>${stats?.origens ?? 0}</strong>
          </div>
        </div>
      </section>

      <section class="section">
        <h3 class="section-title">Resumo Executivo</h3>
        <p class="documento-descricao">${safeBody || "Resumo não informado."}</p>
      </section>

      ${sections
        .map((section, index) => {
          const className = index === 0 ? "section" : "section page-break";
          return `<section class="${className}">
            <h3 class="section-title">${escapeHtml(section.titulo)}</h3>
            ${renderDocumentos(section.documentos)}
          </section>`;
        })
        .join("")}

      <footer class="footer">
        Documento gerado automaticamente pela Cadeia Dominial. Confira os dados antes de uso oficial.
      </footer>
    </main>
  </body>
</html>`;
};
