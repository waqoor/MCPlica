import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import type { SourceVersion } from "@/api/contracts";

const mocks = vi.hoisted(() => ({
  versionsPage: vi.fn(),
  versionMetadata: vi.fn(),
}));

vi.mock("@/api/sources", () => ({
  sourceApi: mocks,
}));

import { SourceVersionHistory } from "./source-version-history";

const projectId = "10000000-0000-4000-8000-000000000001";
const sourceId = "20000000-0000-4000-8000-000000000001";

function version(id: string, hashCharacter: string): SourceVersion {
  return {
    id,
    source_id: sourceId,
    content_sha256: hashCharacter.repeat(64),
    media_type: "application/json",
    byte_size: 512,
    detected_format: "openapi-3.1-json",
    source_etag: `"${hashCharacter}"`,
    source_last_modified: "Wed, 26 Aug 2026 10:00:00 GMT",
    created_by: "30000000-0000-4000-8000-000000000001",
    created_at: "2026-08-26T10:00:00Z",
    deduplicated: false,
  };
}

const healthy = version("40000000-0000-4000-8000-000000000001", "a");
const damaged = version("50000000-0000-4000-8000-000000000001", "b");

beforeEach(() => {
  mocks.versionsPage.mockReset().mockResolvedValue({
    items: [healthy, damaged],
    total: 12,
    page: 1,
    page_size: 10,
  });
  mocks.versionMetadata.mockReset().mockImplementation((versionId: string) => {
    if (versionId === damaged.id)
      return Promise.reject(
        new Error("This version's evidence is unavailable"),
      );
    return Promise.resolve({
      ...healthy,
      parse_status: "valid",
      spec_version: "3.1.0",
      operation_count: 8,
      servers: ["https://api.example.test"],
      auth_schemes: [],
      errors: [],
      preview_markdown: null,
      indexed_chunk_count: null,
      embedding_model: null,
      embedding_dimensions: null,
      index_status: null,
      metadata_build_id: "60000000-0000-4000-8000-000000000001",
      index_generation_id: null,
    });
  });
});

test("loads one bounded history page and isolates per-version evidence failures", async () => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <SourceVersionHistory
        projectId={projectId}
        sourceId={sourceId}
        versionCount={12}
      />
    </QueryClientProvider>,
  );

  await userEvent.click(
    screen.getByText("Version history (12)", { selector: "summary" }),
  );
  expect(await screen.findByText(`SHA-256 ${"a".repeat(64)}`)).toBeVisible();
  expect(screen.getByText(`SHA-256 ${"b".repeat(64)}`)).toBeVisible();
  expect(mocks.versionsPage).toHaveBeenCalledWith(
    projectId,
    sourceId,
    { page: 1, page_size: 10 },
    expect.any(AbortSignal),
  );

  const evidenceToggles = screen.getAllByText(
    /Inspect parse and index evidence/,
  );
  await userEvent.click(evidenceToggles[0]);
  await userEvent.click(evidenceToggles[1]);

  expect(await screen.findByText("Parse valid")).toBeVisible();
  expect(
    await screen.findByText("This version's evidence is unavailable"),
  ).toBeVisible();
  expect(screen.getByText(`SHA-256 ${"a".repeat(64)}`)).toBeVisible();
  expect(screen.getByText(`SHA-256 ${"b".repeat(64)}`)).toBeVisible();
  expect(screen.getByRole("button", { name: "Next versions" })).toBeEnabled();
});
