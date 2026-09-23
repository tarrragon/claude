"""可攜問題分流硬閘門測試（0.1.0-W3-648）。

動機：quality-baseline 規則 5「發現即建立」的預設載體是本地 ticket，但
where.files 全數落在 `.claude/` 之下的問題屬「可攜問題」（替換掉專案名稱
與路徑後仍成立、根源在框架通用資產），合法收件方是 canonical framework
issue（tarrragon/claude），非本地 ticket。既有的 where.files 撞檔熱度提示
（僅警告不阻擋）已證實對此類失效無效，故本閘門為硬擋：命中且未附
`--dedup-checked` 查重結論即阻擋建票。

涵蓋：
- A 層：`is_portable_where_files` 單元測試（純路徑判準）
- B 層：`validate_portable_issue_gate` 單元測試（阻擋/放行 + 訊息內容）
- C 層：argparse `--dedup-checked` 註冊測試
- D 層：`execute()` CLI 整合測試（阻擋 / 放行 / 正向對照組）
- E 層：以本 session 已關閉的五張框架票 where.files 作為紅輸入驗證閘門確實命中
"""

import argparse
from unittest.mock import MagicMock

import pytest

from ticket_system.commands.create import execute
from ticket_system.lib.field_validators import (
    is_portable_where_files,
    validate_portable_issue_gate,
)


# ============================================================
# A 層：is_portable_where_files 單元測試
# ============================================================


class TestIsPortableWhereFiles:
    def test_empty_list_not_portable(self):
        assert is_portable_where_files([]) is False

    def test_all_claude_paths_is_portable(self):
        assert is_portable_where_files([".claude/hooks/foo.py"]) is True

    def test_multiple_claude_paths_is_portable(self):
        assert is_portable_where_files(
            [".claude/pm-rules/", ".claude/references/"]
        ) is True

    def test_mixed_paths_not_portable(self):
        # 混合 lib/ 與 .claude/：問題根源不純在框架資產，不視為可攜
        assert is_portable_where_files(
            ["lib/screens/x.dart", ".claude/skills/doc/doc_system/core/uc_registry.py"]
        ) is False

    def test_non_claude_paths_not_portable(self):
        assert is_portable_where_files(["src/test.py", "lib/a.dart"]) is False

    def test_read_marker_stripped_before_check(self):
        # ::read 意圖標記須先剝除才判斷前綴
        assert is_portable_where_files([".claude/hooks/foo.py::read"]) is True

    def test_read_marker_mixed_still_not_portable(self):
        assert is_portable_where_files(
            ["lib/a.dart::read", ".claude/hooks/foo.py"]
        ) is False

    def test_empty_token_in_list_not_portable(self):
        assert is_portable_where_files(["", ".claude/hooks/foo.py"]) is False


# ============================================================
# B 層：validate_portable_issue_gate 單元測試
# ============================================================


class TestValidatePortableIssueGate:
    def test_non_portable_passes_without_output(self, capsys):
        result = validate_portable_issue_gate(["src/test.py"], None)
        assert result is True
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_portable_without_dedup_checked_blocks(self, capsys):
        result = validate_portable_issue_gate([".claude/hooks/foo.py"], None)
        assert result is False
        captured = capsys.readouterr()
        assert "PORTABLE_ISSUE_UNDEDUPED" in captured.out

    def test_portable_with_empty_string_dedup_checked_blocks(self, capsys):
        # 只給旗標不給結論（空字串）仍阻擋
        result = validate_portable_issue_gate([".claude/hooks/foo.py"], "")
        assert result is False

    def test_portable_with_issue_number_passes(self, capsys):
        result = validate_portable_issue_gate([".claude/hooks/foo.py"], "#102")
        assert result is True
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_portable_with_none_conclusion_passes(self, capsys):
        result = validate_portable_issue_gate([".claude/hooks/foo.py"], "none")
        assert result is True

    def test_block_message_contains_dedup_command_template(self, capsys):
        validate_portable_issue_gate([".claude/hooks/foo.py"], None)
        captured = capsys.readouterr()
        assert "section_comment.py dedup --keywords" in captured.out

    def test_block_message_contains_binary_disposition(self, capsys):
        validate_portable_issue_gate([".claude/hooks/foo.py"], None)
        captured = capsys.readouterr()
        assert "observe" in captured.out
        assert "--dedup-checked" in captured.out
        assert "--why" in captured.out

    def test_block_message_clarifies_hit_does_not_mean_no_ticket(self, capsys):
        """命中 issue 不等於不該建票：framework-issue 模型是「ticket 記執行，
        issue 記問題」，執行類票命中 issue 後仍應建票（issue 號即查重結論）。
        本測試動機：本閘門落地當下即擋下自身（where.files 是純 .claude/ 的
        create.py），原始訊息文字誤導成「命中即不建票」，導致一次真實的誤
        關閉票事故——本票被判定為『知識已在 issue 中，不需執行』而關閉，
        但本票的實際性質是程式碼執行，不是可搬遷的知識文字。"""
        validate_portable_issue_gate([".claude/hooks/foo.py"], None)
        captured = capsys.readouterr()
        assert "記執行" in captured.out
        assert "記問題" in captured.out
        assert "不代表" in captured.out
        assert "建票執行" in captured.out


