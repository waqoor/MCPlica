import { useMutation, useQueries, useQueryClient } from "@tanstack/react-query";
import { Save } from "lucide-react";
import { useState } from "react";
import type { ModelSettings } from "@/api/contracts";
import { settingsApi } from "@/api/settings";
import { PageHeader } from "@/components/page-header";
import { ErrorNotice, MutationError } from "@/components/error-notice";
import { QueryError, QueryPending } from "@/components/query-state";
import { SettingsNavigation } from "@/components/settings-navigation";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { UnsavedChangesGuard } from "@/components/unsaved-changes-guard";

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
  const [draft, setDraft] = useState<{
    source: ModelSettings;
    value: ModelSettings;
  } | null>(null);
  const form =
    settings.data && draft?.source === settings.data
      ? draft.value
      : (settings.data ?? null);
  const setForm = (value: ModelSettings) => {
    if (settings.data) setDraft({ source: settings.data, value });
  };
  const save = useMutation({
    mutationFn: (value: ModelSettings) => settingsApi.updateModels(value),
    onSuccess: (value) => {
      queryClient.setQueryData(["settings", "models"], value);
      setDraft(null);
    },
  });
  if (settings.isPending)
    return <QueryPending label="Loading model configuration" />;
  if (settings.error)
    return (
      <QueryError
        error={settings.error}
        onRetry={() => void settings.refetch()}
      />
    );
  if (!form) return null;
  const structuredModels = (catalog.data ?? []).filter(
    (model) => model.supports_structured_outputs,
  );
  const embeddingModels = (catalog.data ?? []).filter(
    (model) => model.supports_embeddings,
  );
  const dirty = Boolean(
    settings.data && JSON.stringify(form) !== JSON.stringify(settings.data),
  );
  return (
    <div className="space-y-7">
      <UnsavedChangesGuard active={dirty && !save.isPending} />
      <PageHeader
        description="Choose compatible OpenRouter models for build-time analysis, semantic review, and documentation embeddings."
        eyebrow="Settings"
        title="Models"
      />
      <SettingsNavigation canManageInstallation />
      <Alert title="External processing boundary" tone="warning">
        When documentation analysis is enabled, bounded relevant project context
        is sent to the selected OpenRouter model. Credentials and secret fields
        are always excluded.
      </Alert>
      <Card className="max-w-5xl">
        <CardHeader>
          <div>
            <CardTitle>Model policy</CardTitle>
            <p className="mt-1 text-xs text-muted">
              Only compatible models from the provider catalog are selectable.
            </p>
          </div>
        </CardHeader>
        <div className="space-y-4">
          {catalog.isPending && (
            <QueryPending label="Loading compatible model catalog" />
          )}
          {catalog.error && (
            <ErrorNotice
              error={catalog.error}
              nextStep="Saved provider status and manual model identifiers remain editable below."
              onRetry={() => void catalog.refetch()}
              title="Compatible model catalog could not be loaded"
            />
          )}
          <ModelSelect
            catalogAvailable={Boolean(catalog.data)}
            label="Analysis model"
            id="analysis-model"
            value={form.analysis_model ?? ""}
            models={structuredModels}
            onChange={(value) =>
              setForm({ ...form, analysis_model: value || null })
            }
          />
          <ModelSelect
            catalogAvailable={Boolean(catalog.data)}
            label="Semantic validation model"
            id="validation-model"
            value={form.validation_model ?? ""}
            models={structuredModels}
            onChange={(value) =>
              setForm({ ...form, validation_model: value || null })
            }
          />
          <ModelSelect
            catalogAvailable={Boolean(catalog.data)}
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
          disabled={
            save.isPending ||
            JSON.stringify(form) === JSON.stringify(settings.data)
          }
          onClick={() => save.mutate(form)}
        >
          <Save aria-hidden="true" className="size-4" />
          Save model policy
        </Button>
        {save.error && <MutationError error={save.error} />}
        {save.isSuccess && (
          <Alert className="mt-4" tone="success">
            Model policy saved.
          </Alert>
        )}
      </Card>
    </div>
  );
}

function ModelSelect({
  label,
  id,
  value,
  models,
  onChange,
  catalogAvailable,
}: {
  label: string;
  id: string;
  value: string;
  models: Array<{ id: string; name: string }>;
  onChange: (value: string) => void;
  catalogAvailable: boolean;
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      {catalogAvailable ? (
        <Select
          id={id}
          onChange={(event) => onChange(event.target.value)}
          value={value}
        >
          <option value="">Select a compatible model</option>
          {value && !models.some((model) => model.id === value) && (
            <option value={value}>Current: {value}</option>
          )}
          {models.map((model) => (
            <option key={model.id} value={model.id}>
              {model.name} · {model.id}
            </option>
          ))}
        </Select>
      ) : (
        <Input
          id={id}
          onChange={(event) => onChange(event.target.value)}
          placeholder="Provider model identifier"
          value={value}
        />
      )}
    </div>
  );
}
