"""Tests for agent-commit-verification-hook.py SubagentStop schema (W17-160).

W17-160 修復 SubagentStop event schema 違反：
- 修復前：輸出 hookSpecificOutput.additionalContext（schema 不允許）
- 修復後：有警告時輸出 top-level systemMessage；無內容時靜默退出
- 同 W17-158/W17-159 處置（completes 三例修復鎖鏈）

測試覆蓋：
| 測試 | 場景 | 驗證 |
|------|------|------|
| test_no_input_silent | 無 stdin input | return 0、stdout 無輸出 |
| test_no_agent_id_silent | input 缺 agent_id | return 0、stdout 無輸出 |
| test_uncommitted_emits_top_level_systemMessage | 有未 commit 變更 | top-level systemMessage、無 hookSpecificOutput |
| test_clean_state_silent | 無未 commit、無未合併 | return 0、stdout 無輸出（不輸出空殼） |

策略：
- importlib 動態載入（檔名含 hyphen）
- monkeypatch 取代 git query 函式以隔離真實 repo 狀態
- capsys 捕獲 stdout JSON
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest


HOOK_PATH = (
    Path(__file__).parent.parent / "agent-commit-verification-hook.py"
)


def _load_hook_module():
    spec = importlib.util.spec_from_file_location(
        "agent_commit_verification_hook", HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def hook_mod():
    return _load_hook_module()


def _stdin(payload: dict) -> io.StringIO:
    return io.StringIO(json.dumps(payload))


def _patch_clean(hook_mod, monkeypatch):
    """Patch all git/scan helpers to return empty (clean state)."""
    monkeypatch.setattr(hook_mod, "_lookup_agent_info", lambda *a, **kw: ("agent-X", False))
    monkeypatch.setattr(hook_mod, "get_uncommitted_files", lambda *a, **kw: [])
    monkeypatch.setattr(hook_mod, "get_unmerged_worktrees", lambda *a, **kw: [])
    monkeypatch.setattr(hook_mod, "get_unmerged_feature_branches", lambda *a, **kw: [])
    monkeypatch.setattr(hook_mod, "scan_hook_errors", lambda *a, **kw: [])
    monkeypatch.setattr(hook_mod, "get_project_root", lambda: Path("/tmp"))


class TestAgentCommitVerificationSchema:

    def test_no_input_silent(self, hook_mod, monkeypatch, capsys):
        """無 stdin input 時 SystemExit(0) 且 stdout 無輸出（W17-160：不輸出 hookSpecificOutput 殼）。"""
        monkeypatch.setattr(sys, "stdin", io.StringIO(""))
        with pytest.raises(SystemExit) as exc:
            hook_mod.main()
        assert exc.value.code == 0
        captured = capsys.readouterr()
        assert captured.out == "", "無 input 時不應輸出 hookSpecificOutput 殼"

    def test_no_agent_id_silent(self, hook_mod, monkeypatch, capsys):
        """input 缺 agent_id 時 SystemExit(0) 且 stdout 無輸出。"""
        monkeypatch.setattr(sys, "stdin", _stdin({}))
        with pytest.raises(SystemExit) as exc:
            hook_mod.main()
        assert exc.value.code == 0
        captured = capsys.readouterr()
        assert captured.out == "", "缺 agent_id 時不應輸出 hookSpecificOutput 殼"

    def test_uncommitted_emits_top_level_systemMessage(
        self, hook_mod, monkeypatch, capsys
    ):
        """有未 commit 變更時，輸出必須為 top-level systemMessage，禁止 hookSpecificOutput.additionalContext。"""
        _patch_clean(hook_mod, monkeypatch)
        monkeypatch.setattr(
            hook_mod,
            "get_uncommitted_files",
            lambda *a, **kw: ["src/foo.py", "src/bar.py"],
        )
        monkeypatch.setattr(sys, "stdin", _stdin({"agent_id": "agent-xyz"}))

        with pytest.raises(SystemExit) as exc:
            hook_mod.main()
        assert exc.value.code == 0

        captured = capsys.readouterr()
        assert captured.out.strip(), "有警告時 main() 應輸出 JSON"
        payload = json.loads(captured.out)

        assert "systemMessage" in payload, (
            "SubagentStop event 必須使用 top-level systemMessage（W17-160）"
        )
        assert "hookSpecificOutput" not in payload, (
            "SubagentStop schema 不允許 hookSpecificOutput.additionalContext（W17-160）"
        )
        assert isinstance(payload["systemMessage"], str)
        assert payload["systemMessage"], "systemMessage 不應為空字串"

    def test_clean_state_silent(self, hook_mod, monkeypatch, capsys):
        """無未 commit、無未合併、無 hook error 時 stdout 應靜默（W17-160：不輸出空殼）。"""
        _patch_clean(hook_mod, monkeypatch)
        monkeypatch.setattr(sys, "stdin", _stdin({"agent_id": "agent-xyz"}))

        with pytest.raises(SystemExit) as exc:
            hook_mod.main()
        assert exc.value.code == 0

        captured = capsys.readouterr()
        assert captured.out == "", "clean state 不應輸出 hookSpecificOutput 殼"
