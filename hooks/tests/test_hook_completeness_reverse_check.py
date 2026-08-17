"""Tests for hook-completeness-check 反向檢查（W9-004 / framework issue #2）.

驗證：
- resolve_hook_script_path（收斂自共用模組 lib.hook_command_resolver）解析
  $CLAUDE_PROJECT_DIR / interpreter 前綴 / 非腳本命令回 None
- find_phantom_registrations 偵測「已註冊但檔不存在」幽靈註冊（runtime 崩潰類型）
- find_duplicate_registrations 偵測跨檔重複（Stop matcher=""），且不誤判不同 matcher
  的多工具覆蓋（false-positive 回歸防護）
"""
from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path

import pytest

_HOOKS_DIR = Path(__file__).parent.parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

HOOK_FILE = _HOOKS_DIR / "hook-completeness-check.py"


def _load_hook_module():
    spec = importlib.util.spec_from_file_location(
        "hook_completeness_check", HOOK_FILE
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["hook_completeness_check"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def hook_module():
    return _load_hook_module()


def _settings_with_command(event: str, matcher: str, command: str) -> dict:
    return {
        "hooks": {
            event: [
                {"matcher": matcher, "hooks": [{"type": "command", "command": command}]}
            ]
        }
    }


class TestResolveCommandPath:
    def test_resolves_claude_project_dir(self, hook_module, tmp_path):
        cmd = "$CLAUDE_PROJECT_DIR/.claude/hooks/foo.py"
        assert hook_module.resolve_hook_script_path(cmd, tmp_path) == (
            tmp_path / ".claude" / "hooks" / "foo.py"
        )

    def test_resolves_braced_form(self, hook_module, tmp_path):
        cmd = "${CLAUDE_PROJECT_DIR}/.claude/hooks/foo.py"
        assert hook_module.resolve_hook_script_path(cmd, tmp_path) == (
            tmp_path / ".claude" / "hooks" / "foo.py"
        )

    def test_handles_interpreter_prefix(self, hook_module, tmp_path):
        cmd = "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/foo.py --flag"
        assert hook_module.resolve_hook_script_path(cmd, tmp_path) == (
            tmp_path / ".claude" / "hooks" / "foo.py"
        )

    def test_resolves_sh_extension(self, hook_module, tmp_path):
        """0.2.1-W3-513 收斂後新增涵蓋：.sh 副檔名（原實作僅認 .py）。"""
        cmd = "$CLAUDE_PROJECT_DIR/.claude/hooks/foo.sh"
        assert hook_module.resolve_hook_script_path(cmd, tmp_path) == (
            tmp_path / ".claude" / "hooks" / "foo.sh"
        )

    def test_returns_none_for_non_py_command(self, hook_module, tmp_path):
        assert hook_module.resolve_hook_script_path("echo hello", tmp_path) is None

    def test_returns_none_for_empty(self, hook_module, tmp_path):
        assert hook_module.resolve_hook_script_path("", tmp_path) is None


class TestFindPhantomRegistrations:
    def test_detects_registered_but_missing_file(self, hook_module, tmp_path):
        cmd = "$CLAUDE_PROJECT_DIR/.claude/hooks/ghost.py"
        settings = _settings_with_command("Stop", "", cmd)
        phantoms = hook_module.find_phantom_registrations(
            [("settings.local.json", settings)], tmp_path
        )
        assert len(phantoms) == 1
        label, event, path = phantoms[0]
        assert label == "settings.local.json"
        assert event == "Stop"
        assert path.endswith("ghost.py")

    def test_no_phantom_when_file_exists(self, hook_module, tmp_path):
        hook_path = tmp_path / ".claude" / "hooks" / "real.py"
        hook_path.parent.mkdir(parents=True)
        hook_path.write_text("# real", encoding="utf-8")
        cmd = "$CLAUDE_PROJECT_DIR/.claude/hooks/real.py"
        settings = _settings_with_command("Stop", "", cmd)
        phantoms = hook_module.find_phantom_registrations(
            [("settings.json", settings)], tmp_path
        )
        assert phantoms == []

    def test_skips_none_settings(self, hook_module, tmp_path):
        phantoms = hook_module.find_phantom_registrations(
            [("settings.local.json", None)], tmp_path
        )
        assert phantoms == []

    def test_ignores_non_py_inline_command(self, hook_module, tmp_path):
        settings = _settings_with_command("Stop", "", "echo done")
        phantoms = hook_module.find_phantom_registrations(
            [("settings.json", settings)], tmp_path
        )
        assert phantoms == []


class TestFindDuplicateRegistrations:
    def test_detects_cross_file_duplicate(self, hook_module, tmp_path):
        """同一 Stop hook（matcher=""）在 settings.json + settings.local.json → 重複."""
        cmd = "$CLAUDE_PROJECT_DIR/.claude/hooks/stop.py"
        s1 = _settings_with_command("Stop", "", cmd)
        s2 = _settings_with_command("Stop", "", cmd)
        dups = hook_module.find_duplicate_registrations(
            [("settings.json", s1), ("settings.local.json", s2)], tmp_path
        )
        assert len(dups) == 1
        event, path, labels = dups[0]
        assert event == "Stop"
        assert "settings.json" in labels and "settings.local.json" in labels

    def test_different_matchers_not_flagged(self, hook_module, tmp_path):
        """同一 hook 在 PreToolUse 下用不同 matcher（Edit/Write）屬合法多工具覆蓋，不報重複."""
        cmd = "$CLAUDE_PROJECT_DIR/.claude/hooks/guard.py"
        settings = {
            "hooks": {
                "PreToolUse": [
                    {"matcher": "Edit", "hooks": [{"type": "command", "command": cmd}]},
                    {"matcher": "Write", "hooks": [{"type": "command", "command": cmd}]},
                ]
            }
        }
        dups = hook_module.find_duplicate_registrations(
            [("settings.json", settings)], tmp_path
        )
        assert dups == []

    def test_single_registration_not_flagged(self, hook_module, tmp_path):
        cmd = "$CLAUDE_PROJECT_DIR/.claude/hooks/solo.py"
        settings = _settings_with_command("Stop", "", cmd)
        dups = hook_module.find_duplicate_registrations(
            [("settings.json", settings), ("settings.local.json", None)], tmp_path
        )
        assert dups == []


# ============================================================================
# extract_registered_commands：非預期 JSON 結構的 WARNING 可觀測性（0.2.1-W3-513 AC2/AC3）
# ============================================================================


class TestExtractRegisteredCommandsStructureWarning:
    """驗證 settings 結構不符預期時輸出 WARNING（不再靜默略過）。

    範圍校正說明（見 ticket Problem Analysis）：原票面設想的「差集解析恆為
    空使守衛永久 fail-open」情境綁定已刪除的舊版差集解析技術，現存程式碼
    無此技術路徑。此處驗證的是現存最接近的類比：extract_registered_commands
    走訪已解析 dict 時，若 'hooks' 或事件區塊非預期結構，須可觀測（WARNING）
    而非靜默回傳空結果——避免「掃描結果不完整」被誤讀為「確實沒有問題」。
    """

    def test_non_dict_hooks_block_logs_warning(self, hook_module, caplog):
        """settings['hooks'] 非 dict（如字串）時記錄 WARNING 並回傳空清單，不拋例外。"""
        logger_name = "test-w3-513-hooks-not-dict"
        logger = logging.getLogger(logger_name)
        settings = {"hooks": "not-a-dict"}

        with caplog.at_level(logging.WARNING, logger=logger_name):
            triples = hook_module.extract_registered_commands(settings, logger)

        assert triples == []
        assert any("hooks" in record.message and "非預期結構" in record.message for record in caplog.records)

    def test_non_list_event_block_logs_warning_and_skips_only_that_event(
        self, hook_module, caplog
    ):
        """單一事件區塊非 list 時，僅該事件被略過並記錄 WARNING，其餘事件不受影響
        （AC3：schema 變動不會使整個守衛恆放行——其他結構正常的事件仍被正確掃描）。
        """
        logger_name = "test-w3-513-event-not-list"
        logger = logging.getLogger(logger_name)
        cmd = "$CLAUDE_PROJECT_DIR/.claude/hooks/still-works.py"
        settings = {
            "hooks": {
                "PreToolUse": "malformed-should-be-list",
                "PostToolUse": [
                    {"matcher": "Edit", "hooks": [{"type": "command", "command": cmd}]}
                ],
            }
        }

        with caplog.at_level(logging.WARNING, logger=logger_name):
            triples = hook_module.extract_registered_commands(settings, logger)

        assert ("PostToolUse", "Edit", cmd) in triples
        assert not any(t[0] == "PreToolUse" for t in triples)
        assert any(
            "PreToolUse" in record.message and "非預期" in record.message
            for record in caplog.records
        )

    def test_no_logger_does_not_crash(self, hook_module):
        """未傳 logger（如既有呼叫端未更新）時仍不拋例外，僅略過日誌記錄。"""
        settings = {"hooks": "not-a-dict"}
        assert hook_module.extract_registered_commands(settings) == []

    def test_well_formed_settings_produces_no_warning(self, hook_module, caplog):
        """對照組：結構正常的 settings 不產生任何 WARNING（避免過度告警噪音）。"""
        logger_name = "test-w3-513-well-formed"
        logger = logging.getLogger(logger_name)
        cmd = "$CLAUDE_PROJECT_DIR/.claude/hooks/normal.py"
        settings = _settings_with_command("Stop", "", cmd)

        with caplog.at_level(logging.WARNING, logger=logger_name):
            triples = hook_module.extract_registered_commands(settings, logger)

        assert triples == [("Stop", "", cmd)]
        assert caplog.records == []

    def test_phantom_scan_survives_malformed_source_and_still_checks_others(
        self, hook_module, tmp_path
    ):
        """AC3 端對端：settings_sources 中一份結構壞掉，另一份仍被正確掃描出幽靈
        （不會因單一來源解析異常就讓整個 find_phantom_registrations 恆回傳空）。
        """
        ghost_cmd = "$CLAUDE_PROJECT_DIR/.claude/hooks/ghost.py"
        malformed = {"hooks": "not-a-dict"}
        healthy = _settings_with_command("Stop", "", ghost_cmd)

        phantoms = hook_module.find_phantom_registrations(
            [("settings.local.json", malformed), ("settings.json", healthy)], tmp_path
        )

        assert len(phantoms) == 1
        assert phantoms[0][0] == "settings.json"
        assert phantoms[0][2].endswith("ghost.py")
