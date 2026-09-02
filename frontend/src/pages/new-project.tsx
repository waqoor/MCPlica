import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  FileCode2,
  KeyRound,
  Rocket,
  ShieldCheck,
} from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useForm, useWatch } from "react-hook-form";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { z } from "@/lib/schemas";
import { buildApi } from "@/api/builds";
import type {
  Deployment,
  McpAccessToken,
  Project,
  ProjectJourney,
  SourceKind,
} from "@/api/contracts";
import {
  credentialApi,
  credentialSchemeForSource,
  credentialSecretFor,
} from "@/api/credentials";
import { deploymentApi } from "@/api/deployments";
import { projectApi } from "@/api/projects";
import { sourceApi } from "@/api/sources";
import { useCapabilities } from "@/auth/capabilities";
import { BuildProgress } from "@/components/build-progress";
import { ErrorNotice, MutationError } from "@/components/error-notice";
import { OneTimeSecretDialog } from "@/components/one-time-secret-dialog";
import { UnsavedChangesGuard } from "@/components/unsaved-changes-guard";
import {
  BuildStatusBadge,
  DeploymentStatusBadge,
} from "@/components/status-badge";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { buttonVariants } from "@/components/ui/button-variants";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { FieldError, FieldHelp, Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { ValidationSummary } from "@/components/validation-summary";
import { WizardShell } from "@/features/projects/wizard-shell";
import {
  canonicalWizardStep,
  journeyMatchesRequestedBuild,
  shouldPollJourney,
} from "@/features/projects/wizard-state";
import { formatBytes } from "@/lib/format";
import { buildIsActive } from "@/lib/lifecycle";
import { resolveDeploymentState } from "@/lib/deployment-state";
import {
  MAX_UPLOAD_LABEL,
  uploadAccept,
  uploadFileError,
  uploadFormatLabel,
} from "@/lib/uploads";

const identitySchema = z.object({
  name: z.string().trim().min(1, "Enter a project name.").max(160),
  slug: z
    .string()
    .trim()
    .min(3, "Use at least 3 characters.")
    .max(63)
    .regex(
      /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/,
      "Use lowercase letters, numbers, and internal hyphens.",
    ),
  description: z.string().trim().max(10_000).optional(),
});

const serverSchema = z.object({
  default_base_url: z
    .string()
    .trim()
    .refine(
      (value) => !value || z.url().safeParse(value).success,
      "Enter a complete http(s) URL.",
    ),
});

const credentialSchema = z
  .object({
    name: z.string().trim().min(1, "Name this credential."),
    security_scheme: z
      .string()
      .trim()
      .min(1, "Select a source security scheme."),
    scheme_type: z.enum([
      "bearer",
      "api_key_header",
      "api_key_query",
      "basic",
      "oauth2_client_credentials",
      "static_headers",
    ]),
    primary_secret: z.string().min(1, "Enter the secret value."),
    secondary_secret: z.string().optional(),
    scope: z.string().optional(),
    token_auth_method: z.enum(["client_secret_basic", "client_secret_post"]),
    header_name: z.string().optional(),
  })
  .superRefine((value, context) => {
    if (
      ["basic", "oauth2_client_credentials"].includes(value.scheme_type) &&
      !value.secondary_secret?.trim()
    ) {
      context.addIssue({
        code: "custom",
        path: ["secondary_secret"],
        message:
          value.scheme_type === "basic"
            ? "Enter the username."
            : "Enter the client ID.",
      });
    }
    if (
      ["api_key_header", "api_key_query", "static_headers"].includes(
        value.scheme_type,
      ) &&
      !value.header_name?.trim()
    ) {
      context.addIssue({
        code: "custom",
        path: ["header_name"],
        message:
          value.scheme_type === "api_key_query"
            ? "Enter the query parameter name."
            : "Enter the header name.",
      });
    }
  });

type IdentityValues = z.infer<typeof identitySchema>;
type ServerValues = z.infer<typeof serverSchema>;
type CredentialValues = z.infer<typeof credentialSchema>;

function StepActions({
  back,
  children,
}: {
  back?: () => void;
  children: ReactNode;
}) {
  return (
    <div className="mt-6 flex flex-col-reverse gap-3 border-t border-border pt-5 sm:flex-row sm:items-center sm:justify-between">
      {back ? (
        <Button onClick={back} variant="ghost">
          <ArrowLeft aria-hidden="true" className="size-4" />
          Back
        </Button>
      ) : (
        <span />
      )}
      {children}
    </div>
  );
}

export function NewProjectPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const capabilities = useCapabilities();
  const hasExplicitStep = params.has("step");
  const step = Math.min(10, Math.max(1, Number(params.get("step")) || 1));
  const projectId = params.get("project");
  const explicitBuildId = params.get("build");
  const [oneTimeToken, setOneTimeToken] = useState<McpAccessToken | null>(null);

  const project = useQuery({
    queryKey: ["projects", projectId],
    queryFn: ({ signal }) => projectApi.get(projectId!, signal),
    enabled: Boolean(projectId),
  });
  const journey = useQuery({
    queryKey: ["projects", projectId, "journey", explicitBuildId],
    queryFn: ({ signal }) =>
      projectApi.journey(projectId!, explicitBuildId, signal),
    enabled: Boolean(projectId),
    refetchInterval: (query) =>
      shouldPollJourney(query.state.data) ? 2_000 : false,
  });
  const journeyMatchesUrl = journeyMatchesRequestedBuild(
    journey.data,
    explicitBuildId,
  );
  const buildId = journeyMatchesUrl
    ? (journey.data?.selected_build_id ?? null)
    : null;
  const build = useQuery({
    queryKey: ["builds", buildId],
    queryFn: ({ signal }) => buildApi.get(buildId!, signal),
    enabled: Boolean(buildId) && step >= 7,
    refetchInterval: (query) =>
      query.state.data && !buildIsActive(query.state.data.status)
        ? false
        : 2_000,
  });
  const validation = useQuery({
    queryKey: ["builds", buildId, "validation"],
    queryFn: ({ signal }) => buildApi.validation(buildId!, signal),
    enabled: Boolean(buildId) && step >= 8 && build.data?.status === "READY",
  });
  const deployments = useQuery({
    queryKey: ["projects", projectId, "deployments"],
    queryFn: ({ signal }) => deploymentApi.list(projectId!, signal),
    enabled: Boolean(projectId) && step >= 10,
    refetchInterval: (query) =>
      query.state.data?.some((deployment) =>
        ["pending", "deploying", "healthcheck"].includes(deployment.status),
      )
        ? 4_000
        : false,
  });

  useEffect(() => {
    if (!projectId || !journey.data || !journeyMatchesUrl) return;
    const canonicalStep = canonicalWizardStep(
      step,
      hasExplicitStep,
      journey.data,
    );
    const canonicalBuild = journey.data.selected_build_id;
    if (
      canonicalStep === step &&
      hasExplicitStep &&
      (explicitBuildId ?? null) === canonicalBuild
    )
      return;
    const next = new URLSearchParams({
      step: String(canonicalStep),
      project: projectId,
    });
    if (canonicalBuild) next.set("build", canonicalBuild);
    navigate(`/projects/new?${next}`, { replace: true });
  }, [
    explicitBuildId,
    hasExplicitStep,
    journey.data,
    journeyMatchesUrl,
    navigate,
    projectId,
    step,
  ]);

  function go(
    nextStep: number,
    values: { project?: string; build?: string } = {},
  ) {
    const next = new URLSearchParams({ step: String(nextStep) });
    const nextProject = values.project ?? projectId;
    const nextBuild = values.build ?? buildId;
    if (nextProject) next.set("project", nextProject);
    if (nextBuild) next.set("build", nextBuild);
    navigate(`/projects/new?${next}`);
  }

  const shell = (content: ReactNode) => (
    <>
      <WizardShell
        buildId={buildId}
        projectId={projectId}
        step={step}
        steps={journey.data?.steps}
      >
        {content}
      </WizardShell>
      <OneTimeSecretDialog
        onAcknowledged={() => setOneTimeToken(null)}
        secret={oneTimeToken?.token ?? null}
      />
    </>
  );

  if (step > 1 && !projectId)
    return shell(
      <Alert title="Create the project first" tone="warning">
        Durable setup starts with project identity.{" "}
        <Button className="mt-3" onClick={() => go(1)} variant="outline">
          Return to step 1
        </Button>
      </Alert>,
    );
  if (projectId && (project.isPending || journey.isPending))
    return shell(
      <Card>
        <Spinner label="Loading durable project state" />
      </Card>,
    );
  if (project.error)
    return shell(
      <ErrorNotice
        error={project.error}
        onRetry={() => void project.refetch()}
        title="Project state could not be loaded"
      />,
    );
  if (journey.error)
    return shell(
      <ErrorNotice
        error={journey.error}
        nextStep="The project/build relationship was not accepted, so no downstream request was issued."
        onRetry={() => void journey.refetch()}
        title="Setup state could not be loaded"
      />,
    );

  return shell(
    <Card className="border-border-strong p-5 sm:p-7">
      {step === 1 && (
        <IdentityStep
          existing={project.data}
          onCreated={(id) => go(2, { project: id })}
        />
      )}
      {step === 2 && (
        <SourceStep
          kind="executable"
          onBack={() => go(1)}
          onComplete={() => go(3)}
          projectId={projectId!}
          sources={journey.data?.sources ?? []}
        />
      )}
      {step === 3 && (
        <SourceStep
          kind="documentation"
          onBack={() => go(2)}
          onComplete={() => go(4)}
          projectId={projectId!}
          sources={journey.data?.sources ?? []}
        />
      )}
      {step === 4 && (
        <ServerStep
          defaultValue={project.data?.default_base_url ?? ""}
          onBack={() => go(3)}
          onComplete={() => go(5)}
          projectId={projectId!}
        />
      )}
      {step === 5 && (
        <CredentialStep
          boundSchemes={journey.data?.bound_security_schemes ?? []}
          canManage={
            capabilities.canManageCredentials &&
            Boolean(journey.data?.can_manage_credentials)
          }
          mappingComplete={journey.data?.credential_mapping_complete ?? false}
          mappingRequired={journey.data?.credential_mapping_required ?? false}
          onBack={() => go(4)}
          onComplete={() => go(6)}
          projectId={projectId!}
        />
      )}
      {step === 6 && (
        <StartBuildStep
          existingBuildId={
            journey.data?.build_status &&
            !["FAILED", "CANCELLED"].includes(journey.data.build_status)
              ? buildId
              : null
          }
          onBack={() => go(5)}
          onStarted={(id) => go(7, { build: id })}
          projectId={projectId!}
        />
      )}
      {step === 7 && (
        <BuildProgressStep
          build={build.data}
          error={build.error}
          onBack={() => go(6)}
          onContinue={() => go(8)}
        />
      )}
      {step === 8 && (
        <ValidationStep
          error={validation.error}
          onBack={() => go(7)}
          onContinue={() => go(9)}
          report={validation.data}
        />
      )}
      {step === 9 && (
        <AccessStep
          accessConfigured={journey.data?.access_configured ?? false}
          canManage={
            capabilities.canManageMcpAccess &&
            Boolean(journey.data?.can_manage_mcp_access)
          }
          onBack={() => go(8)}
          onComplete={() => go(10)}
          onToken={setOneTimeToken}
          projectId={projectId!}
          remediation={journey.data?.access_remediation ?? null}
        />
      )}
      {step === 10 && (
        <DeployStep
          buildId={buildId}
          deployments={deployments.data ?? []}
          journey={journey.data!}
          onBack={() => go(9)}
          projectId={projectId!}
        />
      )}
    </Card>,
  );
}

