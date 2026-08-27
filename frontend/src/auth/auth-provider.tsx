import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, type ReactNode } from "react";
import { authApi } from "@/api/auth";
import { setSessionRecoveryListener } from "@/api/client";
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
    onSuccess: () => {
      queryClient.setQueryData(["auth", "me"], null);
      queryClient.removeQueries({
        predicate: (query) => query.queryKey[0] !== "auth",
      });
    },
  });

  useEffect(
    () =>
      setSessionRecoveryListener((state) => {
        if (state === "refreshed") {
          void queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
          return;
        }
        queryClient.setQueryData(["auth", "me"], null);
        void queryClient.cancelQueries({
          predicate: (query) => query.queryKey[0] !== "auth",
        });
      }),
    [queryClient],
  );

  const refresh = useCallback(async () => {
    const response = await authApi.refresh();
    queryClient.setQueryData(["auth", "me"], response.user);
    await queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
  }, [queryClient]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user: currentUser.data ?? null,
      isLoading: currentUser.isPending,
      error: currentUser.error,
      login: loginMutation.mutateAsync,
      logout: logoutMutation.mutateAsync,
      logoutError: logoutMutation.error,
      isLoggingOut: logoutMutation.isPending,
      refresh,
    }),
    [
      currentUser.data,
      currentUser.error,
      currentUser.isPending,
      loginMutation.mutateAsync,
      logoutMutation.mutateAsync,
      logoutMutation.error,
      logoutMutation.isPending,
      refresh,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
