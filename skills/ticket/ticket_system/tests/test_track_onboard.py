"""ticket track onboard 命令測試（multi-PM 協調層 Phase 2，入場四節彙整）。

驗證重點：
1. 四節皆為複用既有查詢的薄組裝（collect_* 函式對應 sessions/activity/dashboard）
2. 活同事表 = FRESH session；孤兒 entry 表 = STALE session（同源 _build_rows 拆分）
3. registry 缺檔時各節降級顯示不報錯
4. 髒檔歸屬僅比對 in_progress 票、呈現方向為 file -> tickets、採最長匹配前綴
   特異度歸屬（精確檔案 > 深層目錄 > 淺層目錄），泛目錄 tie 收斂為單行摘要
5. 可認領建議複用 track_dashboard.load_top_ready
6. --format json 支援
7. 本檔不重新定義 stale 閾值常數（全交由 track_sessions._build_rows 內部處理，避免三命令各自
   hardcode 一份導致閾值調整時彼此漂移）

全數測試以 patch collect_* / load_registry / _gather_tickets 隔離，不觸碰真實
`.git/` 或 `docs/work-logs/`。
"""

from __future__ import annotations

import json
import sys
from argparse import Namespace
from datetime import datetime, timezone
from unittest.mock import patch

from ticket_system.commands import track_onboard

from conftest import _iso, fresh_ts, stale_ts  # noqa: F401 — 0.2.1-W3-585/733 收斂複本


# NOW 取模組載入當下（而非固定字面）：所有播種與判定入口皆注入 now=NOW，
# elapsed 完全確定（見 conftest.fresh_ts / stale_ts），故改為動態基準不影響
# FRESH/STALE 判定；同時消除「若入口日後移除 now 注入即立刻引爆」的隱患
# （TEST-MON-001，與 test_lease.py 同型防護，0.2.1-W3-733）。
NOW = datetime.now(timezone.utc)


class TestNoStaleThresholdRedefinition:
    def test_module_has_no_stale_threshold_constant(self):
        """onboard 不應重新定義 stale 閾值常數（避免與 track_sessions 的既有判定漂移）。"""
        assert not hasattr(track_onboard, "STALE_THRESHOLD_MINUTES")


class TestCollectSessionSections:
    def test_fresh_and_stale_split_correctly(self):
        registry = {
            "sessions": {
                "s-fresh": {
                    "name": "fresh-session",
                    "project": "/proj",
                    "heartbeat_ts": fresh_ts(NOW),
                    "tickets": [],
                    "files": [],
                },
                "s-stale": {
                    "name": "stale-session",
                    "project": "/proj",
                    "heartbeat_ts": stale_ts(NOW),
                    "tickets": [],
                    "files": [],
                },
            }
        }
        result = track_onboard.collect_session_sections(
            registry, project_root="/proj", now=NOW
        )
        assert len(result["colleagues"]) == 1
        assert result["colleagues"][0]["session_id"] == "s-fresh"
        assert len(result["orphans"]) == 1
        assert result["orphans"][0]["session_id"] == "s-stale"

    def test_empty_registry_degrades_to_empty_sections(self):
        result = track_onboard.collect_session_sections(
            {"sessions": {}}, project_root="/proj", now=NOW
        )
        assert result["colleagues"] == []
        assert result["orphans"] == []


class TestMatchSpecificity:
    def test_exact_file_match_is_max_specificity(self):
        assert track_onboard._match_specificity("lib/foo.dart", "lib/foo.dart") == sys.maxsize

    def test_directory_match_uses_path_parts_count(self):
        assert track_onboard._match_specificity("lib/domain/foo.dart", "lib/domain") == 2
        assert track_onboard._match_specificity("lib/domain/foo.dart", "lib") == 1

    def test_no_match_returns_none(self):
        assert track_onboard._match_specificity("lib/a.dart", "lib/b.dart") is None


