import { createRootRoute, createRoute, createRouter } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { fetchHealth } from "./api";
import GraphRoute from "./routes/graph";

const rootRoute = createRootRoute({
  component: () => {
    const { data, isLoading, error } = useQuery({
      queryKey: ["health"],
      queryFn: fetchHealth
    });

    return (
      <div className="app">
        <header className="hero">
          <p className="hero-eyebrow">Cadeia Dominial</p>
          <h1>Track land records with clarity.</h1>
          <p className="hero-copy">
            A modern registry workspace that maps ownership history, verifies sources,
            and keeps every title decision transparent.
          </p>
        </header>
        <section className="highlight-grid">
          <div className="highlight">
            <h2>Verified Threads</h2>
            <p>Link each document to its legal basis with audit-ready metadata.</p>
          </div>
          <div className="highlight">
            <h2>Interactive Trees</h2>
            <p>Visualize parcels, transfers, and annotations in a live graph.</p>
          </div>
          <div className="highlight">
            <h2>Field-Ready Reports</h2>
            <p>Export clean summaries for registrars, notaries, and legal teams.</p>
          </div>
        </section>
        <section className="health-panel">
          <h2>API Health</h2>
          {isLoading && <p>Checking API...</p>}
          {error && <p className="health-error">API unavailable.</p>}
          {data && (
            <dl>
              <div>
                <dt>Status</dt>
                <dd>{data.ok ? "OK" : "Not OK"}</dd>
              </div>
              <div>
                <dt>Timestamp</dt>
                <dd>{data.timestamp}</dd>
              </div>
            </dl>
          )}
        </section>
      </div>
    );
  }
});

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: () => null
});

const graphRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/graph",
  component: GraphRoute
});

const routeTree = rootRoute.addChildren([indexRoute, graphRoute]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
