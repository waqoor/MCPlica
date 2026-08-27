import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";
import { ProjectBuildsPage } from "./project-builds";

const projectId = "10000000-0000-4000-8000-000000000001";
const mocks = vi.hoisted(() => ({
  listPage: vi.fn(),
  create: vi.fn(),
  review: vi.fn(),
  rebuild: vi.fn(),
}));

vi.mock("@/api/builds", () => ({ buildApi: mocks }));
vi.mock("@/features/projects/project-context", () => ({
  useProject: () => ({ id: projectId }),
}));

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/projects/${projectId}/builds`]}>
        <Routes>
          <Route
            element={<ProjectBuildsPage />}
            path="/projects/:projectId/builds"
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.listPage.mockResolvedValue({
    items: [],
    page: 1,
    page_size: 50,
    total: 0,
    has_active: false,
  });
});

test("serializes mutually exclusive build actions before the server responds", async () => {
  let resolve!: (value: object) => void;
  mocks.review.mockReturnValue(
    new Promise((next) => {
      resolve = next;
    }),
  );
  const user = userEvent.setup();
  renderPage();

  const review = await screen.findByRole("button", { name: "Review" });
  await user.click(review);
  await user.click(screen.getByRole("button", { name: "Rebuild" }));
  await user.click(screen.getByRole("button", { name: "New build" }));

  expect(mocks.review).toHaveBeenCalledTimes(1);
  expect(mocks.rebuild).not.toHaveBeenCalled();
  expect(mocks.create).not.toHaveBeenCalled();
  expect(screen.getByRole("button", { name: "Review" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Rebuild" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "New build" })).toBeDisabled();
  resolve({});
  await waitFor(() => expect(review).toBeEnabled());
});

test("uses server active-build capability to block every conflicting action", async () => {
  mocks.listPage.mockResolvedValueOnce({
    items: [],
    page: 1,
    page_size: 50,
    total: 0,
    has_active: true,
  });
  renderPage();

  expect(await screen.findByText(/already active/i)).toBeVisible();
  expect(screen.getByRole("button", { name: "Review" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Rebuild" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "New build" })).toBeDisabled();
  expect(
    screen.getByRole("button", { name: "Start first build" }),
  ).toBeDisabled();
});
