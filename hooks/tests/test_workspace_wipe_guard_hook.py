"""
Test: workspace-wipe-guard-hook（0.2.1-W3-485 建立、0.2.1-W3-491 補齊變體）

驗證項目：
1. 五種偵測器（stash 建立形式 / checkout 丟棄整個工作區含帶 ref 前綴形式 /
   reset --hard / clean -f 含單獨 -f / restore 丟棄整個工作區含 --staged
   排除）各自的觸發與豁免形式
2. main() 整合行為：
   - 並行期（dispatch_count > 0）五種操作各自觸發 → DENY（exit 2），訊息含
     操作名稱與安全替代
   - 非並行期（dispatch_count == 0）→ WARN（exit 0 + stderr）
   - 帶 pathspec 的安全形式（含 `git restore --staged .`）在並行期仍放行
     （exit 0，無輸出）
   - 非 Bash 工具 / 不含五種操作的命令不受影響

Source: ticket 0.2.1-W3-485（初版四操作）、0.2.1-W3-491（補 restore / 單獨
clean -f / checkout 帶 ref 前綴形式）
"""

import io
import json
import logging
import sys
import importlib.util
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent))

_spec = importlib.util.spec_from_file_location(
    "workspace_wipe_guard_hook",
    HOOKS_DIR / "workspace-wipe-guard-hook.py",
)
hook_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook_module)

_is_stash_wipe = hook_module._is_stash_wipe
_is_checkout_wipe = hook_module._is_checkout_wipe
_is_reset_hard = hook_module._is_reset_hard
_is_clean_force = hook_module._is_clean_force
_is_restore_wipe = hook_module._is_restore_wipe
_detect_operation = hook_module._detect_operation
main = hook_module.main


def _run_hook(
    monkeypatch,
    command: str,
    dispatch_count: int = 0,
    tool_name: str = "Bash",
    main_repo_dirty: bool = False,
) -> int:
    """以 monkeypatch 模擬 stdin + 依賴（dispatch 計數 + 主 repo 未提交狀態），執行 main()。

    main_repo_dirty 預設 False（主 repo 乾淨），維持既有測試僅測「並行期」
    這一條 DENY 理由時的行為不受新條件干擾。
    """
    payload = {"tool_name": tool_name, "tool_input": {"command": command}}
    stdin_buffer = io.StringIO(json.dumps(payload))
    monkeypatch.setattr(sys, "stdin", stdin_buffer)
    monkeypatch.setattr(hook_module, "get_project_root", lambda: Path("/fake/project"))
    monkeypatch.setattr(
        hook_module,
        "_get_active_dispatch_count",
        lambda root, logger: dispatch_count,
    )
    monkeypatch.setattr(
        hook_module,
        "_has_main_repo_uncommitted_tracked_changes",
        lambda root, logger: main_repo_dirty,
    )
    return main()


# ============================================================================
# _is_stash_wipe：建立形式 vs 安全子命令 / pathspec 豁免
# ============================================================================


class TestIsStashWipe:
    @pytest.mark.parametrize(
        "command",
        [
            "git stash",
            "git stash push",
            "git stash save",
            "git stash -u",
            "git stash --include-untracked",
            "git -C /repo stash",
        ],
    )
    def test_create_forms_detected(self, command):
        assert _is_stash_wipe(command) is True

    @pytest.mark.parametrize(
        "command",
        [
            "git stash pop",
            "git stash apply",
            "git stash list",
            "git stash show",
            "git stash drop",
            "git stash clear",
            "git stash branch foo",
            "git stash push -- src/foo.py",
        ],
    )
    def test_safe_forms_not_detected(self, command):
        assert _is_stash_wipe(command) is False


# ============================================================================
# _is_checkout_wipe：整個工作區（含帶 ref 前綴形式）vs 指定檔案
# ============================================================================


