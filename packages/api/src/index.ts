import { Hono, type Context } from "hono";
import { cors } from "hono/cors";
import { jwt, sign } from "hono/jwt";
import bcrypt from "bcryptjs";
import {
  healthResponseSchema,
  renderPdfTemplate,
  type HealthResponse,
  type PdfReport,
  type PdfChainSection
} from "@cadeia/shared";
import { createSignedUrl } from "./services/r2SignedUrl";
import { getFileFromBucket, putFileIntoBucket } from "./services/storage";

type D1Database = {
  prepare: (query: string) => {
    bind: (...values: unknown[]) => {
      first: <T = Record<string, unknown>>() => Promise<T | null>;
      run: () => Promise<unknown>;
    };
  };
};

type ReadableStreamLike = ReadableStream<Uint8Array> | ArrayBuffer;

type R2Object = {
  body: ReadableStreamLike | null;
  etag: string;
  size: number;
  httpMetadata?: {
    contentType?: string;
  };
};

type R2Bucket = {
  get: (key: string) => Promise<R2Object | null>;
  put: (
    key: string,
    value: ArrayBuffer | ReadableStreamLike,
    options?: { httpMetadata?: { contentType?: string } }
  ) => Promise<unknown>;
  delete: (key: string) => Promise<void>;
};

type Env = {
  Bindings: {
    JWT_SECRET: string;
    DB: D1Database;
    R2: R2Bucket;
    BROWSER_RENDERING_ACCOUNT_ID: string;
    BROWSER_RENDERING_API_TOKEN: string;
    ALLOW_DEV_BOOTSTRAP?: string;
    R2_ACCOUNT_ID: string;
    R2_ACCESS_KEY_ID: string;
    R2_SECRET_ACCESS_KEY: string;
    R2_BUCKET_NAME: string;
    R2_PUBLIC_HOST?: string;
  };
};

const deriveStatsFromChains = (chains: PdfChainSection[]) => {
  let documentos = 0;
  let lancamentos = 0;
  let registros = 0;
  let averbacoes = 0;

  for (const section of chains) {
    for (const documento of section.documentos ?? []) {
      documentos += 1;
      for (const lancamento of documento.lancamentos ?? []) {
        lancamentos += 1;
        const tipo = (lancamento.tipo ?? "").toLowerCase();
        if (tipo.includes("registro")) {
          registros += 1;
        } else if (tipo.includes("averba")) {
          averbacoes += 1;
        }
      }
    }
  }

  return {
    documentos,
    lancamentos,
    registros,
    averbacoes,
    origens: 0
  };
};

const ALLOWED_STORAGE_PREFIXES = new Set(["documents", "exports", "tmp"]);

const isBcryptHash = (hash: string) =>
  hash.startsWith("$2a$") || hash.startsWith("$2b$") || hash.startsWith("$2y$");

const sanitizeKeySegments = (rawKey: string) => {
  const segments = rawKey
    .replaceAll("\\", "/")
    .split("/")
    .filter(Boolean)
    .map((segment) =>
      segment.replace(/[^a-zA-Z0-9._-]+/g, "-").replace(/^-+|-+$/g, "")
    );

  if (segments.length === 0 || segments.some((segment) => segment.length === 0)) {
    return null;
  }

  return segments;
};

const normalizeStorageKey = (
  rawKey: string,
  options: { requirePrefix?: boolean } = {}
) => {
  const cleaned = rawKey.trim().replaceAll("\\", "/").replace(/^\/+|\/+$/g, "");
  if (!cleaned) {
    return null;
  }

  const segments = sanitizeKeySegments(cleaned);
  if (!segments || segments.some((segment) => segment === "." || segment === "..")) {
    return null;
  }

  const normalized = segments.join("/");
  if (normalized !== cleaned) {
    return null;
  }

  if (segments.length > 1 && !ALLOWED_STORAGE_PREFIXES.has(segments[0])) {
    return null;
  }

  if (options.requirePrefix && !ALLOWED_STORAGE_PREFIXES.has(segments[0])) {
    return null;
  }

  return normalized;
};

