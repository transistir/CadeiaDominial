import { fetchHealth } from "./api";

describe("fetchHealth", () => {
  it("parses a valid health response", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify({ ok: true, timestamp: "2026-01-26T00:00:00.000Z" }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      )
    );

    vi.stubGlobal("fetch", fetchMock);

    const result = await fetchHealth();

    expect(result.ok).toBe(true);
    expect(result.timestamp).toBe("2026-01-26T00:00:00.000Z");

    vi.unstubAllGlobals();
  });
});
