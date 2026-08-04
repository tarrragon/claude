"""Tests for sync-claude-pull.py parse_args（0.2.1-W3-164）。

問題：pull 的 main() 此前用手動 argv 比對（`if "--audit" in argv` /
`if "--bump" in argv`），對 `--help` 與未知旗標 fail-open——兩者皆會落入
正常同步主流程，觸發真實不可逆 pull（PM 於 ccsession worktree 實測：
`--help` 未印用法，直接輸出「開始從獨立 repo 拉取 .claude 更新...」）。
與 push 端 v1.48.6 誤推（PC-V1-001）同家族根因，push 端已用 argparse
防護，pull 端此前未套用。

修復：main 改用 argparse（比照 `sync-claude-push.py::parse_args`）。
`--help` exit 0、未知旗標 exit 2，皆在解析階段中止，不進入 clone。

五情境（acceptance 4）：
  1. `--help` → 印用法、exit 0、不進 clone
  2. 未知旗標 → exit 2、不進 clone
  3. `--audit` → args.audit=True，main 呼叫 run_audit 後 return，不進同步
  4. `--bump <版本>` → args.bump 為該版本字串
  5. `--bump`（不帶參數） → args.bump 為 None（代表 latest，語意不變）

Not in scope：不改同步邏輯本身，`_clone_and_backup` / `_complete_sync` 等
維持原樣（真正的網路呼叫皆不在本測試檔內觸發）。
"""
from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-pull.py"
_spec = importlib.util.spec_from_file_location("sync_claude_pull_parse_args", _SCRIPT)
assert _spec and _spec.loader
pull = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_pull_parse_args"] = pull
_spec.loader.exec_module(pull)  # type: ignore[union-attr]


# ============================================================================
# parse_args：單元測試（不涉及 main()，純解析邏輯）
# ============================================================================


class TestParseArgsHelp:
    def test_help_flag_raises_systemexit_zero(self):
        with pytest.raises(SystemExit) as exc_info:
            pull.parse_args(["--help"])
        assert exc_info.value.code == 0

    def test_help_short_flag_raises_systemexit_zero(self):
        with pytest.raises(SystemExit) as exc_info:
            pull.parse_args(["-h"])
        assert exc_info.value.code == 0

    def test_help_prints_usage(self, capsys):
        with pytest.raises(SystemExit):
            pull.parse_args(["--help"])
        out = capsys.readouterr().out
        assert "usage" in out.lower()
        assert "--audit" in out
        assert "--bump" in out


class TestParseArgsUnknownFlag:
    def test_unknown_flag_raises_systemexit_two(self):
        with pytest.raises(SystemExit) as exc_info:
            pull.parse_args(["--nonexistent-flag"])
        assert exc_info.value.code == 2

    def test_unknown_positional_raises_systemexit_two(self):
        """舊版手動解析對任意未知輸入 fail-open，新版 argparse 對未知位置
        參數（--audit/--bump 皆非位置參數）一律 exit 2。"""
        with pytest.raises(SystemExit) as exc_info:
            pull.parse_args(["some-random-arg"])
        assert exc_info.value.code == 2

    def test_unknown_flag_error_to_stderr(self, capsys):
        with pytest.raises(SystemExit):
            pull.parse_args(["--nonexistent-flag"])
        err = capsys.readouterr().err
        assert "unrecognized" in err.lower()


class TestParseArgsAudit:
    def test_audit_flag_sets_true(self):
        args = pull.parse_args(["--audit"])
        assert args.audit is True

    def test_no_audit_flag_defaults_false(self):
        args = pull.parse_args([])
        assert args.audit is False


class TestParseArgsBump:
    def test_no_bump_flag_uses_sentinel(self):
        """acceptance 3 對應：既有語意不變——完全未帶 --bump 時不進入 bump 分支。"""
        args = pull.parse_args([])
        assert args.bump is pull._BUMP_NOT_SET

    def test_bump_without_version_is_none(self):
        """acceptance 3：--bump 不帶參數 = bump 至 latest（None 代表 latest，語意不變）。"""
        args = pull.parse_args(["--bump"])
        assert args.bump is None

    def test_bump_with_version(self):
        """acceptance 3：--bump <版本> = pin 至該版本。"""
        args = pull.parse_args(["--bump", "v1.2.0"])
        assert args.bump == "v1.2.0"

    def test_bump_equals_syntax_also_works(self):
        args = pull.parse_args(["--bump=v2.0.0"])
        assert args.bump == "v2.0.0"

    def test_bump_followed_by_another_flag_not_consumed_as_version(self):
        """--bump 後緊接另一旗標（非版本字串）時，argparse 不應把該旗標
        誤當版本值消費——與舊版 `not argv[idx+1].startswith("-")` 判斷語意一致。"""
        args = pull.parse_args(["--bump", "--audit"])
        assert args.bump is None
        assert args.audit is True


class TestParseArgsReturnType:
    def test_returns_namespace(self):
        assert isinstance(pull.parse_args([]), argparse.Namespace)


# ============================================================================
# main()：--help / 未知旗標不進入同步主流程（整合驗證）
# ============================================================================


