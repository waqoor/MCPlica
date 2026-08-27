import type { McpAuthMode } from "@/api/contracts";
import { z } from "@/lib/schemas";

export const OIDC_SIGNING_ALGORITHMS = [
  "RS256",
  "RS384",
  "RS512",
  "PS256",
  "PS384",
  "PS512",
  "ES256",
  "ES384",
  "ES512",
  "EdDSA",
] as const;

const httpUrl = z
  .string()
  .trim()
  .min(1, "Enter a URL.")
  .refine((value) => {
    try {
      return ["http:", "https:"].includes(new URL(value).protocol);
    } catch {
      return false;
    }
  }, "Enter a complete http(s) URL.");

const valueList = (maximum: number) =>
  z.array(z.string().trim().min(1)).max(maximum);

export const mcpAuthModePayloadSchema = z.discriminatedUnion("mode", [
  z.object({ mode: z.literal("static_bearer") }).strict(),
  z.object({ mode: z.literal("disabled_dev") }).strict(),
  z
    .object({
      mode: z.literal("external_oauth_oidc"),
      issuer_url: httpUrl,
      audiences: valueList(50).min(
        1,
        "Enter at least one audience accepted by the MCP endpoint.",
      ),
      required_scopes: valueList(100).optional(),
      jwks_url: httpUrl.optional(),
      allowed_algorithms: z
        .array(z.enum(OIDC_SIGNING_ALGORITHMS))
        .min(1)
        .max(20)
        .optional(),
    })
    .strict(),
]);

export type McpAuthFormValues = {
  readonly mode: McpAuthMode;
  readonly issuerUrl: string;
  readonly audiences: string;
  readonly requiredScopes: string;
  readonly jwksUrl: string;
  readonly allowedAlgorithms: string;
};

function splitValues(value: string): string[] {
  return [
    ...new Set(
      value
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
    ),
  ];
}

export function buildMcpAuthModePayload(values: McpAuthFormValues) {
  let candidate: unknown;
  if (values.mode === "external_oauth_oidc") {
    const jwksUrl = values.jwksUrl.trim();
    const algorithms = splitValues(values.allowedAlgorithms);
    candidate = {
      mode: values.mode,
      issuer_url: values.issuerUrl.trim(),
      audiences: splitValues(values.audiences),
      required_scopes: splitValues(values.requiredScopes),
      ...(jwksUrl ? { jwks_url: jwksUrl } : {}),
      ...(algorithms.length ? { allowed_algorithms: algorithms } : {}),
    };
  } else {
    candidate = { mode: values.mode };
  }

  return mcpAuthModePayloadSchema.safeParse(candidate);
}
