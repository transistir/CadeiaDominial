import { healthResponseSchema, type HealthResponse } from "@cadeia/shared";

export const healthResponse: HealthResponse = {
  ok: true,
  timestamp: new Date().toISOString()
};

export const healthResponseParsed = healthResponseSchema.parse(healthResponse);
