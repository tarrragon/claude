"""
Test: bash-git-add-broad-guard-hook（PC-092 執行期防線，add 側對稱補位）

0.2.1-W3-708：命令解析層（heredoc 剝離 / 換行正規化 / tokenize / 語句
切分 / stage 別名辨識）已收斂至 `.claude/lib/git_command_parse.py`，本檔
測試改為呼叫該共用模組（`find_git_invocations` / `strip_heredoc_bodies` /
`normalize_newlines_to_separators`），驗證意圖不變，僅呼叫介面調整。

驗證項目：
1. find_git_invocations（共用 lib）：cwd 隱含 / -C 形式 / `stage` 別名
   偵測，heredoc 內文剝離（含保底：找不到結束界線時還原原文）
2. _is_broad_add：判準改為「pathspec 是否可靜態列舉」，涵蓋 `.` / `./`
   / `:/` / 萬用字元 / 尾斜線目錄 / 廣域 flag / 短選項組合
3. normalize_newlines_to_separators（共用 lib）：多行命令中非首行的
   git add 不逃逸
4. main() 整合行為：
   - 廣域 add + 目前有未提交變更 → DENY（exit 2）
   - 廣域 add + 目前無未提交變更 → 放行（無汙染風險）
   - 精準 add（非廣域）不受影響，不論是否有未提交變更
   - worktree 隔離豁免
   - 非 Bash 工具 / 非 git add 命令不受影響
   - heredoc 內文提及廣域 add 字面不誤判
5. DENY 訊息：命令優先於理由、待篩選骨架命令不宣稱可直接複製、僅兩條路徑
"""

import io
import json
import sys
import importlib.util
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent))

_spec = importlib.util.spec_from_file_location(
    "bash_git_add_broad_guard_hook",
    HOOKS_DIR / "bash-git-add-broad-guard-hook.py",
)
hook_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook_module)

from lib.git_command_parse import (  # noqa: E402
    strip_heredoc_bodies as _strip_heredoc_bodies,
    normalize_newlines_to_separators as _normalize_newlines_to_separators,
)


def _find_git_add_invocations(command: str):
    """相容層：舊測試呼叫慣例包成共用 lib 的 find_git_invocations。"""
    result = hook_module.find_git_invocations(command, {"add"})
    return [] if result is None else result


_is_broad_add = hook_module._is_broad_add
FileStatus = hook_module.FileStatus
main = hook_module.main


def _run_hook(
    monkeypatch,
    command: str,
    uncommitted=None,
    is_worktree: bool = False,
    tool_name: str = "Bash",
) -> int:
    payload = {"tool_name": tool_name, "tool_input": {"command": command}}
    stdin_buffer = io.StringIO(json.dumps(payload))
    monkeypatch.setattr(sys, "stdin", stdin_buffer)
    monkeypatch.setattr(hook_module, "get_project_root", lambda: Path("/fake/project"))
    monkeypatch.setattr(
        hook_module, "get_uncommitted_files", lambda cwd=None: uncommitted or []
    )
    monkeypatch.setattr(hook_module, "_is_target_worktree", lambda cwd: is_worktree)
    return main()


def _fs(status: str, path: str) -> FileStatus:
    return FileStatus(status=status, file_path=path)


# ============================================================================
# _find_git_add_invocations：偵測形式
# ============================================================================


