# -*- coding: utf-8 -*-
"""Configuración de Nikola para Textos y Pretextos.

Migrado desde Zola. Ver NIKOLA.md para el detalle del proceso.
"""

# ──────────────────────────────────────────
# Identidad del sitio
# ──────────────────────────────────────────
BLOG_TITLE = "Textos y Pretextos"
BLOG_AUTHOR = "Martín Gaitán"
BLOG_EMAIL = ""
BLOG_DESCRIPTION = "Textos, imágenes y lecturas de Martín Gaitán."
SITE_URL = "https://textosypretextos.pages.dev/"
DEFAULT_LANG = "es"
TRANSLATIONS = {DEFAULT_LANG: ""}
GENERATE_RSS = False
GENERATE_ATOM = True
FEED_LENGTH = 20
ATOM_FILENAME_BASE = "atom"
OUTPUT_FOLDER = "public"

# ──────────────────────────────────────────
# Secciones (equivalente a los sections de Zola)
# ──────────────────────────────────────────
# Patrón: (fuente, carpeta de salida, template). Se enumeran archivos
# directos para no arrastrar `_index.md` ni páginas heredadas como
# `content/blog/subsecciones/*.md` al timeline de posts.
from pathlib import Path
from datetime import datetime
from nikola.utils import slugify


def _section_posts(section):
    return tuple(
        (str(path), section, "post.tmpl")
        for path in sorted(Path("content", section).glob("*.md"))
        if not path.name.startswith("_")
    )


POSTS = (
    *_section_posts("blog"),
    *_section_posts("fotos"),
    *_section_posts("videos"),
    *_section_posts("de-otros"),
    *_section_posts("personal"),
)

# Páginas estáticas (no son posts en el feed)
PAGES = (
    ("content/buscar.md", "", "search.tmpl"),
    ("content/random.md", "", "random.tmpl"),
)

# ──────────────────────────────────────────
# Compiladores y extensiones Markdown
# ──────────────────────────────────────────
COMPILERS = {
    "markdown": [".md", ".txt"],
}
MARKDOWN_EXTENSIONS = [
    "markdown.extensions.extra",
    "markdown.extensions.smarty",  # comillas tipográficas, em-dash, etc.
    "markdown.extensions.toc",
]
MARKDOWN_EXTENSION_CONFIGS = {
    "markdown.extensions.smarty": {
        "smart_dashes": True,
        "smart_quotes": False,  # las comillas las maneja el autor
    }
}

# Separador de teaser (reemplaza al campo `summary` + `deck` de Zola)
# En el cuerpo del artículo, insertar <!-- TEASER_END --> después del primer párrafo.
TEASER_SEPARATOR = "<!-- TEASER_END -->"

# ──────────────────────────────────────────
# Taxonomías (automáticas – reemplaza tag_links / author_links manuales)
# ──────────────────────────────────────────
TAG_PATH = "etiquetas"
TAG_PAGES_ARE_INDEXES = True
TAGS_INDEX_PATH = "etiquetas/index.html"

AUTHOR_PATH = "autores"
AUTHOR_PAGES_ARE_INDEXES = True

# Las categorías no se usan activamente; las secciones las reemplazan
CATEGORY_PATH = "categorias"
CATEGORY_PAGES_ARE_INDEXES = False

# ──────────────────────────────────────────
# Índice principal (home)
# ──────────────────────────────────────────
# El índice principal usa index.tmpl que muestra posts de blog en la home.
# Las secciones adicionales (fotos, videos, de-otros) se inyectan vía
# GLOBAL_CONTEXT_FILLER (ver más abajo).
INDEX_PATH = ""  # se genera en la raíz
INDEX_TITLE = ""  # sin título propio; lo pone el template
INDEX_DISPLAY_POST_COUNT = 100000
STRIP_INDEXES = True

# Búsqueda: el plugin flexsearch_plugin genera public/search_index.json.
# La UI y el índice FlexSearch viven en src/scripts/site.js para mantener
# la estética editorial propia del sitio.
FLEXSEARCH_INDEX_POSTS = True
FLEXSEARCH_INDEX_PAGES = False
FLEXSEARCH_INDEX_DRAFTS = False

# ──────────────────────────────────────────
# URLs / slug
# ──────────────────────────────────────────
SLUG_TAG_PATH = True
SLUG_AUTHOR_PATH = True
# Nikola usa {section}/{slug}/index.html por defecto, que coincide con Zola
PRETTY_URLS = True

# ──────────────────────────────────────────
# Build / assets
# ──────────────────────────────────────────
USE_BUNDLES = False
USE_CDN = False
FILES_FOLDERS = {"static": ""}  # static/ se copia tal cual en public/
THEME = "textosypretextos"

# ──────────────────────────────────────────
# Fecha
# ──────────────────────────────────────────
DATE_FORMAT = "dd.MM.yyyy"
DATETIME_FORMAT = "dd.MM.yyyy HH:mm"

# ──────────────────────────────────────────
# Comentarios (la API custom de Cloudflare Workers se mantiene igual)
# ──────────────────────────────────────────
COMMENT_SYSTEM = ""
COMMENT_SYSTEM_ID = ""