class TestIsCheckoutWipe:
    @pytest.mark.parametrize(
        "command",
        [
            "git checkout -- .",
            "git checkout .",
            "git checkout -- . && echo done",
            "(cd /repo && git checkout -- .)",
            "git checkout HEAD -- .",
            "git checkout main -- .",
        ],
    )
    def test_wipe_forms_detected(self, command):
        assert _is_checkout_wipe(command) is True

    @pytest.mark.parametrize(
        "command",
        [
            "git checkout -- src/foo.py",
            "git checkout -- .gitignore",
            "git checkout main",
            "git checkout -b feat/x",
        ],
    )
    def test_specific_file_forms_not_detected(self, command):
        assert _is_checkout_wipe(command) is False


# ============================================================================
# _is_reset_hard：--hard 不支援 pathspec，無安全形式
# ============================================================================


class TestIsResetHard:
    @pytest.mark.parametrize(
        "command",
        [
            "git reset --hard",
            "git reset --hard HEAD~1",
            "git reset --hard origin/main",
        ],
    )
    def test_hard_forms_detected(self, command):
        assert _is_reset_hard(command) is True

    @pytest.mark.parametrize(
        "command",
        [
            "git reset HEAD",
            "git reset --soft HEAD~1",
            "git reset -- file.py",
        ],
    )
    def test_non_hard_forms_not_detected(self, command):
        assert _is_reset_hard(command) is False


# ============================================================================
# _is_clean_force：force 旗標任意組合（含單獨 -f）vs pathspec 豁免
# ============================================================================


class TestIsCleanForce:
    @pytest.mark.parametrize(
        "command",
        [
            "git clean -fd",
            "git clean -df",
            "git clean -f -d",
            "git clean --force -d",
            "git clean -fdx",
            "git clean -f",
            "git clean --force",
        ],
    )
    def test_force_forms_detected(self, command):
        assert _is_clean_force(command) is True

    @pytest.mark.parametrize(
        "command",
        [
            "git clean -fd -- some/dir",
            "git clean -f -- some/dir",
            "git clean -n",
        ],
    )
    def test_pathspec_or_no_force_not_detected(self, command):
        assert _is_clean_force(command) is False


# ============================================================================
# _is_restore_wipe：整個工作區 vs 指定檔案 vs --staged（純 index）排除
# ============================================================================


class TestIsRestoreWipe:
    @pytest.mark.parametrize(
        "command",
        [
            "git restore .",
            "git restore --worktree .",
            "git restore --source=HEAD~1 .",
            "git restore -s HEAD~1 .",
            "git restore --staged --worktree .",
        ],
    )
    def test_wipe_forms_detected(self, command):
        assert _is_restore_wipe(command) is True

    @pytest.mark.parametrize(
        "command",
        [
            "git restore -- src/foo.py",
            "git restore --staged -- src/foo.py",
        ],
    )
    def test_specific_file_forms_not_detected(self, command):
        assert _is_restore_wipe(command) is False

    def test_staged_only_excluded_index_operation_not_detected(self):
        """`--staged` 且未帶 `--worktree`：只動 index，風險模型與其餘操作不同，刻意排除。"""
        assert _is_restore_wipe("git restore --staged .") is False


# ============================================================================
# main() 整合：並行期 DENY（五種操作各一例，含新增變體）
# ============================================================================


class TestParallelPeriodDeny:
    @pytest.mark.parametrize(
        "command,op_name",
        [
            ("git stash", "git stash"),
            ("git checkout -- .", "git checkout -- ."),
            ("git checkout HEAD -- .", "git checkout -- ."),
            ("git reset --hard", "git reset --hard"),
            ("git clean -fd", "git clean -f"),
            ("git clean -f", "git clean -f"),
            ("git restore .", "git restore ."),
        ],
    )
    def test_denied_when_parallel_active(self, monkeypatch, capsys, command, op_name):
        exit_code = _run_hook(monkeypatch, command, dispatch_count=2)
        assert exit_code == 2
        err = capsys.readouterr().err
        assert op_name in err

    def test_deny_message_contains_safe_alternative(self, monkeypatch, capsys):
        _run_hook(monkeypatch, "git stash", dispatch_count=1)
        err = capsys.readouterr().err
        assert "git worktree" in err
        assert "git diff" in err

    def test_deny_message_contains_dispatch_count(self, monkeypatch, capsys):
        _run_hook(monkeypatch, "git reset --hard", dispatch_count=3)
        err = capsys.readouterr().err
        assert "3" in err

    def test_restore_deny_message_mentions_staged_alternative(self, monkeypatch, capsys):
        """restore 的多行安全提示需完整呈現（含 --staged 替代方案）。"""
        _run_hook(monkeypatch, "git restore .", dispatch_count=1)
        err = capsys.readouterr().err
        assert "git restore -- <file>" in err
        assert "git restore --staged ." in err


