import { z } from "zod";

export const ShotSource = z.enum(["auto", "manual"]);
export type ShotSource = z.infer<typeof ShotSource>;

export const ShotDto = z.object({
  id: z.string(),
  sessionId: z.string(),
  index: z.number().int().positive(),
  tImpact: z.number().nonnegative(),
  tStart: z.number().nonnegative(),
  tEnd: z.number().nonnegative(),
  confidence: z.number().min(0).max(1),
  source: ShotSource,
  clipKey: z.string().nullable(),
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime(),
});
export type ShotDto = z.infer<typeof ShotDto>;

export const UpdateShotBoundaryRequest = z.object({
  tStart: z.number().nonnegative(),
  tEnd: z.number().nonnegative(),
});
export type UpdateShotBoundaryRequest = z.infer<
  typeof UpdateShotBoundaryRequest
>;

export const AddManualShotRequest = z.object({
  tImpact: z.number().nonnegative(),
  tStart: z.number().nonnegative(),
  tEnd: z.number().nonnegative(),
});
export type AddManualShotRequest = z.infer<typeof AddManualShotRequest>;