function IdentityStep({
  onCreated,
  existing,
}: {
  onCreated: (projectId: string) => void;
  existing?: Project;
}) {
  const queryClient = useQueryClient();
  const form = useForm<IdentityValues>({
    resolver: zodResolver(identitySchema),
    defaultValues: {
      name: existing?.name ?? "",
      slug: existing?.slug ?? "",
      description: existing?.description ?? "",
    },
  });
  const save = useMutation({
    mutationFn: (values: IdentityValues) =>
      existing
        ? projectApi.update(existing.id, {
            name: values.name,
            description: values.description || null,
          })
        : projectApi.create(values),
    onSuccess: async (saved) => {
      queryClient.setQueryData(["projects", saved.id], saved);
      await queryClient.invalidateQueries({
        queryKey: ["projects", saved.id, "journey"],
      });
      onCreated(saved.id);
    },
  });
  return (
    <form
      noValidate
      onSubmit={form.handleSubmit((values) => save.mutate(values))}
    >
      <UnsavedChangesGuard active={form.formState.isDirty && !save.isPending} />
      <CardHeader>
        <div>
          <CardTitle id="wizard-step-title">Name the API product</CardTitle>
          <p className="mt-1 text-sm text-muted">
            The slug becomes part of the project MCP hostname and must be
            DNS-safe.
          </p>
        </div>
      </CardHeader>
      <div className="grid gap-5 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="project-name">Project name</Label>
          <Input
            id="project-name"
            autoFocus
            {...form.register("name", {
              onChange: (event) => {
                if (!form.formState.dirtyFields.slug)
                  form.setValue(
                    "slug",
                    event.target.value
                      .toLowerCase()
                      .trim()
                      .replace(/[^a-z0-9]+/g, "-")
                      .replace(/^-|-$/g, ""),
                  );
              },
            })}
            aria-invalid={Boolean(form.formState.errors.name)}
            placeholder="Inventory API"
          />
          {form.formState.errors.name && (
            <FieldError>{form.formState.errors.name.message}</FieldError>
          )}
        </div>
        <div className="space-y-2">
          <Label htmlFor="project-slug">Hostname slug</Label>
          <Input
            disabled={Boolean(existing)}
            id="project-slug"
            {...form.register("slug")}
            aria-invalid={Boolean(form.formState.errors.slug)}
            placeholder="inventory"
          />
          <FieldHelp>3–63 lowercase letters, numbers, or hyphens.</FieldHelp>
          {form.formState.errors.slug && (
            <FieldError>{form.formState.errors.slug.message}</FieldError>
          )}
        </div>
        <div className="space-y-2 sm:col-span-2">
          <Label htmlFor="project-description">
            Description{" "}
            <span className="font-normal text-muted">(optional)</span>
          </Label>
          <Textarea
            id="project-description"
            {...form.register("description")}
            placeholder="What this API exposes and who maintains it."
          />
          {form.formState.errors.description && (
            <FieldError>{form.formState.errors.description.message}</FieldError>
          )}
        </div>
      </div>
      {save.error && <MutationError error={save.error} />}
      <StepActions>
        <Button disabled={save.isPending} type="submit">
          {save.isPending
            ? "Saving project…"
            : existing
              ? "Save and continue"
              : "Create and continue"}
          <ArrowRight aria-hidden="true" className="size-4" />
        </Button>
      </StepActions>
    </form>
  );
}

