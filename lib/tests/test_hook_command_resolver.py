#!/usr/bin/env python3
"""
hook_command_resolver 模組單元測試

驗證項目：
1. substitute_hook_command_vars：$VAR 與 ${VAR} 兩種展開形式
2. tokenize_hook_command：shlex 切分 + ValueError 忠實傳播（畸形引號）
3. resolve_hook_script_path：.py/.sh 兩種副檔名、runner 前綴、尾端引數、
   絕對/相對路徑、非本機腳本、畸形字串降級（不拋例外）

Source: 收斂 hook-completeness-check.py 與 hook_output_validator.py 的
重複命令字串解析實作。
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.hook_command_resolver import (
    HOOK_COMMAND_VARS,
    HOOK_SCRIPT_SUFFIXES,
    hook_command_var_values,
    resolve_hook_script_path,
    substitute_hook_command_vars,
    tokenize_hook_command,
)


PROJECT_ROOT = Path("/fake/project")


class TestHookCommandVarValues:
    def test_returns_both_known_vars(self):
        values = hook_command_var_values(PROJECT_ROOT)
        assert set(values) == set(HOOK_COMMAND_VARS)

    def test_claude_project_dir_value(self):
        values = hook_command_var_values(PROJECT_ROOT)
        assert values["CLAUDE_PROJECT_DIR"] == str(PROJECT_ROOT)

    def test_claude_file_path_value(self):
        values = hook_command_var_values(PROJECT_ROOT)
        assert values["CLAUDE_FILE_PATH"] == str(PROJECT_ROOT / "CLAUDE.md")


class TestSubstituteHookCommandVars:
    def test_bare_dollar_form(self):
        result = substitute_hook_command_vars(
            "$CLAUDE_PROJECT_DIR/.claude/hooks/x.py", PROJECT_ROOT
        )
        assert result == "/fake/project/.claude/hooks/x.py"

    def test_braced_form(self):
        result = substitute_hook_command_vars(
            "${CLAUDE_PROJECT_DIR}/.claude/hooks/x.py", PROJECT_ROOT
        )
        assert result == "/fake/project/.claude/hooks/x.py"

    def test_both_forms_in_same_command(self):
        result = substitute_hook_command_vars(
            "${CLAUDE_PROJECT_DIR}/.claude/hooks/x.py $CLAUDE_FILE_PATH",
            PROJECT_ROOT,
        )
        assert result == "/fake/project/.claude/hooks/x.py /fake/project/CLAUDE.md"

    def test_no_variables_returns_unchanged(self):
        assert substitute_hook_command_vars("echo hello", PROJECT_ROOT) == "echo hello"


class TestTokenizeHookCommand:
    def test_plain_path(self):
        tokens = tokenize_hook_command("$CLAUDE_PROJECT_DIR/.claude/hooks/x.py", PROJECT_ROOT)
        assert tokens == ["/fake/project/.claude/hooks/x.py"]

    def test_uv_run_prefix(self):
        tokens = tokenize_hook_command(
            "uv run $CLAUDE_PROJECT_DIR/.claude/hooks/x.py", PROJECT_ROOT
        )
        assert tokens == ["uv", "run", "/fake/project/.claude/hooks/x.py"]

    def test_quoted_path_with_space(self):
        """shlex 正確處理含空白的引號路徑（樸素 .split() 會誤切）。"""
        tokens = tokenize_hook_command('"/fake/project/.claude/hooks/my hook.py"', PROJECT_ROOT)
        assert tokens == ["/fake/project/.claude/hooks/my hook.py"]

    def test_malformed_quotes_raises_value_error(self):
        """ValueError 忠實傳播，不在本函式吞掉（供需要精確錯誤回報的呼叫端處理）。"""
        with pytest.raises(ValueError):
            tokenize_hook_command('"unterminated quote', PROJECT_ROOT)


class TestResolveHookScriptPath:
    def test_plain_path(self):
        resolved = resolve_hook_script_path(
            "$CLAUDE_PROJECT_DIR/.claude/hooks/x.py", PROJECT_ROOT
        )
        assert resolved == PROJECT_ROOT / ".claude" / "hooks" / "x.py"

    def test_braced_form(self):
        resolved = resolve_hook_script_path(
            "${CLAUDE_PROJECT_DIR}/.claude/hooks/x.py", PROJECT_ROOT
        )
        assert resolved == PROJECT_ROOT / ".claude" / "hooks" / "x.py"

    def test_uv_run_prefix_form(self):
        resolved = resolve_hook_script_path(
            "uv run $CLAUDE_PROJECT_DIR/.claude/hooks/x.py", PROJECT_ROOT
        )
        assert resolved == PROJECT_ROOT / ".claude" / "hooks" / "x.py"

    def test_trailing_argument_form(self):
        resolved = resolve_hook_script_path(
            "$CLAUDE_PROJECT_DIR/.claude/hooks/x.py $CLAUDE_FILE_PATH", PROJECT_ROOT
        )
        assert resolved == PROJECT_ROOT / ".claude" / "hooks" / "x.py"

    def test_shell_script_extension(self):
        resolved = resolve_hook_script_path(
            "$CLAUDE_PROJECT_DIR/.claude/hooks/x.sh", PROJECT_ROOT
        )
        assert resolved == PROJECT_ROOT / ".claude" / "hooks" / "x.sh"

    def test_default_suffixes_cover_both_py_and_sh(self):
        assert set(HOOK_SCRIPT_SUFFIXES) == {".py", ".sh"}

    def test_custom_suffixes_restricts_match(self):
        """呼叫端可覆寫 suffixes 縮小範圍（如只要 .py，不要 .sh）。"""
        resolved = resolve_hook_script_path(
            "$CLAUDE_PROJECT_DIR/.claude/hooks/x.sh", PROJECT_ROOT, suffixes=(".py",)
        )
        assert resolved is None

    def test_non_script_command_returns_none(self):
        assert resolve_hook_script_path("echo hello", PROJECT_ROOT) is None

    def test_empty_command_returns_none(self):
        assert resolve_hook_script_path("", PROJECT_ROOT) is None

    def test_relative_path_resolved_against_project_root(self):
        resolved = resolve_hook_script_path(".claude/hooks/x.py", PROJECT_ROOT)
        assert resolved == PROJECT_ROOT / ".claude" / "hooks" / "x.py"

    def test_absolute_path_kept_as_is(self):
        resolved = resolve_hook_script_path("/opt/other/x.py", PROJECT_ROOT)
        assert resolved == Path("/opt/other/x.py")

    def test_malformed_quotes_does_not_raise_falls_back_to_split(self):
        """畸形字串降級為樸素空白切分，不拋例外（本函式供完整性檢查使用，
        容錯優先於精確——與 tokenize_hook_command 的忠實傳播行為刻意不同）。
        """
        resolved = resolve_hook_script_path(
            '"unterminated $CLAUDE_PROJECT_DIR/.claude/hooks/x.py', PROJECT_ROOT
        )
        # 降級後的樸素切分仍能找到以 .py 結尾的 token（引號字元殘留於 token
        # 開頭，不影響 endswith(".py") 判定）
        assert resolved is not None
        assert str(resolved).endswith("x.py")
