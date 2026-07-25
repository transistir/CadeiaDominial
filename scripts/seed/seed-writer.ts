/**
 * Seed writer — persist generated chains via raw SQL.
 *
 * Implements S-2 persistence contract: synthetic CRIs, deterministic
 * round‑robin CRI assignment, topology‑to‑entity mapping, transactional
 * write, and typed counters.
 *
 * All DB operations use raw SQL (better-sqlite3). Drizzle ORM is not called
 * here to avoid conflicting generic instantiations from different pnpm
 * dependency resolutions.
 */
import type Database from "better-sqlite3";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type SeedDatabase = Database.Database;

export interface SeedReport {
  seed: string;
  inserted: {
    cri: number;
    documento: number;
    imovel: number;
    lancamento: number;
    origem: number;
    lancamentoPessoa: number;
    lancamentoTipo: number;
  };
  errors: Array<{ chainIdx: number; message: string }>;
  elapsedMs: number;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Round‑robin CRI assignment: chainIdx 0→CRI 1, 1→CRI 2, 2→CRI 3, 3→CRI 1… */
function pickCriId(chainIdx: number): number {
  return (chainIdx % 3) + 1;
}

// ---------------------------------------------------------------------------
/** Minimal chain topology shape accepted by the writer. */
interface TopoDocumento {
  tipo?: string;
}
interface TopoLancamento {
  tipo?: string;
  forma?: string;
  descricao?: string;
  id?: string;
}
interface TopoOrigem {
  tipo?: string;
  numero?: string;
  data?: string;
}
interface TopologyInput {
  documentos?: TopoDocumento[];
  lancamentos?: TopoLancamento[];
  origem?: TopoOrigem;
}
interface ChainInput {
  topology: TopologyInput;
}

/**
 * Persist synthetic chains into the database.
 */
export function persistSeedChains(
  database: SeedDatabase,
  seed: string,
  chains: ChainInput[],
): SeedReport {
  const started = Date.now();
  const report: SeedReport = {
    seed,
    inserted: {
      cri: 0,
      documento: 0,
      imovel: 0,
      lancamento: 0,
      origem: 0,
      lancamentoPessoa: 0,
      lancamentoTipo: 0,
    },
    errors: [],
    elapsedMs: 0,
  };

  // Step 1: Ensure synthetic CRIs exist.
  const synCris = [
    { id: 1, nome: "CRI 1º Ofício" },
    { id: 2, nome: "CRI 2º Ofício" },
    { id: 3, nome: "CRI 3º Ofício" },
  ];

  const insertCri = database.prepare(`
    INSERT OR IGNORE INTO cri (id, nome, created_at, updated_at)
    VALUES (?, ?, datetime('now'), datetime('now'))
  `);

  for (const c of synCris) {
    insertCri.run(c.id, c.nome);
  }
  report.inserted.cri = synCris.length;

  // Step 2: Seed lancamento_tipo lookup rows.
  const synTipos = [
    { id: 1, tipo: "inicio_matricula", nome: "Início de Matrícula" },
    { id: 2, tipo: "registro", nome: "Registro" },
    { id: 3, tipo: "averbacao", nome: "Averbação" },
  ];

  const insertTipo = database.prepare(`
    INSERT OR IGNORE INTO lancamento_tipo (id, tipo, nome, requer_detalhes, requer_transmissao, requer_cartorio_origem, requer_data_origem, requer_descricao, requer_folha_origem, requer_forma, requer_livro_origem, requer_observacao, requer_titulo)
    VALUES (?, ?, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
  `);

  for (const t of synTipos) {
    insertTipo.run(t.id, t.tipo, t.nome);
  }
  report.inserted.lancamentoTipo = synTipos.length;

  // Step 3: Chains — each in its own transaction.
  for (let chainIdx = 0; chainIdx < chains.length; chainIdx++) {
    const chain = chains[chainIdx];

    const chainTransaction = database.transaction(() => {
      const criId = pickCriId(chainIdx);
      const now = new Date().toISOString();
      let docs = 0, imovs = 0, lancs = 0, lp = 0, oris = 0;

      // 3.1 Insert documento(s) from topology.
      const documentoIds: number[] = [];

      for (const topoDoc of chain.topology.documentos ?? []) {
        const docType = topoDoc.tipo ?? "matricula";
        const docNumero = docType === "matricula"
          ? `M-${String(docs + 1).padStart(5, "0")}`
          : `T-${String(docs + 1).padStart(5, "0")}`;

        const insertDoc = database.prepare(`
          INSERT INTO documento (tipo, numero, numero_raw, data, cri_id, created_at)
          VALUES (?, ?, ?, ?, ?, ?)
        `);
        const docResult = insertDoc.run(
          docType,
          docNumero + "-" + chainIdx,
          docNumero,
          now.split("T")[0],
          criId,
          now,
        );
        documentoIds.push(Number(docResult.lastInsertRowid));
        docs++;
      }

      // 3.2 Insert imovel(s) — one per documento.
      const imovelIds: number[] = [];
      const imovelCount = (chain.topology.documentos ?? []).length;

      for (let imovIdx = 0; imovIdx < imovelCount; imovIdx++) {
        const insertImovel = database.prepare(`
          INSERT INTO imovel (nome, cri_id, created_at, updated_at)
          VALUES (?, ?, ?, ?)
        `);
        const imovResult = insertImovel.run(
          "Imóvel sintético " + chainIdx + "-" + imovelIds.length,
          criId,
          now,
          now,
        );
        imovelIds.push(Number(imovResult.lastInsertRowid));
        imovs++;
      }

      // 3.3 Link imovel↔documento (imovel_documento).
      for (let i = 0; i < Math.min(documentoIds.length, imovelIds.length); i++) {
        database.prepare(`
          INSERT INTO imovel_documento (imovel_id, documento_id, created_at)
          VALUES (?, ?, ?)
        `).run(imovelIds[i], documentoIds[i], now);
      }

      // 3.4 Insert lancamento(s).
      const lancamentoIdByTopologyId: Array<[string, number]> = [];
      const lancTemplates = chain.topology.lancamentos ?? [
        { tipo: "inicio_matricula" },
      ];

      for (let li = 0; li < lancTemplates.length; li++) {
        const topoLanc = lancTemplates[li];
        const docIdx = Math.min(li, documentoIds.length - 1);

        const tipoRow = database.prepare(
          `SELECT id FROM lancamento_tipo WHERE tipo = ?`,
        ).get(topoLanc.tipo ?? "inicio_matricula") as { id: number } | undefined;

        const tipoId = tipoRow?.id ?? 1;

        const formaMap: Record<string, string> = {
          matricial: "matricial",
          eletronica: "eletrônica",
          mista: "mista",
        };
        const forma = formaMap[topoLanc.forma ?? "matricial"] ?? "matricial";

        const insertLanc = database.prepare(`
          INSERT INTO lancamento (
            documento_id, tipo_id, numero_lancamento, forma, data,
            descricao, created_at
          )
          VALUES (?, ?, ?, ?, ?, ?, ?)
        `);
        const lancResult = insertLanc.run(
          documentoIds[docIdx],
          tipoId,
          li + 1,
          forma,
          now,
          topoLanc.descricao ?? `Lançamento sintético ${li} da chain ${chainIdx}`,
          now,
        );
        lancamentoIdByTopologyId.push([
          topoLanc.id ?? `lanc-${li}`,
          Number(lancResult.lastInsertRowid),
        ]);
        lancs++;
      }

      // 3.5 lancamento_pessoa — requires papel and nome_verbatim.
      for (const [, lancamentoId] of lancamentoIdByTopologyId) {
        const numPessoas = (lp % 2) + 1;

        for (let i = 0; i < numPessoas; i++) {
          const nome = `Pessoa Sintética ${lp + 1}`;
          const papel = i === 0 ? "outorgante" : "adquirente";

          const insertPessoa = database.prepare(`
            INSERT INTO pessoa (nome, created_at, updated_at)
            VALUES (?, ?, ?)
          `);
          const pessoaResult = insertPessoa.run(nome, now, now);
          const pessoaId = Number(pessoaResult.lastInsertRowid);

          database.prepare(`
            INSERT INTO lancamento_pessoa (lancamento_id, pessoa_id, papel, nome_verbatim, created_at)
            VALUES (?, ?, ?, ?, ?)
          `).run(lancamentoId, pessoaId, papel, nome, now);

          lp++;
        }
      }

      // 3.6 Insert origem — requires lancamento_id and indice.
      const topoOrigem = chain.topology.origem ?? {};
      const firstLancamentoId = lancamentoIdByTopologyId.length > 0
        ? lancamentoIdByTopologyId[0][1]
        : 1;

      database.prepare(`
        INSERT INTO origem (
          lancamento_id, documento_id, cri_id, indice, tipo, numero, data, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
      `).run(
        firstLancamentoId,
        documentoIds[0],
        criId,
        0,
        topoOrigem.tipo ?? "matricula",
        topoOrigem.numero ?? `ORIG-${chainIdx}`,
        topoOrigem.data ?? now,
        now,
      );
      oris++;

      return { docs, imovs, lancs, lp, oris };
    });

    // 3.7 Execute the chain transaction.
    try {
      const counts = chainTransaction();
      report.inserted.documento += counts.docs;
      report.inserted.imovel += counts.imovs;
      report.inserted.lancamento += counts.lancs;
      report.inserted.lancamentoPessoa += counts.lp;
      report.inserted.origem += counts.oris;
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      report.errors.push({ chainIdx, message: msg });
    }
  }

  report.elapsedMs = Date.now() - started;
  return report;
}