function SourceStep({
  projectId,
  kind,
  onBack,
  onComplete,
  sources,
}: {
  projectId: string;
  kind: "executable" | "documentation";
  onBack: () => void;
  onComplete: () => void;
  sources: ProjectJourney["sources"];
}) {
  const queryClient = useQueryClient();
  const [origin, setOrigin] = useState<"upload" | "url">("upload");
  const [sourceKind, setSourceKind] = useState<SourceKind>(
    kind === "documentation" ? "documentation" : "openapi",
  );
  const [name, setName] = useState(
    kind === "documentation"
      ? "Product documentation"
      : "Primary API specification",
  );
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const sourceId = useRef(crypto.randomUUID());
  const create = useMutation({
    mutationFn: () =>
      origin === "url"
        ? sourceApi.createFromUrl(projectId, {
            source_id: sourceId.current,
            name,
            kind: sourceKind,
            source_url: url,
            is_primary: kind === "executable",
          })
        : sourceApi.createFromUpload(projectId, {
            source_id: sourceId.current,
            name,
            kind: sourceKind,
            file: file!,
            is_primary: kind === "executable",
          }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["projects", projectId, "journey"],
        }),
        queryClient.invalidateQueries({
          queryKey: ["projects", projectId, "sources"],
        }),
      ]);
      onComplete();
    },
  });
  const existing = sources.filter((source) =>
    kind === "documentation"
      ? source.kind === "documentation"
      : source.is_primary && source.kind !== "documentation",
  );
  const canSubmit =
    name.trim() &&
    (origin === "url" ? /^https?:\/\//.test(url) : Boolean(file) && !fileError);
  return (
    <div>
      <UnsavedChangesGuard
        active={
          !create.isPending &&
          (origin !== "upload" ||
            sourceKind !==
              (kind === "documentation" ? "documentation" : "openapi") ||
            name !==
              (kind === "documentation"
                ? "Product documentation"
                : "Primary API specification") ||
            Boolean(url) ||
            Boolean(file))
        }
      />
      <CardHeader>
        <div>
          <CardTitle id="wizard-step-title">
            {kind === "documentation"
              ? "Add supplemental documentation"
              : "Attach the executable API source"}
          </CardTitle>
          <p className="mt-1 text-sm leading-6 text-muted">
            {kind === "documentation"
              ? "Documentation can enrich descriptions but can never create executable tools. This step is optional."
              : "Use OpenAPI 3.0/3.1 or API Inventory v1. Invalid executable references block a READY build."}
          </p>
        </div>
      </CardHeader>
      {existing.length > 0 && (
        <Alert
          className="mb-5"
          title="Durable source already attached"
          tone="success"
        >
          {existing.map((source) => source.name).join(", ")} is loaded from the
          project record. Continue without creating a duplicate, or attach a new
          source below.
        </Alert>
      )}
      <div className="grid gap-5 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="source-kind">Source format</Label>
          <Select
            id="source-kind"
            onChange={(event) => {
              const nextKind = event.target.value as SourceKind;
              setSourceKind(nextKind);
              setFileError(file ? uploadFileError(file, nextKind) : null);
            }}
            value={sourceKind}
            disabled={kind === "documentation"}
          >
            {kind === "documentation" ? (
              <option value="documentation">Documentation</option>
            ) : (
              <>
                <option value="openapi">OpenAPI 3.x</option>
                <option value="api_inventory">API Inventory v1</option>
              </>
            )}
          </Select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="source-origin">Input method</Label>
          <Select
            id="source-origin"
            onChange={(event) =>
              setOrigin(event.target.value as "upload" | "url")
            }
            value={origin}
          >
            <option value="upload">Upload file</option>
            <option value="url">Secure URL fetch</option>
          </Select>
        </div>
        <div className="space-y-2 sm:col-span-2">
          <Label htmlFor="source-name">Source name</Label>
          <Input
            id="source-name"
            onChange={(event) => setName(event.target.value)}
            value={name}
          />
        </div>
        {origin === "url" ? (
          <div className="space-y-2 sm:col-span-2">
            <Label htmlFor="source-url">HTTPS source URL</Label>
            <Input
              id="source-url"
              inputMode="url"
              onChange={(event) => setUrl(event.target.value)}
              placeholder="https://api.example.com/openapi.json"
              type="url"
              value={url}
            />
            <FieldHelp>
              Redirects and resolved destinations are revalidated by the backend
              SSRF policy.
            </FieldHelp>
          </div>
        ) : (
          <div className="space-y-2 sm:col-span-2">
            <Label htmlFor="source-file">Source file</Label>
            <Input
              accept={uploadAccept(sourceKind)}
              aria-invalid={Boolean(fileError)}
              id="source-file"
              onChange={(event) => {
                const selected = event.target.files?.[0] ?? null;
                setFile(selected);
                setFileError(
                  selected ? uploadFileError(selected, sourceKind) : null,
                );
              }}
              type="file"
            />
            {fileError ? (
              <FieldError>{fileError}</FieldError>
            ) : (
              <FieldHelp>
                {file
                  ? `${file.name} · ${formatBytes(file.size)}`
                  : kind === "documentation"
                    ? `${uploadFormatLabel("documentation")} · ${MAX_UPLOAD_LABEL} maximum.`
                    : `${uploadFormatLabel("openapi")} · ${MAX_UPLOAD_LABEL} maximum.`}
              </FieldHelp>
            )}
          </div>
        )}
      </div>
      {create.error && <MutationError error={create.error} />}
      <StepActions back={onBack}>
        <div className="flex flex-wrap gap-2">
          {existing.length > 0 && (
            <Button onClick={onComplete} variant="outline">
              Continue with existing source
            </Button>
          )}
          {kind === "documentation" && (
            <Button onClick={onComplete} variant="ghost">
              Skip documentation
            </Button>
          )}
          <Button
            disabled={!canSubmit || create.isPending}
            onClick={() => create.mutate()}
          >
            {create.isPending ? "Adding source…" : "Add source and continue"}
            <ArrowRight aria-hidden="true" className="size-4" />
          </Button>
        </div>
      </StepActions>
    </div>
  );
}

