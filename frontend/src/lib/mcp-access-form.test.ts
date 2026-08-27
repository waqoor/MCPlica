import { describe, expect, test } from "vitest";
import { buildMcpAuthModePayload } from "./mcp-access-form";

const oidcValues = {
  mode: "external_oauth_oidc" as const,
  issuerUrl: "https://issuer.example/tenant",
  audiences: "api://inventory, api://inventory",
  requiredScopes: "mcp:invoke, inventory:read",
  jwksUrl: "https://issuer.example/tenant/keys",
  allowedAlgorithms: "RS256, ES256",
};

describe("MCP auth mode payload construction", () => {
  test.each(["static_bearer", "disabled_dev"] as const)(
    "%s omits every retained OIDC field",
    (mode) => {
      const result = buildMcpAuthModePayload({ ...oidcValues, mode });

      expect(result.success).toBe(true);
      if (result.success) expect(result.data).toEqual({ mode });
    },
  );

  test("requires both issuer and audience for OIDC", () => {
    expect(
      buildMcpAuthModePayload({
        ...oidcValues,
        issuerUrl: "",
        audiences: "",
      }).success,
    ).toBe(false);
  });

  test("normalizes the complete OIDC verifier payload", () => {
    const result = buildMcpAuthModePayload(oidcValues);

    expect(result.success).toBe(true);
    if (result.success)
      expect(result.data).toEqual({
        mode: "external_oauth_oidc",
        issuer_url: "https://issuer.example/tenant",
        audiences: ["api://inventory"],
        required_scopes: ["mcp:invoke", "inventory:read"],
        jwks_url: "https://issuer.example/tenant/keys",
        allowed_algorithms: ["RS256", "ES256"],
      });
  });

  test("allows discovery defaults but rejects unsupported signing algorithms", () => {
    const defaults = buildMcpAuthModePayload({
      ...oidcValues,
      jwksUrl: "",
      allowedAlgorithms: "",
    });
    expect(defaults.success).toBe(true);
    if (defaults.success) {
      expect(defaults.data).not.toHaveProperty("jwks_url");
      expect(defaults.data).not.toHaveProperty("allowed_algorithms");
    }

    expect(
      buildMcpAuthModePayload({
        ...oidcValues,
        allowedAlgorithms: "HS256",
      }).success,
    ).toBe(false);
  });
});