class TestFindGitAddInvocations:
    def test_cwd_implicit_form(self):
        result = _find_git_add_invocations("git add .")
        assert len(result) == 1
        assert result[0].statement == ["git", "add", "."]

    def test_dash_c_form(self):
        result = _find_git_add_invocations("git -C /repo add -A")
        assert len(result) == 1
        assert result[0].statement == ["git", "-C", "/repo", "add", "-A"]

    def test_stage_alias_detected(self):
        result = _find_git_add_invocations("git stage .")
        assert len(result) == 1
        assert result[0].statement == ["git", "stage", "."]

    def test_precise_add_still_found(self):
        result = _find_git_add_invocations("git add src/foo.py")
        assert len(result) == 1

    def test_git_status_not_add(self):
        assert _find_git_add_invocations("git status") == []

    def test_empty_command(self):
        assert _find_git_add_invocations("") == []

    def test_no_git_word(self):
        assert _find_git_add_invocations("pytest tests/") == []

    def test_chained_statement_detected(self):
        result = _find_git_add_invocations('git add . && git commit -m "x"')
        assert len(result) == 1
        assert result[0].statement[:2] == ["git", "add"]

    def test_quoted_text_not_misparsed_as_invocation(self):
        """引號內提及 'git add .' 的文字不應被拆成獨立語句誤判為命令本身。"""
        result = _find_git_add_invocations(
            'git commit -m "please remember git add . next time"'
        )
        assert result == []


# ============================================================================
# heredoc 內文剝離（防重演既有守衛的引用誤報 + 保底）
# ============================================================================


class TestHeredocStripping:
    def test_heredoc_body_stripped(self):
        command = (
            "ticket track append-log 0.0.0-W1-001 --section X <<'EOF'\n"
            "範例：git add . 是廣域形式\n"
            "EOF"
        )
        stripped = _strip_heredoc_bodies(command)
        assert "git add ." not in stripped

    def test_heredoc_content_does_not_trigger_invocation(self, monkeypatch, capsys):
        command = (
            "ticket track append-log 0.0.0-W1-001 --section X <<'EOF'\n"
            "範例：git add . 是廣域形式，應避免使用\n"
            "EOF"
        )
        exit_code = _run_hook(
            monkeypatch, command, uncommitted=[_fs("M ", "a.py")]
        )
        assert exit_code == 0
        assert capsys.readouterr().err == ""

    def test_non_heredoc_command_unaffected(self):
        command = "git add ."
        assert _strip_heredoc_bodies(command) == command

    def test_unterminated_heredoc_marker_falls_back_to_original(self):
        """引號內文字恰好長得像 heredoc 起始標記、但找不到結束界線時，
        必須還原整段原文，不可吞掉標記之後的真實命令（必修四保底）。"""
        command = 'echo "example: << FOO"\ngit add -A'
        result = _strip_heredoc_bodies(command)
        assert result == command
        assert "git add -A" in result


# ============================================================================
# 換行語句分隔（必修三：多行命令非首行的 add 不逃逸）
# ============================================================================


class TestNewlineStatementSeparation:
    def test_normalize_converts_bare_newline_to_semicolon(self):
        result = _normalize_newlines_to_separators("git status\ngit add -A")
        assert "\n" not in result
        assert ";" in result

    def test_newline_inside_quotes_preserved(self):
        result = _normalize_newlines_to_separators('git commit -m "line1\nline2"')
        assert result == 'git commit -m "line1\nline2"'

    def test_cd_then_newline_then_add_detected(self, monkeypatch):
        command = "cd /repo\ngit add -A"
        exit_code = _run_hook(
            monkeypatch, command, uncommitted=[_fs("M ", "a.py")]
        )
        assert exit_code == 2

    def test_status_then_newline_then_add_detected(self, monkeypatch):
        command = "git status\ngit add -A"
        exit_code = _run_hook(
            monkeypatch, command, uncommitted=[_fs("M ", "a.py")]
        )
        assert exit_code == 2

    def test_heredoc_then_newline_then_add_detected(self, monkeypatch):
        command = (
            "ticket track append-log 0.0.0-W1-001 --section X <<'EOF'\n"
            "一些說明文字\n"
            "EOF\n"
            "git add -A"
        )
        exit_code = _run_hook(
            monkeypatch, command, uncommitted=[_fs("M ", "a.py")]
        )
        assert exit_code == 2


# ============================================================================
# _is_broad_add：判準改為「是否可靜態列舉」
# ============================================================================


