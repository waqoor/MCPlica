import { useQuery } from "@tanstack/react-query";
import { Activity, Search } from "lucide-react";
import { useState } from "react";
import { auditApi } from "@/api/audit";
import type { AuditEvent } from "@/api/contracts";
import { PageHeader } from "@/components/page-header";
import { QueryError, QueryPending } from "@/components/query-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { formatDate, titleCase } from "@/lib/format";

export function ActivityPage() {
  const [eventType, setEventType] = useState("");
  const [projectId, setProjectId] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [page, setPage] = useState(1);
  const filters = {
    event_type: eventType || undefined,
    project_id: projectId || undefined,
    from: from || undefined,
    to: to || undefined,
    page,
    page_size: 50,
  };
  const activity = useQuery({
    queryKey: ["audit", filters],
    queryFn: ({ signal }) => auditApi.list(filters, signal),
  });
  return (
    <div className="space-y-7">
      <PageHeader
        description="Durable control-plane security and lifecycle events. Secret values and raw sensitive payloads are never displayed."
        eyebrow="Audit"
        title="Activity"
      />
      <Card>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
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
                onChange={(event) => {
                  setPage(1);
                  setEventType(event.target.value);
                }}
                placeholder="deployment, source…"
                value={eventType}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="audit-project">Project ID</Label>
            <Input
              id="audit-project"
              onChange={(event) => {
                setPage(1);
                setProjectId(event.target.value);
              }}
              value={projectId}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="audit-from">From</Label>
            <Input
              id="audit-from"
              onChange={(event) => {
                setPage(1);
                setFrom(event.target.value);
              }}
              type="date"
              value={from}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="audit-to">To</Label>
            <Input
              id="audit-to"
              onChange={(event) => {
                setPage(1);
                setTo(event.target.value);
              }}
              type="date"
              value={to}
            />
          </div>
        </div>
      </Card>
      {activity.isPending && <QueryPending label="Loading audit events" />}
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
            <AuditCard event={event} key={event.id} />
          ))}
          <div className="flex items-center justify-between">
            <Button
              disabled={page === 1}
              onClick={() => setPage((value) => value - 1)}
              variant="outline"
            >
              Previous
            </Button>
            <span className="text-xs text-muted">
              Page {activity.data.page} · {activity.data.total} events
            </span>
            <Button
              disabled={page * activity.data.page_size >= activity.data.total}
              onClick={() => setPage((value) => value + 1)}
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
function AuditCard({ event }: { event: AuditEvent }) {
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
            {event.actor_display_name ??
              (event.actor_user_id
                ? `User ${event.actor_user_id.slice(0, 8)}`
                : "System")}{" "}
            ·{" "}
            {event.project_name ??
              (event.project_id
                ? `Project ${event.project_id.slice(0, 8)}`
                : "Installation")}
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
