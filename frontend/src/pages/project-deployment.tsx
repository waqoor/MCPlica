import { useMutation, useQueries, useQueryClient } from "@tanstack/react-query";
import {
  Clipboard,
  KeyRound,
  Play,
  RefreshCw,
  RotateCcw,
  Square,
  Trash2,
} from "lucide-react";
import { useMemo, useState } from "react";
import type { Deployment, McpAccessToken, McpAuthMode } from "@/api/contracts";
import { deploymentApi } from "@/api/deployments";
import { buildApi } from "@/api/builds";
import { settingsApi } from "@/api/settings";
import { useAuth } from "@/auth/use-auth";
import { QueryError, QueryPending } from "@/components/query-state";
import {
  BuildStatusBadge,
  DeploymentStatusBadge,
  HealthBadge,
} from "@/components/status-badge";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { useProject } from "@/features/projects/project-context";
import { formatDate, shortenHash } from "@/lib/format";
import { buildCanDeploy, canDeploy } from "@/lib/lifecycle";

export function ProjectDeploymentPage() {
  const project = useProject();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [oneTimeToken, setOneTimeToken] = useState<McpAccessToken | null>(null);
  const [selectedBuild, setSelectedBuild] = useState("");
  const [confirm, setConfirm] = useState<{
    action: "stop" | "restart" | "rollback" | "revoke";
    item: Deployment | McpAccessToken;
  } | null>(null);
  const [builds, deployments, access, settings] = useQueries({
    queries: [
      {
        queryKey: ["projects", project.id, "builds"],
        queryFn: ({ signal }: { signal: AbortSignal }) =>
          buildApi.list(project.id, signal),
      },
      {
        queryKey: ["projects", project.id, "deployments"],
        queryFn: ({ signal }: { signal: AbortSignal }) =>
          deploymentApi.list(project.id, signal),
        refetchInterval: 5_000,
      },
      {
        queryKey: ["projects", project.id, "mcp-access"],
        queryFn: ({ signal }: { signal: AbortSignal }) =>
          deploymentApi.access(project.id, signal),
      },
      {
        queryKey: ["settings"],
        queryFn: ({ signal }: { signal: AbortSignal }) =>
          settingsApi.get(signal),
        retry: false,
      },
    ],
  });
  const readyBuilds = useMemo(
    () => builds.data?.filter((build) => build.status === "READY") ?? [],
    [builds.data],
  );
  const buildId = selectedBuild || readyBuilds[0]?.id || "";
  const permitted = canDeploy(
    user,
    settings.data?.builders_can_deploy ?? false,
  );
  const invalidate = () =>
    Promise.all([
      queryClient.invalidateQueries({
        queryKey: ["projects", project.id, "deployments"],
      }),
      queryClient.invalidateQueries({
        queryKey: ["projects", project.id, "mcp-access"],
      }),
    ]);
  const deploy = useMutation({
    mutationFn: () => deploymentApi.deploy(project.id, buildId),
    onSuccess: invalidate,
  });
  const stop = useMutation({
    mutationFn: (id: string) => deploymentApi.stop(id),
    onSuccess: invalidate,
  });
  const restart = useMutation({
    mutationFn: (id: string) => deploymentApi.restart(id),
    onSuccess: invalidate,
  });
  const rollback = useMutation({
    mutationFn: (id: string) => deploymentApi.rollback(project.id, id),
    onSuccess: invalidate,
  });
  const revokeToken = useMutation({
    mutationFn: (id: string) => deploymentApi.revokeToken(project.id, id),
    onSuccess: invalidate,
  });
  const latest = deployments.data?.[0];
  const actionError =
    deploy.error ??
    stop.error ??
    restart.error ??
    rollback.error ??
    revokeToken.error;

  if (builds.isPending || deployments.isPending || access.isPending)
    return <QueryPending label="Loading deployment state" />;
  if (builds.error)
    return (
      <QueryError error={builds.error} onRetry={() => void builds.refetch()} />
    );
  if (deployments.error)
    return (
      <QueryError
        error={deployments.error}
        onRetry={() => void deployments.refetch()}
      />
    );
  if (access.error)
    return (
      <QueryError error={access.error} onRetry={() => void access.refetch()} />
    );

  function confirmAction() {
    if (!confirm) return;
    if (confirm.action === "stop") stop.mutate(confirm.item.id);
    if (confirm.action === "restart") restart.mutate(confirm.item.id);
    if (confirm.action === "rollback") rollback.mutate(confirm.item.id);
    if (confirm.action === "revoke") revokeToken.mutate(confirm.item.id);
    setConfirm(null);
  }

  return (
    <div className="min-w-0 space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-foreground">
          Deployment and MCP access
        </h2>
        <p className="mt-1 text-sm text-muted">
          Runtime lifecycle, endpoint authentication, and build selection remain
          explicit and independently auditable.
        </p>
      </div>
      {access.data.mode === "disabled_dev" && (
        <Alert title="Unauthenticated development mode" tone="danger">
          This mode is forbidden for internet-exposed or production MCP
          endpoints.
        </Alert>
      )}
      <div className="grid gap-5 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Current runtime</CardTitle>
              <p className="mt-1 text-xs text-muted">
                Health-before-switch protects the active build during
                replacement.
              </p>
            </div>
            {latest ? (
              <DeploymentStatusBadge status={latest.status} />
            ) : (
              <Badge>Not deployed</Badge>
            )}
          </CardHeader>
          {latest ? (
            <dl className="space-y-3 text-sm">
              <Fact
                label="Endpoint"
                value={latest.endpoint_url ?? `https://${latest.hostname}/mcp`}
                mono
              />
              <Fact
                label="Health"
                value={
                  <HealthBadge status={latest.health_status ?? latest.status} />
                }
              />
              <Fact
                label="Build"
                value={`#${latest.build_sequence ?? latest.build_id}`}
              />
              <Fact
                label="Image"
                value={latest.image_digest ?? latest.image_ref}
                mono
              />
              <Fact
                label="Manifest"
                value={shortenHash(latest.manifest_sha256)}
                mono
              />
            </dl>
          ) : (
            <EmptyState
              description="Choose a READY build and configure inbound MCP authentication before deploying."
              icon={Play}
              title="No active runtime"
            />
          )}
          {latest && (
            <div className="mt-5 flex flex-wrap gap-2 border-t border-border pt-4">
              <Button
                disabled={!permitted || latest.status === "STOPPED"}
                onClick={() => setConfirm({ action: "restart", item: latest })}
                size="sm"
                variant="outline"
              >
                <RefreshCw aria-hidden="true" className="size-4" />
                Restart
              </Button>
              <Button
                disabled={!permitted || latest.status === "STOPPED"}
                onClick={() => setConfirm({ action: "stop", item: latest })}
                size="sm"
                variant="destructive"
              >
                <Square aria-hidden="true" className="size-4" />
                Stop
              </Button>
              {latest.endpoint_url && (
                <Button
                  onClick={() =>
                    void navigator.clipboard.writeText(latest.endpoint_url!)
                  }
                  size="sm"
                  variant="ghost"
                >
                  <Clipboard aria-hidden="true" className="size-4" />
                  Copy endpoint
                </Button>
              )}
            </div>
          )}
        </Card>
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Deploy a READY build</CardTitle>
              <p className="mt-1 text-xs text-muted">
                A failed build can never replace a healthy deployment.
              </p>
            </div>
            <KeyRound aria-hidden="true" className="size-5 text-warning" />
          </CardHeader>
          <div className="space-y-2">
            <Label htmlFor="deploy-build">Build</Label>
            <Select
              disabled={!readyBuilds.length}
              id="deploy-build"
              onChange={(event) => setSelectedBuild(event.target.value)}
              value={buildId}
            >
              {readyBuilds.length ? (
                readyBuilds.map((build) => (
                  <option key={build.id} value={build.id}>
                    Build #{build.sequence} · {formatDate(build.completed_at)}
                  </option>
                ))
              ) : (
                <option value="">No READY builds</option>
              )}
            </Select>
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Button
              disabled={
                !permitted ||
                !buildCanDeploy(
                  readyBuilds.find((build) => build.id === buildId),
                  access.data.configured,
                ) ||
                deploy.isPending
              }
              onClick={() => deploy.mutate()}
            >
              {deploy.isPending
                ? "Starting replacement…"
                : latest
                  ? "Deploy replacement"
                  : "Deploy runtime"}
            </Button>
            {readyBuilds[0] && (
              <BuildStatusBadge status={readyBuilds[0].status} />
            )}
          </div>
          {!access.data.configured && (
            <Alert className="mt-4" tone="warning">
              Configure an MCP auth mode and active verifier/token before
              deployment.
            </Alert>
          )}
          {!permitted && (
            <Alert className="mt-4" tone="warning">
              Your Builder role does not have deployment permission in
              installation settings.
            </Alert>
          )}
        </Card>
      </div>
      <AccessConfiguration
        access={access.data}
        onChanged={invalidate}
        onToken={setOneTimeToken}
        oneTimeToken={oneTimeToken}
        projectId={project.id}
        onRevoke={(token) => setConfirm({ action: "revoke", item: token })}
      />
      {actionError && <Alert tone="danger">{actionError.message}</Alert>}
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Deployment history</CardTitle>
            <p className="mt-1 text-xs text-muted">
              Rollback creates a new deployment and never mutates historical
              builds.
            </p>
          </div>
        </CardHeader>
        {deployments.data.length ? (
          <div className="max-w-full overflow-x-auto">
            <table className="w-full min-w-[46rem] text-left">
              <thead className="font-mono text-[0.64rem] uppercase tracking-[0.1em] text-muted">
                <tr>
                  <th className="pb-3">Created</th>
                  <th className="pb-3">Build</th>
                  <th className="pb-3">Status</th>
                  <th className="pb-3">Health</th>
                  <th className="pb-3">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {deployments.data.map((deployment) => (
                  <tr key={deployment.id}>
                    <td className="py-3 text-sm text-muted">
                      {formatDate(deployment.created_at)}
                    </td>
                    <td className="py-3 text-sm text-foreground">
                      #
                      {deployment.build_sequence ??
                        deployment.build_id.slice(0, 8)}
                    </td>
                    <td className="py-3">
                      <DeploymentStatusBadge status={deployment.status} />
                    </td>
                    <td className="py-3">
                      <HealthBadge status={deployment.health_status} />
                    </td>
                    <td className="py-3 text-right">
                      {deployment.id !== latest?.id &&
                        deployment.status !== "FAILED" && (
                          <Button
                            disabled={!permitted}
                            onClick={() =>
                              setConfirm({
                                action: "rollback",
                                item: deployment,
                              })
                            }
                            size="sm"
                            variant="ghost"
                          >
                            <RotateCcw aria-hidden="true" className="size-4" />
                            Rollback
                          </Button>
                        )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-muted">
            No deployment events have been recorded.
          </p>
        )}
      </Card>
      <Dialog
        description="This lifecycle change is durable and creates an audit event."
        onClose={() => setConfirm(null)}
        open={Boolean(confirm)}
        title={
          confirm
            ? `${confirm.action[0].toUpperCase()}${confirm.action.slice(1)} confirmation`
            : "Confirm action"
        }
      >
        <div className="space-y-4">
          <Alert tone="warning">
            Confirm the selected {confirm?.action} operation. Existing healthy
            runtime protection remains enforced by the backend state machine.
          </Alert>
          <div className="flex justify-end gap-2">
            <Button onClick={() => setConfirm(null)} variant="ghost">
              Cancel
            </Button>
            <Button
              onClick={confirmAction}
              variant={
                confirm?.action === "stop" || confirm?.action === "revoke"
                  ? "destructive"
                  : "primary"
              }
            >
              Confirm {confirm?.action}
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  );
}

function AccessConfiguration({
  access,
  projectId,
  oneTimeToken,
  onToken,
  onChanged,
  onRevoke,
}: {
  access: Awaited<ReturnType<typeof deploymentApi.access>>;
  projectId: string;
  oneTimeToken: McpAccessToken | null;
  onToken: (token: McpAccessToken) => void;
  onChanged: () => Promise<unknown>;
  onRevoke: (token: McpAccessToken) => void;
}) {
  const [mode, setMode] = useState<McpAuthMode>(access.mode);
  const [issuer, setIssuer] = useState(access.issuer_url ?? "");
  const [audiences, setAudiences] = useState(access.audiences.join(", "));
  const [scopes, setScopes] = useState(access.required_scopes.join(", "));
  const [tokenName, setTokenName] = useState("Primary MCP client");
  const configure = useMutation({
    mutationFn: () =>
      deploymentApi.setAuthMode(projectId, {
        mode,
        issuer_url: issuer || undefined,
        audiences: audiences
          .split(",")
          .map((value) => value.trim())
          .filter(Boolean),
        required_scopes: scopes
          .split(",")
          .map((value) => value.trim())
          .filter(Boolean),
      }),
    onSuccess: onChanged,
  });
  const create = useMutation({
    mutationFn: () => deploymentApi.createToken(projectId, { name: tokenName }),
    onSuccess: (token) => {
      onToken(token);
      void onChanged();
    },
  });
  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>MCP inbound access</CardTitle>
          <p className="mt-1 text-xs text-muted">
            Saved token values are never redisplayed. Rotate instead of
            revealing.
          </p>
        </div>
        <Badge tone={access.configured ? "success" : "warning"}>
          {access.configured ? "Configured" : "Required"}
        </Badge>
      </CardHeader>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="auth-mode">Authentication mode</Label>
          <Select
            id="auth-mode"
            onChange={(event) => setMode(event.target.value as McpAuthMode)}
            value={mode}
          >
            <option value="static_bearer">Static bearer</option>
            <option value="external_oauth_oidc">External OAuth/OIDC</option>
            {access.development_mode && (
              <option value="disabled_dev">Disabled (development only)</option>
            )}
          </Select>
        </div>
        {mode === "external_oauth_oidc" && (
          <>
            <div className="space-y-2">
              <Label htmlFor="issuer-url">Issuer URL</Label>
              <Input
                id="issuer-url"
                onChange={(event) => setIssuer(event.target.value)}
                type="url"
                value={issuer}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="audiences">Audiences</Label>
              <Input
                id="audiences"
                onChange={(event) => setAudiences(event.target.value)}
                placeholder="api://mcplica"
                value={audiences}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="scopes">Required scopes</Label>
              <Input
                id="scopes"
                onChange={(event) => setScopes(event.target.value)}
                placeholder="mcp:invoke"
                value={scopes}
              />
            </div>
          </>
        )}
      </div>
      <Button
        className="mt-4"
        disabled={
          configure.isPending || (mode === "external_oauth_oidc" && !issuer)
        }
        onClick={() => configure.mutate()}
        variant="outline"
      >
        Save auth mode
      </Button>
      {mode === "static_bearer" && (
        <div className="mt-6 border-t border-border pt-5">
          <div className="flex flex-col gap-2 sm:flex-row">
            <div className="flex-1">
              <Label className="sr-only" htmlFor="access-token-name">
                Token name
              </Label>
              <Input
                id="access-token-name"
                onChange={(event) => setTokenName(event.target.value)}
                value={tokenName}
              />
            </div>
            <Button
              disabled={!tokenName.trim() || create.isPending}
              onClick={() => create.mutate()}
            >
              Create token
            </Button>
          </div>
          {oneTimeToken?.token && (
            <Alert className="mt-4" title="Copy this token now" tone="warning">
              <p>
                It is shown once. Store it in the external MCP client's secret
                manager.
              </p>
              <div className="mt-3 flex gap-2">
                <code className="min-w-0 flex-1 overflow-x-auto rounded bg-canvas p-2 font-mono text-xs text-foreground">
                  {oneTimeToken.token}
                </code>
                <Button
                  aria-label="Copy token"
                  onClick={() =>
                    void navigator.clipboard.writeText(oneTimeToken.token!)
                  }
                  size="icon"
                  variant="outline"
                >
                  <Clipboard aria-hidden="true" className="size-4" />
                </Button>
              </div>
            </Alert>
          )}
          <div className="mt-4 space-y-2">
            {access.tokens
              ?.filter((token) => !token.revoked_at)
              .map((token) => (
                <div
                  className="flex items-center justify-between rounded-md border border-border bg-input px-3 py-2"
                  key={token.id}
                >
                  <div>
                    <p className="text-sm text-foreground">{token.name}</p>
                    <p className="font-mono text-xs text-muted">
                      {token.token_prefix}… · rotated{" "}
                      {formatDate(token.created_at)}
                    </p>
                  </div>
                  <Button
                    aria-label={`Revoke ${token.name}`}
                    onClick={() => onRevoke(token)}
                    size="icon"
                    variant="ghost"
                  >
                    <Trash2
                      aria-hidden="true"
                      className="size-4 text-danger-soft"
                    />
                  </Button>
                </div>
              ))}
          </div>
        </div>
      )}
      {(configure.error || create.error) && (
        <Alert className="mt-4" tone="danger">
          {configure.error?.message ?? create.error?.message}
        </Alert>
      )}
    </Card>
  );
}

function Fact({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="flex justify-between gap-4 border-b border-border pb-3 last:border-0 last:pb-0">
      <dt className="text-muted">{label}</dt>
      <dd
        className={
          mono
            ? "max-w-[68%] break-all text-right font-mono text-xs text-foreground"
            : "max-w-[68%] text-right text-foreground"
        }
      >
        {value}
      </dd>
    </div>
  );
}
