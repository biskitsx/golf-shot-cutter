import { z } from "zod";
import { SessionStatus } from "./sessions";
import { ShotDto } from "./shots";

export const SseEventType = z.enum([
  "session.processing.started",
  "session.shot.detected",
  "session.ready",
  "session.failed",
]);

export const SseEventEnvelope = z.object({
  type: SseEventType,
  sessionId: z.string(),
  payload: z.record(z.unknown()),
  occurredAt: z.string().datetime(),
});
export type SseEventEnvelope = z.infer<typeof SseEventEnvelope>;

export const ShotDetectedPayload = z.object({ shot: ShotDto });
export const SessionReadyPayload = z.object({
  status: SessionStatus,
  shotCount: z.number().int().nonnegative(),
});
export const SessionFailedPayload = z.object({
  stage: z.string(),
  message: z.string(),
});
