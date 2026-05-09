#!/usr/bin/env -S uv run python
# /// script
# requires-python = ">=3.11"
# dependencies = ["tomli", "ruamel.yaml"]
# ///
"""Migra artículos Markdown de Zola (TOML frontmatter) a Nikola (YAML frontmatter).

Cambios que aplica
==================
1. Convierte el frontmatter de TOML (``+++…+++``) a YAML (``---…---``).
2. Elimina campos legacy / redundantes::

       legacy_id, visits, popularite, legacy_url, surtitle,
       description, categories, template, comment_count,
       author_links, tag_links, section_slug, section_title, draft=false

   ``author_links`` y ``tag_links`` los genera Nikola automáticamente a partir de
   ``author`` y ``tags``.

3. Promueve los campos de ``[extra]`` al nivel raíz.

4. Renombra ``authors`` (lista) → ``author`` (Nikola espera un solo valor o lista simple).

5. Mueve ``deck`` al comienzo del cuerpo, cuando existe, y agrega
   ``<!-- TEASER_END -->`` después de ese teaser. Si no hay ``deck``, inserta
   el marcador después del primer párrafo no vacío.

6. Actualiza la sintaxis de shortcodes:
   - ``{% name() %}…{% end %}``  →  ``{{% name %}}…{{% /name %}}``
   - ``{{ name(param=val) }}``   →  ``{{% name param=val %}}``

Uso
===
    # Dry-run (muestra qué cambiaría sin tocar archivos):
    uv run scripts/migrate_to_nikola.py

    # Migrar todos los artículos:
    uv run scripts/migrate_to_nikola.py --apply

    # Migrar archivos específicos:
    uv run scripts/migrate_to_nikola.py --apply content/blog/gordo.md
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # fallback pip package
    except ImportError:
        print(
            "ERROR: se requiere tomllib (Python 3.11+) o tomli. "
            "Instalar con: pip install tomli",
            file=sys.stderr,
        )
        sys.exit(1)

try:
    from ruamel.yaml import YAML
    from ruamel.yaml.scalarstring import LiteralScalarString
except ImportError:
    print(
        "ERROR: se requiere ruamel.yaml. Instalar con: pip install ruamel.yaml",
        file=sys.stderr,
    )
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent

# ──────────────────────────────────────────
# Campos que se eliminan del frontmatter migrado
# ──────────────────────────────────────────
REMOVE_FIELDS = frozenset(
    {
        "legacy_id",
        "visits",
        "popularite",
        "legacy_url",
        "surtitle",
        "description",  # reemplazado por TEASER_END en el cuerpo
        "categories",  # reemplazado por la sección/path
        "template",  # Nikola lo determina por POSTS config
        "author_links",  # auto en Nikola
        "tag_links",  # auto en Nikola
        "summary",  # reemplazado por TEASER_END
        "comment_count",  # se infiere de comments
        "section_slug",  # se infiere del path content/<sección>/
        "section_title",  # se infiere de section_slug
    }
)

# Campos del bloque [extra] que se promueven al nivel raíz (o se eliminan si están vacíos)
KEEP_EXTRA = frozenset(
    {
        "hero_image",
        "hero_alt",
        "subtitle",
        "video_id",
        "hide_hero_in_listing",
    }
)

RE_TOML_FM = re.compile(r"^\+\+\+\n(.*?)\n\+\+\+\n(.*)$", re.DOTALL)
RE_BLANK_PAR = re.compile(r"\n\n+")

# Shortcodes: bloque {% name(args) %}…{% end %}
RE_SC_BLOCK = re.compile(
    r"\{%[-\s]*(\w+)\([^)]*\)\s*[-\s]*%\}(.*?)\{%[-\s]*end[-\s]*%\}",
    re.DOTALL,
)
# Shortcodes: inline {{ name(key=val, ...) }}
RE_SC_INLINE = re.compile(r"\{\{[-\s]*(\w+)\(([^)]*)\)[-\s]*\}\}")

CANONICAL_TAGS = {
    "canción": "Canción",
}


def canonical_tag(tag: object) -> str:
    """Normaliza tags de forma case-insensitive conservando nombres editoriales."""
    value = str(tag)
    return CANONICAL_TAGS.get(value.casefold(), value)


def _parse_args(args_str: str) -> str:
    """Convierte 'key="val", key2=val2' → 'key="val" key2=val2' (Nikola style)."""
    return re.sub(r",\s*", " ", args_str.strip()).strip()


def convert_shortcodes(body: str) -> str:
    """Actualiza la sintaxis de shortcodes de Zola a Nikola."""

    def replace_block(m: re.Match) -> str:
        name = m.group(1)
        content = m.group(2)
        return f"{{{{% {name} %}}}}{content}{{{{% /{name} %}}}}"

    def replace_inline(m: re.Match) -> str:
        name = m.group(1)
        raw_args = m.group(2)
        args = _parse_args(raw_args) if raw_args.strip() else ""
        return f"{{{{% {name} {args} %}}}}" if args else f"{{{{% {name} %}}}}"

    body = RE_SC_BLOCK.sub(replace_block, body)
    body = RE_SC_INLINE.sub(replace_inline, body)
    return body


def insert_teaser_end(body: str, teaser: str = "") -> str:
    """Inserta <!-- TEASER_END --> después del primer párrafo no vacío."""
    body = body.strip()
    teaser = convert_shortcodes(teaser.strip())
    if teaser:
        return f"{teaser}\n\n<!-- TEASER_END -->\n\n{body}\n"

    paragraphs = RE_BLANK_PAR.split(body)
    # Buscar el primer párrafo con texto real (no shortcodes solos, no imágenes)
    for i, para in enumerate(paragraphs):
        stripped = para.strip()
        if stripped and not stripped.startswith("{%") and not stripped.startswith("{{"):
            paragraphs.insert(i + 1, "<!-- TEASER_END -->")
            break
    return "\n\n".join(paragraphs) + "\n"


def migrate_frontmatter(toml_str: str) -> tuple[dict, str]:
    """Convierte el dict TOML al esquema simplificado para Nikola."""
    data = tomllib.loads(toml_str)
    extra = data.pop("extra", {})
    teaser = extra.get("deck", "")

    # Eliminar campos de nivel raíz no deseados
    for field in REMOVE_FIELDS:
        data.pop(field, None)

    # authors → author (Nikola usa 'author' singular como string o lista)
    if "authors" in data:
        authors = data.pop("authors")
        if isinstance(authors, list):
            data["author"] = ", ".join(str(author) for author in authors)
        else:
            data["author"] = authors

    if isinstance(data.get("tags"), list):
        data["tags"] = ", ".join(canonical_tag(tag) for tag in data["tags"])

    if data.get("draft") is False:
        data.pop("draft", None)

    # Promover campos relevantes de [extra]
    for field in KEEP_EXTRA:
        if field in extra:
            val = extra[field]
            # No incluir campos vacíos (cadenas vacías, listas vacías)
            if val or val == 0:
                data[field] = val

    # Mantener comentarios estáticos heredados
    if "comments" in extra and extra["comments"]:
        data["comments"] = extra["comments"]

    # Limpiar strings vacíos
    cleaned = {k: v for k, v in data.items() if not (isinstance(v, str) and v == "")}
    return cleaned, teaser


def dict_to_yaml(data: dict) -> str:
    """Serializa el diccionario a YAML limpio con ruamel.yaml."""
    import io

    yaml = YAML()
    yaml.default_flow_style = False
    yaml.allow_unicode = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.width = 120

    stream = io.StringIO()
    yaml.dump(data, stream)
    return stream.getvalue()


def migrate_file(path: Path, apply: bool = False) -> tuple[bool, str]:
    """Migra un archivo .md.  Devuelve (cambiado, nuevo_contenido)."""
    text = path.read_text(encoding="utf-8")
    m = RE_TOML_FM.match(text)
    if not m:
        return False, text  # no tiene frontmatter TOML; no se toca

    toml_str, body = m.group(1), m.group(2)
    try:
        new_meta, teaser = migrate_frontmatter(toml_str)
    except Exception as exc:
        print(f"  ERROR parseando {path}: {exc}", file=sys.stderr)
        return False, text

    new_body = convert_shortcodes(body)
    new_body = insert_teaser_end(new_body, teaser=teaser)
    yaml_str = dict_to_yaml(new_meta)
    new_text = f"---\n{yaml_str}---\n{new_body}"

    changed = new_text != text
    if apply and changed:
        path.write_text(new_text, encoding="utf-8")

    return changed, new_text


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "paths", nargs="*", help="Archivos .md a migrar (default: todo content/)"
    )
    parser.add_argument(
        "--apply", action="store_true", help="Aplicar los cambios (sin esto es dry-run)"
    )
    opts = parser.parse_args()

    if opts.paths:
        files = [Path(p) for p in opts.paths if p.endswith(".md")]
    else:
        editorial_dirs = ["blog", "fotos", "videos", "de-otros", "personal"]
        files = []
        for section in editorial_dirs:
            files.extend(
                f
                for f in (ROOT / "content" / section).glob("*.md")
                if not f.name.startswith("_")
            )
        files.extend(
            f
            for f in [ROOT / "content" / "buscar.md", ROOT / "content" / "random.md"]
            if f.exists()
        )
        files = sorted(files)

    changed_count = 0
    for f in files:
        changed, _ = migrate_file(f, apply=opts.apply)
        if changed:
            changed_count += 1
            action = "migrado" if opts.apply else "pendiente"
            rel = f.relative_to(ROOT) if f.is_absolute() else f
            print(f"  {action}: {rel}")

    mode = (
        "aplicados" if opts.apply else "pendientes (dry-run; usar --apply para aplicar)"
    )
    print(f"\n{changed_count} archivo(s) {mode}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
