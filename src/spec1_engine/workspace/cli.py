"""Command-line interface for case management.

Usage:
    python -m spec1_engine.workspace open "Title" "Question" --tags "tag1,tag2"
    python -m spec1_engine.workspace list
    python -m spec1_engine.workspace status <case_id>
    python -m spec1_engine.workspace close <case_id>
    python -m spec1_engine.workspace report <case_id>
"""

from __future__ import annotations

import sys
import argparse
from pathlib import Path

from spec1_engine.workspace.case import (
    open_case,
    list_cases,
    get_case,
    close_case,
)

REPORTS_DIR = Path(__file__).parent.parent.parent.parent / "workspace" / "reports"


def cmd_open(args):
    """Open a new case."""
    title = args.title
    question = args.question
    tags = [t.strip() for t in args.tags.split(",") if t.strip()]

    case = open_case(title, question, tags)
    return 0


def cmd_list(args):
    """List all open cases."""
    cases = list_cases(status=args.status or None)

    if not cases:
        print("No cases found.")
        return 0

    print(f"\n{'Case ID':<20} {'Title':<40} {'Status':<10} {'Signals':<10}")
    print("-" * 80)

    for case in cases:
        signals = len(case.signal_ids)
        print(f"{case.case_id:<20} {case.title:<40} {case.status:<10} {signals:<10}")

    print()
    return 0


def cmd_status(args):
    """Show detailed case status."""
    case = get_case(args.case_id)

    print(f"\n{'='*60}")
    print(f"CASE: {case.title}")
    print(f"{'='*60}")
    print(f"ID:         {case.case_id}")
    print(f"Status:     {case.status}")
    print(f"Question:   {case.question}")
    print(f"Tags:       {', '.join(case.tags)}")
    print(f"Opened:     {case.opened_at.isoformat()}")
    print(f"Updated:    {case.updated_at.isoformat()}")
    print(f"")
    print(f"Signals:    {len(case.signal_ids)}")
    print(f"Findings:   {len(case.findings)}")
    print(f"Cycles:     {case.research_runs}")
    print(f"Confidence: {case.confidence:.1%}")
    print(f"{'='*60}")

    if case.findings:
        print(f"\nLatest Finding:")
        print(f"{'-'*60}")
        print(case.findings[-1][:500])
        if len(case.findings[-1]) > 500:
            print("...")
        print()

    return 0


def cmd_close(args):
    """Close a case."""
    case = close_case(args.case_id)

    report_file = REPORTS_DIR / f"report_{case.case_id}.md"
    print(f"Report written to: {report_file}")
    return 0


def cmd_report(args):
    """Show the final report for a case."""
    report_file = REPORTS_DIR / f"report_{args.case_id}.md"

    if not report_file.exists():
        print(f"Report not found: {report_file}")
        return 1

    with open(report_file, "r") as f:
        print(f.read())

    return 0


def main():
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="SPEC-1 Case Workspace CLI",
        prog="python -m spec1_engine.workspace",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # open
    open_parser = subparsers.add_parser("open", help="Open a new case")
    open_parser.add_argument("title", help="Case title")
    open_parser.add_argument("question", help="Investigation question")
    open_parser.add_argument("--tags", required=True, help="Comma-separated tags")
    open_parser.set_defaults(func=cmd_open)

    # list
    list_parser = subparsers.add_parser("list", help="List all cases")
    list_parser.add_argument("--status", help="Filter by status (OPEN, CLOSED, WATCHING)")
    list_parser.set_defaults(func=cmd_list)

    # status
    status_parser = subparsers.add_parser("status", help="Show case status")
    status_parser.add_argument("case_id", help="Case ID")
    status_parser.set_defaults(func=cmd_status)

    # close
    close_parser = subparsers.add_parser("close", help="Close a case")
    close_parser.add_argument("case_id", help="Case ID")
    close_parser.set_defaults(func=cmd_close)

    # report
    report_parser = subparsers.add_parser("report", help="Show case report")
    report_parser.add_argument("case_id", help="Case ID")
    report_parser.set_defaults(func=cmd_report)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
