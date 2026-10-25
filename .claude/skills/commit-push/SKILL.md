---
name: commit-push
description: Sicher committen und pushen in ha-grocy-ai (öffentliches Repo). IMMER verwenden, bevor in diesem Repo ein git commit, git push oder git tag ausgeführt wird – prüft vorher auf Secrets, Schlüssel und private Daten und bricht bei jedem Fund ab.
---

# Sicherer Commit & Push

Das Repo ist **öffentlich**. Alles, was gepusht wird, ist dauerhaft abgreifbar
(Forks, Caches, Actions-Logs) – auch nach späterem Löschen. Deshalb vor
**jedem** Commit und **jedem** Push diese Schritte vollständig ausführen.
Keine Abkürzungen, kein `--no-verify`.

## 1. Voraussetzungen prüfen
```bash
git config core.hooksPath        # muss ".githooks" sein
test -f .local/private-terms.txt && echo denylist ok
```
- Fehlt `core.hooksPath`: `git config core.hooksPath .githooks` setzen.
- Fehlt `.local/private-terms.txt` (z. B. frischer Klon): Nutzer fragen bzw.
  aus dem Gedächtnis neu anlegen (Begriffe: interne IP-Adressen, Vornamen von
  Familienmitgliedern/Listen, persönliche E-Mail, Namen persönlicher
  Entitäten). Die Datei ist per `.gitignore` ausgeschlossen und darf **nie**
  committet werden.

## 2. Änderungen ansehen
```bash
git status --short
git diff            # bzw. git diff --cached
```
Jede geänderte Datei selbst lesen und bewusst entscheiden, ob sie ins Repo
gehört. Nur gezielt stagen (`git add <dateien>`), kein blindes `git add -A`,
wenn unbekannte Dateien im Status auftauchen.

## 3. Manuelle Datenschutz-Prüfung (zusätzlich zum Skript)
Im Diff aktiv suchen nach – und entfernen bzw. durch Platzhalter ersetzen:
- **Schlüssel/Tokens/Passwörter** jeder Art (Grocy-API-Key, KI-Keys,
  HA-Long-Lived-Tokens, GitHub-Tokens) – auch in Tests, Logs, Screenshots.
- **Netzwerkdaten**: interne/externe IPs, Hostnamen, Ports der echten
  Installation, Nabu-Casa-/DuckDNS-URLs.
- **Personenbezogenes**: Namen (auch in Entitäts-IDs wie `todo.<name>`),
  E-Mail, Adresse, Standort/Zonen-Koordinaten, Handy-/Gerätenamen
  (`notify.mobile_app_<gerät>`).
- **Konkrete Entitäten aus dem echten HA** → generische Beispiele verwenden
  (`todo.shopping_list`, `ai_task.example`, `notify.mobile_app_phone`).
- Dateien wie `secrets.yaml`, `.env`, `*.db`, `.storage/`, Backups,
  Diagnose-Dumps, HA-Logs.
- Commit-Message selbst ebenfalls prüfen.
Lokale Details gehören nach `.local/` (nicht versioniert).

## 4. Automatische Prüfung
```bash
git add <dateien>
python scripts/check_private_data.py --staged
```
Bei `BLOCKED`: Fund beheben, **nicht** umgehen. Falls ein Treffer wirklich
harmlos ist (z. B. Dokumentations-Beispiel), Beispiel umformulieren statt
Ausnahme ins Skript einzubauen; Ausnahmen nur mit Begründung in
`ALLOWED` und Hinweis an den Nutzer.

## 5. Committen
Englische Commit-Message (Conventional Commits), endet mit:
```
Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```
Der `pre-commit`- und `commit-msg`-Hook prüfen erneut.

## 6. Vor dem Push
```bash
git fetch origin
python scripts/check_private_data.py --range origin/main..HEAD
```
Dann `git push origin main` (der `pre-push`-Hook prüft die Commits nochmals).
Für Releases zusätzlich die Schritte aus CLAUDE.md („Releasen“); Tags
ebenfalls nur nach diesem Ablauf pushen.

## 7. Nach dem Push
- `gh run list --commit $(git rev-parse HEAD)` – der CI-Job
  „Secrets & private data“ (eigenes Skript + gitleaks) muss grün sein.
- **Wurde doch etwas Sensibles gepusht:** sofort dem Nutzer melden, Schlüssel
  als kompromittiert behandeln (in Grocy/beim Anbieter widerrufen und neu
  erzeugen) – Löschen aus der Historie allein reicht nicht.

## 8. Dem Nutzer berichten
Kurz: was committet/gepusht wurde, dass die Prüfung sauber war (oder was
gefunden und entfernt wurde), CI-Status.
