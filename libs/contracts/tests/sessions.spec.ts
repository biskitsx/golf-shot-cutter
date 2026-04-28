import { describe, expect, it } from "vitest";
import { CreateSessionRequest, SessionDto } from "../src/sessions";

describe("SessionDto", () => {
  it("parses a valid session payload", () => {
    const parsed = SessionDto.parse({
      id: "ses_01H...",
      userId: null,
      rawVideoKey: "raw/abc/video.mp4",
      status: "queued",
      preRollSeconds: 2.0,
      postRollSeconds: 5.0,
      shotCount: 0,
      durationSeconds: 923.4,
      error: null,
      createdAt: "2026-04-27T10:00:00.000Z",
      updatedAt: "2026-04-27T10:00:00.000Z",
    });
    expect(parsed.status).toBe("queued");
  });

  it("rejects a status outside the enum", () => {
    expect(() => SessionDto.parse({ status: "weird" } as unknown)).toThrow();
  });
});

describe("CreateSessionRequest", () => {
  it("requires a non-empty originalFilename", () => {
    expect(() =>
      CreateSessionRequest.parse({ originalFilename: "" }),
    ).toThrow();
  });
});