class TestIsBroadAdd:
    def test_dot_pathspec(self):
        result = _find_git_add_invocations("git add .")
        assert _is_broad_add(result[0]) is True

    def test_dot_slash_pathspec(self):
        result = _find_git_add_invocations("git add ./")
        assert _is_broad_add(result[0]) is True

    def test_top_of_worktree_magic_pathspec(self):
        result = _find_git_add_invocations("git add :/")
        assert _is_broad_add(result[0]) is True

    def test_wildcard_pathspec(self):
        result = _find_git_add_invocations("git add *")
        assert _is_broad_add(result[0]) is True

    def test_trailing_slash_directory_pathspec(self):
        result = _find_git_add_invocations("git add src/")
        assert _is_broad_add(result[0]) is True

    def test_stage_alias_dot_is_broad(self):
        result = _find_git_add_invocations("git stage .")
        assert _is_broad_add(result[0]) is True

    def test_dash_a_flag(self):
        result = _find_git_add_invocations("git add -A")
        assert _is_broad_add(result[0]) is True

    def test_all_long_flag(self):
        result = _find_git_add_invocations("git add --all")
        assert _is_broad_add(result[0]) is True

    def test_dash_u_flag(self):
        result = _find_git_add_invocations("git add -u")
        assert _is_broad_add(result[0]) is True

    def test_update_long_flag(self):
        result = _find_git_add_invocations("git add --update")
        assert _is_broad_add(result[0]) is True

    def test_combined_short_flag_with_a(self):
        result = _find_git_add_invocations("git add -vA")
        assert _is_broad_add(result[0]) is True

    def test_precise_pathspec_not_broad(self):
        result = _find_git_add_invocations("git add src/foo.py src/bar.py")
        assert _is_broad_add(result[0]) is False

    def test_dotfile_prefix_not_broad(self):
        """`./foo.py` 是具體檔案（僅前綴為 ./），非目錄列舉語意。"""
        result = _find_git_add_invocations("git add ./foo.py")
        assert _is_broad_add(result[0]) is False

    def test_bare_add_no_pathspec_is_broad(self):
        result = _find_git_add_invocations("git add")
        assert _is_broad_add(result[0]) is True


# ============================================================================
# main() 整合：廣域 add + 未提交變更 → DENY
# ============================================================================


class TestDenyWhenUncommittedExists:
    def test_broad_add_denied_when_uncommitted_exists(self, monkeypatch):
        exit_code = _run_hook(
            monkeypatch, "git add .", uncommitted=[_fs("M ", "a.py")]
        )
        assert exit_code == 2

    def test_deny_message_command_before_reason(self, monkeypatch, capsys):
        _run_hook(monkeypatch, "git add -A", uncommitted=[_fs("M ", "a.py")])
        err = capsys.readouterr().err
        command_pos = err.index("被攔截的命令")
        reason_pos = err.index("理由：")
        assert command_pos < reason_pos

    def test_deny_message_contains_review_skeleton(self, monkeypatch, capsys):
        _run_hook(
            monkeypatch,
            "git add -A",
            uncommitted=[_fs("M ", "docs/work-logs/foo.md"), _fs("??", "src/bar.py")],
        )
        err = capsys.readouterr().err
        assert "git add docs/work-logs/foo.md src/bar.py" in err

    def test_deny_message_does_not_claim_copyable(self, monkeypatch, capsys):
        """骨架命令不得宣稱「可直接複製」——讀者字面執行會 stage 到他人
        未提交的變更，複製出本 hook 要防的 PC-092 壞狀態本身。"""
        _run_hook(
            monkeypatch,
            "git add -A",
            uncommitted=[_fs("M ", "other-session-a.py"), _fs("M ", "other-session-b.py")],
        )
        err = capsys.readouterr().err
        assert "可直接複製" not in err
        assert "不要照原樣執行" in err
        assert "刪去不屬於本次工作的路徑" in err

    def test_deny_message_unlisted_remainder_not_framed_as_optional(
        self, monkeypatch, capsys
    ):
        """逾 10 筆的提示不得暗示「未列出可略過」，未列出的部分同樣需要
        判斷歸屬。"""
        entries = [_fs("M ", f"file{i}.py") for i in range(15)]
        _run_hook(monkeypatch, "git add -A", uncommitted=entries)
        err = capsys.readouterr().err
        assert "另有 5 筆同樣需要判斷歸屬" in err
        assert "請自行加入你 ticket 相關的部分" not in err

    def test_deny_message_rename_uses_new_path(self, monkeypatch, capsys):
        _run_hook(
            monkeypatch,
            "git add .",
            uncommitted=[_fs("R ", "old.py -> new.py")],
        )
        err = capsys.readouterr().err
        assert "git add new.py" in err

    def test_deny_message_only_two_exits_no_third(self, monkeypatch, capsys):
        _run_hook(monkeypatch, "git add .", uncommitted=[_fs("M ", "a.py")])
        err = capsys.readouterr().err
        assert "沒有第三條" in err
        assert "worktree" in err.lower() or "worktree 隔離" in err

    def test_deny_message_cites_four_incident_evidence(self, monkeypatch, capsys):
        _run_hook(monkeypatch, "git add .", uncommitted=[_fs("M ", "a.py")])
        err = capsys.readouterr().err
        assert "四次實證" in err

    def test_deny_message_no_dispatch_phrasing(self, monkeypatch, capsys):
        """判準已移除 dispatch-active 依賴，訊息不應再提及「先確認無他人
        活躍派發」這種與開頭宣告矛盾的死路句。"""
        _run_hook(monkeypatch, "git add .", uncommitted=[_fs("M ", "a.py")])
        err = capsys.readouterr().err
        assert "先確認目前無他人活躍派發" not in err

    def test_deny_message_reason_has_space_before_pc_id(self, monkeypatch, capsys):
        """中英交界須有空格：「造成 PC-092」不可黏成「造成PC-092」。"""
        _run_hook(monkeypatch, "git add .", uncommitted=[_fs("M ", "a.py")])
        err = capsys.readouterr().err
        assert "造成PC-092" not in err
        assert "造成 PC-092" in err


