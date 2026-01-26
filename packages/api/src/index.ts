import { Hono } from "hono";
import { cors } from "hono/cors";
import { healthResponseSchema, type HealthResponse } from "@cadeia/shared";

type Env = {
  Bindings: Record<string, never>;
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

export default app;
