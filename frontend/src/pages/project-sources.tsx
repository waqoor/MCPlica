import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  FileCode2,
  FilePlus2,
  RefreshCw,
  Star,
  Trash2,
  Upload,
} from "lucide-react";
import { useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { ProjectSource, SourceKind } from "@/api/contracts";
import { sourceApi } from "@/api/sources";
import { MutationError } from "@/components/error-notice";
import { JsonCode } from "@/components/json-code";
import { QueryError, QueryPending } from "@/components/query-state";
import { SourceVersionHistory } from "@/components/source-version-history";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { FieldError, FieldHelp, Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { useProject } from "@/features/projects/project-context";
import { formatBytes, formatDate, shortenHash } from "@/lib/format";
import {
  MAX_UPLOAD_LABEL,
  uploadAccept,
  uploadFileError,
  uploadFormatLabel,
} from "@/lib/uploads";

export function ProjectSourcesPage() {
  const project = useProject();
  const queryClient = useQueryClient();
  const [addOpen, setAddOpen] = useState(false);
  const [searchParams, setSearchParams] = useSearchParams();
  const rawPage = Number(searchParams.get("page") ?? "1");
  const page = Number.isInteger(rawPage) && rawPage > 0 ? rawPage : 1;
  const sources = useQuery({
    queryKey: ["projects", project.id, "sources", { page }],
    queryFn: ({ signal }) =>
      sourceApi.listPage(project.id, { page, page_size: 25 }, signal),
  });
  const invalidate = () =>
    queryClient.invalidateQueries({
      queryKey: ["projects", project.id, "sources"],
    });
  const refresh = useMutation({
    mutationFn: (sourceId: string) => sourceApi.refresh(project.id, sourceId),
    onSuccess: invalidate,
  });

  if (sources.isPending)
    return <QueryPending label="Loading project sources" />;
  if (sources.error)
    return (
      <QueryError
        error={sources.error}
        onRetry={() => void sources.refetch()}
      />
    );
  return (
    <div className="space-y-5">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
        <div>
          <h2 className="text-xl font-semibold text-foreground">Sources</h2>
          <p className="mt-1 text-sm text-muted">
            Immutable versions preserve exactly what each build consumed.
          </p>
        </div>
        <Button onClick={() => setAddOpen(true)}>
          <FilePlus2 aria-hidden="true" className="size-4" />
          Add source
        </Button>
      </div>
      {sources.data.items.length === 0 ? (
        <EmptyState
          action={
            <Button onClick={() => setAddOpen(true)}>
              Add executable source
            </Button>
          }
          description="Attach OpenAPI 3.x or API Inventory v1 before starting a build."
          icon={FileCode2}
          title="No source records"
        />
      ) : (
        <div className="space-y-4">
          {sources.data.items.map((source) => (
            <SourceCard
              key={source.id}
              projectId={project.id}
              refreshing={refresh.isPending && refresh.variables === source.id}
              source={source}
              onRefresh={() => refresh.mutate(source.id)}
              onVersionAdded={invalidate}
            />
          ))}
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
              Page {sources.data.page} · {sources.data.total} sources
            </span>
            <Button
              disabled={page * sources.data.page_size >= sources.data.total}
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
        </div>
      )}
      {refresh.error && <MutationError error={refresh.error} />}
      <Dialog
        description="Sources are stored as immutable content-hashed versions."
        onClose={() => setAddOpen(false)}
        open={addOpen}
        title="Add project source"
      >
        <AddSourceForm
          onAdded={() => {
            setAddOpen(false);
            void invalidate();
          }}
          projectId={project.id}
        />
      </Dialog>
    </div>
  );
}

function SourceCard({
  source,
  projectId,
  refreshing,
  onRefresh,
  onVersionAdded,
}: {
  source: ProjectSource;
  projectId: string;
  refreshing: boolean;
  onRefresh: () => void;
  onVersionAdded: () => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const metadata = useQuery({
    queryKey: ["source-versions", source.latest_version?.id, "metadata"],
    queryFn: ({ signal }) =>
      sourceApi.versionMetadata(source.latest_version!.id, signal),
    enabled: historyOpen && Boolean(source.latest_version),
  });
  const version = useMutation({
    mutationFn: () => sourceApi.addVersion(projectId, source.id, file!),
    onSuccess: () => {
      setFile(null);
      setFileError(null);
      onVersionAdded();
    },
  });
  const promote = useMutation({
    mutationFn: () =>
      sourceApi.update(projectId, source.id, { is_primary: true }),
    onSuccess: onVersionAdded,
  });
  const remove = useMutation({
    mutationFn: () => sourceApi.remove(projectId, source.id),
    onSuccess: onVersionAdded,
  });
  const latest = metadata.data ?? source.latest_version;
  return (
    <Card>
      <CardHeader>
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <CardTitle>{source.name}</CardTitle>
            <Badge tone={source.kind === "documentation" ? "info" : "success"}>
              {source.kind}
            </Badge>
            <Badge>{source.origin_type}</Badge>
            <Badge
              tone={
                source.health === "invalid"
                  ? "danger"
                  : source.health === "valid"
                    ? "success"
                    : "warning"
              }
            >
              {source.health}
            </Badge>
            {source.is_primary && <Badge tone="success">Primary</Badge>}
          </div>
          <p className="mt-1 break-all text-xs text-muted">
            {source.source_url ?? "Uploaded source"}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {source.origin_type === "url" && (
            <Button
              disabled={refreshing}
              onClick={onRefresh}
              size="sm"
              variant="outline"
            >
              <RefreshCw
                aria-hidden="true"
                className={
                  refreshing
                    ? "size-4 animate-spin motion-reduce:animate-none"
                    : "size-4"
                }
              />
              Refresh
            </Button>
          )}
          {source.kind !== "documentation" &&
            source.latest_version &&
            !source.is_primary && (
              <Button
                disabled={promote.isPending}
                onClick={() => promote.mutate()}
                size="sm"
                variant="outline"
              >
                <Star aria-hidden="true" className="size-4" />
                Make primary
              </Button>
            )}
          <Button
            disabled={remove.isPending}
            onClick={() => {
              if (
                window.confirm(
                  "Delete this source? Sources referenced by an immutable build are protected.",
                )
              )
                remove.mutate();
            }}
            size="sm"
            variant="ghost"
          >
            <Trash2 aria-hidden="true" className="size-4" />
            Delete
          </Button>
        </div>
      </CardHeader>
      {(promote.error || remove.error) && (
        <MutationError error={promote.error ?? remove.error} />
      )}
      {latest ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Fact
            label="Detected"
            value={latest.detected_format ?? latest.media_type}
          />
          <Fact
            label={
              source.kind === "documentation" ? "Indexed chunks" : "Operations"
            }
            value={
              source.kind === "documentation"
                ? (latest.indexed_chunk_count?.toString() ?? "Pending index")
                : (latest.operation_count?.toString() ?? "Pending parse")
            }
          />
          <Fact label="Size" value={formatBytes(latest.byte_size)} />
          <Fact
            label="SHA-256"
            value={shortenHash(latest.content_sha256)}
            mono
          />
        </div>
      ) : (
        <Alert tone="warning">This source has no stored version yet.</Alert>
      )}
      {latest?.servers?.length ? (
        <div className="mt-4">
          <p className="mb-2 text-xs font-medium text-muted">
            Declared servers
          </p>
          <div className="flex flex-wrap gap-2">
            {latest.servers.map((server) => (
              <code
                className="rounded border border-border bg-input px-2 py-1 font-mono text-[0.68rem] text-info-soft"
                key={server}
              >
                {server}
              </code>
            ))}
          </div>
        </div>
      ) : null}
      {latest?.errors?.length ? (
        <Alert
          className="mt-4"
          title="Source findings"
          tone={
            latest.errors.some((issue) => issue.severity === "error")
              ? "danger"
              : "warning"
          }
        >
          <ul className="space-y-1">
            {latest.errors.map((issue) => (
              <li
                className="space-y-1"
                key={`${issue.stage}-${issue.code}-${issue.pointer ?? "root"}-${issue.line ?? ""}-${issue.column ?? ""}`}
              >
                <div>
                  {issue.code}: {issue.message}
                </div>
                <div className="font-mono text-xs opacity-80">
                  {issue.stage}
                  {issue.pointer ? ` · ${issue.pointer}` : ""}
                  {issue.line ? ` · line ${issue.line}` : ""}
                  {issue.column ? `:${issue.column}` : ""}
                </div>
                {issue.details && Object.keys(issue.details).length > 0 && (
                  <details>
                    <summary className="cursor-pointer text-xs font-medium">
                      Structured evidence
                    </summary>
                    <JsonCode
                      label={`${issue.code} source evidence`}
                      value={issue.details}
                    />
                  </details>
                )}
              </li>
            ))}
          </ul>
        </Alert>
      ) : null}
      <SourceVersionHistory
        onOpenChange={setHistoryOpen}
        projectId={projectId}
        sourceId={source.id}
        versionCount={source.version_count}
      />
      {metadata.error && historyOpen && (
        <QueryError
          error={metadata.error}
          onRetry={() => void metadata.refetch()}
        />
      )}
      <form
        className="mt-5 flex flex-col gap-2 border-t border-border pt-4 sm:flex-row sm:items-end"
        onSubmit={(event) => {
          event.preventDefault();
          if (file && !fileError && !version.isPending) version.mutate();
        }}
      >
        <div className="flex-1 space-y-2">
          <Label htmlFor={`version-${source.id}`}>
            Upload a new immutable version
          </Label>
          <Input
            accept={uploadAccept(source.kind)}
            aria-invalid={Boolean(fileError)}
            id={`version-${source.id}`}
            onChange={(event) => {
              const selected = event.target.files?.[0] ?? null;
              setFile(selected);
              setFileError(
                selected ? uploadFileError(selected, source.kind) : null,
              );
            }}
            type="file"
          />
          {fileError ? (
            <FieldError>{fileError}</FieldError>
          ) : (
            <FieldHelp>
              {file
                ? `${file.name} · ${formatBytes(file.size)}`
                : latest
                  ? `Current version created ${formatDate(latest.created_at)} · ${MAX_UPLOAD_LABEL} maximum.`
                  : `No current version · ${MAX_UPLOAD_LABEL} maximum.`}
            </FieldHelp>
          )}
        </div>
        <Button
          disabled={!file || Boolean(fileError) || version.isPending}
          type="submit"
          variant="outline"
        >
          <Upload aria-hidden="true" className="size-4" />
          {version.isPending ? "Uploading…" : "Add version"}
        </Button>
      </form>
      {version.error && <MutationError error={version.error} />}
    </Card>
  );
}

function Fact({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="rounded-md border border-border bg-input p-3">
      <p className="font-mono text-[0.62rem] uppercase tracking-[0.1em] text-muted">
        {label}
      </p>
      <p
        className={
          mono
            ? "mt-2 truncate font-mono text-xs text-foreground"
            : "mt-2 truncate text-sm text-foreground"
        }
      >
        {value}
      </p>
    </div>
  );
}

function AddSourceForm({
  projectId,
  onAdded,
}: {
  projectId: string;
  onAdded: () => void;
}) {
  const [origin, setOrigin] = useState<"upload" | "url">("upload");
  const [kind, setKind] = useState<SourceKind>("openapi");
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const sourceId = useRef(crypto.randomUUID());
  const create = useMutation({
    mutationFn: () =>
      origin === "url"
        ? sourceApi.createFromUrl(projectId, {
            source_id: sourceId.current,
            name,
            kind,
            source_url: url,
          })
        : sourceApi.createFromUpload(projectId, {
            source_id: sourceId.current,
            name,
            kind,
            file: file!,
          }),
    onSuccess: onAdded,
  });
  const ready =
    name.trim() &&
    (origin === "url" ? /^https?:\/\//.test(url) : Boolean(file) && !fileError);
  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        if (ready && !create.isPending) create.mutate();
      }}
    >
      <div className="space-y-2">
        <Label htmlFor="add-source-name">Name</Label>
        <Input
          autoFocus
          id="add-source-name"
          onChange={(event) => setName(event.target.value)}
          value={name}
        />
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="add-source-kind">Kind</Label>
          <Select
            id="add-source-kind"
            onChange={(event) => {
              const nextKind = event.target.value as SourceKind;
              setKind(nextKind);
              setFileError(file ? uploadFileError(file, nextKind) : null);
            }}
            value={kind}
          >
            <option value="openapi">OpenAPI 3.x</option>
            <option value="api_inventory">API Inventory v1</option>
            <option value="documentation">Documentation</option>
          </Select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="add-source-origin">Input</Label>
          <Select
            id="add-source-origin"
            onChange={(event) =>
              setOrigin(event.target.value as "upload" | "url")
            }
            value={origin}
          >
            <option value="upload">File upload</option>
            <option value="url">Secure URL</option>
          </Select>
        </div>
      </div>
      {origin === "url" ? (
        <div className="space-y-2">
          <Label htmlFor="add-source-url">URL</Label>
          <Input
            id="add-source-url"
            onChange={(event) => setUrl(event.target.value)}
            type="url"
            value={url}
          />
        </div>
      ) : (
        <div className="space-y-2">
          <Label htmlFor="add-source-file">File</Label>
          <Input
            accept={uploadAccept(kind)}
            aria-invalid={Boolean(fileError)}
            id="add-source-file"
            onChange={(event) => {
              const selected = event.target.files?.[0] ?? null;
              setFile(selected);
              setFileError(selected ? uploadFileError(selected, kind) : null);
              if (selected && !name.trim()) setName(selected.name);
            }}
            type="file"
          />
          {fileError ? (
            <FieldError>{fileError}</FieldError>
          ) : (
            <FieldHelp>
              {`${uploadFormatLabel(kind)} · ${MAX_UPLOAD_LABEL} maximum.`}
            </FieldHelp>
          )}
        </div>
      )}
      {create.error && <MutationError error={create.error} />}
      <Button
        className="w-full"
        disabled={!ready || create.isPending}
        type="submit"
      >
        {create.isPending ? "Adding source…" : "Add source"}
      </Button>
    </form>
  );
}
