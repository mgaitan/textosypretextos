# AGENTS.md

## Propósito

Esta guía documenta el flujo editorial, el theme y la operación del sitio para futuras sesiones de trabajo sobre `textosypretextos`.

## Flujo editorial

### Requisitos

- `node` / `npm`
- `uv`
- Nikola ejecutado con `uvx --from 'nikola[extras]' nikola`
- `hunspell` + diccionario `es_AR` (para el checker ortográfico)
- `prek` o `pre-commit` (opcional, para correr el hook antes de cada commit)

### Comandos de trabajo

```bash
npm install
npm run dev
```

- `npm run dev` recompila assets y levanta `nikola auto`.
- `npm run dev:drafts` queda como alias operativo del dev server.
- `npm run build` genera `public/` con Vite + Nikola.
- `npm run preview` levanta una preview local con Wrangler sobre el build.

### Crear un artículo nuevo

En este repo usar:

```bash
uv run scripts/new_article.py blog "Título del artículo"
uv run scripts/new_article.py fotos "Título de la foto" --author "Martín Gaitán"
uv run scripts/new_article.py videos "Título del video" --tags "Cine, Música"
```

Eso genera un Markdown con front matter alineado al sitio.

### Secciones editoriales

- `blog/`: núcleo del sitio. Textos propios, crónicas, cuentos, poemas, apuntes y series.
- `fotos/`: entradas fotográficas. Si la imagen es central, cuidar `hero_image`, `hero_alt` y caption.
- `videos/`: textos con embed o referencia audiovisual.
- `de-otros/`: materiales ajenos; revisar bien autoría real.
- `personal/`: archivo menor, usar sólo si el contenido no encaja en las anteriores.

No crear contenido manual en:

- `autores/`: páginas derivadas de autor.
- `etiquetas/`: páginas derivadas de tags.
- `buscar.md`: página funcional del buscador.

### Boilerplate y metadata

Campos clave del front matter:

- `title`
- `slug`
- `date`
- `draft`
- `author`
- `tags`
- `hero_image`
- `hero_alt`
- `subtitle`
- `deck`  — epígrafe del artículo; soporta markdown. Un blockquote
  dentro del deck se muestra como epígrafe alineado a la derecha.
  El último párrafo del blockquote se interpreta como atribución:

  ```yaml
  deck: |
  > La línea del poema o cita.
  >
  > — Nombre del autor o fuente
  ```

  Alternativamente, usar el shortcode `epigrafe` en el body cuando el
  epígrafe es multilineal o no encaja en el campo deck:

  ```
  {{% epigrafe %}}
  Verso o cita.

  **— Fuente o autor**
  {{% /epigrafe %}}
  ```

  Los blockquotes markdown al comienzo del body también se renderizan
  como epígrafes automáticamente.

No usar campos legacy o inferibles como `legacy_id`, `legacy_url`, `summary`,
`visits`, `popularite`, `author_links`, `tag_links`, `section_slug`,
`section_title` o `comment_count`. Autores y etiquetas se declaran en el
artículo y Nikola genera las páginas públicas automáticamente.

Los comentarios importados desde el sitio anterior viven en `data/comments.json`
indexados por `seccion/slug`; no van dentro del front matter del artículo.

### Etiquetas y criterio editorial

- No sobreactuar el tagueo: preferir pocas etiquetas buenas.
- En `blog`, la primera etiqueta suele funcionar además como subcategoría visible.
- Para textos de terceros, cuidar que no quede Martín como autor visible si corresponde otro autor principal.

Herramienta existente para sugerir/normalizar etiquetas:

```bash
uv run scripts/infer_tags.py
```

### Multimedia

Imágenes:

- Guardar assets en `static/media/` si son nuevos.
- Usar `hero_image` para miniaturas y portada.
- Si una imagen necesita caption editorial, incluirla en el body como `figure`; no mostrar nombres de archivo salvo que funcionen como dato documental.

Videos:

- Preferir embeds actuales de YouTube.
- Verificar siempre que el embed publique correctamente en Pages.

Audio/archivos:

- Reusar los shortcodes de `shortcodes/`.

### Diálogos

- Para bloques de diálogo con una intervención por línea, usar el shortcode `dialogo` en vez de `<br>` manuales:

```md
{{% dialogo %}}
— Primera intervención
— Segunda intervención
{{% /dialogo %}}
```

- Para detectar y corregir casos simples con `--`, usar:

```bash
uv run scripts/fix_dialogues.py --apply content/fotos/cronica-de-un-intento-de-homenaje.md
```

- Sin `--apply`, el script corre en modo dry-run e informa candidatos y casos ambiguos para revisión manual.

### Poesía

- Para poemas o textos con cortes de verso que haya que preservar, usar el shortcode `poetry`:

```md
{{% poetry %}}
Primer verso
Segundo verso
Tercer verso
{{% /poetry %}}
```

- No usar `<br>` manuales si el bloque completo puede resolverse con el shortcode.