# ============================================================================
# main() 整合：廣域 add + 無未提交變更 → 放行
# ============================================================================


class TestAllowWhenNoUncommitted:
    def test_broad_add_allowed_when_no_uncommitted(self, monkeypatch, capsys):
        exit_code = _run_hook(monkeypatch, "git add .", uncommitted=[])
        assert exit_code == 0
        assert capsys.readouterr().err == ""


# ============================================================================
# main() 整合：worktree 隔離豁免
# ============================================================================


class TestWorktreeExemption:
    def test_worktree_exempt_even_with_uncommitted(self, monkeypatch, capsys):
        exit_code = _run_hook(
            monkeypatch,
            "git add .",
            uncommitted=[_fs("M ", "a.py")],
            is_worktree=True,
        )
        assert exit_code == 0
        assert capsys.readouterr().err == ""


# ============================================================================
# main() 整合：精準 add / 非 Bash / 非 git add 不受影響
# ============================================================================


class TestUnaffectedCommands:
    def test_precise_add_allowed_even_with_uncommitted(self, monkeypatch, capsys):
        exit_code = _run_hook(
            monkeypatch,
            "git add src/foo.py src/bar.py",
            uncommitted=[_fs("M ", "other.py")],
        )
        assert exit_code == 0
        assert capsys.readouterr().err == ""

    def test_non_bash_tool_allowed(self, monkeypatch):
        exit_code = _run_hook(
            monkeypatch, "git add .", uncommitted=[_fs("M ", "a.py")], tool_name="Edit"
        )
        assert exit_code == 0

    def test_non_git_command_allowed(self, monkeypatch):
        exit_code = _run_hook(monkeypatch, "pytest tests/ -q", uncommitted=[_fs("M ", "a.py")])
        assert exit_code == 0

    def test_git_commit_only_allowed(self, monkeypatch):
        exit_code = _run_hook(
            monkeypatch, 'git commit -m "x" -- a.py', uncommitted=[_fs("M ", "a.py")]
        )
        assert exit_code == 0

    def test_empty_command_allowed(self, monkeypatch):
        exit_code = _run_hook(monkeypatch, "", uncommitted=[_fs("M ", "a.py")])
        assert exit_code == 0
