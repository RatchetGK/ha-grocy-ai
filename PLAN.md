# PLAN – ha-grocy-ai (`grocy_ai`)

> Referenzdokument. Wird bei jeder Änderung an Architektur, Schnittstelle oder
> Meilensteinen aktualisiert. Aufgaben-Checkliste: [TODO.md](TODO.md).

## 1. Ziel

Eine Home-Assistant-Custom-Integration (HACS Custom Repository), die Grocy um
KI-Funktionen und Automatisierung erweitert. **Grocy bleibt die Datenbasis.**

1. **Bestand per Barcode buchen** – „Plus“ (eingekauft, +X) und „Minus“
   (verbraucht, −X).
2. **MHD per Foto** (optional pro Buchung) – Foto → KI liest MHD (ggf.
   Produktname/Menge) → Buchung mit echtem MHD. Über HA **AI Task**
   (`ai_task.generate_data` mit Anhang + strukturierter Ausgabe), damit der
   KI-Anbieter austauschbar bleibt. Ohne Foto: Grocys Standard-Haltbarkeit des
   Produkts bzw. „läuft nie ab“.
3. **Benachrichtigungen** bei bald ablaufenden Produkten (Vorlauf in Tagen +
   Notify-Dienst im Options-Flow).
4. **Mindestbestand → Bring!** – Produkte unter Mindestbestand/leer landen
   automatisch auf der einstellbaren To-do-Entität, ohne Duplikate.
5. **Saubere Services/Events**, damit später ein Küchen-Tablet (eigene App,
   nicht Teil des Projekts) oder Zigbee-Taster andocken können.

**Nicht im Scope:** Android-Tablet-App, eigene Hardware, Ersatz von Grocy.

## 2. Umgebung (Stand 2026-10-25)

| Thema | Wert |
|---|---|
| Home Assistant | 2026.10.x, HA OS auf Raspberry Pi, Sprache `de` |
| AI Task | eine AI-Task-Entität vorhanden – `generate_data` unterstützt Attachments + `structure` |
| To-do-Listen | mehrere, darunter Bring!-Listen (konkrete Entitäten nur lokal in `.local/ENVIRONMENT.md`) |
| Grocy | noch **nicht** installiert (geplant: Community-Add-on) |
| Grocy-HACS-Integration | im HACS-Store aktuell als `iamkarlson/grocy` gelistet; wird von `grocy_ai` **nicht** benötigt |
| Test-Toolchain | `pytest-homeassistant-custom-component` 0.13.374 → HA 2026.10.3, **Python ≥ 3.14** |

## 3. Architektur

```mermaid
flowchart LR
    subgraph Inputs["Auslöser"]
        TAB["Küchen-Tablet-App<br/>(später, extern)"]
        ZB["Zigbee-Taster /<br/>Automationen"]
        UI["HA-UI / Skripte"]
    end

    subgraph HA["Home Assistant"]
        direction TB
        SVC["grocy_ai Services<br/>add_stock · consume_stock · scan<br/>read_best_before · sync_shopping_list<br/>check_expiring"]
        CO["GrocyAiCoordinator<br/>(DataUpdateCoordinator)"]
        API["GrocyClient<br/>(async REST, aiohttp)"]
        AIT["ai_task.generate_data<br/>(Anbieter austauschbar)"]
        NTF["notify.*"]
        TODO["todo.* (Bring!)"]
        EVT(["Events grocy_ai_*"])
        ENT["Sensoren<br/>ablaufend · unter Mindestbestand"]
    end

    GROCY[("Grocy<br/>(Add-on, REST /api)")]

    TAB & ZB & UI --> SVC
    SVC -->|Foto| AIT
    AIT -->|MHD JSON| SVC
    SVC --> API --> GROCY
    CO --> API
    CO --> ENT
    CO -->|ablaufend| NTF
    CO -->|unter Mindestbestand| TODO
    SVC & CO --> EVT
```

### Module (Zielbild)

| Datei | Aufgabe |
|---|---|
| `__init__.py` | Setup/Unload des Config-Entries, Services registrieren (`async_setup`) |
| `config_flow.py` | Config-Flow (Grocy-URL, API-Key, SSL) + Options-Flow (Vorlauf, Notify, To-do, AI-Task) |
| `api.py` | `GrocyClient` – dünner async-Wrapper um die Grocy-REST-API |
| `coordinator.py` | Pollt Grocy (`/stock/volatile`), triggert Benachrichtigung + Bring!-Sync |
| `services.py` | Service-Handler + Schemas |
| `ai.py` | MHD-Erkennung via `ai_task.generate_data` |
| `shopping.py` | Bring!-/To-do-Abgleich ohne Duplikate |
| `sensor.py` | Zählsensoren (ablaufend, abgelaufen, unter Mindestbestand) |
| `const.py` | Konstanten, Event-Namen, Options-Keys |

