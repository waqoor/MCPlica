# Generated Outputs

MCPlica produces canonical inventories, normalized documentation, MCP manifests, validation reports, build evidence, and deployment metadata from operator-supplied sources.

## Ownership and licensing

The AGPL-3.0-only license covers MCPlica itself and project/runtime code. It does not automatically relicense an operator's API specification, documentation, credentials, or generated output. Operators remain responsible for having the rights to ingest, transform, deploy, and redistribute their inputs and outputs.

Generated output may contain names, descriptions, schemas, and examples derived from source material. The output therefore remains subject to rights and restrictions attached to that source material. MCPlica does not grant rights in third-party APIs or documentation.

## Security and reproducibility

- Secrets must never be embedded in a canonical inventory, manifest, build evidence file, log, or downloadable output.
- Executable HTTP mappings come from deterministic source evidence; AI enrichment may improve semantics but may not invent executable behavior.
- A releasable build must retain source-version identifiers, contract/schema version, validation status, content hashes, and the selected build configuration needed to audit it.
- Generated artifacts are immutable once attached to a deployment. A new source or configuration creates a new build rather than mutating deployed evidence.

Do not publish a generated artifact until its source licenses, secret scan, and validation report have been reviewed.
