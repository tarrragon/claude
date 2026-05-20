"""Tests for stop-worklog-handoff-sync-check-hook.py (W17-083.2 S3).

對應 W17-083 Phase 2 sage §S3 11 測試案例（S3-T01 ~ S3-T11）：
- 四主情境矩陣（雙軌一致 / worklog 有 pending 無 / pending 有 worklog 無 / 雙軌皆無）
- 邊界（worklog 不存在 / mtime 早於 session / 短 ID 補全 / completed 排除 / 孤立 + completed）
- 中斷（event JSON 缺欄位）
- 整合（輸出格式驗證）

策略：
- 用 importlib 動態載入 hook 模組（檔名含 hyphen 無法 import）
- 用 tmp_path 建構假 project_root（含 docs/todolist.yaml + worklog + ticket md + handoff/pending）
- 直接呼叫 detect_sync_drift（避開 stdin 處理 → 簡化測試）
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest


HOOK_PATH = Path(__file__).parent.parent.parent / "skills" / "ticket" / "hooks" / "stop-worklog-handoff-sync-check-hook.py"


def _load_hook_module():
    spec = importlib.util.spec_from_file_location(
        "stop_worklog_handoff_sync_check_hook", HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def hook_mod(monkeypatch):
    """載入 hook 模組並停用 W17-176 in_progress 豁免（測試專注 sync drift 邏輯本身）。

    W17-176 引入兩道豁免：
    1. _is_blocked_this_session：本 session 已執行過 → 跳過（用 tmp_path 隔離 flag）
    2. _has_in_progress_ticket：偵測到 in_progress ticket → 跳過

    本套件測試 detect_sync_drift 的 worklog↔pending 比對邏輯；in_progress 豁免
    應由獨立測試套件覆蓋。此 fixture 將兩道豁免覆寫為 False，讓主邏輯路徑可測。
    """
    module = _load_hook_module()
    monkeypatch.setattr(module, "_has_in_progress_ticket", lambda *a, **kw: False)
    monkeypatch.setattr(module, "_is_blocked_this_session", lambda *a, **kw: False)
    return module


# ---------------------------------------------------------------------------
# Fixtures：假 project_root
# ---------------------------------------------------------------------------


def make_project_root(
    tmp_path,
    version="0.18.0",
    worklog_content=None,
    pending_ticket_ids=None,
    ticket_status_map=None,
    create_worklog=True,
):
    pending_ticket_ids = pending_ticket_ids or set()
    ticket_status_map = ticket_status_map or {}

    root = tmp_path / "fake_project"
    root.mkdir(exist_ok=True)

    # docs/todolist.yaml
    todolist = root / "docs" / "todolist.yaml"
    todolist.parent.mkdir(parents=True, exist_ok=True)
    todolist.write_text(
        f"versions:\n  - version: '{version}'\n    status: active\n",
        encoding="utf-8",
    )

    # worklog 路徑：docs/work-logs/v0/v0.18/v0.18.0/v0.18.0-main.md
    bare = version
    parts = bare.split(".")
    major = parts[0]
    minor = f"{parts[0]}.{parts[1]}"
    worklog_path = (
        root / "docs" / "work-logs" / f"v{major}" / f"v{minor}" / f"v{bare}"
        / f"v{bare}-main.md"
    )
    worklog_path.parent.mkdir(parents=True, exist_ok=True)
    if create_worklog:
        worklog_path.write_text(worklog_content or "", encoding="utf-8")

    # pending dir
    pending_dir = root / ".claude" / "handoff" / "pending"
    pending_dir.mkdir(parents=True, exist_ok=True)
    for tid in pending_ticket_ids:
        (pending_dir / f"{tid}.json").write_text("{}", encoding="utf-8")

    # ticket md（用於 status 查詢）
    tickets_dir = worklog_path.parent / "tickets"
    tickets_dir.mkdir(parents=True, exist_ok=True)
    for tid, status in ticket_status_map.items():
        ticket_md = tickets_dir / f"{tid}.md"
        ticket_md.write_text(
            f"---\nid: {tid}\nstatus: {status}\n---\n\n# Test Ticket\n",
            encoding="utf-8",
        )

    return root, worklog_path


# ---------------------------------------------------------------------------
# S3-T01 ~ S3-T11
# ---------------------------------------------------------------------------


class TestStopWorklogHandoffSyncCheck:

    def test_t01_dual_track_consistent_no_output(self, tmp_path, hook_mod):
        """S3-T01 情境1：雙軌一致 → 不輸出"""
        root, worklog = make_project_root(
            tmp_path,
            worklog_content="## Handoff Context\n\nW17-079 待處理\n",
            pending_ticket_ids={"0.18.0-W17-079"},
            ticket_status_map={"0.18.0-W17-079": "in_progress"},
        )

        result = hook_mod.detect_sync_drift(root, 0.0, MagicMock())
        assert result is None

    def test_t02_worklog_has_pending_missing(self, tmp_path, hook_mod):
        """S3-T02 情境2（核心）：worklog 有兩 ticket、pending 空 → 缺失警告"""
        root, worklog = make_project_root(
            tmp_path,
            worklog_content=(
                "## Handoff Context\n\n"
                "W17-079 與 W17-080 待下 session 處理\n"
            ),
            pending_ticket_ids=set(),
            ticket_status_map={
                "0.18.0-W17-079": "in_progress",
                "0.18.0-W17-080": "pending",
            },
        )

        result = hook_mod.detect_sync_drift(root, 0.0, MagicMock())
        assert result is not None
        assert "[Worklog-CLI Handoff Sync Check]" in result
        assert "0.18.0-W17-079" in result
        assert "0.18.0-W17-080" in result
        assert "ticket handoff 0.18.0-W17-079" in result

    def test_t03_pending_has_worklog_no_orphan(self, tmp_path, hook_mod):
        """S3-T03 情境3：worklog 無關鍵字、pending 有孤立 → 列為孤立"""
        root, worklog = make_project_root(
            tmp_path,
            worklog_content="## 一般工作日誌\n\n今天修了 bug\n",
            pending_ticket_ids={"0.17.0-W5-001"},
            ticket_status_map={"0.17.0-W5-001": "in_progress"},
        )

        result = hook_mod.detect_sync_drift(root, 0.0, MagicMock())
        assert result is not None
        assert "孤立" in result
        assert "0.17.0-W5-001" in result

    def test_t04_dual_track_empty_no_output(self, tmp_path, hook_mod):
        """S3-T04 情境4：雙軌皆無 → 不輸出"""
        root, worklog = make_project_root(
            tmp_path,
            worklog_content="## 一般工作日誌\n\n無接手段落\n",
            pending_ticket_ids=set(),
        )

        result = hook_mod.detect_sync_drift(root, 0.0, MagicMock())
        assert result is None

    def test_t05_worklog_not_exist_silent(self, tmp_path, hook_mod):
        """S3-T05 邊界：worklog 不存在 → 靜默退出（None）"""
        root, worklog = make_project_root(
            tmp_path,
            create_worklog=False,
        )

        result = hook_mod.detect_sync_drift(root, 0.0, MagicMock())
        assert result is None

    def test_t06_worklog_mtime_before_session_skip(self, tmp_path, hook_mod):
        """S3-T06 邊界：worklog mtime 早於 session_start → 不輸出"""
        root, worklog = make_project_root(
            tmp_path,
            worklog_content="## Handoff Context\n\nW17-079 待處理\n",
            pending_ticket_ids=set(),
            ticket_status_map={"0.18.0-W17-079": "in_progress"},
        )

        # 設 worklog mtime 為 1000（很早），session_start 為 2000（之後）
        os.utime(worklog, (1000.0, 1000.0))

        result = hook_mod.detect_sync_drift(root, 2000.0, MagicMock())
        assert result is None

    def test_t07_short_id_completion(self, tmp_path, hook_mod):
        """S3-T07 邊界：worklog 含短 ID（無版本前綴）→ 補全為完整 ID"""
        root, worklog = make_project_root(
            tmp_path,
            worklog_content=(
                "## Handoff Context\n\n下 session 優先建議：W17-079\n"
            ),
            pending_ticket_ids=set(),
            ticket_status_map={"0.18.0-W17-079": "in_progress"},
        )

        result = hook_mod.detect_sync_drift(root, 0.0, MagicMock())
        assert result is not None
        assert "0.18.0-W17-079" in result  # 補全

    def test_t08_completed_ticket_excluded(self, tmp_path, hook_mod):
        """S3-T08 邊界：worklog 含 ID 但 ticket 已 completed → 不視為缺失"""
        root, worklog = make_project_root(
            tmp_path,
            worklog_content="## Handoff Context\n\nW17-079 已完成\n",
            pending_ticket_ids=set(),
            ticket_status_map={"0.18.0-W17-079": "completed"},
        )

        result = hook_mod.detect_sync_drift(root, 0.0, MagicMock())
        # worklog ID 全 completed → missing 為空；pending 也空 → orphan 為空
        # 應該不輸出（雙方比對結果皆無）
        assert result is None

    def test_t09_orphan_with_completed(self, tmp_path, hook_mod):
        """S3-T09 邊界：pending 有 completed ticket、worklog 無關鍵字 → 列為孤立"""
        root, worklog = make_project_root(
            tmp_path,
            worklog_content="## 一般\n",
            pending_ticket_ids={"0.17.0-W5-001"},
            ticket_status_map={"0.17.0-W5-001": "completed"},
        )

        result = hook_mod.detect_sync_drift(root, 0.0, MagicMock())
        # 孤立邏輯：pending 有 worklog_active_set 無 → 列為孤立
        # （sage 規格：仍列為孤立提示「考慮 archive」）
        assert result is not None
        assert "0.17.0-W5-001" in result

    def test_t10_event_missing_session_start(self, tmp_path, hook_mod):
        """S3-T10 中斷：session_start=0（缺欄位 fallback）→ 不 raise，正常檢查"""
        root, worklog = make_project_root(
            tmp_path,
            worklog_content="## Handoff Context\n\nW17-079\n",
            pending_ticket_ids=set(),
            ticket_status_map={"0.18.0-W17-079": "in_progress"},
        )

        # session_start=0 → 不過濾 mtime
        result = hook_mod.detect_sync_drift(root, 0.0, MagicMock())
        assert result is not None
        assert "0.18.0-W17-079" in result

    def test_t11_output_format_structure(self, tmp_path, hook_mod):
        """S3-T11 整合：輸出格式包含所有設計骨架元素 + Stop event JSON schema 驗證（W17-158）

        W17-158 修正：Stop event schema 不允許 hookSpecificOutput.additionalContext，
        改用 top-level systemMessage。本測試額外驗證 main() 輸出的 JSON 頂層欄位結構。
        """
        root, worklog = make_project_root(
            tmp_path,
            worklog_content=(
                "## Handoff Context\n\nW17-079 待處理\n"
            ),
            pending_ticket_ids={"0.17.0-W5-001"},  # 孤立
            ticket_status_map={
                "0.18.0-W17-079": "in_progress",
                "0.17.0-W5-001": "in_progress",
            },
        )

        result = hook_mod.detect_sync_drift(root, 0.0, MagicMock())
        assert result is not None
        # 檢查所有關鍵段落
        assert "[Worklog-CLI Handoff Sync Check]" in result  # 標題
        assert "缺失" in result
        assert "0.18.0-W17-079" in result
        assert "孤立" in result
        assert "0.17.0-W5-001" in result
        assert "建議執行" in result
        assert "ticket handoff 0.18.0-W17-079" in result
        assert "session-switching-sop.md" in result  # SOP 引用

    def test_t12_main_output_uses_stop_event_schema(self, tmp_path, hook_mod, monkeypatch, capsys):
        """W17-158：main() JSON 輸出符合 Stop event schema（top-level systemMessage，
        不得有 hookSpecificOutput.additionalContext）。"""
        root, worklog = make_project_root(
            tmp_path,
            worklog_content="## Handoff Context\n\nW17-079 待處理\n",
            pending_ticket_ids=set(),
            ticket_status_map={"0.18.0-W17-079": "in_progress"},
        )

        # mock get_project_root → tmp root；stdin → 空 event
        monkeypatch.setattr(hook_mod, "get_project_root", lambda: root)
        monkeypatch.setattr(sys, "stdin", __import__("io").StringIO("{}"))

        with pytest.raises(SystemExit) as exc_info:
            hook_mod.main()
        assert exc_info.value.code == 0

        captured = capsys.readouterr()
        # main() 應輸出 JSON 至 stdout
        assert captured.out.strip(), "main() 應輸出 JSON"
        payload = json.loads(captured.out)

        # 規格：top-level systemMessage 必存在且含警告內容
        assert "systemMessage" in payload, "Stop event 必須使用 top-level systemMessage"
        assert "[Worklog-CLI Handoff Sync Check]" in payload["systemMessage"]

        # 規格：禁止 hookSpecificOutput.additionalContext（Stop event schema 不允許）
        assert "hookSpecificOutput" not in payload, (
            "Stop event schema 不允許 hookSpecificOutput.additionalContext（W17-158）"
        )

    def test_t13_only_scans_handoff_section_not_full_worklog(self, tmp_path, hook_mod):
        """W17-156：只掃 handoff 段落而非整份 worklog。

        worklog 含大量歷史段落引用 completed ticket，後段才有 handoff section；
        應只把 handoff section 內的 ticket 視為待處理，不應抓到歷史段落 ID。
        """
        worklog_content = (
            "# v0.18.0 工作日誌\n\n"
            "## 2026-05-01 W17-001 完成\n\n"
            "已完成 W17-001 修復某 bug；亦關閉 W17-002 與 W17-003。\n\n"
            "## 2026-05-02 W17-050 完成\n\n"
            "處理 W17-050、W17-051、W17-052 等多個 ticket。\n\n"
            "## 下個 Session 接手 Context\n\n"
            "W17-200 待處理\n"
        )
        # 歷史 ticket 都已 completed；只有 W17-200 是 in_progress
        status_map = {f"0.18.0-W17-{n:03d}": "completed" for n in (1, 2, 3, 50, 51, 52)}
        status_map["0.18.0-W17-200"] = "in_progress"

        root, _ = make_project_root(
            tmp_path,
            worklog_content=worklog_content,
            pending_ticket_ids=set(),
            ticket_status_map=status_map,
        )

        result = hook_mod.detect_sync_drift(root, 0.0, MagicMock())
        assert result is not None
        # 只應顯示 handoff section 內的 W17-200
        assert "0.18.0-W17-200" in result
        # 不應抓到歷史段落的 ID
        for n in (1, 2, 3, 50, 51, 52):
            assert f"0.18.0-W17-{n:03d}" not in result, (
                f"歷史段落 ticket W17-{n:03d} 不應出現在輸出中"
            )

    def test_t14_no_handoff_keyword_no_ticket_scan(self, tmp_path, hook_mod):
        """W17-156：worklog 無 handoff 關鍵字時，不應掃描出任何 ticket ID。

        即便 worklog 充滿 ticket ID 引用，只要無 handoff 關鍵字，handoff section
        為空，worklog_ids 應為 []，不會與 pending（空）產生 missing。
        """
        worklog_content = (
            "# v0.18.0 工作日誌\n\n"
            "今天進度：W17-100、W17-101、W17-102 都完成了。\n"
            "下一步看 W17-103。\n"
        )
        root, _ = make_project_root(
            tmp_path,
            worklog_content=worklog_content,
            pending_ticket_ids=set(),
            ticket_status_map={
                "0.18.0-W17-100": "in_progress",
                "0.18.0-W17-103": "in_progress",
            },
        )

        result = hook_mod.detect_sync_drift(root, 0.0, MagicMock())
        # 無 handoff 關鍵字 + 無 pending → 不輸出
        assert result is None

    def test_t15_realistic_large_worklog_no_false_positive(self, tmp_path, hook_mod):
        """W17-156：真實規模 worklog（700+ 行）只應抓 handoff section 中的 ticket。

        模擬 v0.18.0-main.md 規模：大量歷史段落 + 多個 ticket ID 引用，
        最後才有 handoff section。修復前會抓 48+ false positive，修復後只應抓 1 個。
        """
        # 構造 ~700 行 worklog：30 個歷史段落 × 約 23 行
        sections = []
        sections.append("# v0.18.0 工作日誌\n")
        for i in range(1, 31):
            sections.append(f"## 2026-04-{i:02d} 進度報告\n")
            for j in range(20):
                tid = f"W17-{i*10 + j:03d}"
                sections.append(f"- 處理 {tid}：完成某項任務並驗證測試通過。")
            sections.append("")
        # 加上 handoff section
        sections.append("## 下個 Session 接手 Context\n")
        sections.append("W17-999 待下 session 處理\n")

        worklog_content = "\n".join(sections)
        # 確認規模 ~700 行
        line_count = worklog_content.count("\n")
        assert line_count >= 600, f"fixture line count {line_count} 不足"

        # 大量歷史 ticket 都已 completed；只有 W17-999 in_progress
        status_map = {}
        for i in range(1, 31):
            for j in range(20):
                status_map[f"0.18.0-W17-{i*10 + j:03d}"] = "completed"
        status_map["0.18.0-W17-999"] = "in_progress"

        root, _ = make_project_root(
            tmp_path,
            worklog_content=worklog_content,
            pending_ticket_ids=set(),
            ticket_status_map=status_map,
        )

        result = hook_mod.detect_sync_drift(root, 0.0, MagicMock())
        assert result is not None
        # 只有 W17-999 應出現
        assert "0.18.0-W17-999" in result
        # 計算 missing 段中的 ticket bullet 行數（- 開頭含 0.18.0-）
        missing_lines = [
            ln for ln in result.split("\n")
            if ln.strip().startswith("- 0.18.0-W17-")
        ]
        assert len(missing_lines) == 1, (
            f"修復後應只抓 1 個 ticket，實際抓到 {len(missing_lines)}：{missing_lines}"
        )


# ---------------------------------------------------------------------------
# W17-165 L2-C：from_ticket terminal 過濾
# ---------------------------------------------------------------------------


class TestPendingDirTerminalFilter:
    """W17-165 L2-C：_scan_pending_dir 過濾 from_ticket 為 terminal 狀態的 handoff JSON。

    前置背景：terminal handoff JSON 在 GC 機制最終被清理，但即時掃描仍會誤入
    orphan 比對導致誤報。本套件驗證 from_ticket 為 completed/closed 的 JSON
    不進入 _scan_pending_dir 結果。
    """

    def _write_handoff(self, pending_dir: Path, ticket_id: str, from_ticket: str = None):
        pending_dir.mkdir(parents=True, exist_ok=True)
        record = {"ticket_id": ticket_id, "from_ticket": from_ticket or ticket_id}
        (pending_dir / f"{ticket_id}.json").write_text(
            json.dumps(record), encoding="utf-8"
        )

    def test_completed_from_ticket_excluded(self, tmp_path, hook_mod):
        """from_ticket 為 completed → 不進結果集。"""
        root, _ = make_project_root(
            tmp_path,
            ticket_status_map={"0.18.0-W17-999": "completed"},
        )
        pending_dir = root / ".claude" / "handoff" / "pending"
        self._write_handoff(pending_dir, "0.18.0-W17-999")
        ids = hook_mod._scan_pending_dir(root)
        assert ids == set()

    def test_closed_from_ticket_excluded(self, tmp_path, hook_mod):
        """from_ticket 為 closed → 不進結果集（W17-165 L2-C 主要修復）。"""
        root, _ = make_project_root(
            tmp_path,
            ticket_status_map={"0.18.0-W17-998": "closed"},
        )
        pending_dir = root / ".claude" / "handoff" / "pending"
        self._write_handoff(pending_dir, "0.18.0-W17-998")
        ids = hook_mod._scan_pending_dir(root)
        assert ids == set()

    def test_in_progress_from_ticket_kept(self, tmp_path, hook_mod):
        """from_ticket 為 in_progress → 保留。"""
        root, _ = make_project_root(
            tmp_path,
            ticket_status_map={"0.18.0-W17-997": "in_progress"},
        )
        pending_dir = root / ".claude" / "handoff" / "pending"
        self._write_handoff(pending_dir, "0.18.0-W17-997")
        ids = hook_mod._scan_pending_dir(root)
        assert ids == {"0.18.0-W17-997"}

    def test_unparseable_json_kept_failopen(self, tmp_path, hook_mod):
        """JSON 解析失敗 → fail-open 保留 ID（不誤刪）。"""
        root, _ = make_project_root(tmp_path)
        pending_dir = root / ".claude" / "handoff" / "pending"
        pending_dir.mkdir(parents=True, exist_ok=True)
        (pending_dir / "0.18.0-W17-996.json").write_text("not-json", encoding="utf-8")
        ids = hook_mod._scan_pending_dir(root)
        assert ids == {"0.18.0-W17-996"}


# ---------------------------------------------------------------------------
# W3-026.3: background_tasks 整合（v2.1.145）
# ---------------------------------------------------------------------------


# Part A: _has_background_agents 弱依賴測試
# mirror sibling .claude/hooks/tests/test_handoff_auto_resume_stop_hook.py:480-518


class TestHasBackgroundAgents:
    """W3-026.3 Part A：_has_background_agents 弱依賴策略驗證。

    mirror sibling W3-026.1 has_background_agents 測試模式。只判斷 list
    非空，欄位不存在 / 非 list / 空 list 皆 fallback False。
    """

    def test_has_background_agents_with_non_empty_list_returns_true(self, hook_mod):
        """background_tasks 非空 list → 視為有背景代理人。"""
        input_data = {"background_tasks": [{"id": "agent-1"}]}
        assert hook_mod._has_background_agents(input_data, MagicMock()) is True

    def test_has_background_agents_with_empty_list_returns_false(self, hook_mod):
        """background_tasks 為空 list → 無背景代理人。"""
        input_data = {"background_tasks": []}
        assert hook_mod._has_background_agents(input_data, MagicMock()) is False

    def test_has_background_agents_missing_field_returns_false(self, hook_mod):
        """欄位不存在（舊版 CC）→ 回 False 觸發 fallback。"""
        assert hook_mod._has_background_agents({}, MagicMock()) is False

    def test_has_background_agents_non_list_type_returns_false(self, hook_mod):
        """background_tasks 為非 list 型別（schema 異常）→ 安全回 False。"""
        assert hook_mod._has_background_agents(
            {"background_tasks": "not-a-list"}, MagicMock()
        ) is False
        assert hook_mod._has_background_agents(
            {"background_tasks": {"key": "value"}}, MagicMock()
        ) is False


# Part B: detect_sync_drift 整合測試


class TestDetectSyncDriftWithBackgroundTasks:
    """W3-026.3 Part B：detect_sync_drift 第三道防護整合測試。

    hook_mod fixture 已 monkeypatch _has_in_progress_ticket /
    _is_blocked_this_session 為 False，故主邏輯路徑可達；本套件再驗證
    background_tasks 第三道防護的行為與 fallback。
    """

    def test_detect_sync_drift_skipped_when_background_tasks_active(
        self, tmp_path, hook_mod
    ):
        """有 sync drift + input_data 含非空 background_tasks → 跳過（None）。"""
        root, _ = make_project_root(
            tmp_path,
            worklog_content="## Handoff Context\n\nW17-079 待處理\n",
            pending_ticket_ids=set(),
            ticket_status_map={"0.18.0-W17-079": "pending"},
        )
        input_data = {"background_tasks": [{"id": "bg-1"}]}
        result = hook_mod.detect_sync_drift(
            root, 0.0, MagicMock(), input_data=input_data
        )
        assert result is None, "background_tasks 非空時應跳過 sync drift 檢查"

    def test_detect_sync_drift_proceeds_when_background_tasks_empty(
        self, tmp_path, hook_mod
    ):
        """有 sync drift + input_data 含空 list background_tasks → 不跳過，正常輸出警告。"""
        root, _ = make_project_root(
            tmp_path,
            worklog_content="## Handoff Context\n\nW17-079 待處理\n",
            pending_ticket_ids=set(),
            ticket_status_map={"0.18.0-W17-079": "pending"},
        )
        input_data = {"background_tasks": []}
        result = hook_mod.detect_sync_drift(
            root, 0.0, MagicMock(), input_data=input_data
        )
        assert result is not None, "background_tasks 空 list 不應跳過"
        assert "0.18.0-W17-079" in result

    def test_detect_sync_drift_proceeds_when_input_data_none(
        self, tmp_path, hook_mod
    ):
        """input_data=None（向後相容）→ fallback 為 {}，不跳過。"""
        root, _ = make_project_root(
            tmp_path,
            worklog_content="## Handoff Context\n\nW17-079 待處理\n",
            pending_ticket_ids=set(),
            ticket_status_map={"0.18.0-W17-079": "pending"},
        )
        # 不傳 input_data 參數（用 default None）
        result = hook_mod.detect_sync_drift(root, 0.0, MagicMock())
        assert result is not None, "input_data 預設 None 應 fallback {} 並執行主檢查"
        assert "0.18.0-W17-079" in result


# Part C: main() stdin 4 路徑整合測試
# mirror sibling commit a6d5cc16 W3-037 _FakeStdin pattern


import io as _io_mod


class _FakeStdin(_io_mod.StringIO):
    """StringIO 包裝，提供 isatty() 介面以模擬 sys.stdin（mirror W3-037）。"""

    def __init__(self, content: str = "", tty: bool = False):
        super().__init__(content)
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


class TestMainStdinIntegration:
    """W3-026.3 Part C：main() stdin 4 路徑整合測試。

    mirror W3-037 commit a6d5cc16 sibling pattern：用 _FakeStdin 覆寫
    isatty() 模擬 tty/pipe 模式，monkeypatch detect_sync_drift 攔截
    input_data 驗證傳遞正確性。
    """

    def _patch_main_dependencies(self, monkeypatch, hook_mod, captured: dict):
        """mock detect_sync_drift 攔截 input_data 並回傳 None（避免實際輸出）。"""

        def fake_detect_sync_drift(
            project_root, session_start, logger, input_data=None
        ):
            captured["input_data"] = input_data
            captured["session_start"] = session_start
            return None

        monkeypatch.setattr(hook_mod, "detect_sync_drift", fake_detect_sync_drift)
        monkeypatch.setattr(hook_mod, "get_project_root", lambda: Path("/tmp/_fake"))

    def test_main_with_background_agents_stdin_short_circuits(
        self, monkeypatch, hook_mod, capsys
    ):
        """路徑 4：stdin 含 background_tasks 時完整 payload 傳遞至 detect_sync_drift。"""
        captured: dict = {}
        self._patch_main_dependencies(monkeypatch, hook_mod, captured)
        payload = {
            "background_tasks": [{"id": "bg-1", "status": "running"}],
            "session_start_timestamp": 1234.5,
        }
        monkeypatch.setattr(
            hook_mod.sys, "stdin", _FakeStdin(json.dumps(payload), tty=False)
        )

        with pytest.raises(SystemExit) as exc_info:
            hook_mod.main()
        assert exc_info.value.code == 0
        assert captured["input_data"] == payload
        assert captured["input_data"]["background_tasks"] == [
            {"id": "bg-1", "status": "running"}
        ]

    def test_main_with_tty_falls_back(self, monkeypatch, hook_mod, capsys):
        """路徑 1：tty 互動模式時不讀 stdin，event 維持空 dict。"""
        captured: dict = {}
        self._patch_main_dependencies(monkeypatch, hook_mod, captured)
        monkeypatch.setattr(hook_mod.sys, "stdin", _FakeStdin("", tty=True))

        with pytest.raises(SystemExit) as exc_info:
            hook_mod.main()
        assert exc_info.value.code == 0
        assert captured["input_data"] == {}, "tty 模式不應讀取 stdin"

    def test_main_with_json_decode_error_falls_back(
        self, monkeypatch, hook_mod, capsys
    ):
        """路徑 2：stdin 為非 JSON 字串 → fallback + warning log，input_data={}。"""
        captured: dict = {}
        self._patch_main_dependencies(monkeypatch, hook_mod, captured)
        monkeypatch.setattr(
            hook_mod.sys, "stdin", _FakeStdin("not a valid json {{{", tty=False)
        )

        with pytest.raises(SystemExit) as exc_info:
            hook_mod.main()
        assert exc_info.value.code == 0
        assert captured["input_data"] == {}, "JSONDecodeError 應 fallback 至空 dict"

    def test_main_with_non_dict_stdin_falls_back(
        self, monkeypatch, hook_mod, capsys
    ):
        """路徑 3：stdin 為 JSON list（非 dict）→ fallback + warning log。"""
        captured: dict = {}
        self._patch_main_dependencies(monkeypatch, hook_mod, captured)
        monkeypatch.setattr(
            hook_mod.sys, "stdin", _FakeStdin('[1, 2, 3]', tty=False)
        )

        with pytest.raises(SystemExit) as exc_info:
            hook_mod.main()
        assert exc_info.value.code == 0
        assert captured["input_data"] == {}, "non-dict JSON 應 fallback 至空 dict"
