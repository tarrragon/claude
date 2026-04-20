"""Tests for ticket_system/commands/track_dispatch_check.py (0.18.0-W10-017.2).

5 情境覆蓋（AC5 要求 3 情境，補 no_file 與 malformed 作邊界）：
1. no_file: 檔案不存在 → exit 0 + [PASS]
2. empty_list: dispatches=[] → exit 0 + [PASS]
3. single: 1 個活躍 → exit 1 + [WARN] + 1 筆列表
4. multiple: 3 個活躍 → exit 1 + [WARN] + 3 筆列表
5. malformed_json: JSON 毀損 → exit 2 + stderr [FAIL]
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

import pytest

from ticket_system.commands import track_dispatch_check as mod
from ticket_system.commands.track_dispatch_check import execute_dispatch_check


def _run(tmp_path: Path, monkeypatch) -> tuple[int, str, str]:
    """呼叫 execute_dispatch_check 並捕獲 stdout/stderr。"""
    monkeypatch.setattr(mod, "get_project_root", lambda: tmp_path)

    args = argparse.Namespace()
    out_buf, err_buf = io.StringIO(), io.StringIO()
    saved_out, saved_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = out_buf, err_buf
    try:
        rc = execute_dispatch_check(args)
    finally:
        sys.stdout, sys.stderr = saved_out, saved_err
    return rc, out_buf.getvalue(), err_buf.getvalue()


def _write_dispatch_file(tmp_path: Path, payload: object) -> Path:
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    path = claude_dir / "dispatch-active.json"
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class TestDispatchCheck:

    def test_no_file(self, tmp_path, monkeypatch):
        """檔案不存在 → exit 0，視同已清空。"""
        rc, out, err = _run(tmp_path, monkeypatch)
        assert rc == 0
        assert "[PASS]" in out
        assert "無活躍派發" in out
        assert err == ""

    def test_empty_list(self, tmp_path, monkeypatch):
        """dispatches=[] → exit 0。"""
        _write_dispatch_file(tmp_path, {"dispatches": []})
        rc, out, err = _run(tmp_path, monkeypatch)
        assert rc == 0
        assert "[PASS]" in out
        assert err == ""

    def test_single_dispatch(self, tmp_path, monkeypatch):
        """1 個活躍派發 → exit 1，列出該筆。"""
        _write_dispatch_file(tmp_path, {
            "dispatches": [
                {
                    "agent_description": "test-agent-alpha",
                    "ticket_id": "0.18.0-W10-017.2",
                    "dispatched_at": "2026-04-20T04:00:00+00:00",
                },
            ],
        })
        rc, out, err = _run(tmp_path, monkeypatch)
        assert rc == 1
        assert "[WARN]" in out
        assert "有 1 個活躍派發" in out
        assert "test-agent-alpha" in out
        assert "0.18.0-W10-017.2" in out
        assert "2026-04-20T04:00:00+00:00" in out

    def test_multiple_dispatches(self, tmp_path, monkeypatch):
        """3 個活躍派發 → exit 1，全部列出。"""
        _write_dispatch_file(tmp_path, {
            "dispatches": [
                {"agent_description": "alpha", "ticket_id": "A", "dispatched_at": "t1"},
                {"agent_description": "beta", "ticket_id": "", "dispatched_at": "t2"},
                {"agent_description": "gamma", "dispatched_at": "t3"},
            ],
        })
        rc, out, err = _run(tmp_path, monkeypatch)
        assert rc == 1
        assert "[WARN]" in out
        assert "有 3 個活躍派發" in out
        assert "alpha" in out
        assert "beta" in out
        assert "gamma" in out
        assert "(no ticket)" in out  # beta 的 ticket_id="" 與 gamma 的缺欄位皆顯示 fallback

    def test_malformed_json(self, tmp_path, monkeypatch):
        """JSON 格式錯誤 → exit 2，stderr 寫 [FAIL]。"""
        _write_dispatch_file(tmp_path, "{this is not valid json")
        rc, out, err = _run(tmp_path, monkeypatch)
        assert rc == 2
        assert "[FAIL]" in err
        assert "JSON 格式錯誤" in err

    def test_non_dict_root(self, tmp_path, monkeypatch):
        """root 不是 dict（list）→ exit 2。"""
        _write_dispatch_file(tmp_path, [1, 2, 3])
        rc, out, err = _run(tmp_path, monkeypatch)
        assert rc == 2
        assert "[FAIL]" in err

    def test_dispatches_not_list(self, tmp_path, monkeypatch):
        """dispatches 欄位不是 list → exit 2。"""
        _write_dispatch_file(tmp_path, {"dispatches": "should be list"})
        rc, out, err = _run(tmp_path, monkeypatch)
        assert rc == 2
        assert "[FAIL]" in err
