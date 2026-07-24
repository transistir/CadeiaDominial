import { healthResponseSchema, pendenciaResponseSchema, type HealthResponse, type PendenciaResponse } from "@cadeia/shared";
import { z } from "zod";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";

export async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/health`);

  if (!response.ok) {
    throw new Error(`Health check failed with status ${response.status}`);
  }

  const json = await response.json();
  return healthResponseSchema.parse(json);
}

function getToken(): string | null {
  const raw = localStorage.getItem("token");
  return raw && raw !== "null" && raw !== "undefined" ? raw : null;
}

async function authHeaders(): Promise<Record<string, string>> {
  const token = getToken();
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

export async function fetchPendencias(): Promise<PendenciaResponse[]> {
  const res = await fetch(`${API_BASE_URL}/pendencias`, {
    headers: await authHeaders(),
  });

  if (!res.ok) {
    throw new Error(`Failed to fetch pendencies: ${res.status}`);
  }

  const json = await res.json();
  return z.array(pendenciaResponseSchema).parse(json);
}

export async function confirmarPendencia(id: number, criConfirmadoId?: number): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/pendencias/${id}/confirmar`, {
    method: "POST",
    headers: {
      ...(await authHeaders()),
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ cri_confirmado_id: criConfirmadoId }),
  });

  if (!res.ok) {
    throw new Error(`Failed to confirm pendencia: ${res.status}`);
  }
}

export async function rejeitarPendencia(id: number): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/pendencias/${id}/rejeitar`, {
    method: "POST",
    headers: await authHeaders(),
  });

  if (!res.ok) {
    throw new Error(`Failed to reject pendencia: ${res.status}`);
  }
}
