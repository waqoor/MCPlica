import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { buildApi } from "@/api/builds";
import { QueryError, QueryPending } from "@/components/query-state";
import { ValidationSummary } from "@/components/validation-summary";

export function ValidationPage() {
  const { buildId } = useParams<{ buildId: string }>();
  const report = useQuery({
    queryKey: ["builds", buildId, "validation"],
    queryFn: ({ signal }) => buildApi.validation(buildId!, signal),
    enabled: Boolean(buildId),
  });
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
