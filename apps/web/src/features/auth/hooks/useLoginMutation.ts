"use client";

import { useMutation } from "@tanstack/react-query";

import { api } from "@/lib/api-client";

interface LoginInput {
  email: string;
  password: string;
}

export function useLoginMutation() {
  return useMutation({
    mutationFn: async ({ email, password }: LoginInput) => {
      await api.post("/auth/login", { email, password });
    },
  });
}