function ServerStep({
  projectId,
  defaultValue,
  onBack,
  onComplete,
}: {
  projectId: string;
  defaultValue: string;
  onBack: () => void;
  onComplete: () => void;
}) {
  const queryClient = useQueryClient();
  const discovery = useQuery({
    queryKey: ["projects", projectId, "source-configuration"],
    queryFn: ({ signal }) => sourceApi.configuration(projectId, signal),
  });
  const [mappingDraft, setMappingDraft] = useState<{
    source: NonNullable<typeof discovery.data>;
    value: Record<string, string>;
  } | null>(null);
  const form = useForm<ServerValues>({
    resolver: zodResolver(serverSchema),
    defaultValues: { default_base_url: defaultValue },
  });
  const discoveredMappings = Object.fromEntries(
    discovery.data?.operations.flatMap((operation) =>
      operation.configured_server_ref
        ? [[operation.operation_key, operation.configured_server_ref]]
        : [],
    ) ?? [],
  );
  const mappings =
    discovery.data && mappingDraft?.source === discovery.data
      ? mappingDraft.value
      : discoveredMappings;
  const update = useMutation({
    mutationFn: async (values: ServerValues) => {
      await projectApi.update(projectId, {
        ...(values.default_base_url
          ? { default_base_url: values.default_base_url }
          : {}),
        server_mappings: mappings,
      });
      return sourceApi.configuration(projectId);
    },
    onSuccess: async (configured) => {
      queryClient.setQueryData(
        ["projects", projectId, "source-configuration"],
        configured,
      );
      void queryClient.invalidateQueries({
        queryKey: ["projects", projectId],
      });
      await queryClient.invalidateQueries({
        queryKey: ["projects", projectId, "journey"],
      });
      if (configured.routing_complete) onComplete();
    },
  });
  const serverByRef = new Map(
    discovery.data?.servers.map((server) => [server.ref, server]) ?? [],
  );
  const unresolved =
    discovery.data?.operations.filter(
      (operation) =>
        (!mappings[operation.operation_key] &&
          !operation.selected_server_ref) ||
        (Boolean(mappings[operation.operation_key]) &&
          !operation.candidate_refs.includes(
            mappings[operation.operation_key],
          )),
    ) ?? [];
  return (
    <form
      noValidate
      onSubmit={form.handleSubmit((values) => update.mutate(values))}
    >
      <UnsavedChangesGuard
        active={
          !update.isPending &&
          (form.formState.isDirty ||
            Object.entries(mappings).some(
              ([operationKey, serverRef]) =>
                discovery.data?.operations.find(
                  (operation) => operation.operation_key === operationKey,
                )?.configured_server_ref !== serverRef,
            ))
        }
      />
      <CardHeader>
        <div>
          <CardTitle id="wizard-step-title">
            Select the upstream API server
          </CardTitle>
          <p className="mt-1 text-sm leading-6 text-muted">
            This is the allowlisted transport destination. MCP callers cannot
            replace it with tool arguments.
          </p>
        </div>
      </CardHeader>
      <div className="space-y-2">
        <Label htmlFor="base-url">
          Resolution base URL{" "}
          <span className="font-normal text-muted">
            (only for relative URLs)
          </span>
        </Label>
        <Input
          id="base-url"
          inputMode="url"
          placeholder="https://inventory.example.com/api"
          type="url"
          {...form.register("default_base_url")}
          aria-invalid={Boolean(form.formState.errors.default_base_url)}
        />
        <FieldHelp>
          Relative source server and OAuth URLs resolve against this stable
          project base. Absolute source URLs do not require an override.
        </FieldHelp>
        {form.formState.errors.default_base_url && (
          <FieldError>
            {form.formState.errors.default_base_url.message}
          </FieldError>
        )}
      </div>
      {discovery.isPending && (
        <div className="mt-5">
          <Spinner label="Inspecting source server candidates" />
        </div>
      )}
      {discovery.error && (
        <ErrorNotice
          error={discovery.error}
          nextStep="Enter a base URL, then save to inspect the resolved candidates."
          onRetry={() => void discovery.refetch()}
          title="Server candidates need a resolution base"
        />
      )}
      {discovery.data && (
        <div className="mt-5 space-y-4">
          {discovery.data.operations.map((operation) => (
            <div
              className="rounded-lg border border-border bg-input p-4"
              key={operation.operation_key}
            >
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <p className="font-mono text-sm text-foreground">
                  {operation.method} {operation.path}
                </p>
                <span className="text-xs text-muted">
                  {operation.candidate_refs.length} candidate
                  {operation.candidate_refs.length === 1 ? "" : "s"}
                </span>
              </div>
              {operation.candidate_refs.length === 1 ? (
                <p className="mt-2 break-all text-sm text-muted">
                  {serverByRef.get(operation.candidate_refs[0])?.url}
                </p>
              ) : (
                <div className="mt-3 space-y-2">
                  <Label htmlFor={`server-${operation.operation_key}`}>
                    Upstream server
                  </Label>
                  <Select
                    id={`server-${operation.operation_key}`}
                    onChange={(event) => {
                      if (!discovery.data) return;
                      setMappingDraft((current) => ({
                        source: discovery.data!,
                        value: {
                          ...(current?.source === discovery.data
                            ? current.value
                            : discoveredMappings),
                          [operation.operation_key]: event.target.value,
                        },
                      }));
                    }}
                    value={mappings[operation.operation_key] ?? ""}
                  >
                    <option value="">Select a source-declared server</option>
                    {operation.candidate_refs.map((candidate) => {
                      const server = serverByRef.get(candidate);
                      return (
                        <option key={candidate} value={candidate}>
                          {server?.description
                            ? `${server.description} — ${server.url}`
                            : (server?.url ?? candidate)}
                        </option>
                      );
                    })}
                  </Select>
                </div>
              )}
              {operation.selection_error && (
                <FieldError>{operation.selection_error}</FieldError>
              )}
            </div>
          ))}
        </div>
      )}
      {update.error && <MutationError error={update.error} />}
      <StepActions back={onBack}>
        <Button
          disabled={
            update.isPending || Boolean(discovery.data && unresolved.length)
          }
          type="submit"
        >
          {update.isPending ? "Validating routing…" : "Save validated routing"}
          <ArrowRight aria-hidden="true" className="size-4" />
        </Button>
      </StepActions>
    </form>
  );
}

