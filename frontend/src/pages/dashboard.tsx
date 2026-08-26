import { useQueries, useQuery } from "@tanstack/react-query";
import {
  Activity,
  ArrowRight,
  Boxes,
  CircleAlert,
  Hammer,
  Plus,
  Rocket,
  ServerCog,
} from "lucide-react";
import { Link } from "react-router-dom";
import { buildApi } from "@/api/builds";
import { projectApi } from "@/api/projects";
import { systemApi } from "@/api/system";
import { PageHeader } from "@/components/page-header";
import { BuildStatusBadge, HealthBadge } from "@/components/status-badge";
import { Alert } from "@/components/ui/alert";
import { buttonVariants } from "@/components/ui/button-variants";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { formatDate } from "@/lib/format";
import { buildIsActive } from "@/lib/lifecycle";

function MetricCard({
  label,
  value,
  detail,
  icon: Icon,
}: {
  label: string;
  value: string | number;
  detail: string;
  icon: typeof Boxes;
}) {
  return (
    <Card className="relative overflow-hidden">
      <div
        aria-hidden="true"
        className="absolute inset-y-0 left-0 w-0.5 bg-accent/70"
      />
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-mono text-[0.66rem] font-semibold uppercase tracking-[0.12em] text-muted">
            {label}
          </p>
          <p className="mt-3 text-3xl font-semibold tracking-tight text-foreground">
            {value}
          </p>
          <p className="mt-1 text-xs text-muted">{detail}</p>
        </div>
        <span className="grid size-10 place-items-center rounded-lg border border-border bg-panel-raised text-accent">
          <Icon aria-hidden="true" className="size-4" />
        </span>
      </div>
    </Card>
  );
}

