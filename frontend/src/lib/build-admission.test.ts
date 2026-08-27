import { describe, expect, it } from "vitest";
import type { Build, BuildAdmissionOverview } from "@/api/contracts";
import { buildAdmissionLabel } from "./build-admission";

const overview = {
  configured_concurrency: 2,
  effective_concurrency: 2,
  waiting_count: 1,
  entries: [
    {
      build_id: "00000000-0000-0000-0000-000000000001",
      project_id: "00000000-0000-0000-0000-000000000010",
      status: "QUEUED",
      state: "waiting",
      position: 3,
      admitted_at: null,
      lease_expires_at: null,
    },
    {
      build_id: "00000000-0000-0000-0000-000000000002",
      project_id: "00000000-0000-0000-0000-000000000011",
      status: "ANALYZING",
      state: "running",
      position: null,
      admitted_at: "2026-08-27T12:00:00Z",
      lease_expires_at: "2026-08-27T12:05:00Z",
    },
  ],
} satisfies BuildAdmissionOverview;

describe("buildAdmissionLabel", () => {
  it("uses authoritative queue position and active permit state", () => {
    expect(
      buildAdmissionLabel(
        { id: overview.entries[0].build_id, status: "QUEUED" } as Build,
        overview,
      ),
    ).toBe("Queue #3");
    expect(
      buildAdmissionLabel(
        { id: overview.entries[1].build_id, status: "ANALYZING" } as Build,
        overview,
      ),
    ).toBe("Permit active");
  });

  it("does not imply a permit for missing or terminal entries", () => {
    expect(
      buildAdmissionLabel(
        { id: "missing", status: "QUEUED" } as Build,
        overview,
      ),
    ).toBe("Awaiting admission");
    expect(
      buildAdmissionLabel({ id: "done", status: "READY" } as Build, overview),
    ).toBe("Released");
  });
});
