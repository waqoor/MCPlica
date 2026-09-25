# Application logging (local implementation for review)

The API, builder worker, deployment supervisor and deployment worker use the
backend's safe stdlib logging pipeline. Console logging still follows `LOG_LEVEL`
and the existing development/production text/JSON choice. Archives always contain
newline-delimited JSON. Docker's existing bounded console logging is unchanged.

## Archive layout

```text
<LOG_DIRECTORY>/
  platform/<service>/<YYYY-MM-DD>/<pid>-<random-instance>.<segment>.log
  projects/<project-uuid>/<build-uuid>/<YYYY-MM-DD>/<pid>-<random-instance>.<segment>.log
```

Services are `mcplica-api`, `mcplica-builder`, and `mcplica-deployment`.
Deployment diagnostics are platform events even when they mention a build ID.
Only an explicit context containing authoritative project and build UUIDs selects
the build archive. The pipeline binds this context around build execution and
emits `build.started`, `build.stage_changed`, `build.failed`, and `build.ready`.
Stage events describe observed persisted stages, including a resumed attempt;
they are diagnostic events, not an exactly-once event ledger. Terminal events are
emitted after the relevant database transaction succeeds. PostgreSQL audit records
remain authoritative and unchanged.

Audit events go directly through `AuditRepository.append` to the PostgreSQL
`audit_events` table. No audit file sink or audit-row mirroring is configured.
Build lifecycle diagnostics are operational messages, not copies of audit rows
or their metadata. Archive files use `.log` exclusively, with one safe JSON
record per line.

## Configuration and persistence

| Setting | Default | Meaning |
| --- | --- | --- |
| `LOG_DIRECTORY` | `/var/log/mcplica` | Absolute non-root Linux path |
| `LOG_MAX_FILE_BYTES` | `10485760` | Segment byte limit, including UTF-8 and newline; minimum 1024 |
| `LOG_RETENTION_DAYS` | `30` | UTC calendar dates retained, including today |
| `LOG_LEVEL` | existing `INFO` default | Existing application logging threshold |

Compose mounts the separate `application-logs` named volume into the API and
workers. A networkless one-shot `log-init` initializes its top-level permissions
for UID/GID 10001; it receives no application secrets. This supports customized
mount destinations as well as the default. Configuration changes take effect on
process restart. Local live verification has been reported for platform logs, a build reaching
READY, and sensitive-value omission. Release deployment remains subject to review.

The archive targets the Linux containers already used by MCPlica. Native Windows
execution retains safe console output and reports archive unavailability: it does
not fall back to weaker path checks. Use a private local filesystem, not an NFS
share or an operator-writable shared folder. Files use mode 0600 and new
directories 0700. Administrators can read archives through the named volume;
there is no new HTTP endpoint or logging UI.

## Rotation and retention

UTC date is selected at emission time. The writer rolls before a serialized
record would exceed the segment limit. Oversized records are replaced with a
small `log.record_omitted` event; individual records are capped at 64 KiB or the
segment limit, whichever is smaller. Each process instance uses its own random
writer ID; a fork receives a new ID on first emission. Each write closes its
descriptors, and the standard handler lock serializes threads. No multi-process
file lock or shared open stream is required.

The API runs retention at startup and hourly, stopping with its dispatcher group.
Thirty days means today plus the previous 29 UTC dates. The cleaner visits only
recognized platform/project/build/date paths, removes recognized expired structured .log
segments, and prunes empty recognized directories. It ignores symlinks, hardlinked
files and unknown files; descriptor-relative no-follow traversal rejects symlink
ancestors and `..` paths. It never scans Docker storage, audits, artifacts or the
runtime directories. Multiple API processes can safely attempt cleanup; retention
is delayed while no API process is running.

Logging failures do not change job outcomes. Archive errors increment the
handler's process-local failure count and emit a safe stderr diagnostic at most
once per minute per handler. Retention failures produce a safe stderr diagnostic.
No failed record, exception message or filesystem path is printed. Disk-full
conditions can therefore lose diagnostic records; this is not a durable audit
transport. Retention limits age, not total disk consumption or a per-project quota.

## Safe records and correlation

Records contain timestamp, level, service, component, scope and a symbolic
`message` event, plus allowlisted identifiers, stage, attempt, outcome, error code,
duration and HTTP metadata where supplied. Unknown extras, formatting arguments,
exception messages/tracebacks, request bodies, provider responses and model
reasoning are omitted. Exception diagnostics contain types only. Callers must
use symbolic event names and trusted IDs, never put secrets in allowed fields.
The isolated indexing logger now follows this same stdlib path.

API request context is reset on exit and propagated across awaits. Inbound
`X-Request-ID` is accepted only as a UUID; other values receive a generated UUID
so an arbitrary header cannot be copied into logs. Job correlation uses build or
command UUIDs and the build attempt number. Request-to-queue correlation is not
persisted in this first version. Build context is reset even on exceptions.
RQ and Uvicorn messages pass through safe formatting; verbose non-symbolic
third-party text is deliberately omitted. No worker lifecycle semantics change.

## Owner review decisions

The initial 10 MiB segment limit and 30-day retention defaults are approved.
Decide separately whether a total storage quota, external collection/alerts,
longer audit retention, infrastructure/runtime archives or a log viewer are needed.
None of those additions is included here.
