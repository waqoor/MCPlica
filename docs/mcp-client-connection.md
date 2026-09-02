# Connect an MCP client

Use the endpoint recorded on the project's Deployment page, normally `https://<project>.<mcp-domain>/mcp`. A client must support MCP Streamable HTTP and the authentication mode configured for that project. Candidate runtimes are certified against protocol revision `2026-07-28`; the canonical runtime also retains tested `2025-11-25` negotiation compatibility.

MCPlica is client-neutral. Client configuration formats change independently, so use that client's
current documentation to register an HTTP/Streamable HTTP server with the exact endpoint and an
authorization header supplied from its secret store. Do not translate this endpoint into stdio,
SSE, WebSocket, or a locally generated wrapper process.

## Static bearer

Create a named token on the MCP Access step and copy the plaintext immediately into the client's secret manager. It is shown once. Configure the client to send:

```text
Authorization: Bearer <token>
```

Do not put a token in a URL, command history, screenshot, client config committed to Git, or issue. MCPlica later shows only the token name/prefix, timestamps, and revocation state. Rotate before expiry or suspected disclosure; the bounded overlap permits client cutover, then the old verifier becomes unusable.

## External OAuth/OIDC

Configure the exact HTTPS issuer and at least one audience, plus required scopes and reviewed JWKS/algorithm metadata. The client obtains a token from that external provider and sends it as a bearer token. The runtime validates signature, issuer, audience, expiry/not-before, and scopes; it does not delegate authorization to browser login or accept unsigned/unexpected algorithms.

## Verification

First check the runtime health state and exact deployment/build identity in MCPlica. Then configure
the client with the endpoint and secret/provider settings and perform:

1. MCP initialize and capability negotiation;
2. list tools and resources;
3. one schema-valid read-only tool call against a non-sensitive test record;
4. one intentionally invalid argument call that the runtime rejects without reaching upstream;
5. token rotation/overlap and old-token rejection where static bearer is used.

The advertised names and input schemas must exactly match the deployed immutable manifest and
validation report. A successful `/readyz` probe alone does not prove MCP authentication or tool
execution. The release-candidate CI harness uses the official Python SDK for initialize, listing,
resource read, and authenticated GET/POST/PATCH/DELETE calls; each named desktop/editor client still
requires its own target-environment acceptance.

If a request fails, distinguish:

- `401/403`: token/OIDC claim, expiry, scope, audience, or revocation issue;
- host/TLS failure: DNS, certificate, or allowed-host mismatch;
- input validation failure: caller payload does not match the advertised JSON Schema;
- upstream/auth failure: project upstream credential or API state, not MCP inbound auth;
- runtime unhealthy/digest failure: deployment evidence or mounted artifact mismatch.

Use request IDs and sanitized runtime/deployment logs. Never enable unauthenticated mode or relax TLS/host checks to diagnose production traffic. `disabled_dev` is restricted to development/test and cannot satisfy a production deployment.
