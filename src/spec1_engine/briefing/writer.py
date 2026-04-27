"""Brief writer — persists generated briefs to disk."""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

BRIEFS_DIR = Path("briefs")
_lock = threading.Lock()


def _extract_prompts(brief: str) -> list[str]:
    """Extract CLAUDE PROMPT blockquote blocks from a generated brief.

    Returns a list of blockquote strings, one per lead.
    """
    prompts = []
    lines = brief.splitlines()
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith(">") and "**CLAUDE PROMPT:**" in stripped:
            block_lines = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                block_lines.append(lines[i])
                i += 1
            prompts.append("\n".join(block_lines))
        else:
            i += 1
    return prompts


def _build_prompts_doc(prompts: list[str], date_str: str, timestamp: str) -> str:
    """Build the prompts-only markdown document."""
    lines = [
        f"# SPEC-1 Investigation Prompts — {date_str}",
        f"Generated: {timestamp}",
        "",
    ]
    if not prompts:
        lines.append("_(No Claude investigation prompts in this brief.)_")
        lines.append("")
    else:
        for i, prompt_block in enumerate(prompts, start=1):
            lines.append(f"## Prompt {i}")
            lines.append("")
            lines.append(prompt_block)
            lines.append("")
    return "\n".join(lines)


def write_brief(
    brief: str,
    run_id: str,
    timestamp: str,
    prompts: str | None = None,  # accepted for backward compat with callers that pass the API prompts text
) -> str:
    """Write brief to disk and return the filepath string.

    Creates:
      briefs/spec1_brief_{YYYY-MM-DD}.md    — dated full brief
      briefs/spec1_brief_latest.md          — always overwritten
      briefs/spec1_prompts_{YYYY-MM-DD}.md  — investigation prompts only
      briefs/spec1_prompts_latest.md        — always overwritten
      briefs/brief_index.jsonl              — append-only index
    """
    BRIEFS_DIR.mkdir(parents=True, exist_ok=True)

    # Parse date from timestamp; fall back to today
    try:
        dt = datetime.fromisoformat(timestamp)
    except Exception:
        dt = datetime.now(timezone.utc)
    date_str = dt.strftime("%Y-%m-%d")

    dated_path = BRIEFS_DIR / f"spec1_brief_{date_str}.md"
    latest_path = BRIEFS_DIR / "spec1_brief_latest.md"
    prompts_dated_path = BRIEFS_DIR / f"spec1_prompts_{date_str}.md"
    prompts_latest_path = BRIEFS_DIR / "spec1_prompts_latest.md"
    index_path = BRIEFS_DIR / "brief_index.jsonl"

    word_count = len(brief.split())

    # Extract and format investigation prompts from brief
    extracted_prompts = _extract_prompts(brief)
    prompts_doc = _build_prompts_doc(extracted_prompts, date_str, timestamp)

    with _lock:
        dated_path.write_text(brief, encoding="utf-8")
        latest_path.write_text(brief, encoding="utf-8")
        prompts_dated_path.write_text(prompts_doc, encoding="utf-8")
        prompts_latest_path.write_text(prompts_doc, encoding="utf-8")

        index_entry = {
            "run_id": run_id,
            "date": date_str,
            "filepath": str(dated_path),
            "word_count": word_count,
            "timestamp": timestamp,
        }
        with index_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(index_entry) + "\n")

    logger.info("Brief written to %s (%d words, %d prompts)", dated_path, word_count, len(extracted_prompts))
    return str(dated_path)


def write_brief_pdf(brief_md_path: Path, out_pdf_path: Path) -> Path:
    """Render a markdown brief to PDF via the out-of-process renderer.

    Subprocesses to `python -m spec1_engine.tools.pdf_render` so weasyprint and
    its native deps stay out of the engine/API process. Raises RuntimeError on
    any subprocess failure (missing input, render error, missing weasyprint).
    """
    brief_md_path = Path(brief_md_path)
    out_pdf_path = Path(out_pdf_path)
    out_pdf_path.parent.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "spec1_engine.tools.pdf_render",
            "--brief-md",
            str(brief_md_path),
            "--out",
            str(out_pdf_path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"PDF render failed (exit {result.returncode}): {result.stderr.strip() or result.stdout.strip()}"
        )
    return out_pdf_path
