"""
children / spawned_tickets 純量寫法解析測試（0.2.1-W3-719）

背景：`extract_children_from_frontmatter`（B7）、
`extract_spawned_tickets_from_frontmatter`（B6）、`_extract_spawned_list`
（B10）的 str 分支僅處理 dash-based 多行列表，對「單一純量、無 dash」
子情況（如 `children: a-1`）因逐行過濾條件 `line.startswith("-")` 不成立
而靜默回傳空清單。此為合法 YAML 寫法（同 `where.files` 已知結果 B8/B9），
非手寫 parser 缺陷，須保留並正確解析。

本測試以 `yaml.safe_load` 實際解析 YAML 原文，鎖定整條「原文 -> 解析 ->
提取」鏈路的行為，並涵蓋 children_checker 端到端阻擋場景。
"""

import logging
import sys
import importlib.util
from pathlib import Path

import yaml

_hooks_dir = Path(__file__).parent.parent
if str(_hooks_dir) not in sys.path:
    sys.path.insert(0, str(_hooks_dir))

from acceptance_checkers.ticket_parser import extract_children_from_frontmatter
from acceptance_checkers.ana_spawned_checker import (
    extract_spawned_tickets_from_frontmatter,
)
from acceptance_checkers.children_checker import (
    check_children_completed_from_frontmatter,
)


def _logger():
    log = logging.getLogger("test_children_spawned_scalar_parsing")
    log.addHandler(logging.NullHandler())
    return log


def _load_scheduler_hint_hook():
    """動態載入 session-start-scheduler-hint-hook.py（檔名含 dash）。"""
    hook_path = _hooks_dir / "session-start-scheduler-hint-hook.py"
    spec = importlib.util.spec_from_file_location(
        "session_start_scheduler_hint_hook_scalar_test", hook_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestExtractChildrenScalarForms:
    """B7：extract_children_from_frontmatter 三種合法寫法固定行為"""

    def test_list_form(self):
        fm = {"children": ["a-1", "a-2"]}
        assert extract_children_from_frontmatter(fm, _logger()) == ["a-1", "a-2"]

    def test_dash_multiline_form(self):
        parsed = yaml.safe_load("children:\n- a-1\n- a-2\n")
        assert extract_children_from_frontmatter(parsed, _logger()) == ["a-1", "a-2"]

    def test_single_scalar_form(self):
        """單一純量寫法（無 dash）為合法 YAML，須回傳單元素清單（非空清單）。"""
        parsed = yaml.safe_load("children: a-1\n")
        assert parsed == {"children": "a-1"}
        assert extract_children_from_frontmatter(parsed, _logger()) == ["a-1"]


class TestExtractSpawnedTicketsScalarForms:
    """B6：extract_spawned_tickets_from_frontmatter 三種合法寫法固定行為"""

    def test_list_form(self):
        fm = {"spawned_tickets": ["b-1", "b-2"]}
        assert extract_spawned_tickets_from_frontmatter(fm, _logger()) == [
            "b-1",
            "b-2",
        ]

    def test_dash_multiline_form(self):
        parsed = yaml.safe_load("spawned_tickets:\n- b-1\n- b-2\n")
        assert extract_spawned_tickets_from_frontmatter(parsed, _logger()) == [
            "b-1",
            "b-2",
        ]

    def test_single_scalar_form(self):
        parsed = yaml.safe_load("spawned_tickets: b-1\n")
        assert parsed == {"spawned_tickets": "b-1"}
        assert extract_spawned_tickets_from_frontmatter(parsed, _logger()) == ["b-1"]


class TestExtractSpawnedListScalarForms:
    """B10：_extract_spawned_list（session-start-scheduler-hint-hook）三種合法寫法固定行為"""

    def test_list_form(self):
        hook = _load_scheduler_hint_hook()
        fm = {"spawned_tickets": ["c-1", "c-2"]}
        assert hook._extract_spawned_list(fm) == ["c-1", "c-2"]

    def test_dash_multiline_form(self):
        hook = _load_scheduler_hint_hook()
        parsed = yaml.safe_load("spawned_tickets:\n- c-1\n- c-2\n")
        assert hook._extract_spawned_list(parsed) == ["c-1", "c-2"]

    def test_single_scalar_form(self):
        hook = _load_scheduler_hint_hook()
        parsed = yaml.safe_load("spawned_tickets: c-1\n")
        assert parsed == {"spawned_tickets": "c-1"}
        assert hook._extract_spawned_list(parsed) == ["c-1"]


class TestChildrenCheckerBlocksOnScalarChildren:
    """端到端：children_checker 對純量寫法的子票能正確偵測並阻擋 parent complete"""

    def _write_child(self, project_dir: Path, ticket_id: str, status: str) -> Path:
        version_part = ticket_id.split("-W")[0]
        ticket_dir = project_dir / "docs" / "work-logs" / f"v{version_part}" / "tickets"
        ticket_dir.mkdir(parents=True, exist_ok=True)
        content = (
            f"---\nid: {ticket_id}\ntitle: {ticket_id}\ntype: IMP\n"
            f"status: {status}\nversion: {version_part}\n---\n\n# Body\n"
        )
        ticket_file = ticket_dir / f"{ticket_id}.md"
        ticket_file.write_text(content, encoding="utf-8")
        return ticket_file

    def test_scalar_children_pending_child_blocks_complete(self, tmp_path):
        """父票 children 為單一純量、子票未完成 -> 須阻擋（修復前會靜默放行）。"""
        self._write_child(tmp_path, "0.0.0-W1-200", status="pending")

        parent_frontmatter = yaml.safe_load("children: 0.0.0-W1-200\n")
        should_block, error_msg = check_children_completed_from_frontmatter(
            ticket_file=tmp_path / "parent.md",
            frontmatter=parent_frontmatter,
            project_dir=tmp_path,
            ticket_id="0.0.0-W1-199",
            logger=_logger(),
        )

        assert should_block is True
        assert "0.0.0-W1-200" in error_msg

    def test_scalar_children_completed_child_allows_complete(self, tmp_path):
        """父票 children 為單一純量、子票已完成 -> 不阻擋（對照組，防止誤報）。"""
        self._write_child(tmp_path, "0.0.0-W1-201", status="completed")

        parent_frontmatter = yaml.safe_load("children: 0.0.0-W1-201\n")
        should_block, error_msg = check_children_completed_from_frontmatter(
            ticket_file=tmp_path / "parent.md",
            frontmatter=parent_frontmatter,
            project_dir=tmp_path,
            ticket_id="0.0.0-W1-199",
            logger=_logger(),
        )

        assert should_block is False
        assert error_msg is None