# ──────────────────────────────────────────
# Navegación
# ──────────────────────────────────────────
NAVIGATION_LINKS = {
    DEFAULT_LANG: (
        ("/", "Inicio"),
        ("/blog/", "Blog"),
        ("/fotos/", "Fotos"),
        ("/de-otros/", "De otres"),
        ("/videos/", "Videos"),
        ("/autores/", "Autoras y autores"),
        ("/etiquetas/", "Etiquetas"),
    )
}

COMMENTS_FILE = Path("data/comments.json")
if COMMENTS_FILE.exists():
    import json

    STATIC_COMMENTS = json.loads(COMMENTS_FILE.read_text(encoding="utf-8"))
else:
    STATIC_COMMENTS = {}


def post_section_slug(post):
    source_path = post.source_path.replace("\\", "/")
    if source_path.startswith("content/"):
        parts = source_path.split("/")
        if len(parts) > 1:
            return parts[1]
    return ""


SECTION_TITLES = {
    "blog": "Blog",
    "fotos": "Fotos",
    "videos": "Videos",
    "de-otros": "De otres",
    "personal": "Personal",
}


def post_comment_key(post):
    source_slug = Path(post.source_path).stem
    slug = post.meta("slug") or source_slug
    return f"{post_section_slug(post)}/{slug}"


def post_comments(post):
    return STATIC_COMMENTS.get(post_comment_key(post), [])


# ──────────────────────────────────────────
# Contexto global (accesible en todos los templates)
# ──────────────────────────────────────────
GLOBAL_CONTEXT = {
    "github_repo": "mgaitan/textosypretextos",
    "github_branch": "main",
    "site_owner": "Martín Gaitán",
    "start_year": 2004,
    "now": datetime.now(),
    "taxonomy_url": lambda kind, name: f"/{kind}/{slugify(name)}/",
    "post_tags": lambda post: post.tags() if callable(post.tags) else (post.tags or []),
    "post_authors": lambda post: post.authors()
    if callable(post.authors)
    else (post.authors or []),
    "post_section_slug": post_section_slug,
    "section_titles": SECTION_TITLES,
    "post_comments": post_comments,
    "post_comment_count": lambda post: len(post_comments(post)),
    # popular_paths y recent_comments se mueven aquí desde content/_index.md
    # para evitar que el template los cargue con get_page() (no disponible en Nikola).
    # Editar manualmente cuando cambien.
    "popular_slugs": [
        "de-otros/no-te-rindas",
        "videos/discurso-de-pepe-mujica-en-rio-20",
        "fotos/reserva-de-orsai-4-cordoba",
        "blog/con-tanta-noche-por-la-ventana",
        "de-otros/gracias-por-el-fuego-fragmento",
        "de-otros/a-mi-no-me-la-vas-a-contar-1951",
        "videos/tupac-amaru-construyendo-un",
        "de-otros/coger-en-castellano",
    ],
}


# ──────────────────────────────────────────
# Context filler: inyecta posts por sección en todos los templates
# (equivalente a get_section() de Zola, resuelve la home multi-sección)
# ──────────────────────────────────────────
def _fill_section_context(context, template_name):
    """Agrupa los posts por sección y los expone como variables globales.

    Esto reemplaza el uso de get_section() en el template index.html de Zola.
    Disponible en cualquier template como blog_posts, fotos_posts, etc.
    """
    from collections import defaultdict

    by_section = defaultdict(list)
    posts = []
    if "site" in context:
        posts = getattr(context["site"], "timeline", [])
    if not posts:
        posts = context.get("posts", []) or context.get("post_list", [])

    for post in posts:
        parts = post.source_path.replace("\\", "/").split("/")
        # source_path es relativo al directorio de conf.py: content/blog/foo.md
        if len(parts) >= 2 and parts[0] == "content":
            by_section[parts[1]].append(post)

    def sorted_posts(lst, reverse=True):
        return sorted(lst, key=lambda p: p.date, reverse=reverse)

    context["blog_posts"] = sorted_posts(by_section.get("blog", []))[:8]
    context["fotos_posts"] = sorted_posts(by_section.get("fotos", []))[:1]
    context["videos_posts"] = sorted_posts(by_section.get("videos", []))[:1]
    context["de_otros_posts"] = sorted_posts(by_section.get("de-otros", []))[:1]

    # Entradas populares: busca posts cuyo slug coincida con popular_slugs
    slug_to_post = {p.meta("slug"): p for p in posts}
    popular = []
    for slug_path in context.get("popular_slugs", []):
        slug = slug_path.split("/")[-1]
        if slug in slug_to_post:
            popular.append(slug_to_post[slug])
    context["popular_posts"] = popular[:8]


GLOBAL_CONTEXT_FILLER = [_fill_section_context]

# ──────────────────────────────────────────
# Miscelánea
# ──────────────────────────────────────────
SOCIAL_BUTTONS_CODE = ""
SEARCH_FORM = ""  # el buscador usa flexsearch_plugin + site.js
BODY_END = ""
EXTRA_HEAD_DATA = ""
