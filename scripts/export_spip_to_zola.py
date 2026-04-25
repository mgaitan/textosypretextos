#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "ftfy>=6.3.1",
#   "tomli-w>=1.2.0",
# ]
# ///
"""Exporta un backup SPIP a contenido Markdown listo para Zola.

Uso:
    uv run scripts/export_spip_to_zola.py

El script:
    - parsea el dump MySQL sin necesitar una base viva
    - convierte artículos SPIP a Markdown con shortcodes de Zola
    - reescribe enlaces internos a referencias `@/` de Zola
    - genera páginas auxiliares de autores y etiquetas
    - copia los assets del backup a `static/media`
"""

from __future__ import annotations

import argparse
import gzip
import html
import re
import shutil
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qs, unquote, urlparse

from ftfy import fix_text
import tomli_w


ARTICLE_FIELDS = [
    "id_article",
    "surtitre",
    "titre",
    "soustitre",
    "id_rubrique",
    "descriptif",
    "chapo",
    "texte",
    "ps",
    "date",
    "statut",
    "id_secteur",
    "maj",
    "export",
    "date_redac",
    "visites",
    "referers",
    "popularite",
    "accepter_forum",
    "date_modif",
    "lang",
    "langue_choisie",
    "id_trad",
    "extra",
    "id_version",
    "nom_site",
    "url_site",
    "virtuel",
]

RUBRIQUE_FIELDS = [
    "id_rubrique",
    "id_parent",
    "titre",
    "descriptif",
    "texte",
    "id_secteur",
    "maj",
    "statut",
    "date",
    "lang",
    "langue_choisie",
    "extra",
    "statut_tmp",
    "date_tmp",
    "profondeur",
]

AUTEUR_FIELDS = [
    "id_auteur",
    "nom",
    "bio",
    "email",
    "nom_site",
    "url_site",
    "login",
    "pass",
    "low_sec",
    "statut",
    "maj",
    "pgp",
    "htpass",
    "en_ligne",
    "imessage",
    "messagerie",
    "alea_actuel",
    "alea_futur",
    "prefs",
    "cookie_oubli",
    "source",
    "lang",
    "extra",
    "webmestre",
    "backup_cles",
]

MOT_FIELDS = [
    "id_mot",
    "titre",
    "descriptif",
    "texte",
    "id_groupe",
    "type",
    "extra",
    "maj",
]

DOCUMENT_FIELDS = [
    "id_document",
    "id_vignette",
    "titre",
    "date",
    "descriptif",
    "fichier",
    "taille",
    "largeur",
    "hauteur",
    "duree",
    "media",
    "mode",
    "distant",
    "statut",
    "credits",
    "alt",
    "date_publication",
    "brise",
    "maj",
    "extension",
]

FORUM_FIELDS = [
    "id_forum",
    "id_objet",
    "objet",
    "id_parent",
    "id_thread",
    "date_heure",
    "titre",
    "texte",
    "auteur",
    "email_auteur",
    "nom_site",
    "url_site",
    "statut",
    "ip",
    "maj",
    "id_auteur",
    "date_thread",
]

URL_FIELDS = [
    "url",
    "type",
    "id_objet",
    "date",
    "segments",
    "perma",
    "langue",
    "id_parent",
]

RUBRIQUE_SLUG_OVERRIDES = {
    "1": "blog",
    "2": "fotos",
    "3": "personal",
    "4": "de-otros",
    "5": "videos",
}

LOCAL_DOMAINS = {
    "textosypretextos.com.ar",
    "www.textosypretextos.com.ar",
    "textosypretextos.nqnwebs.com",
    "www.textosypretextos.nqnwebs.com",
}

IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp", "bmp"}
AUDIO_EXTENSIONS = {"mp3", "ogg", "wav", "m4a"}
FILE_EXTENSIONS = {"pdf", "doc", "docx", "txt", "zip"}
VIDEO_PROVIDERS = {"youtube", "vimeo", "dailymotion"}
AUTHOR_NAME_OVERRIDES = {
    "1": "Martín Gaitán",
}


@dataclass
class Document:
    id_document: str
    titre: str
    descriptif: str
    fichier: str
    media: str
    mode: str
    distant: str
    extension: str
    largeur: str
    hauteur: str
    alt: str
    credits: str

    @property
    def is_remote(self) -> bool:
        return self.distant == "oui" or self.fichier.startswith(("http://", "https://"))

    @property
    def normalized_extension(self) -> str:
        ext = (self.extension or "").lower().strip(".")
        if ext:
            return ext
        suffix = Path(urlparse(self.fichier).path).suffix.lower().strip(".")
        return suffix

    @property
    def is_image(self) -> bool:
        return self.mode == "image" or self.normalized_extension in IMAGE_EXTENSIONS

    @property
    def is_audio(self) -> bool:
        return self.normalized_extension in AUDIO_EXTENSIONS

    @property
    def label(self) -> str:
        return self.titre or self.alt or Path(urlparse(self.fichier).path).name or f"Documento {self.id_document}"


@dataclass
class Comment:
    id_forum: str
    article_id: str
    parent_id: str
    date_heure: str
    titre: str
    texte: str
    auteur: str
    email: str
    url_site: str
    statut: str
    depth: int = 0
    rendered: str = ""


@dataclass
class ArticleExport:
    article: dict[str, str]
    section_slug: str
    section_title: str
    page_path: str
    page_url: str
    slug: str
    authors: list[str]
    tags: list[str]
    body: str
    summary: str
    description: str
    deck: str = ""
    hero_image: str = ""
    hero_alt: str = ""
    comments: list[Comment] = field(default_factory=list)


