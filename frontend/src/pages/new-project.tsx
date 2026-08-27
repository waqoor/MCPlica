import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  Clipboard,
  FileCode2,
  KeyRound,
  Rocket,
  ShieldCheck,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { z } from "@/lib/schemas";
import { buildApi } from "@/api/builds";
import type { McpAccessToken, SourceKind } from "@/api/contracts";
import { credentialApi, credentialSecretFor } from "@/api/credentials";
import { deploymentApi } from "@/api/deployments";
import { projectApi } from "@/api/projects";
import { sourceApi } from "@/api/sources";
import { BuildProgress } from "@/components/build-progress";
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
import { WizardShell } from "@/features/projects/wizard-shell";
import { buildIsActive } from "@/lib/lifecycle";
import { MAX_UPLOAD_LABEL, uploadAccept, uploadFileError } from "@/lib/uploads";

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
  default_base_url: z.string().trim().url("Enter a complete http(s) URL."),
});

const credentialSchema = z
  .object({
    name: z.string().trim().min(1, "Name this credential."),
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
    token_url: z.string().optional(),
    scope: z.string().optional(),
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
    if (value.scheme_type === "oauth2_client_credentials") {
      const parsed = z.url().safeParse(value.token_url);
      if (!parsed.success) {
        context.addIssue({
          code: "custom",
          path: ["token_url"],
          message: "Enter a complete token URL.",
        });
      }
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
  const step = Math.min(10, Math.max(1, Number(params.get("step")) || 1));
  const projectId = params.get("project");
  const explicitBuildId = params.get("build");
  const [oneTimeToken, setOneTimeToken] = useState<McpAccessToken | null>(null);

  const project = useQuery({
    queryKey: ["projects", projectId],
    queryFn: ({ signal }) => projectApi.get(projectId!, signal),
    enabled: Boolean(projectId),
  });
  const builds = useQuery({
    queryKey: ["projects", projectId, "builds"],
    queryFn: ({ signal }) => buildApi.list(projectId!, signal),
    enabled: Boolean(projectId) && step >= 6,
  });
  const buildId = explicitBuildId ?? builds.data?.[0]?.id ?? null;
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
  const access = useQuery({
    queryKey: ["projects", projectId, "mcp-access"],
    queryFn: ({ signal }) => deploymentApi.access(projectId!, signal),
    enabled: Boolean(projectId) && step >= 9,
  });
  const deployments = useQuery({
    queryKey: ["projects", projectId, "deployments"],
    queryFn: ({ signal }) => deploymentApi.list(projectId!, signal),
    enabled: Boolean(projectId) && step >= 10,
    refetchInterval: 4_000,
  });

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
    <WizardShell buildId={buildId} projectId={projectId} step={step}>
      {content}
    </WizardShell>
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
  if (projectId && project.isPending)
    return shell(
      <Card>
        <Spinner label="Loading durable project state" />
      </Card>,
    );
  if (project.error)
    return shell(
      <Alert title="Project state could not be loaded" tone="danger">
        {project.error.message}
      </Alert>,
    );

  return shell(
    <Card className="border-border-strong p-5 sm:p-7">
      {step === 1 && (
        <IdentityStep onCreated={(id) => go(2, { project: id })} />
      )}
      {step === 2 && (
        <SourceStep
          kind="executable"
          onBack={() => go(1)}
          onComplete={() => go(3)}
          projectId={projectId!}
        />
      )}
      {step === 3 && (
        <SourceStep
          kind="documentation"
          onBack={() => go(2)}
          onComplete={() => go(4)}
          projectId={projectId!}
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
          onBack={() => go(4)}
          onComplete={() => go(6)}
          projectId={projectId!}
        />
      )}
      {step === 6 && (
        <StartBuildStep
          existingBuildId={buildId}
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
          accessConfigured={access.data?.configured ?? false}
          onBack={() => go(8)}
          onComplete={() => go(10)}
          onToken={setOneTimeToken}
          oneTimeToken={oneTimeToken}
          projectId={projectId!}
        />
      )}
      {step === 10 && (
        <DeployStep
          accessConfigured={access.data?.configured ?? false}
          buildId={buildId}
          deployments={deployments.data ?? []}
          onBack={() => go(9)}
          projectId={projectId!}
        />
      )}
    </Card>,
  );
}

function IdentityStep({
  onCreated,
}: {
  onCreated: (projectId: string) => void;
}) {
  const form = useForm<IdentityValues>({
    resolver: zodResolver(identitySchema),
    defaultValues: { name: "", slug: "", description: "" },
  });
  const create = useMutation({
    mutationFn: projectApi.create,
    onSuccess: (project) => onCreated(project.id),
  });
  return (
    <form
      noValidate
      onSubmit={form.handleSubmit((values) => create.mutate(values))}
    >
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
      {create.error && (
        <Alert className="mt-5" tone="danger">
          {create.error.message}
        </Alert>
      )}
      <StepActions>
        <Button disabled={create.isPending} type="submit">
          {create.isPending ? "Creating project…" : "Create and continue"}
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
}: {
  projectId: string;
  kind: "executable" | "documentation";
  onBack: () => void;
  onComplete: () => void;
}) {
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
  const create = useMutation({
    mutationFn: () =>
      origin === "url"
        ? sourceApi.createFromUrl(projectId, {
            name,
            kind: sourceKind,
            source_url: url,
            is_primary: kind === "executable",
          })
        : sourceApi.createFromUpload(projectId, {
            name,
            kind: sourceKind,
            file: file!,
            is_primary: kind === "executable",
          }),
    onSuccess: onComplete,
  });
  const canSubmit =
    name.trim() &&
    (origin === "url" ? /^https?:\/\//.test(url) : Boolean(file) && !fileError);
  return (
    <div>
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
                  ? `${file.name} · ${(file.size / 1_000_000).toFixed(2)} MB`
                  : kind === "documentation"
                    ? `JSON, Markdown, TXT, CSV, XLSX, DOCX, HTML, or PDF · ${MAX_UPLOAD_LABEL} maximum.`
                    : `OpenAPI 3.x or API Inventory v1 JSON/YAML · ${MAX_UPLOAD_LABEL} maximum.`}
              </FieldHelp>
            )}
          </div>
        )}
      </div>
      {create.error && (
        <Alert className="mt-5" tone="danger">
          {create.error.message}
        </Alert>
      )}
      <StepActions back={onBack}>
        <div className="flex flex-wrap gap-2">
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
  const form = useForm<ServerValues>({
    resolver: zodResolver(serverSchema),
    defaultValues: { default_base_url: defaultValue },
  });
  const update = useMutation({
    mutationFn: (values: ServerValues) => projectApi.update(projectId, values),
    onSuccess: onComplete,
  });
  return (
    <form
      noValidate
      onSubmit={form.handleSubmit((values) => update.mutate(values))}
    >
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
        <Label htmlFor="base-url">Base URL</Label>
        <Input
          id="base-url"
          inputMode="url"
          placeholder="https://inventory.example.com/api"
          type="url"
          {...form.register("default_base_url")}
          aria-invalid={Boolean(form.formState.errors.default_base_url)}
        />
        <FieldHelp>
          Use the exact server selected from the source or an explicitly
          configured equivalent.
        </FieldHelp>
        {form.formState.errors.default_base_url && (
          <FieldError>
            {form.formState.errors.default_base_url.message}
          </FieldError>
        )}
      </div>
      {update.error && (
        <Alert className="mt-5" tone="danger">
          {update.error.message}
        </Alert>
      )}
      <StepActions back={onBack}>
        <Button disabled={update.isPending} type="submit">
          Save server
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
}: {
  projectId: string;
  onBack: () => void;
  onComplete: () => void;
}) {
  const form = useForm<CredentialValues>({
    resolver: zodResolver(credentialSchema),
    defaultValues: {
      name: "Primary upstream credential",
      scheme_type: "bearer",
      primary_secret: "",
      secondary_secret: "",
      token_url: "",
      scope: "",
      header_name: "",
    },
  });
  const scheme = form.watch("scheme_type");
  const create = useMutation({
    mutationFn: (values: CredentialValues) => {
      const credential = credentialSecretFor(values.scheme_type, {
        value: values.primary_secret,
        identity: values.secondary_secret,
        tokenUrl: values.token_url,
        scope: values.scope,
        headerName: values.header_name,
      });
      return credentialApi.create(projectId, {
        name: values.name,
        scheme_type: values.scheme_type,
        ...credential,
      });
    },
    onSuccess: onComplete,
  });
  const secondaryLabel =
    scheme === "basic"
      ? "Username"
      : scheme === "oauth2_client_credentials"
        ? "Client ID"
        : null;
  return (
    <form
      noValidate
      onSubmit={form.handleSubmit((values) => create.mutate(values))}
    >
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
      <div className="grid gap-5 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="credential-name">Credential name</Label>
          <Input id="credential-name" {...form.register("name")} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="scheme">Authentication scheme</Label>
          <Select id="scheme" {...form.register("scheme_type")}>
            <option value="bearer">Bearer token</option>
            <option value="api_key_header">API key header</option>
            <option value="api_key_query">API key query</option>
            <option value="basic">HTTP Basic</option>
            <option value="oauth2_client_credentials">
              OAuth client credentials
            </option>
            <option value="static_headers">Static secret header</option>
          </Select>
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
            <Label htmlFor="token-url">Token URL</Label>
            <Input
              id="token-url"
              inputMode="url"
              type="url"
              {...form.register("token_url")}
            />
            {form.formState.errors.token_url && (
              <FieldError>{form.formState.errors.token_url.message}</FieldError>
            )}
            <Label htmlFor="oauth-scope">Scope (optional)</Label>
            <Input id="oauth-scope" {...form.register("scope")} />
          </div>
        )}
      </div>
      <Alert className="mt-5" tone="info">
        MCP inbound access is configured separately in step 9. Upstream
        credentials never become tool arguments or manifest fields.
      </Alert>
      {create.error && (
        <Alert className="mt-5" tone="danger">
          {create.error.message}
        </Alert>
      )}
      <StepActions back={onBack}>
        <div className="flex flex-wrap gap-2">
          <Button onClick={onComplete} variant="ghost">
            API requires no authentication
          </Button>
          <Button disabled={create.isPending} type="submit">
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
  const start = useMutation({
    mutationFn: () => buildApi.create(projectId),
    onSuccess: (build) => onStarted(build.id),
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
      {start.error && (
        <Alert className="mt-5" tone="danger">
          {start.error.message}
        </Alert>
      )}
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
        <Alert title="Build status is unavailable" tone="danger">
          {error.message}
        </Alert>
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
      <BuildProgress status={build.status} />
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
        <Alert title="Validation report is unavailable" tone="danger">
          {error.message}
        </Alert>
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
      <div className="grid gap-3 sm:grid-cols-4">
        <Metric label="Source" value={report.operation_source_count} />
        <Metric label="Excluded" value={report.operation_excluded_count} />
        <Metric label="Generated" value={report.operation_generated_count} />
        <Metric label="Blocking" value={report.blocking_error_count} />
      </div>
      {valid ? (
        <Alert className="mt-5" title="Validation passed" tone="success">
          Executable coverage, manifest structure, and runtime compatibility
          passed the configured checks.
        </Alert>
      ) : (
        <Alert
          className="mt-5"
          title="Deployment remains blocked"
          tone="danger"
        >
          Resolve blocking findings or explicitly exclude unsupported operations
          with a reason.
        </Alert>
      )}
      <StepActions back={onBack}>
        <Button disabled={!valid} onClick={onContinue}>
          Configure MCP access
          <ArrowRight aria-hidden="true" className="size-4" />
        </Button>
      </StepActions>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-border bg-input p-4">
      <p className="font-mono text-[0.65rem] uppercase tracking-[0.1em] text-muted">
        {label}
      </p>
      <p className="mt-2 text-2xl font-semibold text-foreground">{value}</p>
    </div>
  );
}

