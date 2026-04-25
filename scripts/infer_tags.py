#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["tomli-w>=1.2.0"]
# ///
"""Infiera etiquetas transversales (Humor, Familia, etc.) sobre los artículos
y las agrega al frontmatter (campo `tags`, `extra.tag_links`).

Las etiquetas se eligen por matching de keywords sobre el cuerpo + título.
Cada artículo recibe entre 0 y 2 inferidas. La temática SPIP original
(primera entrada existente en tag_links) sigue siendo la subcategoría
mostrada como kicker, pero no se duplica.
"""
from __future__ import annotations

import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

import tomli_w

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"

# (etiqueta, slug, lista de patrones regex en minúsculas, palabras-stop opcional)
INFERRED_TAGS = [
    ("Humor", "humor", [
        r"\bchiste\b", r"\bch[oó]chera\b", r"\brisa\b", r"\bre[ií]rme?\b", r"\bcarcajad",
        r"\babsurd", r"\bironi", r"\bsarc[aá]s", r"\bdivert[ií]d", r"\bgracios",
        r"\bridicul",
    ]),
    ("Familia", "familia", [
        r"\bmi (?:vieja|viejo|mam[aá]|pap[aá]|abuel[oa]|t[ií]a|t[ií]o|hermana|hermano|primo|prima)\b",
        r"\bmis (?:viejos|abuelos|hermanos|t[ií]os|primos|hijos)\b",
        r"\bmi familia\b", r"\bmi casa\b",
    ]),
    ("Amor", "amor", [
        r"\benamorad", r"\benamorarse\b", r"\bbeso\b", r"\bbesarse\b",
        r"\bamor\b", r"\bnovi[ao]\b", r"\bamantes?\b", r"\bromance\b",
    ]),
    ("Amistad", "amistad", [
        r"\bamigo\b", r"\bamiga\b", r"\bamigos\b", r"\bamigas\b",
        r"\bamistad\b", r"\bcompa[ñn]ero[s]?\b",
    ]),
    ("Música", "musica", [
        r"\bm[uú]sica\b", r"\bcanci[oó]n\b", r"\bdisco\b", r"\bguitarra\b",
        r"\bcantante\b", r"\bbanda\b", r"\bconcierto\b", r"\brecital\b",
        r"\bspinetta\b", r"\bgarc[ií]a\b", r"\bp[aá]ez\b", r"\bcerati\b",
        r"\bcantar\b", r"\bcantando\b",
    ]),
    ("Cine", "cine", [
        r"\bpel[ií]cul", r"\bfilm\b", r"\bdirector\b", r"\bcortometraje\b",
        r"\bdocumental\b", r"\bcinematogr[aá]fic", r"\bguion\b", r"\bgui[oó]n\b",
        r"\bactor\b", r"\bactriz\b",
    ]),
    ("Política", "politica", [
        r"\bgobierno\b", r"\bpresidente\b", r"\bkirchner\b", r"\bperonismo\b",
        r"\bperonista\b", r"\bmacri\b", r"\bmenem\b", r"\belecciones\b",
        r"\bpol[ií]tic", r"\bcapitalismo\b", r"\bsocialismo\b", r"\bdictadura\b",
        r"\bdesaparecidos\b",
    ]),
    ("Tecnología", "tecnologia", [
        r"\bsoftware\b", r"\blinux\b", r"\bpython\b", r"\bcodigo\b",
        r"\bc[oó]digo\b", r"\bprogramaci[oó]n\b", r"\bordenador\b",
        r"\bcomputadora\b", r"\binternet\b", r"\bweb\b", r"\bblog\b",
        r"\bgithub\b", r"\bopenoffice\b", r"\bgnu\b",
    ]),
    ("Córdoba", "cordoba", [
        r"\bc[oó]rdoba\b", r"\bcordob[eé]s", r"\bcordobesa\b",
        r"\bcerro de las rosas\b", r"\bnueva c[oó]rdoba\b", r"\bcanal de los molinos\b",
    ]),
    ("Memoria", "memoria", [
        r"\brecuerdo\b", r"\brecuerda?\b", r"\binfanci", r"\bni[ñn]ez\b",
        r"\bmemor[ií]a\b", r"\bnostalgi", r"\bayer\b",
    ]),
]


