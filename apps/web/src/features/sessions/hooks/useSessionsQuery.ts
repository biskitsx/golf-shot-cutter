"use client";

import type { SessionDto } from "@golf/contracts";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api-client";

interface ListResponse {
  data: SessionDto[];
}

export function useSessionsQuery() {
  return useQuery({
    queryKey: ["sessions"],
    queryFn: async () => {
      const r = await api.get<ListResponse>("/sessions");
      return r.data.data;
    },
  });
}
