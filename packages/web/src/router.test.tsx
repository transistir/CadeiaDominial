import { RouterProvider } from "@tanstack/react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, act } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";

const graphModule = vi.hoisted(() => {
  let resolve: ((mod: { default: () => JSX.Element }) => void) | null = null;
  const promise = new Promise<{ default: () => JSX.Element }>((res) => {
    resolve = res;
  });

  return {
    promise,
    resolve: resolve as (mod: { default: () => JSX.Element }) => void
  };
});

vi.mock("./routes/graph", () => graphModule.promise);

describe("router lazy-loaded graph route", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("shows loading state and resolves graph route without console errors", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify({ ok: true, timestamp: "2026-01-26T00:00:00.000Z" }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      )
    );

    vi.stubGlobal("fetch", fetchMock);

    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});

    const { router } = await import("./router");
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } }
    });

    render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    );

    const navigation = router.navigate({ to: "/graph" });

    expect(await screen.findByText(/loading graph/i)).toBeInTheDocument();
    await act(async () => {
      graphModule.resolve({
        default: () => <div data-testid="graph-route">Graph Route Loaded</div>
      });
    });
    await navigation;

    expect(await screen.findByTestId("graph-route")).toBeInTheDocument();
    expect(consoleError).not.toHaveBeenCalled();
  });
});