class TestAttributeDirtyFilesByFile:
    def test_single_specific_match(self):
        tickets = [{"id": "A", "where": {"files": ["lib/foo.dart"]}}]
        result = track_onboard.attribute_dirty_files_by_file(tickets, ["lib/foo.dart"])
        assert result == [{"file": "lib/foo.dart", "tickets": ["A"], "summary": None}]

    def test_more_specific_ticket_wins_over_generic(self):
        tickets = [
            {"id": "A", "where": {"files": [".claude"]}},
            {"id": "B", "where": {"files": ["lib/domain/foo.dart"]}},
        ]
        result = track_onboard.attribute_dirty_files_by_file(
            tickets, ["lib/domain/foo.dart"]
        )
        assert len(result) == 1
        assert result[0]["tickets"] == ["B"]
        assert result[0]["summary"] is None

    def test_generic_dir_tie_collapses_to_summary(self):
        tickets = [
            {"id": "A", "where": {"files": [".claude"]}},
            {"id": "B", "where": {"files": [".claude"]}},
            {"id": "C", "where": {"files": [".claude"]}},
        ]
        result = track_onboard.attribute_dirty_files_by_file(
            tickets, [".claude/hooks/foo.py"]
        )
        assert len(result) == 1
        assert result[0]["tickets"] is None
        assert result[0]["summary"] == "泛目錄宣告命中 3 票（無鑑別力）"

    def test_generic_dir_single_ticket_not_collapsed(self):
        """單一命中即使是淺層目錄也不需收斂（無 tie 可言）。"""
        tickets = [{"id": "A", "where": {"files": [".claude"]}}]
        result = track_onboard.attribute_dirty_files_by_file(
            tickets, [".claude/hooks/foo.py"]
        )
        assert result[0]["tickets"] == ["A"]
        assert result[0]["summary"] is None

    def test_exact_file_tie_not_collapsed(self):
        """精確檔案層級的 tie 是有意義的真實衝突訊號，不收斂。"""
        tickets = [
            {"id": "A", "where": {"files": ["lib/foo.dart"]}},
            {"id": "B", "where": {"files": ["lib/foo.dart"]}},
        ]
        result = track_onboard.attribute_dirty_files_by_file(tickets, ["lib/foo.dart"])
        assert result[0]["tickets"] == ["A", "B"]
        assert result[0]["summary"] is None

    def test_no_match_file_omitted(self):
        tickets = [{"id": "A", "where": {"files": ["lib/foo.dart"]}}]
        result = track_onboard.attribute_dirty_files_by_file(tickets, ["other/file.py"])
        assert result == []


class TestCollectDirtyAttribution:
    def test_no_dirty_files_returns_empty_without_extra_call(self):
        tickets = [{"id": "A", "status": "in_progress", "where": {"files": ["lib/foo.dart"]}}]
        with patch.object(track_onboard, "list_dirty_files", return_value=[]), \
             patch.object(track_onboard, "attribute_dirty_files_by_file") as mock_attr:
            result = track_onboard.collect_dirty_attribution(tickets, "/proj")
        assert result == []
        mock_attr.assert_not_called()

    def test_only_in_progress_tickets_considered(self):
        """狀態過濾：completed/pending 票不應納入歸屬比對（審查實測噪音來源）。"""
        tickets = [
            {"id": "A", "status": "completed", "where": {"files": ["lib/foo.dart"]}},
            {"id": "B", "status": "pending", "where": {"files": ["lib/foo.dart"]}},
            {"id": "C", "status": "in_progress", "where": {"files": ["lib/foo.dart"]}},
        ]
        with patch.object(track_onboard, "list_dirty_files", return_value=["lib/foo.dart"]):
            result = track_onboard.collect_dirty_attribution(tickets, "/proj")
        assert len(result) == 1
        assert result[0]["tickets"] == ["C"]

    def test_delegates_to_attribute_dirty_files_by_file(self):
        tickets = [{"id": "A", "status": "in_progress", "where": {"files": ["lib/foo.dart"]}}]
        with patch.object(track_onboard, "list_dirty_files", return_value=["lib/foo.dart"]), \
             patch.object(
                 track_onboard, "attribute_dirty_files_by_file",
                 return_value=[{"file": "lib/foo.dart", "tickets": ["A"], "summary": None}],
             ) as mock_attr:
            result = track_onboard.collect_dirty_attribution(tickets, "/proj")
        assert result == [{"file": "lib/foo.dart", "tickets": ["A"], "summary": None}]
        mock_attr.assert_called_once()


