#!/usr/bin/env python3
"""Block secrets and private data from being committed or pushed.

Modes:
  --staged          scan files staged for commit (pre-commit)
  --range A..B      scan every file version added in a commit range (pre-push)
  --all             scan the working tree and the complete git history

Checks generic secret patterns (API keys, tokens, private keys, credentials in
URLs, private IPs, e-mail addresses) plus an optional, untracked denylist of
personal terms in ``.local/private-terms.txt`` (one term per line).

Exit code 1 if anything is found. Standard library only.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
DENYLIST = ROOT / ".local" / "private-terms.txt"

# Files that must never be tracked at all.
FORBIDDEN_PATHS = re.compile(
    r"(^|/)(secrets\.ya?ml|\.env(\..*)?|.*\.pem|.*\.key|id_rsa.*|\.storage/.*|"
    r"home-assistant_v2\.db|\.local/.*|.*\.p12|.*\.pfx)$",
    re.IGNORECASE,
)

PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("GitHub token", re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})")),
    ("OpenAI/Anthropic key", re.compile(r"\bsk-(ant-)?[A-Za-z0-9_-]{20,}")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}")),
    ("AWS access key", re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("Private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("JWT / HA long-lived token", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.")),
    ("Credentials in URL", re.compile(r"[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s@]+@", re.IGNORECASE)),
    (
        "Hard-coded secret",
        re.compile(
            r"(api[_-]?key|token|secret|passw(or)?d)\s*[:=]\s*['\"][A-Za-z0-9_\-+/=]{16,}['\"]",
            re.IGNORECASE,
        ),
    ),
    (
        "Private IP address",
        re.compile(
            r"\b(10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|"
            r"172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b"
        ),
    ),
    ("E-mail address", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
]

# Values that look sensitive but are fine to publish.
ALLOWED = [
    re.compile(r"@users\.noreply\.github\.com$"),
    re.compile(r"^noreply@(anthropic|github)\.com$"),
    re.compile(r"^git@github\.com$"),
]

SKIP_FILES = {"scripts/check_private_data.py"}  # contains the patterns themselves


def git(*args: str) -> str:
    """Run git in the repository root and return stdout."""
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True, encoding="utf-8"
    ).stdout


def load_denylist() -> list[str]:
    """Return personal terms from the untracked denylist."""
    if not DENYLIST.exists():
        return []
    lines = (raw.strip() for raw in DENYLIST.read_text(encoding="utf-8").splitlines())
    return [line.lower() for line in lines if line and not line.startswith("#")]


def scan_text(path: str, text: str, terms: list[str]) -> list[str]:
    """Return findings for one file's content."""
    if path in SKIP_FILES:
        return []
    findings = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for name, pattern in PATTERNS:
            for match in pattern.finditer(line):
                value = match.group(0)
                if any(a.search(value) for a in ALLOWED):
                    continue
                findings.append(f"{path}:{lineno}: {name}: {mask(value)}")
        lowered = line.lower()
        findings.extend(
            f"{path}:{lineno}: private term from denylist: {mask(t)}" for t in terms if t in lowered
        )
    return findings


def mask(value: str) -> str:
    """Do not echo full secrets into logs."""
    return value if len(value) <= 6 else f"{value[:3]}...{value[-2:]}"


def blob(spec: str) -> str | None:
    """Read a git object as text, None for binary content."""
    data = subprocess.run(
        ["git", "cat-file", "-p", spec], cwd=ROOT, capture_output=True, check=True
    )
    if b"\0" in data.stdout[:8000]:
        return None
    return data.stdout.decode("utf-8", errors="replace")


def check_path(path: str) -> list[str]:
    """Flag files that must never be tracked."""
    return [f"{path}: forbidden file type"] if FORBIDDEN_PATHS.search(path) else []


def scan_staged(terms: list[str]) -> list[str]:
    """Scan the index (what is about to be committed)."""
    findings = []
    for path in git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z").split("\0"):
        if not path:
            continue
        findings += check_path(path)
        text = blob(f":{path}")
        if text is not None:
            findings += scan_text(path, text, terms)
    findings += scan_text("<commit message>", read_commit_msg(), terms)
    return findings


def read_commit_msg() -> str:
    """Return the pending commit message if git already wrote one."""
    msg = ROOT / ".git" / "COMMIT_EDITMSG"
    return msg.read_text(encoding="utf-8", errors="replace") if msg.exists() else ""


def scan_commits(revs: list[str], terms: list[str]) -> list[str]:
    """Scan every blob, path, message and author of the given commits."""
    findings: list[str] = []
    seen: set[str] = set()
    for rev in revs:
        meta = git("log", "-1", "--format=%an <%ae>%n%cn <%ce>%n%B", rev)
        findings += scan_text(f"<commit {rev[:8]}>", meta, terms)
        for entry in git("ls-tree", "-r", "-z", rev).split("\0"):
            if not entry:
                continue
            info, path = entry.split("\t", 1)
            obj = info.split()[2]
            if obj in seen:
                continue
            seen.add(obj)
            findings += check_path(path)
            text = blob(obj)
            if text is not None:
                findings += scan_text(f"{path}@{rev[:8]}", text, terms)
    return findings


def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--staged", action="store_true")
    group.add_argument("--range")
    group.add_argument("--all", action="store_true")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    terms = load_denylist()
    if args.staged:
        findings = scan_staged(terms)
    elif args.range:
        findings = scan_commits(git("rev-list", args.range).split(), terms)
    else:
        findings = scan_commits(git("rev-list", "--all").split(), terms)
        for path in git("ls-files", "-z").split("\0"):
            if path and (ROOT / path).is_file():
                text = (ROOT / path).read_text(encoding="utf-8", errors="replace")
                findings += check_path(path) + scan_text(path, text, terms)

    findings = sorted(set(findings))
    if not terms:
        print("note: no .local/private-terms.txt - only generic patterns checked")
    if findings:
        print("BLOCKED - possible secrets or private data:")
        print("\n".join(f"  {f}" for f in findings))
        return 1
    print("ok: no secrets or private data found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
