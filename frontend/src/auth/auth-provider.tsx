import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useMemo, type ReactNode } from "react";
import { authApi } from "@/api/auth";
import { AuthContext, type AuthContextValue } from "./auth-context";

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const currentUser = useQuery({
    queryKey: ["auth", "me"],
    queryFn: ({ signal }) => authApi.me(signal),
    retry: false,
    staleTime: 60_000,
  });
  const loginMutation = useMutation({
    mutationFn: authApi.login,
    onSuccess: (user) => queryClient.setQueryData(["auth", "me"], user),
  });
  const logoutMutation = useMutation({
    mutationFn: authApi.logout,
    onSettled: () => {
      queryClient.setQueryData(["auth", "me"], null);
      queryClient.removeQueries({
        predicate: (query) => query.queryKey[0] !== "auth",
      });
    },
  });

  const refresh = useCallback(async () => {
    await currentUser.refetch();
  }, [currentUser]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user: currentUser.data ?? null,
      isLoading: currentUser.isPending,
      error: currentUser.error,
      login: loginMutation.mutateAsync,
      logout: logoutMutation.mutateAsync,
      refresh,
    }),
    [
      currentUser.data,
      currentUser.error,
      currentUser.isPending,
      loginMutation.mutateAsync,
      logoutMutation.mutateAsync,
      refresh,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
