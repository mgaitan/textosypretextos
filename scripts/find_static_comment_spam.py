#!/usr/bin/env -S uv run python
# /// script
# requires-python = ">=3.11"
# ///
"""Detect obvious spam candidates in static frontmatter comments."""

from __future__ import annotations

import argparse
import pathlib
import re
import tomllib

ROOT = pathlib.Path(__file__).resolve().parent.parent
RE_FRONTMATTER = re.compile(r"^\+\+\+\n(.*?)\n\+\+\+\n?", re.DOTALL)
RE_RANDOM_AUTHOR = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])[A-Za-z]{12,}$")
RE_LINK = re.compile(r"https?://|www\.", re.IGNORECASE)

SPAM_MARKERS = [
    "display:none",
    "position:relative;left:-",
    "hair loss treatment",
    "mutuelle",
    "guadeloupe",
    "visites guidées",
    "université de la cartouche",
    "facebook.com/profile.php?id=",
]

FOREIGN_MARKERS = [
    "i feel like you could probably teach a class",
    "quel beau texte",
    "simplement magnifique",
    "votre article est excellant",
    "locations de véhicules",
]


def parse_frontmatter(path: pathlib.Path) -> dict:
    text = path.read_text(encoding="utf-8")
    match = RE_FRONTMATTER.match(text)
    if not match:
        return {}
    return tomllib.loads(match.group(1))


def detect_reasons(comment: dict) -> list[str]:
    reasons: list[str] = []
    author = str(comment.get("author", "")).strip()
    body = str(comment.get("body", "")).strip().lower()
    url_site = str(comment.get("url_site", "")).strip().lower()

    if author and RE_RANDOM_AUTHOR.match(author):
        reasons.append("author-random")
    if url_site and "facebook.com/profile.php?id=" in url_site and reasons:
        reasons.append("fb-profile")

    if any(marker in body for marker in SPAM_MARKERS):
        reasons.append("seo-marker")
    if any(marker in body for marker in FOREIGN_MARKERS):
        reasons.append("foreign-template")

    body_link_count = len(RE_LINK.findall(body))
    if body_link_count >= 2 and ("seo-marker" in reasons or "foreign-template" in reasons):
        reasons.append("many-links")
    elif body_link_count >= 1 and ("seo-marker" in reasons or "foreign-template" in reasons):
        reasons.append("promo-link")

    if author.lower() in {"mutuelle-conseil"}:
        reasons.append("spam-author")

    return reasons


def resolve_paths(args: list[str]) -> list[pathlib.Path]:
    if args:
        return [(ROOT / arg).resolve() if not pathlib.Path(arg).is_absolute() else pathlib.Path(arg) for arg in args]
    return sorted((ROOT / "content").rglob("*.md"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="Archivos a revisar (default: content/**/*.md)")
    opts = parser.parse_args()

    total = 0
    for path in resolve_paths(opts.paths):
        if not path.exists() or path.suffix != ".md":
            continue
        data = parse_frontmatter(path)
        comments = (((data.get("extra") or {}).get("comments")) or [])
        for comment in comments:
            reasons = detect_reasons(comment)
            if not reasons:
                continue
            total += 1
            print(
                f"{path.relative_to(ROOT)} "
                f"comment_id={comment.get('id')} "
                f"author={comment.get('author', '')!r} "
                f"reasons={','.join(reasons)}"
            )
    print(f"\nTotal candidatos: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
