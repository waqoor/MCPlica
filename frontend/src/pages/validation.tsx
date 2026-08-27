import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { buildApi } from "@/api/builds";
import { QueryError, QueryPending } from "@/components/query-state";
import { ValidationSummary } from "@/components/validation-summary";
import { buildOwnershipError } from "@/lib/build-ownership";

export function ValidationPage() {
  const { buildId, projectId } = useParams<{
    buildId: string;
    projectId: string;
  }>();
  const build = useQuery({
    queryKey: ["builds", buildId],
    queryFn: ({ signal }) => buildApi.get(buildId!, signal),
    enabled: Boolean(buildId),
  });
  const report = useQuery({
    queryKey: ["builds", buildId, "validation"],
    queryFn: ({ signal }) => buildApi.validation(buildId!, signal),
    enabled: build.data?.project_id === projectId,
  });
  if (build.isPending)
    return <QueryPending label="Verifying build ownership" />;
  if (build.error)
    return (
      <QueryError error={build.error} onRetry={() => void build.refetch()} />
    );
  const ownershipError = buildOwnershipError(build.data, projectId);
  if (ownershipError) return <QueryError error={ownershipError} />;
  if (report.isPending)
    return <QueryPending label="Loading validation report" />;
  if (report.error)
    return (
      <QueryError error={report.error} onRetry={() => void report.refetch()} />
    );
  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-xl font-semibold text-foreground">
          Validation report
        </h2>
        <p className="mt-1 text-sm text-muted">
          Deterministic failures remain blocking regardless of semantic review.
        </p>
      </div>
      <ValidationSummary report={report.data} />
    </div>
  );
}
