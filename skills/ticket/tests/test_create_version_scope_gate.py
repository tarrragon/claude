"""版本範圍凍結硬閘門測試（0.1.0-W3-651）。

動機：現有版本歸屬引導只有「功能 vs 修復」一個軸，沒有「目標版本現在還
收不收票」的軸；todolist.yaml 的 status 只有 active|planned|completed，
一旦 active 所有根票（含 spawn 票）預設流入。0.1.0 實測：pending 池 83
張，必要與非必要工作混在同一池裡無法分辨——版本無法發佈不是因為必要
工作沒做完，是必要與非必要在同一池裡無法分辨。本閘門與可攜問題分流
閘門（W3-648）正交，同在 create 驗證層，形態比照其五層結構。

涵蓋：
- A 層：`is_version_scope_frozen` 單元測試（欄位缺席/open/frozen/版本不存在）
- B 層：`suggest_overflow_version` 單元測試（feature→minor+1、patch 類→patch+1）
- C 層：`validate_version_scope_gate` 單元測試（放行/阻擋 + 訊息內容）
- D 層：argparse `--scope-blocker` 註冊測試
- E 層：`execute()` CLI 整合測試（凍結阻擋根票 / 放行子票 / --scope-blocker
  放行 / 未凍結版本正向對照），以 tmp todolist.yaml fixture 注入
  `scope: frozen` 作為紅輸入驗證閘門確實命中
"""

import argparse
from unittest.mock import MagicMock

import pytest

from ticket_system.commands.create import execute
from ticket_system.lib.field_validators import validate_version_scope_gate
from ticket_system.lib.version import (
    _suggest_next_patch,
    is_version_scope_frozen,
    suggest_overflow_version,
    validate_version_registered,
)


# ============================================================
# A 層：is_version_scope_frozen 單元測試
# ============================================================


class TestIsVersionScopeFrozen:
    def test_todolist_missing_not_frozen(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "ticket_system.lib.version.get_project_root", lambda: tmp_path
        )
        assert is_version_scope_frozen("0.1.0") is False

    def test_scope_field_absent_not_frozen(self, monkeypatch, tmp_path):
        _write_todolist(tmp_path, [{"version": "0.1.0", "status": "active"}])
        monkeypatch.setattr(
            "ticket_system.lib.version.get_project_root", lambda: tmp_path
        )
        assert is_version_scope_frozen("0.1.0") is False

    def test_scope_open_not_frozen(self, monkeypatch, tmp_path):
        _write_todolist(
            tmp_path,
            [{"version": "0.1.0", "status": "active", "scope": "open"}],
        )
        monkeypatch.setattr(
            "ticket_system.lib.version.get_project_root", lambda: tmp_path
        )
        assert is_version_scope_frozen("0.1.0") is False

    def test_scope_frozen_is_frozen(self, monkeypatch, tmp_path):
        _write_todolist(
            tmp_path,
            [{"version": "0.1.0", "status": "active", "scope": "frozen"}],
        )
        monkeypatch.setattr(
            "ticket_system.lib.version.get_project_root", lambda: tmp_path
        )
        assert is_version_scope_frozen("0.1.0") is True

    def test_version_not_found_not_frozen(self, monkeypatch, tmp_path):
        _write_todolist(
            tmp_path,
            [{"version": "0.1.0", "status": "active", "scope": "frozen"}],
        )
        monkeypatch.setattr(
            "ticket_system.lib.version.get_project_root", lambda: tmp_path
        )
        assert is_version_scope_frozen("9.9.9") is False