class TestCollectOrphanedDirtyFiles:
    """無主髒檔小節：dirty_paths 扣除已被 in_progress 票命中者的補集。"""

    def test_no_dirty_files_returns_empty(self):
        tickets = [{"id": "A", "status": "in_progress", "where": {"files": ["lib/foo.dart"]}}]
        with patch.object(track_onboard, "list_dirty_files", return_value=[]):
            result = track_onboard.collect_orphaned_dirty_files(tickets, "/proj")
        assert result == []

    def test_unmatched_file_listed_without_ticket_id(self):
        """零命中髒檔應被列出，且不得附任何票 ID 推測。"""
        tickets = [{"id": "A", "status": "in_progress", "where": {"files": ["lib/foo.dart"]}}]
        with patch.object(
            track_onboard, "list_dirty_files",
            return_value=["lib/foo.dart", "lib/unrelated.dart"],
        ):
            result = track_onboard.collect_orphaned_dirty_files(tickets, "/proj")
        assert result == ["lib/unrelated.dart"]

    def test_all_files_matched_returns_empty(self):
        tickets = [{"id": "A", "status": "in_progress", "where": {"files": ["lib/foo.dart"]}}]
        with patch.object(track_onboard, "list_dirty_files", return_value=["lib/foo.dart"]):
            result = track_onboard.collect_orphaned_dirty_files(tickets, "/proj")
        assert result == []

    def test_completed_and_pending_tickets_not_consulted(self):
        """已 completed/pending 票的 where.files 不參與比對（避免復發已否決的噪音根因）。"""
        tickets = [
            {"id": "A", "status": "completed", "where": {"files": ["lib/foo.dart"]}},
            {"id": "B", "status": "pending", "where": {"files": ["lib/foo.dart"]}},
        ]
        with patch.object(track_onboard, "list_dirty_files", return_value=["lib/foo.dart"]):
            result = track_onboard.collect_orphaned_dirty_files(tickets, "/proj")
        assert result == ["lib/foo.dart"]


class TestCollectReadySuggestions:
    def test_delegates_to_dashboard_load_top_ready(self):
        tickets = [{"id": "A"}]
        with patch.object(track_onboard, "_get_pending_handoff_info", return_value={}), \
             patch.object(
                 track_onboard, "load_top_ready",
                 return_value=[{"id": "A", "title": "t", "priority": "P1", "readiness": "READY"}],
             ) as mock_ready:
            result = track_onboard.collect_ready_suggestions(tickets, top=5)
        assert len(result) == 1
        mock_ready.assert_called_once_with(tickets, top=5, handoff_info={})


