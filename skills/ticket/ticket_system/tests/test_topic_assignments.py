"""lib/topic_assignments.py 的單元測試：改派途徑（0.2.1-W3-804）。

`append_assignment` 的基礎行為（建檔、註冊主題、拒絕重複 ticket_id）已由
`tests/test_topic_backfill.py::TestAppendAssignmentBasic` 覆蓋（該模組
re-export 同一組函式，兩檔測資互不重疊，本檔僅聚焦本票新增的改派途徑：
`reassign_assignment` 與 `list_assignment_history`）。

隔離依賴同目錄 `.claude/skills/ticket/conftest.py` 的 autouse fixture
`_isolate_project_root`：每個 test 前自動清 `get_project_root()` 快取並
注入獨立 tmp 目錄，故本檔測試互不污染，亦不觸及真實 repo 的
`docs/work-logs/topic-assignments.txt`。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from ticket_system.lib import topic_assignments
from ticket_system.lib import topic_registry
from ticket_system.lib.paths import (
    get_project_root,
    reset_project_root_cache,
    reset_ticket_state_root_cache,
)


def _assignments_file():
    return get_project_root() / topic_assignments.TOPIC_ASSIGNMENTS_RELATIVE_PATH


def _run_git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    )


def _init_git_repo(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    _run_git(root, "init", "-q")
    _run_git(root, "checkout", "-q", "-b", "main")
    _run_git(root, "config", "user.email", "test@example.com")
    _run_git(root, "config", "user.name", "Test")
    (root / "README.md").write_text("init\n", encoding="utf-8")
    _run_git(root, "add", "README.md")
    _run_git(root, "commit", "-q", "-m", "init")


@pytest.fixture
def linked_worktree(tmp_path, monkeypatch):
    """建立真實 main repo + linked worktree，cwd 切至 worktree。

    關閉 autouse `_isolate_project_root` 注入的
    `TICKET_SYSTEM_TEST_ISOLATION` 逃生艙與 `CLAUDE_PROJECT_DIR`（手法同
    `conftest.py` 的 `real_repo_root` fixture：後設定的 monkeypatch 勝出），
    使 `get_project_root()` / `get_ticket_state_root()` 走真實 git 解析鏈，
    真實重現 worktree 場景下兩者的根目錄分歧。
    """
    main_root = tmp_path / "main"
    wt_root = tmp_path / "wt"
    _init_git_repo(main_root)
    _run_git(main_root, "worktree", "add", "-q", "-b", "feat/test", str(wt_root), "HEAD")

    monkeypatch.delenv("TICKET_SYSTEM_TEST_ISOLATION", raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    reset_project_root_cache()
    reset_ticket_state_root_cache()
    monkeypatch.chdir(wt_root)

    yield main_root, wt_root

    reset_project_root_cache()
    reset_ticket_state_root_cache()


class TestAppendAssignmentWorktreeRootUnification:
    """0.2.1-W4-025：linked worktree cwd 下寫入應落在主倉庫，非 worktree 副本。"""

    def test_append_assignment_in_linked_worktree_writes_to_main_repo(
        self, linked_worktree
    ):
        main_root, wt_root = linked_worktree

        result = topic_assignments.append_assignment("0.1.0-W1-777", "主題 A")

        main_file = main_root / topic_assignments.TOPIC_ASSIGNMENTS_RELATIVE_PATH
        wt_file = wt_root / topic_assignments.TOPIC_ASSIGNMENTS_RELATIVE_PATH

        assert result is True
        assert main_file.exists()
        assert "0.1.0-W1-777\t主題 A" in main_file.read_text(encoding="utf-8")
        assert not wt_file.exists()


class TestReassignAssignmentBasic:
    def test_reassign_on_unassigned_ticket_writes_like_append(self):
        result = topic_assignments.reassign_assignment("0.1.0-W1-001", "主題 A")
        assert result is True
        assert topic_assignments.list_assignments() == {"0.1.0-W1-001": "主題 A"}

    def test_reassign_registers_topic_in_central_registry(self):
        topic_assignments.reassign_assignment("0.1.0-W1-001", "主題 A")
        assert topic_registry.list_topics() == ["主題 A"]

    def test_reassign_rejects_blank_ticket_id(self):
        try:
            topic_assignments.reassign_assignment("   ", "主題 A")
        except ValueError:
            pass
        else:
            raise AssertionError("reassign_assignment 應對空白 ticket_id 拋出 ValueError")

    def test_reassign_rejects_blank_topic(self):
        try:
            topic_assignments.reassign_assignment("0.1.0-W1-001", "   ")
        except ValueError:
            pass
        else:
            raise AssertionError("reassign_assignment 應對空白 topic 拋出 ValueError")


class TestReassignAssignmentOverwritesReadSemantics:
    """acceptance 第 1 條：改派後 list_assignments 回傳新主題。"""

    def test_list_assignments_returns_new_topic_after_reassign(self):
        topic_assignments.append_assignment("0.1.0-W1-001", "主題 A")
        result = topic_assignments.reassign_assignment("0.1.0-W1-001", "主題 B")

        assert result is True
        assert topic_assignments.list_assignments() == {"0.1.0-W1-001": "主題 B"}

    def test_reassign_is_noop_when_topic_unchanged(self):
        topic_assignments.append_assignment("0.1.0-W1-001", "主題 A")
        result = topic_assignments.reassign_assignment("0.1.0-W1-001", "主題 A")

        assert result is False
        assert topic_assignments.list_assignments() == {"0.1.0-W1-001": "主題 A"}

    def test_reassign_does_not_affect_other_tickets(self):
        topic_assignments.append_assignment("0.1.0-W1-001", "主題 A")
        topic_assignments.append_assignment("0.1.0-W1-002", "主題 B")
        topic_assignments.reassign_assignment("0.1.0-W1-001", "主題 C")

        assert topic_assignments.list_assignments() == {
            "0.1.0-W1-001": "主題 C",
            "0.1.0-W1-002": "主題 B",
        }


class TestReassignAssignmentAppendOnly:
    """硬約束：檔案層維持 append-only，既有行不得改寫，改派以追加表示。"""

    def test_original_line_survives_as_prefix_after_reassign(self):
        topic_assignments.append_assignment("0.1.0-W1-001", "主題 A")
        original_content = _assignments_file().read_text(encoding="utf-8")

        topic_assignments.reassign_assignment("0.1.0-W1-001", "主題 B")
        new_content = _assignments_file().read_text(encoding="utf-8")

        assert new_content.startswith(original_content)
        assert new_content != original_content

    def test_file_contains_both_old_and_new_lines(self):
        topic_assignments.append_assignment("0.1.0-W1-001", "主題 A")
        topic_assignments.reassign_assignment("0.1.0-W1-001", "主題 B")

        content = _assignments_file().read_text(encoding="utf-8")
        assert "0.1.0-W1-001\t主題 A\n" in content
        assert "0.1.0-W1-001\t主題 B\n" in content


class TestListAssignmentHistory:
    """acceptance 第 4 條：改派歷史可查，能看出某票曾屬哪些主題。"""

    def test_history_empty_for_unknown_ticket(self):
        assert topic_assignments.list_assignment_history("0.1.0-W1-999") == []

    def test_history_single_entry_for_never_reassigned_ticket(self):
        topic_assignments.append_assignment("0.1.0-W1-001", "主題 A")
        assert topic_assignments.list_assignment_history("0.1.0-W1-001") == ["主題 A"]

    def test_history_lists_all_topics_in_write_order(self):
        topic_assignments.append_assignment("0.1.0-W1-001", "主題 A")
        topic_assignments.reassign_assignment("0.1.0-W1-001", "主題 B")
        topic_assignments.reassign_assignment("0.1.0-W1-001", "主題 C")

        assert topic_assignments.list_assignment_history("0.1.0-W1-001") == [
            "主題 A",
            "主題 B",
            "主題 C",
        ]

    def test_history_current_value_is_last_item(self):
        topic_assignments.append_assignment("0.1.0-W1-001", "主題 A")
        topic_assignments.reassign_assignment("0.1.0-W1-001", "主題 B")

        history = topic_assignments.list_assignment_history("0.1.0-W1-001")
        current = topic_assignments.list_assignments()["0.1.0-W1-001"]
        assert history[-1] == current

    def test_history_does_not_include_other_tickets(self):
        topic_assignments.append_assignment("0.1.0-W1-001", "主題 A")
        topic_assignments.append_assignment("0.1.0-W1-002", "主題 B")
        topic_assignments.reassign_assignment("0.1.0-W1-002", "主題 C")

        assert topic_assignments.list_assignment_history("0.1.0-W1-001") == ["主題 A"]