def _write_todolist(tmp_path, versions: list) -> None:
    import yaml

    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    with open(docs_dir / "todolist.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump({"versions": versions}, f, allow_unicode=True)


# ============================================================
# B 層：suggest_overflow_version 單元測試
# ============================================================


class TestSuggestOverflowVersion:
    def test_feature_action_suggests_minor_bump(self):
        result = suggest_overflow_version("0.1.0", "IMP", "新增")
        assert result is not None
        version, reason = result
        assert version == "0.2.0"

    def test_implement_action_suggests_minor_bump(self):
        result = suggest_overflow_version("0.1.0", "IMP", "實作")
        version, _reason = result
        assert version == "0.2.0"

    def test_fix_action_suggests_patch_bump(self):
        result = suggest_overflow_version("0.1.0", "IMP", "修復")
        version, _reason = result
        assert version == "0.1.1"

    def test_ana_type_suggests_patch_bump(self):
        result = suggest_overflow_version("0.1.0", "ANA", "分析")
        version, _reason = result
        assert version == "0.1.1"

    def test_doc_type_suggests_patch_bump(self):
        result = suggest_overflow_version("0.1.0", "DOC", "文件")
        version, _reason = result
        assert version == "0.1.1"

    def test_malformed_version_returns_none(self):
        assert suggest_overflow_version("0.1", "IMP", "新增") is None
        assert suggest_overflow_version("not-a-version", "IMP", "新增") is None


# ============================================================
# C 層：validate_version_scope_gate 單元測試
# ============================================================


class TestValidateVersionScopeGate:
    def test_not_frozen_passes_without_output(self, monkeypatch, capsys):
        monkeypatch.setattr(
            "ticket_system.lib.version.is_version_scope_frozen", lambda v: False
        )
        result = validate_version_scope_gate("0.1.0", "IMP", "新增", None)
        assert result is True
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_frozen_without_blocker_blocks(self, monkeypatch, capsys):
        monkeypatch.setattr(
            "ticket_system.lib.version.is_version_scope_frozen", lambda v: True
        )
        monkeypatch.setattr(
            "ticket_system.lib.version.suggest_overflow_version",
            lambda v, t, a: ("0.2.0", "新功能歸下一個小版本"),
        )
        result = validate_version_scope_gate("0.1.0", "IMP", "新增", None)
        assert result is False
        captured = capsys.readouterr()
        assert "VERSION_SCOPE_FROZEN" in captured.out
        assert "0.2.0" in captured.out
        assert "--version" in captured.out
        assert "--scope-blocker" in captured.out

    def test_frozen_with_empty_string_blocker_blocks(self, monkeypatch, capsys):
        # E1：只給旗標不給理由（空字串）仍阻擋
        monkeypatch.setattr(
            "ticket_system.lib.version.is_version_scope_frozen", lambda v: True
        )
        monkeypatch.setattr(
            "ticket_system.lib.version.suggest_overflow_version",
            lambda v, t, a: ("0.2.0", "新功能歸下一個小版本"),
        )
        result = validate_version_scope_gate("0.1.0", "IMP", "新增", "")
        assert result is False
        captured = capsys.readouterr()
        assert "VERSION_SCOPE_FROZEN" in captured.out

    def test_frozen_with_reason_passes(self, monkeypatch, capsys):
        monkeypatch.setattr(
            "ticket_system.lib.version.is_version_scope_frozen", lambda v: True
        )
        result = validate_version_scope_gate(
            "0.1.0", "IMP", "新增", "必要 bugfix，需進已凍結版本"
        )
        assert result is True
        captured = capsys.readouterr()
        assert "版本範圍凍結" in captured.out


# ============================================================
# D 層：argparse 註冊測試
# ============================================================


class TestScopeBlockerArgRegistered:
    def _build_parser(self):
        from ticket_system.commands.create import register

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="cmd")
        register(subparsers)
        return parser

    def test_scope_blocker_flag_registered(self):
        parser = self._build_parser()
        args = parser.parse_args([
            "create",
            "--action", "test",
            "--target", "sth",
            "--scope-blocker", "必要理由",
        ])
        assert args.scope_blocker == "必要理由"

    def test_scope_blocker_default_none(self):
        parser = self._build_parser()
        args = parser.parse_args([
            "create",
            "--action", "test",
            "--target", "sth",
        ])
        assert getattr(args, "scope_blocker", None) is None


# ============================================================
# E 層：execute() CLI 整合測試
# ============================================================


