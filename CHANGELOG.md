# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project intends to follow [Semantic Versioning](https://semver.org/)
once it reaches 1.0.

## [0.1.0] - Unreleased

Initial release. Phase 1-3 of the project roadmap (see README/docs for the
full phase breakdown):

### Added

- `slopscan analyze` supporting local directories, ZIP archives, live
  websites, and public GitHub repositories, with automatic target-type
  detection.
- A modular rule engine (`slopscan.rules`) with 22 initial rules across
  visual, copy, template/layout, repetition, typography, animation, code,
  and accessibility categories.
- A scoring engine using a diminishing-returns activation curve per rule
  and noisy-OR combination within categories, explicitly designed to avoid
  linear "violation counting" and double-counting of related signals.
- Positive-signal detection (semantic HTML, typographic variety, design
  token systems, accessible images) surfaced for context, never
  mechanically offsetting the score.
- Terminal (Rich), JSON, Markdown, and HTML report formats.
- `slopscan rules list` / `slopscan rules show <id>` for rule
  introspection.
- `slopscan doctor` and `slopscan config` for environment/config
  visibility.
- CI-friendly `--fail-under` threshold with dedicated exit codes.
- SSRF protection for live website scanning (private/loopback/link-local
  IP blocking, re-validated on every redirect hop).
- ZIP-extraction protection (path traversal, symlink rejection, zip-bomb
  compression-ratio and total-size limits).
- Optional AI-enhanced interpretation layer (`--ai`) with a provider
  abstraction supporting Anthropic, OpenAI, and Google, sending only
  aggregated deterministic evidence -- never raw source -- and never
  overriding the deterministic score.
- `.slopscan.toml` and `.slopscanignore` support for configuration.

### Known limitations (tracked for future phases)

- No browser-based rendering yet (`--crawl`/Playwright-based visual
  analysis is planned; static HTML/CSS/JS analysis works today without
  it).
- No `compare` or `baseline` commands yet.
- No SARIF output format yet.
- No official GitHub Action yet (the CLI itself is CI-ready via
  `--format json` and `--fail-under`; wrapping it in an Action is
  straightforward future work).
