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

驗證設計：透過 patch `git_utils._run_git` 捕捉 commit 步驟收到的 `-m`
訊息參數，隔離真實 git 副作用（同 test_auto_commit_operation_param.py
慣例）；`resolve_current_session_id` 亦以 patch 控制回傳值，避免斷言
依賴執行環境的 `CLAUDE_CODE_SESSION_ID` 是否設定而變得不確定。
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from ticket_system.lib import git_utils


def _make_run_git(recorder):
    """產生 fake _run_git：rev-parse/add 成功、diff 回 1（有變更）觸發 commit。"""

    def fake_run_git(cwd, *args, timeout=git_utils._FAST_GIT_TIMEOUT):
        if args[0] == "commit":
            recorder.recorded_args = args
            return MagicMock(returncode=0, stderr="")
        if args[:2] == ("diff", "--cached"):
            return MagicMock(returncode=1)
        return MagicMock(returncode=0)

    return fake_run_git


class _Recorder:
    recorded_args: tuple = ()


def _recorded_message(recorder) -> str:
    msg_idx = recorder.recorded_args.index("-m") + 1
    return recorder.recorded_args[msg_idx]


class TestSessionTrailerPresent:
    """AC1：session_id 可解析時，trailer 附加且值一致。"""

    def test_trailer_appended_when_session_id_resolvable(self):
        recorder = _Recorder()
        with patch.object(git_utils, "_run_git", side_effect=_make_run_git(recorder)), \
             patch.object(
                 git_utils, "resolve_current_session_id",
                 return_value="test-session-abc123",
             ):
            status = git_utils._auto_commit_ticket_md(
                "/tmp/x.md", "0.0.0-W0-TRAILER", "Solution"
            )

        assert status == "committed"
        message = _recorded_message(recorder)
        assert message == (
            "chore(0.0.0-W0-TRAILER): append-log Solution\n\n"
            "Session: test-session-abc123"
        )

    def test_trailer_value_matches_resolve_current_session_id_verbatim(self):
        """trailer 值與 resolve_current_session_id 回傳值逐字一致
        （AC1「與 registry session id 一致」——本模組不自行推導，全權委派）。
        """
        recorder = _Recorder()
        session_id = "7543918a-abcd-4ef0-9999-000000000000"
        with patch.object(git_utils, "_run_git", side_effect=_make_run_git(recorder)), \
             patch.object(
                 git_utils, "resolve_current_session_id", return_value=session_id
             ):
            git_utils._auto_commit_ticket_md("/tmp/x.md", "0.0.0-W0-TRAILER2", "Solution")

        message = _recorded_message(recorder)
        trailer_line = message.splitlines()[-1]
        assert trailer_line == f"Session: {session_id}"

    def test_subject_line_unaffected_by_trailer(self):
        """git log --pretty=%s 語意：trailer 位於 body，subject（第一行）
        維持既有格式不變（向後相容既有格式斷言測試）。
        """
        recorder = _Recorder()
        with patch.object(git_utils, "_run_git", side_effect=_make_run_git(recorder)), \
             patch.object(
                 git_utils, "resolve_current_session_id", return_value="sess-x"
             ):
            git_utils._auto_commit_ticket_md(
                "/tmp/x.md", "0.0.0-W0-TRAILER3", "Test Results",
                operation="set-exit-status",
            )

        message = _recorded_message(recorder)
        subject = message.splitlines()[0]
        assert subject == "chore(0.0.0-W0-TRAILER3): set-exit-status Test Results"


class TestSessionTrailerAbsent:
    """AC2：session_id 無法解析時，trailer 完整省略，不虛構值。"""

    def test_trailer_omitted_when_session_id_unresolvable(self):
        recorder = _Recorder()
        with patch.object(git_utils, "_run_git", side_effect=_make_run_git(recorder)), \
             patch.object(git_utils, "resolve_current_session_id", return_value=None):
            status = git_utils._auto_commit_ticket_md(
                "/tmp/x.md", "0.0.0-W0-NOTRAILER", "Solution"
            )

        assert status == "committed"
        message = _recorded_message(recorder)
        assert message == "chore(0.0.0-W0-NOTRAILER): append-log Solution"
        assert "Session:" not in message

    def test_trailer_omitted_when_session_id_empty_string(self):
        """resolve_current_session_id 理論上不回傳空字串（內部已 strip 判斷），
        但呼叫端仍以 falsy 檢查防禦，避免產生空白 trailer 行。"""
        recorder = _Recorder()
        with patch.object(git_utils, "_run_git", side_effect=_make_run_git(recorder)), \
             patch.object(git_utils, "resolve_current_session_id", return_value=""):
            git_utils._auto_commit_ticket_md(
                "/tmp/x.md", "0.0.0-W0-EMPTYSESSION", "Solution"
            )

        message = _recorded_message(recorder)
        assert "Session:" not in message
