import type { McpAccessToken } from "@/api/contracts";

export type McpTokenLifecycle = "active" | "expired" | "revoked";

export function mcpTokenLifecycle(
  token: Pick<McpAccessToken, "expires_at" | "revoked_at">,
  now = Date.now(),
): McpTokenLifecycle {
  if (token.revoked_at) return "revoked";
  if (token.expires_at && Date.parse(token.expires_at) <= now) return "expired";
  return "active";
}

export function tokenExpirationToIso(
  localDateTime: string,
  now = Date.now(),
): { readonly value: string | null; readonly error: string | null } {
  if (!localDateTime) return { value: null, error: null };
  const timestamp = new Date(localDateTime).getTime();
  if (!Number.isFinite(timestamp))
    return { value: null, error: "Enter a valid expiration date and time." };
  if (timestamp <= now)
    return { value: null, error: "Expiration must be in the future." };
  return { value: new Date(timestamp).toISOString(), error: null };
}
