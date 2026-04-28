"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api-client";

interface CreateInput {
  originalFilename: string;
  preRollSeconds?: number;
  postRollSeconds?: number;
}

interface CreateResponse {
  data: { sessionId: string; signedUploadUrl: string; expiresAt: string };
}

export function useCreateSessionMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: CreateInput) => {
      const r = await api.post<CreateResponse>("/sessions", input);
      return r.data.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sessions"] }),
  });
}
