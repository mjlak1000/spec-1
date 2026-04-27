"""Tests for mcp_server.py — MCP server tool implementations."""

from __future__ import annotations

import json
import sys
import os
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add repo root to path for mcp_server import
sys.path.insert(0, str(Path(__file__).parent.parent))

import mcp_server
from mcp_server import (
    _make_response,
    _make_error,
    handle_initialize,
    handle_tools_list,
    handle_tools_call,
    handle_request,
    tool_get_signals,
    tool_get_intel,
    tool_get_leads,
    tool_get_brief,
    tool_get_psyop,
    tool_get_fara,
    tool_analyse_psyop,
    tool_get_stats,
    tool_file_verdict,
    tool_get_verdicts,
    tool_get_calibration,
    TOOLS,
)


class TestProtocolHelpers:
    def test_make_response_structure(self):
        resp = _make_response("req-1", {"result": "ok"})
        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] == "req-1"
        assert resp["result"] == {"result": "ok"}

    def test_make_error_structure(self):
        err = _make_error("req-1", -32601, "Method not found")
        assert err["jsonrpc"] == "2.0"
        assert err["id"] == "req-1"
        assert err["error"]["code"] == -32601
        assert "Method not found" in err["error"]["message"]


class TestInitialize:
    def test_returns_protocol_version(self):
        resp = handle_initialize("id-1", {})
        assert resp["result"]["protocolVersion"] == "2024-11-05"
        assert "serverInfo" in resp["result"]
        assert resp["result"]["serverInfo"]["name"] == "spec1-mcp-server"


class TestToolsList:
    def test_lists_all_tools(self):
        resp = handle_tools_list("id-1", {})
        tools = resp["result"]["tools"]
        tool_names = [t["name"] for t in tools]
        assert "run_cycle" in tool_names
        assert "get_signals" in tool_names
        assert "get_intel" in tool_names
        assert "get_leads" in tool_names
        assert "get_brief" in tool_names
        assert "get_psyop" in tool_names
        assert "get_fara" in tool_names
        assert "analyse_psyop" in tool_names
        assert "get_stats" in tool_names
        assert "file_verdict" in tool_names
        assert "get_verdicts" in tool_names
        assert "get_calibration" in tool_names

    def test_each_tool_has_description(self):
        resp = handle_tools_list("id-1", {})
        for tool in resp["result"]["tools"]:
            assert tool["description"]

    def test_each_tool_has_input_schema(self):
        resp = handle_tools_list("id-1", {})
        for tool in resp["result"]["tools"]:
            assert "inputSchema" in tool


class TestToolsCall:
    def test_unknown_tool_returns_error(self):
        resp = handle_tools_call("id-1", {"name": "nonexistent_tool", "arguments": {}})
        assert resp["id"] == "id-1"
        assert "error" in resp

    def test_analyse_psyop_tool_works(self):
        resp = handle_tools_call("id-1", {
            "name": "analyse_psyop",
            "arguments": {"text": "false flag staged crisis actor deep state"},
        })
        assert resp["result"]["isError"] is False
        content_text = resp["result"]["content"][0]["text"]
        data = json.loads(content_text)
        assert "score_id" in data
        assert "classification" in data

    def test_tool_exception_returns_is_error_true(self):
        with patch.dict(mcp_server.TOOLS, {
            "bad_tool": {"fn": lambda args: 1 / 0, "description": "bad", "parameters": {}}
        }):
            resp = handle_tools_call("id-1", {"name": "bad_tool", "arguments": {}})
        assert resp["result"]["isError"] is True


