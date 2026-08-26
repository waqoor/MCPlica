import { useQueries } from "@tanstack/react-query";
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
import { deploymentApi } from "@/api/deployments";
import { sourceApi } from "@/api/sources";
import {
  BuildStatusBadge,
  DeploymentStatusBadge,
} from "@/components/status-badge";
import { Alert } from "@/components/ui/alert";
import { buttonVariants } from "@/components/ui/button-variants";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { useProject } from "@/features/projects/project-context";
import { formatDate } from "@/lib/format";

export function ProjectOverviewPage() {
  const project = useProject();
  const [sources, builds, deployments, access] = useQueries({
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
        queryKey: ["projects", project.id, "mcp-access"],
        queryFn: ({ signal }: { signal: AbortSignal }) =>
          deploymentApi.access(project.id, signal),
      },
    ],
  });
  const latestBuild = builds.data?.[0];
  const latestDeployment = deployments.data?.[0];
  const executableSources =
    sources.data?.filter((source) => source.kind !== "documentation") ?? [];
  const setupStep =
    executableSources.length === 0
      ? 2
      : !project.default_base_url
        ? 4
        : !latestBuild
          ? 6
          : latestBuild.status !== "READY"
            ? 7
            : !access.data?.configured
              ? 9
              : !latestDeployment
                ? 10
                : null;

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
              to={`/projects/new?project=${project.id}&step=${setupStep}${latestBuild ? `&build=${latestBuild.id}` : ""}`}
            >
              Continue setup
              <ArrowRight aria-hidden="true" className="size-4" />
            </Link>
          </div>
        </Alert>
      )}

      <section
        aria-label="Project lifecycle"
        className="grid gap-4 md:grid-cols-2 xl:grid-cols-4"
      >
        <SummaryCard
          icon={FileCode2}
          label="Sources"
          value={`${executableSources.length} executable`}
          detail={`${sources.data?.filter((source) => source.kind === "documentation").length ?? 0} documentation`}
          to="sources"
        />
        <SummaryCard
          icon={Hammer}
          label="Latest build"
          value={latestBuild ? `Build #${latestBuild.sequence}` : "Not started"}
          detail={
            latestBuild ? (
              <BuildStatusBadge status={latestBuild.status} />
            ) : (
              "No artifact"
            )
          }
          to="builds"
        />
        <SummaryCard
          icon={ShieldCheck}
          label="Coverage"
          value={latestBuild?.status === "READY" ? "Validated" : "Not proven"}
          detail={latestBuild?.manifest_schema_version ?? "No READY build"}
          to={latestBuild ? `validation/${latestBuild.id}` : "builds"}
        />
        <SummaryCard
          icon={Rocket}
          label="Deployment"
          value={latestDeployment?.hostname ?? "Not deployed"}
          detail={
            latestDeployment ? (
              <DeploymentStatusBadge status={latestDeployment.status} />
            ) : (
              "No runtime"
            )
          }
          to="deployment"
        />
      </section>

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
          {sources.data?.length ? (
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
              <CardTitle>Endpoint and access</CardTitle>
              <p className="mt-1 text-xs text-muted">
                Inbound MCP access is independent from upstream API credentials.
              </p>
            </div>
            <KeyRound aria-hidden="true" className="size-5 text-warning" />
          </CardHeader>
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between gap-4 border-b border-border pb-3">
              <dt className="text-muted">Endpoint</dt>
              <dd className="max-w-[70%] break-all text-right font-mono text-xs text-foreground">
                {latestDeployment?.endpoint_url ??
                  (latestDeployment
                    ? `https://${latestDeployment.hostname}/mcp`
                    : "Not deployed")}
              </dd>
            </div>
            <div className="flex justify-between gap-4 border-b border-border pb-3">
              <dt className="text-muted">Auth mode</dt>
              <dd className="text-foreground">
                {access.data?.mode ?? "Not configured"}
              </dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-muted">Last project update</dt>
              <dd className="text-foreground">
                {formatDate(project.updated_at)}
              </dd>
            </div>
          </dl>
        </Card>
      </div>

      {[sources, builds, deployments, access].some(
        (query) => query.isError,
      ) && (
        <Alert tone="warning">
          Some project summaries are temporarily unavailable. Detailed tabs
          provide scoped retry controls.
        </Alert>
      )}
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
  to: string;
}) {
  return (
    <Link
      className="group rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
      to={to}
    >
      <Card className="h-full transition group-hover:border-border-strong group-hover:bg-panel-raised">
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
    </Link>
  );
}
