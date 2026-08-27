import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  createMemoryRouter,
  RouterProvider,
  useNavigate,
} from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";
import type { Project } from "@/api/contracts";
import { ProjectsPage } from "./projects";

const mocks = vi.hoisted(() => ({ list: vi.fn() }));

vi.mock("@/api/projects", () => ({ projectApi: mocks }));

const project = (id: string, name: string): Project => ({
  id,
  name,
  slug: name.toLowerCase(),
  description: null,
  is_enabled: true,
  created_by: "20000000-0000-4000-8000-000000000001",
  mcp_hostname: `${name.toLowerCase()}.mcp.example.test`,
  default_base_url: "https://api.example.test",
  active_server_ref: null,
  server_mappings: {},
  active_build_id: null,
  active_deployment_id: null,
  created_at: "2026-08-27T10:00:00Z",
  updated_at: "2026-08-27T10:00:00Z",
  runtime_effect_state: "effective",
  runtime_command_id: null,
  runtime_error_code: null,
});

function HistoryHarness() {
  const navigate = useNavigate();
  return (
    <>
      <button onClick={() => void navigate(-1)} type="button">
        Back
      </button>
      <button onClick={() => void navigate(1)} type="button">
        Forward
      </button>
      <ProjectsPage />
    </>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.list.mockResolvedValue([
    project("10000000-0000-4000-8000-000000000001", "Alpha"),
    project("10000000-0000-4000-8000-000000000002", "Beta"),
  ]);
});

test("restores the project filter across browser back and forward history", async () => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const router = createMemoryRouter(
    [{ path: "/projects", element: <HistoryHarness /> }],
    {
      initialEntries: ["/projects?search=Alpha", "/projects?search=Beta"],
      initialIndex: 1,
    },
  );
  const user = userEvent.setup();
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );

  expect(await screen.findByLabelText("Search projects")).toHaveValue("Beta");
  expect(await screen.findByText("Beta")).toBeVisible();
  expect(screen.queryByText("Alpha")).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Back" }));
  expect(await screen.findByLabelText("Search projects")).toHaveValue("Alpha");
  expect(await screen.findByText("Alpha")).toBeVisible();
  expect(screen.queryByText("Beta")).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Forward" }));
  expect(await screen.findByLabelText("Search projects")).toHaveValue("Beta");
});
