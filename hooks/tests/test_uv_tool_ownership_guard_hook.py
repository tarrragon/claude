"""
Tests for uv-tool-ownership-guard-hook（PreToolUse: Bash）。

對應 ticket 0.19.0-W3-090（方案 A ownership guard）。

覆蓋三路徑：
  - match：receipt directory == 當前專案 → 零 reinstall
  - mismatch：receipt directory == 他專案 → 觸發 reinstall
  - 非工具命令：fast-path 立即返回，零 IO / 零 reinstall

附加：命令辨識（cd 包裹 / 連接符）、迴圈防護、receipt 缺失。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_HOOKS_DIR = Path(__file__).parent.parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

HOOK_FILE = _HOOKS_DIR / "uv-tool-ownership-guard-hook.py"


def _load_hook_module():
    spec = importlib.util.spec_from_file_location(
        "uv_tool_ownership_guard_hook", HOOK_FILE
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["uv_tool_ownership_guard_hook"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def hook():
    return _load_hook_module()


@pytest.fixture
def logger():
    return MagicMock()


@pytest.fixture(autouse=True)
def _non_shim_by_default(hook, monkeypatch):
    """既有 ownership 測試假設 CLI 非 shim；隔離 host 環境真實 which 結果，
    避免本機 ticket/doc 已 shim 化時 is_shimmed_cli 短路提前 continue。"""
    monkeypatch.setattr(
        hook, "is_shimmed_cli", lambda cli, logger=None: False
    )


# ---------------------------------------------------------------------------
# 命令辨識（_extract_invoked_exes）
# ---------------------------------------------------------------------------


class TestCommandRecognition:
    def test_plain_invocation(self, hook):
        assert hook._extract_invoked_exes("ticket track list") == ["ticket"]

    def test_cd_wrapped_subshell(self, hook):
        # (cd x && ticket ...)：cd 段首 token 為 cd（被忽略），ticket 段命中
        assert hook._extract_invoked_exes(
            "(cd .claude/skills/ticket && ticket track list)"
        ) == ["ticket"]

    def test_chained_and_operator(self, hook):
        assert hook._extract_invoked_exes("doc build && ticket complete x") == [
            "doc",
            "ticket",
        ]

    def test_pipe_operator(self, hook):
        assert hook._extract_invoked_exes("echo hi | ticket track list") == ["ticket"]

    def test_exe_as_argument_not_matched(self, hook):
        # ticket 出現在參數位置（非首 token）不應命中，避免誤判
        assert hook._extract_invoked_exes("echo ticket") == []

    def test_non_tool_command_empty(self, hook):
        assert hook._extract_invoked_exes("git status && npm test") == []

    def test_all_seven_skills_covered(self, hook):
        # 對照表涵蓋 7 個 skill
        assert len(hook.SKILLS) == 7
        for cli in [
            "ticket",
            "doc",
            "version-release",
            "mermaid-ascii",
            "worktree",
            "branch-worktree-guardian",
            "project-init",
        ]:
            assert cli in hook.EXE_SET


# ---------------------------------------------------------------------------
# fast-path（非工具命令 → 零 IO / 零 reinstall）
# ---------------------------------------------------------------------------


class TestFastPath:
    def test_non_tool_command_no_receipt_read(self, hook, logger):
        with patch.object(hook, "_read_receipt_directory") as m_read, patch.object(
            hook, "_reinstall"
        ) as m_reinstall:
            hook._guard_command("git status", Path("/proj"), logger)
            m_read.assert_not_called()
            m_reinstall.assert_not_called()

    def test_loop_protection_uv_tool_install_passes(self, hook, logger):
        # reinstall 命令本身不得再觸發 ownership 檢查
        with patch.object(hook, "_read_receipt_directory") as m_read, patch.object(
            hook, "_reinstall"
        ) as m_reinstall:
            hook._guard_command(
                "uv tool install . --reinstall", Path("/proj"), logger
            )
            m_read.assert_not_called()
            m_reinstall.assert_not_called()

    def test_loop_protection_even_with_tool_name(self, hook, logger):
        # 即使命令也含 ticket，只要含 uv tool install 即放行
        with patch.object(hook, "_reinstall") as m_reinstall:
            hook._guard_command(
                "cd .claude/skills/ticket && uv tool install . --reinstall",
                Path("/proj"),
                logger,
            )
            m_reinstall.assert_not_called()


# ---------------------------------------------------------------------------
# match / mismatch（_guard_command 整合）
# ---------------------------------------------------------------------------


class TestOwnershipGuard:
    def test_match_no_reinstall(self, hook, logger):
        project_root = Path("/Users/me/project/book_overview_v1")
        expected = (project_root / ".claude/skills/ticket").resolve()
        with patch.object(
            hook, "_read_receipt_directory", return_value=str(expected)
        ), patch.object(hook, "_reinstall") as m_reinstall:
            hook._guard_command("ticket track list", project_root, logger)
            m_reinstall.assert_not_called()

    def test_mismatch_triggers_reinstall(self, hook, logger):
        project_root = Path("/Users/me/project/book_overview_v1")
        other_project = "/Users/me/project/screen_clock/.claude/skills/ticket"
        with patch.object(
            hook, "_read_receipt_directory", return_value=other_project
        ), patch.object(hook, "_reinstall", return_value=True) as m_reinstall:
            hook._guard_command("ticket track list", project_root, logger)
            m_reinstall.assert_called_once()
            # reinstall 對象為 ticket skill
            called_skill = m_reinstall.call_args[0][0]
            assert called_skill.cli_name == "ticket"

    def test_missing_receipt_triggers_reinstall(self, hook, logger):
        project_root = Path("/Users/me/project/book_overview_v1")
        with patch.object(
            hook, "_read_receipt_directory", return_value=None
        ), patch.object(hook, "_reinstall", return_value=True) as m_reinstall:
            hook._guard_command("doc build", project_root, logger)
            m_reinstall.assert_called_once()
            assert m_reinstall.call_args[0][0].cli_name == "doc"

    def test_multiple_exes_each_checked(self, hook, logger):
        project_root = Path("/Users/me/project/book_overview_v1")
        with patch.object(
            hook, "_read_receipt_directory", return_value=None
        ), patch.object(hook, "_reinstall", return_value=True) as m_reinstall:
            hook._guard_command("doc build && ticket complete x", project_root, logger)
            assert m_reinstall.call_count == 2


# ---------------------------------------------------------------------------
# _is_owned_by_project（路徑比對）
# ---------------------------------------------------------------------------


class TestOwnershipComparison:
    def test_exact_match(self, hook, tmp_path):
        d = tmp_path / "skills" / "ticket"
        d.mkdir(parents=True)
        assert hook._is_owned_by_project(str(d), d.resolve()) is True

    def test_different_dir(self, hook, tmp_path):
        a = tmp_path / "a"
        b = tmp_path / "b"
        a.mkdir()
        b.mkdir()
        assert hook._is_owned_by_project(str(a), b.resolve()) is False

    def test_invalid_path_returns_false(self, hook):
        assert hook._is_owned_by_project("\x00invalid", Path("/x")) is False


# ---------------------------------------------------------------------------
# _reinstall（subprocess 行為 + 可觀測性）
# ---------------------------------------------------------------------------


class TestReinstall:
    def test_reinstall_success_invokes_uv(self, hook, logger, tmp_path):
        source = tmp_path / ".claude/skills/ticket"
        source.mkdir(parents=True)
        skill = hook.SkillEntry(".claude/skills/ticket", "ticket-system", "ticket")
        mock_result = MagicMock(returncode=0, stderr="")
        with patch.object(hook.subprocess, "run", return_value=mock_result) as m_run:
            ok = hook._reinstall(skill, tmp_path, logger)
        assert ok is True
        args, kwargs = m_run.call_args
        assert args[0] == ["uv", "tool", "install", ".", "--reinstall"]
        assert kwargs["cwd"] == str(source)

    def test_reinstall_source_missing_returns_false(self, hook, logger, tmp_path):
        skill = hook.SkillEntry(".claude/skills/ticket", "ticket-system", "ticket")
        # tmp_path 下無 .claude/skills/ticket
        ok = hook._reinstall(skill, tmp_path, logger)
        assert ok is False

    def test_reinstall_nonzero_returns_false(self, hook, logger, tmp_path):
        source = tmp_path / ".claude/skills/ticket"
        source.mkdir(parents=True)
        skill = hook.SkillEntry(".claude/skills/ticket", "ticket-system", "ticket")
        mock_result = MagicMock(returncode=1, stderr="boom")
        with patch.object(hook.subprocess, "run", return_value=mock_result):
            ok = hook._reinstall(skill, tmp_path, logger)
        assert ok is False

    def test_reinstall_writes_stderr_observability(self, hook, logger, tmp_path, capsys):
        source = tmp_path / ".claude/skills/ticket"
        source.mkdir(parents=True)
        skill = hook.SkillEntry(".claude/skills/ticket", "ticket-system", "ticket")
        mock_result = MagicMock(returncode=0, stderr="")
        with patch.object(hook.subprocess, "run", return_value=mock_result):
            hook._reinstall(skill, tmp_path, logger)
        captured = capsys.readouterr()
        # 雙通道：stderr 有訊息 + logger.info 被呼叫
        assert "OwnershipGuard" in captured.err
        assert logger.info.called


# ---------------------------------------------------------------------------
# _read_receipt_directory（receipt 解析）
# ---------------------------------------------------------------------------


class TestReceiptParsing:
    def test_parses_directory_field(self, hook, logger, tmp_path, monkeypatch):
        fake_home = tmp_path
        receipt = (
            fake_home / ".local/share/uv/tools/ticket-system/uv-receipt.toml"
        )
        receipt.parent.mkdir(parents=True)
        receipt.write_text(
            '[tool]\nrequirements = [{ name = "ticket-system", '
            'directory = "/Users/me/project/book_overview_v1/.claude/skills/ticket" }]\n',
            encoding="utf-8",
        )
        monkeypatch.setattr(hook.Path, "home", lambda: fake_home)
        result = hook._read_receipt_directory("ticket-system", logger)
        assert result == "/Users/me/project/book_overview_v1/.claude/skills/ticket"

    def test_missing_receipt_returns_none(self, hook, logger, tmp_path, monkeypatch):
        monkeypatch.setattr(hook.Path, "home", lambda: tmp_path)
        assert hook._read_receipt_directory("nonexistent-pkg", logger) is None


# ---------------------------------------------------------------------------
# 0.37.0-W7-002：cwd-resolving shim 略過行為（ARCH-APP-002）
# ---------------------------------------------------------------------------


class TestShimSkip:
    def test_shim_cli_not_reinstalled(self, hook, logger, monkeypatch):
        """偵測 CLI 為 shim 時放行，不讀 receipt、不 reinstall。"""
        project_root = Path("/Users/me/project/book_overview_v1")
        monkeypatch.setattr(hook, "is_shimmed_cli", lambda cli, logger=None: True)
        with patch.object(
            hook, "_read_receipt_directory"
        ) as m_receipt, patch.object(hook, "_reinstall") as m_reinstall:
            hook._guard_command("ticket track list", project_root, logger)
            m_reinstall.assert_not_called()
            m_receipt.assert_not_called()

    def test_shim_skip_selective_per_exe(self, hook, logger, monkeypatch):
        """混合命令中僅非 shim 的 CLI 走 ownership 比對 → reinstall。"""
        project_root = Path("/Users/me/project/book_overview_v1")
        # ticket 為 shim（放行），doc 非 shim（receipt 缺失 → reinstall）
        monkeypatch.setattr(
            hook, "is_shimmed_cli", lambda cli, logger=None: cli == "ticket"
        )
        with patch.object(
            hook, "_read_receipt_directory", return_value=None
        ), patch.object(hook, "_reinstall", return_value=True) as m_reinstall:
            hook._guard_command("doc build && ticket complete x", project_root, logger)
            m_reinstall.assert_called_once()
            assert m_reinstall.call_args[0][0].cli_name == "doc"