# ============================================================================
# main() 整合：非並行期 WARN
# ============================================================================


class TestNonParallelPeriodWarn:
    def test_warned_when_no_parallel(self, monkeypatch, capsys):
        exit_code = _run_hook(monkeypatch, "git stash", dispatch_count=0)
        assert exit_code == 0
        err = capsys.readouterr().err
        assert "提醒" in err

    def test_warn_does_not_block(self, monkeypatch, capsys):
        exit_code = _run_hook(monkeypatch, "git clean -fd", dispatch_count=0)
        assert exit_code == 0


# ============================================================================
# main() 整合：安全形式在並行期仍放行
# ============================================================================


class TestSafeFormsPassThroughEvenWhenParallel:
    @pytest.mark.parametrize(
        "command",
        [
            "git stash push -- src/foo.py",
            "git stash pop",
            "git checkout -- src/foo.py",
            "git reset -- file.py",
            "git clean -fd -- some/dir",
            "git restore -- src/foo.py",
            "git restore --staged .",
        ],
    )
    def test_safe_forms_allowed_even_when_parallel(self, monkeypatch, capsys, command):
        exit_code = _run_hook(monkeypatch, command, dispatch_count=5)
        assert exit_code == 0
        assert capsys.readouterr().err == ""


# ============================================================================
# main() 整合：非 Bash / 不含五種操作不受影響
# ============================================================================


class TestUnaffectedCommands:
    def test_non_bash_tool_allowed(self, monkeypatch, capsys):
        exit_code = _run_hook(monkeypatch, "git stash", dispatch_count=5, tool_name="Edit")
        assert exit_code == 0

    def test_unrelated_git_command_allowed(self, monkeypatch, capsys):
        exit_code = _run_hook(monkeypatch, "git status", dispatch_count=5)
        assert exit_code == 0

    def test_non_git_command_allowed(self, monkeypatch, capsys):
        exit_code = _run_hook(monkeypatch, "pytest tests/ -q", dispatch_count=5)
        assert exit_code == 0

    def test_empty_command_allowed(self, monkeypatch, capsys):
        exit_code = _run_hook(monkeypatch, "", dispatch_count=5)
        assert exit_code == 0


# ============================================================================
# 註冊點：fail_closed=True（0.2.1-W3-507）
# ============================================================================


class TestRegistrationFailClosed:
    def test_registration_uses_fail_closed_true(self):
        """`__main__` 區塊須以 fail_closed=True 呼叫 run_hook_safely，執行期
        異常時保守 DENY 而非 fail-open 放行（本守衛防的是不可逆資料遺失）。
        """
        source = (HOOKS_DIR / "workspace-wipe-guard-hook.py").read_text(encoding="utf-8")
        assert 'run_hook_safely(main, "workspace-wipe-guard", fail_closed=True)' in source

    def test_unhandled_exception_in_main_returns_2_via_fail_closed(self, monkeypatch):
        """main() 拋出未預期例外時，run_hook_safely(fail_closed=True) 回傳 2 而非 1。"""

        def _boom(command):
            raise RuntimeError("unexpected failure")

        monkeypatch.setattr(hook_module, "_detect_operation", _boom)
        monkeypatch.setattr(
            sys,
            "stdin",
            io.StringIO(json.dumps({"tool_name": "Bash", "tool_input": {"command": "git stash"}})),
        )

        exit_code = hook_module.run_hook_safely(
            hook_module.main, "workspace-wipe-guard-test-fail-closed", fail_closed=True
        )

        assert exit_code == 2

    def test_unhandled_exception_in_main_returns_1_via_fail_open(self, monkeypatch):
        """對照組：fail_closed=False 時同一例外仍回傳 1（既有 wrapper 語意不變）。"""

        def _boom(command):
            raise RuntimeError("unexpected failure")

        monkeypatch.setattr(hook_module, "_detect_operation", _boom)
        monkeypatch.setattr(
            sys,
            "stdin",
            io.StringIO(json.dumps({"tool_name": "Bash", "tool_input": {"command": "git stash"}})),
        )

        exit_code = hook_module.run_hook_safely(
            hook_module.main, "workspace-wipe-guard-test-fail-open", fail_closed=False
        )

        assert exit_code == 1