class ExportContext:
    def __init__(self, *, root: Path, dump_path: Path, assets_dir: Path) -> None:
        self.root = root
        self.dump_path = dump_path
        self.assets_dir = assets_dir
        self.content_dir = root / "content"
        self.static_dir = root / "static"
        self.media_dir = self.static_dir / "media"
        self.prefix = detect_prefix(dump_path)

        self.articles = load_table_objects(dump_path, f"{self.prefix}articles", ARTICLE_FIELDS)
        self.rubriques = load_table_objects(dump_path, f"{self.prefix}rubriques", RUBRIQUE_FIELDS)
        self.auteurs = load_table_objects(dump_path, f"{self.prefix}auteurs", AUTEUR_FIELDS)
        self.mots = load_table_objects(dump_path, f"{self.prefix}mots", MOT_FIELDS)
        self.documents = {
            row["id_document"]: Document(
                id_document=row["id_document"],
                titre=row["titre"],
                descriptif=row["descriptif"],
                fichier=row["fichier"],
                media=row["media"],
                mode=row["mode"],
                distant=row["distant"],
                extension=row["extension"],
                largeur=row["largeur"],
                hauteur=row["hauteur"],
                alt=row["alt"],
                credits=row["credits"],
            )
            for row in load_table_objects(dump_path, f"{self.prefix}documents", DOCUMENT_FIELDS).values()
        }
        self.urls = load_table_objects(dump_path, f"{self.prefix}urls", URL_FIELDS)
        self.article_authors = load_link_table(dump_path, f"{self.prefix}auteurs_liens", "id_auteur", target_type="article")
        self.article_tags = load_link_table(dump_path, f"{self.prefix}mots_liens", "id_mot", target_type="article")
        self.article_documents = load_document_links(dump_path, f"{self.prefix}documents_liens", target_type="article")
        self.article_comments = load_forum_comments(dump_path, f"{self.prefix}forum")

        self.url_map = build_url_map(self.urls)
        self.author_display_names = {
            author_id: display_author_name(author_id, author.get("nom", ""))
            for author_id, author in self.auteurs.items()
        }
        self.author_name_to_id = {
            slugify(name, fallback=f"autor-{author_id}"): author_id
            for author_id, name in self.author_display_names.items()
        }
        self.section_slugs = self._build_section_slugs()
        self.article_paths: dict[str, str] = {}
        self.article_urls: dict[str, str] = {}
        self.author_paths: dict[str, str] = {}
        self.tag_paths: dict[str, str] = {}
        self.section_paths = {rid: f"{slug}/_index.md" for rid, slug in self.section_slugs.items()}

    def _build_section_slugs(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for rubrique_id, rubrique in self.rubriques.items():
            url_slug = self.url_map.get(("rubrique", rubrique_id))
            result[rubrique_id] = RUBRIQUE_SLUG_OVERRIDES.get(
                rubrique_id,
                slugify(url_slug or rubrique.get("titre", ""), fallback=f"seccion-{rubrique_id}"),
            )
        return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Exporta un backup SPIP a contenido Zola")
    parser.add_argument(
        "--dump",
        type=Path,
        default=Path("/home/tin/lab/nqnwebsc/backups/textosypretextos.nqnwebs.com/database.sql.gz"),
    )
    parser.add_argument(
        "--assets-dir",
        type=Path,
        default=Path("/home/tin/lab/nqnwebsc/backups/textosypretextos.nqnwebs.com/spip-assets/IMG"),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("/home/tin/lab/nqnwebsc/sites/textosypretextos"),
    )
    return parser.parse_args()


def open_dump(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="latin-1", errors="ignore")
    return path.open("r", encoding="latin-1", errors="ignore")


def parse_insert_values(line: str) -> list[list[str]]:
    data = line.split("VALUES ", 1)[1].rstrip("\n")
    if data.endswith(";"):
        data = data[:-1]

    rows: list[list[str]] = []
    row: list[str] = []
    field = ""
    in_string = False
    escaped = False
    depth = 0

    for ch in data:
        if in_string:
            field += ch
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == "'":
                in_string = False
            continue

        if ch == "'":
            in_string = True
            field += ch
        elif ch == "(":
            depth += 1
            if depth == 1:
                row = []
                field = ""
            else:
                field += ch
        elif ch == ")":
            if depth == 1:
                row.append(field)
                rows.append(row)
                field = ""
            else:
                field += ch
            depth -= 1
        elif ch == "," and depth == 1:
            row.append(field)
            field = ""
        elif depth >= 1:
            field += ch

    return rows


def decode_value(value: str) -> str:
    value = value.strip()
    if value in {"", "NULL"}:
        return ""
    if value.startswith("'") and value.endswith("'"):
        value = value[1:-1]

    value = (
        value.replace("\\r", "\r")
        .replace("\\n", "\n")
        .replace("\\t", "\t")
        .replace("\\'", "'")
        .replace("\\\\", "\\")
    )
    value = html.unescape(value)

    for _ in range(3):
        try:
            repaired = value.encode("latin-1").decode("utf-8")
        except UnicodeError:
            break
        if repaired == value:
            break
        value = repaired

    return fix_text(value).replace("\x00", "").strip()


def slugify(text: str, fallback: str) -> str:
    base = unicodedata.normalize("NFKD", text)
    base = base.encode("ascii", "ignore").decode("ascii").lower()
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    return base or fallback


def display_author_name(author_id: str, raw_name: str) -> str:
    if author_id in AUTHOR_NAME_OVERRIDES:
        return AUTHOR_NAME_OVERRIDES[author_id]
    name = (raw_name or "").strip()
    if name.islower():
        return name.title()
    return name


def detect_prefix(path: Path) -> str:
    prefixes: list[str] = []
    with open_dump(path) as handle:
        for line in handle:
            match = re.search(r"INSERT INTO `([^`]+?)articles` VALUES ", line)
            if match:
                prefixes.append(match.group(1))
    if not prefixes:
        raise RuntimeError("No se pudo detectar el prefijo de tablas SPIP")
    return "spip_" if "spip_" in prefixes else prefixes[0]


def load_table_objects(path: Path, table: str, fields: list[str]) -> dict[str, dict[str, str]]:
    needle = f"INSERT INTO `{table}` VALUES "
    result: dict[str, dict[str, str]] = {}
    with open_dump(path) as handle:
        for line in handle:
            if needle not in line:
                continue
            for row in parse_insert_values(line):
                values = {
                    fields[index]: decode_value(row[index])
                    for index in range(min(len(row), len(fields)))
                }
                object_id = values[fields[0]]
                result[object_id] = values
    return result


def load_link_table(path: Path, table: str, source_key: str, *, target_type: str) -> dict[str, list[str]]:
    if source_key == "id_auteur":
        fields = ["id_auteur", "id_objet", "objet", "vu"]
    else:
        fields = ["id_mot", "id_objet", "objet"]

    needle = f"INSERT INTO `{table}` VALUES "
    result: dict[str, list[str]] = defaultdict(list)
    with open_dump(path) as handle:
        for line in handle:
            if needle not in line:
                continue
            for row in parse_insert_values(line):
                values = {
                    fields[index]: decode_value(row[index])
                    for index in range(min(len(row), len(fields)))
                }
                if values.get("objet") != target_type:
                    continue
                result[values["id_objet"]].append(values[source_key])
    return result


def load_document_links(path: Path, table: str, *, target_type: str) -> dict[str, list[str]]:
    fields = ["id_document", "id_objet", "objet", "vu", "rang_lien"]
    needle = f"INSERT INTO `{table}` VALUES "
    result: dict[str, list[str]] = defaultdict(list)
    with open_dump(path) as handle:
        for line in handle:
            if needle not in line:
                continue
            for row in parse_insert_values(line):
                values = {
                    fields[index]: decode_value(row[index])
                    for index in range(min(len(row), len(fields)))
                }
                if values.get("objet") != target_type:
                    continue
                result[values["id_objet"]].append(values["id_document"])
    return result


def load_forum_comments(path: Path, table: str) -> dict[str, list[Comment]]:
    needle = f"INSERT INTO `{table}` VALUES "
    result: dict[str, list[Comment]] = defaultdict(list)
    by_thread: dict[str, dict[str, Comment]] = defaultdict(dict)

    with open_dump(path) as handle:
        for line in handle:
            if needle not in line:
                continue
            for row in parse_insert_values(line):
                values = {
                    FORUM_FIELDS[index]: decode_value(row[index])
                    for index in range(min(len(row), len(FORUM_FIELDS)))
                }
                if values.get("objet") != "article":
                    continue
                comment = Comment(
                    id_forum=values["id_forum"],
                    article_id=values["id_objet"],
                    parent_id=values["id_parent"],
                    date_heure=values["date_heure"],
                    titre=values["titre"],
                    texte=values["texte"],
                    auteur=values["auteur"],
                    email=values["email_auteur"],
                    url_site=values["url_site"],
                    statut=values["statut"],
                )
                result[comment.article_id].append(comment)
                by_thread[comment.article_id][comment.id_forum] = comment

    for article_id, comments in result.items():
        lookup = by_thread[article_id]
        for comment in comments:
            depth = 0
            parent = comment.parent_id
            seen: set[str] = set()
            while parent and parent != "0" and parent in lookup and parent not in seen:
                seen.add(parent)
                depth += 1
                parent = lookup[parent].parent_id
            comment.depth = depth
        comments.sort(key=lambda item: item.date_heure)

    return result


def build_url_map(rows: dict[str, dict[str, str]]) -> dict[tuple[str, str], str]:
    best_rows: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows.values():
        key = (row["type"], row["id_objet"])
        current = best_rows.get(key)
        if current is None:
            best_rows[key] = row
            continue
        current_perma = current.get("perma") == "1"
        row_perma = row.get("perma") == "1"
        if row_perma and not current_perma:
            best_rows[key] = row
            continue
        if current_perma == row_perma and row.get("date", "") > current.get("date", ""):
            best_rows[key] = row
    return {key: value["url"] for key, value in best_rows.items()}


def plain_text_summary(*parts: str, limit: int = 220) -> str:
    text = "\n".join(part for part in parts if part)
    text = strip_all_markup(text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0].rstrip(".,;:") + "…"


def strip_all_markup(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = normalize_spip_soft_breaks(text, hard_breaks=False)
    text = re.sub(r"<(?:img|doc|emb)\d+\|[^>]*>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<cita\|[^>]+>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<quote>|</quote>|<poesie>|</poesie>|<poetry>|</poetry>|<html>|</html>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\[[A-Za-z0-9_-]+<-\]", " ", text)
    text = re.sub(r"\[([^\]]+?)\-\>[^\]]+\]", r"\1", text)
    text = re.sub(r"\[\-\>([^\]]+)\]", lambda m: m.group(1).strip(), text)
    text = re.sub(r"\[\?([^\]]+)\]", lambda m: m.group(1).strip(), text)
    text = text.replace("{{{", "").replace("}}}", "").replace("{{", "").replace("}}", "").replace("{", "").replace("}", "")
    return fix_text(html.unescape(text))


def article_status_to_draft(status: str) -> bool:
    return status != "publie"


def parse_spip_datetime(*values: str) -> datetime:
    for value in values:
        candidate = (value or "").strip()
        if not candidate or candidate == "0000-00-00 00:00:00":
            continue
        try:
            return datetime.strptime(candidate, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return datetime(2000, 1, 1, 0, 0, 0)


def format_spip_date(value: str) -> str:
    return parse_spip_datetime(value).strftime("%d.%m.%Y")


def build_article_paths(context: ExportContext) -> None:
    seen: Counter[str] = Counter()
    for article_id, article in sorted(context.articles.items(), key=lambda item: int(item[0])):
        rubrique_id = article.get("id_rubrique", "")
        section_slug = context.section_slugs.get(rubrique_id, "archivo")
        base_slug = slugify(
            context.url_map.get(("article", article_id)) or article.get("titre", ""),
            fallback=f"articulo-{article_id}",
        )
        seen_key = f"{section_slug}/{base_slug}"
        seen[seen_key] += 1
        if seen[seen_key] > 1:
            base_slug = f"{base_slug}-{article_id}"
        page_path = f"{section_slug}/{base_slug}.md"
        context.article_paths[article_id] = page_path
        context.article_urls[article_id] = f"/{section_slug}/{base_slug}/"

    for author_id, author in context.auteurs.items():
        slug_base = slugify(
            context.url_map.get(("auteur", author_id)) or author.get("nom", ""),
            fallback=f"autor-{author_id}",
        )
        context.author_paths[author_id] = f"autores/{slug_base}.md"

    for mot_id, mot in context.mots.items():
        slug_base = slugify(
            context.url_map.get(("mot", mot_id)) or mot.get("titre", ""),
            fallback=f"etiqueta-{mot_id}",
        )
        context.tag_paths[mot_id] = f"etiquetas/{slug_base}.md"


def normalize_article_authors(context: ExportContext, article: dict[str, str]) -> list[str]:
    author_ids = context.article_authors.get(article["id_article"], [])
    names = [context.author_display_names[author_id] for author_id in author_ids if author_id in context.author_display_names]
    deduped = list(dict.fromkeys(name.strip() for name in names if name.strip()))
    if article.get("id_rubrique") == "4" and len(deduped) > 1:
        cleaned = [name for name in deduped if slugify(name, "autor") != "martin-gaitan"]
        if cleaned:
            deduped = cleaned
    if article.get("id_rubrique") == "4" and (not deduped or deduped == ["Martín Gaitán"]):
        subtitle = (article.get("soustitre") or "").strip()
        if subtitle:
            subtitle_slug = slugify(subtitle, fallback="autor")
            author_id = context.author_name_to_id.get(subtitle_slug)
            if author_id:
                return [context.author_display_names[author_id]]
            return [subtitle]
    return deduped or ["Martín Gaitán"]


def article_tags(context: ExportContext, article_id: str) -> list[str]:
    tag_ids = context.article_tags.get(article_id, [])
    return list(
        dict.fromkeys(
            context.mots[mot_id]["titre"]
            for mot_id in tag_ids
            if mot_id in context.mots and context.mots[mot_id].get("titre")
        )
    )


def resolve_internal_url(context: ExportContext, url: str) -> str | None:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if parsed.scheme in {"http", "https"} and host not in LOCAL_DOMAINS:
        return None
    if parsed.scheme in {"http", "https"} and host in LOCAL_DOMAINS:
        path_parts = [part for part in parsed.path.split("/") if part]
        fragment = f"#{parsed.fragment}" if parsed.fragment else ""
        if "spip.php" in parsed.path:
            params = parse_qs(parsed.query)
            for key in ("article", "id_article"):
                if key in params and params[key]:
                    article_id = params[key][0]
                    if article_id in context.article_paths:
                        return f"{context.article_urls[article_id]}{fragment}" if fragment else f"@/{context.article_paths[article_id]}"
            for key in ("rubrique", "id_rubrique"):
                if key in params and params[key]:
                    rubrique_id = params[key][0]
                    if rubrique_id in context.section_paths:
                        section_url = f"/{context.section_slugs[rubrique_id]}/"
                        return f"{section_url}{fragment}" if fragment else f"@/{context.section_paths[rubrique_id]}"
            for key in ("auteur", "id_auteur"):
                if key in params and params[key]:
                    auteur_id = params[key][0]
                    if auteur_id in context.author_paths:
                        author_url = f"/{context.author_paths[auteur_id][:-3]}/"
                        return f"{author_url}{fragment}" if fragment else f"@/{context.author_paths[auteur_id]}"
        if path_parts:
            slug_part = path_parts[-1]
            slug = slugify(unquote(slug_part), fallback=slug_part.lower())
            for article_id, page_path in context.article_paths.items():
                if slugify(Path(page_path).stem, "articulo") == slug:
                    return f"{context.article_urls[article_id]}{fragment}" if fragment else f"@/{page_path}"
            for auteur_id, page_path in context.author_paths.items():
                if slugify(Path(page_path).stem, "autor") == slug:
                    author_url = f"/{page_path[:-3]}/"
                    return f"{author_url}{fragment}" if fragment else f"@/{page_path}"
            for mot_id, page_path in context.tag_paths.items():
                if slugify(Path(page_path).stem, "etiqueta") == slug:
                    tag_url = f"/{page_path[:-3]}/"
                    return f"{tag_url}{fragment}" if fragment else f"@/{page_path}"
            for rubrique_id, section_path in context.section_paths.items():
                if slugify(Path(section_path).parent.name, "seccion") == slug:
                    section_url = f"/{context.section_slugs[rubrique_id]}/"
                    return f"{section_url}{fragment}" if fragment else f"@/{section_path}"
    return None


def resolve_spip_target(context: ExportContext, target: str) -> str:
    target = html.unescape(target.strip())
    target = target.replace("&amp;", "&")
    if not target:
        return "#"

    internal_from_url = resolve_internal_url(context, target)
    if internal_from_url:
        return internal_from_url

    lower = target.lower()
    if lower.startswith(("http://", "https://", "mailto:", "ftp://")):
        return target

    if target.startswith("#"):
        return target

    if match := re.fullmatch(r"art(?:icle)?(\d+)", lower):
        article_id = match.group(1)
        return f"@/{context.article_paths[article_id]}" if article_id in context.article_paths else "#"

    if match := re.fullmatch(r"rub(?:rique)?(\d+)", lower):
        rubrique_id = match.group(1)
        return f"@/{context.section_paths[rubrique_id]}" if rubrique_id in context.section_paths else "#"

    if match := re.fullmatch(r"aut(?:eur)?(\d+)", lower):
        author_id = match.group(1)
        return f"@/{context.author_paths[author_id]}" if author_id in context.author_paths else "#"

    if match := re.fullmatch(r"mot(\d+)", lower):
        mot_id = match.group(1)
        return f"@/{context.tag_paths[mot_id]}" if mot_id in context.tag_paths else "#"

    if match := re.fullmatch(r"doc(\d+)", lower):
        doc_id = match.group(1)
        document = context.documents.get(doc_id)
        if document:
            return media_url(document)
        return "#"

    if re.fullmatch(r"\d+", lower):
        if lower in context.article_paths:
            return f"@/{context.article_paths[lower]}"
        if lower in context.section_paths:
            return f"@/{context.section_paths[lower]}"
        if lower in context.author_paths:
            return f"@/{context.author_paths[lower]}"
        if lower in context.tag_paths:
            return f"@/{context.tag_paths[lower]}"

    return target


def media_url(document: Document) -> str:
    if document.is_remote:
        return document.fichier
    return "/media/" + document.fichier.lstrip("/")


def escape_shortcode(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _looks_like_filename(text: str) -> bool:
    text = (text or "").strip()
    if not text:
        return True
    if "/" in text or "\\" in text:
        return True
    if re.fullmatch(r"[A-Za-z0-9._-]+\.(jpe?g|png|gif|webp|bmp|tiff?|svg|mp3|mp4|mov|avi|pdf|doc|flv|wma|wav)", text, flags=re.IGNORECASE):
        return True
    return False


def _meaningful_caption(document: Document) -> str:
    descriptif = (document.descriptif or "").strip()
    if descriptif and not _looks_like_filename(descriptif):
        return descriptif
    titre = (document.titre or "").strip()
    if titre and not _looks_like_filename(titre):
        return titre
    return ""


def media_shortcode(document: Document, *, align: str = "center", caption: str = "") -> str:
    explicit_caption = (caption or "").strip()
    if explicit_caption and _looks_like_filename(explicit_caption):
        explicit_caption = ""
    label = explicit_caption or _meaningful_caption(document)

    provider, remote_id, remote_url = detect_remote_provider(document.fichier)
    if provider in VIDEO_PROVIDERS and remote_id:
        return '{{ video_embed(provider="%s", id="%s", title="%s") }}' % (
            escape_shortcode(provider),
            escape_shortcode(remote_id),
            escape_shortcode(document.titre or document.label),
        )

    if provider and remote_url:
        return '{{ external_embed(provider="%s", url="%s", title="%s") }}' % (
            escape_shortcode(provider),
            escape_shortcode(remote_url),
            escape_shortcode(document.titre or document.label),
        )

    if document.is_image:
        alt_candidate = (document.alt or "").strip()
        if not alt_candidate or _looks_like_filename(alt_candidate):
            alt_candidate = label
        return '{{ media_image(src="%s", alt="%s", caption="%s", align="%s") }}' % (
            escape_shortcode(media_url(document)),
            escape_shortcode(alt_candidate),
            escape_shortcode(label),
            escape_shortcode(align),
        )

    if document.is_audio:
        return '{{ media_audio(src="%s", title="%s") }}' % (
            escape_shortcode(media_url(document)),
            escape_shortcode(document.titre or document.label),
        )

    return '{{ media_file(url="%s", title="%s") }}' % (
        escape_shortcode(media_url(document)),
        escape_shortcode(document.titre or document.label),
    )


def detect_remote_provider(url: str) -> tuple[str, str, str]:
    text = html.unescape(url or "").strip()
    lower = text.lower()

    if match := re.search(r"(?:youtube\.com/(?:v|embed)/|youtu\.be/)([A-Za-z0-9_-]{6,})", text, flags=re.IGNORECASE):
        return "youtube", match.group(1), text
    if match := re.search(r"youtube\.com/watch\?v=([A-Za-z0-9_-]{6,})", text, flags=re.IGNORECASE):
        return "youtube", match.group(1), text
    if match := re.search(r"vimeo\.com/(?:moogaloop\.swf\?clip_id=|video/)?(\d+)", text, flags=re.IGNORECASE):
        return "vimeo", match.group(1), text
    if match := re.search(r"dailymotion\.com/(?:swf/|video/)([a-z0-9]+)", text, flags=re.IGNORECASE):
        return "dailymotion", match.group(1), text
    if match := re.search(r"video\.google\.[^?]+/googleplayer\.swf\?docid=([-\d]+)", text, flags=re.IGNORECASE):
        return "googlevideo", match.group(1), text
    if "slideshare.net" in lower:
        return "slideshare", "", text
    if "veoh.com" in lower:
        return "veoh", "", text
    if "sevenload.com" in lower:
        return "sevenload", "", text
    if "tu.tv" in lower:
        return "tu.tv", "", text
    return "", "", text


def normalize_spip_soft_breaks(text: str, *, hard_breaks: bool) -> str:
    replacement = "  \n" if hard_breaks else " "
    text = re.sub(r"(?m)^_ +", "", text)
    text = re.sub(
        r"\s+_\s+(?=(?:\*\*|[A-ZÁÉÍÓÚÜÑ(]|[A-Za-z][\w.-]*:|el\b|la\b|\d{4}|https?://|\[OT\]))",
        replacement,
        text,
    )
    return text


def normalize_spip_dialogue(text: str) -> str:
    normalized_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.lstrip()
        leading = line[: len(line) - len(stripped)]
        if stripped.startswith("-- "):
            stripped = "— " + stripped[3:]
            stripped = re.sub(r"\s+--\s+", " — ", stripped)
        stripped = re.sub(r"^((?:\*\*[^*\n]+\*\*|\([^)\n]+\)|\*[^*\n]+\*))\s+--\s+", r"\1 — ", stripped)
        normalized_lines.append(leading + stripped)
    return "\n".join(normalized_lines)


def label_for_spip_target(context: ExportContext, target: str) -> str:
    target = html.unescape(target.strip()).replace("&amp;", "&")
    lower = target.lower()

    if match := re.fullmatch(r"art(?:icle)?(\d+)", lower):
        article_id = match.group(1)
        if article_id in context.articles:
            return context.articles[article_id].get("titre", "").strip() or target
    if match := re.fullmatch(r"rub(?:rique)?(\d+)", lower):
        rubrique_id = match.group(1)
        if rubrique_id in context.rubriques:
            return context.rubriques[rubrique_id].get("titre", "").strip() or target
    if match := re.fullmatch(r"aut(?:eur)?(\d+)", lower):
        author_id = match.group(1)
        if author_id in context.author_display_names:
            return context.author_display_names[author_id]
    if match := re.fullmatch(r"mot(\d+)", lower):
        mot_id = match.group(1)
        if mot_id in context.mots:
            return context.mots[mot_id].get("titre", "").strip() or target
    if match := re.fullmatch(r"doc(\d+)", lower):
        doc_id = match.group(1)
        if doc_id in context.documents:
            return context.documents[doc_id].label
    if re.fullmatch(r"\d+", lower):
        if lower in context.articles:
            return context.articles[lower].get("titre", "").strip() or target
        if lower in context.rubriques:
            return context.rubriques[lower].get("titre", "").strip() or target
        if lower in context.author_display_names:
            return context.author_display_names[lower]
        if lower in context.mots:
            return context.mots[lower].get("titre", "").strip() or target
    return target


def convert_inline_markup(context: ExportContext, text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = html.unescape(text)
    text = normalize_spip_soft_breaks(text, hard_breaks=True)
    text = normalize_spip_dialogue(text)

    placeholders: list[str] = []
    shortcode_placeholders: list[str] = []

    def protect_shortcode(match: re.Match[str]) -> str:
        shortcode_placeholders.append(match.group(0))
        return f"@@SHORTCODE{len(shortcode_placeholders) - 1}@@"

    def replace_link(match: re.Match[str]) -> str:
        label = match.group(1).strip()
        target = resolve_spip_target(context, match.group(2))
        placeholders.append(f"[{label}]({target})")
        return f"@@LINK{len(placeholders) - 1}@@"

    def replace_bare_link(match: re.Match[str]) -> str:
        raw_target = match.group(1).strip()
        label = label_for_spip_target(context, raw_target)
        target = resolve_spip_target(context, raw_target)
        placeholders.append(f"[{label}]({target})")
        return f"@@LINK{len(placeholders) - 1}@@"

    text = re.sub(r"\{\{\s*[a-zA-Z_][\w-]*\([^{}]*\)\s*\}\}", protect_shortcode, text)
    text = re.sub(r"\[([A-Za-z0-9_-]+)<-\]", r'<span id="\1"></span>', text)
    text = re.sub(r"\[\-\>([^\]]+)\]", replace_bare_link, text)
    text = re.sub(r"\[([^\]]+?)\-\>([^\]]+)\]", replace_link, text)
    text = re.sub(r"\[([^\]]+?)\-\>\]", lambda m: m.group(1).strip(), text)
    text = re.sub(r"\[\?([^\]]+)\]", lambda m: m.group(1).strip(), text)
    text = re.sub(r"\{\{\{([^{}]+)\}\}\}", r"### \1", text)
    text = re.sub(r"\{\{([^{}]+)\}\}", r"**\1**", text)
    text = re.sub(r"\{([^{}]+)\}", r"*\1*", text)

    for index, replacement in enumerate(placeholders):
        text = text.replace(f"@@LINK{index}@@", replacement)
    for index, replacement in enumerate(shortcode_placeholders):
        text = text.replace(f"@@SHORTCODE{index}@@", replacement)

    text = text.replace("“", '"').replace("”", '"').replace("’", "'")
    return fix_text(text)


def blockquote_markdown(text: str) -> str:
    lines = [line.rstrip() for line in text.strip().splitlines()]
    return "\n".join(f"> {line}" if line else ">" for line in lines)


def poetry_html(text: str) -> str:
    lines = [line.rstrip() for line in text.strip().splitlines()]
    escaped = "<br>\n".join(html.escape(line) for line in lines)
    return f'<div class="poetry">{escaped}</div>'


def replace_embedded_media(context: ExportContext, text: str, article_doc_ids: Iterable[str]) -> tuple[str, set[str]]:
    allowed_docs = {doc_id: context.documents[doc_id] for doc_id in article_doc_ids if doc_id in context.documents}
    used_doc_ids: set[str] = set()
    placeholders: list[str] = []

    def add_placeholder(replacement: str) -> str:
        placeholders.append(f"\n\n{replacement}\n\n")
        return f"@@BLOCK{len(placeholders) - 1}@@"

    def replace_spip_doc(match: re.Match[str]) -> str:
        kind = match.group(1).lower()
        doc_id = match.group(2)
        align_spec = match.group(3) or "center"
        document = allowed_docs.get(doc_id) or context.documents.get(doc_id)
        if not document:
            return ""
        used_doc_ids.add(doc_id)
        return add_placeholder(media_shortcode(document, align=extract_align(align_spec)))

    text = re.sub(r"<(img|doc|emb)(\d+)\|([^>]*)>", replace_spip_doc, text, flags=re.IGNORECASE)

    def replace_embed_html(match: re.Match[str]) -> str:
        snippet = match.group(0)
        provider, remote_id, remote_url = detect_remote_provider(snippet)
        if provider in VIDEO_PROVIDERS and remote_id:
            return add_placeholder(
                '{{ video_embed(provider="%s", id="%s") }}'
                % (escape_shortcode(provider), escape_shortcode(remote_id))
            )
        if provider:
            return add_placeholder(
                '{{ external_embed(provider="%s", url="%s") }}'
                % (escape_shortcode(provider), escape_shortcode(remote_url))
            )
        return snippet

    text = re.sub(r"<object\b.*?</object>", replace_embed_html, text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<iframe\b.*?</iframe>", replace_embed_html, text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<embed\b[^>]*>", replace_embed_html, text, flags=re.IGNORECASE | re.DOTALL)

    for index, replacement in enumerate(placeholders):
        text = text.replace(f"@@BLOCK{index}@@", replacement)

    return text, used_doc_ids


def extract_align(spec: str) -> str:
    lower = spec.lower()
    if "left" in lower:
        return "left"
    if "right" in lower:
        return "right"
    return "center"


def convert_spip_body(context: ExportContext, raw_text: str, article_doc_ids: list[str]) -> tuple[str, set[str]]:
    text = raw_text or ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = html.unescape(text).replace('\\"', '"')
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)

    text, used_doc_ids = replace_embedded_media(context, text, article_doc_ids)

    text = re.sub(
        r"<quote>(.*?)</quote>",
        lambda m: "\n\n" + blockquote_markdown(convert_inline_markup(context, m.group(1))) + "\n\n",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    text = re.sub(
        r"<(?:poesie|poetry)>(.*?)</(?:poesie|poetry)>",
        lambda m: "\n\n" + poetry_html(convert_inline_markup(context, m.group(1))) + "\n\n",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    def replace_cita(match: re.Match[str]) -> str:
        params = parse_pipe_params(match.group(1))
        lines = [params[key] for key in sorted(params) if key.startswith("linea") and params[key].strip()]
        if not lines and params.get("autor"):
            lines = [params["autor"]]
        quote = "\n".join(f"> {convert_inline_markup(context, line)}" for line in lines if line)
        author = params.get("autor", "").strip()
        if author:
            quote += f"\n>\n> — {convert_inline_markup(context, author)}"
        return "\n\n" + quote + "\n\n"

    text = re.sub(r"<cita\|([^>]+)>", replace_cita, text, flags=re.IGNORECASE)
    text = re.sub(r"</?(?:html)>", "", text, flags=re.IGNORECASE)

    text = convert_inline_markup(context, text)
    text = text.replace("<ul>", "\n<ul>\n").replace("</ul>", "\n</ul>\n")
    text = text.replace("<ol>", "\n<ol>\n").replace("</ol>", "\n</ol>\n")
    text = text.replace("</li>", "</li>\n")
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip() + "\n", used_doc_ids


def parse_pipe_params(raw: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for part in raw.split("|"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def additional_media_blocks(context: ExportContext, article_id: str, used_doc_ids: set[str]) -> list[str]:
    blocks: list[str] = []
    for doc_id in context.article_documents.get(article_id, []):
        if doc_id in used_doc_ids:
            continue
        document = context.documents.get(doc_id)
        if not document:
            continue
        blocks.append(media_shortcode(document))
    return blocks


def hero_image_from_docs(context: ExportContext, article_id: str) -> tuple[str, str]:
    for doc_id in context.article_documents.get(article_id, []):
        document = context.documents.get(doc_id)
        if document and document.is_image and not document.is_remote:
            return media_url(document), document.alt or document.titre or document.label
    return "", ""


def render_comment_markdown(context: ExportContext, comment: Comment) -> str:
    content, _ = convert_spip_body(context, comment.texte, [])
    return content.strip()


def is_visible_comment(comment: Comment) -> bool:
    if comment.statut != "publie":
        return False
    lower = f"{comment.texte} {comment.url_site}".lower()
    if comment.date_heure >= "2020-01-01":
        if "http://" in lower or "https://" in lower or comment.url_site.strip():
            return False
        spam_markers = [
            "online contact",
            "best mom of the bride",
            "high-profile event",
            "hgh",
            "wordpress.com",
        ]
        if any(marker in lower for marker in spam_markers):
            return False
    return True


def write_markdown(path: Path, front_matter: dict, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "+++\n" + tomli_w.dumps(front_matter) + "+++\n\n" + body.strip() + "\n"
    path.write_text(content, encoding="utf-8")


def export_articles(context: ExportContext) -> list[ArticleExport]:
    exports: list[ArticleExport] = []
    for article_id, article in sorted(context.articles.items(), key=lambda item: int(item[0])):
        section_slug = context.section_slugs.get(article.get("id_rubrique", ""), "archivo")
        rubrique = context.rubriques.get(article.get("id_rubrique", ""), {})
        section_title = rubrique.get("titre", "Archivo")
        article_doc_ids = context.article_documents.get(article_id, [])
        authors = normalize_article_authors(context, article)
        tags = article_tags(context, article_id)

        main_body, used_doc_ids = convert_spip_body(context, article.get("texte", ""), article_doc_ids)
        suffix_blocks: list[str] = []

        deck_text = ""
        if article.get("chapo", "").strip():
            chapo_body, _ = convert_spip_body(context, article["chapo"], [])
            deck_text = chapo_body.strip()
        elif article.get("descriptif", "").strip():
            descr_body, _ = convert_spip_body(context, article["descriptif"], [])
            descr_body = descr_body.strip()
            # Only use descriptif if it isn't already the leading paragraph of the body.
            head = (main_body or "").strip()[:160]
            if descr_body[:60] not in head:
                deck_text = descr_body
        if article.get("ps", "").strip():
            ps_body, _ = convert_spip_body(context, article["ps"], [])
            suffix_blocks.append(
                "{% postscript() %}\n" + ps_body.strip() + "\n{% end %}"
            )

        extra_media = additional_media_blocks(context, article_id, used_doc_ids)
        if extra_media:
            suffix_blocks.append("### Galería\n\n" + "\n\n".join(extra_media))

        body_parts = [part for part in [main_body.strip()] + suffix_blocks if part.strip()]
        body = "\n\n".join(body_parts).strip() + "\n"

        summary = plain_text_summary(article.get("descriptif", ""), article.get("chapo", ""), article.get("texte", ""))
        description = plain_text_summary(article.get("descriptif", "") or article.get("texte", ""), limit=170)
        hero_image, hero_alt = hero_image_from_docs(context, article_id)

        comments = [comment for comment in context.article_comments.get(article_id, []) if is_visible_comment(comment)]
        for comment in comments:
            comment.rendered = render_comment_markdown(context, comment)

        if comments:
            body = body.rstrip() + "\n\n<span id=\"comments\"></span>\n"

        exports.append(
            ArticleExport(
                article=article,
                section_slug=section_slug,
                section_title=section_title,
                page_path=context.article_paths[article_id],
                page_url=context.article_urls[article_id],
                slug=Path(context.article_paths[article_id]).stem,
                authors=authors,
                tags=tags,
                body=body,
                summary=summary,
                description=description,
                hero_image=hero_image,
                hero_alt=hero_alt,
                deck=deck_text,
                comments=comments,
            )
        )

    return exports


def article_front_matter(context: ExportContext, article_export: ArticleExport) -> dict:
    article = article_export.article
    author_links = []
    for author_name in article_export.authors:
        author_id = None
        if article.get("id_rubrique") == "4" and article.get("soustitre", "").strip():
            subtitle_slug = slugify(article.get("soustitre", ""), fallback="autor")
            author_id = context.author_name_to_id.get(subtitle_slug)
        if author_id is None:
            author_id = context.author_name_to_id.get(slugify(author_name, fallback="autor"))
        author_links.append(
            {
                "name": author_name,
                "path": f"/{context.author_paths[author_id][:-3]}/" if author_id in context.author_paths else "",
            }
        )

    tag_links = []
    for tag_name in article_export.tags:
        tag_id = next(
            (
                mot_id
                for mot_id, mot in context.mots.items()
                if mot.get("titre") == tag_name
            ),
            None,
        )
        tag_links.append(
            {
                "name": tag_name,
                "path": f"/{context.tag_paths[tag_id][:-3]}/" if tag_id in context.tag_paths else "",
            }
        )

    extra = {
        "legacy_id": int(article["id_article"]),
        "section_slug": article_export.section_slug,
        "section_title": article_export.section_title,
        "summary": article_export.summary,
        "visits": int(article.get("visites") or 0),
        "popularite": float(article.get("popularite") or 0),
        "hero_image": article_export.hero_image,
        "hero_alt": article_export.hero_alt,
        "comment_count": len(article_export.comments),
        "legacy_url": article_export.page_url,
        "surtitle": article.get("surtitre", ""),
        "subtitle": article.get("soustitre", ""),
        "deck": article_export.deck,
        "author_links": author_links,
        "tag_links": tag_links,
        "comments": [
            {
                "id": int(comment.id_forum),
                "anchor": f"comment-{comment.id_forum}",
                "author": comment.auteur,
                "date": comment.date_heure,
                "date_display": format_spip_date(comment.date_heure),
                "depth": comment.depth,
                "url_site": comment.url_site,
                "title": comment.titre,
                "body": comment.rendered,
            }
            for comment in article_export.comments
        ],
    }

    date_value = parse_spip_datetime(
        article.get("date", ""),
        article.get("date_redac", ""),
        article.get("date_modif", ""),
        article.get("maj", ""),
    )

    return {
        "title": article.get("titre", f"Artículo {article['id_article']}"),
        "slug": article_export.slug,
        "date": date_value,
        "description": article_export.description,
        "draft": article_status_to_draft(article.get("statut", "")),
        "template": "article.html",
        "authors": article_export.authors,
        "categories": [article_export.section_title],
        "tags": article_export.tags,
        "extra": extra,
    }


def write_article_pages(context: ExportContext, exports: list[ArticleExport]) -> None:
    for article_export in exports:
        write_markdown(
            context.content_dir / article_export.page_path,
            article_front_matter(context, article_export),
            article_export.body,
        )


def build_section_indexes(context: ExportContext, exports: list[ArticleExport]) -> None:
    by_section: dict[str, list[ArticleExport]] = defaultdict(list)
    for item in exports:
        by_section[item.section_slug].append(item)

    root_extra = build_home_extra(exports)
    write_markdown(
        context.content_dir / "_index.md",
        {
            "title": "Textos y Pretextos",
            "template": "index.html",
            "sort_by": "date",
            "extra": root_extra,
        },
        "",
    )

    for rubrique_id, rubrique in sorted(context.rubriques.items(), key=lambda item: int(item[0])):
        section_slug = context.section_slugs[rubrique_id]
        summary = rubrique.get("descriptif") or rubrique.get("texte") or ""
        write_markdown(
            context.content_dir / section_slug / "_index.md",
            {
                "title": rubrique.get("titre", "Sección"),
                "sort_by": "date",
                "template": "section.html",
                "page_template": "article.html",
                "transparent": False,
                "extra": {
                    "section_slug": section_slug,
                    "summary": plain_text_summary(summary, limit=200),
                },
            },
            convert_inline_markup(context, rubrique.get("texte", "")).strip(),
        )


def build_home_extra(exports: list[ArticleExport]) -> dict:
    published = [item for item in exports if item.article.get("statut") == "publie"]
    by_section: dict[str, list[ArticleExport]] = defaultdict(list)
    for item in published:
        by_section[item.section_slug].append(item)

    popular = sorted(published, key=lambda item: int(item.article.get("visites") or 0), reverse=True)[:8]
    latest_comments = sorted(
        (
            {
                "article_path": item.page_path,
                "article_title": item.article.get("titre", ""),
                "author": comment.auteur,
                "anchor": f"comment-{comment.id_forum}",
                "date": comment.date_heure,
                "date_display": format_spip_date(comment.date_heure),
                "excerpt": plain_text_summary(comment.texte, limit=120),
            }
            for item in published
            for comment in item.comments
        ),
        key=lambda comment: comment["date"],
        reverse=True,
    )[:8]

    featured_photo = next((item.page_path for item in by_section.get("fotos", [])), "")
    latest_video = next((item.page_path for item in by_section.get("videos", [])), "")
    latest_other = next((item.page_path for item in by_section.get("de-otros", [])), "")

    return {
        "featured_photo_path": featured_photo,
        "latest_video_path": latest_video,
        "latest_other_path": latest_other,
        "popular_paths": [item.page_path for item in popular],
        "recent_comments": latest_comments,
    }


def build_author_pages(context: ExportContext, exports: list[ArticleExport]) -> None:
    published_by_author: dict[str, list[ArticleExport]] = defaultdict(list)
    for export in exports:
        if export.article.get("statut") != "publie":
            continue
        for author_name in export.authors:
            published_by_author[author_name].append(export)

    write_markdown(
        context.content_dir / "autores" / "_index.md",
        {
            "title": "Autores",
            "template": "authors_index.html",
            "sort_by": "none",
        },
        "",
    )

    media_dir = context.media_dir
    for author_id, author in sorted(context.auteurs.items(), key=lambda item: item[1].get("nom", "").lower()):
        path = context.author_paths[author_id]
        display_name = context.author_display_names[author_id]
        related = published_by_author.get(display_name, [])
        if not related and slugify(author.get("nom", ""), "autor") != "martin":
            continue
        body, _ = convert_spip_body(context, author.get("bio", ""), [])

        author_image = ""
        for ext in ("jpg", "jpeg", "png", "gif", "webp"):
            candidate = context.assets_dir / f"auton{author_id}.{ext}"
            if candidate.exists():
                target_name = f"auton{author_id}.{ext}"
                target = media_dir / target_name
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.exists() or target.stat().st_size != candidate.stat().st_size:
                    shutil.copy2(candidate, target)
                author_image = f"/media/{target_name}"
                break

        slug_for_excl = slugify(author.get("nom", ""), "autor")
        write_markdown(
            context.content_dir / path,
            {
                "title": display_name,
                "template": "author.html",
                "extra": {
                    "legacy_id": int(author_id),
                    "legacy_slug": context.url_map.get(("auteur", author_id), ""),
                    "article_paths": [item.page_path for item in related],
                    "image": author_image,
                    "is_owner": slug_for_excl == "martin",
                },
            },
            body.strip(),
        )


def build_tag_pages(context: ExportContext, exports: list[ArticleExport]) -> None:
    published_by_tag: dict[str, list[ArticleExport]] = defaultdict(list)
    by_title: dict[str, tuple[str, dict[str, str]]] = {}
    for mot_id, mot in context.mots.items():
        by_title[mot.get("titre", "")] = (mot_id, mot)

    for export in exports:
        if export.article.get("statut") != "publie":
            continue
        for tag_name in export.tags:
            published_by_tag[tag_name].append(export)

    write_markdown(
        context.content_dir / "etiquetas" / "_index.md",
        {
            "title": "Etiquetas",
            "template": "tags_index.html",
            "sort_by": "none",
        },
        "",
    )

    for tag_name, related in sorted(published_by_tag.items(), key=lambda item: item[0].lower()):
        mot_id, mot = by_title[tag_name]
        description = mot.get("descriptif", "") or mot.get("texte", "")
        body = convert_inline_markup(context, description).strip()
        write_markdown(
            context.content_dir / context.tag_paths[mot_id],
            {
                "title": tag_name,
                "template": "tag.html",
                "extra": {
                    "legacy_id": int(mot_id),
                    "group_id": int(mot.get("id_groupe") or 0),
                    "group_name": mot.get("type", ""),
                    "article_paths": [item.page_path for item in related],
                },
            },
            body,
        )


def copy_media(context: ExportContext) -> None:
    if context.media_dir.exists():
        shutil.rmtree(context.media_dir)
    context.media_dir.mkdir(parents=True, exist_ok=True)

    for source in context.assets_dir.rglob("*"):
        if not source.is_file():
            continue
        relative = source.relative_to(context.assets_dir)
        if any(part == "config" for part in relative.parts):
            continue
        if source.name in {".ok", "remove.txt"}:
            continue
        target = context.media_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def ensure_clean_content(root: Path) -> None:
    for name in ("content", "static/media"):
        target = root / name
        if target.exists():
            shutil.rmtree(target)


def main() -> None:
    args = parse_args()
    root = args.output_root
    ensure_clean_content(root)

    context = ExportContext(root=root, dump_path=args.dump, assets_dir=args.assets_dir)
    build_article_paths(context)
    copy_media(context)
    exports = export_articles(context)
    write_article_pages(context, exports)
    build_section_indexes(context, exports)
    build_author_pages(context, exports)
    build_tag_pages(context, exports)

    published = sum(1 for item in exports if item.article.get("statut") == "publie")
    drafts = len(exports) - published
    print(f"Exportados {len(exports)} artículos ({published} publicados, {drafts} borradores/propuestas).")
    print(f"Media copiada a {context.media_dir}")


if __name__ == "__main__":
    main()
