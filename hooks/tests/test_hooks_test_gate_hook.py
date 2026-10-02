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

    def test_uv_launch_failure_denies(self, monkeypatch, tmp_path):
        """E2 正向對照：uv 啟動失敗（OSError）須判 red 並 deny，不可放行。"""
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

        def _raise(*a, **k):
            raise FileNotFoundError(2, "No such file or directory: 'uv'")

        monkeypatch.setattr(hook_module.subprocess, "run", _raise)

        exit_code, captured = _run_main(
            monkeypatch,
            {"tool_name": "Bash", "tool_input": {"command": 'git commit -m "x"'}},
        )
        assert exit_code == 0
        assert len(captured) == 1
        output = json.loads(captured[0])
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "foo-hook.py" in output["hookSpecificOutput"]["permissionDecisionReason"]

    def _raise_fnf(self, monkeypatch):
        def _raise(*a, **k):
            raise FileNotFoundError(2, "No such file or directory: 'uv'")

        monkeypatch.setattr(hook_module.subprocess, "run", _raise)

    def test_uv_launch_failure_stderr_visible(self, monkeypatch, tmp_path, capsys):
        """規則 4：uv 啟動失敗須在 stderr 輸出錯誤類型與命令。"""
        import logging

        self._raise_fnf(monkeypatch)
        status, tail = hook_module._run_pytest(
            [tmp_path / "t.py"], tmp_path, logging.getLogger("t-stderr")
        )
        err = capsys.readouterr().err
        assert status == "red"
        assert "FileNotFoundError" in err
        assert "uv" in err and "pytest" in err

    def test_uv_launch_failure_written_to_log_file(self, monkeypatch, tmp_path):
        """uv 啟動失敗須寫入日誌檔，含錯誤類型與訊息。"""
        import logging

        self._raise_fnf(monkeypatch)
        log_file = tmp_path / "gate.log"
        handler = logging.FileHandler(log_file, encoding="utf-8")
        lg = logging.getLogger("t-logfile")
        lg.addHandler(handler)
        lg.setLevel(logging.DEBUG)
        try:
            hook_module._run_pytest([tmp_path / "t.py"], tmp_path, lg)
        finally:
            handler.close()
            lg.removeHandler(handler)
        text = log_file.read_text(encoding="utf-8")
        assert "FileNotFoundError" in text
        assert "No such file or directory" in text

    # ---- 0.4.1-W1-035.2：每檔分段計時日誌（只加日誌，不改判定）----

    def _capture_logger(self, name):
        import logging

        records = []

        class _H(logging.Handler):
            def emit(self, record):
                records.append(record)

        lg = logging.getLogger(name)
        lg.handlers = [_H()]
        lg.setLevel(logging.DEBUG)
        lg.propagate = False
        return lg, records

    def _fake_run(self, monkeypatch, returncode, stdout, delay=0.05):
        import subprocess as sp

        def _run(cmd, **kw):
            time.sleep(delay)
            return sp.CompletedProcess(cmd, returncode, stdout=stdout, stderr="")

        monkeypatch.setattr(hook_module.subprocess, "run", _run)

    @staticmethod
    def _timing_records(records):
        return [r for r in records if "分段計時" in r.getMessage()]

    @pytest.mark.parametrize(
        "returncode,stdout,expected",
        [
            (0, "1 passed in 0.01s\n", "pass"),
            (1, "1 failed in 0.01s\n", "red"),
        ],
    )
    def test_segment_timing_logged_pass_red(
        self, monkeypatch, tmp_path, returncode, stdout, expected
    ):
        """E2 對照：pass／red 路徑記錄分段欄位，判定與修正前相同。"""
        self._fake_run(monkeypatch, returncode, stdout)
        lg, records = self._capture_logger("t-seg-%s" % expected)
        status, _ = hook_module._run_pytest([tmp_path / "test_a.py"], tmp_path, lg)
        assert status == expected
        recs = self._timing_records(records)
        assert len(recs) == 1
        msg = recs[0].getMessage()
        for field in ("test_a.py", "total=", "pytest_self_reported=",
                      "uv_and_startup_gap=", "load1="):
            assert field in msg
        import re

        total = float(re.search(r"total=(\d+\.\d+)s", msg).group(1))
        assert 0.04 <= total < 5  # fake run 睡 0.05s
        assert "pytest_self_reported=0.01s" in msg
        assert recs[0].levelname == "INFO"

    def test_segment_timing_logged_timeout(self, monkeypatch, tmp_path):
        """E2 對照：timeout 路徑記錄 total，pytest 自報不可得，判定仍為 timeout。"""
        import subprocess as sp

        def _run(cmd, **kw):
            raise sp.TimeoutExpired(cmd, 1)

        monkeypatch.setattr(hook_module.subprocess, "run", _run)
        lg, records = self._capture_logger("t-seg-timeout")
        status, _ = hook_module._run_pytest([tmp_path / "test_a.py"], tmp_path, lg, 1)
        assert status == "timeout"
        recs = self._timing_records(records)
        assert len(recs) == 1
        msg = recs[0].getMessage()
        assert "total=" in msg and "status=timeout" in msg
        assert "pytest_self_reported=n/a" in msg

    def test_segment_parse_failure_warns_without_changing_verdict(
        self, monkeypatch, tmp_path
    ):
        """分段解析失敗（無摘要行）只記 warning，判定不變。"""
        self._fake_run(monkeypatch, 0, "no summary here\n")
        lg, records = self._capture_logger("t-seg-parsefail")
        status, _ = hook_module._run_pytest([tmp_path / "test_a.py"], tmp_path, lg)
        assert status == "pass"
        warns = [r for r in records if r.levelname == "WARNING"]
        assert any("分段" in r.getMessage() for r in warns)
        assert not [r for r in records if r.levelname in ("ERROR", "CRITICAL")]

    # ---- 0.4.1-W1-035.4：細化分段計時（四段 + 兩次 load1）----

    def _fake_run_with_timing(self, monkeypatch, marks, returncode=0,
                              stdout="1 passed in 0.01s\n"):
        """假 subprocess.run：依 env 計時檔路徑寫入 marks（相對 spawn 的秒偏移）。"""
        import subprocess as sp

        def _run(cmd, **kw):
            path = kw["env"][hook_module.TIMING_ENV]
            now = time.time()
            payload = {k: (now + v if k in ("configure", "unconfigure", "atexit") else v)
                       for k, v in marks.items()}
            Path(path).write_text(json.dumps(payload), encoding="utf-8")
            time.sleep(0.05)
            return sp.CompletedProcess(cmd, returncode, stdout=stdout, stderr="")

        monkeypatch.setattr(hook_module.subprocess, "run", _run)

    _FULL_MARKS = {"configure": 0.01, "unconfigure": 0.03, "atexit": 0.04,
                   "load1_start": 1.5, "load1_end": 2.25}

    def test_segments_logged_sum_equals_total(self, monkeypatch, tmp_path):
        self._fake_run_with_timing(monkeypatch, self._FULL_MARKS)
        lg, records = self._capture_logger("t-seg4-sum")
        status, _ = hook_module._run_pytest([tmp_path / "test_a.py"], tmp_path, lg)
        assert status == "pass"
        msg = self._timing_records(records)[0].getMessage()
        import re

        def _f(name):
            return float(re.search(name + r"=(-?\d+\.\d+)s", msg).group(1))

        parts = [_f(n) for n in ("spawn_to_configure", "configure_to_summary",
                                 "summary_to_pyexit", "pyexit_to_uvexit")]
        assert all(p >= 0 for p in parts)
        assert abs(sum(parts) - _f("total")) < 0.05  # 牆鐘 vs monotonic 差
        assert abs(_f("segment_sum") - sum(parts)) < 0.011  # 各段四捨五入
        assert abs(_f("sum_residual")) < 0.05
        assert "load1_start=1.50" in msg and "load1_end=2.25" in msg

    def test_timing_file_missing_warns_verdict_unchanged(self, monkeypatch, tmp_path):
        """E2：外掛沒寫時刻檔（外掛失敗）只記 warning，細分 n/a，判定不變。"""
        self._fake_run(monkeypatch, 0, "1 passed in 0.01s\n")
        lg, records = self._capture_logger("t-seg4-missing")
        status, _ = hook_module._run_pytest([tmp_path / "test_a.py"], tmp_path, lg)
        assert status == "pass"
        msg = self._timing_records(records)[0].getMessage()
        assert "spawn_to_configure=n/a" in msg and "load1_start=n/a" in msg
        assert any(r.levelname == "WARNING" and "計時檔" in r.getMessage()
                   for r in records)
        assert not [r for r in records if r.levelname in ("ERROR", "CRITICAL")]

    def test_timing_file_corrupt_warns_verdict_unchanged(self, monkeypatch, tmp_path):
        import subprocess as sp

        def _run(cmd, **kw):
            Path(kw["env"][hook_module.TIMING_ENV]).write_text("{not json", encoding="utf-8")
            return sp.CompletedProcess(cmd, 1, stdout="1 failed in 0.01s\n", stderr="")

        monkeypatch.setattr(hook_module.subprocess, "run", _run)
        lg, records = self._capture_logger("t-seg4-corrupt")
        status, _ = hook_module._run_pytest([tmp_path / "test_a.py"], tmp_path, lg)
        assert status == "red"
        assert any("計時檔" in r.getMessage() for r in records if r.levelname == "WARNING")

    def test_timeout_path_reads_partial_marks_verdict_unchanged(self, monkeypatch, tmp_path):
        import subprocess as sp

        def _run(cmd, **kw):
            Path(kw["env"][hook_module.TIMING_ENV]).write_text(
                json.dumps({"configure": time.time(), "load1_start": 3.0}), encoding="utf-8")
            raise sp.TimeoutExpired(cmd, 1)

        monkeypatch.setattr(hook_module.subprocess, "run", _run)
        lg, records = self._capture_logger("t-seg4-timeout")
        status, _ = hook_module._run_pytest([tmp_path / "test_a.py"], tmp_path, lg, 1)
        assert status == "timeout"
        msg = self._timing_records(records)[0].getMessage()
        assert "load1_start=3.00" in msg and "summary_to_pyexit=n/a" in msg

    def test_timing_file_cleaned_up(self, monkeypatch, tmp_path):
        seen = []
        import subprocess as sp

        def _run(cmd, **kw):
            seen.append(kw["env"][hook_module.TIMING_ENV])
            return sp.CompletedProcess(cmd, 0, stdout="1 passed in 0.01s\n", stderr="")

        monkeypatch.setattr(hook_module.subprocess, "run", _run)
        lg, _ = self._capture_logger("t-seg4-clean")
        hook_module._run_pytest([tmp_path / "test_a.py"], tmp_path, lg)
        assert seen and not Path(seen[0]).exists()

    # ---- conftest 計時外掛：E1 傳與不傳對照 + 真實 pytest 子程序 liveness ----

    @staticmethod
    def _load_conftest(monkeypatch, env_value):
        if env_value is None:
            monkeypatch.delenv("HOOKS_TEST_GATE_TIMING_FILE", raising=False)
        else:
            monkeypatch.setenv("HOOKS_TEST_GATE_TIMING_FILE", env_value)
        spec = importlib.util.spec_from_file_location(
            "conftest_probe", Path(__file__).parent.parent / "conftest.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_plugin_not_loaded_without_env(self, monkeypatch):
        mod = self._load_conftest(monkeypatch, None)
        assert not hasattr(mod, "pytest_configure")
        assert not hasattr(mod, "pytest_unconfigure")

    def test_plugin_loaded_with_env(self, monkeypatch, tmp_path):
        mod = self._load_conftest(monkeypatch, str(tmp_path / "t.json"))
        assert callable(mod.pytest_configure) and callable(mod.pytest_unconfigure)

    def test_plugin_write_failure_only_stderr(self, monkeypatch, tmp_path, capsys):
        mod = self._load_conftest(monkeypatch, str(tmp_path / "no_dir" / "t.json"))
        mod.pytest_unconfigure(None)  # 不得拋例外
        assert "gate-timing-plugin" in capsys.readouterr().err

    # 真實子程序測試以 wallclock 標記移出預設主套件（pyproject addopts 排除）：
    # 逾時上界是機器負載的函數，紅燈不一定反映程式缺陷。執行：uv run pytest -m wallclock
    # 逾時時直接判紅（不 skip），子程序卡死與計時外掛失效因此仍可被獨立套件偵測。
    REAL_PYTEST_TIMEOUT_SEC = 120

    @staticmethod
    def _run_child(cmd, env, cwd, timeout):
        """seam：以 timeout 執行子程序；逾時拋 TimeoutExpired（由測試判紅）。"""
        import subprocess as sp

        return sp.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)

    @pytest.mark.wallclock
    def test_real_pytest_subprocess_writes_ordered_marks(self, tmp_path):
        import os

        out = tmp_path / "marks.json"
        hooks_dir = Path(__file__).parent.parent
        env = dict(os.environ, HOOKS_TEST_GATE_TIMING_FILE=str(out))
        r = self._run_child(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
             "tests/test_hooks_test_gate_hook.py::TestFastReject::test_empty_command_rejected"],
            env, str(hooks_dir), self.REAL_PYTEST_TIMEOUT_SEC,
        )
        assert r.returncode == 0, r.stdout + r.stderr
        marks = json.loads(out.read_text(encoding="utf-8"))
        assert marks["configure"] <= marks["unconfigure"] <= marks["atexit"]
        assert isinstance(marks["load1_start"], float) and isinstance(marks["load1_end"], float)

    @pytest.mark.wallclock
    def test_real_pytest_hung_child_is_red_not_skipped(self, tmp_path):
        """E2 正向對照：永不結束的子程序必須以 TimeoutExpired 判紅，不得被吞成 skip/pass。"""
        import os
        import subprocess as sp

        hang = [sys.executable, "-c", "import time; time.sleep(3600)"]
        try:
            with pytest.raises(sp.TimeoutExpired):
                self._run_child(hang, dict(os.environ), str(tmp_path), 2)
        except pytest.skip.Exception:
            pytest.fail("逾時被轉成 skip：卡死子程序與放行同形")

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

    def _budget_exhausted_setup(self, monkeypatch, tmp_path, names, red=()):
        """假時鐘：每次 pytest 呼叫推進 10s、總預算 20s：前兩檔跑完後剩餘 0，
        其餘預算耗盡未執行。不實際睡眠，結果與機器負載無關。"""
        import subprocess
        import types

        self._setup_files(monkeypatch, tmp_path, names)
        clock = {"t": 0.0}

        def _fake_run(cmd, timeout=None, **kw):
            clock["t"] += 10.0
            paths = [c for c in cmd if c.endswith(".py")]
            rc = 1 if any(r in p for p in paths for r in red) else 0
            return subprocess.CompletedProcess(cmd, rc, stdout="out", stderr="")

        monkeypatch.setattr(hook_module.subprocess, "run", _fake_run)
        monkeypatch.setattr(
            hook_module, "time", types.SimpleNamespace(monotonic=lambda: clock["t"])
        )
        monkeypatch.setattr(hook_module, "PER_FILE_TIMEOUT", 60.0, raising=False)
        monkeypatch.setattr(hook_module, "TOTAL_BUDGET", 20.0, raising=False)

    def test_e1_budget_exhausted_all_green_allowed_with_reminder(
        self, monkeypatch, tmp_path
    ):
        """E1：預算耗盡、已執行檔全綠 -> 放行（非 deny），additional_context
        指名未驗證檔並附可直接複製的補跑指令。"""
        self._budget_exhausted_setup(monkeypatch, tmp_path, ["a", "b", "c", "d"])
        exit_code, captured = _run_main(monkeypatch, self._cmd_input())
        assert exit_code == 0
        assert len(captured) == 1
        specific = json.loads(captured[0])["hookSpecificOutput"]
        assert specific.get("permissionDecision") != "deny"
        ctx = specific["additionalContext"]
        assert "d-hook.py" in ctx and "test_d_hook.py" in ctx
        assert "總預算" in ctx
        assert "uv run --directory .claude/hooks pytest" in ctx
        assert "a-hook.py" not in ctx  # 已驗證檔不列入

    def test_e2_red_file_with_unverified_denied_and_lists_unverified(
        self, monkeypatch, tmp_path
    ):
        """E2：已執行檔含紅燈且另有未驗證檔 -> deny，訊息含未驗證清單。"""
        self._budget_exhausted_setup(
            monkeypatch, tmp_path, ["a", "b", "c", "d"], red=("a",)
        )
        _, captured = _run_main(monkeypatch, self._cmd_input())
        specific = json.loads(captured[0])["hookSpecificOutput"]
        assert specific["permissionDecision"] == "deny"
        reason = specific["permissionDecisionReason"]
        assert "a-hook.py" in reason and "紅燈" in reason
        assert "d-hook.py" in reason and "未驗證" in reason
        assert "uv run --directory .claude/hooks pytest" in reason

    def test_unverified_and_untested_reminders_coexist(self, monkeypatch, tmp_path):
        """未驗證與無對應測試並存：兩類提醒都出現，不互相覆蓋。"""
        self._budget_exhausted_setup(monkeypatch, tmp_path, ["a", "b", "c", "d"])
        staged = "".join(f"M\0.claude/hooks/{n}-hook.py\0" for n in "abcd")
        staged += "M\0.claude/hooks/orphan-hook.py\0"
        monkeypatch.setattr(hook_module, "run_git_command", lambda *a, **k: (True, staged))
        _, captured = _run_main(monkeypatch, self._cmd_input())
        assert len(captured) == 1
        ctx = json.loads(captured[0])["hookSpecificOutput"]["additionalContext"]
        assert "d-hook.py" in ctx and "總預算" in ctx
        assert "orphan-hook.py" in ctx and "未受測試保護" in ctx

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


