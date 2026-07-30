/**
 * Seed writer — persist generated chains via raw SQL.
 *
 * Implements S-2 persistence contract: receives GeneratedSeedChain[] from S-1,
 * persists filled entities to their tables, maps topology structure to foreign
 * keys, and enforces invariants per the schema.
 *
 * All DB operations use raw SQL (better-sqlite3). Drizzle ORM is not called
 * here to avoid conflicting generic instantiations from different pnpm
 * dependency resolutions.
 */
import type Database from "better-sqlite3";

import type { GeneratedSeedChain } from "./seed-orchestrator.js";
import type { TopologyGraph } from "./chain-topology.js";

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

/** Build lookup: topologyId → DB id for documentos. */
function buildDocumentoIdMap(
  topology: TopologyGraph,
  documentoIds: number[]
): Map<string, number> {
  const map = new Map<string, number>();
  for (let i = 0; i < topology.documentos.length; i++) {
    map.set(topology.documentos[i].id, documentoIds[i]);
  }
  return map;
}

/** Build lookup: lancamento topology id → DB id. */
function buildLancamentoIdMap(
  topology: TopologyGraph,
  lancamentoIds: number[]
): Map<string, number> {
  const map = new Map<string, number>();
  for (let i = 0; i < topology.lancamentos.length; i++) {
    map.set(topology.lancamentos[i].id, lancamentoIds[i]);
  }
  return map;
}

// ---------------------------------------------------------------------------

/**
 * Persist synthetic chains into the database.
 *
 * @param database - better-sqlite3 Database instance
 * @param seed - Seed string for reproducibility
 * @param chains - GeneratedSeedChain[] from S-1 orchestrator
 * @returns SeedReport with counts and any errors
 */
