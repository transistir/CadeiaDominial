import { describe, expect, it, vi, afterEach } from "vitest";
import app from "./index";

type UserRecord = {
  id: string;
  email: string;
  role: string;
  password_hash: string;
};

const makeTestEnv = () => {
  const users = new Map<string, UserRecord>();

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
      get: vi.fn().mockResolvedValue(null),
      put: vi.fn().mockResolvedValue(undefined),
      delete: vi.fn().mockResolvedValue(undefined)
    },
    DB: {
      prepare: (query: string) => ({
        bind: (...values: unknown[]) => ({
          first: async () => {
            if (query.includes("SELECT") && query.includes("FROM users")) {
              const email = String(values[0] ?? "");
              return users.get(email) ?? null;
            }
            return null;
          },
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
            if (query.includes("UPDATE users SET password_hash")) {
              const [passwordHash, id] = values as string[];
              for (const [email, user] of users.entries()) {
                if (user.id === String(id)) {
                  users.set(email, { ...user, password_hash: String(passwordHash) });
                  break;
                }
              }
            }
            return {};
          }
        })
      })
    },
    __users: users
  };
};

const loginAndGetToken = async (env: ReturnType<typeof makeTestEnv>) => {
  const loginRes = await app.request(
    "/auth/login",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ email: "user@example.com", password: "dev-password" })
    },
    env
  );

  expect(loginRes.status).toBe(200);
  const { token } = (await loginRes.json()) as { token: string };
  return token;
};

describe("api health", () => {
  it("responds with ok and timestamp", async () => {
    const res = await app.request("/health", {}, makeTestEnv());
    const json = (await res.json()) as { ok: boolean; timestamp: string };

    expect(res.status).toBe(200);
    expect(json).toHaveProperty("ok", true);
    expect(typeof json.timestamp).toBe("string");
  });
});

describe("auth flow", () => {
  it("rejects session without token", async () => {
    const res = await app.request("/auth/session", {}, makeTestEnv());
    expect(res.status).toBe(401);
  });

  it("returns a token and validates session", async () => {
    const env = makeTestEnv();
    const loginRes = await app.request(
      "/auth/login",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ email: "user@example.com", password: "dev-password" })
      },
      env
    );

    expect(loginRes.status).toBe(200);
    const { token } = (await loginRes.json()) as { token: string };
    expect(typeof token).toBe("string");

    const sessionRes = await app.request(
      "/auth/session",
      {
        headers: {
          Authorization: `Bearer ${token}`
        }
      },
      env
    );

    expect(sessionRes.status).toBe(200);
    const sessionJson = await sessionRes.json();
    expect(sessionJson).toHaveProperty("authenticated", true);
    expect(sessionJson).toHaveProperty("payload.sub");
  });

  it("rejects invalid credentials for existing user", async () => {
    const env = makeTestEnv();
    const firstLogin = await app.request(
      "/auth/login",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ email: "user@example.com", password: "dev-password" })
      },
      env
    );

    expect(firstLogin.status).toBe(200);

    const badLogin = await app.request(
      "/auth/login",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ email: "user@example.com", password: "wrong-pass" })
      },
      env
    );

    expect(badLogin.status).toBe(401);
  });

  it("accepts legacy dev hashes and migrates them", async () => {
    const env = makeTestEnv();
    const legacyUser: UserRecord = {
      id: "legacy-id",
      email: "legacy@example.com",
      role: "viewer",
      password_hash: "dev-legacy-pass"
    };
    env.__users.set(legacyUser.email, legacyUser);

    const loginRes = await app.request(
      "/auth/login",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ email: "legacy@example.com", password: "legacy-pass" })
      },
      env
    );

    expect(loginRes.status).toBe(200);
    const migrated = env.__users.get("legacy@example.com");
    expect(migrated?.password_hash.startsWith("$2")).toBe(true);
  });
});