class TestVerificationStageFailClosed:
    """驗證階段（確認觸及 hook 檔之後）拋例外須 deny；偵測階段維持 fail-open。"""

    def _setup(self, monkeypatch, tmp_path):
        tests_dir = tmp_path / ".claude" / "hooks" / "tests"
        tests_dir.mkdir(parents=True)
        (tests_dir / "test_foo_hook.py").write_text("def test_x():\n    assert True\n")
        monkeypatch.setattr(hook_module, "get_project_root", lambda: tmp_path)
        monkeypatch.setattr(
            hook_module,
            "run_git_command",
            lambda *a, **k: (True, "M\0.claude/hooks/foo-hook.py\0"),
        )

    @staticmethod
    def _commit_input():
        return {"tool_name": "Bash", "tool_input": {"command": 'git commit -m "x"'}}

    @staticmethod
    def _decisions(captured):
        """logger.critical 的 traceback 亦經 print 進入 captured；只取 hook 輸出 JSON。"""
        out = []
        for item in captured:
            try:
                parsed = json.loads(item)
            except (TypeError, ValueError):
                continue
            if isinstance(parsed, dict) and "hookSpecificOutput" in parsed:
                out.append(item)
        return out

    @staticmethod
    def _boom(*a, **k):
        raise RuntimeError("injected failure")

    def test_e1_injected_exception_denies_while_baseline_allows(
        self, monkeypatch, tmp_path
    ):
        """E1 對照：同一 fixture，注入例外 -> deny；不注入（綠燈）-> 無輸出。"""
        self._setup(monkeypatch, tmp_path)
        monkeypatch.setattr(
            hook_module,
            "_run_pytest",
            lambda test_paths, hooks_dir, logger, timeout=None: ("pass", "1 passed"),
        )
        base_code, base_out = _run_main(monkeypatch, self._commit_input())

        monkeypatch.setattr(hook_module, "_resolve_test_paths", self._boom)
        inj_code, inj_raw = _run_main(monkeypatch, self._commit_input())
        inj_out = self._decisions(inj_raw)

        assert base_code == 0 and base_out == []
        assert inj_code == 0 and len(inj_out) == 1
        assert inj_out != base_out
        specific = json.loads(inj_out[0])["hookSpecificOutput"]
        assert specific["permissionDecision"] == "deny"
        reason = specific["permissionDecisionReason"]
        assert "RuntimeError" in reason and "injected failure" in reason
        assert "無法驗證等同未通過" in reason
        assert "終端機" in reason

    @pytest.mark.parametrize(
        "target", ["_resolve_test_paths", "_run_all_tests", "_build_deny_message"]
    )
    def test_e2_verification_stage_exception_always_denies(
        self, monkeypatch, tmp_path, target
    ):
        """E2 正向對照：驗證階段各函式拋例外必定 deny。"""
        self._setup(monkeypatch, tmp_path)
        monkeypatch.setattr(
            hook_module,
            "_run_pytest",
            lambda test_paths, hooks_dir, logger, timeout=None: ("red", "1 failed"),
        )
        monkeypatch.setattr(hook_module, target, self._boom)
        exit_code, raw = _run_main(monkeypatch, self._commit_input())
        captured = self._decisions(raw)
        assert exit_code == 0 and len(captured) == 1
        specific = json.loads(captured[0])["hookSpecificOutput"]
        assert specific["permissionDecision"] == "deny"
        assert "RuntimeError" in specific["permissionDecisionReason"]

    def test_e2_timing_log_exception_with_green_tests_still_allows(
        self, monkeypatch, tmp_path, capsys
    ):
        """E2：計時日誌拋例外但測試綠燈 -> 放行（exit 0、無 deny），並於 stderr 可見。"""
        import subprocess

        self._setup(monkeypatch, tmp_path)
        monkeypatch.setattr(
            hook_module.subprocess,
            "run",
            lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr=""),
        )
        monkeypatch.setattr(hook_module, "_log_segment_timing", self._boom)
        exit_code, captured = _run_main(monkeypatch, self._commit_input())
        assert exit_code == 0
        assert captured == []
        assert "injected failure" in capsys.readouterr().err

    @pytest.mark.parametrize(
        "command",
        [
            "flutter test",
            "git status && echo commit",
            "git -C /some/other/repo commit -m x",
        ],
    )
    def test_detection_stage_payloads_exit_zero_with_empty_stdout(
        self, monkeypatch, tmp_path, command
    ):
        self._setup(monkeypatch, tmp_path)
        monkeypatch.setattr(hook_module, "_resolve_test_paths", self._boom)
        exit_code, captured = _run_main(
            monkeypatch, {"tool_name": "Bash", "tool_input": {"command": command}}
        )
        assert exit_code == 0
        assert captured == []

    def test_detection_stage_no_hook_touched_exit_zero_with_empty_stdout(
        self, monkeypatch, tmp_path
    ):
        self._setup(monkeypatch, tmp_path)
        monkeypatch.setattr(
            hook_module, "run_git_command", lambda *a, **k: (True, "M\0README.md\0")
        )
        monkeypatch.setattr(hook_module, "_resolve_test_paths", self._boom)
        exit_code, captured = _run_main(monkeypatch, self._commit_input())
        assert exit_code == 0
        assert captured == []