function CredentialStep({
  projectId,
  onBack,
  onComplete,
  canManage,
  mappingComplete,
  mappingRequired,
  boundSchemes,
}: {
  projectId: string;
  onBack: () => void;
  onComplete: () => void;
  canManage: boolean;
  mappingComplete: boolean;
  mappingRequired: boolean;
  boundSchemes: readonly string[];
}) {
  const queryClient = useQueryClient();
  const discovery = useQuery({
    queryKey: ["projects", projectId, "source-configuration"],
    queryFn: ({ signal }) => sourceApi.configuration(projectId, signal),
  });
  const form = useForm<CredentialValues>({
    resolver: zodResolver(credentialSchema),
    defaultValues: {
      name: "Primary upstream credential",
      security_scheme: "",
      scheme_type: "bearer",
      primary_secret: "",
      secondary_secret: "",
      scope: "",
      token_auth_method: "client_secret_basic",
      header_name: "",
    },
  });
  const scheme = useWatch({ control: form.control, name: "scheme_type" });
  const securitySchemeName = useWatch({
    control: form.control,
    name: "security_scheme",
  });
  const supportedSchemes =
    discovery.data?.security_schemes.filter(
      (item) => credentialSchemeForSource(item) !== null,
    ) ?? [];
  const sourceScheme = discovery.data?.security_schemes.find(
    (item) => item.name === securitySchemeName,
  );
  const selectSourceScheme = (name: string) => {
    const selected = supportedSchemes.find((item) => item.name === name);
    form.setValue("security_scheme", name, { shouldValidate: true });
    if (!selected) return;
    const selectedType = credentialSchemeForSource(selected);
    if (selectedType) form.setValue("scheme_type", selectedType);
    form.setValue("header_name", selected.parameter_name ?? "");
  };
  useEffect(() => {
    const discovered = discovery.data?.security_schemes.filter(
      (item) => credentialSchemeForSource(item) !== null,
    );
    if (discovered?.length !== 1 || securitySchemeName) return;
    const selected = discovered[0];
    form.setValue("security_scheme", selected.name, { shouldValidate: true });
    const selectedType = credentialSchemeForSource(selected);
    if (selectedType) form.setValue("scheme_type", selectedType);
    form.setValue("header_name", selected.parameter_name ?? "");
  }, [discovery.data, form, securitySchemeName]);
  const create = useMutation({
    mutationFn: (values: CredentialValues) => {
      const credential = credentialSecretFor(values.scheme_type, {
        value: values.primary_secret,
        identity: values.secondary_secret,
        scope: values.scope,
        headerName: values.header_name,
        securityScheme: values.security_scheme,
        tokenAuthMethod: values.token_auth_method,
      });
      return credentialApi.create(projectId, {
        name: values.name,
        scheme_type: values.scheme_type,
        ...credential,
      });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["projects", projectId, "journey"],
      });
      onComplete();
    },
  });
  const secondaryLabel =
    scheme === "basic"
      ? "Username"
      : scheme === "oauth2_client_credentials"
        ? "Client ID"
        : null;
  if (!canManage) {
    return (
      <div>
        <CardHeader>
          <div>
            <CardTitle id="wizard-step-title">
              Configure upstream authentication
            </CardTitle>
            <p className="mt-1 text-sm leading-6 text-muted">
              Credential values and binding controls are administrator-only.
            </p>
          </div>
          <KeyRound aria-hidden="true" className="size-5 text-warning" />
        </CardHeader>
        <Alert
          title={
            mappingComplete
              ? "Upstream authorization is ready"
              : "Administrator handoff required"
          }
          tone={mappingComplete ? "success" : "warning"}
        >
          {mappingComplete
            ? `The server-derived mapping is complete${boundSchemes.length ? ` for ${boundSchemes.join(", ")}` : ""}. Secret metadata remains hidden.`
            : "Ask an administrator to bind one compatible active credential for every required source security alternative. This page does not call the protected credential API."}
        </Alert>
        <StepActions back={onBack}>
          <Button disabled={!mappingComplete} onClick={onComplete}>
            Continue with verified mapping
            <ArrowRight aria-hidden="true" className="size-4" />
          </Button>
        </StepActions>
      </div>
    );
  }
  return (
    <form
      noValidate
      onSubmit={form.handleSubmit((values) => create.mutate(values))}
    >
      <UnsavedChangesGuard
        active={form.formState.isDirty && !create.isPending}
      />
      <CardHeader>
        <div>
          <CardTitle id="wizard-step-title">
            Configure upstream authentication
          </CardTitle>
          <p className="mt-1 text-sm leading-6 text-muted">
            Secrets are accepted once, encrypted by the control plane, and never
            redisplayed.
          </p>
        </div>
        <KeyRound aria-hidden="true" className="size-5 text-warning" />
      </CardHeader>
      {mappingComplete && (
        <Alert
          className="mb-5"
          title="Existing mapping verified"
          tone="success"
        >
          {boundSchemes.length
            ? `Active credentials cover ${boundSchemes.join(", ")}.`
            : "The source permits anonymous upstream access."}{" "}
          Continue without creating duplicate credentials, or add a deliberate
          replacement.
        </Alert>
      )}
      <div className="grid gap-5 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="credential-name">Credential name</Label>
          <Input id="credential-name" {...form.register("name")} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="source-security-scheme">Source security scheme</Label>
          <Select
            id="source-security-scheme"
            onChange={(event) => selectSourceScheme(event.target.value)}
            value={securitySchemeName}
          >
            <option value="">Select a discovered scheme</option>
            {supportedSchemes.map((item) => (
              <option key={item.name} value={item.name}>
                {item.name} · {item.type}
              </option>
            ))}
          </Select>
          {form.formState.errors.security_scheme && (
            <FieldError>
              {form.formState.errors.security_scheme.message}
            </FieldError>
          )}
        </div>
        {secondaryLabel && (
          <div className="space-y-2">
            <Label htmlFor="secondary-secret">{secondaryLabel}</Label>
            <Input
              autoComplete="off"
              id="secondary-secret"
              {...form.register("secondary_secret")}
            />
          </div>
        )}
        <div className="space-y-2">
          <Label htmlFor="primary-secret">
            {scheme === "basic"
              ? "Password"
              : scheme === "oauth2_client_credentials"
                ? "Client secret"
                : "Secret value"}
          </Label>
          <Input
            autoComplete="new-password"
            id="primary-secret"
            type="password"
            {...form.register("primary_secret")}
            aria-invalid={Boolean(form.formState.errors.primary_secret)}
          />
          {form.formState.errors.primary_secret && (
            <FieldError>
              {form.formState.errors.primary_secret.message}
            </FieldError>
          )}
        </div>
        {["api_key_header", "api_key_query", "static_headers"].includes(
          scheme,
        ) && (
          <div className="space-y-2">
            <Label htmlFor="header-name">
              {scheme === "api_key_query" ? "Query parameter" : "Header name"}
            </Label>
            <Input id="header-name" {...form.register("header_name")} />
            {form.formState.errors.header_name && (
              <FieldError>
                {form.formState.errors.header_name.message}
              </FieldError>
            )}
          </div>
        )}
        {scheme === "oauth2_client_credentials" && (
          <div className="space-y-2 sm:col-span-2">
            <Label>Source token endpoint</Label>
            <p className="break-all rounded-md border border-border bg-input px-3 py-2 font-mono text-xs text-muted">
              {sourceScheme?.token_url ?? "Select an OAuth source scheme"}
            </p>
            <Label htmlFor="oauth-scope">Default scope (optional)</Label>
            <Input id="oauth-scope" {...form.register("scope")} />
            <FieldHelp>
              Explicit operation scopes remain authoritative. This default is
              used only for an empty source scope set.
            </FieldHelp>
            <Label htmlFor="oauth-token-method">
              Token endpoint auth method
            </Label>
            <Select
              id="oauth-token-method"
              {...form.register("token_auth_method")}
            >
              <option value="client_secret_basic">client_secret_basic</option>
              <option value="client_secret_post">client_secret_post</option>
            </Select>
          </div>
        )}
      </div>
      <Alert className="mt-5" tone="info">
        MCP inbound access is configured separately in step 9. Upstream
        credentials never become tool arguments or manifest fields.
      </Alert>
      {create.error && <MutationError error={create.error} />}
      {discovery.isPending && (
        <div className="mt-5">
          <Spinner label="Loading source security schemes" />
        </div>
      )}
      {discovery.error && (
        <ErrorNotice
          error={discovery.error}
          onRetry={() => void discovery.refetch()}
          title="Source security schemes could not be loaded"
        />
      )}
      {discovery.data && supportedSchemes.length === 0 && (
        <Alert
          className="mt-5"
          tone={discovery.data.security_schemes.length ? "danger" : "info"}
        >
          {discovery.data.security_schemes.length
            ? "The source requires an authentication scheme this runtime cannot execute."
            : "The source declares no upstream authentication requirement."}
        </Alert>
      )}
      <StepActions back={onBack}>
        <div className="flex flex-wrap gap-2">
          {(mappingComplete || !mappingRequired) && (
            <Button onClick={onComplete} variant="outline">
              Continue with current mapping
            </Button>
          )}
          {discovery.data &&
            (discovery.data.security_schemes.length === 0 ||
              discovery.data.security_schemes.every(
                (item) => item.optional_for_all_operations,
              )) && (
              <Button onClick={onComplete} variant="ghost">
                Continue without an upstream credential
              </Button>
            )}
          <Button
            disabled={
              create.isPending ||
              discovery.isPending ||
              Boolean(discovery.error) ||
              supportedSchemes.length === 0
            }
            type="submit"
          >
            Save credential
            <ArrowRight aria-hidden="true" className="size-4" />
          </Button>
        </div>
      </StepActions>
    </form>
  );
}

