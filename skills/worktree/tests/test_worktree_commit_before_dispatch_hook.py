"""
worktree-commit-before-dispatch-hook 測試套件（0.2.1-W3-761）

覆蓋範圍：PC-019 主 repo 髒污判定由 DENY 降為 WARN 後的行為
（原 exit 2 + BLOCK_MESSAGE 改為 exit 0 + WARN_MESSAGE stderr 提醒），
以及 origin/main 落後超門檻的 DENY 分支維持不變。
"""

import importlib.util
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_HOOK_FILE = (
    Path(__file__).resolve().parent.parent
    / "hooks"
    / "worktree-commit-before-dispatch-hook.py"
)
_spec = importlib.util.spec_from_file_location(
    "worktree_commit_before_dispatch_hook", _HOOK_FILE
)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)


def _diff_result(stdout=""):
    return MagicMock(returncode=0, stdout=stdout, stderr="")


@pytest.fixture(autouse=True)
def _stub_hook_logging():
    # setup_hook_logging 內部會發出 git rev-parse 偵測 log 目錄位置的真實
    # subprocess 呼叫；測試以 hook.subprocess.run 的 side_effect 序列模擬
    # git diff 呼叫時，這些呼叫會被誤消耗，故以固定 logger 取代避免干擾。
    with patch.object(
        hook, "setup_hook_logging",
        return_value=logging.getLogger("test-worktree-commit-before-dispatch"),
    ):
        yield


class TestMainSkipConditions:
    def test_non_worktree_isolation_passes(self):
        data = {"tool_input": {"isolation": "none"}}
        with patch.object(hook, "read_json_from_stdin", return_value=data):
            assert hook.main() == 0

    def test_missing_isolation_passes(self):
        data = {"tool_input": {}}
        with patch.object(hook, "read_json_from_stdin", return_value=data):
            assert hook.main() == 0

    def test_empty_stdin_passes(self):
        with patch.object(hook, "read_json_from_stdin", return_value=None):
            assert hook.main() == 0


class TestPC019DowngradedToWarn:
    """0.2.1-W3-761：主 repo 髒污不再 DENY，改為 exit 0 + stderr 提醒。"""

    def test_dirty_repo_exits_zero_with_stderr_warning(self, capsys):
        data = {"tool_input": {"isolation": "worktree"}}
        with patch.object(hook, "read_json_from_stdin", return_value=data), patch.object(
            hook, "_check_origin_behind", return_value=0
        ), patch.object(
            hook.subprocess,
            "run",
            side_effect=[_diff_result("src/a.py\n"), _diff_result("")],
        ):
            rc = hook.main()
        assert rc == 0
        captured = capsys.readouterr()
        assert "[PC-019 提醒]" in captured.err
        assert "src/a.py" in captured.err

    def test_clean_repo_exits_zero_without_warning(self, capsys):
        data = {"tool_input": {"isolation": "worktree"}}
        with patch.object(hook, "read_json_from_stdin", return_value=data), patch.object(
            hook, "_check_origin_behind", return_value=0
        ), patch.object(
            hook.subprocess,
            "run",
            side_effect=[_diff_result(""), _diff_result("")],
        ):
            rc = hook.main()
        assert rc == 0
        captured = capsys.readouterr()
        assert "PC-019" not in captured.err

    def test_git_diff_failure_passes(self):
        data = {"tool_input": {"isolation": "worktree"}}
        with patch.object(hook, "read_json_from_stdin", return_value=data), patch.object(
            hook, "_check_origin_behind", return_value=0
        ), patch.object(
            hook.subprocess, "run", side_effect=FileNotFoundError("git missing")
        ):
            assert hook.main() == 0


class TestOriginBehindDenyUnchanged:
    """W4-008：origin/main 落後超門檻仍 exit 2，本票不動。"""

    def test_over_threshold_still_blocks(self, capsys):
        data = {"tool_input": {"isolation": "worktree"}}
        with patch.object(hook, "read_json_from_stdin", return_value=data), patch.object(
            hook, "_check_origin_behind", return_value=hook.LAG_DENY_THRESHOLD
        ) as behind:
            rc = hook.main()
        assert rc == 2
        captured = capsys.readouterr()
        assert "W4-008 防護" in captured.err
        assert "禁止派發" in captured.err
        behind.assert_called_once()

    def test_under_threshold_does_not_block(self):
        data = {"tool_input": {"isolation": "worktree"}}
        with patch.object(hook, "read_json_from_stdin", return_value=data), patch.object(
            hook, "_check_origin_behind", return_value=hook.LAG_DENY_THRESHOLD - 1
        ), patch.object(
            hook.subprocess,
            "run",
            side_effect=[_diff_result(""), _diff_result("")],
        ):
            assert hook.main() == 0


