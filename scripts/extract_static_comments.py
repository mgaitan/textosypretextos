#!/usr/bin/env -S uv run python
# /// script
# requires-python = ">=3.11"
# dependencies = ["ruamel.yaml"]
# ///
"""Mueve comentarios heredados desde front matter a data/comments.json."""

from __future__ import annotations

import argparse
import io
import json
import re
from pathlib import Path

from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parent.parent
RE_YAML_FM = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)
SECTIONS = ["blog", "fotos", "videos", "de-otros", "personal"]


def iter_markdown() -> list[Path]:
    files: list[Path] = []
    for section in SECTIONS:
        files.extend((ROOT / "content" / section).glob("*.md"))
    return sorted(files)


def dump_yaml(yaml: YAML, data) -> str:
    stream = io.StringIO()
    yaml.dump(data, stream)
    return stream.getvalue()


def comment_key(path: Path, meta: dict) -> str:
    section = path.parent.name
    slug = str(meta.get("slug") or path.stem)
    return f"{section}/{slug}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 120

    comments_by_article: dict[str, list[dict]] = {}
    changed_files = 0

    for path in iter_markdown():
        text = path.read_text(encoding="utf-8")
        match = RE_YAML_FM.match(text)
        if not match:
            continue
        meta = yaml.load(match.group(1))
        if not isinstance(meta, dict):
            continue
        comments = meta.pop("comments", None)
        if not comments:
            continue
        comments_by_article[comment_key(path, meta)] = comments
        changed_files += 1
        if args.apply:
            path.write_text(f"---\n{dump_yaml(yaml, meta)}---\n{match.group(2)}", encoding="utf-8")

    if args.apply:
        target = ROOT / "data" / "comments.json"
        target.parent.mkdir(exist_ok=True)
        target.write_text(
            json.dumps(comments_by_article, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    action = "Actualizados" if args.apply else "Cambiarían"
    print(f"{action}: {changed_files} artículos")
    print(f"Comentarios exportados: {sum(len(items) for items in comments_by_article.values())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
