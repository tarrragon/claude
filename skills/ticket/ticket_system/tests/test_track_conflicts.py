"""ticket track conflicts 命令測試（multi-PM 協調層 Phase 2）。

驗證重點：
1. where.files 直接交集（檔案級 / 目錄級前綴）判定衝突
2. PurePosixPath 前綴比對非 string startswith（"lib/foo" 不誤命中 "lib/foobar.dart"）
3. impl->test 擴張啟發式：宣告不含測試檔時仍判交集（Dart + Python 兩慣例）
4. Python 分支僅在真實 `tests/` 兄弟目錄存在時衍生候選（不再假設模組同層
   插 `tests/` 子目錄，審查修正）
5. 無交集不判衝突
6. registry 與票面兩源不一致時回傳 stderr 警告內容，且僅採 FRESH session
   宣告（STALE 殘留 entry 排除，審查修正）
7. exit code：0 無衝突 / 1 有衝突
8. --format json 結構化輸出

全數測試以 patch `load_registry` / `_gather_tickets` 隔離，不觸碰真實
`.git/` 或 `docs/work-logs/`。
"""

from __future__ import annotations

import json
from argparse import Namespace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from ticket_system.commands import track_conflicts


NOW = datetime(2026, 8, 18, 12, 0, 0, tzinfo=timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _ticket(tid, status, files):
    return {"id": tid, "status": status, "where": {"files": files}}


def _fresh_registry(session_id: str, tickets: list, files: list) -> dict:
    """建立含單一 FRESH session 的假 registry（heartbeat 5 分鐘前）。"""
    return {
        "sessions": {
            session_id: {
                "project": "/proj",
                "heartbeat_ts": _iso(NOW - timedelta(minutes=5)),
                "tickets": tickets,
                "files": files,
            }
        }
    }


def _stale_registry(session_id: str, tickets: list, files: list) -> dict:
    """建立含單一 STALE session 的假 registry（heartbeat 45 分鐘前，逾 30 分閾值）。"""
    return {
        "sessions": {
            session_id: {
                "project": "/proj",
                "heartbeat_ts": _iso(NOW - timedelta(minutes=45)),
                "tickets": tickets,
                "files": files,
            }
        }
    }


class TestFilesIntersect:
    def test_exact_match(self):
        assert track_conflicts._files_intersect("lib/foo.dart", "lib/foo.dart") is True

    def test_directory_prefix_matches(self):
        assert track_conflicts._files_intersect("lib/foo", "lib/foo/bar.dart") is True

    def test_prefix_not_string_startswith(self):
        assert track_conflicts._files_intersect("lib/foo", "lib/foobar.dart") is False

    def test_disjoint_paths_no_match(self):
        assert track_conflicts._files_intersect("lib/a.dart", "lib/b.dart") is False


class TestFindNearestTestsDir:
    def test_finds_package_root_sibling_tests_dir(self, tmp_path):
        # 模擬 ticket_system/{commands,tests}/ 結構：tests/ 是 commands/ 的
        # 兄弟層（package 根），非 commands/ 自身子目錄
        (tmp_path / "ticket_system" / "commands").mkdir(parents=True)
        (tmp_path / "ticket_system" / "tests").mkdir(parents=True)

        result = track_conflicts._find_nearest_tests_dir(
            "ticket_system/commands/track_conflicts.py", tmp_path
        )
        assert str(result) == "ticket_system/tests"

    def test_finds_immediate_sibling_tests_dir(self, tmp_path):
        # 模擬 hooks/{*.py,tests}/ 結構：tests/ 直接是檔案自身目錄的兄弟層
        (tmp_path / "hooks").mkdir(parents=True)
        (tmp_path / "hooks" / "tests").mkdir(parents=True)

        result = track_conflicts._find_nearest_tests_dir("hooks/some_hook.py", tmp_path)
        assert str(result) == "hooks/tests"

    def test_no_tests_dir_anywhere_returns_none(self, tmp_path):
        (tmp_path / "pkg" / "commands").mkdir(parents=True)
        result = track_conflicts._find_nearest_tests_dir(
            "pkg/commands/foo.py", tmp_path
        )
        assert result is None


class TestDeriveTestCandidates:
    def test_dart_lib_derives_test_dart(self):
        candidates = track_conflicts._derive_test_candidates("lib/domain/foo.dart")
        assert "test/domain/foo_test.dart" in candidates

    def test_python_module_derives_real_package_root_tests_dir(self, tmp_path):
        """審查修正：tests/ 是套件根兄弟層，非模組同層子目錄。"""
        (tmp_path / "ticket_system" / "commands").mkdir(parents=True)
        (tmp_path / "ticket_system" / "tests").mkdir(parents=True)

        candidates = track_conflicts._derive_test_candidates(
            "ticket_system/commands/track_conflicts.py", tmp_path
        )
        assert "ticket_system/tests/test_track_conflicts.py" in candidates
        # 舊版錯誤路徑（模組同層插 tests/ 子目錄）不應出現
        assert "ticket_system/commands/tests/test_track_conflicts.py" not in candidates

    def test_python_module_without_project_root_no_candidate(self):
        """project_root 為 None 時無法驗證真實目錄結構，不猜測候選。"""
        candidates = track_conflicts._derive_test_candidates(
            "ticket_system/commands/track_conflicts.py"
        )
        assert candidates == []

    def test_python_module_no_real_tests_dir_no_candidate(self, tmp_path):
        (tmp_path / "pkg" / "commands").mkdir(parents=True)
        candidates = track_conflicts._derive_test_candidates(
            "pkg/commands/foo.py", tmp_path
        )
        assert candidates == []

    def test_existing_test_file_no_derivation(self, tmp_path):
        candidates = track_conflicts._derive_test_candidates(
            "ticket_system/tests/test_track_conflicts.py", tmp_path
        )
        assert candidates == []

    def test_conftest_no_derivation(self, tmp_path):
        assert track_conflicts._derive_test_candidates(
            "ticket_system/tests/conftest.py", tmp_path
        ) == []

    def test_unrecognized_extension_no_derivation(self):
        assert track_conflicts._derive_test_candidates("README.md") == []


class TestFindConflicts:
    def test_direct_file_conflict_detected(self):
        tickets = [
            _ticket("A", "pending", ["lib/foo.dart"]),
            _ticket("B", "pending", ["lib/foo.dart"]),
        ]
        conflicts = track_conflicts.find_conflicts(tickets)
        assert len(conflicts) == 1
        assert conflicts[0]["ticket_a"] == "A"
        assert conflicts[0]["ticket_b"] == "B"
        assert conflicts[0]["heuristic_only"] is False

    def test_no_conflict_when_disjoint(self):
        tickets = [
            _ticket("A", "pending", ["lib/foo.dart"]),
            _ticket("B", "pending", ["lib/bar.dart"]),
        ]
        assert track_conflicts.find_conflicts(tickets) == []

    def test_heuristic_expansion_detects_hidden_conflict(self):
        # A 宣告實作檔，B 宣告該實作檔的「伴生測試檔」（A 未宣告）——
        # 純宣告值交集判定會漏掉，擴張啟發式應偵測到
        tickets = [
            _ticket("A", "pending", ["lib/domain/foo.dart"]),
            _ticket("B", "pending", ["test/domain/foo_test.dart"]),
        ]
        conflicts = track_conflicts.find_conflicts(tickets)
        assert len(conflicts) == 1
        assert conflicts[0]["heuristic_only"] is True

    def test_directory_level_declaration_conflicts_with_file_level(self):
        tickets = [
            _ticket("A", "in_progress", ["lib/domain"]),
            _ticket("B", "pending", ["lib/domain/foo.dart"]),
        ]
        conflicts = track_conflicts.find_conflicts(tickets)
        assert len(conflicts) == 1

    def test_completed_tickets_excluded(self):
        tickets = [
            _ticket("A", "completed", ["lib/foo.dart"]),
            _ticket("B", "pending", ["lib/foo.dart"]),
        ]
        assert track_conflicts.find_conflicts(tickets) == []

    def test_empty_where_files_ignored(self):
        tickets = [
            _ticket("A", "pending", []),
            _ticket("B", "pending", ["lib/foo.dart"]),
        ]
        assert track_conflicts.find_conflicts(tickets) == []


class TestCrossCheckRegistry:
    def test_mismatch_produces_warning(self):
        tickets = [_ticket("A", "in_progress", ["lib/foo.dart"])]
        registry = _fresh_registry("s1", ["A"], ["lib/other.dart"])
        warnings = track_conflicts.cross_check_registry(
            tickets, registry, project_root="/proj", now=NOW
        )
        assert len(warnings) == 1
        assert "A" in warnings[0]

    def test_warning_includes_consequence_and_next_step(self):
        """審查修正：stderr 警告需含後果與下一步指引，非純事實陳述。"""
        tickets = [_ticket("A", "in_progress", ["lib/foo.dart"])]
        registry = _fresh_registry("s1", ["A"], ["lib/other.dart"])
        warnings = track_conflicts.cross_check_registry(
            tickets, registry, project_root="/proj", now=NOW
        )
        assert "衝突判定僅採 where.files" in warnings[0]
        assert "校正票面宣告或重跑 claim" in warnings[0]

    def test_matching_files_no_warning(self):
        tickets = [_ticket("A", "in_progress", ["lib/foo.dart"])]
        registry = _fresh_registry("s1", ["A"], ["lib/foo.dart"])
        assert track_conflicts.cross_check_registry(
            tickets, registry, project_root="/proj", now=NOW
        ) == []

    def test_no_registry_entry_no_warning(self):
        tickets = [_ticket("A", "in_progress", ["lib/foo.dart"])]
        registry = {"sessions": {}}
        assert track_conflicts.cross_check_registry(
            tickets, registry, project_root="/proj", now=NOW
        ) == []

    def test_pending_ticket_not_checked(self):
        tickets = [_ticket("A", "pending", ["lib/foo.dart"])]
        registry = _fresh_registry("s1", ["A"], ["lib/other.dart"])
        assert track_conflicts.cross_check_registry(
            tickets, registry, project_root="/proj", now=NOW
        ) == []

    def test_stale_session_excluded_from_cross_check(self):
        """審查修正：STALE session 的宣告不應觸發誤報。"""
        tickets = [_ticket("A", "in_progress", ["lib/foo.dart"])]
        registry = _stale_registry("s1", ["A"], ["lib/other.dart"])
        assert track_conflicts.cross_check_registry(
            tickets, registry, project_root="/proj", now=NOW
        ) == []


class TestExecuteConflicts:
    def test_exit_code_0_when_no_conflicts(self, capsys):
        args = Namespace(version="9.9.9", all=False, format="table")
        with patch.object(track_conflicts, "_gather_tickets", return_value=[]), \
             patch.object(track_conflicts, "get_project_root", return_value=Path("/proj")), \
             patch.object(track_conflicts, "load_registry", return_value={"sessions": {}}):
            rc = track_conflicts.execute_conflicts(args)
        assert rc == 0
        assert "無衝突" in capsys.readouterr().out

    def test_exit_code_1_when_conflicts_found(self, capsys):
        tickets = [
            _ticket("A", "pending", ["lib/foo.dart"]),
            _ticket("B", "pending", ["lib/foo.dart"]),
        ]
        args = Namespace(version="9.9.9", all=False, format="table")
        with patch.object(track_conflicts, "_gather_tickets", return_value=tickets), \
             patch.object(track_conflicts, "get_project_root", return_value=Path("/proj")), \
             patch.object(track_conflicts, "load_registry", return_value={"sessions": {}}):
            rc = track_conflicts.execute_conflicts(args)
        assert rc == 1
        out = capsys.readouterr().out
        assert "A" in out and "B" in out

    def test_registry_warning_does_not_flip_exit_code(self, capsys):
        tickets = [_ticket("A", "in_progress", ["lib/foo.dart"])]
        registry = _fresh_registry("s1", ["A"], ["lib/other.dart"])
        args = Namespace(version="9.9.9", all=False, format="table", _now=NOW)
        with patch.object(track_conflicts, "_gather_tickets", return_value=tickets), \
             patch.object(track_conflicts, "get_project_root", return_value=Path("/proj")), \
             patch.object(track_conflicts, "load_registry", return_value=registry):
            rc = track_conflicts.execute_conflicts(args)
        assert rc == 0
        err = capsys.readouterr().err
        assert "宣告不一致" in err

    def test_stale_registry_entry_produces_no_warning(self, capsys):
        """審查修正端到端驗證：STALE session 的宣告不誤觸發 stderr 警告。"""
        tickets = [_ticket("A", "in_progress", ["lib/foo.dart"])]
        registry = _stale_registry("s1", ["A"], ["lib/other.dart"])
        args = Namespace(version="9.9.9", all=False, format="table", _now=NOW)
        with patch.object(track_conflicts, "_gather_tickets", return_value=tickets), \
             patch.object(track_conflicts, "get_project_root", return_value=Path("/proj")), \
             patch.object(track_conflicts, "load_registry", return_value=registry):
            rc = track_conflicts.execute_conflicts(args)
        assert rc == 0
        assert capsys.readouterr().err == ""

    def test_json_output_structure(self, capsys):
        tickets = [
            _ticket("A", "pending", ["lib/foo.dart"]),
            _ticket("B", "pending", ["lib/foo.dart"]),
        ]
        args = Namespace(version="9.9.9", all=False, format="json")
        with patch.object(track_conflicts, "_gather_tickets", return_value=tickets), \
             patch.object(track_conflicts, "get_project_root", return_value=Path("/proj")), \
             patch.object(track_conflicts, "load_registry", return_value={"sessions": {}}):
            rc = track_conflicts.execute_conflicts(args)
        assert rc == 1
        payload = json.loads(capsys.readouterr().out)
        assert "conflicts" in payload
        assert len(payload["conflicts"]) == 1
        assert payload["conflicts"][0]["ticket_a"] == "A"
