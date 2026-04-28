"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api-client";

interface DeleteInput {
  sessionId: string;
  shotId: string;
}

export function useDeleteShotMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ sessionId, shotId }: DeleteInput) => {
      await api.delete(`/sessions/${sessionId}/shots/${shotId}`);
    },
    onSuccess: (_d, vars) =>
      qc.invalidateQueries({ queryKey: ["sessions", vars.sessionId] }),
  });
}
