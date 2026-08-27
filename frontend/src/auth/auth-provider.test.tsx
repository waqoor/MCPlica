import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { AuthProvider } from "./auth-provider";
import { useAuth } from "./use-auth";

function Probe() {
  const { user, logout, logoutError } = useAuth();
  return (
    <div>
      <p>{user?.email ?? "signed-out"}</p>
      <p>{logoutError?.message ?? "no-logout-error"}</p>
      <button
        onClick={() => void logout().catch(() => undefined)}
        type="button"
      >
        Sign out
      </button>
    </div>
  );
}

afterEach(() => vi.restoreAllMocks());

test("keeps authenticated state and exposes a retryable error when logout fails", async () => {
  const fetchMock = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          id: "00000000-0000-0000-0000-000000000001",
          email: "admin@example.com",
          display_name: "Admin",
          role: "admin",
          is_active: true,
          created_at: null,
          updated_at: null,
          last_login_at: null,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    )
    .mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          error: {
            code: "LOGOUT_FAILED",
            message: "Logout is temporarily unavailable",
          },
        }),
        { status: 503, headers: { "Content-Type": "application/json" } },
      ),
    );
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <Probe />
      </AuthProvider>
    </QueryClientProvider>,
  );

  expect(await screen.findByText("admin@example.com")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Sign out" }));
  expect(
    await screen.findByText("Logout is temporarily unavailable"),
  ).toBeInTheDocument();
  expect(screen.getByText("admin@example.com")).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledTimes(2);
});
