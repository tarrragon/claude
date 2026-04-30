"""
Tests for process-skip-guard-hook.py — active-dispatch guard

Ticket: 0.18.0-W11-004.3 (IMP-B)

覆蓋 AC：
- AC1 讀取 .claude/dispatch-active.json 判斷 active dispatch
- AC2 dispatches 陣列非空時跳過驗收檢查提醒
- AC3 active/inactive 兩種情況
- AC4 處理 JSON 損毀或檔案不存在的 edge case
"""

import json
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch
import importlib.util

import pytest

# 動態導入 Hook 檔案
hook_path = Path(__file__).parent.parent / "process-skip-guard-hook.py"
spec = importlib.util.spec_from_file_location("process_skip_guard_hook", hook_path)
process_skip_guard_hook = importlib.util.module_from_spec(spec)
sys.path.insert(0, str(Path(__file__).parent.parent))
spec.loader.exec_module(process_skip_guard_hook)

main = process_skip_guard_hook.main
has_active_dispatch = process_skip_guard_hook.has_active_dispatch


def _make_input(prompt: str) -> str:
    return json.dumps({"prompt": prompt})


def _run_main_with_dispatch(input_data: str, mock_has_active: bool):
    """執行 main，mock has_active_dispatch 與其他環境輔助"""
    with patch("sys.stdin", StringIO(input_data)):
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
                with patch.object(process_skip_guard_hook, "setup_hook_logging"):
                    with patch.object(process_skip_guard_hook, "is_subagent_environment", return_value=False):
                        with patch.object(
                            process_skip_guard_hook,
                            "get_active_in_progress_ticket",
                            return_value=None,
                            create=True,
                        ):
                            with patch.object(
                                process_skip_guard_hook,
                                "has_active_dispatch",
                                return_value=mock_has_active,
                            ):
                                exit_code = main()
    return exit_code, mock_stdout.getvalue(), mock_stderr.getvalue()


def _has_reminder(stdout: str, stderr: str) -> bool:
    parsed = json.loads(stdout)
    has_context = "additionalContext" in parsed.get("hookSpecificOutput", {})
    has_stderr = bool(stderr.strip())
    return has_context or has_stderr


# ============================================================================
# AC2 + AC3：active dispatch 時靜音；inactive 時觸發
# ============================================================================

class TestActiveDispatchGuard:
    """主要 AC：dispatches 陣列非空時跳過提醒"""

    def test_active_dispatch_silences_skip_acceptance(self):
        """active dispatch + SKIP_ACCEPTANCE 詞 → 靜音"""
        exit_code, stdout, stderr = _run_main_with_dispatch(
            _make_input("跳過驗收"), mock_has_active=True
        )
        assert exit_code == 0
        assert not _has_reminder(stdout, stderr), \
            "active dispatch 應靜音 SKIP_ACCEPTANCE 提醒"

    def test_active_dispatch_silences_skip_phase4(self):
        """active dispatch + SKIP_PHASE4 詞 → 靜音"""
        exit_code, stdout, stderr = _run_main_with_dispatch(
            _make_input("不需要重構"), mock_has_active=True
        )
        assert exit_code == 0
        assert not _has_reminder(stdout, stderr), \
            "active dispatch 應靜音 SKIP_PHASE4 提醒"

    def test_active_dispatch_silences_skip_agent_dispatch(self):
        """active dispatch + SKIP_AGENT_DISPATCH 詞 → 靜音

        覆蓋所有 skip type，非僅 SA review
        """
        exit_code, stdout, stderr = _run_main_with_dispatch(
            _make_input("我自己做不用代理人"), mock_has_active=True
        )
        assert exit_code == 0
        assert not _has_reminder(stdout, stderr), \
            "active dispatch 應靜音任何 skip 類型"

    def test_inactive_dispatch_triggers_reminder(self):
        """無 active dispatch + skip 詞 → 觸發提醒（原行為）"""
        exit_code, stdout, stderr = _run_main_with_dispatch(
            _make_input("跳過驗收"), mock_has_active=False
        )
        assert exit_code == 0
        assert _has_reminder(stdout, stderr), \
            "無 active dispatch 應維持原行為（觸發提醒）"

    def test_no_skip_intent_does_not_query_dispatch(self):
        """無 skip intent → 不應呼叫 has_active_dispatch（cold path）"""
        call_counter = {"n": 0}

        def _spy(*args, **kwargs):
            call_counter["n"] += 1
            return False

        with patch("sys.stdin", StringIO(_make_input("繼續執行下一個任務"))):
            with patch("sys.stdout", new_callable=StringIO):
                with patch("sys.stderr", new_callable=StringIO):
                    with patch.object(process_skip_guard_hook, "setup_hook_logging"):
                        with patch.object(process_skip_guard_hook, "is_subagent_environment", return_value=False):
                            with patch.object(
                                process_skip_guard_hook,
                                "has_active_dispatch",
                                side_effect=_spy,
                            ):
                                main()

        assert call_counter["n"] == 0, \
            "無 skip intent 不應呼叫 has_active_dispatch（cold path 違規）"


