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
SECTION_TITLES = {
    "blog": "Blog",
    "fotos": "Fotos",
    "videos": "Videos",
    "de-otros": "De otres",
    "personal": "Personal",
}


def slugify(value: str) -> str:
    text = normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "nuevo-articulo"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Crea un nuevo artículo Markdown para Zola.")
    parser.add_argument("section", choices=sorted(SECTION_TITLES), help="Sección de destino.")
    parser.add_argument("title", help="Título del contenido.")
    parser.add_argument("--slug", help="Slug manual. Si se omite, se deriva del título.")
    parser.add_argument("--author", default="Martín Gaitán", help="Autor visible.")
    parser.add_argument("--tags", default="", help="Lista separada por comas.")
    parser.add_argument("--date", help="Fecha manual en formato ISO. Default: ahora.")
    parser.add_argument("--publish", action="store_true", help="Crear como publicado en vez de draft.")
    return parser.parse_args()


def build_front_matter(args: argparse.Namespace, slug: str, now: datetime) -> str:
    tags = [item.strip() for item in args.tags.split(",") if item.strip()]
    section_title = SECTION_TITLES[args.section]
    draft = "false" if args.publish else "true"
    tags_block = ",\n".join(f'    "{tag}"' for tag in tags)
    tag_links_block = ",\n".join(f'    {{ name = "{tag}", path = "" }}' for tag in tags)
    return f"""+++
title = "{args.title}"
slug = "{slug}"
date = {now.strftime("%Y-%m-%d %H:%M:%S")}
draft = {draft}
template = "article.html"
authors = [
    "{args.author}",
]
categories = [
    "{section_title}",
]
tags = [
{tags_block}
]

[extra]
section_slug = "{args.section}"
section_title = "{section_title}"
summary = ""
hero_image = ""
hero_alt = ""
subtitle = ""
deck = ""
author_links = [
    {{ name = "{args.author}", path = "" }},
]
tag_links = [
{tag_links_block}
]
comments = []
+++

"""


def main() -> int:
    args = parse_args()
    slug = args.slug or slugify(args.title)
    now = datetime.fromisoformat(args.date) if args.date else datetime.now()
    section_dir = CONTENT / args.section
    target = section_dir / f"{slug}.md"
    if target.exists():
        print(f"Ya existe: {target}", file=sys.stderr)
        return 1
    target.write_text(build_front_matter(args, slug, now), encoding="utf-8")
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
