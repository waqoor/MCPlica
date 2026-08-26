# Backup, restore, and recovery drills

A recoverable MCPlica backup is a consistent set containing PostgreSQL, the artifact store, the runtime host root for active deployment evidence, encryption/signing material from the external secret store, and the exact release/image digest inventory. A database dump without its encryption key cannot recover stored credentials.

## Data classification

- PostgreSQL is authoritative and must be backed up with point-in-time recovery or frequent encrypted dumps.
- `artifacts` contains immutable source/build evidence and must be backed up with hashes and access controls.
- `MCP_LICA_RUNTIME_HOST_ROOT` contains per-project manifest/secret mounts used by deployed runtimes. Treat it as secret material and back it up encrypted.
- The control-plane encryption key and key version belong in a separate secret manager/escrow, never inside the database dump.
- Redis queues/cache are disposable. Stop mutations and drain or cancel jobs; do not treat Redis restoration as authoritative recovery.
- Milvus, MinIO, and etcd hold builder-side indexes. Back them up consistently when rapid recovery matters, or rebuild them from authoritative documentation artifacts after restore.

## Backup procedure

1. Record the running commit, release tag, backend/frontend/runtime image digests, schema revision, and configuration key names without values.
2. Put the installation in maintenance mode and stop both workers so no build/deployment writes race the snapshot.
3. Produce an encrypted PostgreSQL custom-format dump using `pg_dump -Fc` from a trusted backup host.
4. Snapshot/copy the artifact volume and runtime host root while preserving ownership and permissions.
5. Export or verify escrow of the encryption key, signing key, refresh pepper, and their version metadata in the designated secret manager.
6. Hash every backup object, encrypt it before leaving the host, store it in a separate failure domain, and apply retention/restore-access policy.
7. Restart both workers and verify readiness and both queue consumers.

Never place a dump, runtime secret bundle, `.env`, or backup checksum containing a sensitive filename in an issue or CI artifact.

## Restore procedure

1. Provision an isolated host with the exact release images; keep external routing disabled.
2. Restore secrets from escrow, then PostgreSQL into an empty database and run `alembic current`. Do not run a newer migration until the original restore is proven.
3. Restore artifacts and runtime-root data with UID/GID 10001 and restrictive permissions.
4. Start PostgreSQL, Redis, Milvus, API, builder worker, and deployment worker without public Traefik routes. Verify `/api/v1/ready`, login, both queue consumers, project/source/build histories, credential decryptability through a non-disclosing connection test, and audit records.
5. Rebuild Milvus indexes from authoritative documentation generations when vector state was not restored.
6. Reconcile Docker state: create fresh runtime containers from recorded READY builds rather than trusting orphaned container IDs.
7. Exercise one authenticated MCP request and compare manifest/image digests before enabling DNS/routing.

## Drill and recovery evidence

Run an isolated restore drill before first production use and at least quarterly thereafter. Record recovery-point gap, recovery time, dump/artifact checksums, schema/image versions, test results, and follow-up defects. A backup is not release evidence until a restore drill has proven that encrypted credentials, artifacts, and a runtime can be recovered without secret disclosure.
