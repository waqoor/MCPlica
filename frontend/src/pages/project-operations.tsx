import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Braces, Filter, RefreshCw, Search, ShieldAlert } from "lucide-react";
import { useDeferredValue, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { Operation } from "@/api/contracts";
import { buildApi } from "@/api/builds";
import { MutationError } from "@/components/error-notice";
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
import { selectEvidenceBuild } from "@/features/projects/evidence-build";
import { operationPolicyState } from "@/features/projects/operation-policy";
import { useProject } from "@/features/projects/project-context";
import { buildOwnershipError } from "@/lib/build-ownership";

const methodTone: Record<
  string,
  "info" | "success" | "warning" | "danger" | "neutral"
> = {
  GET: "info",
  POST: "success",
  PUT: "warning",
  PATCH: "warning",
  DELETE: "danger",
  HEAD: "info",
  OPTIONS: "neutral",
  TRACE: "warning",
};

export function ProjectOperationsPage() {
  const project = useProject();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const search = searchParams.get("search") ?? "";
  const deferredSearch = useDeferredValue(search.toLowerCase());
  const method = searchParams.get("method") ?? "";
  const scope = searchParams.get("scope") ?? "all";
  const rawPage = Number(searchParams.get("page") ?? "1");
  const page = Number.isInteger(rawPage) && rawPage > 0 ? rawPage : 1;
  const updateFilter = (name: string, value: string) => {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      if (value) next.set(name, value);
      else next.delete(name);
      next.delete("page");
      return next;
    });
  };
  const builds = useQuery({
    queryKey: ["projects", project.id, "builds"],
    queryFn: ({ signal }) => buildApi.list(project.id, signal),
  });
  const requestedBuildId = searchParams.get("build");
  const pinnedBuildId = requestedBuildId ?? project.active_build_id;
  const pinnedBuildInPage = builds.data?.find(
    (build) => build.id === pinnedBuildId,
  );
  const needsExactBuild = Boolean(
    builds.data && pinnedBuildId && !pinnedBuildInPage,
  );
  const exactBuild = useQuery({
    queryKey: ["builds", pinnedBuildId],
    queryFn: ({ signal }) => buildApi.get(pinnedBuildId!, signal),
    enabled: needsExactBuild,
  });
  const exactBuildResolved = !needsExactBuild || exactBuild.isSuccess;
  const evidenceBuilds =
    needsExactBuild && exactBuild.data
      ? [...(builds.data ?? []), exactBuild.data]
      : (builds.data ?? []);
  const latest = builds.data?.[0] ?? exactBuild.data;
  const requestedBuild = requestedBuildId
    ? evidenceBuilds.find((build) => build.id === requestedBuildId)
    : undefined;
  const selectedBuild = selectEvidenceBuild(
    evidenceBuilds,
    requestedBuildId,
    project.active_build_id,
  );
  const ownershipCandidate = requestedBuild ?? selectedBuild;
  const ownershipError = ownershipCandidate
    ? buildOwnershipError(ownershipCandidate, project.id)
    : null;
  useEffect(() => {
    if (
      !exactBuildResolved ||
      !selectedBuild ||
      requestedBuildId === selectedBuild.id
    )
      return;
    setSearchParams(
      (current) => {
        const next = new URLSearchParams(current);
        next.set("build", selectedBuild.id);
        return next;
      },
      { replace: true },
    );
  }, [exactBuildResolved, requestedBuildId, selectedBuild, setSearchParams]);
  const operations = useQuery({
    queryKey: [
      "builds",
      selectedBuild?.id,
      "operations",
      { search: deferredSearch, method, scope, page },
    ],
    queryFn: ({ signal }) =>
      buildApi.operations(
        selectedBuild!.id,
        {
          search: deferredSearch || undefined,
          method: method || undefined,
          scope,
          page,
          page_size: 50,
        },
        signal,
      ),
    enabled: Boolean(selectedBuild) && !ownershipError && exactBuildResolved,
  });
  const policyChangeCount = operations.data?.policy_change_count ?? 0;
  const rebuild = useMutation({
    mutationFn: () => buildApi.rebuild(project.id),
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: ["projects", project.id, "builds"],
      }),
  });
  if (builds.isPending)
    return <QueryPending label="Finding the latest build" />;
  if (builds.error)
    return (
      <QueryError error={builds.error} onRetry={() => void builds.refetch()} />
    );
  if (needsExactBuild && exactBuild.isPending)
    return <QueryPending label="Loading the selected evidence build" />;
  if (needsExactBuild && exactBuild.error)
    return (
      <QueryError
        error={exactBuild.error}
        onRetry={() => void exactBuild.refetch()}
      />
    );
  if (ownershipError) return <QueryError error={ownershipError} />;
  if (!latest)
    return (
      <EmptyState
        description="Start a build after attaching an executable source. Operations remain source-derived and are not inferred from documentation."
        icon={Braces}
        title="No operation snapshot yet"
      />
    );
  if (!selectedBuild)
    return (
      <EmptyState
        description={`Build #${latest.sequence} is ${latest.status.toLowerCase()} and no build has reached a canonical operation snapshot yet. Build progress is separate from immutable evidence.`}
        icon={Braces}
        title="No inspectable operation snapshot yet"
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
      <div className="flex flex-col justify-between gap-3 lg:flex-row lg:items-start">
        <div>
          <h2 className="text-xl font-semibold text-foreground">
            Operations and tools
          </h2>
          <p className="mt-1 text-sm text-muted">
            Build #{selectedBuild.sequence} is the selected immutable evidence
            snapshot. Policy changes apply only to the next build and never
            rewrite this evidence.
          </p>
        </div>
        <div className="flex min-w-[15rem] flex-col gap-2 sm:flex-row lg:justify-end">
          <div>
            <Label className="sr-only" htmlFor="evidence-build">
              Evidence build
            </Label>
            <Select
              id="evidence-build"
              onChange={(event) =>
                setSearchParams((current) => {
                  const next = new URLSearchParams(current);
                  next.set("build", event.target.value);
                  return next;
                })
              }
              value={selectedBuild.id}
            >
              {evidenceBuilds
                .filter((build) => build.canonical_snapshot_id)
                .map((build) => (
                  <option key={build.id} value={build.id}>
                    Build #{build.sequence} · {build.status}
                    {build.id === project.active_build_id
                      ? " · active served"
                      : ""}
                  </option>
                ))}
            </Select>
          </div>
          {policyChangeCount > 0 && (
            <Button
              disabled={rebuild.isPending}
              onClick={() => rebuild.mutate()}
              variant="outline"
            >
              <RefreshCw aria-hidden="true" className="size-4" />
              Rebuild with {policyChangeCount} policy{" "}
              {policyChangeCount === 1 ? "change" : "changes"}
            </Button>
          )}
        </div>
      </div>
      {latest.id !== selectedBuild.id && (
        <Alert
          title={`Current build progress: #${latest.sequence}`}
          tone="info"
        >
          Build #{latest.sequence} is {latest.status}. Evidence remains pinned
          to build #{selectedBuild.sequence} by the URL until you select another
          inspectable snapshot.
        </Alert>
      )}
      {policyChangeCount > 0 && (
        <Alert title="Current policy differs from this build" tone="warning">
          {policyChangeCount} operation{" "}
          {policyChangeCount === 1 ? "policy has" : "policies have"} changed
          since build #{selectedBuild.sequence}. The currently served or
          inspected artifact is unchanged until a new build validates
          successfully and is deployed.
        </Alert>
      )}
      {rebuild.data && (
        <Alert
          title={`Build #${rebuild.data.sequence} requested`}
          tone="success"
        >
          The new build is using the current exclusion policy. Build #
          {selectedBuild.sequence} remains immutable for comparison and audit.
        </Alert>
      )}
      {rebuild.error && <MutationError error={rebuild.error} />}
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
            onChange={(event) => updateFilter("search", event.target.value)}
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
            onChange={(event) => updateFilter("method", event.target.value)}
            value={method}
          >
            <option value="">All methods</option>
            {[
              "GET",
              "POST",
              "PUT",
              "PATCH",
              "DELETE",
              "HEAD",
              "OPTIONS",
              "TRACE",
            ].map((value) => (
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
            onChange={(event) => updateFilter("scope", event.target.value)}
            value={scope}
          >
            <option value="all">All operations</option>
            <option value="current-included">Currently included</option>
            <option value="current-excluded">Currently excluded</option>
            <option value="build-excluded">Excluded in this build</option>
            <option value="changed">Changed since this build</option>
          </Select>
        </div>
      </div>
      <p aria-live="polite" className="text-xs text-muted">
        Showing {operations.data.items.length} of {operations.data.total}{" "}
        matching operations
      </p>
      {!operations.data.items.length ? (
        <EmptyState
          description="Change the search or filters to inspect other operations."
          icon={Filter}
          title="No matching operations"
        />
      ) : (
        <div className="space-y-3">
          {operations.data.items.map((operation) => (
            <OperationCard
              buildId={selectedBuild.id}
              buildSequence={selectedBuild.sequence}
              key={operation.key}
              operation={operation}
              projectId={project.id}
            />
          ))}
        </div>
      )}
      {operations.data.total > operations.data.page_size && (
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
            Page {operations.data.page} of{" "}
            {Math.ceil(operations.data.total / operations.data.page_size)}
          </span>
          <Button
            disabled={page * operations.data.page_size >= operations.data.total}
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

function OperationCard({
  operation,
  projectId,
  buildId,
  buildSequence,
}: {
  operation: Operation;
  projectId: string;
  buildId: string;
  buildSequence: number;
}) {
  const queryClient = useQueryClient();
  const policy = operationPolicyState(operation);
  const [excludeOpen, setExcludeOpen] = useState(false);
  const [inspectOpen, setInspectOpen] = useState(false);
  const [reason, setReason] = useState("");
  const exclude = useMutation({
    mutationFn: () =>
      buildApi.excludeOperation(projectId, operation.key, reason),
    onSuccess: async () => {
      setExcludeOpen(false);
      setReason("");
      await queryClient.invalidateQueries({
        queryKey: ["builds", buildId, "operations"],
      });
    },
  });
  const include = useMutation({
    mutationFn: () =>
      buildApi.removeExclusion(projectId, operation.current_exclusion_id!),
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: ["builds", buildId, "operations"],
      }),
  });
  return (
    <Card
      className={policy.changedSinceBuild ? "border-warning/50" : undefined}
    >
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={methodTone[operation.method] ?? "neutral"}>
              {operation.method}
            </Badge>
            <code className="break-all font-mono text-sm text-foreground">
              {operation.path_template}
            </code>
            <Badge tone={policy.excludedInBuild ? "warning" : "neutral"}>
              {policy.excludedInBuild
                ? `Excluded in build #${buildSequence}`
                : `Included in build #${buildSequence}`}
            </Badge>
            <Badge tone={policy.currentlyExcluded ? "warning" : "success"}>
              {policy.currentlyExcluded
                ? "Excluded from next build"
                : "Included in next build"}
            </Badge>
            {policy.changedSinceBuild && (
              <Badge tone="info">Policy changed</Badge>
            )}
          </div>
          <p className="mt-2 text-sm font-medium text-foreground">
            {operation.title ??
              operation.source_summary ??
              operation.source_operation_id ??
              operation.key}
          </p>
          <p className="mt-1 font-mono text-xs text-muted">
            Source operation: {operation.source_operation_id ?? operation.key}
          </p>
          <p className="mt-1 text-xs text-muted">
            Generated tool:{" "}
            <code className="font-mono text-accent">
              {operation.tool_name ?? "Not generated"}
            </code>
          </p>
        </div>
        {operation.current_exclusion_id ? (
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
      {operation.build_exclusion_reason && (
        <Alert className="mt-4" tone="warning">
          Build #{buildSequence} exclusion reason:{" "}
          {operation.build_exclusion_reason}
        </Alert>
      )}
      {operation.current_exclusion_reason && (
        <Alert className="mt-4" tone="info">
          Current policy reason: {operation.current_exclusion_reason}
        </Alert>
      )}
      {operation.semantic_warnings.length > 0 && (
        <Alert className="mt-4" title="Semantic warnings" tone="warning">
          <ul className="list-disc space-y-1 pl-4">
            {operation.semantic_warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
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
      <details
        className="mt-4 border-t border-border pt-4"
        onToggle={(event) => setInspectOpen(event.currentTarget.open)}
      >
        <summary className="cursor-pointer text-sm font-medium text-accent">
          Inspect schema, auth mapping, and provenance
        </summary>
        {inspectOpen && (
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <div>
              <p className="mb-2 text-xs font-medium text-muted">
                Input schema
              </p>
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
                <p className="mb-2 text-xs font-medium text-muted">
                  Provenance
                </p>
                <JsonCode
                  label={`${operation.key} provenance`}
                  value={operation.provenance}
                />
              </div>
            </div>
          </div>
        )}
      </details>
      {(exclude.error || include.error) && (
        <MutationError error={exclude.error ?? include.error} />
      )}
      <Dialog
        description={`This changes current project policy only. Build #${buildSequence} remains immutable; rebuild to recalculate expected-operation coverage.`}
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
