# Grocy AI for Home Assistant

[![Validate](https://github.com/RatchetGK/ha-grocy-ai/actions/workflows/validate.yml/badge.svg)](https://github.com/RatchetGK/ha-grocy-ai/actions/workflows/validate.yml)
[![Lint & Test](https://github.com/RatchetGK/ha-grocy-ai/actions/workflows/lint-test.yml/badge.svg)](https://github.com/RatchetGK/ha-grocy-ai/actions/workflows/lint-test.yml)
[![hacs](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/docs/faq/custom_repositories)

Custom integration (`grocy_ai`) that extends [Grocy](https://grocy.info) with
AI and automation inside Home Assistant. Grocy stays the source of truth.

| Feature | Status |
|---|---|
| Config flow (Grocy URL + API key) & options | ✅ v0.1.0 |
| Book stock by barcode (plus / minus) | ✅ v0.2.0 |
| Unknown barcodes are created automatically via Open Food Facts (through Grocy) | ✅ v0.3.0 |
| Best-before date from a photo via HA **AI Task** (provider-agnostic) | ✅ v0.4.0 |
| Phone page in the sidebar: camera for barcode and best-before date | ✅ v0.5.0 |
| Notifications for products expiring soon | 🔜 v0.6.0 |
| Products below minimum stock → Bring! (any to-do entity), no duplicates | 🔜 v0.7.0 |
| Stable services & events for a kitchen tablet / Zigbee buttons | ✅ v0.2.0 (extended later) |

Planned services/events: see [PLAN.md §5](PLAN.md#5-schnittstelle-services--events).

## Requirements
- Home Assistant **2026.10** or newer
- [HACS](https://hacs.xyz)
- A running Grocy instance reachable from Home Assistant (e.g. the
  *Grocy* community add-on) and a Grocy API key
  (Grocy → *Settings / Manage API keys*)
- For photo recognition (v0.4.0+): an **AI Task** entity
  (e.g. Google Generative AI, OpenAI, Ollama …)

## Installation (HACS custom repository)
1. HACS → ⋮ (top right) → **Custom repositories**
2. Repository: `https://github.com/RatchetGK/ha-grocy-ai`, Type: **Integration** → *Add*
3. Search **Grocy AI** in HACS → **Download** (latest release)
4. Restart Home Assistant
5. *Settings → Devices & services → Add integration → Grocy AI*
6. Enter Grocy URL and API key. For the Grocy community add-on use
   `http://a0d7b954-grocy` and disable *Verify SSL*.
   **Important:** the add-on only enables direct (non-Ingress) access when a
   port is set under *Add-on → Configuration → Network* (e.g. `9192`).
   Without it the connection fails.

Updates appear in HACS automatically when a new release is published.

## Configuration
**Setup:** Grocy URL, API key, verify SSL.
**Options** (*Configure* on the integration):
- Days before expiry to notify
- Notify service (e.g. `notify.mobile_app_…`)
- To-do entity for the shopping list (e.g. a Bring! list)
- AI Task entity (empty = Home Assistant default)
- Look up unknown barcodes online (default on): on a purchase with an
  unknown barcode Grocy queries [Open Food Facts](https://world.openfoodfacts.org)
  (free, only the barcode is sent) and creates the product. Set default
  location/quantity unit for new products in Grocy (*Settings → Stock*).

API keys are stored only in Home Assistant's config entry – never in this
repository.

## Phone page
After setup a **Grocy AI** entry appears in the sidebar (also in the
Companion app):
1. Choose **Purchased (+)** or **Used (−)**.
2. **📷 Photo** next to the barcode opens the camera; the barcode is read by the
   browser (if supported) or by AI Task. Typing or a hardware scanner works too.
3. For purchases optionally **📷 Photograph best-before date** (or enter a date).
4. **Book** – the result shows product, new stock and best-before date.

Photos are scaled down on the phone, kept only in Home Assistant's memory and
deleted right after the AI has read them (at the latest after 10 minutes).

## Services
| Service | Purpose |
|---|---|
| `grocy_ai.add_stock` | Purchased: stock +amount (barcode **or** product_id, optional `best_before_date`, `price`, `location_id`) |
| `grocy_ai.consume_stock` | Used up: stock −amount (optional `spoiled`) |
| `grocy_ai.scan` | Barcode + `mode: plus/minus` – for buttons and tablets |
| `grocy_ai.read_best_before` | Read the best-before date from a photo (no booking) |
| `grocy_ai.read_barcode` | Read the barcode number from a photo (no booking, check digit verified) |

All services return a response (product, amount, best-before date and its
source, new stock amount, whether the product was just created) and fire
events: `grocy_ai_stock_added`, `grocy_ai_stock_consumed`,
`grocy_ai_product_created`, `grocy_ai_barcode_unknown`, `grocy_ai_error`.
Without `best_before_date` the product's default shelf life configured in
Grocy is used (`-1` or `0` = never expires).

**Best-before date from a photo:** pass `image` (a camera snapshot such as
`media-source://camera/camera.kitchen` or an uploaded photo) to `add_stock` /
`scan`. The configured AI Task entity reads the date (`12/2026` = end of
month). If the photo is unreadable or the AI is unsure, the booking still
happens with the default shelf life and `grocy_ai_best_before_failed` is
fired.

Example (e.g. a Zigbee button action):
```yaml
action: grocy_ai.scan
data:
  barcode: "4006040001234"
  mode: minus
```

## Development
Privacy: every commit/push is checked by `scripts/check_private_data.py`
(git hooks in `.githooks`, CI job + gitleaks). Enable the hooks after cloning:
`git config core.hooksPath .githooks`.

See [CLAUDE.md](CLAUDE.md) (conventions, tests, release process) and
[PLAN.md](PLAN.md) (architecture, milestones).

## License
MIT
