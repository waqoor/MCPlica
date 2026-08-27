import { useQuery } from "@tanstack/react-query";
import { Activity, Search } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import { auditApi } from "@/api/audit";
import type { AuditEvent } from "@/api/contracts";
import { projectApi } from "@/api/projects";
import { userApi } from "@/api/settings";
import { PageHeader } from "@/components/page-header";
import { QueryError, QueryPending } from "@/components/query-state";
import { Badge } from "@/components/ui/badge";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import {
  auditCalendarRange,
  browserTimeZone,
  isAuditCalendarDate,
} from "@/lib/audit-date-range";
import { formatDate, titleCase } from "@/lib/format";

export function ActivityPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const eventType = searchParams.get("event_type") ?? "";
  const projectId = searchParams.get("project_id") ?? "";
  const actor = searchParams.get("actor") ?? "";
  const from = searchParams.get("from_date") ?? "";
  const to = searchParams.get("to_date") ?? "";
  const rawPage = Number(searchParams.get("page") ?? "1");
  const page = Number.isInteger(rawPage) && rawPage > 0 ? rawPage : 1;
  const rawPageSize = Number(searchParams.get("page_size") ?? "50");
  const pageSize = [25, 50, 100].includes(rawPageSize) ? rawPageSize : 50;
  const range = auditCalendarRange(from, to);
  const invalidCalendarDate =
    !isAuditCalendarDate(from) || !isAuditCalendarDate(to);
  const invalidRange = invalidCalendarDate || Boolean(from && to && from > to);
  const updateSearch = (
    name: string,
    value: string,
    { resetPage = true }: { resetPage?: boolean } = {},
  ) => {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(name, value);
    else next.delete(name);
    if (resetPage) next.delete("page");
    setSearchParams(next, { replace: true });
  };
  const filters = {
    actor: actor || undefined,
    event_type: eventType || undefined,
    project_id: projectId || undefined,
    from: range.from,
    to: range.to,
    page,
    page_size: pageSize,
  };
  const activity = useQuery({
    queryKey: ["audit", filters],
    queryFn: ({ signal }) => auditApi.list(filters, signal),
    enabled: !invalidRange,
  });
  const projects = useQuery({
    queryKey: ["projects"],
    queryFn: ({ signal }) => projectApi.list(signal),
  });
  const users = useQuery({
    queryKey: ["users"],
    queryFn: ({ signal }) => userApi.list(signal),
  });
  const projectNames = new Map(
    projects.data?.map((project) => [project.id, project.name]),
  );
  const actorNames = new Map(
    users.data?.map((user) => [user.id, user.display_name]),
  );
  return (
    <div className="space-y-7">
      <PageHeader
        description="Durable control-plane security and lifecycle events. Secret values and raw sensitive payloads are never displayed."
        eyebrow="Audit"
        title="Activity"
      />
      <Card>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <div className="space-y-2">
            <Label htmlFor="event-type">Event type</Label>
            <div className="relative">
              <Search
                aria-hidden="true"
                className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted"
              />
              <Input
                className="pl-10"
                id="event-type"
                onChange={(event) =>
                  updateSearch("event_type", event.target.value)
                }
                placeholder="deployment, source…"
                value={eventType}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="audit-actor">Actor</Label>
            <Select
              id="audit-actor"
              onChange={(event) => updateSearch("actor", event.target.value)}
              value={actor}
            >
              <option value="">All actors</option>
              {users.data?.map((user) => (
                <option key={user.id} value={user.email}>
                  {user.display_name} · {user.email}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="audit-project">Project</Label>
            <Select
              id="audit-project"
              onChange={(event) =>
                updateSearch("project_id", event.target.value)
              }
              value={projectId}
            >
              <option value="">All projects</option>
              {projects.data?.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="audit-from">From date</Label>
            <Input
              id="audit-from"
              onChange={(event) =>
                updateSearch("from_date", event.target.value)
              }
              type="date"
              value={from}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="audit-to">Through date</Label>
            <Input
              id="audit-to"
              onChange={(event) => updateSearch("to_date", event.target.value)}
              type="date"
              value={to}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="audit-page-size">Events per page</Label>
            <Select
              id="audit-page-size"
              onChange={(event) =>
                updateSearch("page_size", event.target.value)
              }
              value={String(pageSize)}
            >
              {[25, 50, 100].map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </Select>
          </div>
        </div>
        <p className="mt-4 text-xs text-muted">
          Calendar dates use {browserTimeZone()}. The final selected day is
          included in full.
        </p>
      </Card>
      {invalidRange && (
        <Alert title="Invalid date range" tone="danger">
          {invalidCalendarDate
            ? "Use real calendar dates in YYYY-MM-DD format. No unfiltered request was sent."
            : "The from date must not be later than the through date."}
        </Alert>
      )}
      {activity.isPending && !invalidRange && (
        <QueryPending label="Loading audit events" />
      )}
      {activity.error && (
        <QueryError
          error={activity.error}
          onRetry={() => void activity.refetch()}
        />
      )}
      {activity.data && activity.data.items.length === 0 && (
        <EmptyState
          description="No durable events match these filters."
          icon={Activity}
          title="No activity found"
        />
      )}
      {activity.data?.items.length ? (
        <div className="space-y-3">
          {activity.data.items.map((event) => (
            <AuditCard
              actorName={
                event.actor_user_id
                  ? (actorNames.get(event.actor_user_id) ?? "Former user")
                  : "System"
              }
              event={event}
              key={event.id}
              projectName={
                event.project_id
                  ? (projectNames.get(event.project_id) ?? "Deleted project")
                  : "Installation"
              }
            />
          ))}
          <div className="flex items-center justify-between">
            <Button
              disabled={page === 1}
              onClick={() =>
                updateSearch("page", String(page - 1), { resetPage: false })
              }
              variant="outline"
            >
              Previous
            </Button>
            <span className="text-xs text-muted">
              Page {activity.data.page} · {activity.data.total} events
            </span>
            <Button
              disabled={page * activity.data.page_size >= activity.data.total}
              onClick={() =>
                updateSearch("page", String(page + 1), { resetPage: false })
              }
              variant="outline"
            >
              Next
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

const safeMetadataKeys = new Set([
  "status",
  "previous_status",
  "reason_code",
  "source_name",
  "build_sequence",
  "auth_mode",
  "role",
  "changed_fields",
]);
function safeMetadata(
  metadata: Record<string, unknown>,
): Array<[string, string]> {
  return Object.entries(metadata)
    .filter(
      ([key, value]) =>
        safeMetadataKeys.has(key) &&
        ["string", "number", "boolean"].includes(typeof value),
    )
    .map(([key, value]) => [key, String(value)]);
}
function AuditCard({
  event,
  actorName,
  projectName,
}: {
  event: AuditEvent;
  actorName: string;
  projectName: string;
}) {
  const metadata = safeMetadata(event.metadata);
  return (
    <Card className="p-4">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="info">{titleCase(event.event_type)}</Badge>
            <span className="text-xs text-muted">{event.entity_type}</span>
          </div>
          <p className="mt-3 text-sm text-foreground">
            {actorName} · {projectName}
          </p>
          {metadata.length > 0 && (
            <dl className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
              {metadata.map(([key, value]) => (
                <div className="flex gap-1" key={key}>
                  <dt>{titleCase(key)}:</dt>
                  <dd className="text-foreground">{value}</dd>
                </div>
              ))}
            </dl>
          )}
        </div>
        <div className="text-right">
          <p className="text-xs text-muted">{formatDate(event.created_at)}</p>
          {event.request_id && (
            <p className="mt-1 font-mono text-[0.62rem] text-muted">
              {event.request_id}
            </p>
          )}
        </div>
      </div>
    </Card>
  );
}