class TestExecuteOnboard:
    def _base_args(self, fmt="table"):
        return Namespace(version="9.9.9", all=False, top=5, format=fmt, _now=NOW)

    def test_table_output_four_sections(self, capsys):
        args = self._base_args()
        with patch.object(track_onboard, "_gather_tickets", return_value=[]), \
             patch.object(track_onboard, "get_project_root", return_value="/proj"), \
             patch.object(track_onboard, "load_registry", return_value={"sessions": {}}), \
             patch.object(track_onboard, "collect_dirty_attribution", return_value=[]), \
             patch.object(track_onboard, "collect_ready_suggestions", return_value=[]):
            rc = track_onboard.execute_onboard(args)
        assert rc == 0
        out = capsys.readouterr().out
        assert "[活同事]" in out
        assert "[孤兒 entry]" in out
        assert "[髒檔歸屬]" in out
        assert "[可認領建議" in out

    def test_registry_load_failure_degrades_all_sections(self, capsys):
        """registry 缺檔/損毀時 load_registry 回傳空結構，各節不報錯。"""
        args = self._base_args()
        with patch.object(track_onboard, "_gather_tickets", return_value=[]), \
             patch.object(track_onboard, "get_project_root", return_value="/proj"), \
             patch.object(track_onboard, "load_registry", return_value={"schema_version": 0, "sessions": {}}), \
             patch.object(track_onboard, "collect_dirty_attribution", return_value=[]), \
             patch.object(track_onboard, "collect_ready_suggestions", return_value=[]):
            rc = track_onboard.execute_onboard(args)
        assert rc == 0
        out = capsys.readouterr().out
        assert "（無活同事）" in out  # 0.2.1-W3-574 W5：與 [活同事] 章節標頭術語對齊
        assert "（無孤兒 entry）" in out
        assert "（無髒檔）" in out
        assert "（無可認領建議）" in out

    def test_json_output_structure(self, capsys):
        args = self._base_args(fmt="json")
        colleague_row = {
            "session_id": "s1", "name": "n1", "heartbeat_age_minutes": 3,
            "status": "FRESH", "tickets_count": 1, "files_count": 2,
        }
        with patch.object(track_onboard, "_gather_tickets", return_value=[]), \
             patch.object(track_onboard, "get_project_root", return_value="/proj"), \
             patch.object(track_onboard, "load_registry", return_value={"sessions": {}}), \
             patch.object(
                 track_onboard, "collect_session_sections",
                 return_value={"colleagues": [colleague_row], "orphans": []},
             ), \
             patch.object(track_onboard, "collect_dirty_attribution", return_value=[]), \
             patch.object(track_onboard, "collect_ready_suggestions", return_value=[]):
            rc = track_onboard.execute_onboard(args)
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["colleagues"] == [colleague_row]
        assert payload["orphans"] == []
        assert payload["dirty_attribution"] == []
        assert payload["ready"] == []

    def test_dirty_attribution_summary_rendered(self, capsys):
        args = self._base_args()
        dirty = [{"file": ".claude/hooks/foo.py", "tickets": None, "summary": "泛目錄宣告命中 3 票（無鑑別力）"}]
        with patch.object(track_onboard, "_gather_tickets", return_value=[]), \
             patch.object(track_onboard, "get_project_root", return_value="/proj"), \
             patch.object(track_onboard, "load_registry", return_value={"sessions": {}}), \
             patch.object(track_onboard, "collect_dirty_attribution", return_value=dirty), \
             patch.object(track_onboard, "collect_ready_suggestions", return_value=[]):
            rc = track_onboard.execute_onboard(args)
        assert rc == 0
        out = capsys.readouterr().out
        assert "泛目錄宣告命中 3 票（無鑑別力）" in out

    def test_orphaned_dirty_files_section_rendered(self, capsys):
        args = self._base_args()
        with patch.object(track_onboard, "_gather_tickets", return_value=[]), \
             patch.object(track_onboard, "get_project_root", return_value="/proj"), \
             patch.object(track_onboard, "load_registry", return_value={"sessions": {}}), \
             patch.object(track_onboard, "collect_dirty_attribution", return_value=[]), \
             patch.object(
                 track_onboard, "collect_orphaned_dirty_files",
                 return_value=["lib/unrelated.dart"],
             ), \
             patch.object(track_onboard, "collect_ready_suggestions", return_value=[]):
            rc = track_onboard.execute_onboard(args)
        assert rc == 0
        out = capsys.readouterr().out
        assert "[無主髒檔]" in out
        assert "lib/unrelated.dart" in out

    def test_orphaned_dirty_files_section_omitted_when_empty(self, capsys):
        """空集合時不輸出無主髒檔小節，避免無事時增加噪音。"""
        args = self._base_args()
        with patch.object(track_onboard, "_gather_tickets", return_value=[]), \
             patch.object(track_onboard, "get_project_root", return_value="/proj"), \
             patch.object(track_onboard, "load_registry", return_value={"sessions": {}}), \
             patch.object(track_onboard, "collect_dirty_attribution", return_value=[]), \
             patch.object(track_onboard, "collect_orphaned_dirty_files", return_value=[]), \
             patch.object(track_onboard, "collect_ready_suggestions", return_value=[]):
            rc = track_onboard.execute_onboard(args)
        assert rc == 0
        out = capsys.readouterr().out
        assert "[無主髒檔]" not in out

    def test_orphaned_dirty_files_json_output(self, capsys):
        args = self._base_args(fmt="json")
        with patch.object(track_onboard, "_gather_tickets", return_value=[]), \
             patch.object(track_onboard, "get_project_root", return_value="/proj"), \
             patch.object(track_onboard, "load_registry", return_value={"sessions": {}}), \
             patch.object(track_onboard, "collect_dirty_attribution", return_value=[]), \
             patch.object(
                 track_onboard, "collect_orphaned_dirty_files",
                 return_value=["lib/unrelated.dart"],
             ), \
             patch.object(track_onboard, "collect_ready_suggestions", return_value=[]):
            rc = track_onboard.execute_onboard(args)
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["orphaned_dirty_files"] == ["lib/unrelated.dart"]

    def test_orphaned_dirty_files_omitted_from_json_when_empty(self, capsys):
        args = self._base_args(fmt="json")
        with patch.object(track_onboard, "_gather_tickets", return_value=[]), \
             patch.object(track_onboard, "get_project_root", return_value="/proj"), \
             patch.object(track_onboard, "load_registry", return_value={"sessions": {}}), \
             patch.object(track_onboard, "collect_dirty_attribution", return_value=[]), \
             patch.object(track_onboard, "collect_orphaned_dirty_files", return_value=[]), \
             patch.object(track_onboard, "collect_ready_suggestions", return_value=[]):
            rc = track_onboard.execute_onboard(args)
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert "orphaned_dirty_files" not in payload

    def test_ready_suggestions_rendered_with_index(self, capsys):
        args = self._base_args()
        ready = [{"id": "A", "title": "do X", "priority": "P1", "readiness": "READY"}]
        with patch.object(track_onboard, "_gather_tickets", return_value=[]), \
             patch.object(track_onboard, "get_project_root", return_value="/proj"), \
             patch.object(track_onboard, "load_registry", return_value={"sessions": {}}), \
             patch.object(track_onboard, "collect_dirty_attribution", return_value=[]), \
             patch.object(track_onboard, "collect_ready_suggestions", return_value=ready):
            rc = track_onboard.execute_onboard(args)
        assert rc == 0
        out = capsys.readouterr().out
        assert "[1]" in out
        assert "A" in out
        assert "do X" in out
