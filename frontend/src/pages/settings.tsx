import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, Cloud, ExternalLink, Save, ServerCog, Users } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { buildApi } from "@/api/builds";
import type { SystemSettings } from "@/api/contracts";
import { settingsApi } from "@/api/settings";
import { systemApi } from "@/api/system";
import { useCapabilities } from "@/auth/capabilities";
import { PageHeader } from "@/components/page-header";
import { ErrorNotice, MutationError } from "@/components/error-notice";
import { QueryError, QueryPending } from "@/components/query-state";
import { SettingsNavigation } from "@/components/settings-navigation";
import { HealthBadge } from "@/components/status-badge";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { UnsavedChangesGuard } from "@/components/unsaved-changes-guard";
import { FieldHelp, Label } from "@/components/ui/label";
import {
  operationalSettingsSchema,
  OPERATIONAL_SETTING_BOUNDS,
} from "@/lib/settings-form";

export function SettingsPage() {
  const capabilities = useCapabilities();
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
  const admission = useQuery({
    queryKey: ["build-admission"],
    queryFn: ({ signal }) => buildApi.admission(signal),
    refetchInterval: (query) =>
      query.state.data?.waiting_count ? 2_000 : false,
  });
  const [draft, setDraft] = useState<{
    source: SystemSettings;
    value: SystemSettings;
  } | null>(null);
  const form =
    settings.data && draft?.source === settings.data
      ? draft.value
      : (settings.data ?? null);
  const setForm = (value: SystemSettings) => {
    if (settings.data) setDraft({ source: settings.data, value });
  };
  const save = useMutation({
    mutationFn: (payload: SystemSettings) => settingsApi.update(payload),
    onSuccess: (value) => {
      queryClient.setQueryData(["settings"], value);
      setDraft(null);
    },
  });
  const admin = capabilities.canManageInstallation;
  const validation = form ? operationalSettingsSchema.safeParse(form) : null;
  const dirty = Boolean(
    form &&
    settings.data &&
    JSON.stringify(form) !== JSON.stringify(settings.data),
  );
  const fieldError = (name: keyof SystemSettings) =>
    validation && !validation.success
      ? validation.error.issues.find((issue) => issue.path[0] === name)?.message
      : undefined;
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
      <UnsavedChangesGuard active={dirty && !save.isPending} />
      <PageHeader
        description="Installation-level provider, model, access, retention, and resource controls. PostgreSQL remains authoritative."
        eyebrow="Administration"
        title="Settings"
      />
      <SettingsNavigation canManageInstallation={admin} />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <SettingsLink
          adminOnly
          authorized={admin}
          description="Connect the public OpenRouter service, securely save or rotate its API key, and test live reachability."
          icon={Cloud}
          label="Providers"
          to="providers"
        />
        <SettingsLink
          adminOnly
          authorized={admin}
          description="Select compatible analysis, validation, and embedding models from the live provider catalog."
          icon={Bot}
          label="Models"
          to="models"
        />
        <SettingsLink
          authorized={admin}
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
      {readiness.error && (
        <ErrorNotice
          error={readiness.error}
          onRetry={() => void readiness.refetch()}
          title="Dependency readiness is unavailable"
        />
      )}
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
              error={fieldError("mcp_base_domain")}
              onChange={(value) => setForm({ ...form, mcp_base_domain: value })}
              value={form.mcp_base_domain}
            />
            <SettingField
              disabled={!admin}
              label="Build concurrency"
              name="build_concurrency"
              error={fieldError("build_concurrency")}
              max={OPERATIONAL_SETTING_BOUNDS.build_concurrency.max}
              min={OPERATIONAL_SETTING_BOUNDS.build_concurrency.min}
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
              error={fieldError("max_upload_bytes")}
              max={OPERATIONAL_SETTING_BOUNDS.max_upload_bytes.max}
              min={OPERATIONAL_SETTING_BOUNDS.max_upload_bytes.min}
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
              error={fieldError("max_operations_per_project")}
              max={OPERATIONAL_SETTING_BOUNDS.max_operations_per_project.max}
              min={OPERATIONAL_SETTING_BOUNDS.max_operations_per_project.min}
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
              error={fieldError("max_document_chunks_per_project")}
              max={
                OPERATIONAL_SETTING_BOUNDS.max_document_chunks_per_project.max
              }
              min={
                OPERATIONAL_SETTING_BOUNDS.max_document_chunks_per_project.min
              }
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
              error={fieldError("build_retention_count")}
              max={OPERATIONAL_SETTING_BOUNDS.build_retention_count.max}
              min={OPERATIONAL_SETTING_BOUNDS.build_retention_count.min}
              number
              onChange={(value) =>
                setForm({
                  ...form,
                  build_retention_count: value ? Number(value) : null,
                })
              }
              value={String(form.build_retention_count ?? "")}
            />
            <SettingField
              disabled={!admin}
              label="Source version retention days"
              name="source_retention_days"
              error={fieldError("source_retention_days")}
              max={OPERATIONAL_SETTING_BOUNDS.source_retention_days.max}
              min={OPERATIONAL_SETTING_BOUNDS.source_retention_days.min}
              number
              onChange={(value) =>
                setForm({
                  ...form,
                  source_retention_days: value ? Number(value) : null,
                })
              }
              value={String(form.source_retention_days ?? "")}
            />
          </div>
          <div
            aria-live="polite"
            className="mt-5 grid gap-3 rounded-md border border-border bg-input px-4 py-3 text-sm sm:grid-cols-3"
          >
            <div>
              <span className="block text-xs text-muted">Configured limit</span>
              <strong>
                {admission.data?.configured_concurrency ?? "Unknown"}
              </strong>
            </div>
            <div>
              <span className="block text-xs text-muted">
                Effective permits
              </span>
              <strong>
                {admission.data?.effective_concurrency ?? "Unknown"}
              </strong>
            </div>
            <div>
              <span className="block text-xs text-muted">Waiting builds</span>
              <strong>{admission.data?.waiting_count ?? "Unknown"}</strong>
            </div>
          </div>
          {admission.error && (
            <ErrorNotice
              error={admission.error}
              nextStep="The persisted concurrency limit is unchanged."
              onRetry={() => void admission.refetch()}
              title="Build admission telemetry is unavailable"
            />
          )}
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
          {save.error && <MutationError error={save.error} />}
          {save.isSuccess && (
            <Alert className="mt-5" tone="success">
              Installation settings saved.
            </Alert>
          )}
          {admin && (
            <Button
              className="mt-5"
              disabled={save.isPending || !dirty || !validation?.success}
              onClick={() => {
                if (validation?.success) save.mutate(validation.data);
              }}
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
  authorized = true,
  adminOnly = false,
}: {
  label: string;
  description: string;
  icon: typeof Bot;
  to: string;
  authorized?: boolean;
  adminOnly?: boolean;
}) {
  const content = (
    <>
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
    </>
  );
  if (!authorized) {
    return (
      <div aria-disabled="true" className="cursor-not-allowed opacity-80">
        {content}
      </div>
    );
  }
  return (
    <Link
      className="group rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
      to={to}
    >
      {content}
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
  min,
  max,
  error,
}: {
  label: string;
  name: string;
  value: string;
  onChange: (value: string) => void;
  disabled: boolean;
  number?: boolean;
  min?: number;
  max?: number;
  error?: string;
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={name}>{label}</Label>
      <Input
        disabled={disabled}
        id={name}
        aria-invalid={Boolean(error)}
        max={number ? max : undefined}
        min={number ? min : undefined}
        onChange={(event) => onChange(event.target.value)}
        type={number ? "number" : "text"}
        value={value}
      />
      <FieldHelp>
        {error ??
          (number && min !== undefined && max !== undefined
            ? `Allowed range: ${min.toLocaleString()}–${max.toLocaleString()}`
            : "Environment: installation configuration")}
      </FieldHelp>
    </div>
  );
}
