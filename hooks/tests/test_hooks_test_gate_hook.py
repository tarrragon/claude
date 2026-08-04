"""
Test: hooks-test-gate-hook（0.2.1-W3-189）

驗證項目：
1. _fast_reject: 便宜前置判斷（不含 'commit' 字樣立即短路）
2. _candidate_tests: 命名慣例對應規則
3. _touched_hook_filenames: staged + 命令字面推導兩來源聯集
4. main() 整合行為：
   - 非 Bash 工具 / 無輸入 → 允許
   - 不含 commit 字樣 → 允許（fast-path）
   - commit 但未觸及 .claude/hooks/*.py → 允許
   - commit 觸及有對應測試的 hook 檔，測試綠燈 → 允許
   - commit 觸及有對應測試的 hook 檔，測試紅燈 → deny，訊息含邊界說明
   - commit 觸及無對應測試的 hook 檔 → additional_context 提醒（不阻擋）
   - git add x.py && git commit 串接情境 → 仍能推導出觸及檔案

Source: ticket 0.2.1-W3-189（source ANA 0.2.1-W3-188）
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent))

_spec = importlib.util.spec_from_file_location(
    "hooks_test_gate_hook", HOOKS_DIR / "hooks-test-gate-hook.py"
)
hook_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook_module)


def _run_main(monkeypatch, input_data: dict) -> "tuple[int, list]":
    """執行 main()，攔截 stdout 上的 emit_hook_output JSON 輸出。"""
    stdin = io.StringIO(json.dumps(input_data))
    monkeypatch.setattr(sys, "stdin", stdin)
    captured = []

    def _fake_print(*args, **kwargs):
        captured.append(args[0] if args else "")

    with patch("builtins.print", side_effect=_fake_print):
        exit_code = hook_module.main()
    return exit_code, captured


class TestFastReject:
    def test_empty_command_rejected(self):
        assert hook_module._fast_reject("") is True

    def test_command_without_commit_word_rejected(self):
        assert hook_module._fast_reject("flutter test") is True
        assert hook_module._fast_reject("ls -la") is True

    def test_command_with_commit_word_not_rejected(self):
        assert hook_module._fast_reject('git commit -m "msg"') is False


class TestCandidateTests:
    def test_naming_convention(self):
        candidates = hook_module._candidate_tests("uv-tool-ownership-guard-hook.py")
        assert candidates == {
            "test_uv_tool_ownership_guard_hook.py",
            "test_uv_tool_ownership_guard.py",
        }


class TestTouchedHookFilenames:
    def test_from_command_literal_path(self, monkeypatch):
        # git diff --cached 回傳空（尚未實際 add），但同指令含 add pathspec
        monkeypatch.setattr(
            hook_module,
            "run_git_command",
            lambda *a, **k: (True, ""),
        )
        logger = MagicMock()
        command = "git add .claude/hooks/foo-hook.py && git commit -m x"
        result = hook_module._touched_hook_filenames(command, "/repo", logger)
        assert "foo-hook.py" in result

    def test_excludes_nested_paths(self, monkeypatch):
        monkeypatch.setattr(
            hook_module,
            "run_git_command",
            lambda *a, **k: (True, ".claude/hooks/tests/test_foo.py\n.claude/hooks/bar-hook.py"),
        )
        logger = MagicMock()
        result = hook_module._touched_hook_filenames("git commit -m x", "/repo", logger)
        assert result == {"bar-hook.py"}

    def test_literal_path_ignored_outside_add_or_pathspec_position(self, monkeypatch):
        """0.2.1-W3-191 acceptance 3：字面提及來源限定於 git add 或 commit
        pathspec 的參數位置，非命令任意位置（如 echo 字面）。"""
        monkeypatch.setattr(
            hook_module, "run_git_command", lambda *a, **k: (True, "")
        )
        logger = MagicMock()
        command = 'echo ".claude/hooks/foo-hook.py" && git commit -m x'
        result = hook_module._touched_hook_filenames(command, "/repo", logger)
        assert result == set()

    def test_literal_path_ignored_in_piped_json_payload(self, monkeypatch):
        """0.2.1-W3-191 acceptance 1：命令字面提及 hook 路徑但非 git add／
        commit pathspec 參數位置（此處是被管線呼叫的執行對象），不採計。"""
        monkeypatch.setattr(
            hook_module, "run_git_command", lambda *a, **k: (True, "")
        )
        logger = MagicMock()
        command = (
            'echo \'{"command":"git commit -m \\"test\\""}\''
            " | .claude/hooks/hooks-test-gate-hook.py"
        )
        result = hook_module._touched_hook_filenames(command, "/repo", logger)
        assert result == set()


class TestMainIntegration:
    def test_non_bash_tool_allows(self, monkeypatch):
        exit_code, captured = _run_main(
            monkeypatch, {"tool_name": "Edit", "tool_input": {}}
        )
        assert exit_code == 0
        assert captured == []

    def test_no_commit_word_allows_without_git_diff(self, monkeypatch):
        called = {"n": 0}

        def _fake_run_git_command(*a, **k):
            called["n"] += 1
            return True, ""

        monkeypatch.setattr(hook_module, "run_git_command", _fake_run_git_command)
        exit_code, captured = _run_main(
            monkeypatch,
            {"tool_name": "Bash", "tool_input": {"command": "flutter test"}},
        )
        assert exit_code == 0
        assert captured == []
        assert called["n"] == 0  # 零開銷：未執行 git diff --cached

    def test_commit_without_touching_hooks_allows(self, monkeypatch):
        monkeypatch.setattr(
            hook_module, "run_git_command", lambda *a, **k: (True, "README.md")
        )
        exit_code, captured = _run_main(
            monkeypatch,
            {
                "tool_name": "Bash",
                "tool_input": {"command": 'git commit -m "docs"'},
            },
        )
        assert exit_code == 0
        assert captured == []

    def test_commit_touching_hook_with_passing_test_allows(self, monkeypatch, tmp_path):
        hooks_dir = tmp_path / ".claude" / "hooks"
        tests_dir = hooks_dir / "tests"
        tests_dir.mkdir(parents=True)
        (tests_dir / "test_foo_hook.py").write_text("def test_x():\n    assert True\n")

        monkeypatch.setattr(hook_module, "get_project_root", lambda: tmp_path)
        monkeypatch.setattr(
            hook_module,
            "run_git_command",
            lambda *a, **k: (True, ".claude/hooks/foo-hook.py"),
        )
        monkeypatch.setattr(
            hook_module, "_run_pytest", lambda test_paths, hooks_dir, logger: (True, "1 passed")
        )

        exit_code, captured = _run_main(
            monkeypatch,
            {"tool_name": "Bash", "tool_input": {"command": 'git commit -m "x"'}},
        )
        assert exit_code == 0
        assert captured == []

    def test_commit_touching_hook_with_failing_test_denies(self, monkeypatch, tmp_path):
        hooks_dir = tmp_path / ".claude" / "hooks"
        tests_dir = hooks_dir / "tests"
        tests_dir.mkdir(parents=True)
        (tests_dir / "test_foo_hook.py").write_text("def test_x():\n    assert False\n")

        monkeypatch.setattr(hook_module, "get_project_root", lambda: tmp_path)
        monkeypatch.setattr(
            hook_module,
            "run_git_command",
            lambda *a, **k: (True, ".claude/hooks/foo-hook.py"),
        )
        monkeypatch.setattr(
            hook_module,
            "_run_pytest",
            lambda test_paths, hooks_dir, logger: (False, "1 failed"),
        )

        exit_code, captured = _run_main(
            monkeypatch,
            {"tool_name": "Bash", "tool_input": {"command": 'git commit -m "x"'}},
        )
        assert exit_code == 0
        assert len(captured) == 1
        output = json.loads(captured[0])
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
        reason = output["hookSpecificOutput"]["permissionDecisionReason"]
        assert "foo-hook.py" in reason
        assert "範疇邊界" in reason
        assert "跨檔破壞" in reason

    def test_commit_touching_hook_without_test_reminds(self, monkeypatch, tmp_path):
        hooks_dir = tmp_path / ".claude" / "hooks"
        tests_dir = hooks_dir / "tests"
        tests_dir.mkdir(parents=True)

        monkeypatch.setattr(hook_module, "get_project_root", lambda: tmp_path)
        monkeypatch.setattr(
            hook_module,
            "run_git_command",
            lambda *a, **k: (True, ".claude/hooks/untested-hook.py"),
        )

        exit_code, captured = _run_main(
            monkeypatch,
            {"tool_name": "Bash", "tool_input": {"command": 'git commit -m "x"'}},
        )
        assert exit_code == 0
        assert len(captured) == 1
        output = json.loads(captured[0])
        assert "permissionDecision" not in output["hookSpecificOutput"]
        context = output["hookSpecificOutput"]["additionalContext"]
        assert "untested-hook.py" in context
        assert "未受測試保護" in context

    def test_add_and_commit_chain_detected(self, monkeypatch, tmp_path):
        """0.2.1-W3-154 同類串接情境：add && commit 時，diff --cached 尚為空，
        須從命令字串本身推導出觸及的 hook 檔。"""
        hooks_dir = tmp_path / ".claude" / "hooks"
        tests_dir = hooks_dir / "tests"
        tests_dir.mkdir(parents=True)
        (tests_dir / "test_chained_hook.py").write_text("def test_x():\n    assert False\n")

        monkeypatch.setattr(hook_module, "get_project_root", lambda: tmp_path)
        monkeypatch.setattr(hook_module, "run_git_command", lambda *a, **k: (True, ""))

        command = "git add .claude/hooks/chained-hook.py && git commit -m x"
        exit_code, captured = _run_main(
            monkeypatch, {"tool_name": "Bash", "tool_input": {"command": command}}
        )
        assert exit_code == 0
        assert len(captured) == 1
        output = json.loads(captured[0])
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_diagnostic_command_with_embedded_json_not_falsely_triggered(
        self, monkeypatch
    ):
        """0.2.1-W3-191 acceptance 1：PM 驗收 W3-189 時實測誤觸發的診斷命令
        形式——命令含 hook 路徑字面與 `git commit` 字樣，但本身不是 commit，
        不應觸發 gate（含不應付出 git diff --cached 的額外開銷）。"""
        called = {"n": 0}

        def _fake_run_git_command(*a, **k):
            called["n"] += 1
            return True, ""

        monkeypatch.setattr(hook_module, "run_git_command", _fake_run_git_command)
        command = (
            'echo \'{"hook_event_name":"PreToolUse","command":"git commit -m '
            '\\"test\\""}\' | .claude/hooks/hooks-test-gate-hook.py'
        )
        exit_code, captured = _run_main(
            monkeypatch, {"tool_name": "Bash", "tool_input": {"command": command}}
        )
        assert exit_code == 0
        assert captured == []
        assert called["n"] == 0  # 未真正判定為 commit，未執行 git diff

    def test_cross_repo_commit_skipped(self, monkeypatch, tmp_path):
        monkeypatch.setattr(hook_module, "get_project_root", lambda: tmp_path)
        called = {"n": 0}

        def _fake_run_git_command(*a, **k):
            called["n"] += 1
            return True, ".claude/hooks/foo-hook.py"

        monkeypatch.setattr(hook_module, "run_git_command", _fake_run_git_command)

        command = "git -C /some/other/repo commit -m x"
        exit_code, captured = _run_main(
            monkeypatch, {"tool_name": "Bash", "tool_input": {"command": command}}
        )
        assert exit_code == 0
        assert captured == []
        assert called["n"] == 0  # 跨 repo 時不應執行本專案的 git diff