# ============================================================================
# _get_active_dispatch_count：讀取失敗保守回傳 None（0.2.1-W3-507）
# ============================================================================


class TestGetActiveDispatchCountReadFailure:
    def test_read_failure_returns_none_not_zero(self, monkeypatch):
        """讀取失敗時回傳 None（無法判定），不得回傳 0（會被誤讀為非並行期）。"""

        def _raise(root):
            raise json.JSONDecodeError("bad json", "doc", 0)

        monkeypatch.setattr(hook_module, "get_active_dispatches", _raise)
        logger = logging.getLogger("test-workspace-wipe-guard-read-failure")

        result = hook_module._get_active_dispatch_count(Path("/fake/project"), logger)

        assert result is None

    def test_read_failure_logs_warning(self, monkeypatch, caplog):
        """讀取失敗時記錄 warning 日誌（quality-baseline 規則 4 雙通道要求）。"""

        def _raise(root):
            raise OSError("cannot read dispatch-active.json")

        monkeypatch.setattr(hook_module, "get_active_dispatches", _raise)
        logger_name = "test-workspace-wipe-guard-log-warning"
        logger = logging.getLogger(logger_name)

        with caplog.at_level(logging.WARNING, logger=logger_name):
            hook_module._get_active_dispatch_count(Path("/fake/project"), logger)

        assert any("dispatch-active.json" in record.message for record in caplog.records)

    def test_success_path_still_returns_int(self, monkeypatch):
        """讀取成功時仍回傳實際計數（int），非受影響路徑不改變行為。"""
        monkeypatch.setattr(hook_module, "get_active_dispatches", lambda root: [1, 2, 3])
        logger = logging.getLogger("test-workspace-wipe-guard-success")

        result = hook_module._get_active_dispatch_count(Path("/fake/project"), logger)

        assert result == 3


# ============================================================================
# main() 整合：讀取失敗時保守 DENY，不 fallback 為非並行期（0.2.1-W3-507）
# ============================================================================


class TestMainConservativeOnDispatchReadFailure:
    def test_denied_when_dispatch_read_fails(self, monkeypatch, capsys):
        """dispatch-active.json 讀取失敗時，main() 保守 DENY（不 fallback 為 WARN 放行）。"""
        payload = {"tool_name": "Bash", "tool_input": {"command": "git stash"}}
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        monkeypatch.setattr(hook_module, "get_project_root", lambda: Path("/fake/project"))

        def _raise(root):
            raise OSError("disk error")

        monkeypatch.setattr(hook_module, "get_active_dispatches", _raise)

        exit_code = main()

        assert exit_code == 2
        err = capsys.readouterr().err
        assert "git stash" in err
        assert "無法讀取並行派發記錄" in err

    def test_denied_message_explains_read_failure_not_fabricated_count(self, monkeypatch, capsys):
        """讀取失敗的 DENY 訊息須說明「讀取失敗」，不得虛構一個計數。"""
        payload = {"tool_name": "Bash", "tool_input": {"command": "git reset --hard"}}
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        monkeypatch.setattr(hook_module, "get_project_root", lambda: Path("/fake/project"))
        monkeypatch.setattr(
            hook_module, "get_active_dispatches", lambda root: (_ for _ in ()).throw(OSError("x"))
        )

        main()

        err = capsys.readouterr().err
        assert "保守視為並行期阻擋" in err


