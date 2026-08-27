import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { AuthContext, type AuthContextValue } from "./auth-context";
import { ProtectedRoute } from "./protected-route";

function LoginLocation() {
  const location = useLocation();
  return <p>{String((location.state as { from?: string } | null)?.from)}</p>;
}

describe("ProtectedRoute", () => {
  it("preserves the full deep link when authentication is required", async () => {
    const auth: AuthContextValue = {
      user: null,
      isLoading: false,
      error: null,
      login: vi.fn(),
      logout: vi.fn(),
      logoutError: null,
      isLoggingOut: false,
      refresh: vi.fn(),
    };
    render(
      <AuthContext.Provider value={auth}>
        <MemoryRouter
          initialEntries={["/projects/project-1?tab=sources#latest-version"]}
        >
          <Routes>
            <Route element={<ProtectedRoute />}>
              <Route path="/projects/:projectId" element={<p>Protected</p>} />
            </Route>
            <Route path="/login" element={<LoginLocation />} />
          </Routes>
        </MemoryRouter>
      </AuthContext.Provider>,
    );

    expect(
      await screen.findByText("/projects/project-1?tab=sources#latest-version"),
    ).toBeInTheDocument();
  });
});
