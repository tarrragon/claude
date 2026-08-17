"""ticket track activity 命令測試（multi-PM 協調層 Phase 2，L1 新鮮度）。

驗證重點：
1. 三源分別命中時各自正確解析（md mtime / git commit / dirty file）
2. 三源皆缺 -> no-signal（非報錯）
3. 取三源中最新者作為 last_activity，並標記對應 source
4. --format json 結構化輸出
5. 髒檔路徑比對用 PurePosixPath 前綴而非 string startswith（"lib/foo" 不誤命中
   "lib/foobar.dart"）
6. attribute_dirty_files（供 onboard 複用的獨立函式）僅回傳有命中的 ticket

全數測試以 patch `run_git_command` 模擬 git 輸出，搭配 tmp_path 假 ticket md
與假 dirty file，不觸碰真實 `.git/`。
"""

from __future__ import annotations

import json
from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from ticket_system.commands import track_activity


def _ticket(tid: str, path: Path, where_files=None, agent="thyme-python-developer"):
    return {
        "id": tid,
        "status": "in_progress",
        "_path": str(path),
        "where": {"files": where_files or []},
        "who": {"current": agent},
    }


class TestThreeSources:
    def test_md_mtime_source_used_when_alone(self, tmp_path):
        md_path = tmp_path / "ticket.md"
        md_path.write_text("dummy", encoding="utf-8")
        ticket = _ticket("0.0.0-W0-001", md_path)

        with patch.object(track_activity, "run_git_command", return_value=(False, "")):
            result = track_activity.compute_activity(
                ticket, dirty_paths=[], project_root=tmp_path
            )

        assert result["source"] == track_activity.SOURCE_MD_MTIME
        assert result["last_activity"] is not None

    def test_git_commit_source_used_when_alone(self, tmp_path):
        ticket = {
            "id": "0.0.0-W0-002",
            "status": "in_progress",
            "_path": str(tmp_path / "missing.md"),
            "where": {"files": []},
            "who": {"current": "x"},
        }
        commit_time = "2026-08-18T10:00:00+00:00"

        def _fake_run(args, cwd=None):
            if args[0] == "log":
                return True, f"{commit_time}\x00feat(0.0.0-W0-002): do thing"
            return True, ""

        with patch.object(track_activity, "run_git_command", side_effect=_fake_run):
            result = track_activity.compute_activity(
                ticket, dirty_paths=[], project_root=tmp_path
            )

        assert result["source"] == track_activity.SOURCE_GIT_COMMIT
        assert result["last_activity"] == commit_time

    def test_dirty_file_source_used_when_alone(self, tmp_path):
        (tmp_path / "lib").mkdir()
        dirty_file = tmp_path / "lib" / "foo.dart"
        dirty_file.write_text("x", encoding="utf-8")

        ticket = {
            "id": "0.0.0-W0-003",
            "status": "in_progress",
            "_path": str(tmp_path / "missing.md"),
            "where": {"files": ["lib/foo.dart"]},
            "who": {"current": "x"},
        }

        with patch.object(track_activity, "run_git_command", return_value=(False, "")):
            result = track_activity.compute_activity(
                ticket, dirty_paths=["lib/foo.dart"], project_root=tmp_path
            )

        assert result["source"] == track_activity.SOURCE_DIRTY_FILE

    def test_all_sources_missing_no_signal(self, tmp_path):
        ticket = {
            "id": "0.0.0-W0-004",
            "status": "in_progress",
            "_path": str(tmp_path / "missing.md"),
            "where": {"files": []},
            "who": {"current": "x"},
        }
        with patch.object(track_activity, "run_git_command", return_value=(False, "")):
            result = track_activity.compute_activity(
                ticket, dirty_paths=[], project_root=tmp_path
            )
        assert result["source"] == track_activity.NO_SIGNAL
        assert result["last_activity"] is None

    def test_latest_of_three_sources_wins(self, tmp_path):
        md_path = tmp_path / "ticket.md"
        md_path.write_text("dummy", encoding="utf-8")
        # 設定 md mtime 為明確過去時間
        import os
        old_ts = datetime(2020, 1, 1, tzinfo=timezone.utc).timestamp()
        os.utime(md_path, (old_ts, old_ts))

        ticket = _ticket("0.0.0-W0-005", md_path)
        commit_time = "2026-08-18T10:00:00+00:00"  # 明顯比 md mtime 新

        def _fake_run(args, cwd=None):
            if args[0] == "log":
                return True, f"{commit_time}\x00feat(0.0.0-W0-005): do thing"
            return True, ""

        with patch.object(track_activity, "run_git_command", side_effect=_fake_run):
            result = track_activity.compute_activity(
                ticket, dirty_paths=[], project_root=tmp_path
            )

        assert result["source"] == track_activity.SOURCE_GIT_COMMIT


class TestPathMatching:
    def test_prefix_not_string_startswith(self):
        # "lib/foo" 是宣告目錄，"lib/foobar.dart" 不應被視為其子路徑
        assert track_activity._path_matches("lib/foobar.dart", "lib/foo") is False

    def test_directory_prefix_matches(self):
        assert track_activity._path_matches("lib/foo/bar.dart", "lib/foo") is True

    def test_exact_match(self):
        assert track_activity._path_matches("lib/foo.dart", "lib/foo.dart") is True


