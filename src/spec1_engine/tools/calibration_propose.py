"""CLI: read intel + verdicts stores, write a calibration proposal report.

Usage:
    PYTHONPATH=src python -m spec1_engine.tools.calibration_propose \
        --intel spec1_intelligence.jsonl \
        --verdicts verdicts.jsonl \
        --out-dir generated/

Writes:
    <out-dir>/calibration_report.md     — human-readable proposal
    <out-dir>/calibration_report.jsonl  — append-only audit trail
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from cls_calibration.aggregator import produce_report
from cls_calibration.formatter import to_markdown
from cls_calibration.proposer import propose_adjustments


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="spec1_engine.tools.calibration_propose")
    p.add_argument(
        "--intel",
        default=os.environ.get("SPEC1_STORE_PATH", "spec1_intelligence.jsonl"),
        help="Path to intelligence JSONL store",
    )
    p.add_argument(
        "--verdicts",
        default=os.environ.get("SPEC1_VERDICTS_PATH", "verdicts.jsonl"),
        help="Path to verdicts JSONL store",
    )
    p.add_argument(
        "--out-dir",
        default="generated",
        help="Directory to write the proposal report into",
    )
    p.add_argument("--sample-floor", type=int, default=5)
    p.add_argument("--delta-floor", type=float, default=0.15)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_argparser().parse_args(argv)
    intel_path = Path(args.intel)
    verdicts_path = Path(args.verdicts)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    records = _read_jsonl(intel_path)
    verdicts = _read_jsonl(verdicts_path)

    calibration_report = produce_report(records, verdicts)
    proposal = propose_adjustments(
        calibration_report,
        sample_floor=args.sample_floor,
        delta_floor=args.delta_floor,
    )

    md_path = out_dir / "calibration_report.md"
    md_path.write_text(to_markdown(proposal), encoding="utf-8")

    audit_path = out_dir / "calibration_report.jsonl"
    audit_entry = {
        "written_at": datetime.now(timezone.utc).isoformat(),
        "intel_path": str(intel_path),
        "verdicts_path": str(verdicts_path),
        "calibration": calibration_report.to_dict(),
        "proposal": proposal.to_dict(),
    }
    with audit_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(audit_entry) + "\n")

    print(
        f"records={len(records)} verdicts={len(verdicts)} "
        f"adjustments={len(proposal.adjustments)} -> {md_path}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
