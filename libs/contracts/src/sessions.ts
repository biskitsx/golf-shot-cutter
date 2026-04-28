import { z } from "zod";

export const SessionStatus = z.enum([
  "uploading",
  "queued",
  "processing",
  "ready",
  "failed",
]);
export type SessionStatus = z.infer<typeof SessionStatus>;

export const SessionError = z.object({
  stage: z.string(),
  message: z.string(),
});

export const SessionDto = z.object({
  id: z.string(),
  userId: z.string().nullable(),
  rawVideoKey: z.string(),
  status: SessionStatus,
  preRollSeconds: z.number().nonnegative(),
  postRollSeconds: z.number().nonnegative(),
  shotCount: z.number().int().nonnegative(),
  durationSeconds: z.number().nonnegative(),
  error: SessionError.nullable(),
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime(),
});
export type SessionDto = z.infer<typeof SessionDto>;

export const CreateSessionRequest = z.object({
  originalFilename: z.string().min(1),
  preRollSeconds: z.number().nonnegative().default(2.0),
  postRollSeconds: z.number().nonnegative().default(5.0),
});
export type CreateSessionRequest = z.infer<typeof CreateSessionRequest>;

export const CreateSessionResponse = z.object({
  sessionId: z.string(),
  signedUploadUrl: z.string().url(),
  expiresAt: z.string().datetime(),
});
export type CreateSessionResponse = z.infer<typeof CreateSessionResponse>;
