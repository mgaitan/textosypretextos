#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["tomli-w>=1.2.0"]
# ///
"""Simplify Zola front matter while preserving the rendered site.

This is a one-shot migration script. It removes SPIP-era fields from article
sources, extracts static comments to data/comments.json, and removes inverse
article lists from author/tag pages.
"""
from __future__ import annotations

import json
import re
import sys
import tomllib
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import Any

import tomli_w

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"
DATA = ROOT / "data"
ARTICLE_SECTIONS = ("blog", "fotos", "videos", "de-otros", "personal")
SECTION_TITLES = {
    "blog": "Blog",
    "fotos": "Fotos",
    "videos": "Videos",
    "de-otros": "De otres",
    "personal": "Personal",
}
DROP_EXTRA_KEYS = {
    "legacy_id",
    "legacy_url",
    "section_slug",
    "section_title",
    "summary",
    "visits",
    "popularite",
    "comment_count",
    "author_links",
    "tag_links",
    "comments",
}


def split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("+++"):
        return "", text
    end = text.find("\n+++", 3)
    if end == -1:
        return "", text
    return text[3:end].strip(), text[end + 4 :].lstrip("\n")


def stringify_dates(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat(sep=" ") if isinstance(value, datetime) else value.isoformat()
    if isinstance(value, list):
        return [stringify_dates(item) for item in value]
    if isinstance(value, dict):
        return {key: stringify_dates(item) for key, item in value.items()}
    return value


def render_frontmatter(data: dict[str, Any]) -> str:
    return tomli_w.dumps(data)


def slugify(value: str) -> str:
    text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()


def load_toml(path: Path) -> tuple[dict[str, Any], str]:
    fm_text, body = split_frontmatter(path.read_text(encoding="utf-8"))
    if not fm_text:
        return {}, body
    return tomllib.loads(fm_text), body


def canonical_tags() -> dict[str, str]:
    tags: dict[str, str] = {}
    tags_dir = CONTENT / "etiquetas"
    if tags_dir.is_dir():
        for path in tags_dir.glob("*.md"):
            if path.name == "_index.md":
                continue
            fm, _body = load_toml(path)
            title = str(fm.get("title") or path.stem)
            tags[title.casefold()] = title
            tags[slugify(title)] = title
    return tags


def simplify_article(path: Path, tag_names: dict[str, str]) -> tuple[str, list[dict[str, Any]]]:
    fm, body = load_toml(path)
    if not fm:
        return "", []

    section = path.parent.name
    slug = str(fm.get("slug") or path.stem)
    key = f"{section}/{slug}"
    extra = dict(fm.get("extra") or {})
    comments = stringify_dates(extra.get("comments") or [])

    # Keep Zola essentials and editorial fields only.
    fm.pop("categories", None)
    if fm.get("draft") is False:
        fm.pop("draft", None)
    if fm.get("template") == "article.html":
        fm.pop("template", None)

    tags = []
    seen = set()
    for tag in list(fm.get("tags") or []):
        name = tag_names.get(str(tag).casefold()) or tag_names.get(slugify(str(tag))) or str(tag)
        marker = slugify(name)
        if marker in seen:
            continue
        seen.add(marker)
        tags.append(name)
    fm["tags"] = tags

    for drop_key in DROP_EXTRA_KEYS:
        extra.pop(drop_key, None)
    if not extra.get("hero_image"):
        extra.pop("hero_image", None)
        extra.pop("hero_alt", None)
    elif not extra.get("hero_alt"):
        extra.pop("hero_alt", None)
    for optional_empty in ("surtitle", "subtitle", "deck"):
        if extra.get(optional_empty) == "":
            extra.pop(optional_empty, None)
    if extra:
        fm["extra"] = extra
    else:
        fm.pop("extra", None)

    path.write_text("+++\n" + render_frontmatter(fm).strip() + "\n+++\n\n" + body.rstrip() + "\n", encoding="utf-8")
    return key, comments


def simplify_metadata_page(path: Path, *drop_keys: str) -> None:
    fm, body = load_toml(path)
    if not fm:
        return
    extra = dict(fm.get("extra") or {})
    extra.pop("legacy_id", None)
    extra.pop("legacy_slug", None)
    for drop_key in drop_keys:
        extra.pop(drop_key, None)
    if extra:
        fm["extra"] = extra
    else:
        fm.pop("extra", None)
    path.write_text("+++\n" + render_frontmatter(fm).strip() + "\n+++\n\n" + body.rstrip() + "\n", encoding="utf-8")


def main() -> int:
    tag_names = canonical_tags()
    comments_path = DATA / "comments.json"
    comments_by_article: dict[str, list[dict[str, Any]]] = {}
    if comments_path.exists():
        comments_by_article = json.loads(comments_path.read_text(encoding="utf-8"))

    for section in ARTICLE_SECTIONS:
        section_dir = CONTENT / section
        if not section_dir.is_dir():
            continue
        for path in sorted(section_dir.glob("*.md")):
            if path.name == "_index.md":
                continue
            key, comments = simplify_article(path, tag_names)
            if key and comments:
                comments_by_article[key] = comments

    for path in (CONTENT / "autores").glob("*.md"):
        if path.name != "_index.md":
            simplify_metadata_page(path, "article_paths")
    for path in (CONTENT / "etiquetas").glob("*.md"):
        if path.name != "_index.md":
            simplify_metadata_page(path, "article_paths")
    for path in (CONTENT / "blog" / "subsecciones").glob("*.md"):
        if path.name != "_index.md":
            simplify_metadata_page(path, "article_paths", "subsection_slug")

    DATA.mkdir(exist_ok=True)
    comments_path.write_text(
        json.dumps(comments_by_article, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"Extracted comments for {len(comments_by_article)} articles")
    return 0


if __name__ == "__main__":
    sys.exit(main())
