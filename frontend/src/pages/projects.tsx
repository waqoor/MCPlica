import { useQuery } from "@tanstack/react-query";
import { Boxes, Plus, Search } from "lucide-react";
import { useDeferredValue, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { projectApi } from "@/api/projects";
import { PageHeader } from "@/components/page-header";
import { QueryError, QueryPending } from "@/components/query-state";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button-variants";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { formatDate } from "@/lib/format";

export function ProjectsPage() {
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search.trim().toLowerCase());
  const projects = useQuery({
    queryKey: ["projects"],
    queryFn: ({ signal }) => projectApi.list(signal),
  });
  const filtered = useMemo(
    () =>
      projects.data?.filter(
        (project) =>
          !deferredSearch ||
          `${project.name} ${project.slug} ${project.description ?? ""}`
            .toLowerCase()
            .includes(deferredSearch),
      ) ?? [],
    [deferredSearch, projects.data],
  );

  return (
    <div className="space-y-7">
      <PageHeader
        actions={
          <Link className={buttonVariants()} to="/projects/new">
            <Plus aria-hidden="true" className="size-4" />
            New project
          </Link>
        }
        description="Each project owns one API source set, immutable builds, credentials, hostname, and isolated MCP runtime lifecycle."
        eyebrow="Workspace"
        title="Projects"
      />

      <div className="relative max-w-xl">
        <label className="sr-only" htmlFor="project-search">
          Search projects
        </label>
        <Search
          aria-hidden="true"
          className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted"
        />
        <Input
          id="project-search"
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search by name, slug, or description"
          type="search"
          value={search}
          className="pl-10"
        />
      </div>

      {projects.isPending && <QueryPending label="Loading projects" />}
      {projects.error && (
        <QueryError
          error={projects.error}
          onRetry={() => void projects.refetch()}
        />
      )}
      {projects.data && projects.data.length === 0 && (
        <EmptyState
          action={
            <Link className={buttonVariants()} to="/projects/new">
              Create project
            </Link>
          }
          description="An executable OpenAPI or API Inventory source is required before a project can build."
          icon={Boxes}
          title="No projects yet"
        />
      )}
      {projects.data && projects.data.length > 0 && filtered.length === 0 && (
        <EmptyState
          description="Clear or change the search to see other projects."
          icon={Search}
          title="No matching projects"
        />
      )}

      {filtered.length > 0 && (
        <section
          aria-label="Project list"
          className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3"
        >
          {filtered.map((project) => (
            <Link
              className="group rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
              key={project.id}
              to={`/projects/${project.id}`}
            >
              <Card className="h-full transition-colors duration-200 group-hover:border-border-strong group-hover:bg-panel-raised">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <h2 className="truncate text-base font-semibold text-foreground">
                      {project.name}
                    </h2>
                    <p className="mt-1 truncate font-mono text-xs text-accent">
                      {project.mcp_hostname ?? `${project.slug}.mcp`}
                    </p>
                  </div>
                  <Badge tone={project.is_enabled ? "success" : "neutral"}>
                    {project.is_enabled ? "Enabled" : "Disabled"}
                  </Badge>
                </div>
                <p className="mt-4 line-clamp-2 min-h-10 text-sm leading-5 text-muted">
                  {project.description ||
                    "No project description has been added."}
                </p>
                <div className="mt-5 flex items-center justify-between border-t border-border pt-4 text-xs text-muted">
                  <span>
                    Updated{" "}
                    {formatDate(project.updated_at, { dateStyle: "medium" })}
                  </span>
                  <span className="font-medium text-foreground transition group-hover:text-accent">
                    Open project →
                  </span>
                </div>
              </Card>
            </Link>
          ))}
        </section>
      )}
    </div>
  );
}
