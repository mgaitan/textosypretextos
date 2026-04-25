# Textos y Pretextos

Sitio personal de Martín Gaitán (textos, fotos, videos, lecturas) generado con
[Zola](https://www.getzola.org/) y desplegado en Cloudflare Pages.

## Estructura

- `content/` — artículos, fotos, videos, autores y etiquetas en Markdown.
- `static/media/` — imágenes y archivos asociados a los artículos.
- `templates/` — templates Tera (Zola).
- `src/styles/` — CSS con Tailwind v4.
- `src/scripts/` — JS del cliente (navegación, comentarios dinámicos).
- `scripts/` — scripts Python (uv) para regenerar el contenido desde el dump
  SPIP original o inferir etiquetas.
- `functions/api/comments.js` — Cloudflare Pages Function que sirve la API de
  comentarios contra una base D1.
- `migrations/` — esquema D1.

## Desarrollo

Necesitás Node 20+, [Zola](https://www.getzola.org/documentation/getting-started/installation/) y
[uv](https://docs.astral.sh/uv/) (solo si vas a re-correr los scripts de export).

```bash
npm install
npm run dev          # build:assets + zola serve
```

### Re-generar contenido desde el dump SPIP

```bash
uv run scripts/export_spip_to_zola.py
uv run scripts/infer_tags.py
```

(El dump original vive fuera del repo; el script asume rutas absolutas que
podés ajustar con `--dump`, `--assets-dir`, `--output-root`.)

## Build y deploy

```bash
npm run build        # vite build + zola build → public/
npm run preview      # build + npx wrangler pages dev public/
npm run deploy       # build + npx wrangler pages deploy public/
```

El despliegue automático corre en GitHub Actions cuando se mergea a `main`.

### Secrets necesarios en el repo

- `CLOUDFLARE_API_TOKEN` — token de Cloudflare con permisos de _Pages_ y _D1_.
  Se crea en https://dash.cloudflare.com/profile/api-tokens.
- `CLOUDFLARE_ACCOUNT_ID` — ID de la cuenta (`npx wrangler whoami`).

### Comentarios (D1)

Los comentarios dinámicos viven en una base D1 (`textosypretextos-comments`).

Inicializar / migrar:

```bash
npx wrangler d1 execute textosypretextos-comments --remote --file=migrations/001_init.sql
```

Variables opcionales en Pages (`Settings → Environment variables`):

- `COMMENT_SALT` — sal para hashear IPs (privacidad básica + rate limiting).

Los comentarios históricos importados desde SPIP siguen siendo estáticos
(viven en el frontmatter del artículo). Los nuevos van a D1.
