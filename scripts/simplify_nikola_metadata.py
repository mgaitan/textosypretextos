#!/usr/bin/env -S uv run python
# /// script
# requires-python = ">=3.11"
# dependencies = ["ruamel.yaml"]
# ///
"""Simplifica front matter YAML ya migrado a Nikola."""

from __future__ import annotations

import argparse
import io
import re
from pathlib import Path

from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parent.parent
RE_YAML_FM = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)

REMOVE_ALWAYS = {
    "section_slug",
    "section_title",
    "comment_count",
}


def iter_markdown(paths: list[str]) -> list[Path]:
    if paths:
        return [Path(path) for path in paths]
    sections = ["blog", "fotos", "videos", "de-otros", "personal"]
    files: list[Path] = []
    for section in sections:
        files.extend((ROOT / "content" / section).glob("*.md"))
    return sorted(files)


def dump_yaml(yaml: YAML, data) -> str:
    stream = io.StringIO()
    yaml.dump(data, stream)
    return stream.getvalue()


def simplify_file(path: Path, apply: bool) -> bool:
    text = path.read_text(encoding="utf-8")
    match = RE_YAML_FM.match(text)
    if not match:
        return False

    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 120
    data = yaml.load(match.group(1))
    if not isinstance(data, dict):
        return False

    original = dump_yaml(yaml, data)

    for field in REMOVE_ALWAYS:
        data.pop(field, None)

    if data.get("draft") is False:
        data.pop("draft", None)

    hero_image = data.get("hero_image")
    hero_alt = data.get("hero_alt")
    if hero_image and hero_alt and Path(str(hero_image)).name == str(hero_alt):
        data.pop("hero_alt", None)

    simplified = dump_yaml(yaml, data)
    if simplified == original:
        return False

    new_text = f"---\n{simplified}---\n{match.group(2)}"
    if apply:
        path.write_text(new_text, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    changed = []
    for path in iter_markdown(args.paths):
        if simplify_file(path, args.apply):
            changed.append(path)

    action = "Actualizados" if args.apply else "Cambiarían"
    print(f"{action}: {len(changed)} archivos")
    for path in changed[:40]:
        print(path.relative_to(ROOT))
    if len(changed) > 40:
        print(f"... y {len(changed) - 40} más")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
