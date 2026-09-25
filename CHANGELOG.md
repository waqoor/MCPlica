# Changelog

All notable MCPlica changes are recorded here. The format follows Keep a Changelog, and release
identities follow Semantic Versioning. Unreleased entries describe repository changes only; a
version is not published until its immutable tag and release workflow complete.

## [Unreleased]

### Changed

- Raised a dedicated `ExecutionOwnershipError` when a build's execution lease is stale, and skipped
  the failure-audit write when that loss is itself the error being recorded, so an expired lease no
  longer masks the real failure behind a doomed ownership recheck.

## [1.0.0-rc.1] - 2026-09-04

