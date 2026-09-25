# Changelog

All notable MCPlica changes are recorded here. The format follows Keep a Changelog, and release
identities follow Semantic Versioning. Unreleased entries describe repository changes only; a
version is not published until its immutable tag and release workflow complete.

## [Unreleased]

### Changed

- Rejected OpenAPI and API Inventory documents whose operations reference an undefined security
  scheme at parse time instead of admitting them silently.
