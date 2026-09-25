import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";
import { NewProjectPage } from "./new-project";

const mocks = vi.hoisted(() => ({
  project: vi.fn(),
  journey: vi.fn(),
  build: vi.fn(),
  create: vi.fn(),
}));
vi.mock("@/api/projects", () => ({
  projectApi: { get: mocks.project, journey: mocks.journey },
}));
vi.mock("@/api/builds", () => ({
  buildApi: { get: mocks.build, create: mocks.create },
}));
vi.mock("@/auth/capabilities", () => ({ useCapabilities: () => ({}) }));

function journey(status: string, id = "build-1") {
  return {
    project_id: "project-1",
    requested_build_id: id,
    selected_build_id: id,
    build_status: status,
    resume_step: status === "FAILED" ? 6 : 7,
    steps: [],
    sources: [],
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.project.mockResolvedValue({ id: "project-1", name: "Test project" });
  mocks.journey.mockImplementation((_project, id) =>
    Promise.resolve(journey("INDEXING", id)),
  );
  mocks.build.mockImplementation((id) =>
    Promise.resolve({
      id,
      sequence: 1,
      status: "INDEXING",
      pipeline_stage: "INDEXING",
    }),
  );
  mocks.create.mockResolvedValue({ id: "build-2" });
});

function setup() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter
        initialEntries={[
          "/projects/new?step=7&project=project-1&build=build-1",
        ]}
      >
        <NewProjectPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return client;
}

test.each(["INDEXING", "ANALYZING"])(
  "keeps failure visible after async %s failure and allows retry",
  async (stage) => {
    const client = setup();
    await screen.findByText("Build #1");
    await act(async () => {
      client.setQueryData(["builds", "build-1"], {
        id: "build-1",
        sequence: 1,
        status: "FAILED",
        pipeline_stage: stage,
        error_summary: "DO_NOT_EXPOSE_PROVIDER_DETAIL",
      });
      client.setQueryData(
        ["projects", "project-1", "journey", "build-1"],
        journey("FAILED"),
      );
    });
    expect(
      await screen.findByRole("heading", { name: "Start build" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Build failed");
    expect(
      screen.getByRole("link", { name: "Inspect failed build" }),
    ).toHaveAttribute("href", "/projects/project-1/builds/build-1");
    expect(
      screen.queryByText("DO_NOT_EXPOSE_PROVIDER_DETAIL"),
    ).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Start build" }));
    expect(mocks.create).toHaveBeenCalledWith("project-1");
    await screen.findByText("Build #1");
    expect(screen.queryByText("Inspect failed build")).not.toBeInTheDocument();
  },
);

test("successful build still enables validation review", async () => {
  const client = setup();
  await screen.findByText("Build #1");
  await act(async () => {
    client.setQueryData(["builds", "build-1"], {
      id: "build-1",
      sequence: 1,
      status: "READY",
      pipeline_stage: "READY",
    });
    client.setQueryData(["projects", "project-1", "journey", "build-1"], {
      ...journey("READY"),
      resume_step: 8,
    });
  });
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Review validation" }),
    ).toBeEnabled(),
  );
  expect(screen.queryByText("Inspect failed build")).not.toBeInTheDocument();
});
