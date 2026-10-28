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

- [x] Integration per HACS (Custom Repository) installiert, HA neu gestartet, lädt ohne Fehler
- [x] Manuelle Abnahme: Config-Flow erfolgreich abgeschlossen

## M2 – Grocy-Anbindung & Barcode-Buchung (v0.2.0)
- [x] Grocy-Add-on installiert (`a0d7b954_grocy` v0.26.5; culture de, EUR, ssl aus, Watchdog an, Auto-Update aus) und gestartet
- [x] Nutzer: Grocy-Passwort geändert, API-Key erzeugt
- [x] Add-on-Netzwerk-Port 80/tcp → 9192 gesetzt (Voraussetzung für Direktzugriff, auch für Grocy Android)
- [x] Integration mit `http://a0d7b954-grocy` eingerichtet und geladen
- [x] `GrocyClient`: `get_product`, `get_product_by_barcode`, `add_product`, `consume_product` (Buchung immer per ID nach Auflösung)
- [ ] `get_volatile` → verschoben nach M4 (Coordinator)
- [x] Fehlerklassen (`GrocyConnectionError`, `GrocyAuthError`, `GrocyNotFoundError`, `GrocyApiError`)
- [x] `services.yaml` + Service-Handler `add_stock`, `consume_stock`, `scan` (mit Response)
- [x] Events `grocy_ai_stock_added`, `grocy_ai_stock_consumed`, `grocy_ai_barcode_unknown`, `grocy_ai_error`
- [x] Tests mit gemockter API (aioclient_mock) – 24 grün
- [x] Übersetzte Fehlermeldungen (de/en), Standard-Haltbarkeit selbst berechnet
- [x] Release v0.2.0, HACS-Update + HA-Neustart (mit Freigabe), Integration geladen, 3 Dienste registriert
- [x] Live-Smoke-Test: `scan` mit unbekanntem Barcode → „Barcode … is not known in Grocy“ (Verbindung + Fehlerpfad ok)
- [ ] Manuelle Abnahme in HA: Testprodukt mit Barcode anlegen, Plus/Minus über Entwicklerwerkzeuge → Aktionen

## M2b – Barcode-Lookup Open Food Facts (v0.3.0)
- [x] Nutzer-Freigabe (kostenlos, unkritisch)
- [x] `GrocyClient.external_lookup` (`?add=true`), leere Antworten robust als `null`
- [x] Option `external_barcode_lookup` (Std. an) im Options-Flow, de/en
- [x] Nur bei Plus; Minus legt nie an; Plugin-Fehler/nichts gefunden → „Barcode unbekannt“
- [x] Event `grocy_ai_product_created`, Antwortfeld `product_created`
- [x] Tests (29 grün)
- [x] Release v0.3.0, HACS-Update + Neustart (mit Freigabe), Integration geladen, keine Log-Fehler
- [ ] Live-Abnahme mit echtem, unbekanntem Barcode (Nutzer; bewusst kein Test mit Fantasie-Barcode, weil OFF Datenmüll enthält und ein Schrottprodukt anlegen könnte)

## M3 – MHD per Foto (v0.4.0)
- [ ] `ai.py`: Prompt + Struktur + Parsing (TT.MM.JJ, MM/JJJJ → Monatsende, …)
- [ ] Plausibilitätsprüfung + Fallback + Event `grocy_ai_best_before_failed`
- [ ] Service `read_best_before`; `image` in `add_stock`/`scan`
- [ ] Tests (gemocktes `ai_task.generate_data`)
- [ ] Abnahme mit echten Fotos (Kamera / Upload)

## M4 – Ablauf-Benachrichtigungen & Sensoren (v0.5.0)
- [ ] `coordinator.py` (Polling `/stock/volatile`)
- [ ] Sensoren expiring/expired/missing
- [ ] Tägliche Benachrichtigung zur Uhrzeit X (Options-Flow), max. 1×/Tag
- [ ] Service `check_expiring`, Event `grocy_ai_product_expiring`
- [ ] Tests

## M5 – Bring!-Sync (v0.6.0)
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
- 2026-10-25: hassfest verbietet URLs mit Hostnamen in `strings.json`/Übersetzungen → Beispiel-URL per `description_placeholders` (`{url_example}`) einsetzen.
- 2026-10-25: Im öffentlichen Repo laufen jetzt alle Checks inkl. echter `hacs/action` grün.
- 2026-10-25: Grocy-Add-on: Standard `ssl: true` erwartet Zertifikate → auf false gesetzt. Port 80/tcp ist standardmäßig nicht nach außen gemappt; HA Core erreicht das Add-on intern über `http://a0d7b954-grocy` (Port 80). Ingress (Port 8099) nur für die Sidebar. Standard-Login admin/admin → sofort ändern. ha-mcp läuft auf dem PC und kann das interne Netz nicht direkt testen (Ingress-Proxy antwortet 302 → Add-on läuft).
- 2026-10-25: Erster Config-Flow → „Verbindung fehlgeschlagen“. Ursache: Das Grocy-Add-on erzeugt die nginx-Konfiguration für den Direktzugriff (Port 80) nur, wenn `bashio::app.port 80` gesetzt ist (init-nginx). Ohne Netzwerk-Port gibt es nur Ingress. Fix: Port 9192 eintragen, Add-on neu starten. Danach: `/api/system/info` ohne Key → 401 (erreichbar).
- 2026-10-25: Config-Entry `grocy_ai` mit `http://a0d7b954-grocy` eingerichtet, Status `loaded` → interne Verbindung HA Core → Grocy-Add-on bestätigt.
- 2026-10-25: Grocy-API `POST …/add` setzt ohne `best_before_date` das **heutige** Datum (nicht die Standard-Haltbarkeit). grocy_ai berechnet das Datum aus `default_best_before_days` (-1/0 → 2999-12-31). Unbekannter Barcode/Produkt → HTTP 400 mit `error_message`.
- 2026-10-25: `aioclient_mock.mock_calls` speichert die HTTP-Methode großgeschrieben (`POST`).
- 2026-10-25: Fehlermeldungen kommen über ha-mcp/API auf Englisch (Sprache des API-Aufrufers); in der deutschen HA-UI erscheinen die de-Übersetzungen.
- 2026-10-25: grocy_ai fragt beim Scannen bisher nur Grocys eigene Produktdatenbank ab. Grocy hat aber einen eingebauten externen Barcode-Lookup (Plugin `OpenFoodFactsBarcodeLookupPlugin`, Standard aktiv), per API `GET /api/stock/barcodes/external-lookup/{barcode}?add=true` → legt Produkt an und liefert die neue ID (200 mit `null`, wenn nichts gefunden).
- 2026-10-28: Nutzer hat Open-Food-Facts-Lookup freigegeben → v0.3.0; folgende Meilensteine je +1 Minor (M3 v0.4.0, M4 v0.5.0, M5 v0.6.0). Grocys OFF-Plugin sendet nur die Barcode-Ziffern an world.openfoodfacts.org; Lagerort/Einheit aus `product_presets_*`, sonst erster Eintrag.