export function DashboardPage() {
  const projects = useQuery({
    queryKey: ["projects"],
    queryFn: ({ signal }) => projectApi.list(signal),
  });
  const [builds, readiness] = useQueries({
    queries: [
      {
        queryKey: ["builds", "global", { page_size: 8 }],
        queryFn: ({ signal }: { signal: AbortSignal }) =>
          buildApi.listAll({ page_size: 8 }, signal),
      },
      {
        queryKey: ["system", "readiness"],
        queryFn: ({ signal }: { signal: AbortSignal }) =>
          systemApi.readiness(signal),
        refetchInterval: 60_000,
      },
    ],
  });

  const activeBuilds =
    builds.data?.filter((build) => buildIsActive(build.status)).length ?? 0;
  const failedBuilds =
    builds.data?.filter((build) => build.status === "FAILED").length ?? 0;
  const activeDeployments =
    projects.data?.filter((project) => project.active_deployment_id).length ??
    0;

  return (
    <div className="space-y-7">
      <PageHeader
        actions={
          <Link className={buttonVariants()} to="/projects/new">
            <Plus aria-hidden="true" className="size-4" />
            New project
          </Link>
        }
        description="Build, validate, and operate isolated MCP runtimes from deterministic API contracts."
        eyebrow="Control plane"
        title="Operational overview"
      />

      <section
        aria-label="Workspace metrics"
        className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"
      >
        <MetricCard
          detail="in this installation"
          icon={Boxes}
          label="Projects"
          value={projects.data?.length ?? "—"}
        />
        <MetricCard
          detail={`${failedBuilds} recent failures`}
          icon={Hammer}
          label="Builds active"
          value={builds.isError ? "—" : activeBuilds}
        />
        <MetricCard
          detail="active project references"
          icon={Rocket}
          label="Deployments"
          value={projects.isError ? "—" : activeDeployments}
        />
        <MetricCard
          detail="builder dependencies"
          icon={ServerCog}
          label="System"
          value={readiness.data?.status ?? "Checking"}
        />
      </section>

      {(builds.isError || projects.isError) && (
        <Alert
          title="Some operational summaries are unavailable"
          tone="warning"
        >
          Detailed pages can still be used. Refresh after the backend finishes
          its current operation.
        </Alert>
      )}

      <div className="grid gap-5 xl:grid-cols-[1.15fr_0.85fr]">
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Recent builds</CardTitle>
              <p className="mt-1 text-xs text-muted">
                Immutable compilation attempts across projects
              </p>
            </div>
            <Link
              className="text-sm font-medium text-accent hover:text-accent-strong"
              to="/builds"
            >
              View all
            </Link>
          </CardHeader>
          {builds.data?.length ? (
            <div className="divide-y divide-border">
              {builds.data.slice(0, 6).map((build) => (
                <Link
                  className="flex min-h-16 items-center gap-4 py-3 transition hover:bg-panel-hover/50"
                  key={build.id}
                  to={`/projects/${build.project_id}/builds/${build.id}`}
                >
                  <span className="grid size-9 shrink-0 place-items-center rounded-md border border-border bg-input font-mono text-xs text-muted">
                    #{build.sequence}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-foreground">
                      {build.project_name ?? "Project build"}
                    </span>
                    <span className="block text-xs text-muted">
                      {formatDate(build.created_at)}
                    </span>
                  </span>
                  <BuildStatusBadge status={build.status} />
                </Link>
              ))}
            </div>
          ) : (
            <EmptyState
              action={
                <Link
                  className={buttonVariants({ variant: "outline" })}
                  to="/projects"
                >
                  Choose a project
                </Link>
              }
              description="Attach an executable source, then start the first deterministic build."
              icon={Hammer}
              title="No builds yet"
            />
          )}
        </Card>

        <div className="space-y-5">
          <Card>
            <CardHeader>
              <div>
                <CardTitle>System readiness</CardTitle>
                <p className="mt-1 text-xs text-muted">
                  Serving runtimes stay independent of build-time AI and vector
                  services.
                </p>
              </div>
              <HealthBadge status={readiness.data?.status} />
            </CardHeader>
            <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
              {readiness.data?.checks.map((check) => (
                <div
                  className="flex items-center justify-between rounded-md border border-border bg-input px-3 py-2"
                  key={check.name}
                >
                  <span className="text-sm capitalize text-muted">
                    {check.name}
                  </span>
                  <HealthBadge status={check.status} />
                </div>
              )) ?? (
                <p className="text-sm text-muted">Checking dependencies…</p>
              )}
            </div>
          </Card>

          <Card>
            <CardHeader>
              <div>
                <CardTitle>Deployment workspace</CardTitle>
                <p className="mt-1 text-xs text-muted">
                  Open a project to inspect health and lifecycle history
                </p>
              </div>
              <Link
                aria-label="View deployments"
                className="text-accent"
                to="/deployments"
              >
                <ArrowRight aria-hidden="true" className="size-4" />
              </Link>
            </CardHeader>
            {projects.data?.length ? (
              <div className="space-y-3">
                {projects.data.slice(0, 4).map((project) => (
                  <Link
                    className="flex items-center justify-between gap-3"
                    key={project.id}
                    to={`/projects/${project.id}/deployment`}
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm text-foreground">
                        {project.name}
                      </p>
                      <p className="truncate font-mono text-[0.68rem] text-muted">
                        {project.mcp_hostname}
                      </p>
                    </div>
                    <span className="font-mono text-[0.65rem] uppercase tracking-[0.08em] text-accent">
                      {project.active_deployment_id ? "Active" : "Configure"}
                    </span>
                  </Link>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted">No deployment history yet.</p>
            )}
          </Card>
        </div>
      </div>

      {projects.data?.length === 0 && (
        <EmptyState
          action={
            <Link className={buttonVariants()} to="/projects/new">
              Create the first project
              <ArrowRight aria-hidden="true" className="size-4" />
            </Link>
          }
          description="Start with an OpenAPI 3.x specification or API Inventory v1 file. Documentation is optional and cannot create executable operations."
          icon={Activity}
          title="The workspace is ready for its first API"
        />
      )}

      {failedBuilds > 0 && (
        <Alert title="Review required" tone="danger">
          <span className="inline-flex items-center gap-2">
            <CircleAlert aria-hidden="true" className="size-4" />
            {failedBuilds} failed build(s) are visible in the detailed views.
          </span>
        </Alert>
      )}
    </div>
  );
}
