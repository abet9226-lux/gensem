# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.8.0] - 2026-04-11

### Added
- Mono-plugin architecture: single `plugin/` directory deployable on both Claude Code and Cursor
- 22 commands covering the full SDLC: orchestration, planning, engineering, quality, capitalization
- 16 core principles (P1-P16): human-in-the-loop, guardrails, traceability, complexity budget, adversarial review, etc.
- 9 agents: 8 specialized (architect, code-reviewer, security-auditor, test-strategist, requirements-analyst, ux-advocate, guardrail-enforcer, devil-advocate) + 1 orchestrator
- 15 artefact and configuration templates
- Generator script (`gse_generate.py`): builds `plugin/` from `src/` with cross-platform parity verification
- Hooks support for both platforms (Claude PascalCase / Cursor camelCase)
- Marketplace metadata for Claude Code

### Changed
- Complexity-based sprint sizing replaces time-based estimation (adapted for AI-assisted engineering)
- Plugin manifests updated to point to `nicolasguelfi/gensem` repository

## [0.7.0] - 2026-04-10

### Added
- Initial implementation of the plugin structure
- Specification document (`gse-one-spec-v0.7.md`)
- Implementation design document (`gse-one-implementation-design-v0.7.md`)
- Cross-inspection and alignment between spec and design

## [0.6.0] - 2026-04-09

### Added
- Critical review and final inspection reports
- Cross-platform deployment analysis (Claude Code + Cursor)

## [0.4.0] - 2026-04-08

### Added
- Design review report (v0.4 vs spec v0.6)
- Specification v0.4, v0.5, v0.6

## [0.1.0] - 2026-04-06

### Added
- Initial project creation (originally named "gone")
- First specification and implementation design drafts
- Requirements document

[0.8.0]: https://github.com/nicolasguelfi/gensem/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/nicolasguelfi/gensem/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/nicolasguelfi/gensem/compare/v0.4.0...v0.6.0
[0.4.0]: https://github.com/nicolasguelfi/gensem/compare/v0.1.0...v0.4.0
[0.1.0]: https://github.com/nicolasguelfi/gensem/releases/tag/v0.1.0
