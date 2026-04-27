"""Tests for the out-of-process PDF renderer and its subprocess wrapper."""

from __future__ import annotations

import subprocess
import sys

import pytest

from spec1_engine.briefing.writer import write_brief_pdf
from spec1_engine.tools import pdf_render


def test_argparser_requires_brief_md_and_out():
    parser = pdf_render.build_argparser()
    with pytest.raises(SystemExit):
        parser.parse_args([])
    args = parser.parse_args(["--brief-md", "in.md", "--out", "out.pdf"])
    assert args.brief_md == "in.md"
    assert args.out == "out.pdf"


def test_render_brief_html_wraps_template(tmp_path):
    pytest.importorskip("markdown")
    html = pdf_render.render_brief_html("# Hello\n\nbody text")
    assert "<html>" in html
    assert "Hello" in html
    assert "body text" in html
    assert "<svg" in html  # sacred geometry logo


def test_wrapper_raises_runtime_error_on_subprocess_failure(tmp_path):
    """Passing a nonexistent input path must surface as RuntimeError."""
    missing = tmp_path / "does_not_exist.md"
    out = tmp_path / "out.pdf"
    with pytest.raises(RuntimeError, match="PDF render failed"):
        write_brief_pdf(brief_md_path=missing, out_pdf_path=out)
    assert not out.exists()


def test_render_pdf_end_to_end(tmp_path):
    """Full render path — skipped when weasyprint or markdown isn't installed."""
    pytest.importorskip("weasyprint")
    pytest.importorskip("markdown")

    brief = tmp_path / "brief.md"
    brief.write_text("# SPEC-1 Test Brief\n\nA short paragraph.\n", encoding="utf-8")
    out = tmp_path / "out.pdf"

    write_brief_pdf(brief_md_path=brief, out_pdf_path=out)

    assert out.exists()
    assert out.read_bytes()[:5] == b"%PDF-"


def test_cli_module_invocation_help():
    """`python -m spec1_engine.tools.pdf_render --help` returns 0."""
    result = subprocess.run(
        [sys.executable, "-m", "spec1_engine.tools.pdf_render", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "--brief-md" in result.stdout
    assert "--out" in result.stdout
