"""Tests for ticket_system/commands/track_dispatch_check.py (0.18.0-W10-017.2).

5 情境覆蓋（AC5 要求 3 情境，補 no_file 與 malformed 作邊界）：
1. no_file: 檔案不存在 → exit 0 + [PASS]
2. empty_list: dispatches=[] → exit 0 + [PASS]
3. single: 1 個活躍 → exit 1 + [WARN] + 1 筆列表
4. multiple: 3 個活躍 → exit 1 + [WARN] + 3 筆列表
5. malformed_json: JSON 毀損 → exit 2 + stderr [FAIL]

新鮮度維度（0.2.1-W3-1323，3-H 個案 1／2）：判定原只收「dispatches 是否
為空」，PM 依 WARN 後無從分辨活躍派發是剛發出還是已逾時遺留。新增每筆
記錄年齡標註（逾 60 分鐘標 [STALE]，沿用 track_dashboard 同一新鮮度慣例）
與彙總計數。

`--prune`（3-F M-6）：清理「[STALE] 且 session 不存在」的條目，取代文件
原載「見 [STALE] 手動清理 dispatch-active.json」的無痕跡做法，見
TestPruneFlag。

`--prune` 票終態判準（0.2.1-W3-1371）：新增第二條獨立清理判準——
ticket_id 非空且對應票已為終態（completed/closed）即清理，不要求
[STALE] 或 session 存在性（票已終態代表對應派發不可能仍在進行，判準
權威來源是票狀態本身，不需 session 存活佐證）。此判準不受 registry
是否可用影響，見 TestPruneTerminalTicket / TestIsTicketTerminal。
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

import pytest

from ticket_system.commands import track_dispatch_check as mod
from ticket_system.commands.track_dispatch_check import execute_dispatch_check


def _run(tmp_path: Path, monkeypatch, *, prune: bool = False) -> tuple[int, str, str]:
    """呼叫 execute_dispatch_check 並捕獲 stdout/stderr。"""
    monkeypatch.setattr(mod, "get_ticket_state_root", lambda: tmp_path)

    args = argparse.Namespace(prune=prune)
    out_buf, err_buf = io.StringIO(), io.StringIO()
    saved_out, saved_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = out_buf, err_buf
    try:
        rc = execute_dispatch_check(args)
    finally:
        sys.stdout, sys.stderr = saved_out, saved_err
    return rc, out_buf.getvalue(), err_buf.getvalue()


def _write_dispatch_file(tmp_path: Path, payload: object) -> Path:
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    path = claude_dir / "dispatch-active.json"
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class TestDispatchCheck:

    def test_no_file(self, tmp_path, monkeypatch):
        """檔案不存在 → exit 0，視同已清空。"""
        rc, out, err = _run(tmp_path, monkeypatch)
        assert rc == 0
        assert "[PASS]" in out
        assert "無活躍派發" in out
        assert err == ""

    def test_empty_list(self, tmp_path, monkeypatch):
        """dispatches=[] → exit 0。"""
        _write_dispatch_file(tmp_path, {"dispatches": []})
        rc, out, err = _run(tmp_path, monkeypatch)
        assert rc == 0
        assert "[PASS]" in out
        assert err == ""

    def test_single_dispatch(self, tmp_path, monkeypatch):
        """1 個活躍派發 → exit 1，列出該筆。"""
        _write_dispatch_file(tmp_path, {
            "dispatches": [
                {
                    "agent_description": "test-agent-alpha",
                    "ticket_id": "0.18.0-W10-017.2",
                    "dispatched_at": "2026-04-20T04:00:00+00:00",
                },
            ],
        })
        rc, out, err = _run(tmp_path, monkeypatch)
        assert rc == 1
        assert "[WARN]" in out
        assert "有 1 個活躍派發" in out
        assert "test-agent-alpha" in out
        assert "0.18.0-W10-017.2" in out
        assert "2026-04-20T04:00:00+00:00" in out

    def test_multiple_dispatches(self, tmp_path, monkeypatch):
        """3 個活躍派發 → exit 1，全部列出。"""
        _write_dispatch_file(tmp_path, {
            "dispatches": [
                {"agent_description": "alpha", "ticket_id": "A", "dispatched_at": "t1"},
                {"agent_description": "beta", "ticket_id": "", "dispatched_at": "t2"},
                {"agent_description": "gamma", "dispatched_at": "t3"},
            ],
        })
        rc, out, err = _run(tmp_path, monkeypatch)
        assert rc == 1
        assert "[WARN]" in out
        assert "有 3 個活躍派發" in out
        assert "alpha" in out
        assert "beta" in out
        assert "gamma" in out
        assert "(no ticket)" in out  # beta 的 ticket_id="" 與 gamma 的缺欄位皆顯示 fallback

    def test_malformed_json(self, tmp_path, monkeypatch):
        """JSON 格式錯誤 → exit 2，stderr 寫 [FAIL]。"""
        _write_dispatch_file(tmp_path, "{this is not valid json")
        rc, out, err = _run(tmp_path, monkeypatch)
        assert rc == 2
        assert "[FAIL]" in err
        assert "JSON 格式錯誤" in err

    def test_non_dict_root(self, tmp_path, monkeypatch):
        """root 不是 dict（list）→ exit 2。"""
        _write_dispatch_file(tmp_path, [1, 2, 3])
        rc, out, err = _run(tmp_path, monkeypatch)
        assert rc == 2
        assert "[FAIL]" in err

    def test_dispatches_not_list(self, tmp_path, monkeypatch):
        """dispatches 欄位不是 list → exit 2。"""
        _write_dispatch_file(tmp_path, {"dispatches": "should be list"})
        rc, out, err = _run(tmp_path, monkeypatch)
        assert rc == 2
        assert "[FAIL]" in err


class TestFreshnessDimension:
    """0.2.1-W3-1323（3-H 個案 1／2）：dispatch-check 補新鮮度維度。"""

    def test_recent_dispatch_not_marked_stale(self, tmp_path, monkeypatch):
        """剛派發（< 60 分鐘）不標 [STALE]。"""
        from datetime import datetime, timedelta, timezone

        recent = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        _write_dispatch_file(tmp_path, {
            "dispatches": [
                {"agent_description": "fresh-agent", "ticket_id": "A", "dispatched_at": recent},
            ],
        })
        rc, out, err = _run(tmp_path, monkeypatch)
        assert rc == 1
        assert "[STALE" not in out

    def test_old_dispatch_marked_stale_with_summary_count(self, tmp_path, monkeypatch):
        """逾 60 分鐘的活躍記錄標 [STALE] 並在彙總行給出計數與下一步建議。"""
        from datetime import datetime, timedelta, timezone

        old = (datetime.now(timezone.utc) - timedelta(minutes=90)).isoformat()
        _write_dispatch_file(tmp_path, {
            "dispatches": [
                {"agent_description": "stale-agent", "ticket_id": "A", "dispatched_at": old},
            ],
        })
        rc, out, err = _run(tmp_path, monkeypatch)
        assert rc == 1
        assert "[STALE" in out
        assert "其中 1 筆" in out
        assert "track sessions" in out

    def test_malformed_dispatched_at_not_marked_stale(self, tmp_path, monkeypatch):
        """dispatched_at 缺失或格式錯誤時不猜測，不標 [STALE]（回歸：
        既有測試以 "t1"/"t2"/"t3" 等非 ISO 字面值仍需維持綠燈）。"""
        _write_dispatch_file(tmp_path, {
            "dispatches": [
                {"agent_description": "malformed-ts", "ticket_id": "A", "dispatched_at": "not-a-timestamp"},
                {"agent_description": "missing-ts", "ticket_id": "B"},
            ],
        })
        rc, out, err = _run(tmp_path, monkeypatch)
        assert rc == 1
        assert "[STALE" not in out


class TestPruneFlag:
    """3-F M-6：`--prune` 清理「[STALE] 且 session 不存在」的條目。"""

    def test_prune_removes_stale_entry_with_missing_session(self, tmp_path, monkeypatch):
        """session_id 不在 registry 內 + [STALE] → 清理，票面/回傳皆歸零。"""
        from datetime import datetime, timedelta, timezone

        old = (datetime.now(timezone.utc) - timedelta(minutes=90)).isoformat()
        dispatch_path = _write_dispatch_file(tmp_path, {
            "dispatches": [
                {
                    "agent_description": "gone-agent",
                    "ticket_id": "A",
                    "dispatched_at": old,
                    "session_id": "sess-dead",
                },
            ],
        })
        monkeypatch.setattr(mod, "_load_registry_session_ids", lambda: set())
        monkeypatch.setattr(mod, "_get_prune_logger", lambda: None)

        rc, out, err = _run(tmp_path, monkeypatch, prune=True)

        assert rc == 0
        assert "[PASS]" in out
        assert "已清理 1 筆" in out
        assert "gone-agent" in err
        assert "sess-dead" in err
        remaining = json.loads(dispatch_path.read_text(encoding="utf-8"))
        assert remaining["dispatches"] == []

    def test_prune_removes_empty_ticket_id_entry_after_session_confirmed_gone(
        self, tmp_path, monkeypatch
    ):
        """反事實測試（0.2.1-W3-1371 acceptance）：空 `ticket_id`（無票
        派發）記錄，agent 終止後（session 已不在 pm-registry）立即消失，
        不等 24 小時的 `cleanup_expired` TTL——本測試全程不呼叫
        `cleanup_expired`，`dispatched_at` 僅 65 分鐘前（距 24 小時 TTL
        邊界甚遠，僅剛過 [STALE] 60 分鐘門檻），故條目消失唯一可能原因
        是本函式的 session 存活判準（既有機制，獨立於 ticket 事件），
        非 24 小時逾時路徑。"""
        from datetime import datetime, timedelta, timezone

        just_past_stale_threshold = (
            datetime.now(timezone.utc) - timedelta(minutes=65)
        ).isoformat()
        dispatch_path = _write_dispatch_file(tmp_path, {
            "dispatches": [
                {
                    "agent_description": "no-ticket-reviewer",
                    "ticket_id": "",
                    "dispatched_at": just_past_stale_threshold,
                    "session_id": "sess-terminated",
                },
            ],
        })
        monkeypatch.setattr(mod, "_load_registry_session_ids", lambda: set())
        monkeypatch.setattr(mod, "_get_prune_logger", lambda: None)

        rc, out, err = _run(tmp_path, monkeypatch, prune=True)

        assert rc == 0
        assert "[PASS]" in out
        remaining = json.loads(dispatch_path.read_text(encoding="utf-8"))
        assert remaining["dispatches"] == []

    def test_prune_keeps_stale_entry_with_existing_session(self, tmp_path, monkeypatch):
        """session_id 仍在 registry 內（heartbeat 慢但仍存活）→ 不清理，
        即使該條目年齡已逾 [STALE] 門檻。"""
        from datetime import datetime, timedelta, timezone

        old = (datetime.now(timezone.utc) - timedelta(minutes=90)).isoformat()
        dispatch_path = _write_dispatch_file(tmp_path, {
            "dispatches": [
                {
                    "agent_description": "slow-heartbeat-agent",
                    "ticket_id": "A",
                    "dispatched_at": old,
                    "session_id": "sess-alive",
                },
            ],
        })
        monkeypatch.setattr(mod, "_load_registry_session_ids", lambda: {"sess-alive"})

        rc, out, err = _run(tmp_path, monkeypatch, prune=True)

        assert rc == 1
        assert "無符合" in out
        assert "slow-heartbeat-agent" in out
        assert "[STALE" in out
        remaining = json.loads(dispatch_path.read_text(encoding="utf-8"))
        assert len(remaining["dispatches"]) == 1

    def test_prune_keeps_entry_without_session_id(self, tmp_path, monkeypatch):
        """session_id 缺失／空字串（無法歸戶）→ 保守保留，不視為不存在。"""
        from datetime import datetime, timedelta, timezone

        old = (datetime.now(timezone.utc) - timedelta(minutes=90)).isoformat()
        _write_dispatch_file(tmp_path, {
            "dispatches": [
                {"agent_description": "no-session-agent", "ticket_id": "A", "dispatched_at": old},
            ],
        })
        monkeypatch.setattr(mod, "_load_registry_session_ids", lambda: set())

        rc, out, err = _run(tmp_path, monkeypatch, prune=True)

        assert rc == 1
        assert "無符合" in out
        assert "no-session-agent" in out

    def test_prune_skips_when_registry_unavailable(self, tmp_path, monkeypatch):
        """registry 讀取失敗（回傳 None）→ 保守不清理，訊息與「無符合條件」
        區分，不誤報為已確認無需清理。"""
        from datetime import datetime, timedelta, timezone

        old = (datetime.now(timezone.utc) - timedelta(minutes=90)).isoformat()
        dispatch_path = _write_dispatch_file(tmp_path, {
            "dispatches": [
                {
                    "agent_description": "unverifiable-agent",
                    "ticket_id": "A",
                    "dispatched_at": old,
                    "session_id": "sess-unknown",
                },
            ],
        })
        monkeypatch.setattr(mod, "_load_registry_session_ids", lambda: None)

        rc, out, err = _run(tmp_path, monkeypatch, prune=True)

        assert rc == 1
        assert "不可用" in out
        assert "無法判定" in out
        remaining = json.loads(dispatch_path.read_text(encoding="utf-8"))
        assert len(remaining["dispatches"]) == 1

    def test_prune_flag_absent_leaves_file_and_behavior_unchanged(self, tmp_path, monkeypatch):
        """未帶 --prune 時行為與既有版本一致（回歸：預設不清理）。"""
        from datetime import datetime, timedelta, timezone

        old = (datetime.now(timezone.utc) - timedelta(minutes=90)).isoformat()
        dispatch_path = _write_dispatch_file(tmp_path, {
            "dispatches": [
                {
                    "agent_description": "gone-agent",
                    "ticket_id": "A",
                    "dispatched_at": old,
                    "session_id": "sess-dead",
                },
            ],
        })
        monkeypatch.setattr(mod, "_load_registry_session_ids", lambda: set())

        rc, out, err = _run(tmp_path, monkeypatch, prune=False)

        assert rc == 1
        assert "[WARN]" in out
        remaining = json.loads(dispatch_path.read_text(encoding="utf-8"))
        assert len(remaining["dispatches"]) == 1

    def test_prune_writes_hook_log_via_real_logger(self, tmp_path, monkeypatch):
        """真實 `setup_hook_logging` 落地：`.claude/hook-logs/
        dispatch-check-prune/` 下應可讀到含清理內容的日誌檔（雙通道驗證，
        非僅 mock 呼叫次數）。

        日誌落點依據（0.1.0-W3-273 修復後）：`_get_prune_logger` 顯式傳入
        `get_ticket_state_root()`，使日誌根目錄與 `dispatch-active.json`
        的狀態根目錄對齊（原本各自解析、worktree 環境下會分裂成兩個
        不同目錄）。本測試的 `_run()` 已將 `mod.get_ticket_state_root`
        monkeypatch 為 `lambda: tmp_path`（供 `dispatch-active.json` 讀寫
        使用），故對齊後日誌根目錄同為 `tmp_path`，不是
        `CLAUDE_PROJECT_DIR`（後者僅在未被此 monkeypatch 覆寫時才是
        `get_ticket_state_root()` 的解析結果，見 `.claude/skills/ticket/
        conftest.py` 的 `_isolate_project_root`）。
        """
        from datetime import datetime, timedelta, timezone

        old = (datetime.now(timezone.utc) - timedelta(minutes=90)).isoformat()
        _write_dispatch_file(tmp_path, {
            "dispatches": [
                {
                    "agent_description": "logged-agent",
                    "ticket_id": "A",
                    "dispatched_at": old,
                    "session_id": "sess-dead",
                },
            ],
        })
        monkeypatch.setattr(mod, "_load_registry_session_ids", lambda: set())

        rc, out, err = _run(tmp_path, monkeypatch, prune=True)

        assert rc == 0
        log_dir = tmp_path / ".claude" / "hook-logs" / "dispatch-check-prune"
        log_files = sorted(log_dir.glob("dispatch-check-prune-*.log"))
        assert log_files, "應產生 .claude/hook-logs/dispatch-check-prune/dispatch-check-prune-*.log"
        content = log_files[0].read_text(encoding="utf-8")
        assert "logged-agent" in content
        assert "sess-dead" in content


class TestIsTicketTerminal:
    """`mod._is_ticket_terminal` 單元測試（0.2.1-W3-1371）：判斷 ticket_id
    對應的票是否為終態，保守失敗（查不到 / 例外一律回傳 False）。"""

    def test_ticket_id_without_version_returns_false(self):
        assert mod._is_ticket_terminal("not-a-ticket-id") is False

    def test_ticket_not_found_returns_false(self, monkeypatch):
        monkeypatch.setattr(
            "ticket_system.lib.ticket_loader.load_ticket",
            lambda version, tid: None,
        )
        assert mod._is_ticket_terminal("0.2.1-W3-1") is False

    def test_completed_status_returns_true(self, monkeypatch):
        monkeypatch.setattr(
            "ticket_system.lib.ticket_loader.load_ticket",
            lambda version, tid: {"status": "completed"},
        )
        assert mod._is_ticket_terminal("0.2.1-W3-1") is True

    def test_closed_status_returns_true(self, monkeypatch):
        monkeypatch.setattr(
            "ticket_system.lib.ticket_loader.load_ticket",
            lambda version, tid: {"status": "closed"},
        )
        assert mod._is_ticket_terminal("0.2.1-W3-1") is True

    def test_in_progress_status_returns_false(self, monkeypatch):
        monkeypatch.setattr(
            "ticket_system.lib.ticket_loader.load_ticket",
            lambda version, tid: {"status": "in_progress"},
        )
        assert mod._is_ticket_terminal("0.2.1-W3-1") is False

    def test_load_ticket_exception_returns_false(self, monkeypatch):
        def _raise(version, tid):
            raise RuntimeError("boom")

        monkeypatch.setattr(
            "ticket_system.lib.ticket_loader.load_ticket", _raise
        )
        assert mod._is_ticket_terminal("0.2.1-W3-1") is False


class TestPruneTerminalTicket:
    """`--prune` 的票終態判準（0.2.1-W3-1371）：獨立於 [STALE]／session
    存在性，ticket_id 對應票已終態即清理。"""

    def test_removes_terminal_ticket_entry_even_when_not_stale(
        self, tmp_path, monkeypatch
    ):
        """未逾 [STALE] 門檻的新近記錄，只要對應票已終態即清理——票終態
        判準不要求時間新鮮度。"""
        from datetime import datetime, timezone

        recent = datetime.now(timezone.utc).isoformat()
        _write_dispatch_file(tmp_path, {
            "dispatches": [
                {
                    "agent_description": "fresh-but-ticket-done",
                    "ticket_id": "0.2.1-W3-1275",
                    "dispatched_at": recent,
                },
            ],
        })
        monkeypatch.setattr(mod, "_load_registry_session_ids", lambda: None)
        monkeypatch.setattr(mod, "_is_ticket_terminal", lambda tid: tid == "0.2.1-W3-1275")
        monkeypatch.setattr(mod, "_get_prune_logger", lambda: None)

        rc, out, err = _run(tmp_path, monkeypatch, prune=True)

        assert rc == 0
        assert "[PASS]" in out
        assert "已清理 1 筆" in out

    def test_removes_terminal_ticket_entry_even_when_session_still_alive(
        self, tmp_path, monkeypatch
    ):
        """session 仍在 registry 內（原判準會保留）不影響票終態判準——
        票已完成即代表對應派發不可能仍在進行，不需 session 存活佐證。"""
        from datetime import datetime, timedelta, timezone

        old = (datetime.now(timezone.utc) - timedelta(minutes=90)).isoformat()
        dispatch_path = _write_dispatch_file(tmp_path, {
            "dispatches": [
                {
                    "agent_description": "ticket-done-session-alive",
                    "ticket_id": "0.2.1-W3-1275",
                    "dispatched_at": old,
                    "session_id": "sess-alive",
                },
            ],
        })
        monkeypatch.setattr(mod, "_load_registry_session_ids", lambda: {"sess-alive"})
        monkeypatch.setattr(mod, "_is_ticket_terminal", lambda tid: True)
        monkeypatch.setattr(mod, "_get_prune_logger", lambda: None)

        rc, out, err = _run(tmp_path, monkeypatch, prune=True)

        assert rc == 0
        remaining = json.loads(dispatch_path.read_text(encoding="utf-8"))
        assert remaining["dispatches"] == []

    def test_keeps_entry_with_non_terminal_ticket(self, tmp_path, monkeypatch):
        """非終態票 + 不符合原判準（session 存在）→ 保留。"""
        from datetime import datetime, timedelta, timezone

        old = (datetime.now(timezone.utc) - timedelta(minutes=90)).isoformat()
        _write_dispatch_file(tmp_path, {
            "dispatches": [
                {
                    "agent_description": "still-in-progress",
                    "ticket_id": "0.2.1-W3-2000",
                    "dispatched_at": old,
                    "session_id": "sess-alive",
                },
            ],
        })
        monkeypatch.setattr(mod, "_load_registry_session_ids", lambda: {"sess-alive"})
        monkeypatch.setattr(mod, "_is_ticket_terminal", lambda tid: False)

        rc, out, err = _run(tmp_path, monkeypatch, prune=True)

        assert rc == 1
        assert "無符合" in out
        assert "still-in-progress" in out

    def test_terminal_ticket_criterion_works_when_registry_unavailable(
        self, tmp_path, monkeypatch
    ):
        """registry 不可用（session 存活判準完全無法判定）不影響票終態
        判準——兩者為獨立判準，不因其一不可用而互相拖累。"""
        from datetime import datetime, timedelta, timezone

        old = (datetime.now(timezone.utc) - timedelta(minutes=90)).isoformat()
        dispatch_path = _write_dispatch_file(tmp_path, {
            "dispatches": [
                {
                    "agent_description": "ticket-done-no-registry",
                    "ticket_id": "0.2.1-W3-1275",
                    "dispatched_at": old,
                    "session_id": "sess-unknown",
                },
            ],
        })
        monkeypatch.setattr(mod, "_load_registry_session_ids", lambda: None)
        monkeypatch.setattr(mod, "_is_ticket_terminal", lambda tid: True)
        monkeypatch.setattr(mod, "_get_prune_logger", lambda: None)

        rc, out, err = _run(tmp_path, monkeypatch, prune=True)

        assert rc == 0
        assert "已清理 1 筆" in out
        remaining = json.loads(dispatch_path.read_text(encoding="utf-8"))
        assert remaining["dispatches"] == []

    def test_empty_ticket_id_never_checked_against_terminal_criterion(
        self, tmp_path, monkeypatch
    ):
        """空 ticket_id 一律不查票終態（無票派發不受 ticket 事件驅動，
        清除路徑是 agent 終止事件，非本判準涵蓋範圍）。"""
        from datetime import datetime, timedelta, timezone

        old = (datetime.now(timezone.utc) - timedelta(minutes=90)).isoformat()
        _write_dispatch_file(tmp_path, {
            "dispatches": [
                {
                    "agent_description": "no-ticket-reviewer",
                    "ticket_id": "",
                    "dispatched_at": old,
                    "session_id": "sess-alive",
                },
            ],
        })
        monkeypatch.setattr(mod, "_load_registry_session_ids", lambda: {"sess-alive"})
        calls = []

        def _tracking_is_terminal(tid):
            calls.append(tid)
            return False

        monkeypatch.setattr(mod, "_is_ticket_terminal", _tracking_is_terminal)

        rc, out, err = _run(tmp_path, monkeypatch, prune=True)

        assert rc == 1
        assert calls == []


class TestPruneConcurrency:
    """0.2.1-W3-1380：`--prune` 的讀-改-寫必須與 `record_dispatch` 共用
    同一把鎖，否則兩者交錯時任一方的寫入可能被另一方持有的舊快照覆寫
    （lost update）。修復前 `--prune` 完全在鎖外讀取/計算/寫入，本測試
    人工延長 `--prune` 的判準執行時間製造交錯窗口，斷言交錯期間
    `record_dispatch` 寫入的記錄不會消失。"""

    def test_prune_interleaved_with_record_dispatch_no_lost_update(
        self, tmp_path, monkeypatch
    ):
        import threading
        import time

        from lib.dispatch_tracker import get_active_dispatches, record_dispatch

        monkeypatch.setattr(mod, "get_ticket_state_root", lambda: tmp_path)
        (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)

        record_dispatch(tmp_path, agent_description="gone-agent", ticket_id="A")

        entered_predicate = threading.Event()
        release_predicate = threading.Event()

        def _blocking_is_terminal(ticket_id):
            # 模擬 --prune 判準執行期間，另一 session 同時呼叫
            # record_dispatch——鎖若正確涵蓋整個讀-改-寫週期，
            # record_dispatch 應被阻塞至此函式返回、寫入完成為止。
            entered_predicate.set()
            release_predicate.wait(timeout=5)
            return True

        monkeypatch.setattr(mod, "_is_ticket_terminal", _blocking_is_terminal)
        monkeypatch.setattr(mod, "_load_registry_session_ids", lambda: None)
        monkeypatch.setattr(mod, "_get_prune_logger", lambda: None)

        prune_thread = threading.Thread(
            target=lambda: _run(tmp_path, monkeypatch, prune=True)
        )
        prune_thread.start()
        assert entered_predicate.wait(timeout=5), "prune 判準未如預期開始執行"

        record_thread = threading.Thread(
            target=lambda: record_dispatch(
                tmp_path, agent_description="new-agent-during-prune", ticket_id="B"
            )
        )
        record_thread.start()
        # 給 record_dispatch 機會嘗試取得鎖（此時應被 prune 持有的鎖阻塞，
        # 直到 release_predicate 被設定才可能取得）
        time.sleep(0.2)

        release_predicate.set()
        prune_thread.join(timeout=5)
        record_thread.join(timeout=5)

        assert not prune_thread.is_alive(), "prune 執行緒未如預期結束"
        assert not record_thread.is_alive(), "record_dispatch 執行緒未如預期結束"

        remaining = get_active_dispatches(tmp_path)
        descriptions = {e.get("agent_description") for e in remaining}
        assert "new-agent-during-prune" in descriptions, (
            "record_dispatch 於 --prune 執行期間寫入的記錄不應遺失；"
            f"實際: {descriptions}"
        )
