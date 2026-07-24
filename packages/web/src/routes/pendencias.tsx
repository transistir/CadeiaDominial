import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchPendencias, confirmarPendencia, rejeitarPendencia } from "../api";

export default function PendenciasPage() {
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const { data: pendencias, isLoading, error } = useQuery({
    queryKey: ["pendencias"],
    queryFn: fetchPendencias,
    refetchInterval: 30_000,
  });

  const confirmMutation = useMutation({
    mutationFn: (id: number) => confirmarPendencia(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pendencias"] });
      setSelectedId(null);
    },
  });

  const rejectMutation = useMutation({
    mutationFn: (id: number) => rejeitarPendencia(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pendencias"] });
      setSelectedId(null);
    },
  });

  if (isLoading) {
    return <div className="route-loading">Carregando pendências...</div>;
  }

  if (error) {
    return (
      <div className="health-error">
        Erro ao carregar pendências: {String(error)}
      </div>
    );
  }

  if (!pendencias || pendencias.length === 0) {
    return (
      <div className="app">
        <h1>Pendências de Cartório</h1>
        <p>Nenhuma pendência pendente. Todas as origens estão resolvidas.</p>
      </div>
    );
  }

  return (
    <div className="app" style={{ maxWidth: "960px", margin: "0 auto", padding: "1rem" }}>
      <h1>Pendências de Cartório</h1>
      <p style={{ color: "#666", marginBottom: "1.5rem" }}>
        {pendencias.length} pendência{pendencias.length !== 1 ? "s" : ""} aguardando revisão
      </p>

      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ textAlign: "left", borderBottom: "2px solid #ddd" }}>
            <th style={{ padding: "0.5rem" }}>ID</th>
            <th style={{ padding: "0.5rem" }}>Origem</th>
            <th style={{ padding: "0.5rem" }}>Tipo</th>
            <th style={{ padding: "0.5rem" }}>Confiança</th>
            <th style={{ padding: "0.5rem" }}>Cartório Sugerido</th>
            <th style={{ padding: "0.5rem" }}>Data</th>
            <th style={{ padding: "0.5rem" }}>Ações</th>
          </tr>
        </thead>
        <tbody>
          {pendencias.map((p) => (
            <tr
              key={p.id}
              style={{
                borderBottom: "1px solid #eee",
                backgroundColor: selectedId === p.id ? "#f0f7ff" : "transparent",
              }}
            >
              <td style={{ padding: "0.5rem" }}>{p.id}</td>
              <td style={{ padding: "0.5rem" }}>
                {p.origemNumero || p.origemNumeroRaw || `#${p.origemId}`}
              </td>
              <td style={{ padding: "0.5rem" }}>{p.origemTipo}</td>
              <td style={{ padding: "0.5rem" }}>
                <span
                  style={{
                    padding: "0.1rem 0.4rem",
                    borderRadius: "4px",
                    fontSize: "0.85em",
                    fontWeight: 600,
                    backgroundColor:
                      p.confianca === "fraca"
                        ? "#fff3cd"
                        : p.confianca === "alerta"
                          ? "#f8d7da"
                          : "#d1ecf1",
                    color:
                      p.confianca === "fraca"
                        ? "#856404"
                        : p.confianca === "alerta"
                          ? "#721c24"
                          : "#0c5460",
                  }}
                >
                  {p.confianca}
                </span>
              </td>
              <td style={{ padding: "0.5rem" }}>
                {p.criNome ? `${p.criNome} (${p.criCidade}/${p.criUf})` : "—"}
              </td>
              <td style={{ padding: "0.5rem", fontSize: "0.9em" }}>
                {new Date(p.createdAt).toLocaleDateString("pt-BR")}
              </td>
              <td style={{ padding: "0.5rem" }}>
                <button
                  onClick={() => {
                    setSelectedId(p.id);
                    confirmMutation.mutate(p.id);
                  }}
                  disabled={confirmMutation.isPending}
                  style={{
                    marginRight: "0.5rem",
                    padding: "0.3rem 0.7rem",
                    backgroundColor: "#28a745",
                    color: "#fff",
                    border: "none",
                    borderRadius: "4px",
                    cursor: "pointer",
                  }}
                >
                  Confirmar
                </button>
                <button
                  onClick={() => {
                    setSelectedId(p.id);
                    rejectMutation.mutate(p.id);
                  }}
                  disabled={rejectMutation.isPending}
                  style={{
                    padding: "0.3rem 0.7rem",
                    backgroundColor: "#dc3545",
                    color: "#fff",
                    border: "none",
                    borderRadius: "4px",
                    cursor: "pointer",
                  }}
                >
                  Rejeitar
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
