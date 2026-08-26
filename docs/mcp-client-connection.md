# Connect an MCP client

Use the endpoint recorded on the project's Deployment page, normally `https://<project>.<mcp-domain>/mcp`. A client must support MCP Streamable HTTP and the authentication mode configured for that project.

## Static bearer

Create a named token on the MCP Access step and copy the plaintext immediately into the client's secret manager. It is shown once. Configure the client to send:

```text
Authorization: Bearer <token>
```

Do not put a token in a URL, command history, screenshot, client config committed to Git, or issue. MCPlica later shows only the token name/prefix, timestamps, and revocation state. Rotate before expiry or suspected disclosure; the bounded overlap permits client cutover, then the old verifier becomes unusable.

## External OAuth/OIDC

Configure the exact HTTPS issuer and at least one audience, plus required scopes and reviewed JWKS/algorithm metadata. The client obtains a token from that external provider and sends it as a bearer token. The runtime validates signature, issuer, audience, expiry/not-before, and scopes; it does not delegate authorization to browser login or accept unsigned/unexpected algorithms.

## Verification

First check the runtime health state in MCPlica. Then configure the MCP client with the endpoint and secret/provider settings and perform its normal initialize/list-tools sequence. The advertised tools and input schemas must exactly match the deployed manifest validation report.

If a request fails, distinguish:

- `401/403`: token/OIDC claim, expiry, scope, audience, or revocation issue;
- host/TLS failure: DNS, certificate, or allowed-host mismatch;
- input validation failure: caller payload does not match the advertised JSON Schema;
- upstream/auth failure: project upstream credential or API state, not MCP inbound auth;
- runtime unhealthy/digest failure: deployment evidence or mounted artifact mismatch.

Use request IDs and sanitized runtime/deployment logs. Never enable unauthenticated mode or relax TLS/host checks to diagnose production traffic. `disabled_dev` is restricted to development/test and cannot satisfy a production deployment.
