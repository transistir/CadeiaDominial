import { describe, expect, it } from "vitest";
import app from "./index";

type UserRecord = {
  id: string;
  email: string;
  role: string;
  password_hash: string;
};

type DocRow = { id: number; tipo: string; numero: string; data: string | null; criId: number };
type LancRow = { id: number; documentoId: number; tipo: string };
type OrigRow = {
  id: number;
  lancamentoId: number;
  documentoId: number | null;
  tipo: string;
  tipoFimCadeia: string | null;
  especificacao: string | null;
};

/**
 * Minimal in-memory fixture mirroring the real schema for imóvel 4:
 * two chain documentos, two lançamentos (one per doc), and one origem
 * linking doc 5 → doc 4. Referentially complete so buildGraph would not throw.
 */
const GRAPH_FIXTURE: Record<number, { documentos: DocRow[]; lancamentos: LancRow[]; origens: OrigRow[] }> = {
  4: {
    documentos: [
      { id: 4, tipo: "matricula", numero: "6726", data: "2024-01-01", criId: 1355 },
      { id: 5, tipo: "matricula", numero: "517", data: "2025-07-07", criId: 1355 }
    ],
    lancamentos: [
      { id: 1, documentoId: 4, tipo: "averbacao" },
      { id: 7, documentoId: 4, tipo: "registro" },
      { id: 8, documentoId: 5, tipo: "registro" }
    ],
    // origem cites doc 5 (source) on a lançamento of doc 4 (target), then
    // doc 5 has an explicit classified fim_cadeia origin.
    origens: [
      {
        id: 1,
        lancamentoId: 7,
        documentoId: 5,
        tipo: "matricula",
        tipoFimCadeia: null,
        especificacao: null
      },
      {
        id: 2,
        lancamentoId: 8,
        documentoId: null,
        tipo: "fim_cadeia",
        tipoFimCadeia: "destacamento_publico",
        especificacao: "Patrimônio público estadual"
      }
    ]
  }
};

const makeGraphEnv = () => {
  const users = new Map<string, UserRecord>();

  const resolveAll = (query: string, values: unknown[]) => {
    const imovelId = Number(values[0]);
    const data = GRAPH_FIXTURE[imovelId];
    if (!data) {
      return { results: [] as unknown[] };
    }

    if (query.includes("FROM lancamento l") && query.includes("lancamento_tipo")) {
      return { results: data.lancamentos };
    }
    // Source-documento subquery (`WHERE d.id IN (...)`) — must be checked
    // before the generic documento query since it also references `documento`.
    if (query.includes("WHERE d.id IN (")) {
      const ids = new Set(
        data.origens.flatMap((o) => (o.documentoId === null ? [] : [o.documentoId]))
      );
      return { results: data.documentos.filter((d) => ids.has(d.id)) };
    }
    if (query.includes("FROM origem o")) {
      return { results: data.origens };
    }
    if (query.includes("FROM documento d")) {
      return { results: data.documentos };
    }
    return { results: [] as unknown[] };
  };

  return {
    JWT_SECRET: "test-secret",
    ALLOW_DEV_BOOTSTRAP: "true",
    R2_ACCOUNT_ID: "test-account",
    R2_ACCESS_KEY_ID: "test-access-key",
    R2_SECRET_ACCESS_KEY: "test-secret-key",
    R2_BUCKET_NAME: "cadeia-dominial-files",
    BROWSER_RENDERING_ACCOUNT_ID: "test-browser-account",
    BROWSER_RENDERING_API_TOKEN: "test-browser-token",
    R2: {
      get: async () => null,
      put: async () => undefined,
      delete: async () => undefined
    },
    DB: {
      prepare: (query: string) => ({
        bind: (...values: unknown[]) => ({
          first: async () => {
            if (query.includes("SELECT") && query.includes("FROM users")) {
              return users.get(String(values[0] ?? "")) ?? null;
            }
            return null;
          },
          all: async () => resolveAll(query, values),
          run: async () => {
            if (query.includes("INSERT INTO users")) {
              const [id, email, passwordHash, role] = values as string[];
              users.set(String(email), {
                id: String(id),
                email: String(email),
                role: String(role),
                password_hash: String(passwordHash)
              });
            }
            return {};
          }
        })
      })
    }
  };
};

