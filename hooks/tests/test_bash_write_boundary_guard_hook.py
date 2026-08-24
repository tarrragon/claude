#!/usr/bin/env python3
"""
Bash Write Boundary Guard Hook - 測試程式碼

main-thread-edit-restriction-hook.py 僅註冊於 Edit/Write/MultiEdit，可被 Bash
寫入（heredoc / cat > / cat >> / tee / sed -i / python open() / cp / mv）繞過。
本 hook 是該缺口的 Bash matcher 補網，涵蓋：

- 候選寫入路徑抽取（各種語法形態）
- test/、lib/、*.dart 命中時轉呼 check_file_permission 判定違規
- 合法 Bash 使用場景（讀取、非目標路徑寫入）不誤擋（fail-open）
- 非 Bash 工具 / subagent 環境 / 開發分支跳過
"""

import importlib.util
import logging
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

hook_dir = Path(__file__).parent.parent
sys.path.insert(0, str(hook_dir))
sys.path.insert(0, str(hook_dir.parent))

spec = importlib.util.spec_from_file_location(
    "bash_write_boundary_guard_hook_module",
    hook_dir / "bash-write-boundary-guard-hook.py",
)
hook_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook_module)

_extract_candidate_paths = hook_module._extract_candidate_paths
_find_boundary_violation = hook_module._find_boundary_violation
main = hook_module.main


@pytest.fixture
def logger():
    lg = logging.getLogger("test-bash-write-boundary-guard")
    lg.addHandler(logging.NullHandler())
    return lg


# ============================================================================
# 候選路徑抽取：各種寫入語法形態
# ============================================================================


class TestCandidatePathExtraction:
    """各寫入語法形態應正確抽出目標路徑。"""

    def test_cat_redirect_heredoc(self):
        cmd = "cat > lib/foo.dart <<'EOF'\nclass Foo {}\nEOF"
        assert "lib/foo.dart" in _extract_candidate_paths(cmd)

    def test_cat_append_heredoc(self):
        cmd = "cat >> test/foo_test.dart <<'EOF'\nvoid main(){}\nEOF"
        assert "test/foo_test.dart" in _extract_candidate_paths(cmd)

    def test_python_open_in_heredoc(self):
        cmd = "python3 - <<'EOF'\nopen('lib/bar.dart', 'w').write('x')\nEOF"
        assert "lib/bar.dart" in _extract_candidate_paths(cmd)

    def test_sed_inplace(self):
        cmd = "sed -i '' 's/a/b/' lib/foo.dart"
        assert "lib/foo.dart" in _extract_candidate_paths(cmd)

    def test_cp_target(self):
        cmd = "cp source.dart lib/dest.dart"
        assert "lib/dest.dart" in _extract_candidate_paths(cmd)

    def test_mv_target(self):
        cmd = "mv old.dart lib/new.dart"
        assert "lib/new.dart" in _extract_candidate_paths(cmd)

    def test_tee_target(self):
        cmd = "tee lib/output.dart <<'EOF'\nfoo\nEOF"
        assert "lib/output.dart" in _extract_candidate_paths(cmd)

    def test_no_candidates_for_read_only_command(self):
        assert _extract_candidate_paths("git status") == []
        assert _extract_candidate_paths("ls -la") == []


# ============================================================================
# 違規偵測：命中 test/lib/dart 且判定不允許
# ============================================================================


class TestBoundaryViolationDetection:
    """重現 0.2.1-W3-825 紀錄的繞過形態，確認修復後被偵測。"""

    def test_heredoc_write_to_lib_dart_is_violation(self, logger):
        cmd = "cat > lib/foo.dart <<'EOF'\nclass Foo {}\nEOF"
        assert _find_boundary_violation(cmd, logger) == "lib/foo.dart"

    def test_python_inline_script_write_to_lib_is_violation(self, logger):
        cmd = "python3 - <<'EOF'\nopen('lib/bar.dart', 'a').write('x')\nEOF"
        assert _find_boundary_violation(cmd, logger) == "lib/bar.dart"

    def test_sed_inplace_write_to_dart_is_violation(self, logger):
        cmd = "sed -i '' 's/a/b/' lib/foo.dart"
        assert _find_boundary_violation(cmd, logger) == "lib/foo.dart"

    def test_cp_into_test_dir_is_violation(self, logger):
        cmd = "cp source_test.dart test/foo_test.dart"
        assert _find_boundary_violation(cmd, logger) == "test/foo_test.dart"

    def test_mv_into_lib_dir_is_violation(self, logger):
        cmd = "mv scratch.dart lib/new_widget.dart"
        assert _find_boundary_violation(cmd, logger) == "lib/new_widget.dart"


