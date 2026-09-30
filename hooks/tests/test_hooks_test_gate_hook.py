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
import time
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
            lambda *a, **k: (
                True,
                "M\0.claude/hooks/tests/test_foo.py\0M\0.claude/hooks/bar-hook.py\0",
            ),
        )
        logger = MagicMock()
        result = hook_module._touched_hook_filenames("git commit -m x", "/repo", logger)
        assert result == {"bar-hook.py"}

    def test_deleted_hook_excluded(self, monkeypatch):
        """已刪除（status D）的 hook 檔不存在，不採計為觸及檔案，避免對
        已刪除路徑誤報「未受測試保護」。"""
        monkeypatch.setattr(
            hook_module,
            "run_git_command",
            lambda *a, **k: (True, "D\0.claude/hooks/removed-hook.py\0"),
        )
        logger = MagicMock()
        result = hook_module._touched_hook_filenames("git commit -m x", "/repo", logger)
        assert result == set()

    def test_renamed_hook_uses_new_path_only(self, monkeypatch):
        """已改名（status R）僅新路徑採計，舊路徑不出現在結果中。"""
        monkeypatch.setattr(
            hook_module,
            "run_git_command",
            lambda *a, **k: (
                True,
                "R100\0.claude/hooks/old-hook.py\0.claude/hooks/new-hook.py\0",
            ),
        )
        logger = MagicMock()
        result = hook_module._touched_hook_filenames("git commit -m x", "/repo", logger)
        assert result == {"new-hook.py"}
        assert "old-hook.py" not in result

    def test_mixed_deleted_and_modified(self, monkeypatch):
        """同一次 commit 混合刪除與修改：僅修改的檔案採計。"""
        monkeypatch.setattr(
            hook_module,
            "run_git_command",
            lambda *a, **k: (
                True,
                "D\0.claude/hooks/removed-hook.py\0M\0.claude/hooks/kept-hook.py\0",
            ),
        )
        logger = MagicMock()
        result = hook_module._touched_hook_filenames("git commit -m x", "/repo", logger)
        assert result == {"kept-hook.py"}

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
            hook_module, "run_git_command", lambda *a, **k: (True, "M\tREADME.md")
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
            lambda *a, **k: (True, "M\0.claude/hooks/foo-hook.py\0"),
        )
        monkeypatch.setattr(
            hook_module,
            "_run_pytest",
            lambda test_paths, hooks_dir, logger, timeout=None: ("pass", "1 passed"),
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
            lambda *a, **k: (True, "M\0.claude/hooks/foo-hook.py\0"),
        )
        monkeypatch.setattr(
            hook_module,
            "_run_pytest",
            lambda test_paths, hooks_dir, logger, timeout=None: ("red", "1 failed"),
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
            lambda *a, **k: (True, "M\0.claude/hooks/untested-hook.py\0"),
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

    def test_commit_deleting_hook_does_not_remind(self, monkeypatch, tmp_path):
        """已刪除的 hook 檔（`git rm` 後 staged 為 D）commit 時，不應觸發
        「未受測試保護」提醒——該 hook 已不存在，無測試對應可言。
        （W3-565 落地時實測誤報：session-registry-stop-hook.py 被 git rm，
        commit 時仍誤報為觸及但無對應測試）"""
        hooks_dir = tmp_path / ".claude" / "hooks"
        tests_dir = hooks_dir / "tests"
        tests_dir.mkdir(parents=True)

        monkeypatch.setattr(hook_module, "get_project_root", lambda: tmp_path)
        monkeypatch.setattr(
            hook_module,
            "run_git_command",
            lambda *a, **k: (True, "D\0.claude/hooks/removed-hook.py\0"),
        )

        exit_code, captured = _run_main(
            monkeypatch,
            {"tool_name": "Bash", "tool_input": {"command": 'git commit -m "remove"'}},
        )
        assert exit_code == 0
        assert captured == []

    # ---- 逐檔執行與逾時語意（E1 / E2） ----

    def _setup_files(self, monkeypatch, tmp_path, names):
        tests_dir = tmp_path / ".claude" / "hooks" / "tests"
        tests_dir.mkdir(parents=True)
        staged = ""
        for n in names:
            (tests_dir / f"test_{n}_hook.py").write_text("def test_x():\n    pass\n")
            staged += f"M\0.claude/hooks/{n}-hook.py\0"
        monkeypatch.setattr(hook_module, "get_project_root", lambda: tmp_path)
        monkeypatch.setattr(hook_module, "run_git_command", lambda *a, **k: (True, staged))

    def _fake_subprocess(self, monkeypatch, per_file_seconds, hang=(), red=()):
        """假 subprocess.run：耗時 = 0.5s * 檔案數（合併呼叫隨檔數線性增長，
        單檔皆快）；檔名含 hang 者永遠卡住，含 red 者 returncode=1。"""
        import subprocess

        def _fake_run(cmd, timeout=None, **kw):
            paths = [c for c in cmd if c.endswith(".py")]
            hangs = any(h in p for p in paths for h in hang)
            duration = 1000 if hangs else per_file_seconds * len(paths)
            if timeout is not None and duration > timeout:
                time.sleep(timeout)
                raise subprocess.TimeoutExpired(cmd, timeout)
            time.sleep(duration)
            rc = 1 if any(r in p for p in paths for r in red) else 0
            return subprocess.CompletedProcess(cmd, rc, stdout="out", stderr="")

        monkeypatch.setattr(hook_module.subprocess, "run", _fake_run)

    def _cmd_input(self):
        return {"tool_name": "Bash", "tool_input": {"command": 'git commit -m "x"'}}

    def test_e1_many_green_files_total_over_single_limit_allowed(
        self, monkeypatch, tmp_path
    ):
        """E1：4 檔各 0.5s 皆綠，合併耗時 2s 超過單一上限 1s。修正前合併執行
        逾時被 deny；逐檔執行後每檔 0.5s < 1s，放行。"""
        self._setup_files(monkeypatch, tmp_path, ["a", "b", "c", "d"])
        self._fake_subprocess(monkeypatch, 0.5)
        # 舊常數（修正前）與新常數同設 1s，使同一測試可在修正前後各跑一次
        monkeypatch.setattr(hook_module, "PYTEST_TIMEOUT", 1.0, raising=False)
        monkeypatch.setattr(hook_module, "PER_FILE_TIMEOUT", 1.0, raising=False)
        monkeypatch.setattr(hook_module, "TOTAL_BUDGET", 30, raising=False)
        exit_code, captured = _run_main(monkeypatch, self._cmd_input())
        assert exit_code == 0
        assert captured == []

    def test_e2_single_file_hang_still_denied(self, monkeypatch, tmp_path):
        """E2 核心：單檔真實卡住，修正前後皆 deny（逾時語意不變，保守方向）。"""
        self._setup_files(monkeypatch, tmp_path, ["a", "stuck"])
        self._fake_subprocess(monkeypatch, 0.1, hang=("stuck",))
        monkeypatch.setattr(hook_module, "PYTEST_TIMEOUT", 1.0, raising=False)
        monkeypatch.setattr(hook_module, "PER_FILE_TIMEOUT", 1.0, raising=False)
        monkeypatch.setattr(hook_module, "TOTAL_BUDGET", 30, raising=False)
        _, captured = _run_main(monkeypatch, self._cmd_input())
        output = json.loads(captured[0])
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_e2_single_file_hang_denied_and_named(self, monkeypatch, tmp_path):
        """E2：單檔真實卡住仍 deny，訊息指名該檔且標示逾時（非紅燈）。"""
        self._setup_files(monkeypatch, tmp_path, ["a", "stuck"])
        self._fake_subprocess(monkeypatch, 0.1, hang=("stuck",))
        monkeypatch.setattr(hook_module, "PYTEST_TIMEOUT", 1.0, raising=False)
        monkeypatch.setattr(hook_module, "PER_FILE_TIMEOUT", 1.0, raising=False)
        monkeypatch.setattr(hook_module, "TOTAL_BUDGET", 30, raising=False)
        exit_code, captured = _run_main(monkeypatch, self._cmd_input())
        assert exit_code == 0
        output = json.loads(captured[0])
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
        reason = output["hookSpecificOutput"]["permissionDecisionReason"]
        assert "stuck-hook.py" in reason
        assert "逾時" in reason
        assert "a-hook.py ->" not in reason  # 綠燈檔不列入

    def test_e2_red_file_denied_and_labeled_red_not_timeout(
        self, monkeypatch, tmp_path
    ):
        """E2：測試紅燈 deny，標示紅燈而非逾時。"""
        self._setup_files(monkeypatch, tmp_path, ["a", "bad"])
        self._fake_subprocess(monkeypatch, 0.1, red=("bad",))
        monkeypatch.setattr(hook_module, "PYTEST_TIMEOUT", 5.0, raising=False)
        monkeypatch.setattr(hook_module, "PER_FILE_TIMEOUT", 5.0, raising=False)
        monkeypatch.setattr(hook_module, "TOTAL_BUDGET", 30, raising=False)
        _, captured = _run_main(monkeypatch, self._cmd_input())
        reason = json.loads(captured[0])["hookSpecificOutput"]["permissionDecisionReason"]
        assert "bad-hook.py" in reason
        assert "紅燈" in reason
        assert "逾時" not in reason.split("測試輸出")[0]

    def test_total_budget_exhausted_denies_unrun_files(self, monkeypatch, tmp_path):
        """總耗時上界：預算耗盡後未執行的檔案保守 deny 並指名，總耗時不超過預算。"""
        self._setup_files(monkeypatch, tmp_path, ["a", "b", "c", "d"])
        self._fake_subprocess(monkeypatch, 0.5)
        monkeypatch.setattr(hook_module, "PER_FILE_TIMEOUT", 5.0, raising=False)
        monkeypatch.setattr(hook_module, "TOTAL_BUDGET", 1.2, raising=False)
        start = time.monotonic()
        _, captured = _run_main(monkeypatch, self._cmd_input())
        elapsed = time.monotonic() - start
        reason = json.loads(captured[0])["hookSpecificOutput"]["permissionDecisionReason"]
        assert "總預算" in reason
        assert "d-hook.py" in reason
        assert elapsed < 1.2 + 1.0  # 預算 + 最後一檔單次誤差

    def test_settings_timeout_exceeds_worst_case(self):
        """settings.json 註冊本 hook 的 timeout（單位：秒）須與常數一致，
        且大於最壞總耗時上界 TOTAL_BUDGET + 5s 開銷，否則平台先殺掉 gate
        （non-blocking）等於放行。"""
        settings = json.loads((HOOKS_DIR.parent / "settings.json").read_text())
        found = []
        for entries in settings["hooks"].values():
            for entry in entries:
                for h in entry.get("hooks", []):
                    if "hooks-test-gate-hook.py" in h.get("command", ""):
                        found.append(h.get("timeout"))
        assert found and all(t is not None for t in found), "須明示 timeout"
        for t in found:
            assert t == hook_module.PLATFORM_TIMEOUT_SECONDS
            assert t > hook_module.TOTAL_BUDGET + 5

    def test_cross_repo_commit_skipped(self, monkeypatch, tmp_path):
        monkeypatch.setattr(hook_module, "get_project_root", lambda: tmp_path)
        called = {"n": 0}

        def _fake_run_git_command(*a, **k):
            called["n"] += 1
            return True, "M\0.claude/hooks/foo-hook.py\0"

        monkeypatch.setattr(hook_module, "run_git_command", _fake_run_git_command)

        command = "git -C /some/other/repo commit -m x"
        exit_code, captured = _run_main(
            monkeypatch, {"tool_name": "Bash", "tool_input": {"command": command}}
        )
        assert exit_code == 0
        assert captured == []
        assert called["n"] == 0  # 跨 repo 時不應執行本專案的 git diff
