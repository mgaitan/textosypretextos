#!/usr/bin/env -S uv run python
# /// script
# requires-python = ">=3.11"
# ///
"""Normalize obvious dialogue blocks in markdown content.

Conservative by design:
- only rewrites blocks with 2+ dialogue lines starting with `--`
- skips files that already use the `dialogo` shortcode for that block
- reports single/ambiguous candidates for manual review
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys
from dataclasses import dataclass

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"

RE_FRONTMATTER = re.compile(r"^\+\+\+\n.*?\n\+\+\+\n?", re.DOTALL)
RE_DIALOGUE_START = re.compile(r"^(\s*)--(?!-)(.*\S)?\s*$")
RE_DIALOGUE_IGNORE = re.compile(r"^\s*--+\s*$|^\s*--o--\s*$", re.IGNORECASE)
RE_DIALOGUE_SHORTCODE_START = re.compile(r"^\s*\{%\s*dialogo\(\)\s*%\}\s*$")
RE_DIALOGUE_SHORTCODE_END = re.compile(r"^\s*\{%\s*end\s*%\}\s*$")


@dataclass
class Block:
    start: int
    end: int
    lines: list[str]


def split_frontmatter(text: str) -> tuple[str, str]:
    match = RE_FRONTMATTER.match(text)
    if not match:
        return "", text
    return match.group(0), text[match.end() :]


def is_dialogue_line(line: str) -> bool:
    if RE_DIALOGUE_IGNORE.match(line):
        return False
    match = RE_DIALOGUE_START.match(line)
    if not match:
        return False
    rest = (match.group(2) or "").strip()
    return bool(rest)


def normalize_dialogue_line(line: str) -> str:
    match = RE_DIALOGUE_START.match(line)
    if not match:
        return line.rstrip()
    indent = match.group(1)
    rest = (match.group(2) or "").strip()
    return f"{indent}— {rest}".rstrip()


def find_blocks(lines: list[str]) -> tuple[list[Block], list[int]]:
    blocks: list[Block] = []
    ambiguous: list[int] = []
    in_shortcode = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if RE_DIALOGUE_SHORTCODE_START.match(line):
            in_shortcode = True
            i += 1
            continue
        if in_shortcode:
            if RE_DIALOGUE_SHORTCODE_END.match(line):
                in_shortcode = False
            i += 1
            continue
        if not is_dialogue_line(line):
            i += 1
            continue

        start = i
        candidate_indexes: list[int] = []
        j = i
        while j < len(lines):
            current = lines[j]
            if is_dialogue_line(current):
                candidate_indexes.append(j)
                j += 1
                continue
            if current.strip() == "":
                j += 1
                continue
            break

        if len(candidate_indexes) >= 2:
            block_lines = [normalize_dialogue_line(lines[idx]) for idx in candidate_indexes]
            blocks.append(Block(start=start, end=j, lines=block_lines))
        else:
            ambiguous.extend(candidate_indexes)
        i = j
    return blocks, ambiguous


def apply_blocks(lines: list[str], blocks: list[Block]) -> list[str]:
    if not blocks:
        return lines[:]
    out: list[str] = []
    cursor = 0
    for block in blocks:
        out.extend(lines[cursor:block.start])
        if out and out[-1].strip():
            out.append("")
        out.append("{% dialogo() %}")
        out.extend(block.lines)
        out.append("{% end %}")
        if block.end < len(lines) and lines[block.end].strip():
            out.append("")
        cursor = block.end
    out.extend(lines[cursor:])
    return out


def process_file(path: pathlib.Path, apply: bool) -> tuple[int, int]:
    text = path.read_text(encoding="utf-8")
    frontmatter, body = split_frontmatter(text)
    lines = body.splitlines()
    blocks, ambiguous = find_blocks(lines)

    rel = path.relative_to(ROOT)
    if not blocks and not ambiguous:
        return 0, 0

    if blocks:
        ranges = ", ".join(f"{b.start + 1}-{b.end}" for b in blocks)
        print(f"{rel}: {len(blocks)} bloque(s) candidatos en líneas {ranges}")
    if ambiguous:
        joined = ", ".join(str(n + 1) for n in ambiguous[:10])
        suffix = "…" if len(ambiguous) > 10 else ""
        print(f"{rel}: {len(ambiguous)} línea(s) ambiguas para revisión manual ({joined}{suffix})")

    if apply and blocks:
        new_body = "\n".join(apply_blocks(lines, blocks))
        if body.endswith("\n"):
            new_body += "\n"
        path.write_text(frontmatter + new_body, encoding="utf-8")
    return len(blocks), len(ambiguous)


def resolve_paths(args: list[str]) -> list[pathlib.Path]:
    if args:
        return [pathlib.Path(arg).resolve() for arg in args]
    return sorted(CONTENT.rglob("*.md"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="Archivos a revisar (default: content/**/*.md)")
    parser.add_argument("--apply", action="store_true", help="Escribir cambios en los archivos")
    opts = parser.parse_args()

    paths = [path for path in resolve_paths(opts.paths) if path.exists() and path.suffix == ".md"]
    total_blocks = 0
    total_ambiguous = 0
    for path in paths:
        blocks, ambiguous = process_file(path, apply=opts.apply)
        total_blocks += blocks
        total_ambiguous += ambiguous

    mode = "apply" if opts.apply else "dry-run"
    print(
        f"\nResumen ({mode}): {total_blocks} bloque(s) candidatos, "
        f"{total_ambiguous} línea(s) ambiguas."
    )
    if total_ambiguous:
        print("Revisá manualmente los casos ambiguos antes de asumir que todo quedó listo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