# ============================================================================
# 誤判率評估：合法 Bash 使用場景不誤擋
# ============================================================================


class TestLegitimateUsageNotBlocked:
    """至少 3 個合法 Bash 使用場景（非寫入 test/lib/dart 路徑）驗證不誤擋。"""

    def test_flutter_test_command_not_blocked(self, logger):
        cmd = "flutter test test/unit/foo_test.dart"
        assert _find_boundary_violation(cmd, logger) is None

    def test_ticket_cli_not_blocked(self, logger):
        cmd = "ticket track claim ticket-id --as basil-hook-architect"
        assert _find_boundary_violation(cmd, logger) is None

    def test_grep_read_lib_not_blocked(self, logger):
        cmd = "grep -rn 'foo' lib/"
        assert _find_boundary_violation(cmd, logger) is None

    def test_cat_read_dart_file_not_blocked(self, logger):
        cmd = "cat lib/foo.dart"
        assert _find_boundary_violation(cmd, logger) is None

    def test_write_to_docs_not_blocked(self, logger):
        cmd = "echo hi > docs/notes.md"
        assert _find_boundary_violation(cmd, logger) is None

    def test_write_to_allowed_claude_hooks_not_blocked(self, logger):
        cmd = "cat > .claude/hooks/foo-hook.py <<'EOF'\nprint(1)\nEOF"
        assert _find_boundary_violation(cmd, logger) is None


# ============================================================================
# main() 整合：工具過濾 / subagent / 開發分支
# ============================================================================


class TestMainEntryPoint:
    """main() 流程整合測試：非 Bash 工具、subagent、開發分支跳過。"""

    def _run_main(self, monkeypatch, stdin_json, is_subagent=False, branch="main"):
        import io
        import json as json_mod

        monkeypatch.setattr(sys, "stdin", io.StringIO(json_mod.dumps(stdin_json)))
        with patch.object(hook_module, "is_subagent_environment", return_value=is_subagent), \
             patch.object(hook_module, "get_current_branch", return_value=branch), \
             patch.object(hook_module, "is_allowed_branch", return_value=(branch != "main")):
            return main()

    def test_non_bash_tool_allowed(self, monkeypatch):
        exit_code = self._run_main(
            monkeypatch,
            {"tool_name": "Read", "tool_input": {"file_path": "lib/foo.dart"}},
        )
        assert exit_code == 0

    def test_subagent_environment_allowed(self, monkeypatch):
        exit_code = self._run_main(
            monkeypatch,
            {"tool_name": "Bash", "tool_input": {"command": "cat > lib/foo.dart <<'EOF'\nx\nEOF"}, "agent_id": "sub-1"},
            is_subagent=True,
        )
        assert exit_code == 0

    def test_dev_branch_allowed(self, monkeypatch):
        exit_code = self._run_main(
            monkeypatch,
            {"tool_name": "Bash", "tool_input": {"command": "cat > lib/foo.dart <<'EOF'\nx\nEOF"}},
            branch="feat/some-feature",
        )
        assert exit_code == 0

    def test_main_thread_bash_violation_denied(self, monkeypatch):
        exit_code = self._run_main(
            monkeypatch,
            {"tool_name": "Bash", "tool_input": {"command": "cat > lib/foo.dart <<'EOF'\nclass Foo {}\nEOF"}},
            branch="main",
        )
        assert exit_code == 2

    def test_main_thread_legit_command_allowed(self, monkeypatch):
        exit_code = self._run_main(
            monkeypatch,
            {"tool_name": "Bash", "tool_input": {"command": "git status"}},
            branch="main",
        )
        assert exit_code == 0