const mergeReportStats = (report: PdfReport | undefined, chains: PdfChainSection[] | undefined) => {
  if (!chains || chains.length === 0) {
    return report;
  }

  const derivedStats = deriveStatsFromChains(chains);
  return {
    ...report,
    estatisticas: {
      ...derivedStats,
      ...(report?.estatisticas ?? {})
    }
  };
};

const app = new Hono<Env>();

app.use("*", cors());

app.get("/health", (c) => {
  const response: HealthResponse = {
    ok: true,
    timestamp: new Date().toISOString()
  };

  const parsed = healthResponseSchema.parse(response);
  return c.json(parsed);
});

const authMiddleware = async (c: Context<Env>, next: () => Promise<void>) => {
  const middleware = jwt({ secret: c.env.JWT_SECRET, alg: "HS256" });
  return middleware(c, next);
};

app.post("/auth/login", async (c) => {
  const body = await c.req.json().catch(() => ({}));
  const email = typeof body?.email === "string" ? body.email.trim() : "";
  const password = typeof body?.password === "string" ? body.password : "";

  if (!email || !password) {
    return c.json({ error: "Email and password are required." }, 400);
  }

  const existingUser = await c.env.DB.prepare(
    "SELECT id, email, role, password_hash FROM users WHERE email = ?"
  )
    .bind(email)
    .first<{
      id: string;
      email: string;
      role: string;
      password_hash: string;
    }>();

  const allowBootstrap = c.env.ALLOW_DEV_BOOTSTRAP === "true";
  let user = existingUser;

  if (!user && allowBootstrap) {
    const id = crypto.randomUUID();
    const passwordHash = await bcrypt.hash(password, 10);
    const role = "viewer";

    await c.env.DB.prepare(
      "INSERT INTO users (id, email, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)"
    )
      .bind(id, email, passwordHash, role, Date.now())
      .run();

    user = { id, email, role, password_hash: passwordHash };
  }

  if (!user) {
    return c.json({ error: "Invalid credentials" }, 401);
  }

  let passwordMatches = false;

  if (isBcryptHash(user.password_hash)) {
    try {
      passwordMatches = await bcrypt.compare(password, user.password_hash);
    } catch {
      passwordMatches = false;
    }
  } else if (user.password_hash.startsWith("dev-")) {
    passwordMatches = user.password_hash === `dev-${password}`;
    if (passwordMatches) {
      const passwordHash = await bcrypt.hash(password, 10);
      await c.env.DB.prepare("UPDATE users SET password_hash = ? WHERE id = ?")
        .bind(passwordHash, user.id)
        .run();
      user = { ...user, password_hash: passwordHash };
    }
  }

  if (!passwordMatches) {
    return c.json({ error: "Invalid credentials" }, 401);
  }

  const now = Math.floor(Date.now() / 1000);
  const token = await sign(
    {
      sub: user.id,
      role: user.role,
      iat: now,
      exp: now + 60 * 60 * 12
    },
    c.env.JWT_SECRET
  );
  return c.json({ token, user: { id: user.id, email: user.email, role: user.role } });
});

app.get("/auth/session", authMiddleware, (c) => {
  const payload = c.get("jwtPayload");
  return c.json({ authenticated: true, payload });
});

app.get("/protected", authMiddleware, (c) => {
  return c.json({ ok: true });
});