def slugify_tag(text: str) -> str:
    norm = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    norm = re.sub(r"[^a-zA-Z0-9]+", "-", norm).strip("-").lower()
    return norm


def split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("+++"):
        return "", text
    end = text.find("\n+++", 3)
    if end == -1:
        return "", text
    fm = text[3:end].strip()
    rest = text[end + 4 :].lstrip("\n")
    return fm, rest


def parse_frontmatter(fm: str) -> dict:
    import tomllib
    return tomllib.loads(fm)


def render_frontmatter(fm: dict) -> str:
    return tomli_w.dumps(fm)


def score_tags(text: str) -> list[tuple[str, str, int]]:
    text_lower = text.lower()
    scores: list[tuple[str, str, int]] = []
    for name, slug, patterns in INFERRED_TAGS:
        count = 0
        for pat in patterns:
            count += len(re.findall(pat, text_lower))
        if count > 0:
            scores.append((name, slug, count))
    scores.sort(key=lambda x: -x[2])
    return scores


def process_articles() -> tuple[Counter[str], dict[str, list[str]]]:
    counter: Counter[str] = Counter()
    by_tag: dict[str, list[str]] = {}
    files = []
    for section in ("blog", "de-otros", "personal", "fotos", "videos"):
        section_dir = CONTENT / section
        if not section_dir.is_dir():
            continue
        for p in section_dir.iterdir():
            if p.is_file() and p.suffix == ".md" and p.name != "_index.md":
                files.append(p)

    for path in files:
        text = path.read_text(encoding="utf-8")
        fm_text, body = split_frontmatter(text)
        if not fm_text:
            continue
        fm = parse_frontmatter(fm_text)
        if fm.get("draft"):
            continue

        existing_tags = list(fm.get("tags") or [])
        existing_tag_links = list((fm.get("extra") or {}).get("tag_links") or [])

        # Score using title + body (limit body to first ~6000 chars to keep fast)
        title = fm.get("title", "")
        scored = score_tags(title + "\n\n" + body[:8000])
        # Filter out tags that are already present (case-insensitive)
        existing_lower = {t.lower() for t in existing_tags}
        new_inferred = []
        for name, slug, _score in scored:
            if name.lower() in existing_lower:
                continue
            new_inferred.append((name, slug))
            if len(new_inferred) >= 2:
                break

        if not new_inferred:
            continue

        # Append to tags and tag_links
        section_slug = path.parent.name
        rel_path = f"{section_slug}/{path.name}"
        for name, slug in new_inferred:
            existing_tags.append(name)
            existing_tag_links.append({"name": name, "path": f"/etiquetas/{slug}/"})
            counter[name] += 1
            by_tag.setdefault(name, []).append(rel_path)

        fm["tags"] = existing_tags
        if "extra" not in fm:
            fm["extra"] = {}
        fm["extra"]["tag_links"] = existing_tag_links

        path.write_text("+++\n" + render_frontmatter(fm) + "+++\n\n" + body.strip() + "\n", encoding="utf-8")

    return counter, by_tag


def write_tag_pages(counts: Counter[str], by_tag: dict[str, list[str]]) -> None:
    tags_dir = CONTENT / "etiquetas"
    tags_dir.mkdir(exist_ok=True)
    for name, _slug, _patterns in INFERRED_TAGS:
        if name not in counts:
            continue
        slug = slugify_tag(name)
        path = tags_dir / f"{slug}.md"
        if path.exists():
            # Don't overwrite if it exists; merge would be nicer but skip for now
            continue
        # Sort article paths by date (descending) using file mtime as fallback
        article_paths = sorted(set(by_tag.get(name, [])))
        fm = {
            "title": name,
            "template": "tag.html",
            "extra": {
                "legacy_id": 0,
                "legacy_slug": slug,
                "group_id": 99,
                "group_name": "transversales",
                "article_paths": article_paths,
                "inferred": True,
            },
        }
        path.write_text("+++\n" + render_frontmatter(fm) + "+++\n", encoding="utf-8")


def main() -> int:
    counts, by_tag = process_articles()
    write_tag_pages(counts, by_tag)
    print("Tags inferidos asignados:")
    for name, count in counts.most_common():
        print(f"  {name}: {count} artículos")
    print(f"\nTotal único de tags inferidos: {len(counts)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
