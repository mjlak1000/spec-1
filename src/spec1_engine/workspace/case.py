"""Case file management for persistent investigations."""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime
from typing import Optional

from spec1_engine.core import ids, logging_utils
from spec1_engine.schemas.models import CaseFile, Signal

logger = logging_utils.get_logger(__name__)

# Workspace directory at project root
WORKSPACE_DIR = Path(__file__).parent.parent.parent.parent / "workspace"
CASES_DIR = WORKSPACE_DIR / "cases"
REPORTS_DIR = WORKSPACE_DIR / "reports"
INDEX_FILE = WORKSPACE_DIR / "case_index.jsonl"


def _ensure_dirs():
    """Ensure workspace directories exist."""
    CASES_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def open_case(
    title: str,
    question: str,
    tags: list[str],
    environment: str = "osint",
    run_id: Optional[str] = None,
) -> CaseFile:
    """
    Open a new case file.

    Args:
        title: Human-readable name
        question: Core investigation question
        tags: List of search tags
        environment: Environment identifier
        run_id: Optional run ID

    Returns:
        CaseFile object
    """
    _ensure_dirs()

    if not run_id:
        run_id = ids.run_id()

    case_id = ids.case_id()
    now = datetime.utcnow()

    case = CaseFile(
        case_id=case_id,
        title=title,
        question=question,
        tags=tags,
        status="OPEN",
        opened_at=now,
        updated_at=now,
        run_id=run_id,
        environment=environment,
    )

    # Write case file
    case_file = CASES_DIR / f"case_{case_id}.json"
    with open(case_file, "w") as f:
        f.write(json.dumps(case.to_dict(), indent=2, default=str))

    # Append to index
    with open(INDEX_FILE, "a") as f:
        f.write(json.dumps({"case_id": case_id, "title": title, "status": "OPEN", "opened_at": now.isoformat()}) + "\n")

    logger.info(f"case_opened: case_id={case_id}, title={title}, tags={tags}")
    print(f"\n[OK] Case opened: {case_id}")
    print(f"  Title:    {title}")
    print(f"  Question: {question}")
    print(f"  Tags:     {', '.join(tags)}\n")

    return case


def update_case(
    case_id: str,
    new_signals: list[Signal],
    new_finding: str,
) -> CaseFile:
    """
    Update a case with new signals and finding.

    Args:
        case_id: Case ID
        new_signals: List of Signal objects matched to this case
        new_finding: Finding string from researcher

    Returns:
        Updated CaseFile
    """
    _ensure_dirs()

    case_file = CASES_DIR / f"case_{case_id}.json"
    if not case_file.exists():
        raise ValueError(f"Case {case_id} not found")

    # Load case
    with open(case_file, "r") as f:
        case_dict = json.load(f)

    case = _dict_to_case(case_dict)

    # Append new signal IDs
    for sig in new_signals:
        if sig.signal_id not in case.signal_ids:
            case.signal_ids.append(sig.signal_id)

    # Append finding
    if new_finding:
        case.findings.append(new_finding)

    # Update metadata
    case.updated_at = datetime.utcnow()
    case.research_runs += 1

    # Recalculate confidence (simple: average over findings)
    if case.findings:
        high_count = sum(1 for f in case.findings if "HIGH" in f.upper())
        medium_count = sum(1 for f in case.findings if "MEDIUM" in f.upper())
        low_count = sum(1 for f in case.findings if "LOW" in f.upper())
        total = high_count + medium_count + low_count
        if total > 0:
            case.confidence = (high_count * 1.0 + medium_count * 0.5 + low_count * 0.0) / total

    # Write back
    with open(case_file, "w") as f:
        f.write(json.dumps(case.to_dict(), indent=2, default=str))

    logger.info(f"case_updated: case_id={case_id}, signals_added={len(new_signals)}, total_signals={len(case.signal_ids)}, findings={len(case.findings)}")

    return case