app.post("/api/pdf", authMiddleware, async (c) => {
  if (!c.env.BROWSER_RENDERING_ACCOUNT_ID || !c.env.BROWSER_RENDERING_API_TOKEN) {
    return c.json({ error: "Browser Rendering is not configured." }, 501);
  }

  const body = await c.req.json().catch(() => ({}));
  const title = typeof body?.title === "string" ? body.title : "Cadeia Dominial";
  const subtitle = typeof body?.subtitle === "string" ? body.subtitle : undefined;
  const content = typeof body?.content === "string" ? body.content : "Documento gerado.";
  const report =
    typeof body?.report === "object" && body.report ? (body.report as PdfReport) : undefined;
  const chains = Array.isArray(body?.chains) ? (body.chains as PdfChainSection[]) : undefined;
  const reportWithStats = mergeReportStats(report, chains);
  const html =
    typeof body?.html === "string"
      ? body.html
      : renderPdfTemplate({
          title,
          subtitle,
          body: content,
          report: reportWithStats,
          chains
        });

  const endpoint = `https://api.cloudflare.com/client/v4/accounts/${c.env.BROWSER_RENDERING_ACCOUNT_ID}/browser-rendering/pdf`;
  const response = await fetch(endpoint, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${c.env.BROWSER_RENDERING_API_TOKEN}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ html })
  });

  if (!response.ok) {
    const errorText = await response.text();
    return c.json({ error: "PDF rendering failed.", details: errorText }, 502);
  }

  const pdfBuffer = await response.arrayBuffer();
  return c.body(pdfBuffer, 200, {
    "Content-Type": "application/pdf",
    "Content-Disposition": "attachment; filename=\"cadeia-dominial.pdf\""
  });
});

app.post("/api/files", authMiddleware, async (c) => {
  const formData = await c.req.formData().catch(() => null);
  if (!formData) {
    return c.json({ error: "Expected multipart form data." }, 400);
  }

  const file = formData.get("file");
  if (!file || typeof file !== "object" || typeof (file as { arrayBuffer?: unknown }).arrayBuffer !== "function") {
    return c.json({ error: "File is required." }, 400);
  }

  const fileObject = file as {
    arrayBuffer: () => Promise<ArrayBuffer>;
    type?: string;
    name?: string;
    size?: number;
  };

  const providedKey = formData.get("key");
  const key =
    typeof providedKey === "string" && providedKey.trim().length > 0
      ? providedKey.trim()
      : `${crypto.randomUUID()}-${fileObject.name ?? "upload.bin"}`;

  const result = await putFileIntoBucket(c.env.R2, key, fileObject);
  return c.json(result, 201);
});

app.get("/api/files/sign-download", authMiddleware, async (c) => {
  if (!c.env.R2_ACCOUNT_ID || !c.env.R2_ACCESS_KEY_ID || !c.env.R2_SECRET_ACCESS_KEY) {
    return c.json({ error: "R2 signing is not configured." }, 501);
  }

  const keyParam = c.req.query("key");
  const keyInput = typeof keyParam === "string" ? keyParam : "";
  const key = normalizeStorageKey(keyInput);
  if (!key) {
    return c.json({ error: "Invalid key format." }, 400);
  }

  const expiresInParam = c.req.query("expiresIn");
  const expiresIn = Math.min(Math.max(Number(expiresInParam ?? 900), 60), 3600);
  const host = c.env.R2_PUBLIC_HOST || `${c.env.R2_ACCOUNT_ID}.r2.cloudflarestorage.com`;

  const signed = await createSignedUrl({
    method: "GET",
    host,
    bucket: c.env.R2_BUCKET_NAME,
    key,
    accessKeyId: c.env.R2_ACCESS_KEY_ID,
    secretAccessKey: c.env.R2_SECRET_ACCESS_KEY,
    expiresIn
  });

  return c.json({
    key,
    url: signed.url,
    expiresAt: signed.expiresAt,
    method: "GET"
  });
});

app.get("/api/files", authMiddleware, async (c) => {
  const keyParam = c.req.query("key");
  const keyInput = typeof keyParam === "string" ? keyParam : "";
  const key = normalizeStorageKey(keyInput);
  if (!key) {
    return c.json({ error: "Invalid key format." }, 400);
  }

  const object = await getFileFromBucket(c.env.R2, key);
  if (!object || !object.body) {
    return c.json({ error: "File not found." }, 404);
  }

  return new Response(object.body, {
    status: 200,
    headers: {
      "Content-Type": object.httpMetadata?.contentType ?? "application/octet-stream",
      "Content-Disposition": `inline; filename="${key}"`,
      ETag: object.etag
    }
  });
});

