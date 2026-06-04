import { describe, expect, it } from "vitest";
import { healthResponseSchema, renderPdfTemplate } from "./index";

describe("healthResponseSchema", () => {
  it("accepts a valid payload", () => {
    const result = healthResponseSchema.safeParse({
      ok: true,
      timestamp: "2026-06-04T12:00:00Z"
    });
    expect(result.success).toBe(true);
  });

  it("rejects when ok is not a boolean", () => {
    const result = healthResponseSchema.safeParse({
      ok: "yes",
      timestamp: "2026-06-04T12:00:00Z"
    });
    expect(result.success).toBe(false);
  });

  it("rejects when timestamp is missing", () => {
    const result = healthResponseSchema.safeParse({ ok: true });
    expect(result.success).toBe(false);
  });
});

describe("renderPdfTemplate — HTML escaping (XSS prevention)", () => {
  it("escapes <script> tags in the title", () => {
    const html = renderPdfTemplate({ title: "<script>alert(1)</script>" });
    expect(html).not.toContain("<script>alert(1)</script>");
    expect(html).toContain("&lt;script&gt;alert(1)&lt;/script&gt;");
  });

  it("escapes &, <, >, quotes, and apostrophes in the subtitle", () => {
    const html = renderPdfTemplate({
      title: "T",
      subtitle: `A & B <c> "d" 'e'`
    });
    expect(html).toContain("A &amp; B &lt;c&gt; &quot;d&quot; &#39;e&#39;");
  });

  it("escapes user content inside the body and converts newlines to <br />", () => {
    const html = renderPdfTemplate({
      title: "T",
      body: "line 1 <b>bold</b>\nline 2"
    });
    expect(html).toContain("line 1 &lt;b&gt;bold&lt;/b&gt;<br />line 2");
  });

  it("escapes values in report.ti and report.imovel meta-grid", () => {
    const html = renderPdfTemplate({
      title: "T",
      report: {
        ti: { nome: "<img onerror=alert(1) src=x>" },
        imovel: { matricula: '12"34' }
      }
    });
    expect(html).toContain("&lt;img onerror=alert(1) src=x&gt;");
    expect(html).toContain("12&quot;34");
    expect(html).not.toContain("<img onerror=alert(1) src=x>");
  });

  it("escapes section titulo and documento.tipo/numero", () => {
    const html = renderPdfTemplate({
      title: "T",
      chains: [
        {
          titulo: "<h1>Hack</h1>",
          documentos: [
            { tipo: "<bad>", numero: "1\"2", cartorio: "cartório" }
          ]
        }
      ]
    });
    expect(html).toContain("&lt;h1&gt;Hack&lt;/h1&gt;");
    expect(html).toContain("&lt;bad&gt;");
    expect(html).toContain("1&quot;2");
    expect(html).not.toContain("<h1>Hack</h1>");
  });
});

describe("renderPdfTemplate — defaults and empty state", () => {
  it("uses a Portuguese fallback subtitle when none is provided", () => {
    const html = renderPdfTemplate({ title: "Relatório" });
    expect(html).toContain("Relatório completo da cadeia dominial");
  });

  it("falls back to 'Resumo não informado' when body is missing", () => {
    const html = renderPdfTemplate({ title: "Relatório" });
    expect(html).toContain("Resumo não informado");
  });

  it("emits a doctype, the title in <title>, and the user-supplied <h1>", () => {
    const html = renderPdfTemplate({ title: "Cadeia Dominial — Terra X" });
    expect(html.startsWith("<!doctype html>")).toBe(true);
    expect(html).toContain("<title>Cadeia Dominial — Terra X</title>");
    expect(html).toContain("<h1>Cadeia Dominial — Terra X</h1>");
  });

  it("renders stats as 0 when estatisticas is not provided", () => {
    const html = renderPdfTemplate({ title: "T" });
    expect(html).toContain("<strong>0</strong>");
  });

  it("emits the 'Nenhum lançamento registrado' placeholder when lancamentos is empty", () => {
    const html = renderPdfTemplate({
      title: "T",
      chains: [
        { titulo: "Seção", documentos: [{ tipo: "MATRÍCULA", numero: "1", lancamentos: [] }] }
      ]
    });
    expect(html).toContain("Nenhum lançamento registrado");
  });

  it("renders lancamento table rows with XSS-escaped values (non-empty case)", () => {
    const html = renderPdfTemplate({
      title: "T",
      chains: [
        {
          titulo: "Seção",
          documentos: [
            {
              tipo: "MATRÍCULA",
              numero: "1",
              lancamentos: [
                {
                  tipo: "REGISTRO <hack>",
                  cartorio: "1º Cartório \"X\"",
                  data: "2026-06-04",
                  descricao: "A&B 'evil'"
                }
              ]
            }
          ]
        }
      ]
    });
    // Table rendered (and not the empty placeholder)
    expect(html).toContain('<table class="lancamentos">');
    expect(html).not.toContain("Nenhum lançamento registrado");
    // Header columns
    expect(html).toContain("<th>Tipo</th>");
    expect(html).toContain("<th>Cartório</th>");
    expect(html).toContain("<th>Data</th>");
    expect(html).toContain("<th>Descrição</th>");
    // Escaped values present
    expect(html).toContain("REGISTRO &lt;hack&gt;");
    expect(html).toContain("1º Cartório &quot;X&quot;");
    expect(html).toContain("A&amp;B &#39;evil&#39;");
    // Raw forms absent (negative assertion on each attack vector)
    expect(html).not.toContain("REGISTRO <hack>");
    expect(html).not.toContain("1º Cartório \"X\"");
    expect(html).not.toContain("A&B 'evil'");
  });

  it("emits the 'Nenhum documento nesta seção' placeholder for an empty section", () => {
    const html = renderPdfTemplate({
      title: "T",
      chains: [{ titulo: "Seção vazia", documentos: [] }]
    });
    expect(html).toContain("Nenhum documento nesta seção");
  });
});

describe("renderPdfTemplate — multi-section page breaks", () => {
  it("adds page-break class to the 2nd+ chain section but not the first", () => {
    // The template has 3 inline `<section class="section">` wrappers
    // (meta-grid, stats, resumo executivo). The 4th+ `<section>` tags are
    // the chain sections — first uses `class="section"`, rest use
    // `class="section page-break"`. We assert on the page-break count.
    const html = renderPdfTemplate({
      title: "T",
      chains: [
        { titulo: "S1", documentos: [{ tipo: "X", numero: "1" }] },
        { titulo: "S2", documentos: [{ tipo: "Y", numero: "2" }] },
        { titulo: "S3", documentos: [{ tipo: "Z", numero: "3" }] }
      ]
    });
    const pageBreakCount = (html.match(/<section class="section page-break">/g) ?? []).length;
    const totalChainSections = (html.match(/<h3 class="section-title">S\d/g) ?? []).length;
    expect(totalChainSections).toBe(3);
    expect(pageBreakCount).toBe(2); // N-1 for N chain sections
  });
});
