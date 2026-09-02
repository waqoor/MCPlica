import { useMutation, useQueries, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  Cloud,
  ExternalLink,
  KeyRound,
  Radio,
  Save,
  Send,
} from "lucide-react";
import { useState } from "react";
import { settingsApi } from "@/api/settings";
import { systemApi } from "@/api/system";
import { MutationError } from "@/components/error-notice";
import { PageHeader } from "@/components/page-header";
import { QueryError, QueryPending } from "@/components/query-state";
import { SettingsNavigation } from "@/components/settings-navigation";
import { HealthBadge } from "@/components/status-badge";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { buttonVariants } from "@/components/ui/button-variants";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { FieldError, FieldHelp, Label } from "@/components/ui/label";
import { UnsavedChangesGuard } from "@/components/unsaved-changes-guard";
import { cn } from "@/lib/utils";

const OPENROUTER_API_URL = "https://openrouter.ai/api/v1";
const OPENROUTER_SITE_URL = "https://openrouter.ai/";

function validateApiKey(value: string): string | null {
  const normalized = value.trim();
  if (!normalized) return "Enter an OpenRouter API key.";
  if (normalized.length < 10 || normalized.length > 500) {
    return "The API key must contain 10–500 characters.";
  }
  if (
    [...normalized].some(
      (character) =>
        character.charCodeAt(0) < 33 || character.charCodeAt(0) > 126,
    )
  ) {
    return "The API key may contain printable ASCII characters only.";
  }
  return null;
}