# ============================================================================
# _has_main_repo_uncommitted_tracked_changes：主 repo 未提交 tracked 變更偵測
# （0.2.1-W3-760：DENY 條件擴充為「並行期 OR 主 repo 有未提交 tracked 變更」）
# ============================================================================


class TestHasMainRepoUncommittedTrackedChanges:
    def test_tracked_change_returns_true(self, monkeypatch):
        monkeypatch.setattr(
            hook_module,
            "get_uncommitted_files",
            lambda cwd=None: [hook_module.FileStatus(status=" M", file_path="foo.py")],
        )
        logger = logging.getLogger("test-main-repo-dirty-tracked")

        result = hook_module._has_main_repo_uncommitted_tracked_changes(Path("/fake/project"), logger)

        assert result is True

    def test_untracked_only_returns_false(self, monkeypatch):
        """只有未追蹤新檔案（`??`）不算 tracked 變更，不觸發本條件。"""
        monkeypatch.setattr(
            hook_module,
            "get_uncommitted_files",
            lambda cwd=None: [hook_module.FileStatus(status="??", file_path="new.txt")],
        )
        logger = logging.getLogger("test-main-repo-dirty-untracked-only")

        result = hook_module._has_main_repo_uncommitted_tracked_changes(Path("/fake/project"), logger)

        assert result is False

    def test_clean_returns_false(self, monkeypatch):
        monkeypatch.setattr(hook_module, "get_uncommitted_files", lambda cwd=None: [])
        logger = logging.getLogger("test-main-repo-dirty-clean")

        result = hook_module._has_main_repo_uncommitted_tracked_changes(Path("/fake/project"), logger)

        assert result is False

    def test_read_failure_returns_none_not_false(self, monkeypatch):
        """讀取失敗時回傳 None（無法判定），不得回傳 False（會被誤讀為乾淨）。"""

        def _raise(cwd=None):
            raise OSError("cannot read git status")

        monkeypatch.setattr(hook_module, "get_uncommitted_files", _raise)
        logger = logging.getLogger("test-main-repo-dirty-read-failure")

        result = hook_module._has_main_repo_uncommitted_tracked_changes(Path("/fake/project"), logger)

        assert result is None

    def test_read_failure_logs_warning(self, monkeypatch, caplog):
        """讀取失敗時記錄 warning 日誌（quality-baseline 規則 4 雙通道要求）。"""

        def _raise(cwd=None):
            raise OSError("cannot read git status")

        monkeypatch.setattr(hook_module, "get_uncommitted_files", _raise)
        logger_name = "test-main-repo-dirty-log-warning"
        logger = logging.getLogger(logger_name)

        with caplog.at_level(logging.WARNING, logger=logger_name):
            hook_module._has_main_repo_uncommitted_tracked_changes(Path("/fake/project"), logger)

        assert any("git status" in record.message for record in caplog.records)


# ============================================================================
# _detect_operation：heredoc 內作為資料引用的操作名稱不觸發偵測（0.2.1-W3-684）
# ============================================================================


