import { z } from "zod";

export const healthResponseSchema = z.object({
  ok: z.boolean(),
  timestamp: z.string()
});

export type HealthResponse = z.infer<typeof healthResponseSchema>;
