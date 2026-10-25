# Grocy AI for Home Assistant

[![Validate](https://github.com/RatchetGK/ha-grocy-ai/actions/workflows/validate.yml/badge.svg)](https://github.com/RatchetGK/ha-grocy-ai/actions/workflows/validate.yml)
[![Lint & Test](https://github.com/RatchetGK/ha-grocy-ai/actions/workflows/lint-test.yml/badge.svg)](https://github.com/RatchetGK/ha-grocy-ai/actions/workflows/lint-test.yml)
[![hacs](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/docs/faq/custom_repositories)

Custom integration (`grocy_ai`) that extends [Grocy](https://grocy.info) with
AI and automation inside Home Assistant. Grocy stays the source of truth.

| Feature | Status |
|---|---|
| Config flow (Grocy URL + API key) & options | ✅ v0.1.0 |
| Book stock by barcode (plus / minus) | 🔜 v0.2.0 |
| Best-before date from a photo via HA **AI Task** (provider-agnostic) | 🔜 v0.3.0 |
| Notifications for products expiring soon | 🔜 v0.4.0 |
| Products below minimum stock → Bring! (any to-do entity), no duplicates | 🔜 v0.5.0 |
| Stable services & events for a kitchen tablet / Zigbee buttons | 🔜 v0.2.0+ |

Planned services/events: see [PLAN.md §5](PLAN.md#5-schnittstelle-services--events).

## Requirements
- Home Assistant **2026.10** or newer
- [HACS](https://hacs.xyz)
- A running Grocy instance reachable from Home Assistant (e.g. the
  *Grocy* community add-on) and a Grocy API key
  (Grocy → *Settings / Manage API keys*)
- For photo recognition (v0.3.0+): an **AI Task** entity
  (e.g. Google Generative AI, OpenAI, Ollama …)

## Installation (HACS custom repository)
1. HACS → ⋮ (top right) → **Custom repositories**
2. Repository: `https://github.com/RatchetGK/ha-grocy-ai`, Type: **Integration** → *Add*
3. Search **Grocy AI** in HACS → **Download** (latest release)
4. Restart Home Assistant
5. *Settings → Devices & services → Add integration → Grocy AI*
6. Enter Grocy URL and API key. For the community add-on the URL from inside
   Home Assistant is `http://a0d7b954-grocy` (internal port 80) or the
   add-on's exposed port, e.g. `http://homeassistant.local:9192`.

Updates appear in HACS automatically when a new release is published.

## Configuration
**Setup:** Grocy URL, API key, verify SSL.
**Options** (*Configure* on the integration):
- Days before expiry to notify
- Notify service (e.g. `notify.mobile_app_…`)
- To-do entity for the shopping list (e.g. a Bring! list)
- AI Task entity (empty = Home Assistant default)

API keys are stored only in Home Assistant's config entry – never in this
repository.

## Development
Privacy: every commit/push is checked by `scripts/check_private_data.py`
(git hooks in `.githooks`, CI job + gitleaks). Enable the hooks after cloning:
`git config core.hooksPath .githooks`.

See [CLAUDE.md](CLAUDE.md) (conventions, tests, release process) and
[PLAN.md](PLAN.md) (architecture, milestones).

## License
MIT
