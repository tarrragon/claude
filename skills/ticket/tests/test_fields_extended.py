"""PROP-009 面向 A：擴充欄位命令測試。

測試 set-priority、add-acceptance、remove-acceptance、
add-spawned、set-decision-tree 五個新命令。
"""

import argparse
import os
import tempfile

import pytest
import yaml

from ticket_system.commands.fields import (
    execute_set_priority,
    execute_add_acceptance,
    execute_remove_acceptance,
    execute_add_spawned,
    execute_set_decision_tree,
)


def _create_ticket_file(tmp_path, ticket_id, version, **extra_fields):
    """建立測試用 Ticket 檔案，回傳 (version, tickets_dir)。"""
    tickets_dir = tmp_path / "docs" / "work-logs" / f"v{version}" / "tickets"
    tickets_dir.mkdir(parents=True)

    frontmatter = {
        "id": ticket_id,
        "title": "Test Ticket",
        "type": "IMP",
        "status": "in_progress",
        "version": version,
        "wave": 1,
        "priority": "P2",
        "acceptance": ["[ ] AC-1", "[ ] AC-2"],
        "spawned_tickets": [],
        "decision_tree_path": {
            "entry_point": "",
            "final_decision": "",
            "rationale": "",
        },
    }
    frontmatter.update(extra_fields)

    ticket_path = tickets_dir / f"{ticket_id}.md"
    content = "---\n" + yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False) + "---\n\n# Execution Log\n"
    ticket_path.write_text(content, encoding="utf-8")

    return version, tmp_path


def _make_args(ticket_id, version=None, **kwargs):
    """建立 argparse.Namespace mock。"""
    ns = argparse.Namespace(ticket_id=ticket_id, version=version)
    for k, v in kwargs.items():
        setattr(ns, k, v)
    return ns


@pytest.fixture
def ticket_env(tmp_path, monkeypatch):
    """建立測試環境：tmp Ticket + 設定工作目錄。"""
    ticket_id = "0.99.0-W1-001"
    version, base_dir = _create_ticket_file(tmp_path, ticket_id, "0.99.0")
    monkeypatch.chdir(base_dir)
    return ticket_id, version


class TestSetPriority:
    """set-priority 命令測試"""

    def test_set_priority_success(self, ticket_env):
        ticket_id, version = ticket_env
        args = _make_args(ticket_id, version, value="P0")
        result = execute_set_priority(args, version)
        assert result == 0


class TestAddAcceptance:
    """add-acceptance 命令測試"""

    def test_add_acceptance_appends(self, ticket_env):
        ticket_id, version = ticket_env
        args = _make_args(ticket_id, version, value="新增的驗收條件")
        result = execute_add_acceptance(args, version)
        assert result == 0

    def test_add_acceptance_has_checkbox_prefix(self, ticket_env, capsys):
        ticket_id, version = ticket_env
        args = _make_args(ticket_id, version, value="帶前綴的條件")
        execute_add_acceptance(args, version)
        captured = capsys.readouterr()
        assert "[ ] 帶前綴的條件" in captured.out


class TestRemoveAcceptance:
    """remove-acceptance 命令測試"""

    def test_remove_acceptance_by_index(self, ticket_env):
        ticket_id, version = ticket_env
        args = _make_args(ticket_id, version, index=1)
        result = execute_remove_acceptance(args, version)
        assert result == 0

    def test_remove_acceptance_invalid_index(self, ticket_env):
        ticket_id, version = ticket_env
        args = _make_args(ticket_id, version, index=99)
        result = execute_remove_acceptance(args, version)
        assert result == 1


class TestAddSpawned:
    """add-spawned 命令測試"""

    def test_add_spawned_appends(self, ticket_env):
        ticket_id, version = ticket_env
        args = _make_args(ticket_id, version, value="0.99.0-W2-001")
        result = execute_add_spawned(args, version)
        assert result == 0

    def test_add_spawned_dedup(self, ticket_env, capsys):
        ticket_id, version = ticket_env
        args = _make_args(ticket_id, version, value="0.99.0-W2-001")
        execute_add_spawned(args, version)
        result = execute_add_spawned(args, version)
        assert result == 0
        captured = capsys.readouterr()
        assert "已存在" in captured.out


class TestSetDecisionTree:
    """set-decision-tree 命令測試"""

    def test_set_decision_tree_full(self, ticket_env):
        ticket_id, version = ticket_env
        args = _make_args(
            ticket_id, version,
            entry="第五層:實作",
            decision="TDD Phase 3b",
            rationale="品質基線",
        )
        result = execute_set_decision_tree(args, version)
        assert result == 0

    def test_set_decision_tree_partial(self, ticket_env, capsys):
        ticket_id, version = ticket_env
        args = _make_args(
            ticket_id, version,
            entry="第五層:分析",
            decision=None,
            rationale=None,
        )
        result = execute_set_decision_tree(args, version)
        assert result == 0
        captured = capsys.readouterr()
        assert "entry_point" in captured.out
