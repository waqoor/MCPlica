import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Plus, RefreshCw, Trash2 } from "lucide-react";
import { useState } from "react";
import type { Credential } from "@/api/contracts";
import {
  credentialApi,
  credentialSecretFor,
  type CredentialScheme,
} from "@/api/credentials";
import { useAuth } from "@/auth/use-auth";
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
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [dialog, setDialog] = useState<{
    mode: "create" | "rotate" | "revoke";
    credential?: Credential;
  } | null>(null);
  const credentials = useQuery({
    queryKey: ["projects", project.id, "credentials"],
    queryFn: ({ signal }) => credentialApi.list(project.id, signal),
  });
  const invalidate = () =>
    queryClient.invalidateQueries({
      queryKey: ["projects", project.id, "credentials"],
    });
  const revoke = useMutation({
    mutationFn: (id: string) => credentialApi.revoke(project.id, id),
    onSuccess: () => {
      setDialog(null);
      void invalidate();
    },
  });
  if (credentials.isPending)
    return <QueryPending label="Loading credential metadata" />;
  if (credentials.error)
    return (
      <QueryError
        error={credentials.error}
        onRetry={() => void credentials.refetch()}
      />
    );
  const admin = user?.role === "admin";
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
      {!admin && (
        <Alert tone="info">
          Builder access can inspect credential configuration status but cannot
          create, rotate, reveal, or revoke secrets.
        </Alert>
      )}
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
                    credential.revoked_at
                      ? "danger"
                      : credential.configured
                        ? "success"
                        : "warning"
                  }
                >
                  {credential.revoked_at
                    ? "Revoked"
                    : credential.configured
                      ? "Configured"
                      : "Incomplete"}
                </Badge>
              </CardHeader>
              <dl className="space-y-2 text-sm">
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
            {revoke.error && (
              <Alert tone="danger">{revoke.error.message}</Alert>
            )}
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
  const [tokenUrl, setTokenUrl] = useState("");
  const [scope, setScope] = useState("");
  const [headerName, setHeaderName] = useState(
    typeof credential?.metadata.name === "string"
      ? credential.metadata.name
      : "",
  );
  const parts = () =>
    credentialSecretFor(scheme, {
      value: secret,
      identity,
      tokenUrl,
      scope,
      headerName,
    });
  const save = useMutation({
    mutationFn: () =>
      mode === "create"
        ? credentialApi.create(projectId, {
            name,
            scheme_type: scheme,
            ...parts(),
          })
        : credentialApi.rotate(projectId, credential!.id, parts().secret),
    onSuccess: onSaved,
  });
  return (
    <div className="space-y-4">
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
            <Label htmlFor="credential-dialog-scheme">Scheme</Label>
            <Select
              id="credential-dialog-scheme"
              onChange={(event) =>
                setScheme(event.target.value as CredentialScheme)
              }
              value={scheme}
            >
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
            value={headerName}
          />
        </div>
      )}
      {scheme === "oauth2_client_credentials" && (
        <div className="space-y-2">
          <Label htmlFor="credential-dialog-token-url">Token URL</Label>
          <Input
            id="credential-dialog-token-url"
            onChange={(event) => setTokenUrl(event.target.value)}
            type="url"
            value={tokenUrl}
          />
          <Label htmlFor="credential-dialog-scope">Scope (optional)</Label>
          <Input
            id="credential-dialog-scope"
            onChange={(event) => setScope(event.target.value)}
            value={scope}
          />
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
      {save.error && <Alert tone="danger">{save.error.message}</Alert>}
      <Button
        className="w-full"
        disabled={
          !secret ||
          (mode === "create" && !name.trim()) ||
          (["basic", "oauth2_client_credentials"].includes(scheme) &&
            !identity.trim()) ||
          (["api_key_header", "api_key_query", "static_headers"].includes(
            scheme,
          ) &&
            !headerName.trim()) ||
          (scheme === "oauth2_client_credentials" &&
            !/^https?:\/\//.test(tokenUrl)) ||
          save.isPending
        }
        onClick={() => save.mutate()}
      >
        {save.isPending
          ? "Saving…"
          : mode === "create"
            ? "Save credential"
            : "Rotate credential"}
      </Button>
    </div>
  );
}
