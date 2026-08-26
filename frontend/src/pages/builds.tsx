import { useQuery } from "@tanstack/react-query";
import { Hammer } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { buildApi } from "@/api/builds";
import { PageHeader } from "@/components/page-header";
import { QueryError, QueryPending } from "@/components/query-state";
import { BuildStatusBadge } from "@/components/status-badge";
import { EmptyState } from "@/components/ui/empty-state";
import { Select } from "@/components/ui/select";
import { formatDate, titleCase } from "@/lib/format";

export function BuildsPage() {
  const [status, setStatus] = useState("");
  const builds = useQuery({
    queryKey: ["builds", "global", { status }],
    queryFn: ({ signal }) =>
      buildApi.listAll({ status: status || undefined, page_size: 100 }, signal),
    refetchInterval: 5_000,
  });
  return (
    <div className="space-y-7">
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
          onChange={(event) => setStatus(event.target.value)}
          value={status}
        >
          <option value="">All statuses</option>
          {[
            "QUEUED",
            "INGESTING",
            "PARSING",
            "INDEXING",
            "ANALYZING",
            "COMPILING",
            "VALIDATING",
            "PACKAGING",
            "READY",
            "FAILED",
            "CANCELLED",
          ].map((value) => (
            <option key={value}>{titleCase(value)}</option>
          ))}
        </Select>
      </div>
      {builds.isPending && <QueryPending label="Loading builds" />}
      {builds.error && (
        <QueryError
          error={builds.error}
          onRetry={() => void builds.refetch()}
        />
      )}
      {builds.data && builds.data.length === 0 && (
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
      {builds.data?.length ? (
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full min-w-[52rem] text-left">
            <thead className="bg-panel-raised font-mono text-[0.64rem] uppercase tracking-[0.1em] text-muted">
              <tr>
                <th className="px-4 py-3">Project</th>
                <th className="px-4 py-3">Build</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Trigger</th>
                <th className="px-4 py-3">Created</th>
                <th className="px-4 py-3">
                  <span className="sr-only">Open</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border bg-panel">
              {builds.data.map((build) => (
                <tr className="hover:bg-panel-hover/50" key={build.id}>
                  <td className="px-4 py-4 text-sm font-medium text-foreground">
                    {build.project_name ?? build.project_id.slice(0, 8)}
                  </td>
                  <td className="px-4 py-4 text-sm text-foreground">
                    #{build.sequence}
                  </td>
                  <td className="px-4 py-4">
                    <BuildStatusBadge status={build.status} />
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
    </div>
  );
}
