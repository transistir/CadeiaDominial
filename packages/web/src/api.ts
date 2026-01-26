import { healthResponseSchema, type HealthResponse } from "@cadeia/shared";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";

export async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/health`);

  if (!response.ok) {
    throw new Error(`Health check failed with status ${response.status}`);
  }

  const json = await response.json();
  return healthResponseSchema.parse(json);
}