const loginAndGetToken = async (env: ReturnType<typeof makeGraphEnv>) => {
  const res = await app.request(
    "/auth/login",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "user@example.com", password: "dev-password" })
    },
    env
  );
  expect(res.status).toBe(200);
  const { token } = (await res.json()) as { token: string };
  return token;
};

type ChainDataResponse = {
  documentos: Array<{ id: string; numero: string; tipo: string; cartorioId: string; data: string }>;
  lancamentos: Array<{ id: string; documentoId: string; tipo: string }>;
  origens: Array<{
    id: string;
    lancamentoId: string;
    documentoId: string | null;
    tipoOrigem: string;
    tipoFimCadeia?: string;
    especificacao?: string;
  }>;
};

describe("GET /api/graph/:imovelId", () => {
  it("requires authentication", async () => {
    const res = await app.request("/api/graph/4", {}, makeGraphEnv());
    expect(res.status).toBe(401);
  });

  it("returns 400 for a non-numeric imovelId", async () => {
    const env = makeGraphEnv();
    const token = await loginAndGetToken(env);
    const res = await app.request(
      "/api/graph/abc",
      { headers: { Authorization: `Bearer ${token}` } },
      env
    );
    expect(res.status).toBe(400);
  });

  it("returns 400 for a non-positive imovelId", async () => {
    const env = makeGraphEnv();
    const token = await loginAndGetToken(env);
    const res = await app.request(
      "/api/graph/0",
      { headers: { Authorization: `Bearer ${token}` } },
      env
    );
    expect(res.status).toBe(400);
  });

  it("returns 404 when the imóvel has no documentos", async () => {
    const env = makeGraphEnv();
    const token = await loginAndGetToken(env);
    const res = await app.request(
      "/api/graph/999",
      { headers: { Authorization: `Bearer ${token}` } },
      env
    );
    expect(res.status).toBe(404);
  });

  it("returns referentially-complete ChainData for a known imóvel", async () => {
    const env = makeGraphEnv();
    const token = await loginAndGetToken(env);
    const res = await app.request(
      "/api/graph/4",
      { headers: { Authorization: `Bearer ${token}` } },
      env
    );
    expect(res.status).toBe(200);

    const body = (await res.json()) as ChainDataResponse;
    expect(Array.isArray(body.documentos)).toBe(true);
    expect(Array.isArray(body.lancamentos)).toBe(true);
    expect(Array.isArray(body.origens)).toBe(true);
    expect(body.documentos.length).toBeGreaterThan(0);

    // Shape of a documento entry (matches builder's ChainData).
    const doc = body.documentos[0];
    expect(typeof doc.id).toBe("string");
    expect(typeof doc.numero).toBe("string");
    expect(typeof doc.cartorioId).toBe("string");
    expect(typeof doc.data).toBe("string");
    expect(["matricula", "transcricao", "averbacao"]).toContain(doc.tipo);

    // tipo enums are within the domain sets.
    for (const l of body.lancamentos) {
      expect(["inicio_matricula", "registro", "averbacao"]).toContain(l.tipo);
    }
    for (const o of body.origens) {
      expect(["matricula", "transcricao", "fim_cadeia"]).toContain(o.tipoOrigem);
    }
    expect(body.origens).toContainEqual({
      id: "2",
      lancamentoId: "8",
      documentoId: null,
      tipoOrigem: "fim_cadeia",
      tipoFimCadeia: "destacamento_publico",
      especificacao: "Patrimônio público estadual"
    });

    // Referential integrity — exactly what buildGraph needs to not throw:
    const docIds = new Set(body.documentos.map((d) => d.id));
    const lancIds = new Set(body.lancamentos.map((l) => l.id));
    for (const l of body.lancamentos) {
      expect(docIds.has(l.documentoId)).toBe(true);
    }
    for (const o of body.origens) {
      expect(lancIds.has(o.lancamentoId)).toBe(true);
      if (o.documentoId === null) {
        expect(o.tipoOrigem).toBe("fim_cadeia");
      } else {
        expect(docIds.has(o.documentoId)).toBe(true);
      }
    }
  });
});
