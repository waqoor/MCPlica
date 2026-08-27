import { useQuery } from "@tanstack/react-query";
import { Hammer } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { buildApi, parseBuildStatusFilter } from "@/api/builds";
import { BUILD_STATUSES } from "@/api/generated/constants";
import { projectApi } from "@/api/projects";
import { PageHeader } from "@/components/page-header";
import { QueryError, QueryPending } from "@/components/query-state";
import { BuildStatusBadge } from "@/components/status-badge";
import { EmptyState } from "@/components/ui/empty-state";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { formatDate, titleCase } from "@/lib/format";
import { buildAdmissionLabel } from "@/lib/build-admission";

export function BuildsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const status = parseBuildStatusFilter(searchParams.get("status")) ?? "";
  const rawPage = Number(searchParams.get("page") ?? "1");
  const page = Number.isInteger(rawPage) && rawPage > 0 ? rawPage : 1;
  const builds = useQuery({
    queryKey: ["builds", "global", { status, page }],
    queryFn: ({ signal }) =>
      buildApi.listAllPage(
        { status: status || undefined, page, page_size: 50 },
        signal,
      ),
    refetchInterval: (query) => (query.state.data?.has_active ? 5_000 : false),
  });
  const projects = useQuery({
    queryKey: ["projects"],
    queryFn: ({ signal }) => projectApi.list(signal),
  });
  const admission = useQuery({
    queryKey: ["build-admission"],
    queryFn: ({ signal }) => buildApi.admission(signal),
    refetchInterval: (query) =>
      query.state.data?.waiting_count ? 2_000 : false,
  });
  const projectNames = new Map(
    projects.data?.map((project) => [project.id, project.name]),
  );
  return (
    <div className="min-w-0 space-y-7">
      <PageHeader
        description="Installation-wide immutable build history. Filter here, then inspect exact evidence within its project."
        eyebrow="Operations"
        title="Builds"
      />
      <div className="max-w-xs">
        <label className="sr-only" htmlFor="global-build-status">
          Filter build status
        </label>
        <Select
          id="global-build-status"
          onChange={(event) =>
            setSearchParams((current) => {
              const next = new URLSearchParams(current);
              if (event.target.value) next.set("status", event.target.value);
              else next.delete("status");
              next.delete("page");
              return next;
            })
          }
          value={status}
        >
          <option value="">All statuses</option>
          {BUILD_STATUSES.map((value) => (
            <option key={value} value={value}>
              {titleCase(value)}
            </option>
          ))}
        </Select>
      </div>
      {(builds.isPending || projects.isPending) && (
        <QueryPending label="Loading builds" />
      )}
      {builds.error && (
        <QueryError
          error={builds.error}
          onRetry={() => void builds.refetch()}
        />
      )}
      {projects.error && (
        <QueryError
          error={projects.error}
          onRetry={() => void projects.refetch()}
        />
      )}
      {admission.error && (
        <QueryError
          error={admission.error}
          onRetry={() => void admission.refetch()}
        />
      )}
      {builds.data && builds.data.items.length === 0 && (
        <EmptyState
          description={
            status
              ? "No builds match this status."
              : "Create a project and attach an executable source to begin."
          }
          icon={Hammer}
          title="No builds found"
        />
      )}
      {builds.data?.items.length && projects.data ? (
        <div className="max-w-full overflow-x-auto rounded-xl border border-border">
          <table className="w-full min-w-[52rem] text-left">
            <thead className="bg-panel-raised font-mono text-[0.64rem] uppercase tracking-[0.1em] text-muted">
              <tr>
                <th className="px-4 py-3">Project</th>
                <th className="px-4 py-3">Build</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Admission</th>
                <th className="px-4 py-3">Trigger</th>
                <th className="px-4 py-3">Created</th>
                <th className="px-4 py-3">
                  <span className="sr-only">Open</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border bg-panel">
              {builds.data.items.map((build) => (
                <tr className="hover:bg-panel-hover/50" key={build.id}>
                  <td className="px-4 py-4 text-sm font-medium text-foreground">
                    {projectNames.get(build.project_id) ?? "Deleted project"}
                  </td>
                  <td className="px-4 py-4 text-sm text-foreground">
                    #{build.sequence}
                  </td>
                  <td className="px-4 py-4">
                    <BuildStatusBadge status={build.status} />
                  </td>
                  <td className="px-4 py-4 text-sm text-muted">
                    {buildAdmissionLabel(build, admission.data)}
                  </td>
                  <td className="px-4 py-4 text-sm text-muted">
                    {titleCase(build.trigger)}
                  </td>
                  <td className="px-4 py-4 text-sm text-muted">
                    {formatDate(build.created_at)}
                  </td>
                  <td className="px-4 py-4 text-right">
                    <Link
                      className="text-sm font-medium text-accent"
                      to={`/projects/${build.project_id}/builds/${build.id}`}
                    >
                      Inspect →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {builds.data && builds.data.total > builds.data.page_size && (
        <div className="flex items-center justify-between">
          <Button
            disabled={page === 1}
            onClick={() =>
              setSearchParams((current) => {
                const next = new URLSearchParams(current);
                next.set("page", String(page - 1));
                return next;
              })
            }
            variant="outline"
          >
            Previous
          </Button>
          <span className="text-xs text-muted">
            Page {builds.data.page} · {builds.data.total} builds
          </span>
          <Button
            disabled={page * builds.data.page_size >= builds.data.total}
            onClick={() =>
              setSearchParams((current) => {
                const next = new URLSearchParams(current);
                next.set("page", String(page + 1));
                return next;
              })
            }
            variant="outline"
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
