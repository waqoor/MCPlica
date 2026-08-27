import { z } from "zod";

export const OPERATIONAL_SETTING_BOUNDS = {
  build_concurrency: { min: 1, max: 32 },
  max_upload_bytes: { min: 1_024, max: 500_000_000 },
  max_operations_per_project: { min: 1, max: 100_000 },
  max_document_chunks_per_project: { min: 1, max: 100_000 },
  build_retention_count: { min: 1, max: 10_000 },
  source_retention_days: { min: 1, max: 3_650 },
} as const;

const boundedInteger = (bounds: { min: number; max: number }) =>
  z.number().int().min(bounds.min).max(bounds.max);

export const operationalSettingsSchema = z.object({
  builders_can_deploy: z.boolean(),
  mcp_base_domain: z
    .string()
    .trim()
    .min(1)
    .max(253)
    .regex(
      /^(?=.{1,253}$)(?!-)(?:[a-z\d](?:[a-z\d-]{0,61}[a-z\d])?\.)*[a-z\d](?:[a-z\d-]{0,61}[a-z\d])?$/i,
      "Enter a valid DNS hostname.",
    ),
  build_concurrency: boundedInteger(
    OPERATIONAL_SETTING_BOUNDS.build_concurrency,
  ),
  source_retention_days: boundedInteger(
    OPERATIONAL_SETTING_BOUNDS.source_retention_days,
  ).nullable(),
  build_retention_count: boundedInteger(
    OPERATIONAL_SETTING_BOUNDS.build_retention_count,
  ).nullable(),
  max_upload_bytes: boundedInteger(OPERATIONAL_SETTING_BOUNDS.max_upload_bytes),
  max_operations_per_project: boundedInteger(
    OPERATIONAL_SETTING_BOUNDS.max_operations_per_project,
  ),
  max_document_chunks_per_project: boundedInteger(
    OPERATIONAL_SETTING_BOUNDS.max_document_chunks_per_project,
  ),
  environment: z.enum(["development", "production", "test"]),
});
