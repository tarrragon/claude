"""topic_backfill 命令模組的單元測試（既有 pending 票的主題分批回填）。

隔離依賴 `.claude/skills/ticket/conftest.py` 的 autouse fixture
`_isolate_project_root`：每個 test 前自動清 `get_project_root()` 快取並
注入獨立 tmp 目錄（含已建立的 `docs/work-logs/`），故本檔測試互不污染，
亦不觸及真實 repo 的 `docs/work-logs/topic-assignments.txt` 或
`docs/work-logs/topics-registry.txt`。
"""

from __future__ import annotations

import argparse

from ticket_system.commands import topic_backfill
from ticket_system.lib import topic_registry
from ticket_system.lib.paths import get_project_root


def _assignments_file():
    return get_project_root() / topic_backfill.TOPIC_ASSIGNMENTS_RELATIVE_PATH


def _write_ticket(version: str, ticket_id: str, status: str = "pending") -> None:
    """在隔離的 tmp 專案根下建立一張最小 ticket 檔案（唯讀掃描用測資）。"""
    tickets_dir = get_project_root() / "docs" / "work-logs" / f"v{version}" / "tickets"
    tickets_dir.mkdir(parents=True, exist_ok=True)
    content = (
        "---\n"
        f"id: {ticket_id}\n"
        f"status: {status}\n"
        "title: 測試票\n"
        "type: IMP\n"
        "---\n\n"
        "# Execution Log\n"
    )
    (tickets_dir / f"{ticket_id}.md").write_text(content, encoding="utf-8")


class TestListPendingTicketIds:
    def test_returns_empty_list_when_no_tickets(self):
        assert topic_backfill.list_pending_ticket_ids() == []

    def test_only_includes_pending_status(self):
        _write_ticket("0.1.0", "0.1.0-W1-001", status="pending")
        _write_ticket("0.1.0", "0.1.0-W1-002", status="completed")
        assert topic_backfill.list_pending_ticket_ids() == ["0.1.0-W1-001"]

    def test_scans_hierarchical_version_dirs(self):
        # 三層版本目錄結構：v{major}/v{major.minor}/v{version}/tickets
        tickets_dir = (
            get_project_root()
            / "docs"
            / "work-logs"
            / "v0"
            / "v0.1"
            / "v0.1.0"
            / "tickets"
        )
        tickets_dir.mkdir(parents=True, exist_ok=True)
        (tickets_dir / "0.1.0-W1-003.md").write_text(
            "---\nid: 0.1.0-W1-003\nstatus: pending\n---\n\nBody\n",
            encoding="utf-8",
        )
        assert topic_backfill.list_pending_ticket_ids() == ["0.1.0-W1-003"]


class TestListUnassignedPendingTickets:
    def test_all_pending_unassigned_when_log_absent(self):
        _write_ticket("0.1.0", "0.1.0-W1-001")
        _write_ticket("0.1.0", "0.1.0-W1-002")
        assert topic_backfill.list_unassigned_pending_tickets() == [
            "0.1.0-W1-001",
            "0.1.0-W1-002",
        ]

    def test_excludes_already_assigned_tickets(self):
        _write_ticket("0.1.0", "0.1.0-W1-001")
        _write_ticket("0.1.0", "0.1.0-W1-002")
        topic_backfill.append_assignment("0.1.0-W1-001", "主題 A")

        assert topic_backfill.list_unassigned_pending_tickets() == [
            "0.1.0-W1-002"
        ]