class TestTargetTicketSyncCheck:
    """目標票 md 同步檢查：有差異阻擋 / 無差異放行 / 抽不到 ID 放行 / git 失敗放行。"""

    def _data(self, prompt="Ticket: 0.1.0-W1-001 做點事"):
        return {"tool_input": {"isolation": "worktree", "prompt": prompt}}

    def test_ticket_md_diff_blocks_dispatch(self, capsys, tmp_path):
        fake_root = tmp_path
        md_path = fake_root / "docs" / "work-logs" / "tickets" / "0.1.0-W1-001.md"
        md_path.parent.mkdir(parents=True)
        md_path.write_text("stub")

        with patch.object(hook, "read_json_from_stdin", return_value=self._data()), \
             patch.object(hook, "get_project_root", return_value=fake_root), \
             patch.object(
                 hook.subprocess, "run",
                 return_value=MagicMock(returncode=0, stdout="docs/work-logs/tickets/0.1.0-W1-001.md\n", stderr=""),
             ):
            rc = hook.main()
        assert rc == 2
        captured = capsys.readouterr()
        assert "目標票同步防護" in captured.err
        assert "git push" in captured.err

    def test_ticket_md_no_diff_passes(self, tmp_path):
        fake_root = tmp_path
        md_path = fake_root / "docs" / "work-logs" / "tickets" / "0.1.0-W1-001.md"
        md_path.parent.mkdir(parents=True)
        md_path.write_text("stub")

        with patch.object(hook, "read_json_from_stdin", return_value=self._data()), \
             patch.object(hook, "get_project_root", return_value=fake_root), \
             patch.object(hook, "_check_origin_behind", return_value=0), \
             patch.object(
                 hook.subprocess, "run",
                 side_effect=[
                     MagicMock(returncode=0, stdout="", stderr=""),  # git diff --name-only (sync check)
                     _diff_result(""),  # unstaged
                     _diff_result(""),  # staged
                 ],
             ):
            rc = hook.main()
        assert rc == 0

    def test_no_ticket_id_extracted_passes(self):
        data = {"tool_input": {"isolation": "worktree", "prompt": "沒有票號的一般派發"}}
        with patch.object(hook, "read_json_from_stdin", return_value=data), \
             patch.object(hook, "_check_origin_behind", return_value=0), \
             patch.object(
                 hook.subprocess, "run",
                 side_effect=[_diff_result(""), _diff_result("")],
             ):
            rc = hook.main()
        assert rc == 0

    def test_git_diff_failure_passes(self, tmp_path):
        fake_root = tmp_path
        md_path = fake_root / "docs" / "work-logs" / "tickets" / "0.1.0-W1-001.md"
        md_path.parent.mkdir(parents=True)
        md_path.write_text("stub")

        with patch.object(hook, "read_json_from_stdin", return_value=self._data()), \
             patch.object(hook, "get_project_root", return_value=fake_root), \
             patch.object(hook, "_check_origin_behind", return_value=0), \
             patch.object(
                 hook.subprocess, "run",
                 side_effect=[
                     FileNotFoundError("git missing"),  # sync check fails open
                     _diff_result(""),  # unstaged
                     _diff_result(""),  # staged
                 ],
             ):
            rc = hook.main()
        assert rc == 0


class TestOriginBehindWarningEmission:
    """0 < lag < 閾值：無論主 repo 是否髒污都經 emit_hook_output 單點發出（本票耦合點決策）。"""

    def test_lag_warning_emitted_when_repo_clean(self):
        data = {"tool_input": {"isolation": "worktree"}}
        with patch.object(hook, "read_json_from_stdin", return_value=data), patch.object(
            hook, "_check_origin_behind", return_value=3
        ), patch.object(
            hook.subprocess,
            "run",
            side_effect=[_diff_result(""), _diff_result("")],
        ), patch.object(hook, "emit_hook_output") as emit:
            rc = hook.main()
        assert rc == 0
        emit.assert_called_once()
        assert emit.call_args.kwargs["audience"] == "pm_only"
        assert "W3-007 警告" in emit.call_args.kwargs["additional_context"]

    def test_lag_warning_emitted_when_repo_dirty(self, capsys):
        data = {"tool_input": {"isolation": "worktree"}}
        with patch.object(hook, "read_json_from_stdin", return_value=data), patch.object(
            hook, "_check_origin_behind", return_value=3
        ), patch.object(
            hook.subprocess,
            "run",
            side_effect=[_diff_result("src/a.py\n"), _diff_result("")],
        ), patch.object(hook, "emit_hook_output") as emit:
            rc = hook.main()
        assert rc == 0
        emit.assert_called_once()
        captured = capsys.readouterr()
        # WARN_MESSAGE（stderr）與 lag 警告（emit_hook_output/stdout）分道輸出，
        # 不再併入同一則 stderr 訊息（W4-009 的丟棄前提已隨 exit 0 化失效）
        assert "[PC-019 提醒]" in captured.err
        assert "W3-007 警告" not in captured.err
