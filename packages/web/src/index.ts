import { healthResponseSchema, type HealthResponse } from "@cadeia/shared";

export function parseHealthResponse(input: unknown): HealthResponse {
  return healthResponseSchema.parse(input);
}
