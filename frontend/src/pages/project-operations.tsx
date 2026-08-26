import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Braces, Filter, Search, ShieldAlert } from "lucide-react";
import { useDeferredValue, useMemo, useState } from "react";
import type { Operation } from "@/api/contracts";
import { buildApi } from "@/api/builds";
import { JsonCode } from "@/components/json-code";
import { QueryError, QueryPending } from "@/components/query-state";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { FieldHelp, Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useProject } from "@/features/projects/project-context";

const methodTone: Record<
  string,
  "info" | "success" | "warning" | "danger" | "neutral"
> = {
  GET: "info",
  POST: "success",
  PUT: "warning",
  PATCH: "warning",
  DELETE: "danger",
};

export function ProjectOperationsPage() {
  const project = useProject();
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search.toLowerCase());
  const [method, setMethod] = useState("");
  const [scope, setScope] = useState("all");
  const builds = useQuery({
    queryKey: ["projects", project.id, "builds"],
    queryFn: ({ signal }) => buildApi.list(project.id, signal),
  });
  const latest = builds.data?.[0];
  const operations = useQuery({
    queryKey: ["builds", latest?.id, "operations"],
    queryFn: ({ signal }) => buildApi.operations(latest!.id, signal),
    enabled: Boolean(latest),
  });
  const filtered = useMemo(
    () =>
      operations.data?.filter((operation) => {
        const matchesSearch =
          !deferredSearch ||
          `${operation.key} ${operation.source_operation_id ?? ""} ${operation.method} ${operation.path_template} ${operation.tool_name ?? ""} ${operation.source_summary ?? ""}`
            .toLowerCase()
            .includes(deferredSearch);
        return (
          matchesSearch &&
          (!method || operation.method === method) &&
          (scope === "all" || (scope === "excluded") === operation.excluded)
        );
      }) ?? [],
    [deferredSearch, method, operations.data, scope],
  );

  if (builds.isPending)
    return <QueryPending label="Finding the latest build" />;
  if (builds.error)
    return (
      <QueryError error={builds.error} onRetry={() => void builds.refetch()} />
    );
  if (!latest)
    return (
      <EmptyState
        description="Start a build after attaching an executable source. Operations remain source-derived and are not inferred from documentation."
        icon={Braces}
        title="No operation snapshot yet"
      />
    );
  if (operations.isPending)
    return <QueryPending label="Loading operation mappings" />;
  if (operations.error)
    return (
      <QueryError
        error={operations.error}
        onRetry={() => void operations.refetch()}
      />
    );

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-xl font-semibold text-foreground">
          Operations and tools
        </h2>
        <p className="mt-1 text-sm text-muted">
          Build #{latest.sequence} · source structure, generated semantics, and
          provenance remain distinguishable.
        </p>
      </div>
      <div className="grid gap-3 md:grid-cols-[minmax(14rem,1fr)_10rem_11rem]">
        <div className="relative">
          <Label className="sr-only" htmlFor="operation-search">
            Search operations
          </Label>
          <Search
            aria-hidden="true"
            className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted"
          />
          <Input
            className="pl-10"
            id="operation-search"
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search operation, path, or tool"
            type="search"
            value={search}
          />
        </div>
        <div>
          <Label className="sr-only" htmlFor="method-filter">
            Method
          </Label>
          <Select
            id="method-filter"
            onChange={(event) => setMethod(event.target.value)}
            value={method}
          >
            <option value="">All methods</option>
            {["GET", "POST", "PUT", "PATCH", "DELETE"].map((value) => (
              <option key={value}>{value}</option>
            ))}
          </Select>
        </div>
        <div>
          <Label className="sr-only" htmlFor="scope-filter">
            Exclusion status
          </Label>
          <Select
            id="scope-filter"
            onChange={(event) => setScope(event.target.value)}
            value={scope}
          >
            <option value="all">All operations</option>
            <option value="included">Included only</option>
            <option value="excluded">Excluded only</option>
          </Select>
        </div>
      </div>
      <p aria-live="polite" className="text-xs text-muted">
        Showing {filtered.length} of {operations.data.length} operations
      </p>
      {!filtered.length ? (
        <EmptyState
          description="Change the search or filters to inspect other operations."
          icon={Filter}
          title="No matching operations"
        />
      ) : (
        <div className="space-y-3">
          {filtered.map((operation) => (
            <OperationCard
              buildId={latest.id}
              key={operation.key}
              operation={operation}
              projectId={project.id}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function OperationCard({
  operation,
  projectId,
  buildId,
}: {
  operation: Operation;
  projectId: string;
  buildId: string;
}) {
  const queryClient = useQueryClient();
  const [excludeOpen, setExcludeOpen] = useState(false);
  const [reason, setReason] = useState("");
  const exclude = useMutation({
    mutationFn: () =>
      buildApi.excludeOperation(projectId, operation.key, reason),
    onSuccess: () => {
      setExcludeOpen(false);
      void queryClient.invalidateQueries({
        queryKey: ["builds", buildId, "operations"],
      });
    },
  });
  const include = useMutation({
    mutationFn: () =>
      buildApi.removeExclusion(projectId, operation.exclusion_id!),
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: ["builds", buildId, "operations"],
      }),
  });
  return (
    <Card className={operation.excluded ? "border-warning/35" : undefined}>
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={methodTone[operation.method] ?? "neutral"}>
              {operation.method}
            </Badge>
            <code className="break-all font-mono text-sm text-foreground">
              {operation.path_template}
            </code>
            {operation.excluded && (
              <Badge tone="warning">Explicitly excluded</Badge>
            )}
          </div>
          <p className="mt-2 text-sm font-medium text-foreground">
            {operation.source_operation_id ?? operation.key}
          </p>
          <p className="mt-1 text-xs text-muted">
            Generated tool:{" "}
            <code className="font-mono text-accent">
              {operation.tool_name ?? "Not generated"}
            </code>
          </p>
        </div>
        {operation.excluded && operation.exclusion_id ? (
          <Button
            disabled={include.isPending}
            onClick={() => include.mutate()}
            size="sm"
            variant="outline"
          >
            Restore operation
          </Button>
        ) : (
          <Button
            onClick={() => setExcludeOpen(true)}
            size="sm"
            variant="ghost"
          >
            <ShieldAlert aria-hidden="true" className="size-4" />
            Exclude
          </Button>
        )}
      </div>
      {operation.exclusion_reason && (
        <Alert className="mt-4" tone="warning">
          Exclusion reason: {operation.exclusion_reason}
        </Alert>
      )}
      <div className="mt-4 grid gap-4 border-t border-border pt-4 lg:grid-cols-2">
        <div>
          <p className="font-mono text-[0.65rem] uppercase tracking-[0.1em] text-info-soft">
            Source-derived
          </p>
          <p className="mt-2 text-sm leading-6 text-muted">
            {operation.source_description ??
              operation.source_summary ??
              "No source description."}
          </p>
        </div>
        <div>
          <p className="font-mono text-[0.65rem] uppercase tracking-[0.1em] text-accent">
            Enriched semantics
          </p>
          <p className="mt-2 text-sm leading-6 text-muted">
            {operation.enriched_description ?? "No enrichment stored."}
          </p>
          {operation.confidence !== null && (
            <p className="mt-2 text-xs text-muted">
              Confidence: {Math.round(operation.confidence * 100)}%
            </p>
          )}
        </div>
      </div>
      <details className="mt-4 border-t border-border pt-4">
        <summary className="cursor-pointer text-sm font-medium text-accent">
          Inspect schema, auth mapping, and provenance
        </summary>
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <div>
            <p className="mb-2 text-xs font-medium text-muted">Input schema</p>
            <JsonCode
              label={`${operation.key} input schema`}
              value={operation.input_schema ?? {}}
            />
          </div>
          <div className="space-y-4">
            <div>
              <p className="mb-2 text-xs font-medium text-muted">
                Authentication mapping
              </p>
              <div className="flex flex-wrap gap-2">
                {operation.auth_mapping.length ? (
                  operation.auth_mapping.map((mapping) => (
                    <Badge key={mapping}>{mapping}</Badge>
                  ))
                ) : (
                  <span className="text-sm text-muted">
                    No upstream authentication
                  </span>
                )}
              </div>
            </div>
            <div>
              <p className="mb-2 text-xs font-medium text-muted">Provenance</p>
              <JsonCode
                label={`${operation.key} provenance`}
                value={operation.provenance}
              />
            </div>
          </div>
        </div>
      </details>
      {(exclude.error || include.error) && (
        <Alert className="mt-4" tone="danger">
          {exclude.error?.message ?? include.error?.message}
        </Alert>
      )}
      <Dialog
        description="Exclusions are durable, explicit, and recalculated in expected-operation coverage."
        onClose={() => setExcludeOpen(false)}
        open={excludeOpen}
        title={`Exclude ${operation.method} ${operation.path_template}`}
      >
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor={`exclusion-${operation.key}`}>Reason</Label>
            <Textarea
              autoFocus
              id={`exclusion-${operation.key}`}
              onChange={(event) => setReason(event.target.value)}
              placeholder="Explain why this operation cannot be represented safely."
              value={reason}
            />
            <FieldHelp>No operation may disappear silently.</FieldHelp>
          </div>
          <Button
            className="w-full"
            disabled={reason.trim().length < 5 || exclude.isPending}
            onClick={() => exclude.mutate()}
            variant="destructive"
          >
            Confirm explicit exclusion
          </Button>
        </div>
      </Dialog>
    </Card>
  );
}
