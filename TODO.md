# TODO – ha-grocy-ai

Checkliste pro Meilenstein (Details & Abnahmekriterien: [PLAN.md](PLAN.md)).
Erledigtes abhaken, neue Erkenntnisse sofort unter „Erkenntnisse“ eintragen.

## M1 – Gerüst & CI (v0.1.0)
- [x] `gh` installiert & eingeloggt prüfen
- [x] Repo `RatchetGK/ha-grocy-ai` (MIT) anlegen & klonen
- [x] Sichtbarkeit: öffentlich; Repo mit sauberer Historie neu angelegt, altes als `ha-grocy-ai-old` (privat)
- [ ] Nutzer: altes Repo `ha-grocy-ai-old` löschen (braucht `delete_repo`-Berechtigung)
- [x] Datenschutz: Prüfskript, Git-Hooks, CI-Job (Skript + gitleaks), Skill `commit-push`
- [x] Private Angaben (IP, Vornamen, Entitäten) aus Doku/Tests entfernt → `.local/`
- [x] PLAN.md, TODO.md, CLAUDE.md, CHANGELOG.md, README.md schreiben
- [x] Doku committen & pushen
- [x] `hacs.json`, `manifest.json`
- [x] `const.py`, `api.py` (minimal: `/api/system/info`)
- [x] Config-Flow (URL, API-Key, SSL, Verbindungstest, Duplikat-Schutz)
- [x] Options-Flow (Vorlauf Tage, Notify-Dienst, To-do-Entität, AI-Task-Entität)
- [x] `strings.json` + Übersetzungen `en`/`de`
- [x] `pyproject.toml` (ruff, pytest), `requirements_test.txt`
- [x] Tests: Config-Flow (ok, cannot_connect, invalid_auth, already_configured), Options-Flow, Setup/Unload
- [x] Workflow `validate.yml` (hassfest + HACS)
- [x] Workflow `lint-test.yml` (ruff + pytest)
- [x] Workflow `release.yml` (Tag → Versionscheck → Release)
- [x] Repo-Topics setzen (HACS-Validierung)
- [x] Alle Actions grün
- [x] Tag `v0.1.0` → Release erzeugt
- [x] PLAN/TODO/CHANGELOG aktualisieren

- [ ] Manuelle Abnahme: Integration per HACS installieren und Config-Flow öffnen

## M2 – Grocy-Anbindung & Barcode-Buchung (v0.2.0)
- [ ] Grocy-Add-on installieren (Nutzer) + API-Key erzeugen
- [ ] Interne Add-on-URL verifizieren und in README eintragen
- [ ] `GrocyClient`: `get_product_by_barcode`, `add_by_barcode`, `consume_by_barcode`, `add_product`/`consume_product` (per ID), `get_volatile`
- [ ] Fehlerklassen (`GrocyConnectionError`, `GrocyAuthError`, `GrocyNotFoundError`, `GrocyApiError`)
- [ ] `services.yaml` + Service-Handler `add_stock`, `consume_stock`, `scan` (mit Response)
- [ ] Events `grocy_ai_stock_added`, `grocy_ai_stock_consumed`, `grocy_ai_barcode_unknown`, `grocy_ai_error`
- [ ] Tests mit gemockter API (aioclient_mock)
- [ ] Manuelle Abnahme in HA

## M3 – MHD per Foto (v0.3.0)
- [ ] `ai.py`: Prompt + Struktur + Parsing (TT.MM.JJ, MM/JJJJ → Monatsende, …)
- [ ] Plausibilitätsprüfung + Fallback + Event `grocy_ai_best_before_failed`
- [ ] Service `read_best_before`; `image` in `add_stock`/`scan`
- [ ] Tests (gemocktes `ai_task.generate_data`)
- [ ] Abnahme mit echten Fotos (Kamera / Upload)

## M4 – Ablauf-Benachrichtigungen & Sensoren (v0.4.0)
- [ ] `coordinator.py` (Polling `/stock/volatile`)
- [ ] Sensoren expiring/expired/missing
- [ ] Tägliche Benachrichtigung zur Uhrzeit X (Options-Flow), max. 1×/Tag
- [ ] Service `check_expiring`, Event `grocy_ai_product_expiring`
- [ ] Tests

## M5 – Bring!-Sync (v0.5.0)
- [ ] `shopping.py`: Abgleich `todo.get_items` (needs_action), normalisierter Vergleich
- [ ] Store für selbst hinzugefügte Produkte (kein Re-Add bis Bestand wieder ok)
- [ ] Service `sync_shopping_list`, Event `grocy_ai_shopping_item_added`
- [ ] Automatisch nach Coordinator-Refresh (abschaltbar im Options-Flow)
- [ ] Tests

## M6 – Härtung (v1.0.0)
- [ ] Diagnostics (API-Key redacted)
- [ ] Reauth-Flow
- [ ] Repair-Issue bei dauerhaft nicht erreichbarem Grocy
- [ ] Schnittstellen-Doku für Tablet-App (`docs/API.md`)
- [ ] Quality-Scale-Selbstcheck
- [ ] 2 Wochen Alltagsbetrieb

## Erkenntnisse
- 2026-10-25: HA 2026.10.x; AI-Task-Entität vorhanden, `generate_data` unterstützt `attachments` + `structure`.
- 2026-10-25: `pytest-homeassistant-custom-component` 0.13.374 verlangt Python ≥ 3.14 (pinnt HA 2026.10.3). Lokal Python 3.13 → Tests lokal über `uv` mit 3.14.
- 2026-10-25: Im HACS-Store heißt die Grocy-Integration aktuell `iamkarlson/grocy` (nicht custom-components/grocy). Für `grocy_ai` nicht nötig.
- 2026-10-25: Kein globaler Git-Name/E-Mail gesetzt → repo-lokal auf RatchetGK + noreply gesetzt.
- 2026-10-25: `hacs/action` bricht bei privaten Repos ab („can only validate public repositories“). Lösung: HACS-Job nur bei öffentlichem Repo (`if: !github.event.repository.private`), sonst Job „HACS structure“ (jq-Prüfung von hacs.json/manifest.json/Layout).
- 2026-10-25: Lokale HA-Tests unter Windows unmöglich (`homeassistant.runner` importiert `fcntl`). Ruff läuft lokal (.venv mit uv/Python 3.14), pytest nur in CI (9/9 grün).
- 2026-10-25: Auth-Fehler beim Setup → vorerst `ConfigEntryError`; mit Reauth-Flow (M6) auf `ConfigEntryAuthFailed` umstellen.
- 2026-10-25: „Kurz öffentlich, dann wieder privat“ verworfen (HACS braucht das Repo dauerhaft öffentlich). Entscheidung: öffentlich.
- 2026-10-25: Alte Commits enthielten interne IP + Vornamen (nur solange privat). Historie auf GitHub nicht sicher bereinigbar (alte SHAs bleiben erreichbar, Actions-Logs) → neues Repo, ein sauberer Initial-Commit; altes Repo umbenannt + privat. Lokale Details jetzt in `.local/` (gitignored).