class TestDetectOperationHeredocDataReference:
    def test_operation_name_inside_heredoc_body_not_detected(self):
        """heredoc 內文引用操作名稱字面（如貼一段含 `git stash` 的日誌原文）
        屬 CLI 引數的資料，不是實際要執行的命令，不應觸發偵測。
        """
        command = (
            'ticket track append-log 0.2.1-W3-510 --section "Solution" '
            '"$(cat <<\'EOF\'\n'
            '守衛日誌原文：操作=git stash，活躍派發數=2\n'
            '亦涵蓋 git reset --hard 與 git clean -f 的日誌片段\n'
            'EOF\n'
            ')"'
        )
        assert _detect_operation(command) is None

    def test_real_operation_after_heredoc_still_detected(self):
        """heredoc 之後接的真實破壞性操作仍須被偵測（剝離不可過度吞掉後續內容）。"""
        command = (
            'cat <<\'EOF\'\n'
            '這段引用 git stash 僅為說明文字\n'
            'EOF\n'
            '\ngit reset --hard'
        )
        assert _detect_operation(command) == (
            "git reset --hard",
            hook_module._OPERATIONS[2][2],
        )

    def test_real_operation_still_detected_without_heredoc(self):
        """對照組：不含 heredoc 的真實操作行為不變（無回歸）。"""
        assert _detect_operation("git stash") == (
            "git stash",
            hook_module._OPERATIONS[0][2],
        )

    def test_main_allows_heredoc_data_reference_even_when_parallel(self, monkeypatch, capsys):
        """整合層級：heredoc 內資料引用即使在並行期也應放行（不誤判為真實操作）。"""
        command = (
            'ticket track append-log 0.2.1-W3-510 --section "Solution" '
            '"$(cat <<\'EOF\'\n'
            '守衛日誌原文：操作=git clean -f\n'
            'EOF\n'
            ')"'
        )
        exit_code = _run_hook(monkeypatch, command, dispatch_count=3)
        assert exit_code == 0
        assert capsys.readouterr().err == ""

    def test_main_still_denies_real_operation_when_parallel(self, monkeypatch, capsys):
        """整合層級對照組：真實操作在並行期仍被 DENY（無回歸）。"""
        exit_code = _run_hook(monkeypatch, "git reset --hard", dispatch_count=3)
        assert exit_code == 2
        err = capsys.readouterr().err
        assert "git reset --hard" in err


# ============================================================================
# main() 整合：主 repo 有未提交 tracked 變更時無條件 DENY（不限並行期）
# （0.2.1-W3-760：PC-019 事故鏈第 4 步發生於 agent 完成後，
#   dispatch-active.json 已清空，此時仍須阻擋）
# ============================================================================


class TestMainRepoDirtyDeny:
    def test_denied_when_main_repo_dirty_even_without_parallel(self, monkeypatch, capsys):
        """非並行期（dispatch_count=0）但主 repo 有未提交 tracked 變更 -> DENY。"""
        exit_code = _run_hook(monkeypatch, "git stash", dispatch_count=0, main_repo_dirty=True)

        assert exit_code == 2
        err = capsys.readouterr().err
        assert "主 repo 有未提交變更" in err

    def test_warn_when_main_repo_clean_and_non_parallel(self, monkeypatch, capsys):
        """非並行期且主 repo 乾淨 -> 維持既有 WARN 行為，不擾正常流程。"""
        exit_code = _run_hook(monkeypatch, "git stash", dispatch_count=0, main_repo_dirty=False)

        assert exit_code == 0
        err = capsys.readouterr().err
        assert "提醒" in err

    def test_deny_message_distinguishes_two_trigger_reasons(self, monkeypatch, capsys):
        """兩條件同時成立時，DENY 訊息須同時列出兩種觸發理由。"""
        exit_code = _run_hook(monkeypatch, "git reset --hard", dispatch_count=2, main_repo_dirty=True)

        assert exit_code == 2
        err = capsys.readouterr().err
        assert "並行派發中" in err
        assert "主 repo 有未提交變更" in err

    def test_deny_message_only_main_repo_reason_when_not_parallel(self, monkeypatch, capsys):
        """僅主 repo 髒污觸發時，訊息不應虛構「並行派發中」理由。"""
        exit_code = _run_hook(monkeypatch, "git clean -f", dispatch_count=0, main_repo_dirty=True)

        assert exit_code == 2
        err = capsys.readouterr().err
        assert "主 repo 有未提交變更" in err
        assert "並行派發中" not in err

    def test_denied_when_main_repo_dirty_read_fails_conservative(self, monkeypatch, capsys):
        """主 repo 未提交狀態讀取失敗時保守 DENY（None 視為有變更），不 fallback 為 WARN。"""
        exit_code = _run_hook(monkeypatch, "git checkout -- .", dispatch_count=0, main_repo_dirty=None)

        assert exit_code == 2
