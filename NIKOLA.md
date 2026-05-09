# Migración Zola a Nikola

Esta rama migra el sitio estático de Zola a Nikola manteniendo la estructura
visual del theme editorial, pero simplificando los fuentes de contenido.

## Objetivos resueltos

- Nikola se ejecuta con `uvx --from 'nikola[extras]' nikola`.
- El theme vive en `themes/textosypretextos/` y usa Jinja.
- Los artículos usan YAML simple en lugar del front matter TOML heredado.
- Los comentarios heredados viven en `data/comments.json`, no dentro de cada artículo.
- Las páginas manuales de `content/autores/`, `content/etiquetas/`,
  `content/blog/subsecciones/` y los `_index.md` derivados fueron eliminados.
- Autores y etiquetas salen de la metadata de cada artículo y Nikola genera las
  taxonomías automáticamente.
- El teaser de listados sale del cuerpo antes de `<!-- TEASER_END -->`.
- Los links especiales a fotos con modal se preservan en el contenido.
- `/buscar/` usa `flexsearch_plugin` para generar `public/search_index.json` y
  FlexSearch en el bundle del theme.
- `/random/` reutiliza el mismo índice generado por Nikola.

## Comandos

```bash
npm install
npm run build
npm run dev
npm run preview
```

`npm run build` compila assets con Vite y luego corre Nikola:

```bash
npm run build:assets
uvx --from 'nikola[extras]' nikola build
```

## Metadata simplificada

```yaml
---
title: Gordo
slug: gordo
date: 2008-08-05 15:43:38
author: Martín Gaitán
tags:
  - Gente
  - Amistad
  - Familia
---

Primer párrafo que se muestra como teaser.

<!-- TEASER_END -->

Resto del artículo.
```

Campos legacy o inferibles como `legacy_id`, `legacy_url`, `summary`, `visits`,
`popularite`, `author_links`, `tag_links`, `section_slug`, `section_title` y
`comment_count` no forman parte de los fuentes migrados.

## Fuente de verdad

La fuente de verdad de autores y etiquetas es el artículo. Las páginas públicas
de `/autores/` y `/etiquetas/` son salida generada por Nikola, no contenido que
se edite a mano.

La sección se infiere del path `content/<seccion>/...`. El contador de
comentarios se infiere de `data/comments.json` y de la API dinámica.

El migrador normaliza etiquetas de forma case-insensitive para evitar duplicados
como `canción` y `Canción`. No normaliza autores con alias: si un nombre está
mal escrito, se corrige el artículo fuente.

## Shortcodes

Los shortcodes están en `shortcodes/*.tmpl` y usan sintaxis Nikola:

```md
{{% dialogo %}}
-- Primera intervención
-- Segunda intervención
{{% /dialogo %}}

{{% video_embed provider="youtube" id="X" %}}
```

Para poesía:

```md
{{% poetry %}}
Primer verso
Segundo verso
{{% /poetry %}}
```

## Búsqueda

El plugin `plugins/flexsearch_plugin/` genera `public/search_index.json` durante
el build. La UI de `/buscar/` no usa la interfaz incluida por el plugin: consume
ese JSON desde `src/scripts/site.js` para mantener el diseño del sitio.

Configuración relevante en `conf.py`:

```python
FLEXSEARCH_INDEX_POSTS = True
FLEXSEARCH_INDEX_PAGES = False
FLEXSEARCH_INDEX_DRAFTS = False
```

## Tamaño del repo

El peso del repo viene principalmente de `static/media/` versionado en Git. La
migración de SSG no cambia ese dato; una mejora futura razonable sería mover
media pesada a Git LFS o a un storage/CDN externo.
