import { describe, expect, it } from "vitest";
import type { Operation, OperationExclusion } from "@/api/contracts";
import { operationPolicyState } from "./operation-policy";

const operation = {
  key: "GET /pets",
  source_operation_id: "listPets",
  method: "GET",
  path_template: "/pets",
  tool_name: "list_pets",
  title: "List pets",
  source_summary: "List pets",
  source_description: null,
  enriched_description: null,
  input_schema: null,
  auth_mapping: [],
  provenance: [],
  semantic_warnings: [],
  confidence: null,
  excluded_in_build: false,
  build_exclusion_id: null,
  build_exclusion_reason: null,
  current_exclusion_id: null,
  current_exclusion_reason: null,
} satisfies Operation;

const currentExclusion = {
  id: "10000000-0000-4000-8000-000000000001",
  project_id: "20000000-0000-4000-8000-000000000001",
  build_id: "30000000-0000-4000-8000-000000000001",
  operation_key: operation.key,
  reason_code: "user_requested",
  reason: "Unsafe upstream operation",
  is_user_requested: true,
  created_by: "40000000-0000-4000-8000-000000000001",
  created_at: "2026-08-27T10:00:00Z",
} satisfies OperationExclusion;

describe("operation exclusion policy state", () => {
  it("keeps the immutable build state distinct after a new exclusion", () => {
    expect(operationPolicyState(operation, currentExclusion)).toEqual({
      excludedInBuild: false,
      currentlyExcluded: true,
      changedSinceBuild: true,
    });
  });

  it("keeps the immutable build state distinct after a policy restoration", () => {
    expect(
      operationPolicyState(
        {
          ...operation,
          excluded_in_build: true,
          build_exclusion_id: currentExclusion.id,
          build_exclusion_reason: currentExclusion.reason,
        },
        undefined,
      ),
    ).toEqual({
      excludedInBuild: true,
      currentlyExcluded: false,
      changedSinceBuild: true,
    });
  });

  it("reports unchanged included and excluded policies", () => {
    expect(operationPolicyState(operation, undefined).changedSinceBuild).toBe(
      false,
    );
    expect(
      operationPolicyState(
        { ...operation, excluded_in_build: true },
        currentExclusion,
      ).changedSinceBuild,
    ).toBe(false);
  });
});
