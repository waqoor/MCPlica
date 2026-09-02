import { expect, test } from "vitest";
import { operationalSettingsSchema } from "./settings-form";

const valid = {
  builders_can_deploy: false,
  mcp_base_domain: "mcp.example.com",
  build_concurrency: 4,
  source_retention_days: null,
  build_retention_count: null,
  max_upload_bytes: 10_000,
  max_operations_per_project: 1_000,
  max_document_chunks_per_project: 1_000,
  environment: "production" as const,
};

test("accepts nullable retention and exact operational bounds", () => {
  expect(operationalSettingsSchema.safeParse(valid).success).toBe(true);
  expect(
    operationalSettingsSchema.safeParse({
      ...valid,
      build_concurrency: 32,
      source_retention_days: 3_650,
      build_retention_count: 10_000,
      max_upload_bytes: 100_000_000,
      max_operations_per_project: 100_000,
      max_document_chunks_per_project: 100_000,
    }).success,
  ).toBe(true);
});

test.each([
  ["build_concurrency", 0],
  ["build_concurrency", 33],
  ["source_retention_days", 3_651],
  ["build_retention_count", 10_001],
  ["max_upload_bytes", 1_023],
  ["max_upload_bytes", 100_000_001],
  ["max_operations_per_project", 100_001],
  ["max_document_chunks_per_project", 100_001],
])("rejects %s outside the backend-owned bound", (field, value) => {
  expect(
    operationalSettingsSchema.safeParse({ ...valid, [field]: value }).success,
  ).toBe(false);
});
