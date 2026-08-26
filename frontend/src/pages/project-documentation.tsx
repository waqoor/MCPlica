import { useQuery } from "@tanstack/react-query";
import { BookOpen, FileText } from "lucide-react";
import { Link } from "react-router-dom";
import { sourceApi } from "@/api/sources";
import { QueryError, QueryPending } from "@/components/query-state";
import { SafeMarkdown } from "@/components/safe-markdown";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button-variants";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { useProject } from "@/features/projects/project-context";
import { formatDate } from "@/lib/format";

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
        description="Markdown, text, sanitized HTML, and text-extractable PDFs can enrich tool semantics but never define executable behavior."
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
                <Badge
                  tone={
                    source.latest_version?.parse_status === "invalid"
                      ? "danger"
                      : "info"
                  }
                >
                  {source.latest_version?.parse_status ?? "registered"}
                </Badge>
                <Badge
                  tone={
                    source.latest_version?.index_status === "failed"
                      ? "danger"
                      : source.latest_version?.index_status === "ready"
                        ? "success"
                        : "warning"
                  }
                >
                  {source.latest_version?.index_status ?? "not indexed"}
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
                {source.latest_version?.indexed_chunk_count ?? "Pending index"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted">Embedding model</dt>
              <dd className="mt-1 break-all text-sm text-foreground">
                {source.latest_version?.embedding_model ?? "Not indexed"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted">Dimensions</dt>
              <dd className="mt-1 text-sm text-foreground">
                {source.latest_version?.embedding_dimensions ?? "—"}
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
          {source.latest_version?.preview_markdown && (
            <details className="mt-5 border-t border-border pt-4">
              <summary className="cursor-pointer text-sm font-medium text-accent">
                View sanitized extracted preview
              </summary>
              <div className="mt-4 rounded-lg border border-border bg-input p-4">
                <SafeMarkdown>
                  {source.latest_version.preview_markdown}
                </SafeMarkdown>
              </div>
            </details>
          )}
        </Card>
      ))}
    </div>
  );
}