app.get("/api/files/:key", authMiddleware, async (c) => {
  // R5-3 (typecheck fix, same as fix-ci PR): defensive guard for
  // c.req.param('key') which can return string | undefined.
  const keyParam = c.req.param("key");
  const keyInput = typeof keyParam === "string" ? keyParam : "";
  const key = normalizeStorageKey(keyInput);
  if (!key) {
    return c.json({ error: "Invalid key format." }, 400);
  }
  const object = await getFileFromBucket(c.env.R2, key);
  if (!object || !object.body) {
    return c.json({ error: "File not found." }, 404);
  }

  return new Response(object.body, {
    status: 200,
    headers: {
      "Content-Type": object.httpMetadata?.contentType ?? "application/octet-stream",
      "Content-Disposition": `inline; filename="${key}"`,
      ETag: object.etag
    }
  });
});

app.post("/api/files/sign-upload", authMiddleware, async (c) => {
  if (!c.env.R2_ACCOUNT_ID || !c.env.R2_ACCESS_KEY_ID || !c.env.R2_SECRET_ACCESS_KEY) {
    return c.json({ error: "R2 signing is not configured." }, 501);
  }

  const body = await c.req.json().catch(() => ({}));
  const contentType = typeof body?.contentType === "string" ? body.contentType : undefined;
  const filename = typeof body?.filename === "string" ? body.filename : "upload.bin";
  const expiresIn = Math.min(Math.max(Number(body?.expiresIn ?? 900), 60), 3600);
  const requestedPrefix = typeof body?.prefix === "string" ? body.prefix : "";
  const prefix = ALLOWED_STORAGE_PREFIXES.has(requestedPrefix) ? requestedPrefix : "documents";
  const sanitizedFilename = filename.replace(/[^a-zA-Z0-9._-]+/g, "-").replace(/^-+|-+$/g, "");
  const requestedKey = typeof body?.key === "string" ? body.key.trim() : "";
  let key = "";

  if (requestedKey) {
    const normalizedKey = normalizeStorageKey(requestedKey, { requirePrefix: true });
    if (!normalizedKey) {
      return c.json({ error: "Invalid key format." }, 400);
    }
    key = normalizedKey;
  } else {
    key = `${prefix}/${crypto.randomUUID()}-${sanitizedFilename || "upload.bin"}`;
  }

  const host = c.env.R2_PUBLIC_HOST || `${c.env.R2_ACCOUNT_ID}.r2.cloudflarestorage.com`;

  const signed = await createSignedUrl({
    method: "PUT",
    host,
    bucket: c.env.R2_BUCKET_NAME,
    key,
    accessKeyId: c.env.R2_ACCESS_KEY_ID,
    secretAccessKey: c.env.R2_SECRET_ACCESS_KEY,
    expiresIn,
    contentType
  });

  return c.json({
    key,
    url: signed.url,
    expiresAt: signed.expiresAt,
    method: "PUT",
    requiredHeaders: signed.requiredHeaders
  });
});

app.get("/api/files/:key/sign-download", authMiddleware, async (c) => {
  if (!c.env.R2_ACCOUNT_ID || !c.env.R2_ACCESS_KEY_ID || !c.env.R2_SECRET_ACCESS_KEY) {
    return c.json({ error: "R2 signing is not configured." }, 501);
  }

  // R5-3 (typecheck fix, same as fix-ci PR): defensive guard for
  // c.req.param('key') which can return string | undefined.
  const keyParam = c.req.param("key");
  const keyInput = typeof keyParam === "string" ? keyParam : "";
  const key = normalizeStorageKey(keyInput);
  if (!key) {
    return c.json({ error: "Invalid key format." }, 400);
  }
  const expiresInParam = c.req.query("expiresIn");
  const expiresIn = Math.min(Math.max(Number(expiresInParam ?? 900), 60), 3600);
  const host = c.env.R2_PUBLIC_HOST || `${c.env.R2_ACCOUNT_ID}.r2.cloudflarestorage.com`;

  const signed = await createSignedUrl({
    method: "GET",
    host,
    bucket: c.env.R2_BUCKET_NAME,
    key,
    accessKeyId: c.env.R2_ACCESS_KEY_ID,
    secretAccessKey: c.env.R2_SECRET_ACCESS_KEY,
    expiresIn
  });

  return c.json({
    key,
    url: signed.url,
    expiresAt: signed.expiresAt,
    method: "GET"
  });
});

export default app;
