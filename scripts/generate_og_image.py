#!/usr/bin/env python3

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path


DEFAULT_TITLE = "Textos y Pretextos"
DEFAULT_TAGLINE = "Un weblog de Martín Gaitán"
DEFAULT_BADGE = "Desde 2004"
DEFAULT_WIDTH = 1200
DEFAULT_HEIGHT = 630


def build_html(site_css: Path, title: str, tagline: str, badge: str, width: int, height: int) -> str:
    return f"""<!doctype html>
<html lang="es">
  <head>
    <meta charset="utf-8">
    <title>Textos y Pretextos share card</title>
    <link rel="stylesheet" href="{site_css.resolve().as_uri()}">
    <style>
      html, body {{
        margin: 0;
        padding: 0;
        width: {width}px;
        height: {height}px;
        overflow: hidden;
        background: #fff;
        position: relative;
      }}
      .frame {{
        position: absolute;
        top: 32px;
        left: 32px;
        width: {width - 64}px;
        height: {height - 64}px;
        overflow: hidden;
        box-sizing: border-box;
        border: 2px solid #000;
        background:
          linear-gradient(180deg, rgba(0, 0, 0, 0.03) 0, rgba(0, 0, 0, 0.03) 1px, transparent 1px, transparent 100%),
          linear-gradient(90deg, rgba(0, 0, 0, 0.025) 0, rgba(0, 0, 0, 0.025) 1px, transparent 1px, transparent 100%),
          #fff;
        background-size: 100% 10px, 10px 100%, auto;
        padding: 42px 54px;
        display: grid;
        grid-template-rows: auto 1fr auto 1fr auto;
      }}
      .top-rule {{
        width: 100%;
        height: 10px;
        background: #000;
        margin-bottom: 34px;
      }}
      .masthead {{
        border: 0 !important;
        padding: 0 !important;
        background: transparent !important;
      }}
      .masthead-grid {{
        display: block !important;
      }}
      .brand-title {{
        margin: 0 !important;
        padding: 0 !important;
        font-size: 8.85rem !important;
        line-height: 0.86 !important;
        letter-spacing: -0.06em !important;
      }}
      .story-kicker {{
        margin: 20px 0 0 1.35em !important;
        font-size: 25px !important;
        letter-spacing: 0.24em !important;
        color: rgb(82 90 102) !important;
      }}
      .spacer {{
        min-height: 0;
      }}
      .footer-row {{
        align-self: end;
        position: relative;
        min-height: 50px;
      }}
      .footer-line {{
        position: absolute;
        left: 50%;
        right: 0;
        bottom: 0;
        height: 2px;
        background: #000;
      }}
      .badge {{
        position: absolute;
        right: 0;
        bottom: 0;
        display: inline-flex;
        align-items: center;
        background: #000;
        color: #fff;
        font-family: var(--font-ui);
        font-size: 24px;
        font-weight: 500;
        line-height: 1;
        text-transform: uppercase;
        letter-spacing: 0.16em;
        padding: 10px 18px;
      }}
    </style>
  </head>
  <body>
    <div class="frame">
      <div class="top-rule"></div>
      <div class="spacer"></div>
      <header class="masthead">
        <div class="masthead-grid">
          <div>
            <h1 class="brand-title">{title}</h1>
            <p class="story-kicker">{tagline}</p>
          </div>
        </div>
      </header>
      <div class="spacer"></div>
      <div class="footer-row">
        <span class="footer-line" aria-hidden="true"></span>
        <span class="badge">{badge}</span>
      </div>
    </div>
  </body>
</html>
"""


def find_chrome(explicit: str | None) -> str:
    if explicit:
        return explicit

    for candidate in (
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
    ):
        path = shutil.which(candidate)
        if path:
            return path

    raise SystemExit("No se encontró Chrome/Chromium. Pasá --chrome-bin /ruta/al/binario.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera la og-image.png usando el CSS real del sitio y Chrome headless.")
    parser.add_argument("--output", default="static/og-image.png")
    parser.add_argument("--site-css", default="static/assets/site.css")
    parser.add_argument("--title", default=DEFAULT_TITLE)
    parser.add_argument("--tagline", default=DEFAULT_TAGLINE)
    parser.add_argument("--badge", default=DEFAULT_BADGE)
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT)
    parser.add_argument("--chrome-bin")
    parser.add_argument("--dump-html", help="Guarda el HTML intermedio en esta ruta en vez de usar un tempfile.")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    output = (root / args.output).resolve()
    site_css = (root / args.site_css).resolve()
    chrome_bin = find_chrome(args.chrome_bin)

    if not site_css.exists():
        raise SystemExit(f"No existe el CSS: {site_css}")

    html = build_html(
        site_css=site_css,
        title=args.title,
        tagline=args.tagline,
        badge=args.badge,
        width=args.width,
        height=args.height,
    )

    output.parent.mkdir(parents=True, exist_ok=True)

    if args.dump_html:
        html_path = (root / args.dump_html).resolve()
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(html, encoding="utf-8")
    else:
        tmp = tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8")
        html_path = Path(tmp.name)
        tmp.write(html)
        tmp.close()

    # Chrome headless reserves ~87px for its UI chrome even in headless mode on Linux.
    # We over-provision the window height so the CSS content area is exactly args.height,
    # then crop the screenshot back to the desired dimensions.
    chrome_ui_overhead = 87
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_png:
        raw_png = Path(tmp_png.name)

    cmd = [
        chrome_bin,
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        f"--window-size={args.width},{args.height + chrome_ui_overhead}",
        f"--screenshot={raw_png}",
        html_path.as_uri(),
    ]
    subprocess.run(cmd, check=True)

    try:
        from PIL import Image
        with Image.open(raw_png) as img:
            img.crop((0, 0, args.width, args.height)).save(output)
    except ImportError:
        import shutil
        shutil.move(raw_png, output)
        print("Warning: Pillow not installed; screenshot NOT cropped. Install Pillow for exact dimensions.")
    else:
        raw_png.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
