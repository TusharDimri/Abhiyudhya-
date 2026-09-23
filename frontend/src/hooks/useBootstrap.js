import { useQuery } from "@tanstack/react-query";
import api from "../lib/api";

// Reference lists + per-resource permissions, fetched once and cached.
export function useBootstrap() {
  return useQuery({
    queryKey: ["bootstrap"],
    queryFn: async () => (await api.get("/meta/bootstrap")).data,
    staleTime: 5 * 60 * 1000,
  });
}
