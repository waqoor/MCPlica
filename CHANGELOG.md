# Changelog

All notable MCPlica changes are recorded here. The format follows Keep a Changelog, and release
identities follow Semantic Versioning. Unreleased entries describe repository changes only; a
version is not published until its immutable tag and release workflow complete.

## [Unreleased]

### Changed

- Paged the sources list over distinct sources rather than raw version rows, so a superseded source
  version can no longer land on a different page than its latest version and render as an orphaned
  top-level entry.