## 4. Datenfluss

### 4.1 Plus-Buchung mit Foto
1. Auslöser ruft `grocy_ai.add_stock` mit `barcode`, `amount`, optional `image`.
2. `GrocyClient.get_product_by_barcode(barcode)` → Produkt (404 → Event
   `grocy_ai_barcode_unknown`, Service-Fehler).
3. Wenn `best_before_date` übergeben → direkt verwenden. Sonst wenn `image` →
   `ai_task.generate_data` (Anhang, Struktur `{best_before_date, product_name,
   amount, confidence}`) → Datum validieren (Format, plausibel: nicht > 15 Jahre
   in der Zukunft, nicht deutlich in der Vergangenheit) → bei Fehler Fallback +
   Event `grocy_ai_best_before_failed`.
4. Sonst kein Datum übergeben → Grocy setzt Standard-Haltbarkeit des Produkts
   (`default_best_before_days`; `-1` = läuft nie ab).
5. `POST /api/stock/products/by-barcode/{barcode}/add`.
6. Event `grocy_ai_stock_added`, Coordinator-Refresh.

### 4.2 Minus-Buchung
`grocy_ai.consume_stock` → `POST /api/stock/products/by-barcode/{barcode}/consume`
(`amount`, `spoiled`) → Event `grocy_ai_stock_consumed` → Refresh. Bestand 0 →
Grocy meldet Fehler → Event `grocy_ai_error`, Service-Fehler mit klarem Text.

### 4.3 Periodisch (Coordinator, Standard alle 15 min)
- `GET /api/stock/volatile?due_soon_days=N` → `due_products`,
  `overdue_products`, `expired_products`, `missing_products`.
- Ablaufend: einmal täglich zur eingestellten Uhrzeit Sammel-Benachrichtigung
  über den gewählten Notify-Dienst + je Produkt Event `grocy_ai_product_expiring`.
- Mindestbestand: `missing_products` (Grocy liefert hier Produkte unter
  `min_stock_amount`) → Abgleich mit offenen Einträgen der To-do-Entität →
  nur fehlende hinzufügen (`todo.add_item`).

### 4.4 Duplikat-Vermeidung Bring!
- Vergleich normalisiert (lowercase, getrimmt) gegen alle Einträge mit Status
  `needs_action` (`todo.get_items`).
- Zusätzlich merkt sich die Integration (HA `Store`) welche Produkte sie selbst
  hinzugefügt hat; ein Produkt wird erst wieder hinzugefügt, nachdem es einmal
  über Mindestbestand war (verhindert Re-Add, wenn jemand den Eintrag manuell
  abhakt, aber noch nicht eingebucht hat).

## 5. Schnittstelle (Services & Events)

Stabile Schnittstelle für Tablet-App und Taster. Änderungen = SemVer-Minor
(neu) bzw. -Major (inkompatibel). Alle Services akzeptieren entweder
`barcode` **oder** `product_id`. Bei mehreren Config-Entries optional
`config_entry_id`.

### Services

| Service | Felder | Antwort (`response`) |
|---|---|---|
| `grocy_ai.add_stock` | `barcode`/`product_id`, `amount` (Std. 1), `best_before_date` (opt.), `image` (opt., Media-Selector), `price` (opt.), `location_id` (opt.) | `{product_id, product_name, amount, best_before_date, best_before_source: manual\|ai\|default}` |
| `grocy_ai.consume_stock` | `barcode`/`product_id`, `amount` (Std. 1), `spoiled` (Std. false) | `{product_id, product_name, amount, stock_amount}` |
| `grocy_ai.scan` | `barcode`, `mode: plus\|minus`, `amount`, `image` (opt.) | wie add/consume – Komfort-Service für Taster/Tablet |
| `grocy_ai.read_best_before` | `image` | `{best_before_date, product_name, amount, confidence}` – nur Erkennung, keine Buchung |
| `grocy_ai.sync_shopping_list` | – | `{added: [...], skipped: [...]}` |
| `grocy_ai.check_expiring` | `days` (opt.), `notify` (Std. true) | `{expiring: [...], expired: [...]}` |

### Events

| Event | Daten |
|---|---|
| `grocy_ai_stock_added` | `product_id, product_name, barcode, amount, best_before_date, best_before_source` |
| `grocy_ai_stock_consumed` | `product_id, product_name, barcode, amount, spoiled, stock_amount` |
| `grocy_ai_barcode_unknown` | `barcode, mode` (Tablet kann Produkt-Anlage anbieten) |
| `grocy_ai_best_before_failed` | `barcode, reason` |
| `grocy_ai_product_expiring` | `product_id, product_name, best_before_date, days_left` |
| `grocy_ai_shopping_item_added` | `product_id, product_name, todo_entity_id` |
| `grocy_ai_error` | `service, message` |

