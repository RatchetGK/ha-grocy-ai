# CLAUDE.md – Regeln für Sitzungen in ha-grocy-ai

**Beginne jede Sitzung damit, [PLAN.md](PLAN.md) und [TODO.md](TODO.md) zu lesen.**
Halte beide laufend aktuell: Erledigtes abhaken, neue Erkenntnisse sofort in
TODO.md („Erkenntnisse“) eintragen, Architektur-/Schnittstellenänderungen in
PLAN.md nachziehen, Änderungen pro Version in CHANGELOG.md.

## Kommunikation
- Mit dem Nutzer **Deutsch**; Code, Kommentare, Commit-Messages **Englisch**.
- Nutzer arbeitet smartphone-lastig: alles läuft über GitHub (Push, Actions,
  Releases) und HACS – nie Dateien manuell auf den Pi kopieren.

## Struktur
```
custom_components/grocy_ai/   Integration (Domain grocy_ai)
  __init__.py  config_flow.py  api.py  const.py  manifest.json
  strings.json translations/{en,de}.json  services.py services.yaml ai.py
  photos.py media_source.py frontend/grocy-ai-panel.js  (später: coordinator.py, shopping.py, sensor.py)
tests/                        pytest-homeassistant-custom-component
scripts/check_private_data.py Secret-/Datenschutz-Scan (Hooks, CI, Skill)
.githooks/                    pre-commit, commit-msg, pre-push
.claude/skills/commit-push/   Skill: sicher committen & pushen
.local/                       lokal, NICHT versioniert (Denylist, Umgebungsdetails)
.github/workflows/            validate.yml (privacy+hassfest+HACS), lint-test.yml (ruff+pytest), release.yml
hacs.json  pyproject.toml  requirements_test.txt
```

## Konventionen
- Aktuelle HA-Developer-Konventionen: Config-Flow, `entry.runtime_data`,
  alles `async`, keine blockierenden Aufrufe im Event-Loop, HAs geteilte
  aiohttp-Session (`async_get_clientsession`).
- Grocy wird **direkt über REST** angesprochen (`api.py`), keine pygrocy-
  Abhängigkeit (Begründung PLAN.md D1). `manifest.json` → `requirements: []`.
- KI nur über `ai_task.generate_data` – keine KI-Keys/Anbieter-SDKs in dieser
  Integration.
- Services domain-weit in `async_setup` registrieren; Events heißen
  `grocy_ai_*`. Die Service/Event-Schnittstelle in PLAN.md §5 ist ein Vertrag
  (Tablet-App) → inkompatible Änderungen nur mit Major-Version.
- Texte für UI in `strings.json` pflegen und nach `translations/en.json`
  spiegeln, deutsche Übersetzung in `translations/de.json`.
- Lint: `ruff check .` und `ruff format .` (Konfig in `pyproject.toml`).

## Testen
- Lokal (Python ≥ 3.14 nötig, über uv):
  ```
  uv venv --python 3.14 .venv
  uv pip install --python .venv -r requirements_test.txt
  .venv/Scripts/python -m pytest
  ```
  Unter Windows können HA-Tests scheitern (Socket/Loop-Eigenheiten);
  maßgeblich ist die CI unter Linux.
- Neue Funktionen immer mit Tests (Grocy-API mit `aioclient_mock` mocken,
  `ai_task` per gemocktem Service).
- Live-Prüfung in HA nur lesend per ha-mcp (Logs, Entitäten, HACS-Status).

## Releasen (SemVer)
1. Version in `custom_components/grocy_ai/manifest.json` erhöhen.
2. CHANGELOG.md: Abschnitt `## [X.Y.Z] - YYYY-MM-DD` ergänzen.
3. Commit + Push auf `main` per Skill `commit-push`, Actions abwarten (grün).
4. `git tag -a vX.Y.Z -m vX.Y.Z && git push origin vX.Y.Z` → `release.yml` prüft
   Tag == manifest-Version und erstellt das GitHub-Release mit den
   CHANGELOG-Notizen.
5. In HA erscheint das Update in HACS.

## Harte Regeln
- **Secrets** (Grocy-API-Key, KI-Keys, Tokens) **niemals ins Repo** – nur über
  Config-/Options-Flow. Keine echten Keys in Tests/Fixtures (Dummy-Werte).
- **HACS-Updates installieren und HA neu starten NUR nach ausdrücklicher
  Bestätigung des Nutzers** in der aktuellen Sitzung. Prüfen (Logs, Entitäten,
  verfügbare Updates) ist erlaubt.
- Git-Identität ist repo-lokal gesetzt (RatchetGK, noreply-Adresse).
- Repo ist **öffentlich** (nötig für HACS). Sichtbarkeit nie ohne
  ausdrückliche Zustimmung ändern.
- **Vor jedem Commit, Push und Tag den Skill `commit-push`
  (`.claude/skills/commit-push/SKILL.md`) befolgen.** Nie `--no-verify`.
  Keine echten IPs, Namen, Entitäts-IDs, Gerätenamen oder Keys aus dem
  echten HA ins Repo – generische Beispiele verwenden. Lokale Details
  stehen in `.local/` (gitignored): `ENVIRONMENT.md`, `private-terms.txt`.
- Nach einem Klon: `git config core.hooksPath .githooks`.
