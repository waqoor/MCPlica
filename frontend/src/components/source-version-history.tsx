import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import type { SourceVersion } from "@/api/contracts";
import { sourceApi } from "@/api/sources";
import { QueryError, QueryPending } from "@/components/query-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatBytes, formatDate, shortenHash } from "@/lib/format";

export function SourceVersionHistory({
  projectId,
  sourceId,
  versionCount,
  onOpenChange,
}: {
  projectId: string;
  sourceId: string;
  versionCount: number;
  onOpenChange?: (open: boolean) => void;
}) {
  const [open, setOpen] = useState(false);
  const [page, setPage] = useState(1);
  const history = useQuery({
    queryKey: ["projects", projectId, "sources", sourceId, "versions", page],
    queryFn: ({ signal }) =>
      sourceApi.versionsPage(
        projectId,
        sourceId,
        { page, page_size: 10 },
        signal,
      ),
    enabled: open,
  });

  return (
    <details
      className="mt-5 border-t border-border pt-4"
      onToggle={(event) => {
        const nextOpen = event.currentTarget.open;
        setOpen(nextOpen);
        onOpenChange?.(nextOpen);
      }}
    >
      <summary className="cursor-pointer text-sm font-medium text-accent">
        Version history ({versionCount})
      </summary>
      <div className="mt-4 space-y-3">
        {history.isPending && open && (
          <QueryPending label="Loading immutable version history" />
        )}
        {history.error && (
          <QueryError
            error={history.error}
            onRetry={() => void history.refetch()}
          />
        )}
        {history.data?.items.map((version) => (
          <SourceVersionRow key={version.id} version={version} />
        ))}
        {history.data?.items.length === 0 && (
          <p className="text-sm text-muted">
            No immutable versions were returned.
          </p>
        )}
        {history.data && history.data.total > history.data.page_size && (
          <div className="flex items-center justify-between gap-3">
            <Button
              disabled={page === 1}
              onClick={() => setPage((value) => value - 1)}
              size="sm"
              variant="outline"
            >
              Previous versions
            </Button>
            <span className="text-xs text-muted">
              Page {history.data.page} of{" "}
              {Math.ceil(history.data.total / history.data.page_size)}
            </span>
            <Button
              disabled={page * history.data.page_size >= history.data.total}
              onClick={() => setPage((value) => value + 1)}
              size="sm"
              variant="outline"
            >
              Next versions
            </Button>
          </div>
        )}
      </div>
    </details>
  );
}

function SourceVersionRow({ version }: { version: SourceVersion }) {
  const [open, setOpen] = useState(false);
  const metadata = useQuery({
    queryKey: ["source-versions", version.id, "metadata"],
    queryFn: ({ signal }) => sourceApi.versionMetadata(version.id, signal),
    enabled: open,
  });

  return (
    <article className="rounded-md border border-border bg-input p-3 text-xs">
      <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        <VersionFact label="Created" value={formatDate(version.created_at)} />
        <VersionFact label="Size" value={formatBytes(version.byte_size)} />
        <VersionFact label="Format" value={version.detected_format} />
        <VersionFact label="Created by" value={version.created_by} mono />
      </div>
      <div className="mt-3 space-y-1 border-t border-border pt-3">
        <p className="text-muted">Content-addressed deduplication identity</p>
        <code
          className="block break-all font-mono text-foreground"
          title={version.content_sha256}
        >
          SHA-256 {version.content_sha256}
        </code>
        <p className="text-muted">
          Identical bytes for this source reuse this immutable version instead
          of creating a duplicate history row.
        </p>
        {(version.source_etag || version.source_last_modified) && (
          <p className="break-all text-muted">
            Origin provenance: ETag {version.source_etag ?? "not supplied"} ·
            Last modified {version.source_last_modified ?? "not supplied"}
          </p>
        )}
      </div>
      <details
        className="mt-3 border-t border-border pt-3"
        onToggle={(event) => setOpen(event.currentTarget.open)}
      >
        <summary className="cursor-pointer font-medium text-accent">
          Inspect parse and index evidence · {shortenHash(version.id)}
        </summary>
        <div className="mt-3 space-y-3">
          {metadata.isPending && open && (
            <QueryPending label="Loading this version's evidence" />
          )}
          {metadata.error && (
            <QueryError
              error={metadata.error}
              onRetry={() => void metadata.refetch()}
            />
          )}
          {metadata.data && (
            <div
              aria-label="Version evidence status"
              className="flex flex-wrap gap-2"
            >
              <Badge
                tone={
                  metadata.data.parse_status === "invalid"
                    ? "danger"
                    : metadata.data.parse_status === "valid"
                      ? "success"
                      : "warning"
                }
              >
                Parse {metadata.data.parse_status}
              </Badge>
              <Badge
                tone={
                  metadata.data.index_status === "ready" ? "success" : "neutral"
                }
              >
                Index {metadata.data.index_status ?? "not applicable"}
              </Badge>
              {metadata.data.metadata_build_id && (
                <Badge>
                  Build {shortenHash(metadata.data.metadata_build_id)}
                </Badge>
              )}
              {metadata.data.errors.length > 0 && (
                <Badge tone="danger">
                  {metadata.data.errors.length} source finding
                  {metadata.data.errors.length === 1 ? "" : "s"}
                </Badge>
              )}
            </div>
          )}
        </div>
      </details>
    </article>
  );
}

function VersionFact({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div>
      <p className="text-muted">{label}</p>
      <p
        className={
          mono ? "break-all font-mono text-foreground" : "text-foreground"
        }
      >
        {value}
      </p>
    </div>
  );
}
