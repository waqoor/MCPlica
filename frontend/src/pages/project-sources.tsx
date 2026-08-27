import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileCode2, FilePlus2, RefreshCw, Upload } from "lucide-react";
import { useState } from "react";
import type { ProjectSource, SourceKind } from "@/api/contracts";
import { sourceApi } from "@/api/sources";
import { QueryError, QueryPending } from "@/components/query-state";
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
import { MAX_UPLOAD_LABEL, uploadAccept, uploadFileError } from "@/lib/uploads";

export function ProjectSourcesPage() {
  const project = useProject();
  const queryClient = useQueryClient();
  const [addOpen, setAddOpen] = useState(false);
  const sources = useQuery({
    queryKey: ["projects", project.id, "sources"],
    queryFn: ({ signal }) => sourceApi.list(project.id, signal),
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
      {sources.data.length === 0 ? (
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
          {sources.data.map((source) => (
            <SourceCard
              key={source.id}
              projectId={project.id}
              refreshing={refresh.isPending && refresh.variables === source.id}
              source={source}
              onRefresh={() => refresh.mutate(source.id)}
              onVersionAdded={invalidate}
            />
          ))}
        </div>
      )}
      {refresh.error && <Alert tone="danger">{refresh.error.message}</Alert>}
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
  const version = useMutation({
    mutationFn: () => sourceApi.addVersion(projectId, source.id, file!),
    onSuccess: () => {
      setFile(null);
      setFileError(null);
      onVersionAdded();
    },
  });
  const latest = source.latest_version;
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
          </div>
          <p className="mt-1 break-all text-xs text-muted">
            {source.source_url ?? "Uploaded source"}
          </p>
        </div>
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
      </CardHeader>
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
              <li key={`${issue.code}-${issue.location}`}>
                {issue.code}: {issue.message}
                {issue.location ? ` (${issue.location})` : ""}
              </li>
            ))}
          </ul>
        </Alert>
      ) : null}
      <div className="mt-5 flex flex-col gap-2 border-t border-border pt-4 sm:flex-row sm:items-end">
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
                ? `${file.name} · ${(file.size / 1_000_000).toFixed(2)} MB`
                : latest
                  ? `Current version created ${formatDate(latest.created_at)} · ${MAX_UPLOAD_LABEL} maximum.`
                  : `No current version · ${MAX_UPLOAD_LABEL} maximum.`}
            </FieldHelp>
          )}
        </div>
        <Button
          disabled={!file || Boolean(fileError) || version.isPending}
          onClick={() => version.mutate()}
          variant="outline"
        >
          <Upload aria-hidden="true" className="size-4" />
          {version.isPending ? "Uploading…" : "Add version"}
        </Button>
      </div>
      {version.error && (
        <Alert className="mt-4" tone="danger">
          {version.error.message}
        </Alert>
      )}
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
  const create = useMutation({
    mutationFn: () =>
      origin === "url"
        ? sourceApi.createFromUrl(projectId, { name, kind, source_url: url })
        : sourceApi.createFromUpload(projectId, { name, kind, file: file! }),
    onSuccess: onAdded,
  });
  const ready =
    name.trim() &&
    (origin === "url" ? /^https?:\/\//.test(url) : Boolean(file) && !fileError);
  return (
    <div className="space-y-4">
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
              {kind === "documentation"
                ? `JSON, Markdown, TXT, CSV, XLSX, DOCX, HTML, or PDF · ${MAX_UPLOAD_LABEL} maximum.`
                : `OpenAPI 3.x or API Inventory v1 JSON/YAML · ${MAX_UPLOAD_LABEL} maximum.`}
            </FieldHelp>
          )}
        </div>
      )}
      {create.error && <Alert tone="danger">{create.error.message}</Alert>}
      <Button
        className="w-full"
        disabled={!ready || create.isPending}
        onClick={() => create.mutate()}
      >
        {create.isPending ? "Adding source…" : "Add source"}
      </Button>
    </div>
  );
}
