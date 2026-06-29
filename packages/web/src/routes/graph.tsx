import { useEffect, useMemo, useState } from "react";
import { GraphView, buildGraph } from "../graph";
import type { ChainData, GraphJson } from "../graph";
import { generateMockGraph, type MockShape } from "../graph/mock";
import "./graph.css";

const DEFAULT_IMOVEL_ID = "4";

/** Reads a query-string param from the current URL (null when absent / SSR). */
function readSearchParam(name: string): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return new URLSearchParams(window.location.search).get(name);
}

/**
 * Dev fallback: the deterministic mock generator with its shape selector.
 * Reachable via `/graph?mock=1` (or `?mock=linear` etc — any truthy value).
 */
function MockGraph() {
  const [shape, setShape] = useState<MockShape>("complex");
  const graph = useMemo(() => generateMockGraph(shape), [shape]);

  return (
    <div className="graph-page">
      <div className="graph-page__toolbar">
        <label htmlFor="mock-shape-select">Cadeia (mock):</label>
        <select
          id="mock-shape-select"
          data-testid="mock-shape-select"
          value={shape}
          onChange={(e) => setShape(e.target.value as MockShape)}
        >
          <option value="linear">Linear</option>
          <option value="branching">Branching</option>
          <option value="merge">Merge</option>
          <option value="complex">Complexo</option>
        </select>
      </div>
      <GraphView graph={graph} />
    </div>
  );
}

/**
 * Default: fetch the real dominial chain from `GET /api/graph/:imovelId` and
 * run `buildGraph` on the returned `ChainData`. The endpoint is auth-protected,
 * so a bearer token (when present in localStorage) is attached. Cycle detection
 * and validation live inside `buildGraph`; a thrown error surfaces in the UI.
 */
function RealGraph({ imovelId }: { imovelId: string }) {
  const [graph, setGraph] = useState<GraphJson | null>(null);
  const [status, setStatus] = useState<"loading" | "error" | "ready">("loading");
  const [message, setMessage] = useState("");

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    setMessage("");

    const token =
      typeof window !== "undefined" ? window.localStorage.getItem("token") : null;

    fetch(`/api/graph/${imovelId}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {}
    })
      .then(async (res) => {
        if (!res.ok) {
          throw new Error(`Falha ao carregar a cadeia (HTTP ${res.status}).`);
        }
        return (await res.json()) as ChainData;
      })
      .then((chainData) => {
        if (cancelled) {
          return;
        }
        setGraph(buildGraph(chainData));
        setStatus("ready");
      })
      .catch((err: unknown) => {
        if (cancelled) {
          return;
        }
        setMessage(err instanceof Error ? err.message : String(err));
        setStatus("error");
      });

    return () => {
      cancelled = true;
    };
  }, [imovelId]);

  return (
    <div className="graph-page">
      <div className="graph-page__toolbar">
        <span>Imóvel {imovelId}</span>
        {status === "loading" && (
          <span data-testid="graph-loading">Carregando cadeia…</span>
        )}
        {status === "error" && (
          <span data-testid="graph-error" className="graph-page__error">
            {message}
          </span>
        )}
      </div>
      {graph && <GraphView graph={graph} />}
    </div>
  );
}

function GraphRoute() {
  const mockParam = readSearchParam("mock");
  const isMock =
    mockParam !== null && mockParam !== "0" && mockParam !== "false";
  const imovelId = readSearchParam("imovelId") ?? DEFAULT_IMOVEL_ID;

  return isMock ? <MockGraph /> : <RealGraph imovelId={imovelId} />;
}

export default GraphRoute;
