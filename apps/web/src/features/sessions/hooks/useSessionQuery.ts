"use client";

import type { SessionDto, ShotDto } from "@golf/contracts";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api-client";

export type ShotWithClip = ShotDto & { clipUrl: string | null };

interface SessionDetailResponse {
  data: { session: SessionDto; shots: ShotWithClip[] };
}

export function useSessionQuery(sessionId: string) {
  return useQuery({
    queryKey: ["sessions", sessionId],
    queryFn: async () => {
      const r = await api.get<SessionDetailResponse>(`/sessions/${sessionId}`);
      return r.data.data;
    },
    enabled: Boolean(sessionId),
  });
}