### Entitäten (ab M4)
`sensor.grocy_ai_expiring_products`, `sensor.grocy_ai_expired_products`,
`sensor.grocy_ai_missing_products` (Zustand = Anzahl, Attribut = Liste).

## 6. Entscheidungen

| # | Entscheidung | Begründung |
|---|---|---|
| D1 | **Direkte Grocy-REST-API** (eigener `GrocyClient` mit HAs geteilter `aiohttp`-Session) statt `pygrocy`/`pygrocy2` | `pygrocy` ist synchron (`requests`) → Executor nötig; Original-`pygrocy` ist seit Jahren unverändert, `pygrocy2` ist ein Fork. Wir brauchen nur ~8 Endpunkte. Eine eigene PyPI-Abhängigkeit kann mit der Grocy-HACS-Integration kollidieren (gleiches Paket, andere Version → HA installiert nur eine). Direkt-REST = async, keine Abhängigkeit, volle Kontrolle (z. B. `by-barcode`-Endpunkte, `best_before_date`). |
| D2 | **Kein Abhängigkeitszwang zur Grocy-HACS-Integration** | Wir sprechen Grocy selbst an; die Grocy-Integration kann parallel laufen (Sensoren/Chores), muss aber nicht. |
| D3 | **AI über `ai_task.generate_data`** mit `structure` + `attachments` | Anbieter austauschbar, keine KI-Keys in unserer Integration. AI-Task-Entität im Options-Flow wählbar (leer = HA-Standard). |
| D4 | Bilder als **Media-Source-ID** (`media_content_id`, z. B. `media-source://camera/camera.x` oder `media-source://image_upload/...`) | Das ist genau das Format, das `ai_task` für Attachments erwartet; Tablet kann per Image-Upload liefern. |
| D5 | Services domain-weit in `async_setup` registrieren | HA-Konvention (Quality Scale „action-setup“); Services existieren auch wenn Grocy gerade offline ist. |
| D6 | Secrets nur im Config-Entry (`api_key`), Diagnostik redacted | Projektregel; nichts im Repo. |
| D7 | Konfig: Verbindung im Config-Flow, Verhalten (Vorlauf, Notify, To-do, AI-Task, Uhrzeit) im **Options-Flow** | Verhalten ist änderbar ohne Neueinrichtung. |
| D8 | Mindest-HA **2026.10.0**, Tests mit Python 3.14 | Entspricht `pytest-homeassistant-custom-component` und der installierten HA-Version. |
| D9 | Releases: Tag `vX.Y.Z` → Action prüft `manifest.json`-Version == Tag → GitHub-Release mit Notes aus CHANGELOG | Smartphone-Workflow: Release in GitHub, Update in HACS. HACS lädt den Tag; zusätzlich `grocy_ai.zip` als Asset für manuelle Installation (D13). |
| D10 | `iot_class: local_polling`, `integration_type: service` | Grocy lokal, wird gepollt; kein physisches Gerät. |
| D11 | Git-Autor im Repo: `RatchetGK <163332573+RatchetGK@users.noreply.github.com>` (repo-lokal) | Kein globaler Git-Name gesetzt; noreply-Adresse schützt die echte E-Mail. |
| D12 | Lizenz MIT | Standard für HACS-Integrationen. |
| D13 | **Repo öffentlich, Historie neu gestartet** (2026-10-25) | HACS braucht ein dauerhaft öffentliches Repo. Das zwischenzeitlich private Repo enthielt private Angaben (interne IP, Vornamen in Entitäts-IDs) in alten Commits; auf GitHub lassen sich alte Commits nicht sicher entfernen → altes Repo in `ha-grocy-ai-old` umbenannt (privat), neues öffentliches Repo mit einem sauberen Initial-Commit. Release enthält zusätzlich `grocy_ai.zip`. |
| D14 | **Datenschutz-Schutzschichten**: Skill `commit-push`, Git-Hooks (`.githooks`: pre-commit, commit-msg, pre-push) mit `scripts/check_private_data.py`, untracked Denylist `.local/private-terms.txt`, CI-Job „Secrets & private data“ (Skript + gitleaks) | Öffentliches Repo: Secrets/private Daten dürfen nie committet werden; mehrere unabhängige Prüfungen vor Commit, vor Push und nach Push. |

## 7. Meilensteine & Abnahmekriterien