export function persistSeedChains(
  database: SeedDatabase,
  seed: string,
  chains: GeneratedSeedChain[],
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
      const topology = chain.topology;
      const filled = chain.filled;
      const criId = pickCriId(chainIdx);
      const now = new Date().toISOString();
      let docs = 0, imovs = 0, lancs = 0, lp = 0, oris = 0;

      // 3.1 Insert documento(s) using filled.documentos data.
      const documentoIds: number[] = [];

      for (let i = 0; i < topology.documentos.length; i++) {
        const topoDoc = topology.documentos[i];
        const filledDoc = filled.documentos[i];

        if (!filledDoc) {
          throw new Error(`Missing filled.documentos for ${topoDoc.id}`);
        }

        const insertDoc = database.prepare(`
          INSERT INTO documento (tipo, numero, numero_raw, data, cri_id, created_at)
          VALUES (?, ?, ?, ?, ?, ?)
        `);
        const docResult = insertDoc.run(
          topoDoc.tipo,
          filledDoc.numero,
          filledDoc.numero,
          filledDoc.data,
          criId,
          now,
        );
        documentoIds.push(Number(docResult.lastInsertRowid));
        docs++;
      }

      // 3.2 Insert imovel — ONE per chain, using filled.imoveis[0].
      if (filled.imoveis.length !== 1) {
        throw new Error(
          `Chain ${chainIdx} must have exactly 1 imovel, got ${filled.imoveis.length}`
        );
      }

      const filledImovel = filled.imoveis[0];
      const insertImovel = database.prepare(`
        INSERT INTO imovel (nome, cri_id, created_at, updated_at)
        VALUES (?, ?, ?, ?)
      `);
      const imovResult = insertImovel.run(
        filledImovel.denominacao,
        criId,
        now,
        now,
      );
      const imovelId = Number(imovResult.lastInsertRowid);
      imovs++;

      // 3.3 Link imovel↔documento (imovel_documento) using topology.imovelDocumentos.
      for (const imovelDoc of topology.imovelDocumentos) {
        const docIdMap = buildDocumentoIdMap(topology, documentoIds);
        const dbDocId = docIdMap.get(imovelDoc.documentoId);
        if (dbDocId === undefined) {
          throw new Error(
            `imovelDocumento references missing documento ${imovelDoc.documentoId}`
          );
        }

        database.prepare(`
          INSERT INTO imovel_documento (imovel_id, documento_id, created_at)
          VALUES (?, ?, ?)
        `).run(imovelId, dbDocId, now);
      }

      // 3.4 Insert lancamento(s) — link to documentos via topology.documentoId.
      const lancamentoIds: number[] = [];

      for (let i = 0; i < topology.lancamentos.length; i++) {
        const topoLanc = topology.lancamentos[i];
        const docIdMap = buildDocumentoIdMap(topology, documentoIds);
        const dbDocId = docIdMap.get(topoLanc.documentoId);
        if (dbDocId === undefined) {
          throw new Error(
            `lancamento ${topoLanc.id} references missing documento ${topoLanc.documentoId}`
          );
        }

        const tipoRow = database.prepare(
          `SELECT id FROM lancamento_tipo WHERE tipo = ?`,
        ).get(topoLanc.tipo) as { id: number } | undefined;

        const tipoId = tipoRow?.id ?? 1;

        // Default forma mapping for synthetic chains
        const forma = "matricial";

        const insertLanc = database.prepare(`
          INSERT INTO lancamento (
            documento_id, tipo_id, numero_lancamento, forma, data,
            descricao, created_at
          )
          VALUES (?, ?, ?, ?, ?, ?, ?)
        `);
        const lancResult = insertLanc.run(
          dbDocId,
          tipoId,
          i + 1,
          forma,
          now.split("T")[0],
          `Lançamento ${i + 1} da chain ${chainIdx}`,
          now,
        );
        lancamentoIds.push(Number(lancResult.lastInsertRowid));
        lancs++;
      }

      // 3.5 lancamento_pessoa — use filled.pessoas for nome/cpfCnpj.
      // For synthetic chains, we attach pessoas to the first lancamento.
      const firstLancamentoId = lancamentoIds.length > 0
        ? lancamentoIds[0]
        : null;

      if (firstLancamentoId !== null) {
        for (let i = 0; i < filled.pessoas.length; i++) {
          const pessoa = filled.pessoas[i];
          const papel = i === 0 ? "outorgante" : "adquirente";

          const insertPessoa = database.prepare(`
            INSERT INTO pessoa (nome, created_at, updated_at)
            VALUES (?, ?, ?)
          `);
          const pessoaResult = insertPessoa.run(
            pessoa.nome,
            now,
            now,
          );
          const pessoaId = Number(pessoaResult.lastInsertRowid);

          database.prepare(`
            INSERT INTO lancamento_pessoa (lancamento_id, pessoa_id, papel, nome_verbatim, created_at)
            VALUES (?, ?, ?, ?, ?)
          `).run(firstLancamentoId, pessoaId, papel, pessoa.nome, now);

          lp++;
        }
      }

      // 3.6 Insert origem(s) — iterate over topology.origens (plural array).
      const lancIdMap = buildLancamentoIdMap(topology, lancamentoIds);
      const docIdMap = buildDocumentoIdMap(topology, documentoIds);

      for (const topoOrigem of topology.origens) {
        const dbLancId = lancIdMap.get(topoOrigem.lancamentoId);
        if (dbLancId === undefined) {
          throw new Error(
            `origem ${topoOrigem.id} references missing lancamento ${topoOrigem.lancamentoId}`
          );
        }

        const dbDocId = docIdMap.get(topoOrigem.documentoId);
        if (dbDocId === undefined) {
          throw new Error(
            `origem ${topoOrigem.id} references missing documento ${topoOrigem.documentoId}`
          );
        }

        database.prepare(`
          INSERT INTO origem (
            lancamento_id, documento_id, cri_id, indice, tipo, numero, data, created_at
          )
          VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        `).run(
          dbLancId,
          dbDocId,
          criId,
          topoOrigem.indice,
          "matricula",
          `ORIG-${chainIdx}`,
          now,
          now,
        );
        oris++;
      }

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
