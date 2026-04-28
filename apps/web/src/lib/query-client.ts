import { QueryClient } from "@tanstack/react-query";

export function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: Number.POSITIVE_INFINITY,
        gcTime: 1000 * 60 * 30,
        retry: 1,
        refetchOnWindowFocus: false,
      },
    },
  });
}
