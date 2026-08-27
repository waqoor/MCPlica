import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Clipboard,
  KeyRound,
  Play,
  RefreshCw,
  RotateCcw,
  Square,
  Trash2,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type {
  Build,
  Deployment,
  DeploymentPage,
  McpAccessConfig,
  McpAccessToken,
  McpAuthMode,
} from "@/api/contracts";
import { deploymentApi } from "@/api/deployments";
import { buildApi } from "@/api/builds";
import { useCapabilities } from "@/auth/capabilities";
import { MutationError } from "@/components/error-notice";
import { OneTimeSecretDialog } from "@/components/one-time-secret-dialog";
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
import { FieldError, FieldHelp, Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { useProject } from "@/features/projects/project-context";
import { formatDate, shortenHash } from "@/lib/format";
import {
  hasRollbackCapability,
  resolveDeploymentState,
} from "@/lib/deployment-state";
import { buildCanDeploy } from "@/lib/lifecycle";
import {
  buildMcpAuthModePayload,
  OIDC_SIGNING_ALGORITHMS,
} from "@/lib/mcp-access-form";
import {
  mcpTokenLifecycle,
  tokenExpirationToIso,
} from "@/lib/mcp-token-lifecycle";

export function ProjectDeploymentPage() {
  const project = useProject();
  const capabilities = useCapabilities();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const rawDeploymentPage = Number(searchParams.get("deployment_page") ?? "1");
  const deploymentPage =
    Number.isInteger(rawDeploymentPage) && rawDeploymentPage > 0
      ? rawDeploymentPage
      : 1;
  const [oneTimeToken, setOneTimeToken] = useState<McpAccessToken | null>(null);
  const [confirm, setConfirm] = useState<{
    action: "stop" | "restart" | "rollback" | "revoke";
    item: Deployment | McpAccessToken;
  } | null>(null);
  const builds = useQuery<readonly Build[]>({
    queryKey: ["projects", project.id, "builds"],
    queryFn: ({ signal }) => buildApi.list(project.id, signal),
  });
  const deployments = useQuery<DeploymentPage>({
    queryKey: ["projects", project.id, "deployments", { deploymentPage }],
    queryFn: ({ signal }) =>
      deploymentApi.listPage(
        project.id,
        { page: deploymentPage, page_size: 25 },
        signal,
      ),
    refetchInterval: (query) => (query.state.data?.has_active ? 5_000 : false),
  });
  const access = useQuery<McpAccessConfig>({
    queryKey: [
      "projects",
      project.id,
      "mcp-access",
      capabilities.canManageMcpAccess ? "admin" : "status",
    ],
    queryFn: ({ signal }) =>
      capabilities.canManageMcpAccess
        ? deploymentApi.access(project.id, signal)
        : deploymentApi.accessStatus(project.id, signal),
    refetchInterval: (query) =>
      query.state.data?.runtime_effect_state === "pending" ||
      query.state.data?.tokens?.some(
        (token) => token.runtime_effect_state === "pending",
      )
        ? 5_000
        : false,
  });
  const activeDeployment = useQuery<Deployment>({
    queryKey: ["deployments", project.active_deployment_id],
    queryFn: ({ signal }) =>
      deploymentApi.get(project.active_deployment_id!, signal),
    enabled: Boolean(project.active_deployment_id),
    refetchInterval: (query) =>
      query.state.data &&
      ["PENDING", "DEPLOYING", "HEALTHCHECK", "STOPPING"].includes(
        query.state.data.status,
      )
        ? 5_000
        : false,
  });
  const readyBuilds = useMemo(
    () => builds.data?.filter((build) => build.status === "READY") ?? [],
    [builds.data],
  );
  const buildSequence = (id: string) =>
    builds.data?.find((build) => build.id === id)?.sequence;
  const buildLabel = (id: string) => {
    const sequence = buildSequence(id);
    return sequence === undefined ? "Build unavailable" : `Build #${sequence}`;
  };
  const requestedBuildId = searchParams.get("build") ?? "";
  const buildId =
    readyBuilds.find((build) => build.id === requestedBuildId)?.id ??
    readyBuilds[0]?.id ??
    "";

  useEffect(() => {
    if (!builds.data || requestedBuildId === buildId) return;
    const next = new URLSearchParams(searchParams);
    if (buildId) next.set("build", buildId);
    else next.delete("build");
    setSearchParams(next, { replace: true });
  }, [buildId, builds.data, requestedBuildId, searchParams, setSearchParams]);
  const permitted = capabilities.canDeploy;
  const invalidate = () =>
    Promise.all([
      queryClient.invalidateQueries({
        queryKey: ["projects", project.id, "deployments"],
      }),
      queryClient.invalidateQueries({
        queryKey: ["projects", project.id, "mcp-access"],
      }),
      queryClient.invalidateQueries({
        queryKey: ["projects", project.id],
      }),
      queryClient.invalidateQueries({
        queryKey: ["deployments"],
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
  const { active, newestCandidate: candidate } =
    resolveDeploymentState<Deployment>(
      project.active_deployment_id,
      deployments.data?.items,
      activeDeployment.data,
    );
  const actionError =
    deploy.error ??
    stop.error ??
    restart.error ??
    rollback.error ??
    revokeToken.error;

  if (
    builds.isPending ||
    deployments.isPending ||
    access.isPending ||
    (project.active_deployment_id && activeDeployment.isPending)
  )
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
  if (activeDeployment.error)
    return (
      <QueryError
        error={activeDeployment.error}
        onRetry={() => void activeDeployment.refetch()}
      />
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
            {active ? (
              <DeploymentStatusBadge status={active.status} />
            ) : (
              <Badge>Not deployed</Badge>
            )}
          </CardHeader>
          {active ? (
            <dl className="space-y-3 text-sm">
              <Fact
                label="Endpoint"
                value={active.endpoint_url ?? `https://${active.hostname}/mcp`}
                mono
              />
              <Fact
                label="Health"
                value={
                  <HealthBadge status={active.health_status ?? active.status} />
                }
              />
              <Fact label="Build" value={buildLabel(active.build_id)} />
              <Fact
                label="Image"
                value={active.image_digest ?? active.image_ref}
                mono
              />
              <Fact
                label="Manifest"
                value={shortenHash(active.manifest_sha256)}
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
          {active && (
            <div className="mt-5 flex flex-wrap gap-2 border-t border-border pt-4">
              <Button
                disabled={!permitted || active.status !== "running"}
                onClick={() => setConfirm({ action: "restart", item: active })}
                size="sm"
                variant="outline"
              >
                <RefreshCw aria-hidden="true" className="size-4" />
                Restart
              </Button>
              <Button
                disabled={!permitted || active.status !== "running"}
                onClick={() => setConfirm({ action: "stop", item: active })}
                size="sm"
                variant="destructive"
              >
                <Square aria-hidden="true" className="size-4" />
                Stop
              </Button>
              {active.endpoint_url && (
                <Button
                  onClick={() =>
                    void navigator.clipboard.writeText(active.endpoint_url!)
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
              onChange={(event) => {
                const next = new URLSearchParams(searchParams);
                next.set("build", event.target.value);
                setSearchParams(next);
              }}
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
                : active
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
      {candidate && (
        <Alert title="Newest deployment candidate" tone="info">
          {buildLabel(candidate.build_id)} is {candidate.status.toLowerCase()}.
          It is shown separately because the project still identifies{" "}
          {active ? `deployment ${active.id}` : "no deployment"} as active.
        </Alert>
      )}
      {capabilities.canManageMcpAccess ? (
        <AccessConfiguration
          access={access.data}
          onChanged={invalidate}
          onToken={setOneTimeToken}
          projectId={project.id}
          onRevoke={(token) => setConfirm({ action: "revoke", item: token })}
        />
      ) : (
        <AccessStatus access={access.data} />
      )}
      {actionError && <MutationError error={actionError} />}
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
        {deployments.data.items.length ? (
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
                {deployments.data.items.map((deployment) => (
                  <tr key={deployment.id}>
                    <td className="py-3 text-sm text-muted">
                      {formatDate(deployment.created_at)}
                    </td>
                    <td className="py-3 text-sm text-foreground">
                      {buildLabel(deployment.build_id)}
                    </td>
                    <td className="py-3">
                      <DeploymentStatusBadge status={deployment.status} />
                    </td>
                    <td className="py-3">
                      <HealthBadge status={deployment.health_status} />
                    </td>
                    <td className="py-3 text-right">
                      {deployment.id === active?.id ? (
                        <Badge tone="success">Active runtime</Badge>
                      ) : hasRollbackCapability(deployment) ? (
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
                      ) : deployment.id === candidate?.id ? (
                        <Badge>Newest candidate</Badge>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {deployments.data.total > deployments.data.page_size && (
              <div className="mt-4 flex items-center justify-between">
                <Button
                  disabled={deploymentPage === 1}
                  onClick={() => {
                    const next = new URLSearchParams(searchParams);
                    next.set("deployment_page", String(deploymentPage - 1));
                    setSearchParams(next);
                  }}
                  variant="outline"
                >
                  Previous
                </Button>
                <span className="text-xs text-muted">
                  Page {deployments.data.page} · {deployments.data.total}{" "}
                  deployments
                </span>
                <Button
                  disabled={
                    deploymentPage * deployments.data.page_size >=
                    deployments.data.total
                  }
                  onClick={() => {
                    const next = new URLSearchParams(searchParams);
                    next.set("deployment_page", String(deploymentPage + 1));
                    setSearchParams(next);
                  }}
                  variant="outline"
                >
                  Next
                </Button>
              </div>
            )}
          </div>
        ) : (
          <p className="text-sm text-muted">
            No deployment events have been recorded.
          </p>
        )}
      </Card>
      <OneTimeSecretDialog
        onAcknowledged={() => setOneTimeToken(null)}
        secret={oneTimeToken?.token ?? null}
      />
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

function AccessStatus({
  access,
}: {
  access: Awaited<ReturnType<typeof deploymentApi.accessStatus>>;
}) {
  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>MCP inbound access</CardTitle>
          <p className="mt-1 text-xs text-muted">
            Builders can inspect deployment readiness without receiving token
            inventory or verifier details.
          </p>
        </div>
        <Badge
          tone={
            access.runtime_effect_state === "failed"
              ? "danger"
              : access.runtime_effect_state === "pending"
                ? "warning"
                : access.configured
                  ? "success"
                  : "warning"
          }
        >
          {access.runtime_effect_state === "failed"
            ? "Runtime update failed"
            : access.runtime_effect_state === "pending"
              ? "Runtime update pending"
              : access.configured
                ? "Ready"
                : "Administrator action required"}
        </Badge>
      </CardHeader>
      <Alert
        tone={
          access.runtime_effect_state === "failed"
            ? "danger"
            : access.configured && access.runtime_effect_state === "effective"
              ? "info"
              : "warning"
        }
      >
        {access.runtime_effect_state === "failed"
          ? `The latest inbound-auth runtime transition failed${access.runtime_error_code ? ` (${access.runtime_error_code})` : ""}. Ask an administrator to remediate it before deployment.`
          : access.runtime_effect_state === "pending"
            ? "The saved inbound-auth change is still pending at the runtime boundary. The previous authorization remains authoritative."
            : access.configured
              ? "Inbound MCP access is configured. Secret values and verifier details remain administrator-only."
              : (access.remediation ??
                "Ask an administrator to configure inbound MCP access.")}
      </Alert>
    </Card>
  );
}

function AccessConfiguration({
  access,
  projectId,
  onToken,
  onChanged,
  onRevoke,
}: {
  access: Awaited<ReturnType<typeof deploymentApi.access>>;
  projectId: string;
  onToken: (token: McpAccessToken) => void;
  onChanged: () => Promise<unknown>;
  onRevoke: (token: McpAccessToken) => void;
}) {
  const [mode, setMode] = useState<McpAuthMode>(access.mode);
  const [issuer, setIssuer] = useState(access.issuer_url ?? "");
  const [audiences, setAudiences] = useState(access.audiences.join(", "));
  const [scopes, setScopes] = useState(access.required_scopes.join(", "));
  const [jwksUrl, setJwksUrl] = useState(access.jwks_url ?? "");
  const [algorithms, setAlgorithms] = useState(
    access.allowed_algorithms.join(", "),
  );
  const [tokenName, setTokenName] = useState("Primary MCP client");
  const [tokenExpiry, setTokenExpiry] = useState("");
  const [overlapSeconds, setOverlapSeconds] = useState(300);
  const authPayload = buildMcpAuthModePayload({
    mode,
    issuerUrl: issuer,
    audiences,
    requiredScopes: scopes,
    jwksUrl,
    allowedAlgorithms: algorithms,
  });
  const authIssue = authPayload.success
    ? null
    : (authPayload.error.issues[0]?.message ?? "Complete the OIDC settings.");
  const tokenExpiration = tokenExpirationToIso(tokenExpiry);
  const rotationValid =
    Number.isInteger(overlapSeconds) &&
    overlapSeconds >= 0 &&
    overlapSeconds <= 900;
  const configure = useMutation({
    mutationFn: () => {
      if (!authPayload.success)
        throw new Error(authIssue ?? "Invalid settings");
      return deploymentApi.setAuthMode(projectId, authPayload.data);
    },
    onSuccess: onChanged,
  });
  const create = useMutation({
    mutationFn: () =>
      deploymentApi.createToken(projectId, {
        name: tokenName.trim(),
        expires_at: tokenExpiration.value,
      }),
    onSuccess: (token) => {
      onToken(token);
      void onChanged();
    },
  });
  const rotate = useMutation({
    mutationFn: (token: McpAccessToken) => {
      if (!rotationValid) throw new Error("Rotation overlap is invalid");
      return deploymentApi.rotateToken(projectId, token.id, overlapSeconds);
    },
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
        <Badge
          tone={
            access.runtime_effect_state === "failed"
              ? "danger"
              : access.runtime_effect_state === "pending"
                ? "warning"
                : access.configured
                  ? "success"
                  : "warning"
          }
        >
          {access.runtime_effect_state === "failed"
            ? "Runtime update failed"
            : access.runtime_effect_state === "pending"
              ? "Runtime update pending"
              : access.configured
                ? "Configured"
                : "Required"}
        </Badge>
      </CardHeader>
      {access.runtime_effect_state !== "effective" && (
        <Alert
          className="mb-4"
          tone={access.runtime_effect_state === "failed" ? "danger" : "warning"}
        >
          {access.runtime_effect_state === "failed"
            ? `The inbound-auth runtime transition failed${access.runtime_error_code ? ` (${access.runtime_error_code})` : ""}. The prior runtime authorization remains effective until remediation succeeds.`
            : "The inbound-auth setting is persisted, but it is not effective until runtime replacement or shutdown completes."}
        </Alert>
      )}
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
                aria-invalid={
                  !authPayload.success &&
                  authPayload.error.issues.some(
                    (issue) => issue.path[0] === "issuer_url",
                  )
                }
                id="issuer-url"
                onChange={(event) => setIssuer(event.target.value)}
                type="url"
                value={issuer}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="audiences">Audiences</Label>
              <Input
                aria-invalid={
                  !authPayload.success &&
                  authPayload.error.issues.some(
                    (issue) => issue.path[0] === "audiences",
                  )
                }
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
              <FieldHelp>
                Comma-separated. Leave blank if no scope is required.
              </FieldHelp>
            </div>
            <div className="space-y-2">
              <Label htmlFor="jwks-url">JWKS URL (optional)</Label>
              <Input
                aria-invalid={
                  !authPayload.success &&
                  authPayload.error.issues.some(
                    (issue) => issue.path[0] === "jwks_url",
                  )
                }
                id="jwks-url"
                onChange={(event) => setJwksUrl(event.target.value)}
                placeholder="https://issuer.example/.well-known/jwks.json"
                type="url"
                value={jwksUrl}
              />
              <FieldHelp>
                Leave blank to use OIDC discovery from the issuer.
              </FieldHelp>
            </div>
            <div className="space-y-2 md:col-span-2">
              <Label htmlFor="allowed-algorithms">
                Allowed signing algorithms (optional)
              </Label>
              <Input
                aria-invalid={
                  !authPayload.success &&
                  authPayload.error.issues.some(
                    (issue) => issue.path[0] === "allowed_algorithms",
                  )
                }
                id="allowed-algorithms"
                onChange={(event) => setAlgorithms(event.target.value)}
                placeholder="RS256, ES256"
                value={algorithms}
              />
              <FieldHelp>
                Comma-separated allowlist: {OIDC_SIGNING_ALGORITHMS.join(", ")}.
                Blank uses the server default.
              </FieldHelp>
            </div>
          </>
        )}
      </div>
      {mode === "external_oauth_oidc" && authIssue && (
        <FieldError className="mt-3">{authIssue}</FieldError>
      )}
      <Button
        className="mt-4"
        disabled={configure.isPending || !authPayload.success}
        onClick={() => configure.mutate()}
        variant="outline"
      >
        Save auth mode
      </Button>
      {mode === "static_bearer" && (
        <div className="mt-6 border-t border-border pt-5">
          <form
            className="grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end"
            onSubmit={(event) => {
              event.preventDefault();
              create.mutate();
            }}
          >
            <div className="space-y-2">
              <Label htmlFor="access-token-name">Token name</Label>
              <Input
                id="access-token-name"
                onChange={(event) => setTokenName(event.target.value)}
                value={tokenName}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="access-token-expiry">Expires (optional)</Label>
              <Input
                aria-invalid={Boolean(tokenExpiration.error)}
                id="access-token-expiry"
                onChange={(event) => setTokenExpiry(event.target.value)}
                type="datetime-local"
                value={tokenExpiry}
              />
            </div>
            <Button
              disabled={
                !tokenName.trim() ||
                Boolean(tokenExpiration.error) ||
                create.isPending
              }
              type="submit"
            >
              Create token
            </Button>
            {tokenExpiration.error && (
              <FieldError className="sm:col-span-3">
                {tokenExpiration.error}
              </FieldError>
            )}
          </form>
          <div className="mt-5 max-w-sm space-y-2">
            <Label htmlFor="rotation-overlap">Rotation overlap (seconds)</Label>
            <Input
              aria-invalid={!rotationValid}
              id="rotation-overlap"
              max={900}
              min={0}
              onChange={(event) =>
                setOverlapSeconds(event.currentTarget.valueAsNumber)
              }
              type="number"
              value={Number.isNaN(overlapSeconds) ? "" : overlapSeconds}
            />
            <FieldHelp>
              The replaced token remains valid for this interval while clients
              switch. Use 0 for immediate revocation; maximum 900 seconds.
            </FieldHelp>
            {!rotationValid && (
              <FieldError>Enter a whole number from 0 through 900.</FieldError>
            )}
          </div>
          <div className="mt-4 space-y-2">
            {access.tokens?.length ? (
              access.tokens.map((token) => (
                <AccessTokenRow
                  key={token.id}
                  onRevoke={onRevoke}
                  onRotate={(candidate) => rotate.mutate(candidate)}
                  rotationDisabled={!rotationValid || rotate.isPending}
                  token={token}
                />
              ))
            ) : (
              <p className="text-sm text-muted">
                No static bearer tokens have been issued.
              </p>
            )}
          </div>
        </div>
      )}
      {(configure.error || create.error || rotate.error) && (
        <MutationError
          error={configure.error ?? create.error ?? rotate.error}
        />
      )}
    </Card>
  );
}

function AccessTokenRow({
  token,
  rotationDisabled,
  onRotate,
  onRevoke,
}: {
  readonly token: McpAccessToken;
  readonly rotationDisabled: boolean;
  readonly onRotate: (token: McpAccessToken) => void;
  readonly onRevoke: (token: McpAccessToken) => void;
}) {
  const lifecycle = mcpTokenLifecycle(token);
  const lifecycleLabel =
    lifecycle === "active"
      ? "Active"
      : lifecycle === "expired"
        ? "Expired"
        : "Revoked";
  const runtimeMessage =
    token.runtime_effect_state === "effective"
      ? null
      : token.runtime_effect_state === "failed"
        ? `Runtime update failed${token.runtime_error_code ? ` (${token.runtime_error_code})` : ""}`
        : "Runtime update pending";
  return (
    <div className="rounded-md border border-border bg-input p-3">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-medium text-foreground">{token.name}</p>
            <Badge
              tone={
                lifecycle === "active"
                  ? "success"
                  : lifecycle === "expired"
                    ? "warning"
                    : "neutral"
              }
            >
              {lifecycleLabel}
            </Badge>
          </div>
          <p className="mt-1 break-all font-mono text-xs text-muted">
            {token.token_prefix}…
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {lifecycle === "active" && (
            <Button
              aria-label={`Rotate ${token.name}`}
              disabled={rotationDisabled}
              onClick={() => onRotate(token)}
              size="sm"
              variant="outline"
            >
              <RefreshCw aria-hidden="true" className="size-4" />
              Rotate
            </Button>
          )}
          {lifecycle !== "revoked" && (
            <Button
              aria-label={`Revoke ${token.name}`}
              onClick={() => onRevoke(token)}
              size="sm"
              variant="ghost"
            >
              <Trash2 aria-hidden="true" className="size-4 text-danger-soft" />
              Revoke
            </Button>
          )}
        </div>
      </div>
      <dl className="mt-3 grid gap-2 border-t border-border pt-3 text-xs sm:grid-cols-3">
        <div>
          <dt className="text-muted">Created</dt>
          <dd className="mt-1 text-foreground">
            {formatDate(token.created_at)}
          </dd>
        </div>
        <div>
          <dt className="text-muted">Expires</dt>
          <dd className="mt-1 text-foreground">
            {formatDate(token.expires_at)}
          </dd>
        </div>
        <div>
          <dt className="text-muted">Last used</dt>
          <dd className="mt-1 text-foreground">
            {formatDate(token.last_used_at)}
          </dd>
        </div>
      </dl>
      {runtimeMessage && (
        <p
          className={
            token.runtime_effect_state === "failed"
              ? "mt-3 text-xs text-danger-soft"
              : "mt-3 text-xs text-warning-soft"
          }
        >
          {runtimeMessage}
        </p>
      )}
    </div>
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
