# Changelog

All notable MCPlica changes are recorded here. The format follows Keep a Changelog, and release
identities follow Semantic Versioning. Unreleased entries describe repository changes only; a
version is not published until its immutable tag and release workflow complete.

## [Unreleased]

### Changed

- Declared `JSONB(none_as_null=True)` on the AI run's response/usage/cost columns so a `None` value
  is stored as true SQL `NULL`, fixing an intermittent `IntegrityError` on
  `ck_build_ai_runs_outcome` when an AI operation genuinely failed, and expanded diagnostic logging
  to surface the full exception chain and root cause instead of only the outermost exception type.
