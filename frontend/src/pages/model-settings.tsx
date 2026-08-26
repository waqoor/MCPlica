import { useMutation, useQueries, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Save, Send, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import type { ModelSettings } from "@/api/contracts";
import { settingsApi } from "@/api/settings";
import { PageHeader } from "@/components/page-header";
import { QueryError, QueryPending } from "@/components/query-state";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { FieldHelp, Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

export function ModelSettingsPage() {
  const queryClient = useQueryClient();
  const [settings, catalog] = useQueries({
    queries: [
      {
        queryKey: ["settings", "models"],
        queryFn: ({ signal }: { signal: AbortSignal }) =>
          settingsApi.models(signal),
      },
      {
        queryKey: ["settings", "models", "catalog"],
        queryFn: ({ signal }: { signal: AbortSignal }) =>
          settingsApi.modelCatalog(signal),
      },
    ],
  });
  const [form, setForm] = useState<ModelSettings | null>(null);
  const [apiKey, setApiKey] = useState("");
  useEffect(() => {
    if (settings.data) setForm(settings.data);
  }, [settings.data]);
  const save = useMutation({
    mutationFn: (value: ModelSettings) => settingsApi.updateModels(value),
    onSuccess: (value) => {
      queryClient.setQueryData(["settings", "models"], value);
      setForm(value);
    },
  });
  const rotateKey = useMutation({
    mutationFn: () => settingsApi.updateOpenRouter(apiKey),
    onSuccess: (value) => {
      setApiKey("");
      queryClient.setQueryData(["settings", "models"], value);
    },
  });
  const test = useMutation({ mutationFn: settingsApi.testOpenRouter });
  if (settings.isPending || catalog.isPending)
    return <QueryPending label="Loading model configuration" />;
  if (settings.error)
    return (
      <QueryError
        error={settings.error}
        onRetry={() => void settings.refetch()}
      />
    );
  if (catalog.error)
    return (
      <QueryError
        error={catalog.error}
        onRetry={() => void catalog.refetch()}
        title="Compatible model catalog could not be loaded"
      />
    );
  if (!form) return null;
  const structuredModels = catalog.data.filter(
    (model) => model.supports_structured_outputs,
  );
  const embeddingModels = catalog.data.filter(
    (model) => model.supports_embeddings,
  );
  return (
    <div className="space-y-7">
      <PageHeader
        description="OpenRouter is build-time intelligence only. These settings never enter a generated MCP runtime."
        eyebrow="Settings"
        title="Models and OpenRouter"
      />
      <Alert title="External processing boundary" tone="warning">
        When documentation analysis is enabled, bounded relevant project context
        is sent to the selected OpenRouter model. Credentials and secret fields
        are always excluded.
      </Alert>
      <div className="grid gap-5 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <div>
              <CardTitle>OpenRouter secret</CardTitle>
              <p className="mt-1 text-xs text-muted">
                The existing key is never redisplayed. Saving rotates the
                encrypted value.
              </p>
            </div>
            <KeyRound aria-hidden="true" className="size-5 text-warning" />
          </CardHeader>
          <div className="space-y-2">
            <Label htmlFor="openrouter-key">New API key</Label>
            <Input
              autoComplete="new-password"
              id="openrouter-key"
              onChange={(event) => setApiKey(event.target.value)}
              placeholder={
                form.openrouter_configured
                  ? "Configured — enter only to rotate"
                  : "Enter an OpenRouter key"
              }
              type="password"
              value={apiKey}
            />
            <FieldHelp>
              Status:{" "}
              {form.openrouter_configured ? "configured" : "not configured"}
            </FieldHelp>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button
              disabled={!apiKey || rotateKey.isPending}
              onClick={() => rotateKey.mutate()}
            >
              <ShieldCheck aria-hidden="true" className="size-4" />
              {rotateKey.isPending ? "Saving…" : "Save key"}
            </Button>
            <Button
              disabled={!form.openrouter_configured || test.isPending}
              onClick={() => test.mutate()}
              variant="outline"
            >
              <Send aria-hidden="true" className="size-4" />
              Test capabilities
            </Button>
          </div>
          {(rotateKey.error || test.error) && (
            <Alert className="mt-4" tone="danger">
              {rotateKey.error?.message ?? test.error?.message}
            </Alert>
          )}
          {test.data && (
            <Alert className="mt-4" tone={test.data.ok ? "success" : "warning"}>
              {test.data.message}
            </Alert>
          )}
        </Card>
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Model policy</CardTitle>
              <p className="mt-1 text-xs text-muted">
                Only compatible models from the provider catalog are selectable.
              </p>
            </div>
          </CardHeader>
          <div className="space-y-4">
            <ModelSelect
              label="Analysis model"
              id="analysis-model"
              value={form.analysis_model ?? ""}
              models={structuredModels}
              onChange={(value) =>
                setForm({ ...form, analysis_model: value || null })
              }
            />
            <ModelSelect
              label="Semantic validation model"
              id="validation-model"
              value={form.validation_model ?? ""}
              models={structuredModels}
              onChange={(value) =>
                setForm({ ...form, validation_model: value || null })
              }
            />
            <ModelSelect
              label="Embedding model"
              id="embedding-model"
              value={form.embedding_model ?? ""}
              models={embeddingModels}
              onChange={(value) =>
                setForm({ ...form, embedding_model: value || null })
              }
            />
            <div className="flex min-h-11 items-center gap-3 rounded-md border border-border bg-input px-3 text-sm">
              <input
                checked={form.include_documentation_in_analysis}
                id="include-documentation-analysis"
                onChange={(event) =>
                  setForm({
                    ...form,
                    include_documentation_in_analysis: event.target.checked,
                  })
                }
                type="checkbox"
              />
              <Label
                className="cursor-pointer"
                htmlFor="include-documentation-analysis"
              >
                <span className="font-medium text-foreground">
                  Include documentation in analysis
                </span>
                <span className="block text-xs text-muted">
                  Explicitly controls external document context processing.
                </span>
              </Label>
            </div>
          </div>
          <Button
            className="mt-5"
            disabled={save.isPending}
            onClick={() => save.mutate(form)}
          >
            <Save aria-hidden="true" className="size-4" />
            Save model policy
          </Button>
          {save.error && (
            <Alert className="mt-4" tone="danger">
              {save.error.message}
            </Alert>
          )}
          {save.isSuccess && (
            <Alert className="mt-4" tone="success">
              Model policy saved.
            </Alert>
          )}
        </Card>
      </div>
    </div>
  );
}

function ModelSelect({
  label,
  id,
  value,
  models,
  onChange,
}: {
  label: string;
  id: string;
  value: string;
  models: Array<{ id: string; name: string }>;
  onChange: (value: string) => void;
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      <Select
        id={id}
        onChange={(event) => onChange(event.target.value)}
        value={value}
      >
        <option value="">Select a compatible model</option>
        {models.map((model) => (
          <option key={model.id} value={model.id}>
            {model.name} · {model.id}
          </option>
        ))}
      </Select>
    </div>
  );
}
