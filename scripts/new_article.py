#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path
from unicodedata import normalize


ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"
SECTIONS = ("blog", "fotos", "videos", "de-otros", "personal")


def slugify(value: str) -> str:
    text = normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "nuevo-articulo"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Crea un nuevo artículo Markdown para Nikola.")
    parser.add_argument("section", choices=SECTIONS, help="Sección de destino.")
    parser.add_argument("title", help="Título del contenido.")
    parser.add_argument("--slug", help="Slug manual. Si se omite, se deriva del título.")
    parser.add_argument("--author", default="Martín Gaitán", help="Autor visible.")
    parser.add_argument("--tags", default="", help="Lista separada por comas.")
    parser.add_argument("--date", help="Fecha manual en formato ISO. Default: ahora.")
    parser.add_argument("--draft", action="store_true", help="Crear como borrador.")
    return parser.parse_args()


def yaml_scalar(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def build_front_matter(args: argparse.Namespace, slug: str, now: datetime) -> str:
    tags = [item.strip() for item in args.tags.split(",") if item.strip()]
    lines = [
        "---",
        f"title: {yaml_scalar(args.title)}",
        f"slug: {slug}",
        f"date: {now.strftime('%Y-%m-%d %H:%M:%S')}",
        f"author: {yaml_scalar(args.author)}",
    ]
    if args.draft:
        lines.append("draft: true")
    if tags:
        lines.append("tags: " + ", ".join(tags))
    lines.extend(["---", "", "<!-- TEASER_END -->", ""])
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    slug = args.slug or slugify(args.title)
    now = datetime.fromisoformat(args.date) if args.date else datetime.now()
    target = CONTENT / args.section / f"{slug}.md"
    if target.exists():
        print(f"Ya existe: {target}", file=sys.stderr)
        return 1
    target.write_text(build_front_matter(args, slug, now), encoding="utf-8")
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
