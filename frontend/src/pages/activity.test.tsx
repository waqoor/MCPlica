import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";
import { auditCalendarRange } from "@/lib/audit-date-range";

const mocks = vi.hoisted(() => ({
  auditList: vi.fn(),
  projectList: vi.fn(),
  userList: vi.fn(),
}));

vi.mock("@/api/audit", () => ({ auditApi: { list: mocks.auditList } }));
vi.mock("@/api/projects", () => ({
  projectApi: { list: mocks.projectList },
}));
vi.mock("@/api/settings", () => ({ userApi: { list: mocks.userList } }));

import { ActivityPage } from "./activity";

beforeEach(() => {
  mocks.auditList.mockReset().mockResolvedValue({
    items: [],
    total: 0,
    page: 1,
    page_size: 50,
  });
  mocks.projectList.mockReset().mockResolvedValue([]);
  mocks.userList.mockReset().mockResolvedValue([]);
});

function renderActivity(entry: string) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const router = createMemoryRouter(
    [{ path: "/activity", element: <ActivityPage /> }],
    { initialEntries: [entry] },
  );
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

test("rejects an impossible URL date without issuing an unfiltered audit request", async () => {
  renderActivity("/activity?from_date=2026-02-29");

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "No unfiltered request was sent",
  );
  expect(mocks.auditList).not.toHaveBeenCalled();
});

test("accepts a valid leap day and sends its inclusive calendar boundaries", async () => {
  renderActivity("/activity?from_date=2024-02-29&to_date=2024-02-29");

  await waitFor(() => expect(mocks.auditList).toHaveBeenCalledTimes(1));
  expect(mocks.auditList).toHaveBeenCalledWith(
    expect.objectContaining({
      ...auditCalendarRange("2024-02-29", "2024-02-29"),
      page: 1,
      page_size: 50,
    }),
    expect.any(AbortSignal),
  );
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});