### M1 – Gerüst & CI (v0.1.0) ✅ erledigt 2026-10-25
- Repo mit `hacs.json`, `manifest.json`, Integration mit Config-Flow
  (URL, API-Key, SSL; Verbindungstest gegen `/api/system/info`) + Options-Flow.
- Actions: hassfest + HACS-Validierung bei jedem Push; ruff + pytest; Release
  bei Tag.
- **Abnahme:** alle Actions grün, Release `v0.1.0` existiert, Integration
  erscheint nach HACS-Installation in „Integration hinzufügen“.
- **Ergebnis:** Actions grün (hassfest, HACS-Struktur, ruff, pytest 9/9),
  Release v0.1.0 mit `grocy_ai.zip` (neu erstellt im öffentlichen Repo, D13).
  HACS-Installation in HA steht noch aus.

### M2 – Grocy-Anbindung & Barcode-Buchung (v0.2.0)
- `GrocyClient` (Produkt per Barcode, add, consume, volatile), Fehlerklassen.
- Services `add_stock`, `consume_stock`, `scan` + Events.
- **Abnahme:** Mit installiertem Grocy: Plus/Minus per Service in den
  Entwicklerwerkzeugen ändert Bestand in Grocy; unbekannter Barcode feuert
  `grocy_ai_barcode_unknown`; Tests mit gemockter API.

### M3 – MHD per Foto (v0.3.0)
- `read_best_before` + `image` in `add_stock`/`scan` über `ai_task`.
- Plausibilitätsprüfung + Fallback auf Grocy-Standard.
- **Abnahme:** Foto eines MHD-Aufdrucks (Kamera-Snapshot/Upload) → korrektes
  Datum in Grocy; unlesbares Foto → Fallback + Event.

### M4 – Ablauf-Benachrichtigungen & Sensoren (v0.4.0)
- Coordinator, Sensoren, tägliche Benachrichtigung, `check_expiring`.
- **Abnahme:** Produkt mit MHD in < N Tagen → genau eine Benachrichtigung pro
  Tag auf dem gewählten Notify-Dienst.

### M5 – Bring!-Sync (v0.5.0)
- Mindestbestand/leer → To-do-Entität, ohne Duplikate, Store für Zustand.
- **Abnahme:** Produkt unter Mindestbestand erscheint genau einmal auf Bring!;
  wiederholte Läufe erzeugen keine Duplikate.

### M6 – Härtung (v1.0.0)
- Diagnostics, Reauth-Flow, Repair-Issues bei Grocy offline, Übersetzungen
  de/en vollständig, Doku für Tablet-Entwickler, Quality-Scale-Check.
- **Abnahme:** 2 Wochen Alltagsbetrieb ohne Fehler im Log.

## 8. Risiken / offene Punkte

| Risiko / Frage | Umgang |
|---|---|
| Private Daten/Secrets landen versehentlich im öffentlichen Repo. | D14; bei Leck: Schlüssel sofort widerrufen, nicht nur aus Historie löschen. |
| Frischer Klon ohne `.local/private-terms.txt` / ohne `core.hooksPath`. | Skill `commit-push` Schritt 1 prüft beides. |
| Erreichbarkeit des Grocy-Add-ons aus HA: Ingress-only vs. Port. Interner Hostname vermutlich `http://a0d7b954-grocy` (Port 80) – **zu verifizieren** nach Installation. | In README dokumentieren, Config-Flow-Fehlertext mit Hinweis. |
| KI liest MHD falsch (Formate „31.12.26“, „12/2026“, nur Monat/Jahr). | Prompt mit Formatregeln, Monats-Datum → letzter Tag des Monats, Plausibilitätsprüfung, `confidence` im Ergebnis, Fallback. |
| Bring!-Artikelnamen weichen von Grocy-Namen ab (Duplikat mit anderem Wortlaut). | Normalisierter Vergleich + eigener Store; später optional Mapping-Feld/Grocy-Userfield. |
| Unbekannte Barcodes (Produkt fehlt in Grocy). | Event für Tablet; Produktanlage evtl. später (Open Food Facts) – nicht in M2. |
| `pytest-homeassistant-custom-component` läuft unter Windows nur eingeschränkt. | Tests lokal via `uv` + Python 3.14 versuchen; maßgeblich ist CI (Linux). |
| HACS-Validierung „brands“ verlangt Eintrag im home-assistant/brands-Repo. | Check in CI ignoriert (`ignore: brands`); für Custom Repository nicht nötig. |
| `hacs/action` validiert keine privaten Repos. | Repo ist öffentlich; Ersatz-Job „HACS structure“ greift nur, falls es je wieder privat wird. |
| Zwei Grocy-Integrationen gleichzeitig (iamkarlson/grocy + grocy_ai). | Keine geteilten Abhängigkeiten (D1/D2) → kein Konflikt. |
