"""Brief writer — persists generated briefs to disk."""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

BRIEFS_DIR = Path("briefs")
_lock = threading.Lock()


def write_brief(brief: str, run_id: str, timestamp: str, prompts: str = "") -> str:
    """Write brief to disk and return the filepath string.

    Creates:
      briefs/spec1_brief_{YYYY-MM-DD}.md    — dated file
      briefs/spec1_brief_latest.md          — always overwritten
      briefs/brief_index.jsonl              — append-only index

    When *prompts* is non-empty, also creates:
      briefs/spec1_prompts_{YYYY-MM-DD}.md  — dated prompts artifact
      briefs/spec1_prompts_latest.md        — always overwritten
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

    # Build prompts content: use provided string or extract from brief
    if prompts is not None:
        prompts_doc = prompts
        prompt_count = prompts.count("**CLAUDE PROMPT:**")
    else:
        extracted = _extract_prompts(brief)
        prompts_doc = _build_prompts_doc(extracted, date_str, timestamp)
        prompt_count = len(extracted)

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

        if prompts:
            prompts_dated = BRIEFS_DIR / f"spec1_prompts_{date_str}.md"
            prompts_latest = BRIEFS_DIR / "spec1_prompts_latest.md"
            prompts_dated.write_text(prompts, encoding="utf-8")
            prompts_latest.write_text(prompts, encoding="utf-8")
            logger.info("Prompts written to %s", prompts_dated)

    logger.info("Brief written to %s (%d words)", dated_path, word_count)
    return str(dated_path)