describe("file signing flow", () => {
  it("returns a signed upload URL", async () => {
    const env = makeTestEnv();
    const token = await loginAndGetToken(env);

    const res = await app.request(
      "/api/files/sign-upload",
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          filename: "documento.pdf",
          contentType: "application/pdf",
          prefix: "documents"
        })
      },
      env
    );

    expect(res.status).toBe(200);
    const json = (await res.json()) as { url: string; key: string; requiredHeaders?: Record<string, string> };
    expect(json.key).toMatch(/^documents\//);
    expect(json.url).toContain("X-Amz-Algorithm=AWS4-HMAC-SHA256");
    expect(json.url).toContain("X-Amz-Signature=");
    expect(json.requiredHeaders).toEqual({ "Content-Type": "application/pdf" });
  });

  it("clamps upload expiry and sanitizes key", async () => {
    const env = makeTestEnv();
    const token = await loginAndGetToken(env);

    const res = await app.request(
      "/api/files/sign-upload",
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          filename: "relatorio final 2026!!.pdf",
          contentType: "application/pdf",
          prefix: "tmp",
          expiresIn: 99999
        })
      },
      env
    );

    expect(res.status).toBe(200);
    const json = (await res.json()) as { url: string; key: string };
    expect(json.key).toMatch(/^tmp\//);
    expect(json.key).not.toContain(" ");
    expect(json.key).toContain("relatorio-final-2026");

    const parsed = new URL(json.url);
    expect(parsed.searchParams.get("X-Amz-Expires")).toBe("3600");
  });

  it("rejects signing when credentials are missing", async () => {
    const env = makeTestEnv();
    env.R2_SECRET_ACCESS_KEY = "";
    const token = await loginAndGetToken(env);

    const res = await app.request(
      "/api/files/sign-upload",
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ filename: "documento.pdf", contentType: "application/pdf" })
      },
      env
    );

    expect(res.status).toBe(501);
  });

  it("returns a signed download URL", async () => {
    const env = makeTestEnv();
    const token = await loginAndGetToken(env);

    const res = await app.request(
      "/api/files/sign-download?key=documents/example.pdf",
      {
        headers: {
          Authorization: `Bearer ${token}`
        }
      },
      env
    );

    expect(res.status).toBe(200);
    const json = (await res.json()) as { url: string; key: string };
    expect(json.key).toBe("documents/example.pdf");
    expect(json.url).toContain("X-Amz-Algorithm=AWS4-HMAC-SHA256");
    expect(json.url).toContain("X-Amz-Signature=");
  });

  it("clamps download expiry from query", async () => {
    const env = makeTestEnv();
    const token = await loginAndGetToken(env);

    const res = await app.request(
      "/api/files/sign-download?key=documents/example.pdf&expiresIn=1",
      {
        headers: {
          Authorization: `Bearer ${token}`
        }
      },
      env
    );

    expect(res.status).toBe(200);
    const json = (await res.json()) as { url: string };
    const parsed = new URL(json.url);
    expect(parsed.searchParams.get("X-Amz-Expires")).toBe("60");
  });

  it("rejects provided keys with invalid prefixes", async () => {
    const env = makeTestEnv();
    const token = await loginAndGetToken(env);

    const res = await app.request(
      "/api/files/sign-upload",
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          key: "private/secret.pdf",
          contentType: "application/pdf"
        })
      },
      env
    );

    expect(res.status).toBe(400);
  });
});

describe("pdf export", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("renders HTML with derived stats before sending to browser rendering", async () => {
    const env = makeTestEnv();
    env.BROWSER_RENDERING_ACCOUNT_ID = "account";
    env.BROWSER_RENDERING_API_TOKEN = "token";

    const token = await loginAndGetToken(env);

    const fetchMock = vi.fn(async (_input, init?: { body?: unknown }) => {
      void _input;
      void init;
      return new Response(new ArrayBuffer(8), {
        status: 200,
        headers: { "Content-Type": "application/pdf" }
      });
    });

    vi.stubGlobal("fetch", fetchMock);

    const res = await app.request(
      "/api/pdf",
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          title: "Relatório Cadeia",
          content: "Resumo",
          chains: [
            {
              titulo: "Cadeia Principal",
              documentos: [
                {
                  numero: "123",
                  tipo: "Matrícula",
                  lancamentos: [
                    { tipo: "Registro" },
                    { tipo: "Averbação" }
                  ]
                }
              ]
            }
          ]
        })
      },
      env
    );

    expect(res.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledOnce();
    const payload = fetchMock.mock.calls[0]?.[1]?.body;
    const parsed = payload ? JSON.parse(String(payload)) : {};
    expect(parsed.html).toContain("Documentos");
    expect(parsed.html).toContain(">1<");
    expect(parsed.html).toContain("Lançamentos");
    expect(parsed.html).toContain(">2<");
  });

  it("returns 501 when browser rendering is not configured", async () => {
    const env = makeTestEnv();
    env.BROWSER_RENDERING_ACCOUNT_ID = "";
    env.BROWSER_RENDERING_API_TOKEN = "";
    const token = await loginAndGetToken(env);

    const res = await app.request(
      "/api/pdf",
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ title: "Sem Config", content: "Teste" })
      },
      env
    );

    expect(res.status).toBe(501);
  });
});