class TestAppendAssignmentBasic:
    def test_append_creates_log_when_missing(self):
        _write_ticket("0.1.0", "0.1.0-W1-001")
        assert topic_backfill.append_assignment("0.1.0-W1-001", "主題 A") is True
        assert _assignments_file().exists()
        assert topic_backfill.list_assignments() == {"0.1.0-W1-001": "主題 A"}

    def test_append_registers_topic_in_central_registry(self):
        topic_backfill.append_assignment("0.1.0-W1-001", "主題 A")
        assert topic_registry.list_topics() == ["主題 A"]

    def test_append_returns_false_for_duplicate_ticket_id(self):
        topic_backfill.append_assignment("0.1.0-W1-001", "主題 A")
        result = topic_backfill.append_assignment("0.1.0-W1-001", "主題 B")
        assert result is False
        assert topic_backfill.list_assignments() == {"0.1.0-W1-001": "主題 A"}

    def test_append_rejects_blank_ticket_id(self):
        try:
            topic_backfill.append_assignment("   ", "主題 A")
        except ValueError:
            pass
        else:
            raise AssertionError("append_assignment 應對空白 ticket_id 拋出 ValueError")

    def test_append_rejects_blank_topic(self):
        try:
            topic_backfill.append_assignment("0.1.0-W1-001", "   ")
        except ValueError:
            pass
        else:
            raise AssertionError("append_assignment 應對空白 topic 拋出 ValueError")


class TestAppendAssignmentMissingTrailingNewline:
    """回歸測試：外部手動編輯 assignment log 遺留無尾換行時，append 不得
    與既有末行黏合（同 topic_registry.append_topic 已修復的缺陷模式）。
    """

    def test_append_does_not_merge_with_no_trailing_newline(self):
        log_path = _assignments_file()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        # 手動寫入無尾換行的既有內容，模擬外部編輯遺留的狀態。
        log_path.write_text("0.1.0-W1-001\t主題 A", encoding="utf-8")

        result = topic_backfill.append_assignment("0.1.0-W1-002", "主題 B")

        assert result is True
        assignments = topic_backfill.list_assignments()
        assert assignments == {
            "0.1.0-W1-001": "主題 A",
            "0.1.0-W1-002": "主題 B",
        }

    def test_append_to_empty_file_does_not_prepend_newline(self):
        log_path = _assignments_file()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("", encoding="utf-8")

        topic_backfill.append_assignment("0.1.0-W1-001", "主題 A")

        assert log_path.read_text(encoding="utf-8") == "0.1.0-W1-001\t主題 A\n"

    def test_append_with_existing_trailing_newline_stays_independent(self):
        log_path = _assignments_file()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        # 既有內容已正確以換行結尾（append_assignment 正常寫入路徑產生的
        # 常態），追加新筆次不應誤補多餘空行。
        log_path.write_text("0.1.0-W1-001\t主題 A\n", encoding="utf-8")
        original_content = log_path.read_text(encoding="utf-8")

        topic_backfill.append_assignment("0.1.0-W1-002", "主題 B")

        new_content = log_path.read_text(encoding="utf-8")
        assert new_content == original_content + "0.1.0-W1-002\t主題 B\n"
        assert topic_backfill.list_assignments() == {
            "0.1.0-W1-001": "主題 A",
            "0.1.0-W1-002": "主題 B",
        }

    def test_append_preserves_existing_content_as_prefix(self):
        # acceptance 第 3 條：補行仍為純 append，新檔案內容以原檔案內容為
        # 前綴（涵蓋無尾換行需補行的情境，補行後仍是 append 語意的直接
        # 證明，而非僅驗證最終字典內容）。
        log_path = _assignments_file()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("0.1.0-W1-001\t主題 A", encoding="utf-8")
        original_content = log_path.read_text(encoding="utf-8")

        topic_backfill.append_assignment("0.1.0-W1-002", "主題 B")

        new_content = log_path.read_text(encoding="utf-8")
        assert new_content.startswith(original_content), (
            "追加新筆次後，既有內容必須逐字保留於檔案前綴，"
            f"原內容={original_content!r}，新內容={new_content!r}"
        )


