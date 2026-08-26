# Contributing to MCPlica

Thank you for contributing.

## Contributor License Agreement

MCPlica uses a **CLA-only** contribution model. **DCO is not used.** External code contributions may not be merged until the contributor's applicable individual/entity CLA status is verified.

The repository-level automation is intentionally represented by `.github/workflows/cla.yml`; connect it to the selected CLA service or organization workflow before accepting third-party code.

## Engineering requirements

- Follow the architecture and design specifications in `docs/`.
- Do not add SaaS billing, tenant abstractions, chat/agent runtime, or HITL policy engines.
- Keep OpenRouter and Milvus out of the MCP serving runtime.
- Infrastructure integrations belong behind clients.
- Preserve deterministic executable API mappings.
- Add/adjust tests for every behavior change.
- Never commit secrets or user API documentation/specifications to fixtures without explicit redistribution rights.

## Pull requests

1. Create a focused branch.
2. Add tests.
3. Run `make lint`, `make typecheck`, and `make test`.
4. Explain architecture-impacting changes explicitly.
5. Ensure CLA verification passes.
