# MCPlica documentation

Start with the [user guide](user-guide.md) to run the product, or the
[project overview](project-overview.md) to understand its scope and structure.

## Product and development

- [Project overview](project-overview.md) — boundaries, implemented capabilities, sources of
  truth, and repository map.
- [User guide](user-guide.md) — roles, ten-step setup, workspaces, recovery, and accessibility.
- [Development guide](development.md) — host-side development without the full Compose stack.
- [Compatibility](compatibility.md) — supported platforms, dependency baseline, MCP clients, and
  known limitations.

## API and MCP clients

- [API guide](api.md) — authentication, requests, responses, pagination, and contract changes.
- [API inventory](api-inventory-v1.md) — registered control-plane route and security inventory.
- [MCP client connection](mcp-client-connection.md) — bearer and OIDC connection guidance.

## Architecture sources of truth

These six documents define implementation authority. Later explicit decisions override earlier
conflicts.

1. [Architecture](architecture.md)
2. [Design document](design_document.md)
3. [Product requirements](product_requirements.md)
4. [Implementation plan](implementation_plan.md)
5. [Technology stack](tech_stack.md)
6. [Open-source and sponsorship model](open_source_and_sponsorship_model.md)

## Operations and security

- [Installation](operations/installation.md)
- [Configuration](operations/configuration.md)
- [Docker Compose](operations/docker-compose.md)
- [Domain and TLS](operations/domain-tls.md)
- [Backup and restore](operations/backup-restore.md)
- [Upgrade](operations/upgrade.md)
- [Troubleshooting](operations/troubleshooting.md)
- [Operations runbook](operations/runbook.md)
- [Threat model](security/threat-model.md)
- [Security hardening](security/hardening.md)

## Maintainers and releases

- [`VERSION`](../VERSION) — authoritative release version.
- [Changelog](../CHANGELOG.md) — user and operator-visible history.
- [Release process](maintainers/releasing.md)
- [Release checklist](maintainers/release-checklist.md)
- [v1.0.0-rc.1 notes](releases/v1.0.0-rc.1.md)

Root-level community and legal policies remain authoritative: [license](../LICENSE),
[contributing](../CONTRIBUTING.md), [CLA](../CLA.md), [code of conduct](../CODE_OF_CONDUCT.md),
[governance](../GOVERNANCE.md), [maintainers](../MAINTAINERS.md), [security](../SECURITY.md),
[support](../SUPPORT.md), [sponsorship](../SPONSORSHIP.md), [trademarks](../TRADEMARKS.md), and
[generated outputs](../GENERATED_OUTPUTS.md).
