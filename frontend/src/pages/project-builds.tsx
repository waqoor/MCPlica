import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, Hammer, Plus, RefreshCw } from "lucide-react";
import { useRef } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { buildApi } from "@/api/builds";
import { MutationError } from "@/components/error-notice";
import { QueryError, QueryPending } from "@/components/query-state";
import { BuildStatusBadge } from "@/components/status-badge";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { useProject } from "@/features/projects/project-context";
import { formatDate, shortenHash, titleCase } from "@/lib/format";

export function ProjectBuildsPage() {
  const project = useProject();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const rawPage = Number(searchParams.get("page") ?? "1");
  const page = Number.isInteger(rawPage) && rawPage > 0 ? rawPage : 1;
  const builds = useQuery({
    queryKey: ["projects", project.id, "builds", { page }],
    queryFn: ({ signal }) =>
      buildApi.listPage(project.id, { page, page_size: 50 }, signal),
    refetchInterval: (query) => (query.state.data?.has_active ? 5_000 : false),
  });
  const invalidate = () =>
    queryClient.invalidateQueries({
      queryKey: ["projects", project.id, "builds"],
    });
  const actionLock = useRef(false);
  const buildAction = useMutation({
    mutationFn: (action: "create" | "review" | "rebuild") =>
      action === "create"
        ? buildApi.create(project.id)
        : action === "review"
          ? buildApi.review(project.id)
          : buildApi.rebuild(project.id),
    onSuccess: invalidate,
    onSettled: () => {
      actionLock.current = false;
    },
  });
  const requestBuild = (action: "create" | "review" | "rebuild") => {
    if (actionLock.current || builds.data?.has_active) return;
    actionLock.current = true;
    buildAction.mutate(action);
  };
  if (builds.isPending) return <QueryPending label="Loading build history" />;
  if (builds.error)
    return (
      <QueryError error={builds.error} onRetry={() => void builds.refetch()} />
    );
  const error = buildAction.error;
  const actionPending = buildAction.isPending;
  const actionBlocked = builds.data.has_active || actionPending;
  return (
    <div className="min-w-0 space-y-5">
      <div className="flex flex-col justify-between gap-3 xl:flex-row xl:items-center">
        <div>
          <h2 className="text-xl font-semibold text-foreground">Builds</h2>
          <p className="mt-1 text-sm text-muted">
            Every request creates a new immutable build bound to exact source
            versions.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            disabled={actionBlocked}
            onClick={() => requestBuild("review")}
            variant="outline"
          >
            <Eye aria-hidden="true" className="size-4" />
            Review
          </Button>
          <Button
            disabled={actionBlocked}
            onClick={() => requestBuild("rebuild")}
            variant="outline"
          >
            <RefreshCw aria-hidden="true" className="size-4" />
            Rebuild
          </Button>
          <Button
            disabled={actionBlocked}
            onClick={() => requestBuild("create")}
          >
            <Plus aria-hidden="true" className="size-4" />
            New build
          </Button>
        </div>
      </div>
      {builds.data.has_active && (
        <Alert tone="info">
          A build is already active. Review, rebuild, and new-build requests are
          mutually exclusive until it reaches a terminal state.
        </Alert>
      )}
      {error && <MutationError error={error} />}
      {builds.data.items.length === 0 ? (
        <EmptyState
          action={
            <Button
              disabled={actionBlocked}
              onClick={() => requestBuild("create")}
            >
              Start first build
            </Button>
          }
          description="Attach an executable source and upstream server configuration before building."
          icon={Hammer}
          title="No builds yet"
        />
      ) : (
        <div className="max-w-full overflow-x-auto rounded-xl border border-border">
          <table className="w-full min-w-[48rem] border-collapse text-left">
            <thead className="bg-panel-raised font-mono text-[0.65rem] uppercase tracking-[0.1em] text-muted">
              <tr>
                <th className="px-4 py-3">Build</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Trigger</th>
                <th className="px-4 py-3">Manifest</th>
                <th className="px-4 py-3">Created</th>
                <th className="px-4 py-3">
                  <span className="sr-only">Open</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border bg-panel">
              {builds.data.items.map((build) => (
                <tr className="hover:bg-panel-hover/50" key={build.id}>
                  <td className="px-4 py-4 font-medium text-foreground">
                    #{build.sequence}
                  </td>
                  <td className="px-4 py-4">
                    <BuildStatusBadge status={build.status} />
                  </td>
                  <td className="px-4 py-4 text-sm text-muted">
                    {titleCase(build.trigger)}
                  </td>
                  <td className="px-4 py-4 font-mono text-xs text-muted">
                    {shortenHash(build.manifest_sha256)}
                  </td>
                  <td className="px-4 py-4 text-sm text-muted">
                    {formatDate(build.created_at)}
                  </td>
                  <td className="px-4 py-4 text-right">
                    <Link
                      className="text-sm font-medium text-accent hover:text-accent-strong"
                      to={`${build.id}`}
                    >
                      Inspect →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {builds.data.total > builds.data.page_size && (
        <div className="flex items-center justify-between">
          <Button
            disabled={page === 1}
            onClick={() => {
              const next = new URLSearchParams(searchParams);
              next.set("page", String(page - 1));
              setSearchParams(next);
            }}
            variant="outline"
          >
            Previous
          </Button>
          <span className="text-xs text-muted">
            Page {builds.data.page} · {builds.data.total} builds
          </span>
          <Button
            disabled={page * builds.data.page_size >= builds.data.total}
            onClick={() => {
              const next = new URLSearchParams(searchParams);
              next.set("page", String(page + 1));
              setSearchParams(next);
            }}
            variant="outline"
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
