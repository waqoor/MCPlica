# Changelog

All notable MCPlica changes are recorded here. The format follows Keep a Changelog, and release
identities follow Semantic Versioning. Unreleased entries describe repository changes only; a
version is not published until its immutable tag and release workflow complete.

## [Unreleased]

### Changed

- Resolved path-level OpenAPI servers before checking whether the document has a usable server URL,
  so a spec declaring servers only under a path item (valid per OpenAPI 3.1) no longer fails at
  server selection before the parser's existing path-level handling ever runs.

## [1.0.0-rc.1] - 2026-09-04

