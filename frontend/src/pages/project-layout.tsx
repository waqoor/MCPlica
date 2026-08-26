import { useQuery } from "@tanstack/react-query";
import { Link, Outlet, useParams } from "react-router-dom";
import { projectApi } from "@/api/projects";
import { ProjectNav } from "@/components/project-nav";
import { QueryError, QueryPending } from "@/components/query-state";
import { Badge } from "@/components/ui/badge";
import { ProjectContext } from "@/features/projects/project-context";

export function ProjectLayout() {
  const { projectId } = useParams<{ projectId: string }>();
  const project = useQuery({
    queryKey: ["projects", projectId],
    queryFn: ({ signal }) => projectApi.get(projectId!, signal),
    enabled: Boolean(projectId),
  });

  if (project.isPending) return <QueryPending label="Loading project" />;
  if (project.error)
    return (
      <QueryError
        error={project.error}
        onRetry={() => void project.refetch()}
        title="Project could not be loaded"
      />
    );

  return (
    <ProjectContext.Provider value={project.data}>
      <div className="space-y-6">
        <header>
          <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-muted">
            <Link className="hover:text-foreground" to="/projects">
              Projects
            </Link>
            <span aria-hidden="true">/</span>
            <span>{project.data.name}</span>
            <Badge
              className="ml-1"
              tone={project.data.is_enabled ? "success" : "neutral"}
            >
              {project.data.is_enabled ? "Enabled" : "Disabled"}
            </Badge>
          </div>
          <div className="mb-5 flex flex-col justify-between gap-2 sm:flex-row sm:items-end">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-foreground">
                {project.data.name}
              </h1>
              <p className="mt-1 font-mono text-xs text-muted">
                {project.data.mcp_hostname ?? `${project.data.slug}.mcp`}
              </p>
            </div>
            {project.data.description && (
              <p className="max-w-xl text-sm leading-6 text-muted">
                {project.data.description}
              </p>
            )}
          </div>
          <ProjectNav />
        </header>
        <Outlet />
      </div>
    </ProjectContext.Provider>
  );
}
