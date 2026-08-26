import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Ban, Download, FileDiff, ShieldCheck } from "lucide-react";
import { useParams } from "react-router-dom";
import { buildApi } from "@/api/builds";
import { BuildProgress } from "@/components/build-progress";
import { JsonCode } from "@/components/json-code";
import { QueryError, QueryPending } from "@/components/query-state";
import { BuildStatusBadge } from "@/components/status-badge";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { ValidationSummary } from "@/components/validation-summary";
import { formatDate, shortenHash, titleCase } from "@/lib/format";
import { buildCanCancel, buildIsActive } from "@/lib/lifecycle";

export function BuildDetailPage() {
  const { buildId } = useParams<{ buildId: string }>();
  const queryClient = useQueryClient();
  const build = useQuery({
    queryKey: ["builds", buildId],
    queryFn: ({ signal }) => buildApi.get(buildId!, signal),
    enabled: Boolean(buildId),
    refetchInterval: (query) =>
      query.state.data && buildIsActive(query.state.data.status)
        ? 2_000
        : false,
  });
  const validation = useQuery({
    queryKey: ["builds", buildId, "validation"],
    queryFn: ({ signal }) => buildApi.validation(buildId!, signal),
    enabled: build.data?.status === "READY" || build.data?.status === "FAILED",
  });
  const diff = useQuery({
    queryKey: ["builds", buildId, "diff"],
    queryFn: ({ signal }) => buildApi.diff(buildId!, signal),
    enabled: Boolean(build.data?.previous_build_id),
  });
  const cancel = useMutation({
    mutationFn: () => buildApi.cancel(buildId!),
    onSuccess: (value) => queryClient.setQueryData(["builds", buildId], value),
  });
  const exportBuild = useMutation({
    mutationFn: () => buildApi.export(buildId!),
    onSuccess: (blob) => {
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `mcplica-build-${build.data?.sequence ?? buildId}.zip`;
      anchor.click();
      URL.revokeObjectURL(url);
    },
  });
  if (build.isPending) return <QueryPending label="Loading build" />;
  if (build.error)
    return (
      <QueryError error={build.error} onRetry={() => void build.refetch()} />
    );
  const item = build.data;
  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="text-xl font-semibold text-foreground">
              Build #{item.sequence}
            </h2>
            <BuildStatusBadge status={item.status} />
          </div>
          <p className="mt-2 text-sm text-muted">
            {titleCase(item.trigger)} · created {formatDate(item.created_at)}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            disabled={!buildCanCancel(item.status) || cancel.isPending}
            onClick={() => cancel.mutate()}
            variant="outline"
          >
            <Ban aria-hidden="true" className="size-4" />
            Cancel
          </Button>
          <Button
            disabled={item.status !== "READY" || exportBuild.isPending}
            onClick={() => exportBuild.mutate()}
          >
            <Download aria-hidden="true" className="size-4" />
            Export bundle
          </Button>
        </div>
      </div>
      <Card>
        <BuildProgress status={item.status} />
      </Card>
      {item.error_summary && (
        <Alert title={item.error_code ?? "Build failed"} tone="danger">
          {item.error_summary}
        </Alert>
      )}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Reproducibility</CardTitle>
            <ShieldCheck aria-hidden="true" className="size-5 text-accent" />
          </CardHeader>
          <dl className="space-y-3 text-sm">
            <Fact label="Compiler" value={item.compiler_version} />
            <Fact
              label="Manifest schema"
              value={item.manifest_schema_version}
            />
            <Fact
              label="Runtime compatibility"
              value={item.runtime_compatibility}
            />
            <Fact label="Prompt bundle" value={item.prompt_bundle_version} />
            <Fact
              label="Manifest SHA-256"
              value={shortenHash(item.manifest_sha256)}
              mono
            />
          </dl>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Build-time intelligence</CardTitle>
            <span className="font-mono text-xs text-muted">
              No chain-of-thought
            </span>
          </CardHeader>
          <dl className="space-y-3 text-sm">
            <Fact label="Analysis model" value={item.analysis_model} />
            <Fact label="Validation model" value={item.validation_model} />
            <Fact label="Embedding model" value={item.embedding_model} />
            <Fact
              label="Embedding dimensions"
              value={item.embedding_dimensions?.toString()}
            />
          </dl>
        </Card>
      </div>
      {validation.data && (
        <section>
          <h3 className="mb-4 text-lg font-semibold text-foreground">
            Validation evidence
          </h3>
          <ValidationSummary report={validation.data} />
        </section>
      )}
      {validation.error && (
        <Alert tone="warning">
          Validation report unavailable: {validation.error.message}
        </Alert>
      )}
      {item.previous_build_id && (
        <section>
          <div className="mb-4 flex items-center gap-2">
            <FileDiff aria-hidden="true" className="size-5 text-info" />
            <h3 className="text-lg font-semibold text-foreground">
              Change set
            </h3>
          </div>
          {diff.data ? (
            <JsonCode label="Build diff" value={diff.data} />
          ) : diff.error ? (
            <Alert tone="warning">Diff unavailable: {diff.error.message}</Alert>
          ) : (
            <p className="text-sm text-muted">Loading build diff…</p>
          )}
        </section>
      )}
      {(cancel.error || exportBuild.error) && (
        <Alert tone="danger">
          {cancel.error?.message ?? exportBuild.error?.message}
        </Alert>
      )}
    </div>
  );
}

function Fact({
  label,
  value,
  mono = false,
}: {
  label: string;
  value?: string | null;
  mono?: boolean;
}) {
  return (
    <div className="flex justify-between gap-4 border-b border-border pb-3 last:border-0 last:pb-0">
      <dt className="text-muted">{label}</dt>
      <dd
        className={
          mono
            ? "max-w-[65%] break-all text-right font-mono text-xs text-foreground"
            : "max-w-[65%] text-right text-foreground"
        }
      >
        {value ?? "Not recorded"}
      </dd>
    </div>
  );
}
