import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { flushSync } from "react-dom";
import {
  Link,
  MemoryRouter,
  Route,
  Routes,
  parsePath,
  useLocation,
} from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { User } from "@/api/contracts";
import { AuthContext } from "@/auth/auth-context";
import { ProtectedRoute } from "@/auth/protected-route";
import { LoginPage } from "./login";

const account: User = {
  id: "00000000-0000-4000-8000-000000000001",
  email: "test@example.test",
  display_name: "Test account",
  role: "admin",
  is_active: true,
  created_at: null,
  updated_at: null,
  last_login_at: null,
};

function LocationProbe() {
  const location = useLocation();
  return (
    <output data-testid="location">
      {location.pathname + location.search + location.hash}
    </output>
  );
}

function setup({
  entry = "/login",
  state,
  authenticated = false,
  role = "admin",
  failFirst = false,
}: {
  entry?: string;
  state?: unknown;
  authenticated?: boolean;
  role?: User["role"];
  failFirst?: boolean;
} = {}) {
  let attempts = 0;
  function Harness() {
    const [user, setUser] = useState<User | null>(
      authenticated ? { ...account, role } : null,
    );
    return (
      <AuthContext.Provider
        value={{
          user,
          isLoading: false,
          error: null,
          login: async () => {
            if (failFirst && attempts++ === 0) throw new Error("Try again");
            const result = { ...account, role };
            // AuthProvider updates the auth query before mutateAsync resolves.
            // Force that ordering so competing redirect paths cannot hide a race.
            flushSync(() => setUser(result));
            await new Promise((resolve) => setTimeout(resolve, 0));
            return result;
          },
          logout: async () => setUser(null),
          logoutError: null,
          isLoggingOut: false,
          refresh: vi.fn(),
        }}
      >
        <MemoryRouter initialEntries={[{ ...parsePath(entry), state }]}>
          <LocationProbe />
          <Link to="/login">Direct login</Link>
          <button onClick={() => setUser(null)}>Log out</button>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route element={<ProtectedRoute />}>
              <Route path="*" element={<p>Protected content</p>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </AuthContext.Provider>
    );
  }
  render(<Harness />);
}

async function signIn() {
  await userEvent.type(
    await screen.findByLabelText("Email"),
    "test@example.test",
  );
  await userEvent.type(screen.getByLabelText("Password"), "test-only-password");
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
}

async function expectLocation(path: string) {
  await waitFor(() =>
    expect(screen.getByTestId("location")).toHaveTextContent(path),
  );
  expect(screen.getByTestId("location").textContent).toBe(path);
}

describe.each(["admin", "builder"] as const)("%s login navigation", (role) => {
  it.each([
    "/projects",
    "/projects?phase2=deep-link",
    "/projects?phase2=deep-link#project-list",
  ])(
    "restores %s when auth state updates before login resolves",
    async (entry) => {
      setup({ entry, role });
      await expectLocation("/login");
      await signIn();
      await expectLocation(entry);
    },
  );
});

it("defaults to Dashboard for direct login", async () => {
  setup();
  await signIn();
  await expectLocation("/");
});

it("keeps the default redirect for an already-authenticated direct visit", async () => {
  setup({ authenticated: true });
  await expectLocation("/");
});

it("honors a valid destination when authentication is already available", async () => {
  setup({ authenticated: true, state: { from: "/projects?tab=all#list" } });
  await expectLocation("/projects?tab=all#list");
});

it.each([
  "https://example.test/",
  "//example.test/",
  "/\\example.test/",
  "javascript:alert(1)",
  "projects",
  "/\n/example.test/",
  42,
  {},
  "/login",
])("rejects unsafe or invalid destinations: %j", async (from) => {
  setup({ authenticated: true, state: { from } });
  await expectLocation("/");
});

it("preserves the destination after a failed login and retry", async () => {
  setup({ entry: "/projects?phase2=deep-link#project-list", failFirst: true });
  await signIn();
  expect(await screen.findByText("Sign-in failed")).toBeInTheDocument();
  await expectLocation("/login");
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
  await expectLocation("/projects?phase2=deep-link#project-list");
});

it("does not reuse a previous destination in an unrelated direct login after logout", async () => {
  setup({ entry: "/projects?phase2=deep-link#project-list" });
  await signIn();
  await expectLocation("/projects?phase2=deep-link#project-list");
  await userEvent.click(screen.getByRole("button", { name: "Log out" }));
  await expectLocation("/login");
  await userEvent.click(screen.getByRole("link", { name: "Direct login" }));
  await signIn();
  await expectLocation("/");
});