class TestGitDiffFailureVisible:
    """git diff --cached 失敗時 fail-open 但必須讓使用者看得到提醒（規則 4）。"""

    def _setup(self, monkeypatch, tmp_path, diff_result):
        tests_dir = tmp_path / ".claude" / "hooks" / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / "test_foo_hook.py").write_text("def test_x():\n    assert True\n")
        monkeypatch.setattr(hook_module, "get_project_root", lambda: tmp_path)
        monkeypatch.setattr(hook_module, "run_git_command", lambda *a, **k: diff_result)
        monkeypatch.setattr(
            hook_module,
            "_run_pytest",
            lambda test_paths, hooks_dir, logger, timeout=None: ("pass", "1 passed"),
        )

    def _commit(self, monkeypatch, command='git commit -m "x"'):
        return _run_main(
            monkeypatch, {"tool_name": "Bash", "tool_input": {"command": command}}
        )

    def test_e1_diff_success_vs_failure_outputs_differ(self, monkeypatch, tmp_path):
        """E1 對照：同一指令、同一 fixture，僅 git diff 成敗不同，產物必須不同。"""
        self._setup(monkeypatch, tmp_path, (True, "M\0.claude/hooks/foo-hook.py\0"))
        _, ok_out = self._commit(monkeypatch)
        self._setup(monkeypatch, tmp_path, (False, "timeout"))
        _, fail_out = self._commit(monkeypatch)
        assert ok_out == []
        assert len(fail_out) == 1
        ctx = json.loads(fail_out[0])["hookSpecificOutput"]["additionalContext"]
        assert "staged" in ctx and "timeout" in ctx

    def test_e2_diff_failure_no_literal_reminds_without_deny(
        self, monkeypatch, tmp_path
    ):
        """E2 正向對照：git diff 失敗且命令無字面 hook 檔，必出提醒且非 deny。"""
        self._setup(monkeypatch, tmp_path, (False, "git not found"))
        exit_code, out = self._commit(monkeypatch, 'git commit -m "docs only"')
        assert exit_code == 0
        assert len(out) == 1
        hso = json.loads(out[0])["hookSpecificOutput"]
        assert hso.get("permissionDecision") != "deny"
        assert "additionalContext" in hso

    def test_diff_failure_writes_stderr(self, monkeypatch, tmp_path, capsys):
        self._setup(monkeypatch, tmp_path, (False, "timeout"))
        self._commit(monkeypatch)
        assert "staged" in capsys.readouterr().err

    def test_diff_failure_with_literal_hook_merges_single_output(
        self, monkeypatch, tmp_path
    ):
        """字面來源仍驗證測試；提醒與驗證結果合併為單一輸出，不 deny。"""
        self._setup(monkeypatch, tmp_path, (False, "timeout"))
        _, out = self._commit(
            monkeypatch, "git add .claude/hooks/foo-hook.py && git commit -m x"
        )
        assert len(out) == 1
        hso = json.loads(out[0])["hookSpecificOutput"]
        assert hso.get("permissionDecision") != "deny"
        assert "staged" in hso["additionalContext"]


