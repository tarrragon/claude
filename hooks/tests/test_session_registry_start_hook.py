#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
session-registry-start-hook 測試套件（multi-PM 協調層 Phase 1 + idle agent
回收掃描 0.2.1-W3-1154）

覆蓋：subagent 環境跳過 / session_id 缺失跳過（stdin 與環境變數皆無）/
正常註冊呼叫 register_session / OSError 不阻擋 / idle agent 回收掃描
（歸屬三分 + 孤兒兩級 / ticket 現況跨版本查詢 / 唯讀不變動狀態 / 措辭
可逆性）。
"""

import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lib import ENV_SESSION_ID
from lib.dispatch_tracker import get_state_file_path, record_dispatch, get_active_dispatches
from lib.pm_registry import write_registry, _empty_registry

hooks_path = Path(__file__).parent.parent
hook_file = hooks_path / "session-registry-start-hook.py"
spec = importlib.util.spec_from_file_location("session_registry_start_hook", hook_file)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)

EXIT_SUCCESS = hook.EXIT_SUCCESS

# resolve_session_id 本體測試已收斂至 lib 單一定義，見
# test_hook_logging_session_id.py；本檔不再重複測（0.2.1-W3-560 DRY 下沉）。


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    """臨時 project_root，含 .claude/ 目錄以供 dispatch-active.json 落地。"""
    (tmp_path / ".claude").mkdir()
    return tmp_path


def _write_ticket(project_root: Path, ticket_id: str, status: str) -> Path:
    """在臨時 project_root 下建立最小 ticket md（跨版本目錄結構）。"""
    version = ticket_id.split("-W")[0]
    ticket_dir = project_root / "docs" / "work-logs" / f"v{version}" / "tickets"
    ticket_dir.mkdir(parents=True, exist_ok=True)
    ticket_path = ticket_dir / f"{ticket_id}.md"
    ticket_path.write_text(
        f"---\nid: {ticket_id}\nstatus: {status}\n---\n\n# Execution Log\n",
        encoding="utf-8",
    )
    return ticket_path


class TestMain:
    def _run(self, input_data, subagent=False):
        with patch.object(hook, "setup_hook_logging") as mock_log, patch.object(
            hook, "read_json_from_stdin"
        ) as mock_stdin, patch.object(
            hook, "is_subagent_environment"
        ) as mock_sub, patch.object(
            hook, "get_project_root"
        ) as mock_root, patch.object(
            hook,
            "get_registry_paths",
            return_value=(
                Path("/repo/.git/pm-registry.json"),
                Path("/repo/.git/pm-registry.lock"),
            ),
        ), patch.object(
            hook, "register_session"
        ) as mock_register:
            mock_log.return_value = MagicMock()
            mock_stdin.return_value = input_data
            mock_sub.return_value = subagent
            mock_root.return_value = Path("/repo/worktree-b6")

            result = hook.main()

        return result, mock_register

    def test_subagent_environment_skips_registration(self):
        result, mock_register = self._run({"session_id": "s1"}, subagent=True)
        assert result == EXIT_SUCCESS
        mock_register.assert_not_called()

    def test_missing_session_id_skips_registration(self, monkeypatch, capsys):
        monkeypatch.delenv(ENV_SESSION_ID, raising=False)
        result, mock_register = self._run({}, subagent=False)
        assert result == EXIT_SUCCESS
        mock_register.assert_not_called()
        assert "無法取得 session_id" in capsys.readouterr().err

    def test_normal_registration_calls_register_session(self):
        result, mock_register = self._run({"session_id": "pm-session-1"}, subagent=False)
        assert result == EXIT_SUCCESS
        mock_register.assert_called_once()
        kwargs = mock_register.call_args.kwargs
        assert kwargs["session_id"] == "pm-session-1"
        assert kwargs["name"] == "worktree-b6"
        assert kwargs["project"] == "/repo/worktree-b6"
        assert kwargs["source"] == ""

    def test_resume_source_passed_through(self):
        """registry 契約 v2 D4 增補 1：source 欄位原樣傳給 register_session，
        merge/reset 分流邏輯由 pm_registry.register_session 負責，本 hook
        只負責傳遞。"""
        result, mock_register = self._run(
            {"session_id": "pm-session-1", "source": "resume"}, subagent=False
        )
        assert result == EXIT_SUCCESS
        assert mock_register.call_args.kwargs["source"] == "resume"

    def test_startup_source_passed_through(self):
        result, mock_register = self._run(
            {"session_id": "pm-session-1", "source": "startup"}, subagent=False
        )
        assert result == EXIT_SUCCESS
        assert mock_register.call_args.kwargs["source"] == "startup"

    def test_non_git_environment_skips_registration(self, capsys):
        with patch.object(hook, "setup_hook_logging") as mock_log, patch.object(
            hook, "read_json_from_stdin"
        ) as mock_stdin, patch.object(
            hook, "is_subagent_environment"
        ) as mock_sub, patch.object(
            hook, "get_project_root"
        ) as mock_root, patch.object(
            hook, "get_registry_paths", return_value=None
        ), patch.object(
            hook, "register_session"
        ) as mock_register:
            mock_log.return_value = MagicMock()
            mock_stdin.return_value = {"session_id": "s1"}
            mock_sub.return_value = False
            mock_root.return_value = Path("/repo")

            result = hook.main()

        assert result == EXIT_SUCCESS
        mock_register.assert_not_called()
        assert "非 git 環境" in capsys.readouterr().err

    def test_register_session_oserror_does_not_block(self, capsys):
        with patch.object(hook, "setup_hook_logging") as mock_log, patch.object(
            hook, "read_json_from_stdin"
        ) as mock_stdin, patch.object(
            hook, "is_subagent_environment"
        ) as mock_sub, patch.object(
            hook, "get_project_root"
        ) as mock_root, patch.object(
            hook,
            "get_registry_paths",
            return_value=(
                Path("/repo/.git/pm-registry.json"),
                Path("/repo/.git/pm-registry.lock"),
            ),
        ), patch.object(
            hook, "register_session", side_effect=OSError("disk full")
        ):
            mock_log.return_value = MagicMock()
            mock_stdin.return_value = {"session_id": "s1"}
            mock_sub.return_value = False
            mock_root.return_value = Path("/repo")

            result = hook.main()

        assert result == EXIT_SUCCESS
        assert "registry 註冊失敗" in capsys.readouterr().err


class TestClassifyOwnership:
    """歸屬三分 + 孤兒兩級（AC1/AC9/AC10）。"""

    def test_self_owned(self):
        assert hook._classify_ownership("s1", "s1", {}) == "self"

    def test_cross_session_alive(self):
        fresh_ts = datetime.now(timezone.utc).isoformat()
        registry_sessions = {"s2": {"heartbeat_ts": fresh_ts}}
        assert (
            hook._classify_ownership("s2", "s1", registry_sessions)
            == "cross_session_alive"
        )

    def test_orphan_confirmed_when_session_absent_from_registry(self):
        """session_id 不在 pm-registry.json 的 sessions 中：確定孤兒。"""
        assert hook._classify_ownership("s-gone", "s1", {}) == "orphan_confirmed"

    def test_orphan_suspected_when_heartbeat_stale(self):
        """存在於 registry 但 heartbeat 已逾 30 分鐘：疑似孤兒。"""
        stale_ts = (
            datetime.now(timezone.utc) - timedelta(minutes=40)
        ).isoformat()
        registry_sessions = {"s2": {"heartbeat_ts": stale_ts}}
        assert (
            hook._classify_ownership("s2", "s1", registry_sessions)
            == "orphan_suspected"
        )

    def test_unknown_owner_when_session_id_missing(self):
        """entry 無 session_id（早期派發記錄）：歸屬不明，非誤判為 self。"""
        assert hook._classify_ownership("", "s1", {}) == "unknown_owner"

    def test_registry_unavailable_not_misclassified_as_orphan(self):
        """registry 讀取失敗時不得誤判為 orphan_confirmed——registry 不可
        用本身無法排除該 session 其實仍存在只是讀不到（產生路徑盤點：
        registry 損毀/缺檔的降級讀取路徑）。"""
        assert (
            hook._classify_ownership("s2", "s1", {}, registry_available=False)
            == "registry_unavailable"
        )

    def test_registry_available_true_is_default(self):
        """registry_available 預設 True，既有呼叫端（傳三個參數）行為不變。"""
        assert hook._classify_ownership("s-gone", "s1", {}) == "orphan_confirmed"


class TestResolveTicketStatus:
    """ticket 現況查詢，跨版本跨 Wave（AC1/AC7）。"""

    def test_completed_status(self, project_root: Path):
        _write_ticket(project_root, "0.2.1-W3-9001", "completed")
        status = hook._resolve_ticket_status(
            "0.2.1-W3-9001", project_root, logger=MagicMock()
        )
        assert status == "completed"

    def test_cross_version_lookup(self, project_root: Path):
        """所屬票可能屬更早版本，查詢不得僅限當前版本目錄（AC7）。"""
        _write_ticket(project_root, "0.1.0-W2-9002", "completed")
        status = hook._resolve_ticket_status(
            "0.1.0-W2-9002", project_root, logger=MagicMock()
        )
        assert status == "completed"

    def test_missing_ticket_id_returns_cha_wu(self, project_root: Path):
        assert (
            hook._resolve_ticket_status("", project_root, logger=MagicMock())
            == "查無"
        )

    def test_nonexistent_ticket_returns_cha_wu(self, project_root: Path):
        assert (
            hook._resolve_ticket_status(
                "0.2.1-W3-99999", project_root, logger=MagicMock()
            )
            == "查無"
        )


class TestScanIdleAgents:
    """scan_idle_agents 整合測試：唯讀不變動狀態 / 無條件資源盤點 / 措辭
    可逆性（AC1/AC3/AC6/AC9）。"""

    def _seed_registry(self, project_root: Path, sessions: dict) -> Path:
        registry_file = project_root / ".git" / "pm-registry.json"
        data = _empty_registry()
        data["sessions"] = sessions
        write_registry(registry_file, data)
        return registry_file

    def test_no_candidates_returns_none(self, project_root: Path):
        registry_file = self._seed_registry(project_root, {})
        assert (
            hook.scan_idle_agents(project_root, "s1", registry_file, MagicMock())
            is None
        )

    def test_non_idle_entry_excluded(self, project_root: Path):
        """turn_ended_at 為 None（回合仍在進行中）不屬候選集合。"""
        record_dispatch(project_root, "still running", session_id="s1")
        registry_file = self._seed_registry(project_root, {})
        assert (
            hook.scan_idle_agents(project_root, "s1", registry_file, MagicMock())
            is None
        )

    def test_readonly_does_not_mutate_dispatch_state(self, project_root: Path):
        """掃描為唯讀，不執行任何 TaskStop：執行後 dispatch 記錄不變（AC3）。"""
        _write_ticket(project_root, "0.2.1-W3-9010", "completed")
        record_dispatch(
            project_root,
            "done agent",
            ticket_id="0.2.1-W3-9010",
            session_id="s1",
            name="thyme",
        )
        state_file = get_state_file_path(project_root)
        # 手動標記 turn_ended_at（模擬 SubagentStop 已標記回合結束）
        data = json.loads(state_file.read_text(encoding="utf-8"))
        data["dispatches"][0]["turn_ended_at"] = datetime.now(
            timezone.utc
        ).isoformat()
        state_file.write_text(json.dumps(data), encoding="utf-8")
        before = state_file.read_text(encoding="utf-8")

        registry_file = self._seed_registry(project_root, {})
        result = hook.scan_idle_agents(project_root, "s1", registry_file, MagicMock())

        assert result is not None
        after = state_file.read_text(encoding="utf-8")
        assert before == after, "掃描不得修改 dispatch-active.json"
        assert len(get_active_dispatches(project_root)) == 1

    def test_completed_ticket_with_full_wrapup_still_included(
        self, project_root: Path
    ):
        """無條件資源盤點：ticket 收尾動作完整執行者，掃描仍列為可清，不
        得設計成「找出未完成收尾的票」（AC6）。"""
        _write_ticket(project_root, "0.2.1-W3-9011", "completed")
        record_dispatch(
            project_root,
            "fully wrapped up agent",
            ticket_id="0.2.1-W3-9011",
            session_id="s1",
            name="thyme",
        )
        state_file = get_state_file_path(project_root)
        data = json.loads(state_file.read_text(encoding="utf-8"))
        data["dispatches"][0]["turn_ended_at"] = datetime.now(
            timezone.utc
        ).isoformat()
        state_file.write_text(json.dumps(data), encoding="utf-8")

        registry_file = self._seed_registry(project_root, {})
        result = hook.scan_idle_agents(project_root, "s1", registry_file, MagicMock())

        assert result is not None
        assert "0.2.1-W3-9011" in result
        assert "可清" in result

    def test_wording_avoids_irreversibility_language(self, project_root: Path):
        """回報措辭不得暗示目標已失效或不可回復，須含可恢復說明（AC9）。"""
        _write_ticket(project_root, "0.2.1-W3-9012", "completed")
        record_dispatch(
            project_root,
            "self owned idle agent",
            ticket_id="0.2.1-W3-9012",
            session_id="s1",
            name="thyme",
        )
        state_file = get_state_file_path(project_root)
        data = json.loads(state_file.read_text(encoding="utf-8"))
        data["dispatches"][0]["turn_ended_at"] = datetime.now(
            timezone.utc
        ).isoformat()
        state_file.write_text(json.dumps(data), encoding="utf-8")

        registry_file = self._seed_registry(project_root, {})
        result = hook.scan_idle_agents(project_root, "s1", registry_file, MagicMock())

        assert result is not None
        for banned in ("已失效", "無效", "可刪除"):
            assert banned not in result
        assert "恢復" in result

    def test_cross_session_alive_prompts_receiver_verification(
        self, project_root: Path
    ):
        """接收方須以自身代理人清單驗證歸屬後才執行（AC9），落在可執行的
        回報範本中，非僅記於 Solution。"""
        _write_ticket(project_root, "0.2.1-W3-9013", "completed")
        record_dispatch(
            project_root,
            "other session agent",
            ticket_id="0.2.1-W3-9013",
            session_id="s-other",
            name="thyme",
        )
        state_file = get_state_file_path(project_root)
        data = json.loads(state_file.read_text(encoding="utf-8"))
        data["dispatches"][0]["turn_ended_at"] = datetime.now(
            timezone.utc
        ).isoformat()
        state_file.write_text(json.dumps(data), encoding="utf-8")

        fresh_ts = datetime.now(timezone.utc).isoformat()
        registry_file = self._seed_registry(
            project_root, {"s-other": {"heartbeat_ts": fresh_ts}}
        )
        result = hook.scan_idle_agents(project_root, "s1", registry_file, MagicMock())

        assert result is not None
        assert "驗證" in result and "歸屬" in result
        assert "不採信" in result

    def test_orphan_confirmed_and_suspected_have_distinguishable_wording(
        self, project_root: Path
    ):
        """孤兒兩級語氣須可區分（AC10）。"""
        _write_ticket(project_root, "0.2.1-W3-9014", "completed")
        record_dispatch(
            project_root,
            "confirmed orphan",
            ticket_id="0.2.1-W3-9014",
            session_id="s-ended",
            name="thyme",
        )
        _write_ticket(project_root, "0.2.1-W3-9015", "completed")
        record_dispatch(
            project_root,
            "suspected orphan",
            ticket_id="0.2.1-W3-9015",
            session_id="s-stale",
            name="thyme",
        )
        state_file = get_state_file_path(project_root)
        data = json.loads(state_file.read_text(encoding="utf-8"))
        for entry in data["dispatches"]:
            entry["turn_ended_at"] = datetime.now(timezone.utc).isoformat()
        state_file.write_text(json.dumps(data), encoding="utf-8")

        stale_ts = (
            datetime.now(timezone.utc) - timedelta(minutes=40)
        ).isoformat()
        registry_file = self._seed_registry(
            project_root, {"s-stale": {"heartbeat_ts": stale_ts}}
        )
        result = hook.scan_idle_agents(project_root, "s1", registry_file, MagicMock())

        assert result is not None
        assert "確定孤兒" in result
        assert "疑似孤兒" in result

    def test_missing_registry_file_does_not_misclassify_as_orphan(
        self, project_root: Path
    ):
        """registry_file 不存在（read_registry 降級讀取）時，跨 session
        候選不得被誤判為確定孤兒（產生路徑盤點涵蓋項）。"""
        _write_ticket(project_root, "0.2.1-W3-9016", "completed")
        record_dispatch(
            project_root,
            "cross session agent",
            ticket_id="0.2.1-W3-9016",
            session_id="s-other",
            name="thyme",
        )
        state_file = get_state_file_path(project_root)
        data = json.loads(state_file.read_text(encoding="utf-8"))
        data["dispatches"][0]["turn_ended_at"] = datetime.now(
            timezone.utc
        ).isoformat()
        state_file.write_text(json.dumps(data), encoding="utf-8")

        # 不呼叫 _seed_registry：registry_file 不存在，read_registry 會
        # 回傳降級空結構（DEGRADED_READ_KEY=True）。
        missing_registry_file = project_root / ".git" / "pm-registry.json"
        result = hook.scan_idle_agents(
            project_root, "s1", missing_registry_file, MagicMock()
        )

        assert result is not None
        assert "確定孤兒" not in result
        assert "無法判定（pm-registry.json 讀取失敗或損毀）" in result


class TestMainIntegratesScan:
    """main() 端到端：有候選時 additionalContext 含掃描區塊，無候選時不
    附加。"""

    def _run_with_real_root(self, project_root: Path, session_id: str, capsys):
        registry_paths = (
            project_root / ".git" / "pm-registry.json",
            project_root / ".git" / "pm-registry.lock",
        )
        with patch.object(hook, "setup_hook_logging") as mock_log, patch.object(
            hook, "read_json_from_stdin"
        ) as mock_stdin, patch.object(
            hook, "is_subagent_environment"
        ) as mock_sub, patch.object(
            hook, "get_project_root"
        ) as mock_root, patch.object(
            hook, "get_registry_paths", return_value=registry_paths
        ), patch.object(
            hook, "register_session"
        ):
            mock_log.return_value = MagicMock()
            mock_stdin.return_value = {"session_id": session_id}
            mock_sub.return_value = False
            mock_root.return_value = project_root

            result = hook.main()

        return result, capsys.readouterr().out

    def test_prints_additional_context_when_candidates_exist(
        self, project_root: Path, capsys
    ):
        _write_ticket(project_root, "0.2.1-W3-9020", "completed")
        record_dispatch(
            project_root,
            "idle agent",
            ticket_id="0.2.1-W3-9020",
            session_id="s1",
            name="thyme",
        )
        state_file = get_state_file_path(project_root)
        data = json.loads(state_file.read_text(encoding="utf-8"))
        data["dispatches"][0]["turn_ended_at"] = datetime.now(
            timezone.utc
        ).isoformat()
        state_file.write_text(json.dumps(data), encoding="utf-8")

        result, stdout = self._run_with_real_root(project_root, "s1", capsys)

        assert result == EXIT_SUCCESS
        payload = json.loads(stdout)
        assert (
            "idle agent 回收掃描"
            in payload["hookSpecificOutput"]["additionalContext"]
        )

    def test_no_output_when_no_candidates(self, project_root: Path, capsys):
        result, stdout = self._run_with_real_root(project_root, "s1", capsys)
        assert result == EXIT_SUCCESS
        assert stdout.strip() == ""
