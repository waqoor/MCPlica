import { useQuery } from "@tanstack/react-query";
import { BookOpen, FileText } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import type { ProjectSource } from "@/api/contracts";
import { sourceApi } from "@/api/sources";
import { QueryError, QueryPending } from "@/components/query-state";
import { SafeMarkdown } from "@/components/safe-markdown";
import { SourceVersionHistory } from "@/components/source-version-history";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button-variants";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { useProject } from "@/features/projects/project-context";
import { formatDate } from "@/lib/format";
import { uploadFormatLabel } from "@/lib/uploads";

export function ProjectDocumentationPage() {
  const project = useProject();
  const sources = useQuery({
    queryKey: ["projects", project.id, "sources"],
    queryFn: ({ signal }) => sourceApi.list(project.id, signal),
  });
  if (sources.isPending) return <QueryPending label="Loading documentation" />;
  if (sources.error)
    return (
      <QueryError
        error={sources.error}
        onRetry={() => void sources.refetch()}
      />
    );
  const docs = sources.data.filter((source) => source.kind === "documentation");
  if (!docs.length)
    return (
      <EmptyState
        action={
          <Link
            className={buttonVariants({ variant: "outline" })}
            to="../sources"
          >
            Add documentation
          </Link>
        }
        description={`${uploadFormatLabel("documentation")} can enrich tool semantics but never define executable behavior.`}
        icon={BookOpen}
        title="No documentation sources"
      />
    );
  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-xl font-semibold text-foreground">Documentation</h2>
        <p className="mt-1 text-sm text-muted">
          Project-scoped source and indexing evidence. Embedding vectors are
          never exposed.
        </p>
      </div>
      {docs.map((source) => (
        <Card key={source.id}>
          <CardHeader>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <CardTitle>{source.name}</CardTitle>
                <Badge tone={source.health === "invalid" ? "danger" : "info"}>
                  {source.health}
                </Badge>
                <Badge
                  tone={source.health === "invalid" ? "danger" : "warning"}
                >
                  Evidence on demand
                </Badge>
              </div>
              <p className="mt-1 text-xs text-muted">
                {source.origin_type === "url"
                  ? source.source_url
                  : "Uploaded file"}
              </p>
            </div>
            <FileText aria-hidden="true" className="size-5 text-info" />
          </CardHeader>
          <dl className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <div>
              <dt className="text-xs text-muted">Indexed chunks</dt>
              <dd className="mt-1 text-sm text-foreground">
                Open evidence below
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted">Embedding model</dt>
              <dd className="mt-1 break-all text-sm text-foreground">
                Open evidence below
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted">Dimensions</dt>
              <dd className="mt-1 text-sm text-foreground">
                Open evidence below
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted">Format</dt>
              <dd className="mt-1 text-sm text-foreground">
                {source.latest_version?.detected_format ?? "Pending parse"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted">Version created</dt>
              <dd className="mt-1 text-sm text-foreground">
                {formatDate(source.latest_version?.created_at)}
              </dd>
            </div>
          </dl>
          <DocumentationEvidence source={source} />
          <SourceVersionHistory
            projectId={project.id}
            sourceId={source.id}
            versionCount={source.version_count}
          />
        </Card>
      ))}
    </div>
  );
}

function DocumentationEvidence({ source }: { source: ProjectSource }) {
  const [open, setOpen] = useState(false);
  const metadata = useQuery({
    queryKey: ["source-versions", source.latest_version?.id, "metadata"],
    queryFn: ({ signal }) =>
      sourceApi.versionMetadata(source.latest_version!.id, signal),
    enabled: open && Boolean(source.latest_version),
  });
  return (
    <details
      className="mt-5 border-t border-border pt-4"
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary className="cursor-pointer text-sm font-medium text-accent">
        Load indexing evidence and sanitized preview
      </summary>
      <div className="mt-4 space-y-4">
        {metadata.isPending && open && (
          <QueryPending label="Loading documentation evidence" />
        )}
        {metadata.error && (
          <QueryError
            error={metadata.error}
            onRetry={() => void metadata.refetch()}
          />
        )}
        {metadata.data && (
          <>
            <dl className="grid gap-3 sm:grid-cols-3">
              <div>
                <dt className="text-xs text-muted">Indexed chunks</dt>
                <dd className="mt-1 text-sm text-foreground">
                  {metadata.data.indexed_chunk_count ?? "Not indexed"}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-muted">Embedding model</dt>
                <dd className="mt-1 break-all text-sm text-foreground">
                  {metadata.data.embedding_model ?? "Not indexed"}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-muted">Dimensions</dt>
                <dd className="mt-1 text-sm text-foreground">
                  {metadata.data.embedding_dimensions ?? "—"}
                </dd>
              </div>
            </dl>
            {metadata.data.preview_markdown && (
              <div className="rounded-lg border border-border bg-input p-4">
                <SafeMarkdown>{metadata.data.preview_markdown}</SafeMarkdown>
              </div>
            )}
          </>
        )}
      </div>
    </details>
  );
}