class TestDetectionStageInputDefense:
    """偵測階段非預期輸入：記日誌後 exit 0 放行，不走 crash 路徑（fail-open）。"""

    HOOK_NAME = "hooks-test-gate-hook"

    def _run_via_entry(self, monkeypatch, capsys, payload_text: str):
        """走與 __main__ 相同的 run_hook_safely 入口，取得真實 exit code 與 stderr。"""
        monkeypatch.setattr(sys, "stdin", io.StringIO(payload_text))
        with patch("builtins.print"):
            code = hook_module.run_hook_safely(hook_module.main, self.HOOK_NAME)
        return code, capsys.readouterr().err

    def _symlink_loop(self, tmp_path):
        a, b = tmp_path / "loop_a", tmp_path / "loop_b"
        a.symlink_to(b)
        b.symlink_to(a)
        return a

    def _payloads(self, tmp_path):
        loop = self._symlink_loop(tmp_path)
        return {
            "list_payload": json.dumps([1, 2]),
            "string_tool_input": json.dumps(
                {"tool_name": "Bash", "tool_input": "git commit"}
            ),
            "int_command": json.dumps(
                {"tool_name": "Bash", "tool_input": {"command": 123}}
            ),
            "symlink_loop_dash_c": json.dumps(
                {
                    "tool_name": "Bash",
                    "tool_input": {"command": f"git -C {loop} commit -m x"},
                }
            ),
        }

    @pytest.mark.parametrize(
        "case",
        ["list_payload", "string_tool_input", "int_command", "symlink_loop_dash_c"],
    )
    def test_e2_known_crash_inputs_exit_zero_without_critical(
        self, monkeypatch, capsys, tmp_path, case
    ):
        """E2 正向對照：四類曾讓 gate crash 的輸入，必須 exit 0 且 stderr 無 CRITICAL。"""
        code, err = self._run_via_entry(
            monkeypatch, capsys, self._payloads(tmp_path)[case]
        )
        assert code == 0, err
        assert "CRITICAL" not in err

    def test_e1_same_command_normal_vs_abnormal_type(
        self, monkeypatch, tmp_path
    ):
        """E1 對照：同 command 字串，payload 型別正常走原判斷，異常型別走防禦路徑，日誌可區分。"""
        cmd = 'git commit -m "docs only"'
        monkeypatch.setattr(hook_module, "get_project_root", lambda: tmp_path)
        monkeypatch.setattr(hook_module, "run_git_command", lambda *a, **k: (True, ""))
        fake_logger = MagicMock()
        monkeypatch.setattr(hook_module, "setup_hook_logging", lambda name: fake_logger)

        ok_code, _ = _run_main(
            monkeypatch, {"tool_name": "Bash", "tool_input": {"command": cmd}}
        )
        ok_info = [str(c) for c in fake_logger.info.call_args_list]
        ok_debug = [str(c) for c in fake_logger.debug.call_args_list]
        fake_logger.reset_mock()
        bad_code, _ = _run_main(
            monkeypatch, {"tool_name": "Bash", "tool_input": [cmd]}
        )
        bad_info = [str(c) for c in fake_logger.info.call_args_list]
        bad_debug = [str(c) for c in fake_logger.debug.call_args_list]

        assert ok_code == 0 and bad_code == 0
        assert any("未觸及" in m for m in ok_debug) and ok_info == []
        assert any("型別" in m for m in bad_info)
        assert not any("未觸及" in m for m in bad_debug)

    def test_is_host_repo_commit_valueerror_returns_false(self):
        """路徑含 NUL 時 resolve 拋 ValueError，視為非本專案而非 crash。"""
        assert (
            hook_module._is_host_repo_commit("git -C /tmp/a\x00b commit", "/tmp")
            is False
        )