# ============================================================
# C 層：argparse 註冊測試
# ============================================================


class TestDedupCheckedArgRegistered:
    def _build_parser(self):
        from ticket_system.commands.create import register

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="cmd")
        register(subparsers)
        return parser

    def test_dedup_checked_flag_registered(self):
        parser = self._build_parser()
        args = parser.parse_args([
            "create",
            "--action", "test",
            "--target", "sth",
            "--dedup-checked", "#102",
        ])
        assert args.dedup_checked == "#102"

    def test_dedup_checked_default_none(self):
        parser = self._build_parser()
        args = parser.parse_args([
            "create",
            "--action", "test",
            "--target", "sth",
        ])
        assert getattr(args, "dedup_checked", None) is None


# ============================================================
# D 層：execute() CLI 整合測試
# ============================================================


def _make_args(**overrides) -> argparse.Namespace:
    defaults = {
        "version": None,
        "wave": 3,
        "seq": None,
        "type": "IMP",
        "priority": "P2",
        "action": "實作",
        "target": "測試目標",
        "title": "W3-648 閘門測試票",
        "who": "thyme-python-developer",
        "what": "測試用 what",
        "when": "v0.1.0",
        "where_layer": "Infrastructure",
        "where_files": ".claude/hooks/foo.py",
        "why": "測試用 why",
        "how_type": None,
        "how_strategy": "測試策略",
        "parent": None,
        "source_ticket": None,
        "discovered_during": None,
        "blocked_by": None,
        "related_to": None,
        "acceptance": ["驗收條件 A"],
        "decision_tree_entry": "第三層",
        "decision_tree_decision": "建立 IMP",
        "decision_tree_rationale": "0.1.0-W3-648 測試",
        "force": False,
        "quiet": False,
        "verbose": False,
        "json_output": False,
        "dedup_checked": None,
        "topic": None,
        "new_topic": None,
        "no_topic": True,
        "dry_run": False,
        "allow_duplicate": False,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _install_common_mocks(monkeypatch):
    monkeypatch.setattr(
        "ticket_system.commands.create.resolve_version",
        lambda v: "0.1.0",
    )
    monkeypatch.setattr(
        "ticket_system.lib.version.validate_version_registered",
        lambda v: (True, ""),
    )
    monkeypatch.setattr(
        "ticket_system.lib.field_validators.list_tickets",
        lambda v: [],
    )
    stub_ticket = {
        "id": "stub",
        "title": "stub",
        "what": "stub",
        "type": "IMP",
        "who": {"current": "thyme-python-developer"},
        "where": {"files": ["src/test.py"]},
        "how": {"strategy": "測試策略"},
        "acceptance": ["驗收條件 A"],
    }
    build_and_save_mock = MagicMock(return_value=stub_ticket)
    monkeypatch.setattr(
        "ticket_system.commands.create._build_and_save_ticket",
        build_and_save_mock,
    )
    monkeypatch.setattr(
        "ticket_system.commands.create.get_ticket_path",
        lambda v, tid: f"/tmp/tickets/{tid}.md",
    )
    monkeypatch.setattr(
        "ticket_system.commands.create.update_parent_children",
        lambda v, pid, tid: True,
    )
    monkeypatch.setattr(
        "ticket_system.commands.create.update_source_spawned_tickets",
        lambda sid, tid: True,
    )
    monkeypatch.setattr(
        "ticket_system.lib.ticket_id_allocator.get_next_seq",
        lambda v, w: 1,
    )
    monkeypatch.setattr(
        "ticket_system.lib.ticket_id_allocator.get_next_child_seq",
        lambda pid: 1,
    )
    monkeypatch.setattr(
        "ticket_system.commands.create._auto_extract_context_bundle_post_create",
        lambda *a, **kw: True,
    )
    monkeypatch.setattr(
        "ticket_system.lib.git_utils._auto_commit_ticket_md",
        lambda *a, **kw: "not_git_repo",
    )
    return build_and_save_mock


class TestExecuteBlocksPortableWithoutDedup:
    def test_all_claude_where_files_without_dedup_checked_blocks(
        self, monkeypatch, capsys
    ):
        build_mock = _install_common_mocks(monkeypatch)
        args = _make_args(where_files=".claude/hooks/foo.py")

        rc = execute(args)

        assert rc == 1
        captured = capsys.readouterr()
        assert "PORTABLE_ISSUE_UNDEDUPED" in captured.out
        build_mock.assert_not_called()


class TestExecutePassesPortableWithDedupChecked:
    def test_all_claude_where_files_with_issue_number_passes(
        self, monkeypatch, capsys
    ):
        build_mock = _install_common_mocks(monkeypatch)
        args = _make_args(
            where_files=".claude/hooks/foo.py",
            dedup_checked="#102",
        )

        rc = execute(args)

        assert rc == 0
        build_mock.assert_called_once()

    def test_all_claude_where_files_with_none_conclusion_passes(
        self, monkeypatch, capsys
    ):
        build_mock = _install_common_mocks(monkeypatch)
        args = _make_args(
            where_files=".claude/hooks/foo.py",
            dedup_checked="none",
        )

        rc = execute(args)

        assert rc == 0
        build_mock.assert_called_once()

    def test_all_claude_where_files_with_blank_dedup_checked_still_blocks(
        self, monkeypatch, capsys
    ):
        # 旁路防護：空字串不視為結論
        build_mock = _install_common_mocks(monkeypatch)
        args = _make_args(
            where_files=".claude/hooks/foo.py",
            dedup_checked="",
        )

        rc = execute(args)

        assert rc == 1
        build_mock.assert_not_called()


class TestExecuteNormalCreateUnaffected:
    """正向對照組：where.files 含 lib/ 的正常建票不受閘門影響（acceptance 3）。"""

    def test_where_files_with_lib_unaffected(self, monkeypatch, capsys):
        build_mock = _install_common_mocks(monkeypatch)
        args = _make_args(where_files="lib/screens/x.dart,test/unit/x_test.dart")

        rc = execute(args)

        assert rc == 0
        build_mock.assert_called_once()
        captured = capsys.readouterr()
        assert "PORTABLE_ISSUE_UNDEDUPED" not in captured.out


# ============================================================
# E 層：紅輸入 —— 本 session 已關閉的五張框架票 where.files
# ============================================================
#
# 來源：docs/work-logs/v0/v0.1/v0.1.0/tickets/ 下對應票面 frontmatter
# 的 where.files 逐字複製（commit 03ed9d4fc 五張框架票分流至 canonical
# issue）。W3-645 的 where.files 混合 lib/ 與 test/ 與 .claude/（問題症狀
# 顯現於 lib/test，但根因在框架 hook），依路徑層級判準不落在「全數
# .claude/」內，是本設計已知且接受的限制（決策樹 rationale：路徑判準
# 機械可判、零誤判；語意判準候選不在本票範圍）——此為正確行為而非缺陷，
# 一併驗證於本層對照組。


CLOSED_FRAMEWORK_TICKET_WHERE_FILES = {
    "0.1.0-W3-645": [
        "test/unit/components/matrix_grid_test.dart",
        "test/helpers/test_copy.dart",
        "lib/screens/domain_view/domain_view_screen.dart",
        "lib/screens/uc_flow/uc_flow_screen.dart",
        ".claude/skills/doc/doc_system/core/uc_registry.py",
    ],
    "0.1.0-W3-646": [".claude/hooks"],
    "0.1.0-W3-647": [".claude/skills/ticket/ticket_system"],
    "0.1.0-W4-002": [".claude/pm-rules/", ".claude/references/"],
    "0.1.0-W4-003": [".claude/hooks/acceptance-gate-hook.py"],
}


class TestClosedFrameworkTicketsAsRedInput:
    @pytest.mark.parametrize(
        "ticket_id",
        ["0.1.0-W3-646", "0.1.0-W3-647", "0.1.0-W4-002", "0.1.0-W4-003"],
    )
    def test_pure_claude_tickets_trigger_gate(self, ticket_id, monkeypatch, capsys):
        where_files = CLOSED_FRAMEWORK_TICKET_WHERE_FILES[ticket_id]
        build_mock = _install_common_mocks(monkeypatch)
        args = _make_args(where_files=",".join(where_files))

        rc = execute(args)

        assert rc == 1, f"{ticket_id} 的 where.files 全數落在 .claude/ 下，應觸發閘門"
        build_mock.assert_not_called()
        captured = capsys.readouterr()
        assert "PORTABLE_ISSUE_UNDEDUPED" in captured.out

    def test_mixed_path_ticket_w3_645_does_not_trigger_gate(self, monkeypatch, capsys):
        """W3-645 混合 lib/test 與 .claude/，不符「全數 .claude/」判準，
        不觸發本閘門（設計已知限制，非缺陷）。"""
        where_files = CLOSED_FRAMEWORK_TICKET_WHERE_FILES["0.1.0-W3-645"]
        build_mock = _install_common_mocks(monkeypatch)
        args = _make_args(where_files=",".join(where_files))

        rc = execute(args)

        assert rc == 0
        build_mock.assert_called_once()
        captured = capsys.readouterr()
        assert "PORTABLE_ISSUE_UNDEDUPED" not in captured.out

    @pytest.mark.parametrize(
        "ticket_id",
        ["0.1.0-W3-646", "0.1.0-W3-647", "0.1.0-W4-002", "0.1.0-W4-003"],
    )
    def test_pure_claude_tickets_pass_with_dedup_checked(
        self, ticket_id, monkeypatch, capsys
    ):
        """同一組紅輸入附查重結論後應放行，證明閘門非全域封殺 .claude/ 建票。"""
        where_files = CLOSED_FRAMEWORK_TICKET_WHERE_FILES[ticket_id]
        build_mock = _install_common_mocks(monkeypatch)
        args = _make_args(
            where_files=",".join(where_files),
            dedup_checked="none",
        )

        rc = execute(args)

        assert rc == 0
        build_mock.assert_called_once()
