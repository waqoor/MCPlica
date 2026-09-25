# Changelog

All notable MCPlica changes are recorded here. The format follows Keep a Changelog, and release
identities follow Semantic Versioning. Unreleased entries describe repository changes only; a
version is not published until its immutable tag and release workflow complete.

## [Unreleased]

### Changed

- Persisted the configured embedding model on a document index generation instead of the model name
  a provider's response happened to echo back, so a completed generation's `embedding_model` matches
  what was actually requested.

## [1.0.0-rc.1] - 2026-09-04

