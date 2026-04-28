"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api-client";

interface AddInput {
  sessionId: string;
  tImpact: number;
  tStart: number;
  tEnd: number;
}

export function useAddManualShotMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ sessionId, ...body }: AddInput) => {
      await api.post(`/sessions/${sessionId}/shots`, body);
    },
    onSuccess: (_d, vars) =>
      qc.invalidateQueries({ queryKey: ["sessions", vars.sessionId] }),
  });
}
