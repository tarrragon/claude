"""0.2.1-W3-257 — _auto_commit_ticket_md operation 參數 RED/GREEN 測試。

背景：`_auto_commit_ticket_md` 原將 commit message 硬編為
`chore(<ticket_id>): append-log <section>`，不論實際呼叫端為何。
resolve-spawn-request / add-spawn-request 等非 append-log 呼叫端寫入時，
commit 訊息仍誤標為 append-log，使 `git log --grep` 依操作類型考古時失準
（現成案例：commit 3da9ee54 訊息為 "append-log Spawn Requests"，實際操作是
resolve-spawn-request）。

修法：新增 operation 參數，預設值維持 "append-log"（既有呼叫端訊息逐字
不變，acceptance #2）；新呼叫端顯式傳入自身操作名（acceptance #1）。

驗證設計：提交機制改由 git_utils._auto_commit_ticket_md 委派
git_ops.commit_files_isolated（隔離索引 CAS），改為 patch
`git_utils.commit_files_isolated` 捕捉傳入的 `message` 引數，隔離真實 git
副作用，聚焦本票變更範圍（operation 參數對 commit message 組裝的影響），
與 `test_auto_commit_session_trailer.py` 同模式。

0.2.1-W3-554.2：`_auto_commit_ticket_md` 新增 session_id 可解析時附加
`Session: <id>` trailer 的行為；本檔測項聚焦 operation 參數本身，統一
patch `resolve_current_session_id` 回傳 None（無 trailer），避免斷言
依賴執行環境的 `CLAUDE_CODE_SESSION_ID` 是否設定而變得不確定。trailer
行為本身的測試見 `test_auto_commit_session_trailer.py`。
"""

from __future__ import annotations

from unittest.mock import patch

from ticket_system.lib import git_utils


def _fake_commit_files_isolated(recorder):
    """建立模擬 commit_files_isolated：捕捉 message 引數，回傳 committed。"""

    def fake(paths, message, cwd=None):
        recorder.recorded_message = message
        return {"status": "committed", "commit_sha": "deadbeef", "error": None}

    return fake


class _Recorder:
    """簡易容器，供 fake commit_files_isolated 回填實際收到的 message 供斷言。"""

    recorded_message: str = ""


class TestOperationParamDefault:
    """acceptance #2：既有呼叫端（未傳 operation）訊息格式逐字不變。"""

    def test_default_operation_produces_append_log_message(self):
        recorder = _Recorder()
        with patch.object(
            git_utils, "commit_files_isolated",
            side_effect=_fake_commit_files_isolated(recorder),
        ), patch.object(git_utils, "resolve_current_session_id", return_value=None):
            status = git_utils._auto_commit_ticket_md(
                "/tmp/x.md", "0.2.1-W3-257", "Solution"
            )

        assert status == "committed"
        assert recorder.recorded_message == "chore(0.2.1-W3-257): append-log Solution", (
            "未傳 operation 時應維持既有 append-log 訊息格式（向後相容）"
        )

    def test_explicit_append_log_operation_matches_default(self):
        """顯式傳入 operation='append-log' 應與省略參數結果一致（預設值等價性）。"""
        recorder = _Recorder()
        with patch.object(
            git_utils, "commit_files_isolated",
            side_effect=_fake_commit_files_isolated(recorder),
        ), patch.object(git_utils, "resolve_current_session_id", return_value=None):
            git_utils._auto_commit_ticket_md(
                "/tmp/x.md", "0.2.1-W3-257", "Solution", operation="append-log"
            )

        assert recorder.recorded_message == "chore(0.2.1-W3-257): append-log Solution"


class TestOperationParamCustom:
    """acceptance #1：新呼叫端傳入自身操作名，commit 訊息含實際操作名。"""

    def test_resolve_spawn_request_operation_reflected_in_message(self):
        recorder = _Recorder()
        with patch.object(
            git_utils, "commit_files_isolated",
            side_effect=_fake_commit_files_isolated(recorder),
        ), patch.object(git_utils, "resolve_current_session_id", return_value=None):
            status = git_utils._auto_commit_ticket_md(
                "/tmp/x.md", "0.2.1-W3-257", "Spawn Requests",
                operation="resolve-spawn-request",
            )

        assert status == "committed"
        assert recorder.recorded_message == (
            "chore(0.2.1-W3-257): resolve-spawn-request Spawn Requests"
        ), "resolve-spawn-request 呼叫端訊息不應誤標為 append-log"

    def test_add_spawn_request_operation_reflected_in_message(self):
        recorder = _Recorder()
        with patch.object(
            git_utils, "commit_files_isolated",
            side_effect=_fake_commit_files_isolated(recorder),
        ), patch.object(git_utils, "resolve_current_session_id", return_value=None):
            status = git_utils._auto_commit_ticket_md(
                "/tmp/x.md", "0.2.1-W3-257", "Spawn Requests",
                operation="add-spawn-request",
            )

        assert status == "committed"
        assert recorder.recorded_message == (
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
