# Changelog

All notable MCPlica changes are recorded here. The format follows Keep a Changelog, and release
identities follow Semantic Versioning. Unreleased entries describe repository changes only; a
version is not published until its immutable tag and release workflow complete.

## [Unreleased]

### Changed

- Retried a canonicalization request as the new leader instead of failing it when the concurrent
  in-flight request it was coalesced onto was cancelled by an unrelated caller, preventing one
  cancelled poll from failing every other request waiting on the same result.

## [1.0.0-rc.1] - 2026-09-04