class TestGetSignals:
    def test_returns_empty_when_no_store(self, tmp_path):
        missing = tmp_path / "missing.jsonl"
        with patch.dict(os.environ, {"SPEC1_OSINT_PATH": str(missing)}):
            result = tool_get_signals({})
        assert result == []

    def test_returns_records_from_jsonl(self, tmp_path):
        store_path = tmp_path / "osint.jsonl"
        store_path.write_text(
            json.dumps({"record_id": "r1", "source_type": "rss", "content": "test"}) + "\n"
        )
        with patch.dict(os.environ, {"SPEC1_OSINT_PATH": str(store_path)}):
            result = tool_get_signals({"limit": 10})

        assert len(result) == 1
        assert result[0]["record_id"] == "r1"

    def test_respects_limit(self, tmp_path):
        store_path = tmp_path / "osint.jsonl"
        lines = [json.dumps({"record_id": f"r{i}", "content": f"record {i}"}) for i in range(10)]
        store_path.write_text("\n".join(lines) + "\n")
        with patch.dict(os.environ, {"SPEC1_OSINT_PATH": str(store_path)}):
            result = tool_get_signals({"limit": 3})

        assert len(result) == 3


class TestGetIntel:
    def test_filters_by_min_confidence(self, tmp_path):
        store_path = tmp_path / "intel.jsonl"
        store_path.write_text(
            json.dumps({"record_id": "r1", "confidence": 0.9}) + "\n" +
            json.dumps({"record_id": "r2", "confidence": 0.3}) + "\n"
        )
        with patch.dict(os.environ, {"SPEC1_STORE_PATH": str(store_path)}):
            result = tool_get_intel({"min_confidence": 0.7})

        assert all(r["confidence"] >= 0.7 for r in result)

    def test_no_filter_returns_all(self, tmp_path):
        store_path = tmp_path / "intel.jsonl"
        store_path.write_text(
            json.dumps({"record_id": "r1", "confidence": 0.9}) + "\n" +
            json.dumps({"record_id": "r2", "confidence": 0.3}) + "\n"
        )
        with patch.dict(os.environ, {"SPEC1_STORE_PATH": str(store_path)}):
            result = tool_get_intel({})

        assert len(result) == 2


class TestGetLeads:
    def test_filters_by_priority(self, tmp_path):
        store_path = tmp_path / "leads.jsonl"
        store_path.write_text(
            json.dumps({"lead_id": "l1", "priority": "HIGH"}) + "\n" +
            json.dumps({"lead_id": "l2", "priority": "LOW"}) + "\n"
        )
        with patch.dict(os.environ, {"SPEC1_LEADS_PATH": str(store_path)}):
            result = tool_get_leads({"priority": "HIGH"})

        assert len(result) == 1
        assert result[0]["priority"] == "HIGH"


class TestGetBrief:
    def test_returns_no_brief_message_when_empty(self, tmp_path):
        missing = tmp_path / "missing.jsonl"
        with patch.dict(os.environ, {"SPEC1_BRIEFS_PATH": str(missing)}):
            result = tool_get_brief({})
        assert "No brief" in result.get("message", "")

    def test_returns_latest_brief(self, tmp_path):
        store_path = tmp_path / "briefs.jsonl"
        store_path.write_text(
            json.dumps({"brief_id": "b1", "date": "2024-01-01", "headline": "H1"}) + "\n" +
            json.dumps({"brief_id": "b2", "date": "2024-01-02", "headline": "H2"}) + "\n"
        )
        with patch.dict(os.environ, {"SPEC1_BRIEFS_PATH": str(store_path)}):
            result = tool_get_brief({})

        assert result["brief_id"] == "b2"


class TestGetPsyop:
    def test_filters_by_classification(self, tmp_path):
        store_path = tmp_path / "psyop.jsonl"
        store_path.write_text(
            json.dumps({"score_id": "s1", "classification": "HIGH_RISK", "score": 0.9}) + "\n" +
            json.dumps({"score_id": "s2", "classification": "CLEAN", "score": 0.0}) + "\n"
        )
        with patch.dict(os.environ, {"SPEC1_PSYOP_PATH": str(store_path)}):
            result = tool_get_psyop({"min_classification": "MEDIUM_RISK"})

        assert all(r["classification"] in ("HIGH_RISK", "MEDIUM_RISK") for r in result)


