import app from "./index";

const testEnv = {
  JWT_SECRET: "test-secret",
  DB: {
    prepare: () => ({
      bind: () => ({
        first: async () => null,
        run: async () => ({})
      })
    })
  }
};

describe("api health", () => {
  it("responds with ok and timestamp", async () => {
    const res = await app.request("/health", {}, testEnv);
    const json = await res.json();

    expect(res.status).toBe(200);
    expect(json).toHaveProperty("ok", true);
    expect(typeof json.timestamp).toBe("string");
  });
});

describe("auth flow", () => {
  it("rejects session without token", async () => {
    const res = await app.request("/auth/session", {}, testEnv);
    expect(res.status).toBe(401);
  });

  it("returns a token and validates session", async () => {
    const loginRes = await app.request(
      "/auth/login",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ email: "user@example.com", password: "dev-password" })
      },
      testEnv
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
      testEnv
    );

    expect(sessionRes.status).toBe(200);
    const sessionJson = await sessionRes.json();
    expect(sessionJson).toHaveProperty("authenticated", true);
    expect(sessionJson).toHaveProperty("payload.sub", "user@example.com");
  });
});
