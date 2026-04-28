"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api-client";

interface RawUrlResponse {
  data: { url: string; expiresAt: string };
}

export function useRawVideoUrlQuery(sessionId: string) {
  return useQuery({
    queryKey: ["sessions", sessionId, "raw-url"],
    queryFn: async () => {
      const r = await api.get<RawUrlResponse>(`/sessions/${sessionId}/raw-url`);
      return r.data.data;
    },
    enabled: Boolean(sessionId),
  });
}
