"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api-client";

interface MeResponse {
  data: { userId: string };
}

export function useMeQuery() {
  return useQuery({
    queryKey: ["auth", "me"],
    queryFn: async () => {
      const r = await api.get<MeResponse>("/auth/me");
      return r.data.data;
    },
  });
}
