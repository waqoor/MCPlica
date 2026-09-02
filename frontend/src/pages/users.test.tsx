import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";
import { ApiError } from "@/api/client";
import type { User } from "@/api/contracts";

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  update: vi.fn(),
  create: vi.fn(),
}));

vi.mock("@/api/settings", () => ({ userApi: mocks }));
vi.mock("@/auth/use-auth", () => ({
  useAuth: () => ({
    user: {
      id: "10000000-0000-4000-8000-000000000001",
      role: "admin",
    },
  }),
}));

import { UsersPage } from "./users";

const admin: User = {
  id: "10000000-0000-4000-8000-000000000001",
  email: "admin@example.test",
  display_name: "Installation admin",
  role: "admin",
  is_active: true,
  created_at: "2026-08-27T10:00:00Z",
  updated_at: "2026-08-27T10:00:00Z",
  last_login_at: "2026-08-27T10:00:00Z",
};

beforeEach(() => {
  mocks.list.mockReset().mockResolvedValue([admin]);
  mocks.update.mockReset();
  mocks.create.mockReset();
});

function renderPage(
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } }),
) {
  render(
    <MemoryRouter initialEntries={["/settings/users"]}>
      <QueryClientProvider client={client}>
        <UsersPage />
      </QueryClientProvider>
    </MemoryRouter>,
  );
  return client;
}

test("serializes a self-demotion, disables every row control, and refreshes auth", async () => {
  let resolveUpdate: ((value: User) => void) | undefined;
  const updated = { ...admin, role: "builder" as const };
  mocks.update.mockImplementation(
    () =>
      new Promise<User>((resolve) => {
        resolveUpdate = resolve;
      }),
  );
  const client = renderPage();
  const invalidate = vi.spyOn(client, "invalidateQueries");

  const role = await screen.findByLabelText("Role");
  await userEvent.selectOptions(role, "builder");
  expect(
    screen.getByText(/Your own session may end immediately/),
  ).toBeVisible();
  expect(
    screen.getByText(/last active administrator/, { exact: false }),
  ).toBeVisible();

  const confirm = screen.getByRole("button", {
    name: "Confirm and revoke sessions",
  });
  await userEvent.click(confirm);
  expect(mocks.update).toHaveBeenCalledTimes(1);
  expect(screen.getByLabelText("Role")).toBeDisabled();
  expect(screen.getByLabelText("Display name")).toBeDisabled();
  expect(screen.getByText("Disable access").closest("button")).toBeDisabled();
  expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();

  resolveUpdate?.(updated);
  await waitFor(() =>
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["auth", "me"] }),
  );
  expect(mocks.update).toHaveBeenCalledTimes(1);
});

test("keeps the authoritative role after a rejected last-admin mutation", async () => {
  mocks.update.mockRejectedValue(
    new ApiError(
      409,
      "The last active administrator cannot be disabled or demoted",
      "INVALID_STATE",
      {},
      "request-user-1",
    ),
  );
  renderPage();

  const role = await screen.findByLabelText("Role");
  await userEvent.selectOptions(role, "builder");
  await userEvent.click(
    screen.getByRole("button", { name: "Confirm and revoke sessions" }),
  );

  expect(await screen.findByText("INVALID_STATE")).toBeVisible();
  expect(screen.getByText("request-user-1")).toBeVisible();
  expect(role).toHaveValue("admin");
  expect(
    screen.getByRole("button", { name: "Confirm and revoke sessions" }),
  ).toBeEnabled();
});

test("submits the create-user dialog with Enter through its semantic form", async () => {
  mocks.create.mockResolvedValue({
    ...admin,
    id: "10000000-0000-4000-8000-000000000002",
    email: "builder@example.test",
    display_name: "Build Operator",
    role: "builder",
  });
  const user = userEvent.setup();
  renderPage();

  await user.click(await screen.findByRole("button", { name: "Create user" }));
  const dialog = screen.getByRole("dialog", {
    name: "Create installation user",
  });
  await user.type(
    within(dialog).getByLabelText("Display name"),
    "Build Operator",
  );
  await user.type(
    within(dialog).getByLabelText("Email"),
    "builder@example.test",
  );
  const password = within(dialog).getByLabelText("Temporary password");
  await user.type(password, "correct-horse-battery-staple");
  await user.type(password, "{Enter}");

  await waitFor(() => expect(mocks.create).toHaveBeenCalledTimes(1));
  expect(mocks.create).toHaveBeenCalledWith({
    display_name: "Build Operator",
    email: "builder@example.test",
    password: "correct-horse-battery-staple",
    role: "builder",
  });
});
