# Security Policy

Do not disclose exploitable vulnerabilities in public issues before coordinated disclosure.

Until a dedicated security contact/channel is configured, repository maintainers should use GitHub private vulnerability reporting/security advisories.

Security-sensitive design rules include:

- no secrets in logs/manifests;
- fail-closed credential behavior;
- URL/host allowlisting for remote source retrieval and runtime upstream execution;
- no user-supplied executable code;
- isolated per-project MCP containers;
- no Docker socket in the public API container;
- dependency and container scanning in CI.
