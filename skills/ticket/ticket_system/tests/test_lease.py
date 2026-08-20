"""ticket_system.lib.lease 測試（multi-PM 協調層 Phase 3：lease claim/reclaim）。

驗證重點：
1. claim_lease 寫入 registry lease（tickets/files 併入自身 session entry）
2. release_lease 對稱移除 lease（tickets 移除 + files 依剩餘 tickets 重算）
3. FRESH session 前置衝突僅警告不硬擋（Phase 2 缺口 1、2 落地）
4. session_id 解析：CLAUDE_CODE_SESSION_ID 環境變數優先，其次唯一 FRESH
   同專案 session；兩者皆無法判定時降級跳過（不虛構 session_id）
5. reclaim ghost 鑑識三查：未合併分支 / 髒檔交集 / 缺 Exit Status
6. reclaim 僅接受 reclaimable 票（in_progress 且非 FRESH session 佐證）
7. reclaim dry-run 不寫入；--confirm 且三查全過才轉 pending 並清 lease

registry 讀寫一律經真實 `.claude/lib/pm_registry` 模組（`get_registry_paths`
monkeypatch 重導至 tmp_path），非以 fake stub 取代——直接驗證
`recompute_lease` / `is_fresh` 兩個 API 的真實行為。

heartbeat 種子一律經 `_fresh_ts()` / `_stale_ts()` 播種，不寫固定日期字面
（`is_fresh` 在未注入 now 時取真實時鐘，固定字面必隨時間失效，見
TEST-MON-001）；FRESH/STALE 判定依賴真實時鐘的測試須加前置斷言，使
「條件不成立」與「行為不正確」在紅燈時可區分。

`files_intersect` / `where_files` 的判定邏輯已抽至
`ticket_system.lib.file_conflict`（AC-3 共用實作，Phase 4 審查修正：本檔
不再自帶複本），細節測試在 `test_file_conflict.py`。
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from ticket_system.lib import lease

from conftest import _iso, seed_pm_registry as _seed_registry  # noqa: F401 — 0.2.1-W3-585 收斂複本


# --- heartbeat 播種基準與 FRESH/STALE 語意 helper ----------------------------
#
# lease 的五個入口分兩類時鐘來源：`claim_lease` / `resolve_current_session_id`
# 取真實時鐘（無 `now` 參數），其餘三個由測試注入 `now=NOW`。因此 heartbeat
# 種子必須相對「執行當下」定義——固定日期字面（原
# `NOW = datetime(2026, 8, 18, 12, 0, 0)`，即撰寫當天）在該時刻的
# STALE_THRESHOLD_MINUTES 之後一律被判為 STALE，使依賴 FRESH 前提的測試
# 永久紅燈（TEST-MON-001 時鐘相對 fixture 時間炸彈）。
#
# 全檔種子與注入基準同為 `NOW`（模組載入當下），故注入路徑的 elapsed 完全
# 確定（FRESH 為 0、STALE 為門檻 + 邊際）；真實時鐘路徑則假設「模組載入至
# 斷言執行 < 門檻」——最壞情況為整套 suite 的執行時間（實測 110 秒），對
# 30 分鐘門檻有約 16 倍餘裕，且此餘裕不隨日期推移消耗（NOW 每次執行重取）。
# 該假設若失效，下方三處 `is_fresh` 前置斷言會直接指出成因，不會退化為假綠。
NOW = datetime.now(timezone.utc)


def _stale_threshold() -> timedelta:
    """`pm_registry.STALE_THRESHOLD_MINUTES`（FRESH/STALE 判準單一權威來源）。

    模組不可用時降級為 30 分鐘（現行值）；該情形下 `real_pm_registry`
    fixture 會 skip 所有需要 registry 的測試，此降級值僅為避免 import 期
    失敗，不代表判準真為 30。
    """
    pm_registry = lease._load_pm_registry()
    minutes = getattr(pm_registry, "STALE_THRESHOLD_MINUTES", 30) if pm_registry else 30
    return timedelta(minutes=minutes)


_STALE_THRESHOLD = _stale_threshold()
_STALE_MARGIN = timedelta(minutes=15)


def _fresh_ts() -> str:
    """播種一筆 FRESH heartbeat（elapsed = 0，必在門檻內）。"""
    return _iso(NOW)


def _stale_ts() -> str:
    """播種一筆 STALE heartbeat（超出門檻再加安全邊際）。

    以門檻常數推導而非硬編碼 45 分鐘，使「這筆是 STALE」由常數關係明示，
    讀者不需心算 45 與 30 的大小關係，門檻調整時亦不需逐點改字面。
    """
    return _iso(NOW - _STALE_THRESHOLD - _STALE_MARGIN)


@pytest.fixture
def real_pm_registry(tmp_path, monkeypatch):
    """載入真實 `.claude/lib/pm_registry` 模組，registry 路徑重導至 tmp_path。"""
    pm_registry = lease._load_pm_registry()
    if pm_registry is None:
        pytest.skip("找不到 .claude/lib/pm_registry.py（開發環境結構異常）")
    registry_file = tmp_path / "pm-registry.json"
    lock_file = tmp_path / "pm-registry.lock"
    monkeypatch.setattr(
        pm_registry, "get_registry_paths", lambda cwd=None: (registry_file, lock_file)
    )
    return pm_registry, registry_file, lock_file


# --- resolve_current_session_id（auto-commit trailer 通用解析入口）----------


class TestResolveCurrentSessionId:
    """通用 session_id 解析入口：env var 優先，其次唯一 FRESH 同專案
    session；兩者皆缺時回傳 None，不虛構。與 `_resolve_session_id`
    （claim_lease 內部呼叫）同一套判準，此處驗證公開包裝函式本身。
    """

    def test_env_var_takes_priority(self, real_pm_registry, monkeypatch):
        _pm_registry, registry_file, _lock_file = real_pm_registry
        monkeypatch.setenv(lease.ENV_SESSION_ID, "env-session-id")
        _seed_registry(registry_file, {})

        result = lease.resolve_current_session_id()

        assert result == "env-session-id"

    def test_falls_back_to_unique_fresh_session_when_env_missing(
        self, real_pm_registry, monkeypatch
    ):
        _pm_registry, registry_file, _lock_file = real_pm_registry
        monkeypatch.delenv(lease.ENV_SESSION_ID, raising=False)
        monkeypatch.setattr(lease, "_current_project_root", lambda: "/proj")
        _seed_registry(registry_file, {
            "sess-only": {
                "project": "/proj",
                "heartbeat_ts": _fresh_ts(),
                "tickets": [],
                "files": [],
            }
        })

        result = lease.resolve_current_session_id()

        assert result == "sess-only"

    def test_returns_none_when_ambiguous_and_no_env(self, real_pm_registry, monkeypatch):
        pm_registry, registry_file, _lock_file = real_pm_registry
        monkeypatch.delenv(lease.ENV_SESSION_ID, raising=False)
        monkeypatch.setattr(lease, "_current_project_root", lambda: "/proj")
        now_iso = _fresh_ts()
        _seed_registry(registry_file, {
            "sess-a": {"project": "/proj", "heartbeat_ts": now_iso, "tickets": [], "files": []},
            "sess-b": {"project": "/proj", "heartbeat_ts": now_iso, "tickets": [], "files": []},
        })
        # 前置斷言：`_resolve_session_id` 的 `matches[0] if len(matches) == 1 else None`
        # 對「0 筆」與「2 筆」同樣回傳 None，下方 `result is None` 因而無法單獨
        # 區分兩者。此處先確認種子在真實時鐘下確為 FRESH（即 matches 為 2 筆），
        # 使本測試驗證的是「歧義」而非退化成「無 FRESH session」（TEST-MON-001）。
        assert pm_registry.is_fresh(now_iso) is True

        result = lease.resolve_current_session_id()

        assert result is None

    def test_returns_none_when_pm_registry_unavailable(self, monkeypatch):
        monkeypatch.delenv(lease.ENV_SESSION_ID, raising=False)
        monkeypatch.setattr(lease, "_load_pm_registry", lambda: None)

        result = lease.resolve_current_session_id()

        assert result is None


# --- AC-3 共用實作：確認未自帶複本，而是同一函式物件 -------------------------


class TestSharedImplementationImports:
    """Phase 4 審查修正 6：lease.py 刪除自帶的 `_files_intersect` 複本，改
    import `file_conflict.files_intersect` / `where_files`。直接 assert
    同一物件 `is`，行為測試見 `test_file_conflict.py`。
    """

    def test_files_intersect_is_shared_implementation(self):
        from ticket_system.lib import file_conflict

        assert lease.files_intersect is file_conflict.files_intersect

    def test_where_files_is_shared_implementation(self):
        from ticket_system.lib import file_conflict

        assert lease.where_files is file_conflict.where_files


# --- claim_lease ---------------------------------------------------------------


class TestClaimLease:
    def test_writes_tickets_and_files_into_own_session(self, real_pm_registry, monkeypatch):
        _pm_registry, registry_file, _lock_file = real_pm_registry
        monkeypatch.setenv(lease.ENV_SESSION_ID, "sess-A")
        monkeypatch.setattr(lease, "_current_project_root", lambda: "/proj")
        monkeypatch.setattr(
            lease, "load_ticket",
            lambda version, tid: {"id": tid, "where": {"files": ["lib/foo.dart"]}},
        )
        _seed_registry(registry_file, {
            "sess-A": {
                "project": "/proj",
                "heartbeat_ts": _fresh_ts(),
                "tickets": [],
                "files": [],
            }
        })

        lease.claim_lease("0.0.0", "0.0.0-W1-001")

        data = json.loads(registry_file.read_text(encoding="utf-8"))
        entry = data["sessions"]["sess-A"]
        assert entry["tickets"] == ["0.0.0-W1-001"]
        assert entry["files"] == ["lib/foo.dart"]

    def test_narrowed_where_files_shrinks_registry_files_on_reclaim_run(
        self, real_pm_registry, monkeypatch
    ):
        """files 是 tickets 的推導物化值，非獨立累積狀態：where.files 改窄後
        重跑 claim（同票已在 tickets 清單中），registry.files 需整組重算覆蓋
        同步縮窄，不得殘留舊路徑（否則 track_conflicts 的 registry/票面交叉
        比對會產生假陰性，團隊裁示設計約束）。
        """
        _pm_registry, registry_file, _lock_file = real_pm_registry
        monkeypatch.setenv(lease.ENV_SESSION_ID, "sess-A")
        monkeypatch.setattr(lease, "_current_project_root", lambda: "/proj")
        # 票面 where.files 已改窄為單一檔案（原先曾涵蓋 lib/foo.dart + lib/bar.dart）
        monkeypatch.setattr(
            lease, "load_ticket",
            lambda version, tid: {"id": tid, "where": {"files": ["lib/foo.dart"]}},
        )
        _seed_registry(registry_file, {
            "sess-A": {
                "project": "/proj",
                "heartbeat_ts": _fresh_ts(),
                "tickets": ["0.0.0-W1-001"],
                "files": ["lib/foo.dart", "lib/bar.dart"],  # 重跑 claim 前的舊寬範圍殘留
            }
        })

        lease.claim_lease("0.0.0", "0.0.0-W1-001")

        data = json.loads(registry_file.read_text(encoding="utf-8"))
        entry = data["sessions"]["sess-A"]
        assert entry["tickets"] == ["0.0.0-W1-001"]
        assert entry["files"] == ["lib/foo.dart"], (
            "重跑 claim 後 files 應同步縮窄為當前 where.files，不得殘留舊寬範圍"
        )

    def test_missing_session_entry_degrades_with_stderr(self, real_pm_registry, monkeypatch, capsys):
        _pm_registry, registry_file, _lock_file = real_pm_registry
        monkeypatch.setenv(lease.ENV_SESSION_ID, "sess-ghost")
        monkeypatch.setattr(lease, "_current_project_root", lambda: "/proj")
        monkeypatch.setattr(
            lease, "load_ticket", lambda version, tid: {"id": tid, "where": {"files": []}}
        )
        _seed_registry(registry_file, {})

        lease.claim_lease("0.0.0", "0.0.0-W1-001")

        err = capsys.readouterr().err
        assert "sess-ghost" in err
        assert "跳過 lease 寫入" in err

    def test_ambiguous_fresh_sessions_without_env_skips(self, real_pm_registry, monkeypatch, capsys):
        pm_registry, registry_file, _lock_file = real_pm_registry
        monkeypatch.delenv(lease.ENV_SESSION_ID, raising=False)
        monkeypatch.setattr(lease, "_current_project_root", lambda: "/proj")
        monkeypatch.setattr(
            lease, "load_ticket", lambda version, tid: {"id": tid, "where": {"files": []}}
        )
        seed_ts = _fresh_ts()
        _seed_registry(registry_file, {
            "sess-A": {"project": "/proj", "heartbeat_ts": seed_ts, "tickets": [], "files": []},
            "sess-B": {"project": "/proj", "heartbeat_ts": seed_ts, "tickets": [], "files": []},
        })
        # 前置斷言：claim_lease 走真實時鐘判定 freshness，而「0 筆 FRESH」與
        # 「2 筆 FRESH」都會使 `_resolve_session_id` 回傳 None 並印出同一則
        # stderr。先確認種子確為 FRESH，本測試才真的在驗證歧義路徑；否則會
        # 靜默退化為「無 FRESH session」的假綠（TEST-MON-001）。
        assert pm_registry.is_fresh(seed_ts) is True

        lease.claim_lease("0.0.0", "0.0.0-W1-001")

        err = capsys.readouterr().err
        assert "無法判定當前 session_id" in err

    def test_fresh_conflict_warns_but_does_not_block(self, real_pm_registry, monkeypatch, capsys):
        pm_registry, registry_file, _lock_file = real_pm_registry
        monkeypatch.setenv(lease.ENV_SESSION_ID, "sess-A")
        monkeypatch.setattr(lease, "_current_project_root", lambda: "/proj")
        monkeypatch.setattr(
            lease, "load_ticket",
            lambda version, tid: {"id": tid, "where": {"files": ["lib/foo.dart"]}},
        )
        other_ts = _fresh_ts()
        _seed_registry(registry_file, {
            "sess-A": {"project": "/proj", "heartbeat_ts": _fresh_ts(), "tickets": [], "files": []},
            "sess-B": {
                "project": "/proj",
                "heartbeat_ts": other_ts,
                "tickets": ["0.0.0-W1-OTHER"],
                "files": ["lib/foo.dart"],
            },
        })
        # 前置斷言：`_warn_fresh_conflicts` 對 STALE session 直接 continue，
        # sess-B 一旦被判 STALE 則 stderr 為空，下方斷言的失敗訊息只會顯示
        # 「空字串」而不指向時鐘成因（TEST-MON-001 的原始紅燈樣態）。
        assert pm_registry.is_fresh(other_ts) is True

        lease.claim_lease("0.0.0", "0.0.0-W1-001")

        err = capsys.readouterr().err
        assert "sess-B" in err
        assert "lib/foo.dart" in err
        data = json.loads(registry_file.read_text(encoding="utf-8"))
        assert data["sessions"]["sess-A"]["tickets"] == ["0.0.0-W1-001"]


# --- release_lease ---------------------------------------------------------------


class TestReleaseLease:
    def test_removes_ticket_and_recomputes_files(self, real_pm_registry, monkeypatch):
        _pm_registry, registry_file, _lock_file = real_pm_registry
        _seed_registry(registry_file, {
            "sess-A": {
                "project": "/proj",
                "heartbeat_ts": _fresh_ts(),
                "tickets": ["0.0.0-W1-001", "0.0.0-W1-002"],
                "files": ["lib/a.dart", "lib/b.dart"],
            }
        })

        def _fake_load_ticket(version, tid):
            mapping = {"0.0.0-W1-002": {"id": tid, "where": {"files": ["lib/b.dart"]}}}
            return mapping.get(tid)

        monkeypatch.setattr(lease, "load_ticket", _fake_load_ticket)

        lease.release_lease("0.0.0", "0.0.0-W1-001")

        data = json.loads(registry_file.read_text(encoding="utf-8"))
        entry = data["sessions"]["sess-A"]
        assert entry["tickets"] == ["0.0.0-W1-002"]
        assert entry["files"] == ["lib/b.dart"]

    def test_no_owner_found_is_noop(self, real_pm_registry):
        _pm_registry, registry_file, _lock_file = real_pm_registry
        _seed_registry(registry_file, {})

        lease.release_lease("0.0.0", "0.0.0-W1-999")

        data = json.loads(registry_file.read_text(encoding="utf-8"))
        assert data["sessions"] == {}


# --- ghost forensics ---------------------------------------------------------------


class TestGhostForensics:
    def test_clean_when_no_signals(self, monkeypatch):
        monkeypatch.setattr(lease, "_run_git_lines", lambda args, cwd=None: [])
        body = "## Exit Status\n```yaml\nexit_status: success\n```\n"

        report = lease.run_ghost_forensics("0.0.0-W1-001", ["lib/foo.dart"], body)

        assert report.clean is True

    def test_unmerged_branch_hits(self, monkeypatch):
        def _fake(args, cwd=None):
            if args[0] == "branch":
                return ["  0.0.0-W1-001-wip"]
            return []

        monkeypatch.setattr(lease, "_run_git_lines", _fake)

        report = lease.run_ghost_forensics("0.0.0-W1-001", [], "## Exit Status\nfilled\n")

        assert report.unmerged_branch is True
        assert "0.0.0-W1-001-wip" in report.unmerged_branch_names
        assert report.clean is False

    def test_dirty_file_intersection_hits(self, monkeypatch):
        def _fake(args, cwd=None):
            if args[0] == "status":
                return [" M lib/foo.dart"]
            return []

        monkeypatch.setattr(lease, "_run_git_lines", _fake)

        report = lease.run_ghost_forensics("0.0.0-W1-001", ["lib/foo.dart"], "## Exit Status\nfilled\n")

        assert report.dirty_intersection is True
        assert "lib/foo.dart" in report.dirty_files
        assert report.clean is False

    def test_exit_status_placeholder_hits(self, monkeypatch):
        monkeypatch.setattr(lease, "_run_git_lines", lambda args, cwd=None: [])
        body = "## Exit Status\n<!-- 代理人結束時以 YAML 格式回報 -->\n"

        report = lease.run_ghost_forensics("0.0.0-W1-001", [], body)

        assert report.exit_status_missing is True
        assert report.clean is False

    def test_exit_status_section_absent_hits(self, monkeypatch):
        monkeypatch.setattr(lease, "_run_git_lines", lambda args, cwd=None: [])

        report = lease.run_ghost_forensics("0.0.0-W1-001", [], "no exit status section here")

        assert report.exit_status_missing is True

    def test_render_ghost_report_includes_all_three_checks(self):
        report = lease.GhostReport(
            unmerged_branch=True,
            unmerged_branch_names=["0.0.0-W1-001-wip"],
            dirty_intersection=False,
            exit_status_missing=True,
        )

        text = lease.render_ghost_report("0.0.0-W1-001", report)

        assert "未合併分支" in text
        assert "髒檔交集" in text
        assert "Exit Status" in text
        assert "拒絕 reclaim" in text


# --- _run_git_lines：查詢失敗與「無命中」須可辨識（Phase 4 審查修正 1）--------


class TestRunGitLinesUnknownDetection:
    """`_run_git_lines` 回傳 `None`（查詢失敗，無法辨識）與 `[]`（查詢成功、
    無輸出）須語意不同——先前兩者皆回傳 `[]`，使 ghost 鑑識把「查詢失敗」
    誤判為「無命中」而放行，安全方向錯誤。此二測試補齊審查指出的零覆蓋
    路徑：git_utils 模組載入失敗、`run_git_command` 執行失敗。
    """

    def test_returns_none_when_git_utils_unavailable(self, monkeypatch):
        monkeypatch.setattr(lease, "_load_git_utils", lambda: None)

        result = lease._run_git_lines(["branch", "--no-merged"])

        assert result is None

    def test_returns_none_when_run_git_command_fails(self, monkeypatch):
        class _FakeGitUtils:
            @staticmethod
            def run_git_command(args, cwd=None):
                return False, "fatal: not a git repository"

        monkeypatch.setattr(lease, "_load_git_utils", lambda: _FakeGitUtils())

        result = lease._run_git_lines(["status", "--porcelain"])

        assert result is None

    def test_returns_empty_list_when_command_succeeds_with_no_output(self, monkeypatch):
        class _FakeGitUtils:
            @staticmethod
            def run_git_command(args, cwd=None):
                return True, ""

        monkeypatch.setattr(lease, "_load_git_utils", lambda: _FakeGitUtils())

        result = lease._run_git_lines(["status", "--porcelain"])

        assert result == []


class TestGhostForensicsUnknownPropagation:
    """`run_ghost_forensics` 對查詢失敗（`_run_git_lines` 回傳 `None`）須
    標記對應 `*_unknown` 欄位，並使整體 `clean` 為 False（拒絕，非通過）。
    """

    def test_branch_query_failure_marks_unknown_and_rejects(self, monkeypatch):
        def _fake(args, cwd=None):
            if args[0] == "branch":
                return None
            return []

        monkeypatch.setattr(lease, "_run_git_lines", _fake)

        report = lease.run_ghost_forensics(
            "0.0.0-W1-001", [], "## Exit Status\n```yaml\nexit_status: success\n```\n"
        )

        assert report.unmerged_branch_unknown is True
        assert report.unmerged_branch is False  # 未知不等於命中，欄位語意分離
        assert report.clean is False

    def test_dirty_query_failure_marks_unknown_and_rejects(self, monkeypatch):
        def _fake(args, cwd=None):
            if args[0] == "status":
                return None
            return []

        monkeypatch.setattr(lease, "_run_git_lines", _fake)

        report = lease.run_ghost_forensics(
            "0.0.0-W1-001",
            ["lib/foo.dart"],
            "## Exit Status\n```yaml\nexit_status: success\n```\n",
        )

        assert report.dirty_intersection_unknown is True
        assert report.dirty_intersection is False
        assert report.clean is False

    def test_dirty_query_not_attempted_when_no_ticket_files(self, monkeypatch):
        """ticket_files 為空時第 2 查本就跳過（無比對對象），非「查詢失敗」，
        不應標記 unknown（維持與原設計相同的 n/a 語意）。"""
        monkeypatch.setattr(lease, "_run_git_lines", lambda args, cwd=None: None)

        report = lease.run_ghost_forensics(
            "0.0.0-W1-001", [], "## Exit Status\n```yaml\nexit_status: success\n```\n"
        )

        assert report.dirty_intersection_unknown is False

    def test_render_ghost_report_shows_unable_to_determine_for_unknown(self):
        report = lease.GhostReport(unmerged_branch_unknown=True, dirty_intersection_unknown=True)

        text = lease.render_ghost_report("0.0.0-W1-001", report)

        assert text.count("無法判定") == 2
        assert "拒絕 reclaim" in text


class TestDirtyFilePaths:
    """`_dirty_file_paths` 複用 `.claude/lib/git_utils` 的欄位切分常數
    （Phase 4 審查修正 7，取代已刪除的 `_parse_porcelain_path`）。"""

    def test_parses_modified_file(self):
        assert lease._dirty_file_paths([" M lib/foo.dart"]) == ["lib/foo.dart"]

    def test_rename_takes_new_path(self):
        assert lease._dirty_file_paths(
            ["R  old_name.py -> new_name.py"]
        ) == ["new_name.py"]

    def test_untracked_file(self):
        assert lease._dirty_file_paths(["?? new_file.dart"]) == ["new_file.dart"]

    def test_quoted_path_unquoted(self):
        assert lease._dirty_file_paths(['?? "path with space.dart"']) == [
            "path with space.dart"
        ]

    def test_short_lines_skipped(self):
        assert lease._dirty_file_paths(["", "M"]) == []


# --- check_reclaimable ---------------------------------------------------------------


class TestCheckReclaimable:
    def test_not_in_progress_rejected(self):
        ticket = {"status": "pending"}

        ok, _reason, owner = lease.check_reclaimable(
            ticket, "0.0.0-W1-001", {"sessions": {}}, None, NOW
        )

        assert ok is False
        assert owner is None

    def test_untracked_in_registry_allowed(self):
        ticket = {"status": "in_progress"}

        ok, _reason, owner = lease.check_reclaimable(
            ticket, "0.0.0-W1-001", {"sessions": {}}, None, NOW
        )

        assert ok is True
        assert owner is None

    def test_fresh_owner_rejected(self, real_pm_registry):
        pm_registry, _registry_file, _lock_file = real_pm_registry
        ticket = {"status": "in_progress"}
        registry = {
            "sessions": {"sess-A": {"tickets": ["0.0.0-W1-001"], "heartbeat_ts": _fresh_ts()}}
        }

        ok, _reason, owner = lease.check_reclaimable(
            ticket, "0.0.0-W1-001", registry, pm_registry, NOW
        )

        assert ok is False
        assert owner == "sess-A"

    def test_stale_owner_allowed(self, real_pm_registry):
        pm_registry, _registry_file, _lock_file = real_pm_registry
        ticket = {"status": "in_progress"}
        registry = {
            "sessions": {
                "sess-A": {
                    "tickets": ["0.0.0-W1-001"],
                    "heartbeat_ts": _stale_ts(),
                }
            }
        }

        ok, _reason, owner = lease.check_reclaimable(
            ticket, "0.0.0-W1-001", registry, pm_registry, NOW
        )

        assert ok is True
        assert owner == "sess-A"


# --- check_release_guard ---------------------------------------------------------------


class TestCheckReleaseGuard:
    """`ticket track release` 前置閘門：非自身 FRESH lease 持有時拒絕，
    需 `--force-release-others` 顯式旁路。與 TestReleaseLease 互補——
    後者驗證 lease 移除的機械行為，本類驗證「是否該移除」的閘門判定。
    """

    def test_untracked_in_registry_allows_release(self, real_pm_registry):
        _pm_registry, registry_file, _lock_file = real_pm_registry
        _seed_registry(registry_file, {})

        allowed, reason = lease.check_release_guard("0.0.0-W1-999", now=NOW)

        assert allowed is True
        assert "0.0.0-W1-999" in reason

    def test_self_session_owner_allows_release(self, real_pm_registry, monkeypatch):
        _pm_registry, registry_file, _lock_file = real_pm_registry
        monkeypatch.setenv(lease.ENV_SESSION_ID, "sess-A")
        monkeypatch.setattr(lease, "_current_project_root", lambda: "/proj")
        _seed_registry(registry_file, {
            "sess-A": {
                "project": "/proj",
                "heartbeat_ts": _fresh_ts(),
                "tickets": ["0.0.0-W1-001"],
                "files": [],
            },
        })

        allowed, reason = lease.check_release_guard("0.0.0-W1-001", now=NOW)

        assert allowed is True
        assert "自身" in reason

    def test_other_fresh_owner_blocks_release(self, real_pm_registry, monkeypatch):
        _pm_registry, registry_file, _lock_file = real_pm_registry
        monkeypatch.setenv(lease.ENV_SESSION_ID, "sess-A")
        monkeypatch.setattr(lease, "_current_project_root", lambda: "/proj")
        _seed_registry(registry_file, {
            "sess-A": {
                "project": "/proj",
                "heartbeat_ts": _fresh_ts(),
                "tickets": [],
                "files": [],
            },
            "sess-B": {
                "project": "/proj",
                "heartbeat_ts": _fresh_ts(),
                "tickets": ["0.0.0-W1-001"],
                "files": [],
            },
        })

        allowed, reason = lease.check_release_guard("0.0.0-W1-001", now=NOW)

        assert allowed is False
        assert "sess-B" in reason
        assert "--force-release-others" in reason

    def test_other_stale_owner_allows_release(self, real_pm_registry, monkeypatch):
        _pm_registry, registry_file, _lock_file = real_pm_registry
        monkeypatch.setenv(lease.ENV_SESSION_ID, "sess-A")
        monkeypatch.setattr(lease, "_current_project_root", lambda: "/proj")
        _seed_registry(registry_file, {
            "sess-A": {
                "project": "/proj",
                "heartbeat_ts": _fresh_ts(),
                "tickets": [],
                "files": [],
            },
            "sess-B": {
                "project": "/proj",
                "heartbeat_ts": _stale_ts(),
                "tickets": ["0.0.0-W1-001"],
                "files": [],
            },
        })

        allowed, reason = lease.check_release_guard("0.0.0-W1-001", now=NOW)

        assert allowed is True
        assert "sess-B" in reason

    def test_pm_registry_unavailable_fails_open(self, monkeypatch):
        monkeypatch.setattr(lease, "_load_pm_registry", lambda: None)

        allowed, reason = lease.check_release_guard("0.0.0-W1-001", now=NOW)

        assert allowed is True
        assert "pm_registry 模組不可用" in reason

    def test_project_root_unresolvable_still_blocks_other_fresh_owner(
        self, real_pm_registry, monkeypatch
    ):
        """自身 session_id 因非 git 環境等原因無法解析時，仍以 registry 現有
        owner 資料判定——不可因「無法確認自己是誰」就放行對他人 FRESH lease
        的釋放（fail-open 僅適用於模組/registry 層級不可用，非自身身份缺失）。
        """
        _pm_registry, registry_file, _lock_file = real_pm_registry
        monkeypatch.setattr(lease, "_current_project_root", lambda: None)
        _seed_registry(registry_file, {
            "sess-B": {
                "project": "/proj",
                "heartbeat_ts": _fresh_ts(),
                "tickets": ["0.0.0-W1-001"],
                "files": [],
            },
        })

        allowed, reason = lease.check_release_guard("0.0.0-W1-001", now=NOW)

        assert allowed is False
        assert "sess-B" in reason


# --- reclaim_ticket：dry-run / 拒絕路徑 ---------------------------------------


class TestReclaimTicketDryRun:
    def test_dry_run_reports_and_does_not_write(self, real_pm_registry, monkeypatch, capsys):
        _pm_registry, registry_file, _lock_file = real_pm_registry
        _seed_registry(registry_file, {
            "sess-A": {
                "project": "/proj",
                "heartbeat_ts": _stale_ts(),
                "tickets": ["0.0.0-W1-001"],
                "files": ["lib/foo.dart"],
            },
        })
        ticket = {
            "id": "0.0.0-W1-001",
            "status": "in_progress",
            "where": {"files": ["lib/foo.dart"]},
            "_body": "## Exit Status\n```yaml\nexit_status: success\n```\n",
        }
        monkeypatch.setattr(lease, "load_ticket", lambda version, tid: ticket)
        monkeypatch.setattr(lease, "_run_git_lines", lambda args, cwd=None: [])

        rc = lease.reclaim_ticket("0.0.0", "0.0.0-W1-001", confirm=False, now=NOW)

        assert rc == 0
        out = capsys.readouterr().out
        assert "dry-run" in out
        data = json.loads(registry_file.read_text(encoding="utf-8"))
        assert data["sessions"]["sess-A"]["tickets"] == ["0.0.0-W1-001"]

    def test_rejects_when_fresh_session_holds_it(self, real_pm_registry, monkeypatch):
        _pm_registry, registry_file, _lock_file = real_pm_registry
        _seed_registry(registry_file, {
            "sess-A": {
                "project": "/proj",
                "heartbeat_ts": _fresh_ts(),
                "tickets": ["0.0.0-W1-001"],
                "files": [],
            },
        })
        ticket = {"id": "0.0.0-W1-001", "status": "in_progress", "where": {"files": []}, "_body": ""}
        monkeypatch.setattr(lease, "load_ticket", lambda version, tid: ticket)

        rc = lease.reclaim_ticket("0.0.0", "0.0.0-W1-001", confirm=False, now=NOW)

        assert rc == 1

    def test_rejects_when_ghost_signal_hits(self, real_pm_registry, monkeypatch, capsys):
        _pm_registry, registry_file, _lock_file = real_pm_registry
        _seed_registry(registry_file, {
            "sess-A": {
                "project": "/proj",
                "heartbeat_ts": _stale_ts(),
                "tickets": ["0.0.0-W1-001"],
                "files": ["lib/foo.dart"],
            },
        })
        ticket = {
            "id": "0.0.0-W1-001",
            "status": "in_progress",
            "where": {"files": ["lib/foo.dart"]},
            "_body": "## Exit Status\n```yaml\nexit_status: success\n```\n",
        }
        monkeypatch.setattr(lease, "load_ticket", lambda version, tid: ticket)
        monkeypatch.setattr(
            lease, "_run_git_lines",
            lambda args, cwd=None: (["  0.0.0-W1-001-wip"] if args[0] == "branch" else []),
        )

        rc = lease.reclaim_ticket("0.0.0", "0.0.0-W1-001", confirm=False, now=NOW)

        assert rc == 1
        out = capsys.readouterr().out
        assert "先對帳未合併分支/髒檔再重試" in out  # Phase 4 審查修正 9：拒絕訊息補下一步

    def test_ticket_not_found_returns_error(self, real_pm_registry, monkeypatch):
        _pm_registry, registry_file, _lock_file = real_pm_registry
        _seed_registry(registry_file, {})
        monkeypatch.setattr(lease, "load_ticket", lambda version, tid: None)

        rc = lease.reclaim_ticket("0.0.0", "0.0.0-W1-MISSING", confirm=False)

        assert rc == 1


# --- reclaim_ticket：--confirm 路徑（真實票面轉換） ---------------------------


@pytest.fixture
def tmp_ticket_dir(tmp_path: Path) -> Path:
    d = tmp_path / "tickets"
    d.mkdir()
    return d


def _write_in_progress_ticket(path: Path, tid: str) -> None:
    """最小合法 ticket，status=in_progress，where.files 供 ghost 鑑識比對。"""
    lines = [
        "---",
        f"id: {tid}",
        "title: reclaim target",
        "type: IMP",
        "status: in_progress",
        "assigned: true",
        "started_at: '2026-05-29T10:00:00'",
        "acceptance: []",
        "tdd_phase: ''",
        "children: []",
        "blockedBy: []",
        "where:",
        "  files:",
        "  - lib/foo.dart",
        "---",
        "",
        "## Exit Status",
        "```yaml",
        "exit_status: success",
        "```",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


@pytest.fixture
def patch_reclaim_ticket_paths(tmp_ticket_dir, monkeypatch):
    """重導 lease 模組內部的 get_ticket_path / load_ticket 至 tmp dir。

    `load_and_validate_ticket` / `resolve_ticket_path` 內部依賴 ticket_ops /
    ticket_loader 自身模組綁定的 load_ticket / get_ticket_path，需一併重導
    （同 test_release_status_semantics.py 的 patch_ticket_paths 模式）。
    """
    from ticket_system.lib.parser import parse_frontmatter
    from ticket_system.lib import parser as parser_mod
    from ticket_system.lib import ticket_ops, ticket_loader

    def _fake_get_ticket_path(version: str, ticket_id: str) -> Path:
        return tmp_ticket_dir / f"{ticket_id}.md"

    def _fake_load_ticket(version: str, ticket_id: str):
        path = tmp_ticket_dir / f"{ticket_id}.md"
        if not path.exists():
            return None
        fm, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        if not fm:
            return None
        fm["_body"] = body
        fm["_path"] = str(path)
        return fm

    monkeypatch.setattr(lease, "get_ticket_path", _fake_get_ticket_path)
    monkeypatch.setattr(lease, "load_ticket", _fake_load_ticket)
    monkeypatch.setattr(ticket_loader, "get_ticket_path", _fake_get_ticket_path)
    monkeypatch.setattr(ticket_loader, "load_ticket", _fake_load_ticket)
    monkeypatch.setattr(ticket_ops, "get_ticket_path", _fake_get_ticket_path)
    monkeypatch.setattr(ticket_ops, "load_ticket", _fake_load_ticket)

    yield

    try:
        parser_mod._ticket_cache.clear()
    except Exception:
        pass


class TestReclaimTicketConfirm:
    def test_confirm_transitions_to_pending_and_clears_lease(
        self, tmp_ticket_dir, patch_reclaim_ticket_paths, real_pm_registry, monkeypatch
    ):
        _pm_registry, registry_file, _lock_file = real_pm_registry
        tid = "0.0.0-W0-RECLAIM"
        _write_in_progress_ticket(tmp_ticket_dir / f"{tid}.md", tid)
        _seed_registry(registry_file, {
            "sess-A": {
                "project": "/proj",
                "heartbeat_ts": _stale_ts(),
                "tickets": [tid],
                "files": ["lib/foo.dart"],
            }
        })
        monkeypatch.setattr(lease, "_run_git_lines", lambda args, cwd=None: [])

        rc = lease.reclaim_ticket("0.0.0", tid, confirm=True, now=NOW)

        assert rc == 0
        from ticket_system.lib.parser import parse_frontmatter
        fm, _body = parse_frontmatter((tmp_ticket_dir / f"{tid}.md").read_text(encoding="utf-8"))
        assert fm.get("status") == "pending"
        assert fm.get("assigned") is False
        assert fm.get("started_at") in (None, "null", "")

        data = json.loads(registry_file.read_text(encoding="utf-8"))
        assert data["sessions"]["sess-A"]["tickets"] == []
        assert data["sessions"]["sess-A"]["files"] == []

    def test_confirm_rejected_by_ghost_signal_leaves_ticket_untouched(
        self, tmp_ticket_dir, patch_reclaim_ticket_paths, real_pm_registry, monkeypatch
    ):
        _pm_registry, registry_file, _lock_file = real_pm_registry
        tid = "0.0.0-W0-RECLAIMBLOCKED"
        _write_in_progress_ticket(tmp_ticket_dir / f"{tid}.md", tid)
        _seed_registry(registry_file, {
            "sess-A": {
                "project": "/proj",
                "heartbeat_ts": _stale_ts(),
                "tickets": [tid],
                "files": ["lib/foo.dart"],
            }
        })
        monkeypatch.setattr(
            lease, "_run_git_lines",
            lambda args, cwd=None: ([" M lib/foo.dart"] if args[0] == "status" else []),
        )

        rc = lease.reclaim_ticket("0.0.0", tid, confirm=True, now=NOW)

        assert rc == 1
        from ticket_system.lib.parser import parse_frontmatter
        fm, _body = parse_frontmatter((tmp_ticket_dir / f"{tid}.md").read_text(encoding="utf-8"))
        assert fm.get("status") == "in_progress"

        data = json.loads(registry_file.read_text(encoding="utf-8"))
        assert data["sessions"]["sess-A"]["tickets"] == [tid]


class TestApplyReclaimErrorPropagation:
    """Phase 4 審查修正 10：`_apply_reclaim` 失敗時須回傳
    `load_and_validate_ticket` 的原始錯誤訊息（非僅 bool），
    `reclaim_ticket` 須將其帶入 stderr（先前錯誤原因被吞掉）。"""

    def test_apply_reclaim_returns_error_message_on_missing_ticket(
        self, tmp_ticket_dir, patch_reclaim_ticket_paths
    ):
        # 未寫入任何 ticket 檔，_fake_load_ticket 回傳 None → TICKET_NOT_FOUND
        error = lease._apply_reclaim("0.0.0", "0.0.0-W0-GHOST")

        assert error is not None
        assert isinstance(error, str)

    def test_reclaim_ticket_surfaces_apply_error_to_stderr(
        self, tmp_ticket_dir, patch_reclaim_ticket_paths, real_pm_registry, monkeypatch, capsys
    ):
        _pm_registry, registry_file, _lock_file = real_pm_registry
        tid = "0.0.0-W0-RECLAIMVANISH"
        # dry-run 檢查通過所需的 ticket 資料由 monkeypatch 提供（模擬 reclaim_ticket
        # 頂層讀到票存在，但 _apply_reclaim 內部第二次讀取時已消失的競態）
        ticket = {
            "id": tid,
            "status": "in_progress",
            "where": {"files": []},
            "_body": "## Exit Status\n```yaml\nexit_status: success\n```\n",
        }
        monkeypatch.setattr(lease, "load_ticket", lambda version, t: ticket)
        monkeypatch.setattr(lease, "_run_git_lines", lambda args, cwd=None: [])
        _seed_registry(registry_file, {
            "sess-A": {
                "project": "/proj",
                "heartbeat_ts": _stale_ts(),
                "tickets": [tid],
                "files": [],
            }
        })
        # patch_reclaim_ticket_paths 的 _fake_load_ticket 讀真實 tmp 檔（未寫入，
        # 檔案不存在）——_apply_reclaim 內部的 load_and_validate_ticket 因而失敗，
        # 與頂層 monkeypatch 提供的 ticket 資料形成刻意分歧，模擬競態

        rc = lease.reclaim_ticket("0.0.0", tid, confirm=True, now=NOW)

        assert rc == 1
        err = capsys.readouterr().err
        assert "票面更新失敗" in err
        assert "：" in err  # 錯誤訊息須帶有具體原因，非僅固定字面
