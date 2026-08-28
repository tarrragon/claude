"""_auto_commit_ticket_md Session trailer 測試（0.2.1-W3-554.2）。

驗證重點：
1. session_id 可解析（`resolve_current_session_id` 回傳非 None）時，
   commit 訊息 body 附加 `Session: <id>` trailer（空白行分隔）。
2. session_id 無法解析（回傳 None）時，trailer 完整省略，不虛構值。
3. trailer 值與 `lease.resolve_current_session_id` 的解析結果逐字一致
   （AC1「與 registry session id 一致」——本模組不自行推導 session_id，
   全權委派 lease.py 既有解析邏輯，天然保證一致）。
4. subject line（`git log --pretty=%s`）不受 trailer 影響，維持既有
   `chore(<id>): <operation> <section>` 格式（向後相容，見
   test_auto_commit_operation_param.py / test_append_log_auto_commit.py）。

驗證設計：提交機制改由 git_utils._auto_commit_ticket_md 委派
git_ops.commit_files_isolated（隔離索引 CAS），本檔聚焦 message 組裝，
改為 patch `git_utils.commit_files_isolated` 捕捉傳入的 `message` 引數，
不再 mock 低階 `_run_git`（已隨提交機制改造移除）；
`resolve_current_session_id` 亦以 patch 控制回傳值，避免斷言依賴執行環境
的 `CLAUDE_CODE_SESSION_ID` 是否設定而變得不確定。
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
    recorded_message: str = ""


class TestSessionTrailerPresent:
    """AC1：session_id 可解析時，trailer 附加且值一致。"""

    def test_trailer_appended_when_session_id_resolvable(self):
        recorder = _Recorder()
        with patch.object(
            git_utils, "commit_files_isolated",
            side_effect=_fake_commit_files_isolated(recorder),
        ), patch.object(
            git_utils, "resolve_current_session_id",
            return_value="test-session-abc123",
        ):
            status = git_utils._auto_commit_ticket_md(
                "/tmp/x.md", "0.0.0-W0-TRAILER", "Solution"
            )

        assert status == "committed"
        assert recorder.recorded_message == (
            "chore(0.0.0-W0-TRAILER): append-log Solution\n\n"
            "Session: test-session-abc123"
        )

    def test_trailer_value_matches_resolve_current_session_id_verbatim(self):
        """trailer 值與 resolve_current_session_id 回傳值逐字一致
        （AC1「與 registry session id 一致」——本模組不自行推導，全權委派）。
        """
        recorder = _Recorder()
        session_id = "7543918a-abcd-4ef0-9999-000000000000"
        with patch.object(
            git_utils, "commit_files_isolated",
            side_effect=_fake_commit_files_isolated(recorder),
        ), patch.object(
            git_utils, "resolve_current_session_id", return_value=session_id
        ):
            git_utils._auto_commit_ticket_md("/tmp/x.md", "0.0.0-W0-TRAILER2", "Solution")

        trailer_line = recorder.recorded_message.splitlines()[-1]
        assert trailer_line == f"Session: {session_id}"

    def test_subject_line_unaffected_by_trailer(self):
        """git log --pretty=%s 語意：trailer 位於 body，subject（第一行）
        維持既有格式不變（向後相容既有格式斷言測試）。
        """
        recorder = _Recorder()
        with patch.object(
            git_utils, "commit_files_isolated",
            side_effect=_fake_commit_files_isolated(recorder),
        ), patch.object(
            git_utils, "resolve_current_session_id", return_value="sess-x"
        ):
            git_utils._auto_commit_ticket_md(
                "/tmp/x.md", "0.0.0-W0-TRAILER3", "Test Results",
                operation="set-exit-status",
            )

        subject = recorder.recorded_message.splitlines()[0]
        assert subject == "chore(0.0.0-W0-TRAILER3): set-exit-status Test Results"


class TestSessionTrailerAbsent:
    """AC2：session_id 無法解析時，trailer 完整省略，不虛構值。"""

    def test_trailer_omitted_when_session_id_unresolvable(self):
        recorder = _Recorder()
        with patch.object(
            git_utils, "commit_files_isolated",
            side_effect=_fake_commit_files_isolated(recorder),
        ), patch.object(git_utils, "resolve_current_session_id", return_value=None):
            status = git_utils._auto_commit_ticket_md(
                "/tmp/x.md", "0.0.0-W0-NOTRAILER", "Solution"
            )

        assert status == "committed"
        assert recorder.recorded_message == "chore(0.0.0-W0-NOTRAILER): append-log Solution"
        assert "Session:" not in recorder.recorded_message

    def test_trailer_omitted_when_session_id_empty_string(self):
        """resolve_current_session_id 理論上不回傳空字串（內部已 strip 判斷），
        但呼叫端仍以 falsy 檢查防禦，避免產生空白 trailer 行。"""
        recorder = _Recorder()
        with patch.object(
            git_utils, "commit_files_isolated",
            side_effect=_fake_commit_files_isolated(recorder),
        ), patch.object(git_utils, "resolve_current_session_id", return_value=""):
            git_utils._auto_commit_ticket_md(
                "/tmp/x.md", "0.0.0-W0-EMPTYSESSION", "Solution"
            )

        assert "Session:" not in recorder.recorded_message
