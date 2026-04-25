#!/usr/bin/env -S uv run python
# /// script
# requires-python = ">=3.11"
# ///
"""Spell-check Spanish markdown content via hunspell (es_AR).

Designed to run as a pre-commit hook (file paths as args) or standalone
(scan every `content/**/*.md`).
"""

from __future__ import annotations

import argparse
import pathlib
import re
import shutil
import subprocess
import sys
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parent.parent
ALLOW_FILE = pathlib.Path(__file__).with_name("spell_allow.txt")
DICT = "es_AR"

RE_FRONTMATTER = re.compile(r"^\+\+\+\n.*?\n\+\+\+\n", re.DOTALL)
RE_FENCED_CODE = re.compile(r"```.*?```", re.DOTALL)
RE_INLINE_CODE = re.compile(r"`[^`]*`")
RE_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
RE_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
RE_AUTOLINK = re.compile(r"<https?://[^>]+>")
RE_BARE_URL = re.compile(r"https?://\S+")
RE_EMAIL = re.compile(r"\b[\w.+-]+@[\w.+-]+\b")
RE_REFERENCE_DEF = re.compile(r"^\[[^\]]+\]:\s*\S+.*$", re.MULTILINE)
RE_SHORTCODE = re.compile(r"\{%.*?%\}|\{\{.*?\}\}", re.DOTALL)
RE_HTML_TAG = re.compile(r"<[^>]+>")
RE_TOKEN = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ][A-Za-zÁÉÍÓÚÜÑáéíóúüñ']*")


def strip_markdown(text: str) -> str:
    text = RE_FRONTMATTER.sub(lambda m: "\n" * m.group(0).count("\n"), text, count=1)
    text = RE_FENCED_CODE.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    text = RE_INLINE_CODE.sub(" ", text)
    text = RE_IMAGE.sub(" ", text)
    text = RE_AUTOLINK.sub(" ", text)
    text = RE_BARE_URL.sub(" ", text)
    text = RE_EMAIL.sub(" ", text)
    text = RE_LINK.sub(r"\1", text)
    text = RE_REFERENCE_DEF.sub(" ", text)
    text = RE_SHORTCODE.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    text = RE_HTML_TAG.sub(" ", text)
    return text


def load_allowlist() -> set[str]:
    if not ALLOW_FILE.exists():
        return set()
    out: set[str] = set()
    for line in ALLOW_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.add(line.lower())
    return out


def hunspell_unknown(words: list[str]) -> set[str]:
    if not words:
        return set()
    proc = subprocess.run(
        ["hunspell", "-d", DICT, "-l"],
        input="\n".join(words) + "\n",
        capture_output=True,
        text=True,
        check=False,
    )
    return {w for w in proc.stdout.splitlines() if w}


def collect_tokens(path: pathlib.Path) -> list[tuple[int, str]]:
    text = path.read_text(encoding="utf-8")
    body = strip_markdown(text)
    tokens: list[tuple[int, str]] = []
    for ln, line in enumerate(body.split("\n"), start=1):
        for m in RE_TOKEN.finditer(line):
            w = m.group(0)
            if len(w) <= 2:
                continue
            tokens.append((ln, w))
    return tokens


def check_files(paths: list[pathlib.Path], allow: set[str]) -> int:
    findings: list[tuple[pathlib.Path, int, str]] = []
    for path in paths:
        tokens = collect_tokens(path)
        unique = sorted({w for _, w in tokens if w.lower() not in allow})
        bad = hunspell_unknown(unique)
        bad = {w for w in bad if w.lower() not in allow}
        if not bad:
            continue
        for ln, w in tokens:
            if w in bad:
                findings.append((path, ln, w))
    if not findings:
        return 0
    grouped: dict[pathlib.Path, list[tuple[int, str]]] = {}
    for path, ln, w in findings:
        grouped.setdefault(path, []).append((ln, w))
    for path, items in grouped.items():
        rel = path.resolve().relative_to(ROOT) if path.resolve().is_relative_to(ROOT) else path
        print(f"\n{rel}")
        seen: set[tuple[int, str]] = set()
        for ln, w in items:
            key = (ln, w)
            if key in seen:
                continue
            seen.add(key)
            print(f"  {ln:>5}: {w}")
    distinct = sorted({w for _, _, w in findings}, key=str.lower)
    print(f"\n{len(findings)} ocurrencias / {len(distinct)} palabras desconocidas en {len(grouped)} archivo(s).")
    print("Si alguna es válida (nombre propio, extranjerismo, etc.) agregala a scripts/spell_allow.txt.")
    return 1


def list_unknown(paths: list[pathlib.Path], allow: set[str], top: int) -> int:
    counter: Counter[str] = Counter()
    for path in paths:
        tokens = collect_tokens(path)
        unique = sorted({w for _, w in tokens if w.lower() not in allow})
        bad = hunspell_unknown(unique)
        bad = {w for w in bad if w.lower() not in allow}
        for _, w in tokens:
            if w in bad:
                counter[w] += 1
    for w, n in counter.most_common(top):
        print(f"{n:>5}  {w}")
    return 0


def resolve_paths(args: list[str]) -> list[pathlib.Path]:
    if args:
        return [pathlib.Path(a) for a in args if a.endswith(".md")]
    return sorted((ROOT / "content").rglob("*.md"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="Archivos a revisar (default: content/**/*.md)")
    parser.add_argument("--list-unknown", action="store_true", help="Listar palabras desconocidas por frecuencia")
    parser.add_argument("--top", type=int, default=200, help="Cuántas palabras mostrar con --list-unknown")
    opts = parser.parse_args()

    if not shutil.which("hunspell"):
        print("ERROR: no encuentro `hunspell` en el PATH. Instalalo: sudo apt install hunspell hunspell-es", file=sys.stderr)
        return 2

    paths = [p for p in resolve_paths(opts.paths) if p.exists()]
    if not paths:
        return 0

    allow = load_allowlist()
    if opts.list_unknown:
        return list_unknown(paths, allow, opts.top)
    return check_files(paths, allow)


if __name__ == "__main__":
    sys.exit(main())
