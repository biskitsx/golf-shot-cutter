"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api-client";

interface UpdateInput {
  sessionId: string;
  shotId: string;
  tStart: number;
  tEnd: number;
}

export function useUpdateShotBoundaryMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ sessionId, shotId, tStart, tEnd }: UpdateInput) => {
      await api.patch(`/sessions/${sessionId}/shots/${shotId}`, {
        tStart,
        tEnd,
      });
    },
    onSuccess: (_d, vars) =>
      qc.invalidateQueries({ queryKey: ["sessions", vars.sessionId] }),
  });
}
