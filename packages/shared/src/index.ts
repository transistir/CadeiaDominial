import { z } from "zod";
import { renderPdfTemplate } from "./pdf";

export const healthResponseSchema = z.object({
  ok: z.boolean(),
  timestamp: z.string()
});

export type HealthResponse = z.infer<typeof healthResponseSchema>;

export * from "./pdf";
export { renderPdfTemplate };