class TestGetFara:
    def test_filters_by_country(self, tmp_path):
        store_path = tmp_path / "osint.jsonl"
        store_path.write_text(
            json.dumps({
                "record_id": "f1", "source_type": "fara",
                "metadata": {"country": "Russia", "registrant": "Acme"}
            }) + "\n" +
            json.dumps({
                "record_id": "f2", "source_type": "fara",
                "metadata": {"country": "China", "registrant": "Beta"}
            }) + "\n" +
            json.dumps({
                "record_id": "r1", "source_type": "rss",
                "metadata": {}
            }) + "\n"
        )
        with patch.dict(os.environ, {"SPEC1_OSINT_PATH": str(store_path)}):
            result = tool_get_fara({"country": "Russia"})

        assert len(result) == 1
        assert result[0]["metadata"]["country"] == "Russia"


class TestAnalysePsyop:
    def test_scores_text(self):
        result = tool_analyse_psyop({"text": "false flag staged crisis actor"})
        assert "score_id" in result
        assert "classification" in result
        assert "score" in result

    def test_returns_error_for_missing_text(self):
        result = tool_analyse_psyop({})
        assert "error" in result

    def test_clean_text_is_clean(self):
        result = tool_analyse_psyop({"text": "Weather forecast: sunny skies tomorrow."})
        assert result["classification"] == "CLEAN"


class TestGetStats:
    def test_returns_counts(self, tmp_path):
        for fname in ("intel.jsonl", "osint.jsonl", "leads.jsonl"):
            p = tmp_path / fname
            p.write_text(json.dumps({"record_id": "r1"}) + "\n" * 3)

        env_overrides = {
            "SPEC1_STORE_PATH": str(tmp_path / "intel.jsonl"),
            "SPEC1_OSINT_PATH": str(tmp_path / "osint.jsonl"),
            "SPEC1_LEADS_PATH": str(tmp_path / "leads.jsonl"),
            "SPEC1_PSYOP_PATH": str(tmp_path / "psyop.jsonl"),
            "SPEC1_QUANT_PATH": str(tmp_path / "quant.jsonl"),
            "SPEC1_BRIEFS_PATH": str(tmp_path / "briefs.jsonl"),
            "SPEC1_VERDICTS_PATH": str(tmp_path / "verdicts.jsonl"),
        }
        with patch.dict(os.environ, env_overrides):
            result = tool_get_stats({})

        assert "intelligence" in result
        assert "osint" in result
        assert "verdicts" in result
        assert "checked_at" in result


class TestFileVerdict:
    def test_writes_verdict_to_jsonl(self, tmp_path):
        path = tmp_path / "verdicts.jsonl"
        with patch.dict(os.environ, {"SPEC1_VERDICTS_PATH": str(path)}):
            result = tool_file_verdict({
                "record_id": "rec-1",
                "verdict": "correct",
                "reviewer": "alice",
                "notes": "matches independent reporting",
            })

        assert result["record_id"] == "rec-1"
        assert result["verdict"] == "correct"
        assert result["reviewer"] == "alice"
        assert path.exists()
        line = path.read_text().strip()
        assert json.loads(line)["record_id"] == "rec-1"

    def test_rejects_unknown_verdict(self, tmp_path):
        path = tmp_path / "verdicts.jsonl"
        with patch.dict(os.environ, {"SPEC1_VERDICTS_PATH": str(path)}):
            result = tool_file_verdict({"record_id": "rec-1", "verdict": "maybe"})
        assert "error" in result
        assert not path.exists()

    def test_requires_record_id(self, tmp_path):
        path = tmp_path / "verdicts.jsonl"
        with patch.dict(os.environ, {"SPEC1_VERDICTS_PATH": str(path)}):
            result = tool_file_verdict({"verdict": "correct"})
        assert "error" in result