function StartBuildStep({
  projectId,
  existingBuildId,
  onBack,
  onStarted,
}: {
  projectId: string;
  existingBuildId: string | null;
  onBack: () => void;
  onStarted: (id: string) => void;
}) {
  const queryClient = useQueryClient();
  const start = useMutation({
    mutationFn: () => buildApi.create(projectId),
    onSuccess: (build) => {
      // Move to a URL bound to the created build first. The new journey query
      // validates that project/build relationship before any build detail call.
      onStarted(build.id);
      void queryClient.invalidateQueries({
        queryKey: ["projects", projectId, "journey"],
      });
    },
  });
  return (
    <div>
      <CardHeader>
        <div>
          <CardTitle id="wizard-step-title">
            Create an immutable build
          </CardTitle>
          <p className="mt-1 text-sm leading-6 text-muted">
            The build binds exact source versions, then parses, indexes,
            analyzes, compiles, validates, and packages them asynchronously.
          </p>
        </div>
        <FileCode2 aria-hidden="true" className="size-5 text-accent" />
      </CardHeader>
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-lg border border-border bg-input p-4">
          <p className="font-mono text-xs text-info-soft">01 · Deterministic</p>
          <p className="mt-2 text-sm text-muted">
            Executable method, path, schemas, and auth mappings come from source
            truth.
          </p>
        </div>
        <div className="rounded-lg border border-border bg-input p-4">
          <p className="font-mono text-xs text-accent">02 · Bounded AI</p>
          <p className="mt-2 text-sm text-muted">
            OpenRouter may enrich semantics but cannot mutate executable fields.
          </p>
        </div>
        <div className="rounded-lg border border-border bg-input p-4">
          <p className="font-mono text-xs text-warning-soft">
            03 · Blocking proof
          </p>
          <p className="mt-2 text-sm text-muted">
            Coverage and runtime compatibility must pass before deployment.
          </p>
        </div>
      </div>
      {start.error && <MutationError error={start.error} />}
      <StepActions back={onBack}>
        <div className="flex flex-wrap gap-2">
          {existingBuildId && (
            <Button
              onClick={() => onStarted(existingBuildId)}
              variant="outline"
            >
              Continue existing build
            </Button>
          )}
          <Button disabled={start.isPending} onClick={() => start.mutate()}>
            {start.isPending ? "Queuing build…" : "Start build"}
            <ArrowRight aria-hidden="true" className="size-4" />
          </Button>
        </div>
      </StepActions>
    </div>
  );
}

