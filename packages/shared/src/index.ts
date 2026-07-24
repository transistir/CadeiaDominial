import { z } from "zod";
import { renderPdfTemplate } from "./pdf";

export const healthResponseSchema = z.object({
  ok: z.boolean(),
  timestamp: z.string()
});

export type HealthResponse = z.infer<typeof healthResponseSchema>;

export * from "./pdf";
export { renderPdfTemplate };

// =============================================================================
// Pendencia Cartório types
// =============================================================================

export const pendenciaResponseSchema = z.object({
  id: z.number(),
  origemId: z.number(),
  criSugeridoId: z.number().nullable(),
  confianca: z.enum(["fraca", "forte", "alerta"]),
  status: z.enum(["pendente", "confirmada", "rejeitada"]),
  resolvidoPor: z.string().nullable(),
  resolvidoEm: z.string().nullable(),
  criConfirmadoId: z.number().nullable(),
  createdAt: z.string(),
  origemTipo: z.string(),
  origemNumero: z.string().nullable(),
  origemNumeroRaw: z.string().nullable(),
  criNome: z.string().nullable(),
  criCidade: z.string().nullable(),
  criUf: z.string().nullable(),
});

export type PendenciaResponse = z.infer<typeof pendenciaResponseSchema>;
