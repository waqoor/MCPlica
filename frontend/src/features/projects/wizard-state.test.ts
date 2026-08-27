import { describe, expect, it } from "vitest";
import type { ProjectJourney } from "@/api/contracts";
import {
  canonicalWizardStep,
  journeyMatchesRequestedBuild,
  shouldPollJourney,
} from "./wizard-state";

function journey(values: Partial<ProjectJourney> = {}): ProjectJourney {
  return {
    project_id: "project-1",
    requested_build_id: null,
    selected_build_id: null,
    active_build_id: null,
    active_deployment_id: null,
    resume_step: 6,
    steps: [],
    sources: [],
    source_version_ids: [],
    routing_complete: true,
    credential_mapping_required: false,
    credential_mapping_complete: true,
    bound_security_schemes: [],
    access_mode: null,
    access_configured: false,
    access_runtime_effect_state: "effective",
    access_remediation: null,
    build_status: null,
    build_stale: false,
    validation_status: null,
    validation_complete: false,
    active_deployment_status: null,
    deployment_transition_in_progress: false,
    preflight_ready: false,
    deployable: false,
    deployability_reason_code: null,
    deployability_remediation: null,
    can_manage_credentials: false,
    can_manage_mcp_access: false,
    can_deploy: false,
    ...values,
  };
}

describe("wizard server-state navigation", () => {
  it("rewinds a tampered deep link to the earliest incomplete step", () => {
    expect(canonicalWizardStep(10, true, journey({ resume_step: 4 }))).toBe(4);
  });

  it("allows reviewing an already completed earlier step", () => {
    expect(canonicalWizardStep(2, true, journey({ resume_step: 7 }))).toBe(2);
  });

  it("resumes at authoritative state when the URL has no step", () => {
    expect(canonicalWizardStep(1, false, journey({ resume_step: 8 }))).toBe(8);
  });

  it("polls only while build or deployment state can still advance", () => {
    expect(shouldPollJourney(journey({ build_status: "PARSING" }))).toBe(true);
    expect(
      shouldPollJourney(
        journey({
          build_status: "READY",
          deployment_transition_in_progress: true,
        }),
      ),
    ).toBe(true);
    expect(shouldPollJourney(journey({ build_status: "FAILED" }))).toBe(false);
    expect(shouldPollJourney(journey({ build_status: "READY" }))).toBe(false);
  });

  it("rejects a stale journey response for a different requested build", () => {
    expect(journeyMatchesRequestedBuild(journey(), null)).toBe(true);
    expect(journeyMatchesRequestedBuild(journey(), "build-new")).toBe(false);
    expect(
      journeyMatchesRequestedBuild(
        journey({ requested_build_id: "build-new" }),
        "build-new",
      ),
    ).toBe(true);
  });
});
