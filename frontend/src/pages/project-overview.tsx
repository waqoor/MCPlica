import { useQueries, useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  FileCode2,
  Hammer,
  KeyRound,
  Rocket,
  ShieldCheck,
} from "lucide-react";
import { Link } from "react-router-dom";
import { buildApi } from "@/api/builds";
import type { Deployment } from "@/api/contracts";
import { deploymentApi } from "@/api/deployments";
import { projectApi } from "@/api/projects";
import { sourceApi } from "@/api/sources";
import { QueryError, QueryPending } from "@/components/query-state";
import {
  BuildStatusBadge,
  DeploymentStatusBadge,
} from "@/components/status-badge";
import { Alert } from "@/components/ui/alert";
import { buttonVariants } from "@/components/ui/button-variants";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { useProject } from "@/features/projects/project-context";
import { formatDate } from "@/lib/format";
import { resolveDeploymentState } from "@/lib/deployment-state";

export function ProjectOverviewPage() {
  const project = useProject();
  const [sources, builds, deployments, journey, activeDeployment] = useQueries({
    queries: [
      {
        queryKey: ["projects", project.id, "sources"],
        queryFn: ({ signal }: { signal: AbortSignal }) =>
          sourceApi.list(project.id, signal),
      },
      {
        queryKey: ["projects", project.id, "builds"],
        queryFn: ({ signal }: { signal: AbortSignal }) =>
          buildApi.list(project.id, signal),
      },
      {
        queryKey: ["projects", project.id, "deployments"],
        queryFn: ({ signal }: { signal: AbortSignal }) =>
          deploymentApi.list(project.id, signal),
      },
      {
        queryKey: ["projects", project.id, "journey", null],
        queryFn: ({ signal }: { signal: AbortSignal }) =>
          projectApi.journey(project.id, null, signal),
      },
      {
        queryKey: ["deployments", project.active_deployment_id],
        queryFn: ({ signal }: { signal: AbortSignal }) =>
          deploymentApi.get(project.active_deployment_id!, signal),
        enabled: Boolean(project.active_deployment_id),
      },
    ],
  });
  const latestBuild = builds.data?.[0];
  const validation = useQuery({
    queryKey: ["builds", latestBuild?.id, "validation"],
    queryFn: ({ signal }) => buildApi.validation(latestBuild!.id, signal),
    enabled: builds.isSuccess && latestBuild?.status === "READY",
  });
  const deploymentBuildLabel = (buildId: string) => {
    const sequence = builds.data?.find(
      (build) => build.id === buildId,
    )?.sequence;
    return sequence === undefined ? "Build unavailable" : `Build #${sequence}`;
  };
  const { active, newestCandidate } = resolveDeploymentState<Deployment>(
    project.active_deployment_id,
    deployments.data,
    activeDeployment.data,
  );
  const executableSources = sources.data?.filter(
    (source) => source.kind !== "documentation",
  );
  const documentationSources = sources.data?.filter(
    (source) => source.kind === "documentation",
  );
  const setupStep = journey.data?.steps.find(
    (candidate) => candidate.state === "current",
  )?.number;
  const activeDeploymentPending = Boolean(
    project.active_deployment_id && activeDeployment.isPending,
  );
  const deploymentPending = deployments.isPending || activeDeploymentPending;
  const deploymentError = deployments.error ?? activeDeployment.error;
  const deploymentKnown =
    deployments.isSuccess &&
    (!project.active_deployment_id || activeDeployment.isSuccess);
  const coverageValue = builds.isPending
    ? "Loading…"
    : builds.isError
      ? "Unavailable"
      : !latestBuild || latestBuild.status !== "READY"
        ? "Not proven"
        : validation.isPending
          ? "Loading evidence…"
          : validation.isError
            ? "Unavailable"
            : `${validation.data.coverage_percent}% coverage`;
  const coverageDetail = builds.isError
    ? "Build state is not known"
    : !latestBuild
      ? "No build has been created"
      : latestBuild.status !== "READY"
        ? `Build #${latestBuild.sequence} is ${latestBuild.status.toLowerCase()}`
        : validation.isPending
          ? "Loading the authoritative validation report"
          : validation.isError
            ? "Validation evidence is not known"
            : `${validation.data.operation_generated_count}/${validation.data.operation_expected_count} operations · ${validation.data.blocking_error_count} blocking · ${validation.data.warning_count} warnings`;
  const coverageKnown =
    builds.isSuccess &&
    (!latestBuild || latestBuild.status !== "READY" || validation.isSuccess);

  return (
    <div className="space-y-6">
      {setupStep && (
        <Alert title="Project setup is incomplete" tone="warning">
          <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
            <span>
              Continue the guided workflow from the first incomplete durable
              step.
            </span>
            <Link
              className={buttonVariants({ variant: "outline", size: "sm" })}
              to={`/projects/new?project=${project.id}&step=${setupStep}${journey.data?.selected_build_id ? `&build=${journey.data.selected_build_id}` : ""}`}
            >
              Continue setup
              <ArrowRight aria-hidden="true" className="size-4" />
            </Link>
          </div>
        </Alert>
      )}
      {journey.data?.build_stale && (
        <Alert
          title="Current source or routing requires a rebuild"
          tone="warning"
        >
          The selected immutable build has a different executable-configuration
          fingerprint. It remains available for audit and any already-running
          deployment, but new activation is blocked until a new build validates
          the current source versions, base URL, server selection, and operation
          routing.
        </Alert>
      )}

      <section
        aria-label="Project lifecycle"
        className="grid gap-4 md:grid-cols-2 xl:grid-cols-4"
      >
        <SummaryCard
          icon={FileCode2}
          label="Sources"
          value={
            sources.isPending
              ? "Loading…"
              : sources.isError
                ? "Unavailable"
                : `${executableSources?.length ?? 0} executable`
          }
          detail={
            sources.isSuccess
              ? `${documentationSources?.length ?? 0} documentation`
              : "Source state is not yet known"
          }
          to={sources.isSuccess ? "sources" : undefined}
        />
        <SummaryCard
          icon={Hammer}
          label="Latest build"
          value={
            builds.isPending
              ? "Loading…"
              : builds.isError
                ? "Unavailable"
                : latestBuild
                  ? `Build #${latestBuild.sequence}`
                  : "Not started"
          }
          detail={
            builds.isError ? (
              "Build state is not known"
            ) : latestBuild ? (
              <BuildStatusBadge status={latestBuild.status} />
            ) : (
              "No artifact"
            )
          }
          to={builds.isSuccess ? "builds" : undefined}
        />
        <SummaryCard
          icon={ShieldCheck}
          label="Coverage"
          value={coverageValue}
          detail={coverageDetail}
          to={
            coverageKnown
              ? latestBuild
                ? `validation/${latestBuild.id}`
                : "builds"
              : undefined
          }
        />
        <SummaryCard
          icon={Rocket}
          label="Deployment"
          value={
            deploymentPending
              ? "Loading…"
              : deploymentError
                ? "Unavailable"
                : (active?.hostname ?? "Not deployed")
          }
          detail={
            deploymentError ? (
              "Runtime state is not known"
            ) : active ? (
              <DeploymentStatusBadge status={active.status} />
            ) : (
              "No runtime"
            )
          }
          to={deploymentKnown ? "deployment" : undefined}
        />
      </section>
      {newestCandidate && (
        <Alert title="Newest deployment is not the active runtime" tone="info">
          Candidate {deploymentBuildLabel(newestCandidate.build_id)} is{" "}
          {newestCandidate.status.toLowerCase()}. The active endpoint below
          remains bound to the deployment selected by the project record.
        </Alert>
      )}

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Source truth</CardTitle>
              <p className="mt-1 text-xs text-muted">
                Executable input and enrichment stay visibly separate.
              </p>
            </div>
            <FileCode2 aria-hidden="true" className="size-5 text-info" />
          </CardHeader>
          {sources.isPending ? (
            <QueryPending label="Loading source truth" />
          ) : sources.error ? (
            <QueryError
              error={sources.error}
              onRetry={() => void sources.refetch()}
              title="Source truth could not be loaded"
            />
          ) : sources.data?.length ? (
            <div className="space-y-3">
              {sources.data.slice(0, 5).map((source) => (
                <div
                  className="flex items-center justify-between gap-3 rounded-md border border-border bg-input px-3 py-3"
                  key={source.id}
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-foreground">
                      {source.name}
                    </p>
                    <p className="mt-0.5 font-mono text-[0.68rem] uppercase text-muted">
                      {source.kind} · {source.origin_type}
                    </p>
                  </div>
                  <span className="text-xs text-muted">
                    {source.latest_version?.parse_status ?? "registered"}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted">No sources are attached.</p>
          )}
        </Card>

        <Card>
          <CardHeader>
            <div>
              <CardTitle>Validation evidence</CardTitle>
              <p className="mt-1 text-xs text-muted">
                Coverage comes from the immutable report for the latest build.
              </p>
            </div>
            <ShieldCheck aria-hidden="true" className="size-5 text-success" />
          </CardHeader>
          {builds.isPending ? (
            <QueryPending label="Loading latest build identity" />
          ) : builds.error ? (
            <QueryError
              error={builds.error}
              onRetry={() => void builds.refetch()}
              title="Build evidence could not be loaded"
            />
          ) : !latestBuild ? (
            <p className="text-sm text-muted">
              No build exists, so there is no validation report.
            </p>
          ) : latestBuild.status !== "READY" ? (
            <div className="space-y-3">
              <BuildStatusBadge status={latestBuild.status} />
              <p className="text-sm text-muted">
                Build #{latestBuild.sequence} has no authoritative READY
                validation evidence.
              </p>
            </div>
          ) : validation.isPending ? (
            <QueryPending label="Loading validation evidence" />
          ) : validation.error ? (
            <QueryError
              error={validation.error}
              onRetry={() => void validation.refetch()}
              title="Validation evidence could not be loaded"
            />
          ) : (
            <div className="grid gap-3 text-sm sm:grid-cols-2">
              <EvidenceFact
                label="Coverage"
                value={`${validation.data.coverage_percent}%`}
              />
              <EvidenceFact
                label="Generated operations"
                value={`${validation.data.operation_generated_count} of ${validation.data.operation_expected_count}`}
              />
              <EvidenceFact
                label="Blocking findings"
                value={String(validation.data.blocking_error_count)}
              />
              <EvidenceFact
                label="Warnings"
                value={String(validation.data.warning_count)}
              />
            </div>
          )}
        </Card>

        <Card>
          <CardHeader>
            <div>
              <CardTitle>Endpoint and access</CardTitle>
              <p className="mt-1 text-xs text-muted">
                Inbound MCP access is independent from upstream API credentials.
              </p>
            </div>
            <KeyRound aria-hidden="true" className="size-5 text-warning" />
          </CardHeader>
          <div className="space-y-5">
            <section aria-label="Endpoint state">
              {deploymentPending ? (
                <QueryPending label="Loading endpoint state" />
              ) : deploymentError ? (
                <QueryError
                  error={deploymentError}
                  onRetry={() => {
                    void deployments.refetch();
                    if (project.active_deployment_id)
                      void activeDeployment.refetch();
                  }}
                  title="Endpoint state could not be loaded"
                />
              ) : (
                <EvidenceFact
                  label="Endpoint"
                  mono
                  value={
                    active?.endpoint_url ??
                    (active ? `https://${active.hostname}/mcp` : "Not deployed")
                  }
                />
              )}
            </section>
            <section
              aria-label="Inbound access state"
              className="border-t border-border pt-5"
            >
              {journey.isPending ? (
                <QueryPending label="Loading inbound access state" />
              ) : journey.error ? (
                <QueryError
                  error={journey.error}
                  onRetry={() => void journey.refetch()}
                  title="Inbound access state could not be loaded"
                />
              ) : (
                <EvidenceFact
                  label="Auth mode"
                  value={journey.data.access_mode ?? "Not configured"}
                />
              )}
            </section>
            <div className="border-t border-border pt-5">
              <EvidenceFact
                label="Last project update"
                value={formatDate(project.updated_at)}
              />
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}

function SummaryCard({
  icon: Icon,
  label,
  value,
  detail,
  to,
}: {
  icon: typeof FileCode2;
  label: string;
  value: string;
  detail: React.ReactNode;
  to?: string;
}) {
  const content = (
    <Card
      className={
        to
          ? "h-full transition group-hover:border-border-strong group-hover:bg-panel-raised"
          : "h-full"
      }
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-mono text-[0.65rem] uppercase tracking-[0.11em] text-muted">
            {label}
          </p>
          <p className="mt-3 truncate text-lg font-semibold text-foreground">
            {value}
          </p>
          <div className="mt-2 text-xs text-muted">{detail}</div>
        </div>
        <Icon aria-hidden="true" className="size-4 shrink-0 text-accent" />
      </div>
    </Card>
  );
  if (!to) return content;
  return (
    <Link
      className="group rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
      to={to}
    >
      {content}
    </Link>
  );
}

function EvidenceFact({
  label,
  value,
  mono = false,
}: {
  readonly label: string;
  readonly value: string;
  readonly mono?: boolean;
}) {
  return (
    <div className="flex justify-between gap-4">
      <span className="text-muted">{label}</span>
      <span
        className={
          mono
            ? "max-w-[70%] break-all text-right font-mono text-xs text-foreground"
            : "text-right text-foreground"
        }
      >
        {value}
      </span>
    </div>
  );
}
