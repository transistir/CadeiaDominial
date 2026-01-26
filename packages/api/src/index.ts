import { Hono, type Context } from "hono";
import { cors } from "hono/cors";
import { jwt, sign } from "hono/jwt";
import { healthResponseSchema, type HealthResponse } from "@cadeia/shared";

type D1Database = {
  prepare: (query: string) => {
    bind: (...values: unknown[]) => {
      first: <T = Record<string, unknown>>() => Promise<T | null>;
      run: () => Promise<unknown>;
    };
  };
};

type Env = {
  Bindings: {
    JWT_SECRET: string;
    DB: D1Database;
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
  const email = typeof body?.email === "string" ? body.email : "user@example.com";
  const password = typeof body?.password === "string" ? body.password : "dev-password";
  const role = "viewer";

  const existingUser = await c.env.DB.prepare(
    "SELECT id, email, role FROM users WHERE email = ?"
  )
    .bind(email)
    .first();

  if (!existingUser) {
    await c.env.DB.prepare(
      "INSERT INTO users (id, email, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)"
    )
      .bind(crypto.randomUUID(), email, `dev-${password}`, role, Date.now())
      .run();
  }

  const token = await sign({ sub: email, role }, c.env.JWT_SECRET);
  return c.json({ token });
});

app.get("/auth/session", authMiddleware, (c) => {
  const payload = c.get("jwtPayload");
  return c.json({ authenticated: true, payload });
});

app.get("/protected", authMiddleware, (c) => {
  return c.json({ ok: true });
});

export default app;