class TestCommitReferencesTicket:
    """父子票邊界判定：父票 ID 恰為子票 ID 字首子字串時不誤判為獨立引用。"""

    def test_exact_reference_is_valid(self):
        assert track_activity._commit_references_ticket(
            "feat(0.0.0-W0-100): do thing", "0.0.0-W0-100"
        ) is True

    def test_child_ticket_reference_is_not_valid(self):
        # subject 只提及子票（父票 ID 是子票 ID 的字首），不算父票的獨立引用
        assert track_activity._commit_references_ticket(
            "feat(0.0.0-W0-100.3): do thing", "0.0.0-W0-100"
        ) is False

    def test_mixed_subject_finds_standalone_occurrence_after_child(self):
        # subject 同時提到子票與父票獨立引用時，仍應判為 True（掃描全部出現位置）
        subject = "chore(0.0.0-W0-100.3): 依 0.0.0-W0-100 收尾"
        assert track_activity._commit_references_ticket(subject, "0.0.0-W0-100") is True

    def test_no_occurrence_at_all(self):
        assert track_activity._commit_references_ticket(
            "feat(0.0.0-W0-999): unrelated", "0.0.0-W0-100"
        ) is False


class TestGitCommitSourceBoundary:
    def test_uses_fixed_strings_flag(self, tmp_path):
        captured_args = {}

        def _fake_run(args, cwd=None):
            captured_args["args"] = args
            return True, ""

        with patch.object(track_activity, "run_git_command", side_effect=_fake_run):
            track_activity._git_commit_source("0.0.0-W0-100", cwd=str(tmp_path))

        assert "--fixed-strings" in captured_args["args"]

    def test_child_only_candidate_yields_no_signal(self, tmp_path):
        """父票只被子票的 commit 命中時，該源應回傳 None（非報錯）。"""
        ticket_id = "0.0.0-W0-100"

        def _fake_run(args, cwd=None):
            if args[0] == "log":
                line = "2026-08-18T10:00:00+00:00\x00feat(0.0.0-W0-100.3): 收尾"
                return True, line
            return True, ""

        with patch.object(track_activity, "run_git_command", side_effect=_fake_run):
            result = track_activity._git_commit_source(ticket_id, cwd=str(tmp_path))

        assert result is None

    def test_skips_child_candidate_finds_parent_own_commit(self, tmp_path):
        """最新一筆是子票引用，較舊一筆是父票自身 commit，應取到後者。"""
        ticket_id = "0.0.0-W0-100"
        own_commit_time = "2026-08-18T08:00:00+00:00"

        def _fake_run(args, cwd=None):
            if args[0] == "log":
                lines = "\n".join([
                    "2026-08-18T10:00:00+00:00\x00feat(0.0.0-W0-100.3): 收尾",
                    f"{own_commit_time}\x00feat(0.0.0-W0-100): claim",
                ])
                return True, lines
            return True, ""

        with patch.object(track_activity, "run_git_command", side_effect=_fake_run):
            result = track_activity._git_commit_source(ticket_id, cwd=str(tmp_path))

        assert result is not None
        ts, source = result
        assert ts.isoformat() == own_commit_time
        assert source == track_activity.SOURCE_GIT_COMMIT


class TestAttributeDirtyFiles:
    def test_only_tickets_with_matches_returned(self):
        tickets = [
            {"id": "A", "where": {"files": ["lib/foo.dart"]}},
            {"id": "B", "where": {"files": ["lib/bar.dart"]}},
        ]
        dirty_paths = ["lib/foo.dart"]
        result = track_activity.attribute_dirty_files(tickets, dirty_paths, Path("/tmp"))
        assert len(result) == 1
        assert result[0]["id"] == "A"
        assert result[0]["files"] == ["lib/foo.dart"]

    def test_no_matches_returns_empty(self):
        tickets = [{"id": "A", "where": {"files": ["lib/foo.dart"]}}]
        result = track_activity.attribute_dirty_files(tickets, ["other/file.py"], Path("/tmp"))
        assert result == []


class TestExecuteActivity:
    def test_json_output_structure(self, tmp_path, capsys):
        md_path = tmp_path / "0.0.0-W0-999.md"
        md_path.write_text("dummy", encoding="utf-8")
        ticket = _ticket("0.0.0-W0-999", md_path)

        args = Namespace(version="9.9.9", all=False, format="json")
        with patch.object(track_activity, "_gather_in_progress_tickets", return_value=[ticket]), \
             patch.object(track_activity, "get_project_root", return_value=tmp_path), \
             patch.object(track_activity, "list_dirty_files", return_value=[]), \
             patch.object(track_activity, "run_git_command", return_value=(False, "")):
            rc = track_activity.execute_activity(args)

        assert rc == 0
        out = capsys.readouterr().out
        payload = json.loads(out)
        assert "activity" in payload
        assert payload["activity"][0]["id"] == "0.0.0-W0-999"
        assert payload["activity"][0]["source"] == track_activity.SOURCE_MD_MTIME

    def test_no_in_progress_tickets_table(self, capsys):
        args = Namespace(version="9.9.9", all=False, format="table")
        with patch.object(track_activity, "_gather_in_progress_tickets", return_value=[]), \
             patch.object(track_activity, "get_project_root", return_value=Path("/tmp")), \
             patch.object(track_activity, "list_dirty_files", return_value=[]):
            rc = track_activity.execute_activity(args)
        assert rc == 0
        out = capsys.readouterr().out
        assert "無 in_progress ticket" in out
