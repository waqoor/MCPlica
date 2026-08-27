import type { ProjectJourney } from "@/api/contracts";
import { buildIsActive } from "@/lib/lifecycle";

export function canonicalWizardStep(
  requestedStep: number,
  hasExplicitStep: boolean,
  journey: ProjectJourney,
): number {
  return hasExplicitStep
    ? Math.min(requestedStep, journey.resume_step)
    : journey.resume_step;
}

export function shouldPollJourney(journey: ProjectJourney | undefined) {
  return Boolean(
    journey &&
    ((journey.build_status !== null && buildIsActive(journey.build_status)) ||
      journey.deployment_transition_in_progress),
  );
}

export function journeyMatchesRequestedBuild(
  journey: ProjectJourney | undefined,
  requestedBuildId: string | null,
): boolean {
  return Boolean(
    journey &&
    (journey.requested_build_id ?? null) === (requestedBuildId ?? null),
  );
}