class TestAssignBatch:
    """acceptance 第 2 條：可分批指派主題，單批失敗不影響已完成批次的既有寫入。"""

    def test_all_succeed(self):
        result = topic_backfill.assign_batch(
            {"0.1.0-W1-001": "主題 A", "0.1.0-W1-002": "主題 B"}
        )
        assert result["succeeded"] == ["0.1.0-W1-001", "0.1.0-W1-002"]
        assert result["failed"] == []
        assert topic_backfill.list_assignments() == {
            "0.1.0-W1-001": "主題 A",
            "0.1.0-W1-002": "主題 B",
        }

    def test_single_failure_does_not_affect_prior_successful_writes(self):
        result = topic_backfill.assign_batch(
            {
                "0.1.0-W1-001": "主題 A",
                "0.1.0-W1-002": "   ",  # 空白 topic，觸發驗證失敗
                "0.1.0-W1-003": "主題 C",
            }
        )
        assert result["succeeded"] == ["0.1.0-W1-001", "0.1.0-W1-003"]
        assert result["failed"] == ["0.1.0-W1-002"]
        assert topic_backfill.list_assignments() == {
            "0.1.0-W1-001": "主題 A",
            "0.1.0-W1-003": "主題 C",
        }


class TestAssignBatchReassign:
    """0.2.1-W3-804 acceptance 第 2 條：改派須經與一般指派不同的顯式命令
    或旗標。本組測試 `assign_batch(..., reassign=True)`；CLI 層
    `--reassign` 旗標的透傳見 `TestExecuteTopicBackfillAssign`。
    """

    def test_default_reassign_false_rejects_duplicate_like_before(self):
        topic_backfill.assign_batch({"0.1.0-W1-001": "主題 A"})
        result = topic_backfill.assign_batch({"0.1.0-W1-001": "主題 B"})

        # reassign 預設 False：write_fn 為 append_assignment，回傳 False
        # 但仍計入 succeeded（既有 assign_batch 行為：ValueError 才算
        # failed，False 回傳值不觸發例外），檔案內容維持原指派不變。
        assert result["failed"] == []
        assert topic_backfill.list_assignments() == {"0.1.0-W1-001": "主題 A"}

    def test_reassign_true_overwrites_read_semantics(self):
        topic_backfill.assign_batch({"0.1.0-W1-001": "主題 A"})
        result = topic_backfill.assign_batch(
            {"0.1.0-W1-001": "主題 B"}, reassign=True
        )

        assert result["succeeded"] == ["0.1.0-W1-001"]
        assert topic_backfill.list_assignments() == {"0.1.0-W1-001": "主題 B"}

    def test_reassign_true_preserves_original_line_as_prefix(self):
        topic_backfill.assign_batch({"0.1.0-W1-001": "主題 A"})
        original_content = _assignments_file().read_text(encoding="utf-8")

        topic_backfill.assign_batch({"0.1.0-W1-001": "主題 B"}, reassign=True)
        new_content = _assignments_file().read_text(encoding="utf-8")

        assert new_content.startswith(original_content)


class TestInterruptResumeSemantics:
    """acceptance 第 3 條：中斷後再次執行時從未歸屬者續作，不重複處理已歸屬票。"""

    def test_resume_after_partial_batch_only_processes_remaining(self):
        _write_ticket("0.1.0", "0.1.0-W1-001")
        _write_ticket("0.1.0", "0.1.0-W1-002")
        _write_ticket("0.1.0", "0.1.0-W1-003")

        # 模擬第一次執行只完成一批（中斷前）
        topic_backfill.assign_batch({"0.1.0-W1-001": "主題 A"})
        remaining_after_first_run = topic_backfill.list_unassigned_pending_tickets()
        assert remaining_after_first_run == ["0.1.0-W1-002", "0.1.0-W1-003"]

        # 模擬中斷後重新執行：僅處理續作起點回傳的未歸屬票
        second_batch = {tid: "主題 B" for tid in remaining_after_first_run}
        result = topic_backfill.assign_batch(second_batch)
        assert result["succeeded"] == ["0.1.0-W1-002", "0.1.0-W1-003"]

        # 第一批寫入的指派逐字保留，未被第二批覆蓋或重複處理
        assert topic_backfill.list_assignments() == {
            "0.1.0-W1-001": "主題 A",
            "0.1.0-W1-002": "主題 B",
            "0.1.0-W1-003": "主題 B",
        }
        assert topic_backfill.list_unassigned_pending_tickets() == []