function BuildProgressStep({
  build,
  error,
  onBack,
  onContinue,
}: {
  build?: Awaited<ReturnType<typeof buildApi.get>>;
  error: Error | null;
  onBack: () => void;
  onContinue: () => void;
}) {
  if (error)
    return (
      <div>
        <ErrorNotice error={error} title="Build status is unavailable" />
        <StepActions back={onBack}>
          <span />
        </StepActions>
      </div>
    );
  if (!build) return <Spinner label="Loading build progress" />;
  return (
    <div>
      <CardHeader>
        <div>
          <CardTitle id="wizard-step-title">Build #{build.sequence}</CardTitle>
          <p className="mt-1 text-sm text-muted">
            Progress refreshes without a page reload. Completed builds remain
            immutable.
          </p>
        </div>
        <BuildStatusBadge status={build.status} />
      </CardHeader>
      <BuildProgress
        pipelineStage={build.pipeline_stage}
        status={build.status}
      />
      {build.status === "FAILED" && (
        <Alert
          className="mt-5"
          title={build.error_code ?? "Build failed"}
          tone="danger"
        >
          {build.error_summary ??
            "Open the build detail for sanitized findings and recovery guidance."}
        </Alert>
      )}
      {build.status === "CANCELLED" && (
        <Alert className="mt-5" tone="warning">
          This build was cancelled and cannot become deployable.
        </Alert>
      )}
      <StepActions back={onBack}>
        <Button disabled={build.status !== "READY"} onClick={onContinue}>
          Review validation
          <ArrowRight aria-hidden="true" className="size-4" />
        </Button>
      </StepActions>
    </div>
  );
}

function ValidationStep({
  report,
  error,
  onBack,
  onContinue,
}: {
  report?: Awaited<ReturnType<typeof buildApi.validation>>;
  error: Error | null;
  onBack: () => void;
  onContinue: () => void;
}) {
  if (error)
    return (
      <div>
        <ErrorNotice error={error} title="Validation report is unavailable" />
        <StepActions back={onBack}>
          <span />
        </StepActions>
      </div>
    );
  if (!report) return <Spinner label="Loading validation evidence" />;
  const valid =
    report.overall_status === "pass" &&
    report.coverage_percent === 100 &&
    report.blocking_error_count === 0;
  return (
    <div>
      <CardHeader>
        <div>
          <CardTitle id="wizard-step-title">
            Coverage and blocking findings
          </CardTitle>
          <p className="mt-1 text-sm text-muted">
            READY requires 100% of expected operations after explicit
            exclusions.
          </p>
        </div>
        <span className="text-3xl font-semibold text-foreground">
          {report.coverage_percent}%
        </span>
      </CardHeader>
      <ValidationSummary report={report} />
      <StepActions back={onBack}>
        <Button disabled={!valid} onClick={onContinue}>
          Configure MCP access
          <ArrowRight aria-hidden="true" className="size-4" />
        </Button>
      </StepActions>
    </div>
  );
}

function AccessStep({
  projectId,
  accessConfigured,
  canManage,
  remediation,
  onToken,
  onBack,
  onComplete,
}: {
  projectId: string;
  accessConfigured: boolean;
  canManage: boolean;
  remediation: string | null;
  onToken: (token: McpAccessToken) => void;
  onBack: () => void;
  onComplete: () => void;
}) {
  if (canManage)
    return (
      <AdminAccessControls
        accessConfigured={accessConfigured}
        onBack={onBack}
        onComplete={onComplete}
        onToken={onToken}
        projectId={projectId}
      />
    );
  return (
    <div>
      <CardHeader>
        <div>
          <CardTitle id="wizard-step-title">
            Protect the published MCP endpoint
          </CardTitle>
          <p className="mt-1 text-sm leading-6 text-muted">
            Inbound token inventory and verifier configuration are
            administrator-only.
          </p>
        </div>
        <ShieldCheck aria-hidden="true" className="size-5 text-success" />
      </CardHeader>
      <Alert
        title={
          accessConfigured
            ? "Inbound access is ready"
            : "Administrator handoff required"
        }
        tone={accessConfigured ? "success" : "warning"}
      >
        {accessConfigured
          ? "The redacted server status confirms that a deployable verifier is configured. Secret details remain hidden."
          : (remediation ??
            "Ask an administrator to configure inbound MCP access.")}
      </Alert>
      <StepActions back={onBack}>
        <Button disabled={!accessConfigured} onClick={onComplete}>
          Continue with verified access
          <ArrowRight aria-hidden="true" className="size-4" />
        </Button>
      </StepActions>
    </div>
  );
}

