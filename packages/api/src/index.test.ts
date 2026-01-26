import app from "./index";

describe("api health", () => {
  it("responds with ok and timestamp", async () => {
    const res = await app.request("/health");
    const json = await res.json();

    expect(res.status).toBe(200);
    expect(json).toHaveProperty("ok", true);
    expect(typeof json.timestamp).toBe("string");
  });
});