### Ortografía

```bash
# revisar el corpus completo
uv run scripts/check_spelling.py

# revisar archivos puntuales
uv run scripts/check_spelling.py content/blog/foo.md

# listar las palabras desconocidas más frecuentes (útil para sembrar la allow-list)
uv run scripts/check_spelling.py --list-unknown --top 100
```

El script usa `hunspell -d es_AR` y descarta frontmatter, code blocks, URLs,
emails, shortcodes y HTML antes de tokenizar. Las palabras válidas que el
diccionario no reconoce (nombres propios, marcas, voseo, extranjerismos,
lunfardo) viven en `scripts/spell_allow.txt`.

### Pre-commit hook

`.pre-commit-config.yaml` registra el hook `spell-check-es`. Para activarlo
una vez:

```bash
prek install         # o `pre-commit install`
```

A partir de ahí, cada `git commit` revisa los `.md` modificados bajo
`content/`. Si aparecen palabras desconocidas legítimas, agregalas a
`scripts/spell_allow.txt` (una por línea, sin acento ni mayúscula obligatoria
porque la comparación es case-insensitive).

### Reexportar contenido desde SPIP

```bash
uv run scripts/export_spip_to_zola.py
uv run scripts/infer_tags.py
```

Usar esto sólo si hace falta regenerar desde el dump original. Si el cambio es puntual y editorial, editar el Markdown fuente ya exportado.

## Theme

El theme sigue un sistema editorial inspirado en WIRED. La referencia base local es:

- [DESIGN.md](/home/tin/lab/nqnwebsc/sites/textosypretextos/DESIGN.md)

Origen del sistema:

- <https://getdesign.md/wired/design-md>
- comando de origen: `npx getdesign@latest add wired`

### Pautas visuales

- Tipografía expresiva serif para títulos y serif legible para cuerpo.
- UI y metadata en sans/mono con mayúsculas espaciadas.
- Blanco/negro como base; el azul sólo como acento puntual.
- Bordes rectos, sin sombras, sin glassmorphism, sin “cards SaaS”.
- El sitio debe sentirse editorial, no técnico.

### Archivos principales del theme

- `themes/textosypretextos/templates/base.tmpl`: estructura global, header, nav y footer.
- `themes/textosypretextos/templates/index.tmpl`: home.
- `themes/textosypretextos/templates/post.tmpl`: artículos.
- `themes/textosypretextos/templates/list.tmpl`: listados de sección.
- `themes/textosypretextos/templates/macros.tmpl`: cards/listados reutilizables.
- `src/styles/site.css`: estilos del theme.
- `src/scripts/site.js`: comportamiento del cliente.

## Deploy y operación

### Build y deploy

```bash
npm run build
npm run deploy
```

El deploy productivo usa Cloudflare Pages y el workflow de GitHub Actions al mergear en `main`.

### Wrangler

Comandos útiles:

```bash
npx wrangler pages dev public
npx wrangler pages deploy public --project-name textosypretextos
npx wrangler d1 execute textosypretextos-comments --remote --file=migrations/001_init.sql
```

### Comentarios

La API vive en `functions/api/comments.js` y persiste en D1.

Moderación rápida:

```bash
npx wrangler d1 execute textosypretextos-comments --remote --command "SELECT id, article_slug, author, status FROM comments ORDER BY created_at DESC LIMIT 20;"
npx wrangler d1 execute textosypretextos-comments --remote --command "UPDATE comments SET status='spam' WHERE id=123;"
```

### Secrets relevantes

- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`
- `COMMENT_SALT`

## Preferencia operativa para futuras sesiones

### Inicio de cada tarea

Antes de arrancar cualquier trabajo nuevo, asegurarse de estar en la versión más reciente de `main`, salvo indicación contraria:

```bash
git checkout main && git pull origin main
```

Crear la rama de trabajo a partir de ese punto.

### Pull Requests

Abrir siempre el PR con `gh pr create` y **esperar revisión y aprobación explícita antes de mergear**. No ejecutar `gh pr merge` por iniciativa propia.

### Cuando un prompt traiga una lista de tareas nuevas

1. crear primero issue/s con `gh` en `mgaitan/textosypretextos`
2. usar bodies pragmáticos y concretos, no texto inflado
3. recién después implementar en una rama de trabajo
4. dejar comentarios breves en el issue cuando haya avance real
5. cerrar o vincular el issue en el commit/PR correspondiente

Excepción:

- si el pedido ya dice “implementá el issue #N” o remite con claridad a un issue existente, no crear otro issue duplicado

### Uso correcto de `gh issue create` con body multilínea

Usar siempre `--body-file` para evitar que el shell interpole backticks u otras
expansiones en el cuerpo del issue:

```bash
cat > /tmp/issue_body.md << 'EOF'
Descripción con `backticks` sin problema.
EOF
gh issue create --title "Título" --body-file /tmp/issue_body.md
```
