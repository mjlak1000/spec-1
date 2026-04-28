"""SPEC-1 MCP Server — exposes SPEC-1 tools to Claude via Model Context Protocol.

Tools exposed:
  - run_cycle          Run a full SPEC-1 intelligence cycle
  - get_signals        Return recent harvested signals
  - get_intel          Return intelligence records
  - get_leads          Return actionable leads
  - get_brief          Return the latest world brief
  - get_psyop          Return psyop detection scores
  - get_fara           Return FARA filing records
  - analyse_psyop      Score text for psyop patterns
  - get_stats          Return system statistics
  - file_verdict       File a human verdict on an intelligence record
  - get_verdicts       Return verdicts (optionally for a single record)
  - get_calibration    Produce a calibration drift report from intel + verdicts

This server uses a simple JSON-RPC 2.0 over stdio protocol compatible
with the Claude MCP specification.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# MCP protocol helpers
# ---------------------------------------------------------------------------

def _make_response(request_id: Any, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _make_error(request_id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _send(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def _store_path(env_var: str, default: str) -> Path:
    return Path(os.environ.get(env_var, default))


def _read_jsonl(path: Path, limit: int = 20) -> list[dict]:
    """Read the last `limit` records from a JSONL file."""
    if not path.exists():
        return []
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records[-limit:]


def tool_run_cycle(args: dict) -> dict:
    """Run a full SPEC-1 intelligence cycle."""
    from spec1_engine.core.engine import Engine, EngineConfig

    max_signals = args.get("max_signals")
    environment = args.get("environment", "production")
    store_path = _store_path("SPEC1_STORE_PATH", "spec1_intelligence.jsonl")

    config = EngineConfig(
        environment=environment,
        store_path=store_path,
        max_signals=int(max_signals) if max_signals else None,
    )
    engine = Engine(config)
    stats = engine.run()
    return stats.to_dict()


def tool_get_signals(args: dict) -> list[dict]:
    """Return recent OSINT signals."""
    limit = int(args.get("limit", 20))
    path = _store_path("SPEC1_OSINT_PATH", "osint_records.jsonl")
    return _read_jsonl(path, limit=limit)


def tool_get_intel(args: dict) -> list[dict]:
    """Return intelligence records."""
    limit = int(args.get("limit", 20))
    min_confidence = float(args.get("min_confidence", 0.0))
    path = _store_path("SPEC1_STORE_PATH", "spec1_intelligence.jsonl")
    records = _read_jsonl(path, limit=200)
    if min_confidence > 0:
        records = [r for r in records if float(r.get("confidence", 0)) >= min_confidence]
    return records[-limit:]


def tool_get_leads(args: dict) -> list[dict]:
    """Return actionable intelligence leads."""
    limit = int(args.get("limit", 20))
    priority = args.get("priority")
    path = _store_path("SPEC1_LEADS_PATH", "leads.jsonl")
    records = _read_jsonl(path, limit=200)
    if priority:
        records = [r for r in records if r.get("priority") == priority.upper()]
    return records[-limit:]


def tool_get_brief(args: dict) -> dict:
    """Return the latest world brief."""
    path = _store_path("SPEC1_BRIEFS_PATH", "world_briefs.jsonl")
    records = _read_jsonl(path, limit=1)
    if not records:
        return {"message": "No brief available yet"}
    return records[-1]


def tool_get_psyop(args: dict) -> list[dict]:
    """Return psyop detection scores."""
    limit = int(args.get("limit", 20))
    min_risk = args.get("min_classification", "LOW_RISK")
    path = _store_path("SPEC1_PSYOP_PATH", "psyop_scores.jsonl")
    records = _read_jsonl(path, limit=200)
    order = {"CLEAN": 0, "LOW_RISK": 1, "MEDIUM_RISK": 2, "HIGH_RISK": 3}
    threshold = order.get(min_risk, 1)
    filtered = [r for r in records if order.get(r.get("classification", "CLEAN"), 0) >= threshold]
    return filtered[-limit:]


def tool_get_fara(args: dict) -> list[dict]:
    """Return FARA filing records."""
    limit = int(args.get("limit", 20))
    country = args.get("country")
    path = _store_path("SPEC1_OSINT_PATH", "osint_records.jsonl")
    records = _read_jsonl(path, limit=500)
    fara_records = [r for r in records if r.get("source_type") == "fara"]
    if country:
        fara_records = [
            r for r in fara_records
            if r.get("metadata", {}).get("country", "").lower() == country.lower()
        ]
    return fara_records[-limit:]


def tool_analyse_psyop(args: dict) -> dict:
    """Score text for psychological operation patterns."""
    text = args.get("text", "")
    if not text:
        return {"error": "text is required"}
    from cls_psyop.scorer import score_text
    result = score_text(str(text))
    return result.to_dict()


def tool_get_stats(args: dict) -> dict:
    """Return system statistics (record counts across all stores)."""
    stats: dict[str, int] = {}
    paths = {
        "intelligence": _store_path("SPEC1_STORE_PATH", "spec1_intelligence.jsonl"),
        "osint": _store_path("SPEC1_OSINT_PATH", "osint_records.jsonl"),
        "leads": _store_path("SPEC1_LEADS_PATH", "leads.jsonl"),
        "psyop": _store_path("SPEC1_PSYOP_PATH", "psyop_scores.jsonl"),
        "quant": _store_path("SPEC1_QUANT_PATH", "quant_signals.jsonl"),
        "briefs": _store_path("SPEC1_BRIEFS_PATH", "world_briefs.jsonl"),
        "verdicts": _store_path("SPEC1_VERDICTS_PATH", "verdicts.jsonl"),
    }
    for name, path in paths.items():
        if path.exists():
            with path.open("r", encoding="utf-8") as fh:
                stats[name] = sum(1 for line in fh if line.strip())
        else:
            stats[name] = 0
    stats["checked_at"] = datetime.now(timezone.utc).isoformat()  # type: ignore[assignment]
    return stats


def tool_file_verdict(args: dict) -> dict:
    """File a human verdict on a stored intelligence record."""
    from cls_verdicts.schemas import VALID_VERDICTS, Verdict
    from cls_verdicts.store import VerdictStore

    record_id = str(args.get("record_id", "")).strip()
    kind = str(args.get("verdict", "")).strip().lower()
    reviewer = str(args.get("reviewer", "anonymous")).strip() or "anonymous"
    notes = str(args.get("notes", ""))

    if not record_id:
        return {"error": "record_id is required"}
    if kind not in VALID_VERDICTS:
        return {"error": f"verdict must be one of {sorted(VALID_VERDICTS)}, got {kind!r}"}

    reviewed_at = datetime.now(timezone.utc)
    verdict = Verdict(
        verdict_id=Verdict.make_id(record_id, reviewer, reviewed_at),
        record_id=record_id,
        verdict=kind,  # type: ignore[arg-type]
        reviewer=reviewer,
        reviewed_at=reviewed_at,
        notes=notes,
    )
    store = VerdictStore(_store_path("SPEC1_VERDICTS_PATH", "verdicts.jsonl"))
    return store.save(verdict)


def tool_get_verdicts(args: dict) -> list[dict]:
    """Return verdicts. If record_id is given, returns every verdict for that record."""
    from cls_verdicts.store import VerdictStore

    record_id = args.get("record_id")
    limit = int(args.get("limit", 20))
    store = VerdictStore(_store_path("SPEC1_VERDICTS_PATH", "verdicts.jsonl"))

    if record_id:
        return store.for_record(str(record_id))
    # Tail of the JSONL — last `limit` verdicts in insertion order.
    return list(store.read_all())[-limit:]


def tool_get_calibration(args: dict) -> dict:
    """Produce a calibration drift report from the current intel + verdicts stores."""
    from cls_calibration.aggregator import produce_report
    from cls_calibration.proposer import propose_adjustments

    include_proposals = bool(args.get("include_proposals", False))
    sample_floor = int(args.get("sample_floor", 5))
    delta_floor = float(args.get("delta_floor", 0.15))

    intel = _read_jsonl(_store_path("SPEC1_STORE_PATH", "spec1_intelligence.jsonl"), limit=10**9)
    verdicts = _read_jsonl(_store_path("SPEC1_VERDICTS_PATH", "verdicts.jsonl"), limit=10**9)

    report = produce_report(intel, verdicts)
    out = report.to_dict()
    if include_proposals:
        proposal = propose_adjustments(
            report,
            sample_floor=sample_floor,
            delta_floor=delta_floor,
        )
        out["proposal"] = proposal.to_dict()
    return out


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

TOOLS: dict[str, dict] = {
    "run_cycle": {
        "description": "Run a full SPEC-1 intelligence cycle (harvest, score, investigate, store).",
        "parameters": {
            "type": "object",
            "properties": {
                "max_signals": {"type": "integer", "description": "Limit number of signals (optional)"},
                "environment": {"type": "string", "default": "production"},
            },
        },
        "fn": tool_run_cycle,
    },
    "get_signals": {
        "description": "Return recent harvested OSINT signals.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 20, "maximum": 200},
            },
        },
        "fn": tool_get_signals,
    },
    "get_intel": {
        "description": "Return intelligence records from the analysis store.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 20},
                "min_confidence": {"type": "number", "default": 0.0},
            },
        },
        "fn": tool_get_intel,
    },
    "get_leads": {
        "description": "Return actionable intelligence leads.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 20},
                "priority": {"type": "string", "enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW"]},
            },
        },
        "fn": tool_get_leads,
    },
    "get_brief": {
        "description": "Return the latest world intelligence brief.",
        "parameters": {"type": "object", "properties": {}},
        "fn": tool_get_brief,
    },
    "get_psyop": {
        "description": "Return psychological operation detection scores.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 20},
                "min_classification": {
                    "type": "string",
                    "enum": ["LOW_RISK", "MEDIUM_RISK", "HIGH_RISK"],
                    "default": "LOW_RISK",
                },
            },
        },
        "fn": tool_get_psyop,
    },
    "get_fara": {
        "description": "Return FARA (Foreign Agents Registration Act) filing records.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 20},
                "country": {"type": "string", "description": "Filter by country"},
            },
        },
        "fn": tool_get_fara,
    },
    "analyse_psyop": {
        "description": "Score a text snippet for psychological operation patterns.",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to analyse"},
            },
            "required": ["text"],
        },
        "fn": tool_analyse_psyop,
    },
    "get_stats": {
        "description": "Return record counts across all SPEC-1 stores.",
        "parameters": {"type": "object", "properties": {}},
        "fn": tool_get_stats,
    },
    "file_verdict": {
        "description": (
            "File a human verdict on a stored intelligence record. "
            "Verdicts are append-only — multiple verdicts may exist per record."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "record_id": {"type": "string", "description": "Target IntelligenceRecord id"},
                "verdict": {
                    "type": "string",
                    "enum": ["correct", "incorrect", "partial", "unclear"],
                },
                "reviewer": {"type": "string", "default": "anonymous"},
                "notes": {"type": "string", "default": ""},
            },
            "required": ["record_id", "verdict"],
        },
        "fn": tool_file_verdict,
    },
    "get_verdicts": {
        "description": "Return verdicts. With record_id, returns every verdict for that record.",
        "parameters": {
            "type": "object",
            "properties": {
                "record_id": {"type": "string", "description": "Filter to a single record (optional)"},
                "limit": {"type": "integer", "default": 20},
            },
        },
        "fn": tool_get_verdicts,
    },
    "get_calibration": {
        "description": (
            "Produce a calibration drift report from the current intel + verdicts stores. "
            "Descriptive only — never auto-applies tuning. Set include_proposals=true to "
            "also return suggested adjustments."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "include_proposals": {"type": "boolean", "default": False},
                "sample_floor": {"type": "integer", "default": 5},
                "delta_floor": {"type": "number", "default": 0.15},
            },
        },
        "fn": tool_get_calibration,
    },
}


# ---------------------------------------------------------------------------
# MCP method handlers
# ---------------------------------------------------------------------------

def handle_initialize(request_id: Any, params: dict) -> dict:
    return _make_response(request_id, {
        "protocolVersion": "2024-11-05",
        "capabilities": {"tools": {}},
        "serverInfo": {"name": "spec1-mcp-server", "version": "0.4.0"},
    })


def handle_tools_list(request_id: Any, params: dict) -> dict:
    tools_list = []
    for name, meta in TOOLS.items():
        tools_list.append({
            "name": name,
            "description": meta["description"],
            "inputSchema": meta["parameters"],
        })
    return _make_response(request_id, {"tools": tools_list})


def handle_tools_call(request_id: Any, params: dict) -> dict:
    tool_name = params.get("name", "")
    arguments = params.get("arguments", {})

    if tool_name not in TOOLS:
        return _make_error(request_id, -32601, f"Tool not found: {tool_name}")

    try:
        result = TOOLS[tool_name]["fn"](arguments)
        content = [{"type": "text", "text": json.dumps(result, indent=2, default=str)}]
        return _make_response(request_id, {"content": content, "isError": False})
    except Exception as exc:
        tb = traceback.format_exc()
        return _make_response(request_id, {
            "content": [{"type": "text", "text": f"Error: {exc}\n{tb}"}],
            "isError": True,
        })


def handle_request(line: str) -> None:
    try:
        request = json.loads(line)
    except json.JSONDecodeError as exc:
        _send(_make_error(None, -32700, f"Parse error: {exc}"))
        return

    request_id = request.get("id")
    method = request.get("method", "")
    params = request.get("params", {})

    if method == "initialize":
        _send(handle_initialize(request_id, params))
    elif method == "tools/list":
        _send(handle_tools_list(request_id, params))
    elif method == "tools/call":
        _send(handle_tools_call(request_id, params))
    elif method == "notifications/initialized":
        pass  # No response needed for notifications
    else:
        _send(_make_error(request_id, -32601, f"Method not found: {method}"))


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the MCP server, reading JSON-RPC requests from stdin."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        handle_request(line)


if __name__ == "__main__":
    main()
