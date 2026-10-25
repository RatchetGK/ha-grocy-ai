# Changelog

All notable changes to this project are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versioning follows [SemVer](https://semver.org/).

## [Unreleased]
### Changed
- Config flow URL hint now names the Grocy add-on URL and that the add-on
  needs a network port for direct access.

## [0.1.0] - 2026-10-25
### Added
- Project scaffold: HACS metadata, integration manifest (`grocy_ai`).
- Config flow (Grocy URL, API key, SSL verification) with connection test
  against `/api/system/info`.
- Options flow (expiry lead time in days, notify service, to-do entity for
  Bring!, AI Task entity).
- English and German translations.
- CI: hassfest + HACS validation, ruff + pytest, automatic GitHub release with `grocy_ai.zip` on
  version tag.
- Project documentation (PLAN, TODO, CLAUDE, README).

### Security
- `scripts/check_private_data.py`: blocks secrets and private data
  (tokens, keys, private IPs, e-mail addresses, local denylist).
- Git hooks (`.githooks`: pre-commit, commit-msg, pre-push) and CI job
  "Secrets & private data" (script + gitleaks).
- Claude skill `commit-push` for safe commits and pushes.
