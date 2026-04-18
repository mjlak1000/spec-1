"""WorldBrief persistence — JSONL index + dated Markdown files."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

from cls_world_brief.formatter import to_markdown
from cls_world_brief.schemas import WorldBrief


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class BriefStore:
    """Persists WorldBrief objects to JSONL + Markdown files."""

    def __init__(
        self,
        jsonl_path: Path = Path("world_briefs.jsonl"),
        briefs_dir: Path = Path("briefs"),
    ) -> None:
        self.jsonl_path = Path(jsonl_path)
        self.briefs_dir = Path(briefs_dir)
        self._lock = threading.Lock()

    def save(self, brief: WorldBrief, write_markdown: bool = True) -> dict:
        """Save a WorldBrief to JSONL index and optionally to a Markdown file.

        Returns the JSONL entry dict.
        """
        entry = {**brief.to_dict(), "written_at": _now()}

        with self._lock:
            # Write to JSONL index
            self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
            with self.jsonl_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")

            # Write Markdown file
            if write_markdown:
                self.briefs_dir.mkdir(parents=True, exist_ok=True)
                md_path = self.briefs_dir / f"{brief.date}.md"
                latest_path = self.briefs_dir / "latest.md"
                md_content = to_markdown(brief)
                md_path.write_text(md_content, encoding="utf-8")
                latest_path.write_text(md_content, encoding="utf-8")

        return entry

    def read_all(self) -> Iterator[dict]:
        """Iterate over all brief records from the JSONL index."""
        if not self.jsonl_path.exists():
            return
        with self.jsonl_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue

    def latest(self) -> Optional[dict]:
        """Return the most recently saved brief dict."""
        last = None
        for record in self.read_all():
            last = record
        return last

    def get_by_date(self, date: str) -> Optional[dict]:
        """Return the brief for a specific date (YYYY-MM-DD)."""
        for record in self.read_all():
            if record.get("date") == date:
                return record
        return None

    def count(self) -> int:
        return sum(1 for _ in self.read_all())

    def clear(self) -> None:
        if self.jsonl_path.exists():
            self.jsonl_path.unlink()

    def list_markdown_files(self) -> list[Path]:
        """Return sorted list of brief Markdown files."""
        if not self.briefs_dir.exists():
            return []
        return sorted(self.briefs_dir.glob("*.md"))