class TestFrontmatterUnchanged:
    """acceptance 第 4 條：回填不寫任何 ticket frontmatter 欄位。"""

    def test_ticket_file_byte_identical_after_assignment(self):
        _write_ticket("0.1.0", "0.1.0-W1-001")
        ticket_path = (
            get_project_root()
            / "docs"
            / "work-logs"
            / "v0.1.0"
            / "tickets"
            / "0.1.0-W1-001.md"
        )
        original_content = ticket_path.read_text(encoding="utf-8")

        topic_backfill.append_assignment("0.1.0-W1-001", "主題 A")

        assert ticket_path.read_text(encoding="utf-8") == original_content

    def test_batch_assignment_leaves_all_ticket_files_untouched(self):
        _write_ticket("0.1.0", "0.1.0-W1-001")
        _write_ticket("0.1.0", "0.1.0-W1-002")
        tickets_dir = get_project_root() / "docs" / "work-logs" / "v0.1.0" / "tickets"
        original_contents = {
            path.name: path.read_text(encoding="utf-8")
            for path in tickets_dir.glob("*.md")
        }

        topic_backfill.assign_batch(
            {"0.1.0-W1-001": "主題 A", "0.1.0-W1-002": "主題 B"}
        )

        for name, original in original_contents.items():
            assert (tickets_dir / name).read_text(encoding="utf-8") == original


class TestCliRegistration:
    """CLI 入口註冊（0.2.1-W3-802 acceptance 第 1 條）：命令已在 track.py
    註冊表接線且 --help 可見。track.py 為修復票 where.files 範圍外的
    間接驗證對象，此處僅驗證匯入不炸且 handler dict 含兩個命令，不重新
    測試 track.py 既有的 dispatch 機制本身。
    """

    def test_track_registers_both_backfill_commands(self):
        from ticket_system.commands import track

        handlers = track._create_version_agnostic_handlers()
        assert "topic-backfill-list" in handlers
        assert "topic-backfill-assign" in handlers
        assert handlers["topic-backfill-list"] is topic_backfill.execute_topic_backfill_list
        assert handlers["topic-backfill-assign"] is topic_backfill.execute_topic_backfill_assign

    def test_register_adds_both_subparsers(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="operation")
        topic_backfill.register(subparsers)

        args_list = parser.parse_args(["topic-backfill-list"])
        assert args_list.operation == "topic-backfill-list"

        args_assign = parser.parse_args(["topic-backfill-assign", "--file", "x.txt"])
        assert args_assign.operation == "topic-backfill-assign"
        assert args_assign.file == "x.txt"
        assert args_assign.allow_new_topics is False

        args_assign_allow = parser.parse_args(
            ["topic-backfill-assign", "--file", "x.txt", "--allow-new-topics"]
        )
        assert args_assign_allow.allow_new_topics is True