function AccessStep({
  projectId,
  accessConfigured,
  oneTimeToken,
  onToken,
  onBack,
  onComplete,
}: {
  projectId: string;
  accessConfigured: boolean;
  oneTimeToken: McpAccessToken | null;
  onToken: (token: McpAccessToken) => void;
  onBack: () => void;
  onComplete: () => void;
}) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("Primary MCP client");
  const configure = useMutation({
    mutationFn: () =>
      deploymentApi.setAuthMode(projectId, { mode: "static_bearer" }),
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: ["projects", projectId, "mcp-access"],
      }),
  });
  const token = useMutation({
    mutationFn: () => deploymentApi.createToken(projectId, { name }),
    onSuccess: (value) => {
      onToken(value);
      void queryClient.invalidateQueries({
        queryKey: ["projects", projectId, "mcp-access"],
      });
    },
  });
  const copy = async () => {
    if (oneTimeToken?.token)
      await navigator.clipboard.writeText(oneTimeToken.token);
  };
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
      {oneTimeToken?.token && (
        <Alert className="mt-5" title="Copy this token now" tone="warning">
          <p>
            This plaintext value is shown once and will not be recoverable
            later.
          </p>
          <div className="mt-3 flex gap-2">
            <code className="min-w-0 flex-1 overflow-x-auto rounded bg-canvas px-3 py-2 font-mono text-xs text-foreground">
              {oneTimeToken.token}
            </code>
            <Button
              aria-label="Copy access token"
              onClick={() => void copy()}
              size="icon"
              variant="outline"
            >
              <Clipboard aria-hidden="true" className="size-4" />
            </Button>
          </div>
        </Alert>
      )}
      {(configure.error || token.error) && (
        <Alert className="mt-5" tone="danger">
          {configure.error?.message ?? token.error?.message}
        </Alert>
      )}
      <StepActions back={onBack}>
        <Button
          disabled={!accessConfigured && !oneTimeToken?.token}
          onClick={onComplete}
        >
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
  accessConfigured,
  deployments,
  onBack,
}: {
  projectId: string;
  buildId: string | null;
  accessConfigured: boolean;
  deployments: Awaited<ReturnType<typeof deploymentApi.list>>;
  onBack: () => void;
}) {
  const queryClient = useQueryClient();
  const deploy = useMutation({
    mutationFn: () => deploymentApi.deploy(projectId, buildId!),
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: ["projects", projectId, "deployments"],
      }),
  });
  const latest = deployments[0];
  const canDeploy = Boolean(buildId) && accessConfigured;
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
      {latest && (
        <div className="rounded-lg border border-border bg-input p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-foreground">
                {latest.hostname}
              </p>
              <p className="mt-1 font-mono text-xs text-muted">
                Build {latest.build_sequence ?? latest.build_id}
              </p>
            </div>
            <DeploymentStatusBadge status={latest.status} />
          </div>
        </div>
      )}
      {!accessConfigured && (
        <Alert className="mt-5" tone="danger">
          Inbound MCP authentication is not configured. Return to step 9 before
          deploying.
        </Alert>
      )}
      {deploy.error && (
        <Alert className="mt-5" tone="danger">
          {deploy.error.message}
        </Alert>
      )}
      {latest?.status === "RUNNING" && (
        <Alert className="mt-5" title="MCP runtime is healthy" tone="success">
          The endpoint is ready for an authenticated external MCP client.
          Builder OpenRouter and Milvus availability do not affect runtime
          execution.
        </Alert>
      )}
      <StepActions back={onBack}>
        <div className="flex flex-wrap gap-2">
          {latest?.status === "RUNNING" && (
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
              ["PENDING", "DEPLOYING", "HEALTHCHECK"].includes(
                latest?.status ?? "",
              )
            }
            onClick={() => deploy.mutate()}
          >
            {deploy.isPending
              ? "Starting deployment…"
              : latest
                ? "Deploy replacement"
                : "Deploy runtime"}
            <Rocket aria-hidden="true" className="size-4" />
          </Button>
        </div>
      </StepActions>
    </div>
  );
}
