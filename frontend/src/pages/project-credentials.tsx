import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Plus, RefreshCw, Trash2 } from "lucide-react";
import { useState } from "react";
import type { Credential } from "@/api/contracts";
import {
  credentialApi,
  credentialSchemeForSource,
  credentialSecretFor,
  type CredentialScheme,
} from "@/api/credentials";
import { sourceApi } from "@/api/sources";
import { useCapabilities } from "@/auth/capabilities";
import { MutationError } from "@/components/error-notice";
import { QueryError, QueryPending } from "@/components/query-state";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { FieldHelp, Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { useProject } from "@/features/projects/project-context";
import { formatDate } from "@/lib/format";

export function ProjectCredentialsPage() {
  const project = useProject();
  const capabilities = useCapabilities();
  const queryClient = useQueryClient();
  const [dialog, setDialog] = useState<{
    mode: "create" | "rotate" | "revoke";
    credential?: Credential;
  } | null>(null);
  const credentials = useQuery({
    queryKey: ["projects", project.id, "credentials"],
    queryFn: ({ signal }) => credentialApi.list(project.id, signal),
    refetchInterval: (query) =>
      query.state.data?.some(
        (credential) => credential.runtime_effect_state === "pending",
      )
        ? 5_000
        : false,
    enabled: capabilities.canManageCredentials,
  });
  const invalidate = () =>
    Promise.all([
      queryClient.invalidateQueries({
        queryKey: ["projects", project.id, "credentials"],
      }),
      queryClient.invalidateQueries({
        queryKey: ["projects", project.id, "journey"],
      }),
    ]);
  const revoke = useMutation({
    mutationFn: (id: string) => credentialApi.revoke(project.id, id),
    onSuccess: () => {
      setDialog(null);
      void invalidate();
    },
  });
  if (!capabilities.canManageCredentials)
    return (
      <Alert title="Administrator handoff required" tone="info">
        Upstream authorization records contain security-sensitive metadata and
        are available only to administrators. Ask an administrator to bind the
        discovered source schemes, then return to Builds.
      </Alert>
    );
  if (credentials.isPending)
    return <QueryPending label="Loading credential metadata" />;
  if (credentials.error)
    return (
      <QueryError
        error={credentials.error}
        onRetry={() => void credentials.refetch()}
      />
    );
  const admin = capabilities.canManageCredentials;
  return (
    <div className="space-y-5">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
        <div>
          <h2 className="text-xl font-semibold text-foreground">
            Upstream credentials
          </h2>
          <p className="mt-1 text-sm text-muted">
            Only metadata is readable. Plaintext secrets are never recoverable
            through this UI.
          </p>
        </div>
        {admin && (
          <Button onClick={() => setDialog({ mode: "create" })}>
            <Plus aria-hidden="true" className="size-4" />
            Add credential
          </Button>
        )}
      </div>
      {credentials.data.length === 0 ? (
        <EmptyState
          action={
            admin ? (
              <Button onClick={() => setDialog({ mode: "create" })}>
                Configure credential
              </Button>
            ) : undefined
          }
          description="Add credentials only when the upstream API requires them. MCP inbound access is configured separately."
          icon={KeyRound}
          title="No upstream credentials"
        />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {credentials.data.map((credential) => (
            <Card key={credential.id}>
              <CardHeader>
                <div>
                  <CardTitle>{credential.name}</CardTitle>
                  <p className="mt-1 font-mono text-xs text-muted">
                    {credential.scheme_type}
                  </p>
                </div>
                <Badge
                  tone={
                    credential.runtime_effect_state === "failed"
                      ? "danger"
                      : credential.runtime_effect_state === "pending"
                        ? "warning"
                        : credential.revoked_at
                          ? "danger"
                          : credential.configured
                            ? "success"
                            : "warning"
                  }
                >
                  {credential.runtime_effect_state === "failed"
                    ? "Runtime update failed"
                    : credential.runtime_effect_state === "pending"
                      ? "Runtime update pending"
                      : credential.revoked_at
                        ? "Revoked and effective"
                        : credential.configured
                          ? "Configured"
                          : "Incomplete"}
                </Badge>
              </CardHeader>
              <dl className="space-y-2 text-sm">
                <div className="flex justify-between gap-4">
                  <dt className="text-muted">Source scheme</dt>
                  <dd className="font-mono text-xs text-foreground">
                    {typeof credential.metadata.security_scheme === "string"
                      ? credential.metadata.security_scheme
                      : "Unbound"}
                  </dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-muted">Created</dt>
                  <dd className="text-foreground">
                    {formatDate(credential.created_at)}
                  </dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-muted">Last rotated</dt>
                  <dd className="text-foreground">
                    {formatDate(credential.rotated_at)}
                  </dd>
                </div>
              </dl>
              {credential.runtime_effect_state !== "effective" && (
                <Alert
                  className="mt-4"
                  tone={
                    credential.runtime_effect_state === "failed"
                      ? "danger"
                      : "warning"
                  }
                >
                  {credential.runtime_effect_state === "failed"
                    ? `The runtime change failed${credential.runtime_error_code ? ` (${credential.runtime_error_code})` : ""}. The previous runtime state may still be effective.`
                    : "The control-plane change is saved, but runtime replacement or shutdown is still pending."}
                </Alert>
              )}
              {admin && !credential.revoked_at && (
                <div className="mt-5 flex gap-2 border-t border-border pt-4">
                  <Button
                    onClick={() => setDialog({ mode: "rotate", credential })}
                    size="sm"
                    variant="outline"
                  >
                    <RefreshCw aria-hidden="true" className="size-4" />
                    Rotate
                  </Button>
                  <Button
                    onClick={() => setDialog({ mode: "revoke", credential })}
                    size="sm"
                    variant="destructive"
                  >
                    <Trash2 aria-hidden="true" className="size-4" />
                    Revoke
                  </Button>
                </div>
              )}
            </Card>
          ))}
        </div>
      )}
      <Dialog
        description={
          dialog?.mode === "revoke"
            ? "Revocation may prevent new deployments and can require replacing or stopping an active runtime."
            : "The secret value is accepted once and never redisplayed."
        }
        onClose={() => setDialog(null)}
        open={Boolean(dialog)}
        title={
          dialog?.mode === "create"
            ? "Add upstream credential"
            : dialog?.mode === "rotate"
              ? `Rotate ${dialog.credential?.name}`
              : `Revoke ${dialog?.credential?.name}`
        }
      >
        {dialog?.mode === "revoke" ? (
          <div className="space-y-4">
            <Alert tone="warning">
              Confirm revocation only after coordinating any active runtime
              replacement.
            </Alert>
            {revoke.error && <MutationError error={revoke.error} />}
            <Button
              className="w-full"
              disabled={revoke.isPending}
              onClick={() => revoke.mutate(dialog.credential!.id)}
              variant="destructive"
            >
              Confirm revocation
            </Button>
          </div>
        ) : dialog ? (
          <CredentialSecretForm
            credential={dialog.credential}
            mode={dialog.mode}
            onSaved={() => {
              setDialog(null);
              void invalidate();
            }}
            projectId={project.id}
          />
        ) : null}
      </Dialog>
    </div>
  );
}

function CredentialSecretForm({
  projectId,
  mode,
  credential,
  onSaved,
}: {
  projectId: string;
  mode: "create" | "rotate";
  credential?: Credential;
  onSaved: () => void;
}) {
  const [name, setName] = useState(credential?.name ?? "");
  const [scheme, setScheme] = useState<CredentialScheme>(
    (credential?.scheme_type as CredentialScheme | undefined) ?? "bearer",
  );
  const [secret, setSecret] = useState("");
  const [identity, setIdentity] = useState("");
  const [scope, setScope] = useState(
    typeof credential?.metadata.scope === "string"
      ? credential.metadata.scope
      : "",
  );
  const [sourceSchemeName, setSourceSchemeName] = useState(
    typeof credential?.metadata.security_scheme === "string"
      ? credential.metadata.security_scheme
      : "",
  );
  const [tokenAuthMethod, setTokenAuthMethod] = useState<
    "client_secret_basic" | "client_secret_post"
  >(
    credential?.metadata.token_auth_method === "client_secret_post"
      ? "client_secret_post"
      : "client_secret_basic",
  );
  const [headerName, setHeaderName] = useState(
    typeof credential?.metadata.name === "string"
      ? credential.metadata.name
      : "",
  );
  const discovery = useQuery({
    queryKey: ["projects", projectId, "source-configuration"],
    queryFn: ({ signal }) => sourceApi.configuration(projectId, signal),
  });
  const supportedSchemes =
    discovery.data?.security_schemes.filter(
      (item) => credentialSchemeForSource(item) !== null,
    ) ?? [];
  const sourceScheme = discovery.data?.security_schemes.find(
    (item) => item.name === sourceSchemeName,
  );
  const parts = () =>
    credentialSecretFor(scheme, {
      value: secret,
      identity,
      scope,
      headerName,
      securityScheme: sourceSchemeName,
      tokenAuthMethod,
    });
  const save = useMutation({
    mutationFn: () =>
      mode === "create"
        ? credentialApi.create(projectId, {
            name,
            scheme_type: scheme,
            ...parts(),
          })
        : credentialApi.rotate(projectId, credential!.id, {
            secret: parts().secret,
          }),
    onSuccess: onSaved,
  });
  const canSave = Boolean(
    secret &&
    (mode !== "create" || (name.trim() && sourceSchemeName)) &&
    (!["basic", "oauth2_client_credentials"].includes(scheme) ||
      identity.trim()) &&
    (!["api_key_header", "api_key_query", "static_headers"].includes(scheme) ||
      headerName.trim()) &&
    (mode !== "create" || !discovery.error),
  );
  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        if (canSave && !save.isPending) save.mutate();
      }}
    >
      {mode === "rotate" && (
        <Alert tone="info">
          Source binding, API parameter, OAuth scope, and token method are
          immutable Build inputs. Rotation changes secret material only. Create
          a replacement credential and a new Build to remap authorization.
        </Alert>
      )}
      {mode === "create" && (
        <>
          <div className="space-y-2">
            <Label htmlFor="credential-dialog-name">Name</Label>
            <Input
              autoFocus
              id="credential-dialog-name"
              onChange={(event) => setName(event.target.value)}
              value={name}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="credential-dialog-scheme">
              Source security scheme
            </Label>
            <Select
              id="credential-dialog-scheme"
              onChange={(event) => {
                setSourceSchemeName(event.target.value);
                const selected = supportedSchemes.find(
                  (item) => item.name === event.target.value,
                );
                const selectedType = selected
                  ? credentialSchemeForSource(selected)
                  : null;
                if (selectedType) setScheme(selectedType);
                setHeaderName(selected?.parameter_name ?? "");
              }}
              value={sourceSchemeName}
            >
              <option value="">Select a discovered scheme</option>
              {supportedSchemes.map((item) => (
                <option key={item.name} value={item.name}>
                  {item.name} · {item.type}
                </option>
              ))}
            </Select>
          </div>
        </>
      )}
      {["basic", "oauth2_client_credentials"].includes(scheme) && (
        <div className="space-y-2">
          <Label htmlFor="credential-dialog-identity">
            {scheme === "basic" ? "Username" : "Client ID"}
          </Label>
          <Input
            id="credential-dialog-identity"
            onChange={(event) => setIdentity(event.target.value)}
            value={identity}
          />
        </div>
      )}
      {["api_key_header", "api_key_query", "static_headers"].includes(
        scheme,
      ) && (
        <div className="space-y-2">
          <Label htmlFor="credential-dialog-header">
            {scheme === "api_key_query" ? "Query parameter" : "Header name"}
          </Label>
          <Input
            id="credential-dialog-header"
            onChange={(event) => setHeaderName(event.target.value)}
            readOnly={mode === "rotate" && scheme !== "static_headers"}
            value={headerName}
          />
          {mode === "rotate" && scheme !== "static_headers" && (
            <FieldHelp>
              The source API parameter is fixed for this credential binding.
            </FieldHelp>
          )}
        </div>
      )}
      {scheme === "oauth2_client_credentials" && (
        <div className="space-y-2">
          <Label>Source token endpoint</Label>
          <p className="break-all rounded-md border border-border bg-input px-3 py-2 font-mono text-xs text-muted">
            {sourceScheme?.token_url ??
              "Bound by the immutable source manifest"}
          </p>
          <Label htmlFor="credential-dialog-scope">Scope (optional)</Label>
          <Input
            id="credential-dialog-scope"
            onChange={(event) => setScope(event.target.value)}
            readOnly={mode === "rotate"}
            value={scope}
          />
          {mode === "rotate" && (
            <FieldHelp>
              OAuth scope and token authentication method are fixed for this
              credential binding.
            </FieldHelp>
          )}
          {mode === "create" && (
            <>
              <Label htmlFor="credential-dialog-token-method">
                Token endpoint auth method
              </Label>
              <Select
                id="credential-dialog-token-method"
                onChange={(event) =>
                  setTokenAuthMethod(
                    event.target.value as
                      "client_secret_basic" | "client_secret_post",
                  )
                }
                value={tokenAuthMethod}
              >
                <option value="client_secret_basic">client_secret_basic</option>
                <option value="client_secret_post">client_secret_post</option>
              </Select>
            </>
          )}
        </div>
      )}
      <div className="space-y-2">
        <Label htmlFor="credential-dialog-secret">New secret value</Label>
        <Input
          autoComplete="new-password"
          autoFocus={mode === "rotate"}
          id="credential-dialog-secret"
          onChange={(event) => setSecret(event.target.value)}
          type="password"
          value={secret}
        />
        <FieldHelp>Saved values cannot be revealed later.</FieldHelp>
      </div>
      {save.error && <MutationError error={save.error} />}
      <Button
        className="w-full"
        disabled={!canSave || save.isPending}
        type="submit"
      >
        {save.isPending
          ? "Saving…"
          : mode === "create"
            ? "Save credential"
            : "Rotate credential"}
      </Button>
    </form>
  );
}