class TestExecuteTopicBackfillList:
    """acceptance 第 2 條：可經 CLI 列出尚未歸屬主題的 pending 票。"""

    def test_prints_unassigned_ticket_ids(self, capsys):
        _write_ticket("0.1.0", "0.1.0-W1-001")
        _write_ticket("0.1.0", "0.1.0-W1-002")
        topic_backfill.append_assignment("0.1.0-W1-001", "主題 A")

        rc = topic_backfill.execute_topic_backfill_list(argparse.Namespace(format="table"))

        assert rc == 0
        out = capsys.readouterr().out
        assert "0.1.0-W1-002" in out
        assert "0.1.0-W1-001" not in out

    def test_json_format_reports_count(self, capsys):
        _write_ticket("0.1.0", "0.1.0-W1-001")

        rc = topic_backfill.execute_topic_backfill_list(argparse.Namespace(format="json"))

        assert rc == 0
        import json
        payload = json.loads(capsys.readouterr().out)
        assert payload == {"unassigned": ["0.1.0-W1-001"], "count": 1}

    def test_empty_result_message(self, capsys):
        rc = topic_backfill.execute_topic_backfill_list(argparse.Namespace(format="table"))

        assert rc == 0
        assert "無未歸屬" in capsys.readouterr().out


class TestExecuteTopicBackfillAssign:
    """acceptance 第 3 條：可經 CLI 分批指派主題，行為與模組層一致。"""

    def test_assigns_from_file(self, tmp_path, capsys):
        _write_ticket("0.1.0", "0.1.0-W1-001")
        _write_ticket("0.1.0", "0.1.0-W1-002")
        input_file = tmp_path / "assignments.txt"
        input_file.write_text(
            "0.1.0-W1-001\t主題 A\n0.1.0-W1-002\t主題 B\n", encoding="utf-8"
        )

        rc = topic_backfill.execute_topic_backfill_assign(
            argparse.Namespace(file=str(input_file), allow_new_topics=True)
        )

        assert rc == 0
        assert topic_backfill.list_assignments() == {
            "0.1.0-W1-001": "主題 A",
            "0.1.0-W1-002": "主題 B",
        }
        assert "成功: 2 筆" in capsys.readouterr().out

    def test_unknown_topic_name_rejected_by_default(self, tmp_path, capsys):
        """CLI 層預設拒絕中央清單未見的主題名，不透傳給 assign_batch 自動
        註冊（防呆對齊 create.py `--topic` 白名單語意）。模組層
        `append_assignment` 的自動註冊語意本身不變，見
        `TestAppendAssignmentBasic`。
        """
        _write_ticket("0.1.0", "0.1.0-W1-001")
        input_file = tmp_path / "assignments.txt"
        input_file.write_text("0.1.0-W1-001\t全新主題\n", encoding="utf-8")

        rc = topic_backfill.execute_topic_backfill_assign(
            argparse.Namespace(file=str(input_file), allow_new_topics=False)
        )

        assert rc == 1
        assert topic_registry.list_topics() == []
        assert topic_backfill.list_assignments() == {}
        assert "全新主題" in capsys.readouterr().out

    def test_unknown_topic_name_allowed_with_explicit_flag(self, tmp_path):
        """`--allow-new-topics` 顯式旗標開啟時允許新增，透傳
        `assign_batch` 自動註冊，行為與 `create.py --new-topic` 對齊。
        """
        _write_ticket("0.1.0", "0.1.0-W1-001")
        input_file = tmp_path / "assignments.txt"
        input_file.write_text("0.1.0-W1-001\t全新主題\n", encoding="utf-8")

        rc = topic_backfill.execute_topic_backfill_assign(
            argparse.Namespace(file=str(input_file), allow_new_topics=True)
        )

        assert rc == 0
        assert topic_registry.list_topics() == ["全新主題"]

    def test_known_topic_unaffected_by_unknown_topic_in_same_batch(self, tmp_path):
        """同批次中已知主題名的筆次不受未知主題名筆次遭拒的影響（acceptance
        第 4 條：拒絕發生時該筆不寫入，其餘筆次不受影響）。
        """
        _write_ticket("0.1.0", "0.1.0-W1-001")
        _write_ticket("0.1.0", "0.1.0-W1-002")
        topic_backfill.append_assignment("0.1.0-W1-999", "既有主題")

        input_file = tmp_path / "assignments.txt"
        input_file.write_text(
            "0.1.0-W1-001\t既有主題\n0.1.0-W1-002\t形近錯字主題\n", encoding="utf-8"
        )

        rc = topic_backfill.execute_topic_backfill_assign(
            argparse.Namespace(file=str(input_file), allow_new_topics=False)
        )

        assert rc == 1
        assignments = topic_backfill.list_assignments()
        assert assignments["0.1.0-W1-001"] == "既有主題"
        assert "0.1.0-W1-002" not in assignments

    def test_missing_input_file_returns_error(self, tmp_path, capsys):
        rc = topic_backfill.execute_topic_backfill_assign(
            argparse.Namespace(file=str(tmp_path / "absent.txt"))
        )

        assert rc == 1
        assert "不存在" in capsys.readouterr().out

    def test_partial_failure_reports_nonzero_and_lists_failed(self, tmp_path, capsys):
        input_file = tmp_path / "assignments.txt"
        # 第二行為格式錯誤行（缺 tab），會被解析階段略過（非驗證失敗）；
        # 此測試改以合法解析後的空白 topic 觸發模組層驗證失敗。
        input_file.write_text(
            "0.1.0-W1-001\t主題 A\n0.1.0-W1-002\t   \n", encoding="utf-8"
        )

        rc = topic_backfill.execute_topic_backfill_assign(
            argparse.Namespace(file=str(input_file), allow_new_topics=True)
        )

        assert rc == 1
        out = capsys.readouterr().out
        assert "失敗: 1 筆" in out
        assert "0.1.0-W1-002" in out
        # 單筆失敗不影響已成功寫入的筆次（與模組層 assign_batch 語意一致）
        assert topic_backfill.list_assignments() == {"0.1.0-W1-001": "主題 A"}

    def test_malformed_line_without_tab_is_skipped_not_fatal(self, tmp_path, capsys):
        input_file = tmp_path / "assignments.txt"
        input_file.write_text(
            "0.1.0-W1-001\t主題 A\n這行沒有tab分隔符\n", encoding="utf-8"
        )

        rc = topic_backfill.execute_topic_backfill_assign(
            argparse.Namespace(file=str(input_file), allow_new_topics=True)
        )

        assert rc == 0
        assert topic_backfill.list_assignments() == {"0.1.0-W1-001": "主題 A"}

    def test_without_reassign_flag_existing_ticket_id_not_overwritten(
        self, tmp_path, capsys
    ):
        """0.2.1-W3-804 acceptance 第 2 條：未加 `--reassign` 時，行為與
        既有拒絕重複指派一致（改派須是顯式選擇，非預設行為）。
        """
        topic_backfill.append_assignment("0.1.0-W1-001", "主題 A")
        input_file = tmp_path / "assignments.txt"
        input_file.write_text("0.1.0-W1-001\t主題 A\n", encoding="utf-8")

        rc = topic_backfill.execute_topic_backfill_assign(
            argparse.Namespace(
                file=str(input_file), allow_new_topics=True, reassign=False
            )
        )

        assert rc == 0
        assert topic_backfill.list_assignments() == {"0.1.0-W1-001": "主題 A"}

    def test_reassign_flag_overwrites_read_semantics_via_cli(self, tmp_path, capsys):
        """0.2.1-W3-804 acceptance 第 1、2 條：`--reassign` 旗標使 CLI
        改派已指派票的主題，`list_assignments` 回傳新值。
        """
        topic_backfill.append_assignment("0.1.0-W1-001", "主題 A")
        input_file = tmp_path / "assignments.txt"
        input_file.write_text("0.1.0-W1-001\t主題 B\n", encoding="utf-8")

        rc = topic_backfill.execute_topic_backfill_assign(
            argparse.Namespace(
                file=str(input_file), allow_new_topics=True, reassign=True
            )
        )

        assert rc == 0
        assert topic_backfill.list_assignments() == {"0.1.0-W1-001": "主題 B"}
        assert "成功: 1 筆" in capsys.readouterr().out