def _make_args(**overrides) -> argparse.Namespace:
    defaults = {
        "version": None,
        "wave": 3,
        "seq": None,
        "type": "IMP",
        "priority": "P2",
        "action": "新增",
        "target": "測試目標",
        "title": "W3-651 閘門測試票",
        "who": "thyme-python-developer",
        "what": "測試用 what",
        "when": "v0.1.0",
        "where_layer": "Infrastructure",
        "where_files": "lib/screens/x.dart",
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
        "decision_tree_rationale": "0.1.0-W3-651 測試",
        "force": False,
        "quiet": False,
        "verbose": False,
        "json_output": False,
        "dedup_checked": None,
        "scope_blocker": None,
        "topic": None,
        "new_topic": None,
        "no_topic": True,
        "dry_run": False,
        "allow_duplicate": False,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _install_common_mocks(monkeypatch, frozen: bool = False):
    monkeypatch.setattr(
        "ticket_system.commands.create.resolve_version",
        lambda v: "0.1.0",
    )
    monkeypatch.setattr(
        "ticket_system.lib.version.validate_version_registered",
        lambda v: (True, ""),
    )
    monkeypatch.setattr(
        "ticket_system.lib.version.is_version_scope_frozen",
        lambda v: frozen,
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


class TestExecuteBlocksFrozenRootTicket:
    def test_frozen_version_blocks_root_ticket(self, monkeypatch, capsys):
        build_mock = _install_common_mocks(monkeypatch, frozen=True)
        args = _make_args()

        rc = execute(args)

        assert rc == 1
        captured = capsys.readouterr()
        assert "VERSION_SCOPE_FROZEN" in captured.out
        build_mock.assert_not_called()


class TestExecuteAllowsChildTicketUnderFrozenVersion:
    def test_frozen_version_does_not_block_child_ticket(self, monkeypatch, capsys):
        build_mock = _install_common_mocks(monkeypatch, frozen=True)
        monkeypatch.setattr(
            "ticket_system.commands.create.extract_version_from_ticket_id",
            lambda tid: "0.1.0",
        )
        args = _make_args(parent="0.1.0-W3-001")

        rc = execute(args)

        assert rc == 0
        build_mock.assert_called_once()
        captured = capsys.readouterr()
        assert "VERSION_SCOPE_FROZEN" not in captured.out


class TestExecuteScopeBlockerAllowsRootTicket:
    def test_scope_blocker_with_reason_passes(self, monkeypatch, capsys):
        build_mock = _install_common_mocks(monkeypatch, frozen=True)
        args = _make_args(scope_blocker="必要 bugfix，需進已凍結版本")

        rc = execute(args)

        assert rc == 0
        build_mock.assert_called_once()

    def test_scope_blocker_empty_string_still_blocks(self, monkeypatch, capsys):
        # E1：僅給旗標不給理由（空字串）仍阻擋
        build_mock = _install_common_mocks(monkeypatch, frozen=True)
        args = _make_args(scope_blocker="")

        rc = execute(args)

        assert rc == 1
        build_mock.assert_not_called()


class TestExecuteUnfrozenVersionUnaffected:
    """正向對照組：未凍結版本的正常建票不受閘門影響。"""

    def test_unfrozen_version_root_ticket_passes(self, monkeypatch, capsys):
        build_mock = _install_common_mocks(monkeypatch, frozen=False)
        args = _make_args()

        rc = execute(args)

        assert rc == 0
        build_mock.assert_called_once()
        captured = capsys.readouterr()
        assert "VERSION_SCOPE_FROZEN" not in captured.out


class TestExecuteWithTmpTodolistFixture:
    """E2：以 tmp fixture 注入 scope: frozen 作為紅輸入，驗證閘門確實命中
    （非僅靠 mock is_version_scope_frozen 回傳值，而是走真實 yaml 讀取路徑）。
    """

    def test_tmp_fixture_frozen_scope_blocks(self, monkeypatch, capsys, tmp_path):
        _write_todolist(
            tmp_path,
            [{"version": "0.1.0", "status": "active", "scope": "frozen"}],
        )
        monkeypatch.setattr(
            "ticket_system.lib.version.get_project_root", lambda: tmp_path
        )
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
        args = _make_args()

        rc = execute(args)

        assert rc == 1
        captured = capsys.readouterr()
        assert "VERSION_SCOPE_FROZEN" in captured.out

    def test_tmp_fixture_open_scope_unaffected(self, monkeypatch, capsys, tmp_path):
        _write_todolist(
            tmp_path,
            [{"version": "0.1.0", "status": "active", "scope": "open"}],
        )
        monkeypatch.setattr(
            "ticket_system.lib.version.get_project_root", lambda: tmp_path
        )
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
        build_mock = MagicMock(return_value=stub_ticket)
        monkeypatch.setattr(
            "ticket_system.commands.create._build_and_save_ticket", build_mock
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
        args = _make_args()

        rc = execute(args)

        assert rc == 0
        build_mock.assert_called_once()


# ============================================================
# F 層：validate_version_registered 放寬收 planned（0.1.0-W3-652）
# ============================================================


class TestValidateVersionRegisteredAcceptsPlanned:
    def test_planned_version_passes(self, monkeypatch, tmp_path):
        _write_todolist(
            tmp_path,
            [{"version": "0.2.0", "status": "planned"}],
        )
        monkeypatch.setattr(
            "ticket_system.lib.version.get_project_root", lambda: tmp_path
        )
        is_valid, error_msg = validate_version_registered("0.2.0")
        assert is_valid is True
        assert error_msg == ""

    def test_completed_version_still_rejected(self, monkeypatch, tmp_path):
        """E2：completed 版本作紅輸入，放寬後仍須被拒。"""
        _write_todolist(
            tmp_path,
            [{"version": "0.0.9", "status": "completed"}],
        )
        monkeypatch.setattr(
            "ticket_system.lib.version.get_project_root", lambda: tmp_path
        )
        is_valid, error_msg = validate_version_registered("0.0.9")
        assert is_valid is False
        assert "只有 planned 或 active 版本可建票" in error_msg


class TestExecuteCreatesTicketInPlannedVersion:
    """E2：以 tmp fixture 的 planned 版本作根票版本，驗證 create 真正放行
    （非僅靠單元測試，而是走完整 execute() CLI 整合路徑）。
    """

    def _install_mocks_without_version_registered_stub(self, monkeypatch, resolved_version):
        """比照 TestExecuteWithTmpTodolistFixture：不覆寫
        validate_version_registered，讓它走真實 yaml 讀取路徑。"""
        monkeypatch.setattr(
            "ticket_system.commands.create.resolve_version",
            lambda v: resolved_version,
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
        build_mock = MagicMock(return_value=stub_ticket)
        monkeypatch.setattr(
            "ticket_system.commands.create._build_and_save_ticket", build_mock
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
        return build_mock

    def test_planned_version_allows_root_ticket_create(self, monkeypatch, capsys, tmp_path):
        _write_todolist(
            tmp_path,
            [{"version": "0.2.0", "status": "planned"}],
        )
        monkeypatch.setattr(
            "ticket_system.lib.version.get_project_root", lambda: tmp_path
        )
        build_mock = self._install_mocks_without_version_registered_stub(
            monkeypatch, "0.2.0"
        )
        args = _make_args(version="0.2.0")

        rc = execute(args)

        assert rc == 0
        build_mock.assert_called_once()

    def test_completed_version_blocks_root_ticket_create(self, monkeypatch, capsys, tmp_path):
        """E2：completed 版本作紅輸入，create 整合路徑仍被拒。"""
        _write_todolist(
            tmp_path,
            [{"version": "0.0.9", "status": "completed"}],
        )
        monkeypatch.setattr(
            "ticket_system.lib.version.get_project_root", lambda: tmp_path
        )
        build_mock = self._install_mocks_without_version_registered_stub(
            monkeypatch, "0.0.9"
        )
        args = _make_args(version="0.0.9")

        rc = execute(args)

        assert rc == 1
        build_mock.assert_not_called()


# ============================================================
# G 層：_suggest_next_patch 基準改為 active（0.1.0-W3-652）
# ============================================================


class TestSuggestNextPatchBasisChangedToActive:
    def test_no_active_version_returns_none(self):
        """僅有 completed、無 active：放寬前會回傳 0.0.4，放寬後回傳 None
        （E1：改前改後輸出不同——舊基準有結果，新基準無 active 可算）。"""
        versions = [{"version": "0.0.3", "status": "completed"}]
        assert _suggest_next_patch(versions) is None

    def test_uses_active_not_completed_as_basis(self):
        """completed 停留舊版號、active 已推進：新基準採 active+1，
        非舊基準的 completed+1（E1：改前改後輸出不同）。"""
        versions = [
            {"version": "0.0.3", "status": "completed"},
            {"version": "0.1.0", "status": "active"},
        ]
        result = _suggest_next_patch(versions)
        assert result is not None
        suggested, _reason = result
        # 舊基準（completed+1）會得到 0.0.4；新基準（active+1）得到 0.1.1
        assert suggested == "0.1.1"
        assert suggested != "0.0.4"

    def test_suggested_version_already_registered_returns_existing(self):
        versions = [
            {"version": "0.1.0", "status": "active"},
            {"version": "0.1.1", "status": "planned"},
        ]
        result = _suggest_next_patch(versions)
        assert result == ("0.1.1", "修復/改善/分析/文件類型歸小版本")


# ============================================================
# H 層：--scope-blocker 理由持久化為 frontmatter scope_blocker 欄位
# ============================================================


class TestScopeBlockerPersistedToFrontmatter:
    def test_scope_blocker_written_to_config_and_frontmatter(self, monkeypatch, capsys):
        from ticket_system.lib.ticket_builder import create_ticket_frontmatter

        build_mock = _install_common_mocks(monkeypatch, frozen=True)
        args = _make_args(scope_blocker="必要 bugfix，需進已凍結版本")

        rc = execute(args)

        assert rc == 0
        build_mock.assert_called_once()
        config = build_mock.call_args[0][2]
        assert config["scope_blocker"] == "必要 bugfix，需進已凍結版本"

        frontmatter = create_ticket_frontmatter(config)
        assert frontmatter["scope_blocker"] == "必要 bugfix，需進已凍結版本"

    def test_no_scope_blocker_persists_none(self, monkeypatch, capsys):
        from ticket_system.lib.ticket_builder import create_ticket_frontmatter

        build_mock = _install_common_mocks(monkeypatch, frozen=False)
        args = _make_args()

        rc = execute(args)

        assert rc == 0
        config = build_mock.call_args[0][2]
        assert config.get("scope_blocker") is None

        frontmatter = create_ticket_frontmatter(config)
        assert frontmatter["scope_blocker"] is None