# ============================================================================
# AC1 + AC4：has_active_dispatch helper edge case
# ============================================================================

class TestHasActiveDispatchHelper:
    """has_active_dispatch helper 邊界情況"""

    def test_returns_true_when_dispatches_non_empty(self, tmp_path, monkeypatch):
        """dispatches 陣列含至少一個 entry → True"""
        repo = tmp_path
        (repo / "docs" / "work-logs").mkdir(parents=True)
        claude_dir = repo / ".claude"
        claude_dir.mkdir()
        (claude_dir / "dispatch-active.json").write_text(
            json.dumps({"dispatches": [{"agent_id": "x", "dispatched_at": "2026-01-01T00:00:00Z"}]}),
            encoding="utf-8",
        )
        monkeypatch.setattr(process_skip_guard_hook, "_find_repo_root", lambda: repo)
        assert has_active_dispatch() is True

    def test_returns_false_when_dispatches_empty(self, tmp_path, monkeypatch):
        """dispatches 陣列空 → False"""
        repo = tmp_path
        (repo / "docs" / "work-logs").mkdir(parents=True)
        claude_dir = repo / ".claude"
        claude_dir.mkdir()
        (claude_dir / "dispatch-active.json").write_text(
            json.dumps({"dispatches": []}), encoding="utf-8"
        )
        monkeypatch.setattr(process_skip_guard_hook, "_find_repo_root", lambda: repo)
        assert has_active_dispatch() is False

    def test_returns_false_when_file_missing(self, tmp_path, monkeypatch):
        """dispatch-active.json 不存在 → False"""
        repo = tmp_path
        (repo / "docs" / "work-logs").mkdir(parents=True)
        (repo / ".claude").mkdir()
        monkeypatch.setattr(process_skip_guard_hook, "_find_repo_root", lambda: repo)
        assert has_active_dispatch() is False

    def test_returns_false_when_json_corrupted(self, tmp_path, monkeypatch):
        """JSON 損毀 → False（不阻擋 hook）"""
        repo = tmp_path
        (repo / "docs" / "work-logs").mkdir(parents=True)
        claude_dir = repo / ".claude"
        claude_dir.mkdir()
        (claude_dir / "dispatch-active.json").write_text("{not valid json", encoding="utf-8")
        monkeypatch.setattr(process_skip_guard_hook, "_find_repo_root", lambda: repo)
        assert has_active_dispatch() is False

    def test_returns_false_when_repo_root_not_found(self, monkeypatch):
        """_find_repo_root 回傳 None → False"""
        monkeypatch.setattr(process_skip_guard_hook, "_find_repo_root", lambda: None)
        assert has_active_dispatch() is False

    def test_legacy_bare_list_format_supported(self, tmp_path, monkeypatch):
        """兼容舊格式（裸陣列）"""
        repo = tmp_path
        (repo / "docs" / "work-logs").mkdir(parents=True)
        claude_dir = repo / ".claude"
        claude_dir.mkdir()
        (claude_dir / "dispatch-active.json").write_text(
            json.dumps([{"agent_id": "x"}]), encoding="utf-8"
        )
        monkeypatch.setattr(process_skip_guard_hook, "_find_repo_root", lambda: repo)
        assert has_active_dispatch() is True
