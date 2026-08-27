import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Ban,
  BrainCircuit,
  Download,
  FileDiff,
  FileJson2,
  ShieldCheck,
} from "lucide-react";
import type { BuildAIRun } from "@/api/contracts";
import { useState } from "react";
import { useParams } from "react-router-dom";
import { buildApi } from "@/api/builds";
import { BuildProgress } from "@/components/build-progress";
import { ErrorNotice, MutationError } from "@/components/error-notice";
import { JsonCode } from "@/components/json-code";
import { QueryError, QueryPending } from "@/components/query-state";
import { BuildStatusBadge } from "@/components/status-badge";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { ValidationSummary } from "@/components/validation-summary";
import { formatDate, titleCase } from "@/lib/format";
import { buildOwnershipError } from "@/lib/build-ownership";
import { buildCanCancel, buildIsActive } from "@/lib/lifecycle";

export function BuildDetailPage() {
  const { buildId, projectId } = useParams<{
    buildId: string;
    projectId: string;
  }>();
  const queryClient = useQueryClient();
  const [cancelOpen, setCancelOpen] = useState(false);
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
    enabled: Boolean(
      build.data &&
      build.data.project_id === projectId &&
      (build.data.status === "READY" || build.data.status === "FAILED"),
    ),
  });
  const diff = useQuery({
    queryKey: ["builds", buildId, "diff"],
    queryFn: ({ signal }) => buildApi.diff(buildId!, signal),
    enabled: Boolean(
      build.data &&
      build.data.project_id === projectId &&
      build.data.previous_build_id,
    ),
  });
  const manifest = useQuery({
    queryKey: ["builds", buildId, "manifest"],
    queryFn: ({ signal }) => buildApi.manifest(buildId!, signal),
    enabled: Boolean(
      build.data &&
      build.data.project_id === projectId &&
      build.data.manifest_sha256,
    ),
  });
  const aiRuns = useQuery({
    queryKey: ["builds", buildId, "ai-runs"],
    queryFn: ({ signal }) => buildApi.aiRuns(buildId!, signal),
    enabled: build.data?.project_id === projectId,
  });
  const cancel = useMutation({
    mutationFn: () => buildApi.cancel(buildId!),
    onSuccess: (value) => {
      setCancelOpen(false);
      queryClient.setQueryData(["builds", buildId], value);
    },
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
  const downloadManifest = useMutation({
    mutationFn: () => buildApi.downloadManifest(buildId!),
    onSuccess: (blob) => {
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `manifest-${buildId}.json`;
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
  const ownershipError = buildOwnershipError(item, projectId);
  if (ownershipError) return <QueryError error={ownershipError} />;
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
            disabled={
              !buildCanCancel(item.status) ||
              Boolean(item.cancellation_requested_at) ||
              cancel.isPending
            }
            onClick={() => setCancelOpen(true)}
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
      <Dialog
        description="Cancellation is cooperative. Queued work is removed when possible; running parsing, AI, embedding, and packaging work stops at the next durable checkpoint and records acknowledgement."
        onClose={() => setCancelOpen(false)}
        open={cancelOpen}
        title={`Cancel build #${item.sequence}?`}
      >
        <div className="flex justify-end gap-2">
          <Button onClick={() => setCancelOpen(false)} variant="outline">
            Keep build running
          </Button>
          <Button
            disabled={cancel.isPending}
            onClick={() => cancel.mutate()}
            variant="destructive"
          >
            Request cancellation
          </Button>
        </div>
      </Dialog>
      <Card>
        <BuildProgress
          pipelineStage={item.pipeline_stage}
          status={item.status}
        />
      </Card>
      {item.cancellation_requested_at && !item.cancellation_acknowledged_at && (
        <Alert title="Cancellation requested" tone="info">
          The request was recorded at{" "}
          {formatDate(item.cancellation_requested_at)}. The build remains{" "}
          {item.status.toLowerCase()} until its worker stops at a durable
          checkpoint and acknowledges cancellation.
        </Alert>
      )}
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
              label="Executable configuration SHA-256"
              value={item.executable_configuration_sha256}
              mono
            />
            <Fact label="Manifest SHA-256" value={item.manifest_sha256} mono />
            <Fact label="Artifact SHA-256" value={item.artifact_sha256} mono />
            <Fact
              label="Canonical snapshot"
              value={item.canonical_snapshot_id}
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
      {item.manifest_sha256 && (
        <section className="space-y-4">
          <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
            <div className="flex items-center gap-2">
              <FileJson2 aria-hidden="true" className="size-5 text-accent" />
              <div>
                <h3 className="text-lg font-semibold text-foreground">
                  Immutable MCP manifest
                </h3>
                <p className="text-sm text-muted">
                  Validated against the tracked manifest schema before display.
                </p>
              </div>
            </div>
            <Button
              disabled={downloadManifest.isPending}
              onClick={() => downloadManifest.mutate()}
              variant="outline"
            >
              <Download aria-hidden="true" className="size-4" />
              Download raw manifest
            </Button>
          </div>
          {manifest.data ? (
            <JsonCode
              label={`Build ${item.sequence} immutable manifest`}
              value={manifest.data}
            />
          ) : manifest.error ? (
            <ErrorNotice
              error={manifest.error}
              title="Manifest evidence is unavailable"
            />
          ) : (
            <QueryPending label="Loading immutable manifest" />
          )}
        </section>
      )}
      <section className="space-y-4">
        <div className="flex items-center gap-2">
          <BrainCircuit aria-hidden="true" className="size-5 text-info" />
          <div>
            <h3 className="text-lg font-semibold text-foreground">
              Build-time AI evidence
            </h3>
            <p className="text-sm text-muted">
              Provider metadata, prompt/context identity, usage, cost, and
              response hashes only; model chain-of-thought is never stored or
              exposed.
            </p>
          </div>
        </div>
        {aiRuns.data ? (
          aiRuns.data.length > 0 ? (
            <div className="space-y-4">
              {aiRuns.data.map((run) => (
                <AIRunEvidence key={run.id} run={run} />
              ))}
            </div>
          ) : (
            <Alert tone="info">
              No model runs were recorded for this immutable build.
            </Alert>
          )
        ) : aiRuns.error ? (
          <ErrorNotice
            error={aiRuns.error}
            title="AI-run evidence is unavailable"
          />
        ) : (
          <QueryPending label="Loading AI-run evidence" />
        )}
      </section>
      {validation.data && (
        <section>
          <h3 className="mb-4 text-lg font-semibold text-foreground">
            Validation evidence
          </h3>
          <ValidationSummary report={validation.data} />
        </section>
      )}
      {validation.error && (
        <ErrorNotice
          error={validation.error}
          title="Validation evidence is unavailable"
        />
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
            <ErrorNotice error={diff.error} title="Build diff is unavailable" />
          ) : (
            <p className="text-sm text-muted">Loading build diff…</p>
          )}
        </section>
      )}
      {(cancel.error || exportBuild.error || downloadManifest.error) && (
        <MutationError
          error={cancel.error ?? exportBuild.error ?? downloadManifest.error}
        />
      )}
    </div>
  );
}

function AIRunEvidence({ run }: { run: BuildAIRun }) {
  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>{run.run_key}</CardTitle>
          <p className="mt-1 text-xs text-muted">
            {run.stage}
            {run.operation_key ? ` · ${run.operation_key}` : " · build-wide"}
          </p>
        </div>
        <Badge tone={run.status === "succeeded" ? "success" : "warning"}>
          {run.status}
        </Badge>
      </CardHeader>
      <div className="grid gap-x-8 gap-y-3 text-sm lg:grid-cols-2">
        <Fact label="Provider" value={run.provider} />
        <Fact label="Model" value={run.model} />
        <Fact
          label="Prompt template"
          value={`${run.prompt_template_id}@${run.prompt_template_version}`}
          mono
        />
        <Fact label="Response schema" value={run.response_schema_id} mono />
        <Fact
          label="Input context SHA-256"
          value={run.input_context_sha256}
          mono
        />
        <Fact label="Response SHA-256" value={run.response_sha256} mono />
        <Fact
          label="Latency"
          value={run.latency_ms === null ? null : `${run.latency_ms} ms`}
        />
        <Fact label="Recorded" value={formatDate(run.created_at)} />
        <Fact label="Error code" value={run.error_code} mono />
      </div>
      <div className="mt-4 grid gap-4 border-t border-border pt-4 lg:grid-cols-3">
        <JsonCode
          label={`${run.run_key} retrieved chunk IDs`}
          value={run.retrieved_chunk_ids}
        />
        <JsonCode label={`${run.run_key} provider usage`} value={run.usage} />
        <JsonCode label={`${run.run_key} provider cost`} value={run.cost} />
      </div>
    </Card>
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
