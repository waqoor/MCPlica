import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";
import { ValidationPage } from "./validation";

const mocks = vi.hoisted(() => ({ get: vi.fn(), validation: vi.fn() }));
vi.mock("@/api/builds", () => ({ buildApi: mocks }));

beforeEach(() => {
  mocks.get.mockResolvedValue({ id: "build-1", project_id: "project-a" });
  mocks.validation.mockResolvedValue({});
});

test("does not request validation evidence for a cross-project nested route", async () => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/projects/project-b/validation/build-1"]}>
        <Routes>
          <Route
            element={<ValidationPage />}
            path="/projects/:projectId/validation/:buildId"
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );

  expect(await screen.findByText("BUILD_PROJECT_MISMATCH")).toBeInTheDocument();
  expect(mocks.validation).not.toHaveBeenCalled();
});
