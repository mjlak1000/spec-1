"""Out-of-process PDF renderer for SPEC-1 briefs.

Invoked as a subprocess from spec1_engine.briefing.writer.write_brief_pdf so
the API/engine processes never have to import weasyprint or its native deps.

Usage:
    python -m spec1_engine.tools.pdf_render --brief-md path/in.md --out path/out.pdf
"""

from __future__ import annotations

import argparse
from pathlib import Path


SACRED_GEOMETRY_SVG = '''<svg width="120" height="120" viewBox="0 0 500 500" xmlns="http://www.w3.org/2000/svg" style="display:block;margin:auto">
    <polygon points="250,60 430,160 430,340 250,440 70,340 70,160" fill="none" stroke="rgba(30,30,30,0.55)" stroke-width="8"/>
    <polygon points="250,108 392,188 392,308 250,388 108,308 108,188" fill="none" stroke="rgba(30,30,30,0.35)" stroke-width="6"/>
    <polygon points="250,156 354,216 354,280 250,340 146,280 146,216" fill="none" stroke="rgba(30,30,30,0.22)" stroke-width="5"/>
    <circle cx="250" cy="250" r="68" fill="none" stroke="rgba(30,30,30,0.18)" stroke-width="4"/>
    <circle cx="250" cy="182" r="68" fill="none" stroke="rgba(30,30,30,0.1)" stroke-width="3"/>
    <circle cx="309" cy="216" r="68" fill="none" stroke="rgba(30,30,30,0.1)" stroke-width="3"/>
    <circle cx="309" cy="284" r="68" fill="none" stroke="rgba(30,30,30,0.1)" stroke-width="3"/>
    <circle cx="250" cy="318" r="68" fill="none" stroke="rgba(30,30,30,0.1)" stroke-width="3"/>
    <circle cx="191" cy="284" r="68" fill="none" stroke="rgba(30,30,30,0.1)" stroke-width="3"/>
    <circle cx="191" cy="216" r="68" fill="none" stroke="rgba(30,30,30,0.1)" stroke-width="3"/>
    <g stroke="rgba(30,30,30,0.12)" stroke-width="3">
        <line x1="250" y1="250" x2="250" y2="60"/>
        <line x1="250" y1="250" x2="430" y2="160"/>
        <line x1="250" y1="250" x2="430" y2="340"/>
        <line x1="250" y1="250" x2="250" y2="440"/>
        <line x1="250" y1="250" x2="70" y2="340"/>
        <line x1="250" y1="250" x2="70" y2="160"/>
        <line x1="60" y1="250" x2="440" y2="250"/>
        <line x1="115" y1="115" x2="385" y2="385"/>
        <line x1="385" y1="115" x2="115" y2="385"/>
    </g>
    <path d="M170,250 Q210,200 250,194 Q290,200 330,250" fill="none" stroke="rgba(30,30,30,0.9)" stroke-width="10" stroke-linecap="round"/>
    <path d="M170,250 Q210,300 250,306 Q290,300 330,250" fill="none" stroke="rgba(30,30,30,0.9)" stroke-width="10" stroke-linecap="round"/>
    <circle cx="250" cy="250" r="38" fill="none" stroke="rgba(30,30,30,0.7)" stroke-width="8"/>
    <circle cx="250" cy="250" r="18" fill="rgba(30,30,30,0.9)"/>
    <circle cx="258" cy="242" r="6" fill="rgba(30,30,30,0.4)"/>
</svg>'''


_HTML_TEMPLATE = """<html><head>
<style>
    body {{ font-family: 'EB Garamond', Georgia, serif; color: #222; background: #fff; margin: 0; padding: 0; }}
    .logo-wrap {{ text-align: center; margin-top: 24px; }}
    .brief-content {{ max-width: 700px; margin: 32px auto; padding: 32px; background: #fafaf7; border-radius: 16px; box-shadow: 0 2px 12px #0001; }}
    h1, h2, h3 {{ font-family: 'EB Garamond', Georgia, serif; }}
    h1 {{ font-size: 2.1em; margin-bottom: 0.5em; }}
    h2 {{ font-size: 1.3em; margin-top: 1.5em; }}
    h3 {{ font-size: 1.1em; margin-top: 1.2em; }}
    p {{ font-size: 1.05em; line-height: 1.7; margin-bottom: 1em; }}
    .meta {{ color: #888; font-size: 0.95em; margin-bottom: 1.5em; }}
</style>
</head><body>
    <div class="logo-wrap">{svg}</div>
    <div class="brief-content">
        {body}
    </div>
</body></html>"""


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="spec1_engine.tools.pdf_render")
    p.add_argument("--brief-md", required=True, help="Path to markdown brief")
    p.add_argument("--out", required=True, help="Path to output PDF")
    return p


def render_brief_html(md_text: str) -> str:
    """Wrap rendered markdown in the SPEC-1 brief HTML template + sacred-geometry SVG."""
    from markdown import markdown

    html_body = markdown(md_text)
    return _HTML_TEMPLATE.format(svg=SACRED_GEOMETRY_SVG, body=html_body)


def render_pdf_from_markdown(md_text: str) -> bytes:
    """Convert markdown brief to PDF bytes via WeasyPrint.

    weasyprint is imported lazily so importing this module does not force
    the API/engine processes to load it.
    """
    html = render_brief_html(md_text)
    from weasyprint import HTML  # type: ignore

    return HTML(string=html).write_pdf()


def main(argv: list[str] | None = None) -> int:
    args = build_argparser().parse_args(argv)

    brief_md_path = Path(args.brief_md).expanduser().resolve()
    out_path = Path(args.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    md_text = brief_md_path.read_text(encoding="utf-8")
    pdf_bytes = render_pdf_from_markdown(md_text)
    out_path.write_bytes(pdf_bytes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
