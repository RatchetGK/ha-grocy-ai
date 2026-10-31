# Changelog

All notable changes to this project are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versioning follows [SemVer](https://semver.org/).

## [Unreleased]

## [0.5.0] - 2026-10-31
### Added
- Sidebar page **Grocy AI** for the phone (all users): Purchased/Used, barcode,
  amount, best-before date. The camera buttons open the phone camera directly.
- Barcode from a photo: the browser's own barcode reader is used when
  available, otherwise the new service `grocy_ai.read_barcode` (AI Task). Only
  numbers with a valid EAN/UPC check digit are accepted.
- Photo upload endpoint `/api/grocy_ai/photo` (HA login required) and media
  source `media-source://grocy_ai/…`: photos stay in memory only, expire after
  10 minutes and are deleted right after the AI has read them.

## [0.4.0] - 2026-10-29
### Added
- Best-before date from a photo via Home Assistant's AI Task: new service
  `grocy_ai.read_best_before` and optional `image` for `add_stock` / `scan`.
  Understands ISO, `DD.MM.YY(YY)` and month-only dates (end of month);
  checks confidence and plausibility.
- If the date cannot be read the booking still happens with the default
  shelf life; event `grocy_ai_best_before_failed`, response field `ai_error`.

## [0.3.0] - 2026-10-28
### Added
- Unknown barcodes are created automatically on a purchase (`add_stock`,
  `scan` plus) via Grocy's external barcode lookup (Open Food Facts plugin);
  option "Look up unknown barcodes online" (default on). Consuming never
  creates products.
- Event `grocy_ai_product_created`; response field `product_created`.

### Fixed
- Empty Grocy responses are treated as `null` instead of raising a JSON error.

## [0.2.0] - 2026-10-25
### Added
- Services `grocy_ai.add_stock`, `grocy_ai.consume_stock` and `grocy_ai.scan`
  (barcode or product ID, amount, optional best-before date, price, location,
  spoiled) with service responses.
- Events `grocy_ai_stock_added`, `grocy_ai_stock_consumed`,
  `grocy_ai_barcode_unknown` and `grocy_ai_error`.
- Without a best-before date the product's default shelf life from Grocy is
  applied (`-1`/`0` → never expires); Grocy's API alone would use today.
- Translated error messages (English, German).

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