def close_case(case_id: str) -> CaseFile:
    """
    Close a case and generate final research report.

    Args:
        case_id: Case ID

    Returns:
        Closed CaseFile
    """
    _ensure_dirs()

    case_file = CASES_DIR / f"case_{case_id}.json"
    if not case_file.exists():
        raise ValueError(f"Case {case_id} not found")

    # Load case
    with open(case_file, "r") as f:
        case_dict = json.load(f)

    case = _dict_to_case(case_dict)
    case.status = "CLOSED"

    # Write back
    with open(case_file, "w") as f:
        f.write(json.dumps(case.to_dict(), indent=2, default=str))

    # Generate report
    report_path = REPORTS_DIR / f"report_{case_id}.md"
    report_md = _generate_report_md(case)
    with open(report_path, "w") as f:
        f.write(report_md)

    # Update index
    _update_case_in_index(case_id, "CLOSED")

    logger.info(f"case_closed: case_id={case_id}, title={case.title}")

    print(f"\n[OK] Case closed: {case_id}")
    print(f"  Report: {report_path.relative_to(WORKSPACE_DIR.parent)}\n")

    return case


def list_cases(status: Optional[str] = None) -> list[CaseFile]:
    """
    List all cases, optionally filtered by status.

    Args:
        status: Optional status filter (OPEN, CLOSED, WATCHING)

    Returns:
        List of CaseFile objects
    """
    _ensure_dirs()

    cases = []
    if not CASES_DIR.exists():
        return cases

    # Read from individual case files
    for case_file in sorted(CASES_DIR.glob("case_*.json")):
        with open(case_file, "r") as f:
            case_dict = json.load(f)
            case = _dict_to_case(case_dict)
            if status is None or case.status == status:
                cases.append(case)

    return cases


def get_case(case_id: str) -> CaseFile:
    """Get a specific case by ID."""
    _ensure_dirs()

    case_file = CASES_DIR / f"case_{case_id}.json"
    if not case_file.exists():
        raise ValueError(f"Case {case_id} not found")

    with open(case_file, "r") as f:
        case_dict = json.load(f)

    return _dict_to_case(case_dict)


def _dict_to_case(d: dict) -> CaseFile:
    """Convert dict from JSON to CaseFile."""
    # Handle datetime strings
    opened_at = d["opened_at"]
    if isinstance(opened_at, str):
        opened_at = datetime.fromisoformat(opened_at)

    updated_at = d["updated_at"]
    if isinstance(updated_at, str):
        updated_at = datetime.fromisoformat(updated_at)

    return CaseFile(
        case_id=d["case_id"],
        title=d["title"],
        question=d["question"],
        tags=d.get("tags", []),
        status=d.get("status", "OPEN"),
        opened_at=opened_at,
        updated_at=updated_at,
        signal_ids=d.get("signal_ids", []),
        findings=d.get("findings", []),
        research_runs=d.get("research_runs", 0),
        confidence=d.get("confidence", 0.5),
        run_id=d.get("run_id", ""),
        environment=d.get("environment", "osint"),
        metadata=d.get("metadata", {}),
    )


def _update_case_in_index(case_id: str, status: str):
    """Update case status in the index file."""
    if not INDEX_FILE.exists():
        return

    lines = []
    with open(INDEX_FILE, "r") as f:
        for line in f:
            entry = json.loads(line.strip())
            if entry.get("case_id") == case_id:
                entry["status"] = status
            lines.append(json.dumps(entry))

    with open(INDEX_FILE, "w") as f:
        for line in lines:
            f.write(line + "\n")


def _generate_report_md(case: CaseFile) -> str:
    """Generate a markdown report for a closed case."""
    lines = [
        f"# Case Report: {case.title}",
        f"",
        f"**Case ID:** `{case.case_id}`",
        f"**Status:** {case.status}",
        f"**Opened:** {case.opened_at.isoformat()}",
        f"**Closed:** {datetime.utcnow().isoformat()}",
        f"**Final Confidence:** {case.confidence:.1%}",
        f"",
        f"## Question",
        f"{case.question}",
        f"",
        f"## Tags",
        f"{', '.join(f'`{tag}`' for tag in case.tags)}",
        f"",
        f"## Evidence",
        f"**Signals Matched:** {len(case.signal_ids)}",
        f"**Research Cycles:** {case.research_runs}",
        f"",
    ]

    if case.findings:
        lines.extend([
            f"## Findings",
            f"",
        ])
        for i, finding in enumerate(case.findings, 1):
            lines.append(f"### Cycle {i}")
            lines.append(finding)
            lines.append("")

    lines.extend([
        f"---",
        f"*Generated by SPEC-1 workspace*",
    ])

    return "\n".join(lines)