class TestMainDoesNotEnterSyncOnHelpOrUnknownFlag:
    def test_help_does_not_call_clone(self, monkeypatch):
        """acceptance 1：--help 不應進入 clone（main 應在 parse_args 階段即中止）。"""
        called = {"clone": False}

        def _fake_clone_backup(_root):
            called["clone"] = True
            raise AssertionError("--help 不應觸發同步主流程")

        monkeypatch.setattr(pull, "_clone_and_backup", _fake_clone_backup)
        monkeypatch.setattr(sys, "argv", ["sync-claude-pull.py", "--help"])

        with pytest.raises(SystemExit) as exc_info:
            pull.main()

        assert exc_info.value.code == 0
        assert called["clone"] is False

    def test_unknown_flag_does_not_call_clone(self, monkeypatch):
        """acceptance 2：未知旗標不應進入 clone。"""
        called = {"clone": False}

        def _fake_clone_backup(_root):
            called["clone"] = True
            raise AssertionError("未知旗標不應觸發同步主流程")

        monkeypatch.setattr(pull, "_clone_and_backup", _fake_clone_backup)
        monkeypatch.setattr(sys, "argv", ["sync-claude-pull.py", "--bogus"])

        with pytest.raises(SystemExit) as exc_info:
            pull.main()

        assert exc_info.value.code == 2
        assert called["clone"] is False


class TestMainBumpRoutesCorrectly:
    def test_bump_with_version_calls_update_pinned_version(self, monkeypatch, tmp_path):
        """acceptance 3：--bump <版本> 更新 pin 後仍重跑同步（既有語意）。"""
        recorded = {}

        def _fake_update_pinned(claude_dir, version):
            recorded["claude_dir"] = claude_dir
            recorded["version"] = version

        def _fake_clone_backup(_root):
            recorded["sync_entered"] = True
            raise pull.subprocess.TimeoutExpired(cmd="git", timeout=1)

        monkeypatch.setattr(pull, "find_project_root", lambda: tmp_path)
        monkeypatch.setattr(pull, "update_pinned_version", _fake_update_pinned)
        monkeypatch.setattr(pull, "_clone_and_backup", _fake_clone_backup)
        monkeypatch.setattr(pull, "_validate_environment", lambda _root: None)
        monkeypatch.setattr(pull, "warn_conflict_residue", lambda _dir: None)
        monkeypatch.setattr(sys, "argv", ["sync-claude-pull.py", "--bump", "v1.2.0"])

        with pytest.raises(SystemExit):
            pull.main()

        assert recorded["version"] == "v1.2.0"
        assert recorded.get("sync_entered") is True, "--bump 後仍應重跑同步流程（既有語意）"

    def test_bump_without_version_bumps_to_latest(self, monkeypatch, tmp_path, capsys):
        """acceptance 3：--bump 不帶版本 = bump 至 latest。"""
        recorded = {}

        def _fake_update_pinned(claude_dir, version):
            recorded["version"] = version

        def _fake_clone_backup(_root):
            raise pull.subprocess.TimeoutExpired(cmd="git", timeout=1)

        monkeypatch.setattr(pull, "find_project_root", lambda: tmp_path)
        monkeypatch.setattr(pull, "update_pinned_version", _fake_update_pinned)
        monkeypatch.setattr(pull, "_clone_and_backup", _fake_clone_backup)
        monkeypatch.setattr(pull, "_validate_environment", lambda _root: None)
        monkeypatch.setattr(pull, "warn_conflict_residue", lambda _dir: None)
        monkeypatch.setattr(sys, "argv", ["sync-claude-pull.py", "--bump"])

        with pytest.raises(SystemExit):
            pull.main()

        assert recorded["version"] is None
        out = capsys.readouterr().out
        assert pull.PIN_LATEST in out

    def test_no_bump_flag_skips_update_pinned_version(self, monkeypatch, tmp_path):
        """回歸：完全未帶 --bump 時不呼叫 update_pinned_version（既有語意不變）。"""
        called = {"update": False}

        def _fake_update_pinned(claude_dir, version):
            called["update"] = True

        def _fake_clone_backup(_root):
            raise pull.subprocess.TimeoutExpired(cmd="git", timeout=1)

        monkeypatch.setattr(pull, "find_project_root", lambda: tmp_path)
        monkeypatch.setattr(pull, "update_pinned_version", _fake_update_pinned)
        monkeypatch.setattr(pull, "_clone_and_backup", _fake_clone_backup)
        monkeypatch.setattr(pull, "_validate_environment", lambda _root: None)
        monkeypatch.setattr(pull, "warn_conflict_residue", lambda _dir: None)
        monkeypatch.setattr(sys, "argv", ["sync-claude-pull.py"])

        with pytest.raises(SystemExit):
            pull.main()

        assert called["update"] is False


# ============================================================================
# subprocess 層驗證：真實執行腳本（不模擬），僅測 --help / 未知旗標
# （這兩者在解析階段即中止，不觸發任何 clone / 網路呼叫，符合「禁真實
# remote 呼叫」約束）
# ============================================================================


class TestRealSubprocessHelpAndUnknownFlag:
    def test_real_help_exits_zero_and_prints_usage(self):
        result = subprocess.run(
            [sys.executable, str(_SCRIPT), "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "usage" in result.stdout.lower()
        assert "開始從獨立 repo 拉取" not in result.stdout, "不應進入同步主流程"

    def test_real_unknown_flag_exits_two(self):
        result = subprocess.run(
            [sys.executable, str(_SCRIPT), "--totally-unknown"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 2
        assert "開始從獨立 repo 拉取" not in result.stdout, "不應進入同步主流程"