class TestGetVerdicts:
    def _seed(self, path: Path) -> None:
        path.write_text(
            json.dumps({"verdict_id": "v1", "record_id": "r1", "verdict": "correct"}) + "\n" +
            json.dumps({"verdict_id": "v2", "record_id": "r1", "verdict": "partial"}) + "\n" +
            json.dumps({"verdict_id": "v3", "record_id": "r2", "verdict": "incorrect"}) + "\n"
        )

    def test_returns_all_when_no_filter(self, tmp_path):
        path = tmp_path / "verdicts.jsonl"
        self._seed(path)
        with patch.dict(os.environ, {"SPEC1_VERDICTS_PATH": str(path)}):
            result = tool_get_verdicts({"limit": 10})
        assert len(result) == 3

    def test_filters_by_record_id(self, tmp_path):
        path = tmp_path / "verdicts.jsonl"
        self._seed(path)
        with patch.dict(os.environ, {"SPEC1_VERDICTS_PATH": str(path)}):
            result = tool_get_verdicts({"record_id": "r1"})
        assert len(result) == 2
        assert all(v["record_id"] == "r1" for v in result)

    def test_returns_empty_when_store_missing(self, tmp_path):
        path = tmp_path / "missing.jsonl"
        with patch.dict(os.environ, {"SPEC1_VERDICTS_PATH": str(path)}):
            result = tool_get_verdicts({})
        assert result == []


class TestGetCalibration:
    def test_produces_report_from_intel_and_verdicts(self, tmp_path):
        intel_path = tmp_path / "intel.jsonl"
        verdicts_path = tmp_path / "verdicts.jsonl"
        intel_path.write_text(
            json.dumps({
                "record_id": "r1", "classification": "CORROBORATED",
                "confidence": 0.9, "source_weight": 0.8, "analyst_weight": 0.7,
            }) + "\n"
        )
        verdicts_path.write_text(
            json.dumps({"verdict_id": "v1", "record_id": "r1", "verdict": "correct"}) + "\n"
        )
        env = {
            "SPEC1_STORE_PATH": str(intel_path),
            "SPEC1_VERDICTS_PATH": str(verdicts_path),
        }
        with patch.dict(os.environ, env):
            report = tool_get_calibration({})

        assert report["total_records"] == 1
        assert report["total_verdicts"] == 1
        assert report["matched_verdicts"] == 1
        assert "CORROBORATED" in report["by_classification"]

    def test_include_proposals_adds_proposal_block(self, tmp_path):
        intel_path = tmp_path / "intel.jsonl"
        verdicts_path = tmp_path / "verdicts.jsonl"
        intel_path.write_text("")
        verdicts_path.write_text("")
        env = {
            "SPEC1_STORE_PATH": str(intel_path),
            "SPEC1_VERDICTS_PATH": str(verdicts_path),
        }
        with patch.dict(os.environ, env):
            report = tool_get_calibration({"include_proposals": True})

        assert "proposal" in report
        assert "adjustments" in report["proposal"]


class TestHandleRequest:
    def test_initialize_request(self, capsys):
        line = json.dumps({"jsonrpc": "2.0", "id": "1", "method": "initialize", "params": {}})
        mcp_server.handle_request(line)
        out = capsys.readouterr().out
        resp = json.loads(out)
        assert resp["result"]["protocolVersion"] == "2024-11-05"

    def test_tools_list_request(self, capsys):
        line = json.dumps({"jsonrpc": "2.0", "id": "2", "method": "tools/list", "params": {}})
        mcp_server.handle_request(line)
        out = capsys.readouterr().out
        resp = json.loads(out)
        assert "tools" in resp["result"]

    def test_invalid_json_sends_error(self, capsys):
        mcp_server.handle_request("not valid json{{{")
        out = capsys.readouterr().out
        resp = json.loads(out)
        assert "error" in resp

    def test_unknown_method_sends_error(self, capsys):
        line = json.dumps({"jsonrpc": "2.0", "id": "3", "method": "unknown/method", "params": {}})
        mcp_server.handle_request(line)
        out = capsys.readouterr().out
        resp = json.loads(out)
        assert "error" in resp

    def test_notification_no_response(self, capsys):
        line = json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        mcp_server.handle_request(line)
        out = capsys.readouterr().out
        assert out == ""
