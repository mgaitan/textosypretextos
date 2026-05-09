#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# ///
"""Build derived data for Zola templates from article front matter."""
from __future__ import annotations

import json
import re
import sys
import tomllib
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import Any

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


def split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("+++"):
        return "", text
    end = text.find("\n+++", 3)
    if end == -1:
        return "", text
    return text[3:end].strip(), text[end + 4 :].lstrip("\n")


def load_page(path: Path) -> tuple[dict[str, Any], str]:
    fm_text, body = split_frontmatter(path.read_text(encoding="utf-8"))
    if not fm_text:
        return {}, body
    return tomllib.loads(fm_text), body


def slugify(value: str) -> str:
    text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()


def jsonable(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat(sep=" ") if isinstance(value, datetime) else value.isoformat()
    if isinstance(value, list):
        return [jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    return value


def read_comments() -> dict[str, list[dict[str, Any]]]:
    path = DATA / "comments.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_metadata_pages(folder: str) -> dict[str, dict[str, Any]]:
    pages: dict[str, dict[str, Any]] = {}
    root = CONTENT / folder
    if not root.is_dir():
        return pages
    for path in sorted(root.glob("*.md")):
        if path.name == "_index.md":
            continue
        fm, _body = load_page(path)
        title = str(fm.get("title") or path.stem)
        extra = dict(fm.get("extra") or {})
        pages[title] = {
            "title": title,
            "slug": str(fm.get("slug") or path.stem),
            "url": f"/{folder}/{fm.get('slug') or path.stem}/",
            "image": extra.get("image") or "",
            "gender": extra.get("gender") or "m",
            "is_owner": bool(extra.get("is_owner", False)),
            "group_name": extra.get("group_name") or "",
        }
    return pages


def article_url(section: str, fm: dict[str, Any], path: Path) -> str:
    slug = str(fm.get("slug") or path.stem)
    return f"/{section}/{slug}/"


def main() -> int:
    comments = read_comments()
    authors = read_metadata_pages("autores")
    tags = read_metadata_pages("etiquetas")
    tags_by_slug = {slugify(name): name for name in tags}

    pages: dict[str, dict[str, Any]] = {}
    recent_comments: list[dict[str, Any]] = []

    for section in ARTICLE_SECTIONS:
        section_dir = CONTENT / section
        if not section_dir.is_dir():
            continue
        for path in sorted(section_dir.glob("*.md")):
            if path.name == "_index.md":
                continue
            fm, _body = load_page(path)
            if not fm or fm.get("draft"):
                continue

            relpath = f"{section}/{path.name}"
            slug = str(fm.get("slug") or path.stem)
            key = f"{section}/{slug}"
            extra = dict(fm.get("extra") or {})
            page_authors = [str(author) for author in fm.get("authors") or []]
            page_tags = []
            for tag in fm.get("tags") or []:
                tag_name = str(tag)
                page_tags.append(tags_by_slug.get(slugify(tag_name), tag_name))

            page_data = {
                "title": fm.get("title") or path.stem,
                "url": article_url(section, fm, path),
                "section_slug": section,
                "section_title": SECTION_TITLES.get(section, section.replace("-", " ").title()),
                "date": jsonable(fm.get("date") or ""),
                "authors": page_authors,
                "tags": page_tags,
                "comment_count": len(comments.get(key, [])),
                "description": fm.get("description") or "",
                "hero_image": extra.get("hero_image") or "",
                "hero_alt": extra.get("hero_alt") or "",
                "video_id": extra.get("video_id") or "",
            }
            pages[relpath] = page_data

            for author in page_authors:
                authors.setdefault(
                    author,
                    {
                        "title": author,
                        "slug": slugify(author),
                        "url": f"/autores/{slugify(author)}/",
                        "image": "",
                        "gender": "m",
                        "is_owner": False,
                    },
                )
                authors[author].setdefault("articles", []).append(relpath)

            for tag in page_tags:
                tags.setdefault(
                    tag,
                    {
                        "title": tag,
                        "slug": slugify(tag),
                        "url": f"/etiquetas/{slugify(tag)}/",
                        "group_name": "",
                    },
                )
                tags[tag].setdefault("articles", []).append(relpath)

            for comment in comments.get(key, []):
                recent_comments.append(
                    {
                        "article_path": relpath,
                        "article_title": page_data["title"],
                        "article_url": page_data["url"],
                        "author": comment.get("author") or "Anónimo",
                        "anchor": comment.get("anchor") or "",
                        "date": comment.get("date") or "",
                        "date_display": comment.get("date_display") or "",
                        "excerpt": (comment.get("body") or "").replace("\n", " ")[:180],
                    }
                )

    for collection in (authors, tags):
        for item in collection.values():
            item["articles"] = sorted(
                set(item.get("articles") or []),
                key=lambda rel: pages.get(rel, {}).get("date", ""),
                reverse=True,
            )

    recent_comments.sort(key=lambda item: item["date"], reverse=True)
    index = {
        "sections": SECTION_TITLES,
        "pages": pages,
        "authors": authors,
        "tags": tags,
        "comments": comments,
        "recent_comments": recent_comments,
    }
    DATA.mkdir(exist_ok=True)
    (DATA / "site_index.json").write_text(
        json.dumps(jsonable(index), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Indexed {len(pages)} articles, {len(authors)} authors, {len(tags)} tags")
    return 0


if __name__ == "__main__":
    sys.exit(main())
