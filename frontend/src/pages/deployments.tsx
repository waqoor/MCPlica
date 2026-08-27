import { useQuery } from "@tanstack/react-query";
import { Rocket, Search } from "lucide-react";
import { useDeferredValue, useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { projectApi } from "@/api/projects";
import { PageHeader } from "@/components/page-header";
import { QueryError, QueryPending } from "@/components/query-state";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";

export function DeploymentsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const search = searchParams.get("search") ?? "";
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
          `${project.name} ${project.slug} ${project.mcp_hostname}`
            .toLowerCase()
            .includes(deferredSearch),
      ) ?? [],
    [deferredSearch, projects.data],
  );

  return (
    <div className="space-y-7">
      <PageHeader
        description="Choose a project to inspect its endpoint, health, immutable build reference, access mode, history, and lifecycle controls."
        eyebrow="Serving plane"
        title="Deployments"
      />

      <div className="relative max-w-xl">
        <label className="sr-only" htmlFor="deployment-project-search">
          Search deployment projects
        </label>
        <Search
          aria-hidden="true"
          className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted"
        />
        <Input
          className="pl-10"
          id="deployment-project-search"
          onChange={(event) => {
            const next = new URLSearchParams(searchParams);
            if (event.target.value) next.set("search", event.target.value);
            else next.delete("search");
            setSearchParams(next, { replace: true });
          }}
          placeholder="Search by project, slug, or hostname"
          type="search"
          value={search}
        />
      </div>

      {projects.isPending && (
        <QueryPending label="Loading deployment projects" />
      )}
      {projects.error && (
        <QueryError
          error={projects.error}
          onRetry={() => void projects.refetch()}
        />
      )}
      {projects.data && projects.data.length === 0 && (
        <EmptyState
          description="Create a project, complete a READY build, and configure MCP access before deploying."
          icon={Rocket}
          title="No deployment projects yet"
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
          aria-label="Deployment project list"
          className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3"
        >
          {filtered.map((project) => (
            <Link
              className="group rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
              key={project.id}
              to={`/projects/${project.id}/deployment`}
            >
              <Card className="h-full transition-colors duration-200 group-hover:border-border-strong group-hover:bg-panel-raised">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <h2 className="truncate text-base font-semibold text-foreground">
                      {project.name}
                    </h2>
                    <p className="mt-1 truncate font-mono text-xs text-accent">
                      {project.mcp_hostname}
                    </p>
                  </div>
                  <Badge
                    tone={project.active_deployment_id ? "success" : "neutral"}
                  >
                    {project.active_deployment_id ? "Active" : "Not deployed"}
                  </Badge>
                </div>
                <p className="mt-5 border-t border-border pt-4 text-sm font-medium text-foreground transition group-hover:text-accent">
                  Manage deployment →
                </p>
              </Card>
            </Link>
          ))}
        </section>
      )}
    </div>
  );
}
