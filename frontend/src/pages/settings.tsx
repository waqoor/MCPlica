import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, ExternalLink, Save, ServerCog, Users } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { SystemSettings } from "@/api/contracts";
import { settingsApi } from "@/api/settings";
import { systemApi } from "@/api/system";
import { useAuth } from "@/auth/use-auth";
import { PageHeader } from "@/components/page-header";
import { QueryError, QueryPending } from "@/components/query-state";
import { HealthBadge } from "@/components/status-badge";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { FieldHelp, Label } from "@/components/ui/label";

export function SettingsPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const settings = useQuery({
    queryKey: ["settings"],
    queryFn: ({ signal }) => settingsApi.get(signal),
  });
  const readiness = useQuery({
    queryKey: ["system", "readiness"],
    queryFn: ({ signal }) => systemApi.readiness(signal),
    refetchInterval: 60_000,
  });
  const [form, setForm] = useState<SystemSettings | null>(null);
  useEffect(() => {
    if (settings.data) setForm(settings.data);
  }, [settings.data]);
  const save = useMutation({
    mutationFn: (payload: SystemSettings) => settingsApi.update(payload),
    onSuccess: (value) => {
      queryClient.setQueryData(["settings"], value);
      setForm(value);
    },
  });
  const admin = user?.role === "admin";
  if (settings.isPending)
    return <QueryPending label="Loading installation settings" />;
  if (settings.error)
    return (
      <QueryError
        error={settings.error}
        onRetry={() => void settings.refetch()}
      />
    );
  return (
    <div className="space-y-7">
      <PageHeader
        description="Installation-level build, retention, resource, model, and access controls. PostgreSQL remains authoritative."
        eyebrow="Administration"
        title="Settings"
      />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <SettingsLink
          description="Configure the OpenRouter key, compatible analysis/validation models, embedding model, and documentation processing policy."
          icon={Bot}
          label="Models and OpenRouter"
          to="models"
        />
        <SettingsLink
          description="Create installation users, assign Admin or Builder roles, and disable access without public registration."
          icon={Users}
          label="Users and roles"
          to="users"
          adminOnly
        />
        <Card>
          <CardHeader>
            <CardTitle>Dependency readiness</CardTitle>
            <HealthBadge status={readiness.data?.status} />
          </CardHeader>
          <div className="space-y-2">
            {readiness.data?.checks.map((check) => (
              <div
                className="flex justify-between gap-3 text-sm"
                key={check.name}
              >
                <span className="capitalize text-muted">{check.name}</span>
                <HealthBadge status={check.status} />
              </div>
            )) ?? <p className="text-sm text-muted">Checking…</p>}
          </div>
        </Card>
      </div>
      {!admin && (
        <Alert tone="info">
          Builder access can inspect non-secret installation settings. Only
          administrators can change them.
        </Alert>
      )}
      {form && (
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Operational limits</CardTitle>
              <p className="mt-1 text-xs text-muted">
                Bounds protect memory, queue capacity, external context, and
                host resources.
              </p>
            </div>
            <ServerCog aria-hidden="true" className="size-5 text-accent" />
          </CardHeader>
          <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
            <SettingField
              disabled={!admin}
              label="MCP base domain"
              name="mcp_base_domain"
              onChange={(value) => setForm({ ...form, mcp_base_domain: value })}
              value={form.mcp_base_domain}
            />
            <SettingField
              disabled={!admin}
              label="Build concurrency"
              name="build_concurrency"
              number
              onChange={(value) =>
                setForm({ ...form, build_concurrency: Number(value) })
              }
              value={String(form.build_concurrency)}
            />
            <SettingField
              disabled={!admin}
              label="Maximum upload bytes"
              name="max_upload_bytes"
              number
              onChange={(value) =>
                setForm({ ...form, max_upload_bytes: Number(value) })
              }
              value={String(form.max_upload_bytes)}
            />
            <SettingField
              disabled={!admin}
              label="Maximum operations/project"
              name="max_operations_per_project"
              number
              onChange={(value) =>
                setForm({ ...form, max_operations_per_project: Number(value) })
              }
              value={String(form.max_operations_per_project)}
            />
            <SettingField
              disabled={!admin}
              label="Maximum document chunks/project"
              name="max_document_chunks_per_project"
              number
              onChange={(value) =>
                setForm({
                  ...form,
                  max_document_chunks_per_project: Number(value),
                })
              }
              value={String(form.max_document_chunks_per_project)}
            />
            <SettingField
              disabled={!admin}
              label="Build retention count"
              name="build_retention_count"
              number
              onChange={(value) =>
                setForm({
                  ...form,
                  build_retention_count: value ? Number(value) : null,
                })
              }
              value={String(form.build_retention_count ?? "")}
            />
          </div>
          <div className="mt-5 flex min-h-11 items-center gap-3 rounded-md border border-border bg-input px-3 text-sm text-foreground">
            <input
              checked={form.builders_can_deploy}
              disabled={!admin}
              id="builders-can-deploy"
              onChange={(event) =>
                setForm({ ...form, builders_can_deploy: event.target.checked })
              }
              type="checkbox"
            />
            <Label className="cursor-pointer" htmlFor="builders-can-deploy">
              <span className="font-medium">Builders may deploy</span>
              <span className="block text-xs text-muted">
                When off, deployment controls fail closed for Builder roles.
              </span>
            </Label>
          </div>
          {save.error && (
            <Alert className="mt-5" tone="danger">
              {save.error.message}
            </Alert>
          )}
          {save.isSuccess && (
            <Alert className="mt-5" tone="success">
              Installation settings saved.
            </Alert>
          )}
          {admin && (
            <Button
              className="mt-5"
              disabled={save.isPending}
              onClick={() => save.mutate(form)}
            >
              <Save aria-hidden="true" className="size-4" />
              Save operational settings
            </Button>
          )}
        </Card>
      )}
      <Alert title="No telemetry by default" tone="info">
        This installation does not transmit product analytics to the MCPlica
        project maintainer. OpenRouter receives only configured, bounded build
        context and never credentials.
      </Alert>
    </div>
  );
}

function SettingsLink({
  label,
  description,
  icon: Icon,
  to,
  adminOnly = false,
}: {
  label: string;
  description: string;
  icon: typeof Bot;
  to: string;
  adminOnly?: boolean;
}) {
  return (
    <Link
      className="group rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
      to={to}
    >
      <Card className="h-full transition group-hover:border-border-strong group-hover:bg-panel-raised">
        <div className="flex items-start justify-between">
          <Icon aria-hidden="true" className="size-5 text-accent" />
          <ExternalLink aria-hidden="true" className="size-4 text-muted" />
        </div>
        <h2 className="mt-5 font-semibold text-foreground">{label}</h2>
        <p className="mt-2 text-sm leading-6 text-muted">{description}</p>
        {adminOnly && (
          <p className="mt-3 font-mono text-[0.62rem] uppercase tracking-[0.1em] text-warning-soft">
            Admin only
          </p>
        )}
      </Card>
    </Link>
  );
}
function SettingField({
  label,
  name,
  value,
  onChange,
  disabled,
  number = false,
}: {
  label: string;
  name: string;
  value: string;
  onChange: (value: string) => void;
  disabled: boolean;
  number?: boolean;
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={name}>{label}</Label>
      <Input
        disabled={disabled}
        id={name}
        min={number ? 1 : undefined}
        onChange={(event) => onChange(event.target.value)}
        type={number ? "number" : "text"}
        value={value}
      />
      <FieldHelp>Environment: installation configuration</FieldHelp>
    </div>
  );
}
