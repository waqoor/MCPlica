import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import type { BuildStatus } from "@/api/contracts";
import { BuildProgress } from "./build-progress";

test.each<BuildStatus>([
  "QUEUED",
  "INGESTING",
  "PARSING",
  "INDEXING",
  "ANALYZING",
  "COMPILING",
  "VALIDATING",
  "PACKAGING",
])("reports the authoritative failure stage %s", (stage) => {
  render(<BuildProgress pipelineStage={stage} status="FAILED" />);
  expect(
    screen.getByText(`Failed during ${stage.toLowerCase()}.`),
  ).toBeVisible();
});

test("does not invent a stage for a legacy terminal build", () => {
  render(<BuildProgress pipelineStage={null} status="CANCELLED" />);
  expect(
    screen.getByText(/exact terminal stage is unavailable/i),
  ).toBeVisible();
});
