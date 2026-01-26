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
            return {};
          }
        })
      })
    }
  };
};

describe("api health", () => {
  it("responds with ok and timestamp", async () => {
    const res = await app.request("/health", {}, makeTestEnv());
    const json = await res.json();

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
    const { token } = await loginRes.json();
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
    expect(sessionJson).toHaveProperty("payload.sub", "user@example.com");
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
});
