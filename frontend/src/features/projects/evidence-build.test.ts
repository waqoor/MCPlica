import { describe, expect, it } from "vitest";
import type { Build } from "@/api/contracts";
import { selectEvidenceBuild } from "./evidence-build";

function build(
  id: string,
  sequence: number,
  canonicalSnapshotId: string | null,
): Build {
  return {
    id,
    project_id: "10000000-0000-4000-8000-000000000001",
    sequence,
    status: canonicalSnapshotId ? "READY" : "PARSING",
    pipeline_stage: canonicalSnapshotId ? "READY" : "PARSING",
    trigger: "manual_rebuild",
    executable_configuration_sha256: "a".repeat(64),
    canonical_snapshot_id: canonicalSnapshotId,
    previous_build_id: null,
    compiler_version: "1.0.0",
    manifest_schema_version: "mcp-manifest/v1",
    runtime_compatibility: ">=1,<2",
    analysis_model: null,
    validation_model: null,
    embedding_model: null,
    embedding_dimensions: null,
    prompt_bundle_version: null,
    manifest_sha256: null,
    artifact_sha256: null,
    error_code: null,
    error_summary: null,
    cancellation_requested_at: null,
    cancellation_requested_by: null,
    cancellation_acknowledged_at: null,
    admission_acquired_at: null,
    admission_enqueued_at: null,
    admission_heartbeat_at: null,
    admission_lease_expires_at: null,
    admission_released_at: null,
    admission_attempt_count: 0,
    created_at: "2026-08-27T10:00:00Z",
    started_at: null,
    completed_at: null,
  };
}

const latestInProgress = build("build-3", 3, null);
const activeServed = build("build-1", 1, "snapshot-1");
const latestInspectable = build("build-2", 2, "snapshot-2");
const builds = [latestInProgress, latestInspectable, activeServed];

describe("evidence build selection", () => {
  it("honors an inspectable URL selection", () => {
    expect(selectEvidenceBuild(builds, "build-2", "build-1")?.id).toBe(
      "build-2",
    );
  });

  it("defaults to the active served build ahead of a newer snapshot", () => {
    expect(selectEvidenceBuild(builds, null, "build-1")?.id).toBe("build-1");
  });

  it("falls back to the latest inspectable snapshot", () => {
    expect(selectEvidenceBuild(builds, "build-3", null)?.id).toBe("build-2");
  });

  it("does not select a queued or early failed build without a snapshot", () => {
    expect(selectEvidenceBuild([latestInProgress], null, null)).toBeUndefined();
  });
});
