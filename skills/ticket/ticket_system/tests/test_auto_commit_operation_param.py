"""0.2.1-W3-257 — _auto_commit_ticket_md operation 參數 RED/GREEN 測試。

背景：`_auto_commit_ticket_md` 原將 commit message 硬編為
`chore(<ticket_id>): append-log <section>`，不論實際呼叫端為何。
resolve-spawn-request / add-spawn-request 等非 append-log 呼叫端寫入時，
commit 訊息仍誤標為 append-log，使 `git log --grep` 依操作類型考古時失準
（現成案例：commit 3da9ee54 訊息為 "append-log Spawn Requests"，實際操作是
resolve-spawn-request）。

修法：新增 operation 參數，預設值維持 "append-log"（既有呼叫端訊息逐字
不變，acceptance #2）；新呼叫端顯式傳入自身操作名（acceptance #1）。

驗證設計：透過 patch `git_utils._run_git` 捕捉 commit 步驟收到的 `-m` 訊息
參數，隔離真實 git 副作用，聚焦本票變更範圍（operation 參數對 commit
message 組裝的影響），與 `test_git_index_lock_retry.py` 同模式。
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from ticket_system.lib import git_utils


def _make_run_git(commit_result):
    """產生 fake _run_git：rev-parse/add 成功、diff 回 1（有變更）觸發 commit。

    回傳的 commit_result 供斷言時取用其接收到的 args（含 -m 訊息）。
    """

    def fake_run_git(cwd, *args, timeout=git_utils._FAST_GIT_TIMEOUT):
        if args[0] == "commit":
            commit_result.recorded_args = args
            return MagicMock(returncode=0, stderr="")
        if args[:2] == ("diff", "--cached"):
            return MagicMock(returncode=1)
        return MagicMock(returncode=0)

    return fake_run_git


class _Recorder:
    """簡易容器，供 fake_run_git 回填實際收到的 commit args 供斷言。"""

    recorded_args: tuple = ()


class TestOperationParamDefault:
    """acceptance #2：既有呼叫端（未傳 operation）訊息格式逐字不變。"""

    def test_default_operation_produces_append_log_message(self):
        recorder = _Recorder()
        with patch.object(git_utils, "_run_git", side_effect=_make_run_git(recorder)):
            status = git_utils._auto_commit_ticket_md(
                "/tmp/x.md", "0.2.1-W3-257", "Solution"
            )

        assert status == "committed"
        assert "-m" in recorder.recorded_args
        msg_idx = recorder.recorded_args.index("-m") + 1
        assert recorder.recorded_args[msg_idx] == "chore(0.2.1-W3-257): append-log Solution", (
            "未傳 operation 時應維持既有 append-log 訊息格式（向後相容）"
        )

    def test_explicit_append_log_operation_matches_default(self):
        """顯式傳入 operation='append-log' 應與省略參數結果一致（預設值等價性）。"""
        recorder = _Recorder()
        with patch.object(git_utils, "_run_git", side_effect=_make_run_git(recorder)):
            git_utils._auto_commit_ticket_md(
                "/tmp/x.md", "0.2.1-W3-257", "Solution", operation="append-log"
            )

        msg_idx = recorder.recorded_args.index("-m") + 1
        assert recorder.recorded_args[msg_idx] == "chore(0.2.1-W3-257): append-log Solution"


class TestOperationParamCustom:
    """acceptance #1：新呼叫端傳入自身操作名，commit 訊息含實際操作名。"""

    def test_resolve_spawn_request_operation_reflected_in_message(self):
        recorder = _Recorder()
        with patch.object(git_utils, "_run_git", side_effect=_make_run_git(recorder)):
            status = git_utils._auto_commit_ticket_md(
                "/tmp/x.md", "0.2.1-W3-257", "Spawn Requests",
                operation="resolve-spawn-request",
            )

        assert status == "committed"
        msg_idx = recorder.recorded_args.index("-m") + 1
        assert recorder.recorded_args[msg_idx] == (
            "chore(0.2.1-W3-257): resolve-spawn-request Spawn Requests"
        ), "resolve-spawn-request 呼叫端訊息不應誤標為 append-log"

    def test_add_spawn_request_operation_reflected_in_message(self):
        recorder = _Recorder()
        with patch.object(git_utils, "_run_git", side_effect=_make_run_git(recorder)):
            status = git_utils._auto_commit_ticket_md(
                "/tmp/x.md", "0.2.1-W3-257", "Spawn Requests",
                operation="add-spawn-request",
            )

        assert status == "committed"
        msg_idx = recorder.recorded_args.index("-m") + 1
        assert recorder.recorded_args[msg_idx] == (
            "chore(0.2.1-W3-257): add-spawn-request Spawn Requests"
        ), "add-spawn-request 呼叫端訊息不應誤標為 append-log"


class TestSignatureBackwardCompatible:
    """既有簽章檢查（test_append_log_auto_commit.py）僅斷言前三參數，
    本測試補充驗證新增的第四參數 operation 具預設值（不強制既有呼叫端傳參）。"""

    def test_operation_param_has_default_value(self):
        import inspect

        sig = inspect.signature(git_utils._auto_commit_ticket_md)
        params = sig.parameters
        assert "operation" in params, "應新增 operation 參數"
        assert params["operation"].default == "append-log", (
            "operation 參數預設值應為 'append-log'（既有呼叫端行為不變）"
        )