function AdminAccessControls({
  projectId,
  accessConfigured,
  onToken,
  onBack,
  onComplete,
}: {
  projectId: string;
  accessConfigured: boolean;
  onToken: (token: McpAccessToken) => void;
  onBack: () => void;
  onComplete: () => void;
}) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("Primary MCP client");
  const configure = useMutation({
    mutationFn: () =>
      deploymentApi.setAuthMode(projectId, { mode: "static_bearer" }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["projects", projectId, "mcp-access"],
      });
      void queryClient.invalidateQueries({
        queryKey: ["projects", projectId, "journey"],
      });
    },
  });
  const token = useMutation({
    mutationFn: () => deploymentApi.createToken(projectId, { name }),
    onSuccess: async (value) => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["projects", projectId, "mcp-access"],
        }),
        queryClient.invalidateQueries({
          queryKey: ["projects", projectId, "journey"],
        }),
      ]);
      onToken(value);
    },
  });
  return (
    <div>
      <CardHeader>
        <div>
          <CardTitle id="wizard-step-title">
            Protect the published MCP endpoint
          </CardTitle>
          <p className="mt-1 text-sm leading-6 text-muted">
            Static high-entropy bearer access is the interoperable production
            baseline. It is independent from upstream API authentication.
          </p>
        </div>
        <ShieldCheck aria-hidden="true" className="size-5 text-success" />
      </CardHeader>
      {!accessConfigured && (
        <div className="space-y-4">
          <Alert tone="warning">
            Deployment stays disabled until inbound MCP authentication is
            configured.
          </Alert>
          <Button
            disabled={configure.isPending}
            onClick={() => configure.mutate()}
            variant="outline"
          >
            {configure.isPending
              ? "Configuring…"
              : "Use static bearer authentication"}
          </Button>
        </div>
      )}
      <div className="mt-5 space-y-2">
        <Label htmlFor="token-name">Access token name</Label>
        <div className="flex flex-col gap-2 sm:flex-row">
          <Input
            id="token-name"
            onChange={(event) => setName(event.target.value)}
            value={name}
          />
          <Button
            disabled={!name.trim() || token.isPending}
            onClick={() => token.mutate()}
          >
            {token.isPending ? "Creating…" : "Create access token"}
          </Button>
        </div>
      </div>
      {(configure.error || token.error) && (
        <MutationError error={configure.error ?? token.error} />
      )}
      <StepActions back={onBack}>
        <Button disabled={!accessConfigured} onClick={onComplete}>
          Continue to deploy
          <ArrowRight aria-hidden="true" className="size-4" />
        </Button>
      </StepActions>
    </div>
  );
}

function DeployStep({
  projectId,
  buildId,
  deployments,
  journey,
  onBack,
}: {
  projectId: string;
  buildId: string | null;
  deployments: Awaited<ReturnType<typeof deploymentApi.list>>;
  journey: ProjectJourney;
  onBack: () => void;
}) {
  const queryClient = useQueryClient();
  const buildsQuery = useQuery({
    queryKey: ["projects", projectId, "builds"],
    queryFn: ({ signal }) => buildApi.list(projectId, signal),
  });
  const activeQuery = useQuery({
    queryKey: ["deployments", journey.active_deployment_id],
    queryFn: ({ signal }) =>
      deploymentApi.get(journey.active_deployment_id!, signal),
    enabled: Boolean(journey.active_deployment_id),
  });
  const deploy = useMutation({
    mutationFn: () => deploymentApi.deploy(projectId, buildId!),
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["projects", projectId, "deployments"],
        }),
        queryClient.invalidateQueries({
          queryKey: ["projects", projectId, "journey"],
        }),
        queryClient.invalidateQueries({
          queryKey: ["projects", projectId],
        }),
      ]),
  });
  const { active, newestCandidate: candidate } =
    resolveDeploymentState<Deployment>(
      journey.active_deployment_id,
      deployments,
      activeQuery.data,
    );
  const canDeploy = Boolean(buildId) && journey.deployable;
  const buildLabel = (id: string) => {
    const sequence = buildsQuery.data?.find(
      (build) => build.id === id,
    )?.sequence;
    return sequence === undefined ? "Build unavailable" : `Build #${sequence}`;
  };
  return (
    <div>
      <CardHeader>
        <div>
          <CardTitle id="wizard-step-title">
            Deploy the validated build
          </CardTitle>
          <p className="mt-1 text-sm leading-6 text-muted">
            A separate hardened runtime is health-checked before it becomes
            authoritative. Failed replacements leave the previous healthy
            deployment intact.
          </p>
        </div>
        <Rocket aria-hidden="true" className="size-5 text-accent" />
      </CardHeader>
      {active && (
        <div className="rounded-lg border border-border bg-input p-4">
          <p className="mb-2 font-mono text-[0.64rem] uppercase tracking-[0.1em] text-success-soft">
            Active runtime
          </p>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-foreground">
                {active.hostname}
              </p>
              <p className="mt-1 font-mono text-xs text-muted">
                {buildLabel(active.build_id)}
              </p>
            </div>
            <DeploymentStatusBadge status={active.status} />
          </div>
        </div>
      )}
      {candidate && (
        <Alert className="mt-5" title="Newest deployment candidate" tone="info">
          {buildLabel(candidate.build_id)} is {candidate.status.toLowerCase()}.
          It does not replace the active runtime unless activation commits
          successfully.
        </Alert>
      )}
      {!journey.deployable &&
        !(
          journey.active_build_id === buildId &&
          journey.active_deployment_status === "running"
        ) && (
          <Alert
            className="mt-5"
            title={
              journey.deployability_reason_code ?? "Deployment is not ready"
            }
            tone="danger"
          >
            {journey.deployability_remediation ??
              "Complete the current authoritative setup step before deploying."}
          </Alert>
        )}
      {deploy.error && <MutationError error={deploy.error} />}
      {buildsQuery.error && (
        <ErrorNotice
          error={buildsQuery.error}
          nextStep="Deployment readiness still comes from the server-derived journey state."
          onRetry={() => void buildsQuery.refetch()}
          title="Build display identity could not be loaded"
        />
      )}
      {active?.status === "running" && (
        <Alert className="mt-5" title="MCP runtime is healthy" tone="success">
          The endpoint is ready for an authenticated external MCP client.
          Builder OpenRouter and Milvus availability do not affect runtime
          execution.
        </Alert>
      )}
      <StepActions back={onBack}>
        <div className="flex flex-wrap gap-2">
          {active?.status === "running" && (
            <Link
              className={buttonVariants({ variant: "outline" })}
              to={`/projects/${projectId}/deployment`}
            >
              Open deployment
            </Link>
          )}
          <Button
            disabled={
              !canDeploy ||
              deploy.isPending ||
              journey.deployment_transition_in_progress
            }
            onClick={() => deploy.mutate()}
          >
            {deploy.isPending
              ? "Starting deployment…"
              : active
                ? "Deploy replacement"
                : "Deploy runtime"}
            <Rocket aria-hidden="true" className="size-4" />
          </Button>
        </div>
      </StepActions>
    </div>
  );
}