export function ProviderSettingsPage() {
  const queryClient = useQueryClient();
  const [apiKey, setApiKey] = useState("");
  const [keyTouched, setKeyTouched] = useState(false);
  const [models, readiness] = useQueries({
    queries: [
      {
        queryKey: ["settings", "models"],
        queryFn: ({ signal }: { signal: AbortSignal }) =>
          settingsApi.models(signal),
      },
      {
        queryKey: ["system", "readiness"],
        queryFn: ({ signal }: { signal: AbortSignal }) =>
          systemApi.readiness(signal),
        refetchInterval: 60_000,
      },
    ],
  });
  const testConnection = useMutation({
    mutationFn: settingsApi.testOpenRouter,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["system", "readiness"] });
    },
  });
  const rotateKey = useMutation({
    mutationFn: (value: string) => settingsApi.updateOpenRouter(value.trim()),
    onSuccess: (value) => {
      setApiKey("");
      setKeyTouched(false);
      testConnection.reset();
      queryClient.setQueryData(["settings", "models"], value);
      void queryClient.invalidateQueries({ queryKey: ["system", "readiness"] });
      void queryClient.invalidateQueries({
        queryKey: ["settings", "models", "catalog"],
      });
    },
  });

  if (models.isPending)
    return <QueryPending label="Loading provider configuration" />;
  if (models.error)
    return (
      <QueryError error={models.error} onRetry={() => void models.refetch()} />
    );

  const keyError = apiKey ? validateApiKey(apiKey) : null;
  const openRouterCheck = readiness.data?.checks.find(
    (check) => check.name === "openrouter",
  );
  const providerStatus = openRouterCheck?.status ?? "unknown";
  const modelsConfigured = Boolean(
    models.data.analysis_model &&
    models.data.validation_model &&
    models.data.embedding_model,
  );
  const buildStatus =
    !models.data.openrouter_configured || !modelsConfigured
      ? "unavailable"
      : providerStatus === "ready"
        ? "ready"
        : providerStatus === "unknown"
          ? "unknown"
          : "degraded";

  return (
    <div className="space-y-7">
      <UnsavedChangesGuard active={Boolean(apiKey)} />
      <PageHeader
        actions={
          <a
            className={cn(buttonVariants({ variant: "outline" }))}
            href={OPENROUTER_SITE_URL}
            rel="noreferrer"
            target="_blank"
          >
            Open OpenRouter
            <ExternalLink aria-hidden="true" className="size-4" />
          </a>
        }
        description="Connect the public OpenRouter service used for build-time analysis, validation, and embeddings. Provider credentials never enter generated MCP runtimes."
        eyebrow="Settings"
        title="Providers"
      />
      <SettingsNavigation canManageInstallation />

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.08fr)_minmax(22rem,0.92fr)]">
        <Card>
          <CardHeader>
            <div>
              <CardTitle>OpenRouter credential</CardTitle>
              <p className="mt-1 max-w-2xl text-xs leading-5 text-muted">
                Saving creates an encrypted installation-level override. The
                existing key is write-only and is never returned to this page.
              </p>
            </div>
            <KeyRound aria-hidden="true" className="size-5 text-warning" />
          </CardHeader>

          <div className="space-y-2">
            <Label htmlFor="openrouter-key">New API key</Label>
            <Input
              aria-describedby={
                keyTouched && keyError
                  ? "openrouter-key-error"
                  : "openrouter-key-help"
              }
              aria-invalid={Boolean(keyTouched && keyError)}
              autoComplete="new-password"
              id="openrouter-key"
              maxLength={500}
              minLength={10}
              onBlur={() => setKeyTouched(true)}
              onChange={(event) => {
                setApiKey(event.target.value);
                rotateKey.reset();
                testConnection.reset();
              }}
              placeholder={
                models.data.openrouter_configured
                  ? "Configured — enter a new key only to rotate"
                  : "Enter your OpenRouter API key"
              }
              spellCheck={false}
              type="password"
              value={apiKey}
            />
            {keyTouched && keyError ? (
              <FieldError id="openrouter-key-error">{keyError}</FieldError>
            ) : (
              <FieldHelp id="openrouter-key-help">
                {models.data.openrouter_configured
                  ? "A key is configured. Its value cannot be viewed or copied back."
                  : "No provider key is configured for this installation."}
              </FieldHelp>
            )}
          </div>

          <div className="mt-5 flex flex-wrap gap-2">
            <Button
              disabled={!apiKey || Boolean(keyError) || rotateKey.isPending}
              onClick={() => {
                setKeyTouched(true);
                if (!keyError) rotateKey.mutate(apiKey);
              }}
            >
              <Save aria-hidden="true" className="size-4" />
              {rotateKey.isPending
                ? "Saving…"
                : models.data.openrouter_configured
                  ? "Rotate API key"
                  : "Save API key"}
            </Button>
            <Button
              disabled={
                !models.data.openrouter_configured ||
                Boolean(apiKey) ||
                testConnection.isPending
              }
              onClick={() => testConnection.mutate()}
              variant="outline"
            >
              <Send aria-hidden="true" className="size-4" />
              {testConnection.isPending ? "Testing…" : "Test connection"}
            </Button>
          </div>

          {rotateKey.error && <MutationError error={rotateKey.error} />}
          {testConnection.error && (
            <MutationError error={testConnection.error} />
          )}
          {rotateKey.isSuccess && (
            <Alert className="mt-4" tone="success">
              OpenRouter API key saved. Test the connection to verify the
              credential and live model catalog.
            </Alert>
          )}
          {testConnection.data && (
            <Alert
              className="mt-4"
              tone={testConnection.data.ok ? "success" : "warning"}
            >
              {testConnection.data.message}
            </Alert>
          )}
        </Card>

        <Card className="overflow-hidden">
          <CardHeader>
            <div>
              <CardTitle>Public provider path</CardTitle>
              <p className="mt-1 text-xs leading-5 text-muted">
                MCPlica calls OpenRouter from the control plane during builds.
              </p>
            </div>
            <Cloud aria-hidden="true" className="size-5 text-accent" />
          </CardHeader>
          <div className="rounded-lg border border-border bg-input p-4">
            <p className="font-mono text-[0.64rem] uppercase tracking-[0.12em] text-muted">
              API base
            </p>
            <code className="mt-2 block break-all font-mono text-xs text-info-soft">
              {OPENROUTER_API_URL}
            </code>
          </div>

          <div aria-live="polite" className="relative mt-5 space-y-1">
            <ProviderStage
              detail="An encrypted key or installation environment key is available."
              icon={KeyRound}
              label="Credential configured"
              status={
                models.data.openrouter_configured ? "ready" : "unavailable"
              }
            />
            <ProviderStage
              detail="The control plane can reach and authenticate with the public model catalog."
              icon={Radio}
              label="Provider reachable"
              status={providerStatus}
            />
            <ProviderStage
              detail={
                modelsConfigured
                  ? "Analysis, validation, and embedding models are selected."
                  : "Select analysis, validation, and embedding models in Model settings."
              }
              icon={CheckCircle2}
              label="Ready for builds"
              last
              status={buildStatus}
            />
          </div>
          {readiness.error && (
            <Alert className="mt-4" tone="warning">
              Provider readiness could not be refreshed. Use Test connection for
              a direct capability check.
            </Alert>
          )}
        </Card>
      </div>

      <Alert title="External processing boundary" tone="warning">
        OpenRouter receives only bounded build context allowed by the model
        policy. Project credentials, MCP access tokens, and secret fields are
        excluded.
      </Alert>
    </div>
  );
}

function ProviderStage({
  detail,
  icon: Icon,
  label,
  last = false,
  status,
}: {
  detail: string;
  icon: typeof KeyRound;
  label: string;
  last?: boolean;
  status: string;
}) {
  return (
    <div className="relative grid grid-cols-[2.5rem_minmax(0,1fr)_auto] gap-3 pb-4 last:pb-0">
      {!last && (
        <span
          aria-hidden="true"
          className="absolute bottom-0 left-5 top-9 w-px bg-border-strong"
        />
      )}
      <span className="relative z-10 grid size-10 place-items-center rounded-full border border-border-strong bg-panel-raised text-accent">
        <Icon aria-hidden="true" className="size-4" />
      </span>
      <div className="min-w-0 pt-1">
        <p className="text-sm font-semibold text-foreground">{label}</p>
        <p className="mt-1 text-xs leading-5 text-muted">{detail}</p>
      </div>
      <div className="pt-1">
        <HealthBadge status={status} />
      </div>
    </div>
  );
}
