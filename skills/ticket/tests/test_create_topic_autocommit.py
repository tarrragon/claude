"""0.4.0-W1-052 — create 的 auto-commit 連同旁路寫入一起提交

旁路寫入：(1) topic-assignments.txt 的主題行；(2) --source-ticket 來源票
spawned_tickets 回填。兩者須與新票 md 進同一個隔離索引提交。

topic-assignments.txt 為多寫入者 append-only 檔：提交的 blob 必須是
「HEAD 版本 + 本次追加的那一行」，不可帶入工作區內他人未提交的行。

對照組（E1/E2）：
- E1：有主題 -> 提交後 topic-assignments.txt 乾淨；來源票回填亦乾淨
- E2：--no-topic / 無主題 -> 該檔不出現在任何提交
- 他人未提交的行：提交 blob 不含，工作區仍保留
"""

from __future__ import annotations

import pytest

from tests.test_create_auto_commit import (
    _commit_count,
    _install_context_bundle_path_mocks,
    _make_args,
    _run_git,
    _write_source_ticket_for_bundle,
    git_repo,  # noqa: F401  fixture
    patch_paths_to_repo,  # noqa: F401  fixture
)

TOPIC_REL = "docs/work-logs/topic-assignments.txt"
REGISTRY_REL = "docs/work-logs/topics-registry.txt"


@pytest.fixture
def topic_repo(patch_paths_to_repo, monkeypatch):
    """repo 內備妥已提交的 topic-assignments.txt 與 topics-registry.txt。"""
    repo = patch_paths_to_repo
    (repo / "docs" / "work-logs").mkdir(parents=True)
    topic_file = repo / TOPIC_REL
    registry = repo / REGISTRY_REL
    topic_file.write_text("0.0.0-W9-001\t既有主題\n", encoding="utf-8")
    registry.write_text("既有主題\n", encoding="utf-8")
    _run_git(repo, "add", TOPIC_REL, REGISTRY_REL)
    _run_git(repo, "commit", "-m", "seed topic files")
    monkeypatch.setattr(
        "ticket_system.lib.topic_assignments._assignments_path", lambda: topic_file
    )
    monkeypatch.setattr(
        "ticket_system.lib.topic_registry._registry_path", lambda: registry
    )
    return repo


def _porcelain(repo, rel: str) -> str:
    return _run_git(repo, "status", "--porcelain", "--", rel).stdout.strip()


def _new_ticket_id(tickets_dir, exclude=()) -> str:
    ids = [p.stem for p in tickets_dir.glob("*.md") if p.stem not in exclude]
    assert len(ids) == 1, ids
    return ids[0]


class TestTopicLineCommitted:
    def test_e1_topic_line_in_same_commit_and_worktree_clean(self, topic_repo):
        from ticket_system.commands.create import execute

        repo = topic_repo
        before = _commit_count(repo)
        assert execute(_make_args(topic="既有主題")) == 0

        tid = _new_ticket_id(repo / "tickets")
        assert _commit_count(repo) == before + 1, "應仍為單一提交"
        assert _porcelain(repo, TOPIC_REL) == "", "主題行不應殘留工作區"
        committed = _run_git(repo, "show", f"HEAD:{TOPIC_REL}").stdout
        assert f"{tid}\t既有主題\n" in committed
        changed = _run_git(repo, "show", "--name-only", "--pretty=format:", "HEAD")
        assert set(changed.stdout.split()) == {f"tickets/{tid}.md", TOPIC_REL}

    def test_e2_no_topic_does_not_commit_topic_file(self, topic_repo):
        from ticket_system.commands.create import execute

        repo = topic_repo
        assert execute(_make_args(no_topic=True)) == 0
        changed = _run_git(repo, "show", "--name-only", "--pretty=format:", "HEAD")
        assert TOPIC_REL not in changed.stdout.split()

    def test_others_uncommitted_lines_not_absorbed(self, topic_repo):
        from ticket_system.commands.create import execute

        repo = topic_repo
        topic_file = repo / TOPIC_REL
        with topic_file.open("a", encoding="utf-8") as f:
            f.write("0.0.0-W8-777\t他人未提交\n")

        assert execute(_make_args(topic="既有主題")) == 0

        tid = _new_ticket_id(repo / "tickets")
        committed = _run_git(repo, "show", f"HEAD:{TOPIC_REL}").stdout
        assert f"{tid}\t既有主題" in committed
        assert "他人未提交" not in committed, "他人未提交的行不得進入本次提交"
        assert "他人未提交" in topic_file.read_text(encoding="utf-8"), "工作區須保留"
        assert _porcelain(repo, TOPIC_REL) != "", "他人的行仍是未提交修改"


class TestSourceTicketBackfillCommitted:
    def test_e1_extension_source_spawned_tickets_in_same_commit(
        self, topic_repo, monkeypatch
    ):
        from ticket_system.commands.create import execute

        repo = topic_repo
        tickets_dir = repo / "tickets"
        source_id = "0.0.0-W1-999"
        _write_source_ticket_for_bundle(tickets_dir, source_id)
        _install_context_bundle_path_mocks(monkeypatch, tickets_dir)
        monkeypatch.setattr(
            "ticket_system.lib.ticket_builder.get_ticket_path",
            lambda v, tid: tickets_dir / f"{tid}.md",
        )
        _run_git(repo, "add", f"tickets/{source_id}.md")
        _run_git(repo, "commit", "-m", "seed source ticket")

        assert execute(_make_args(source_ticket=source_id, topic="既有主題")) == 0

        tid = _new_ticket_id(tickets_dir, exclude=(source_id,))
        assert _porcelain(repo, f"tickets/{source_id}.md") == "", "來源票回填不應殘留"
        committed_src = _run_git(repo, "show", f"HEAD:tickets/{source_id}.md").stdout
        assert tid in committed_src
        changed = _run_git(repo, "show", "--name-only", "--pretty=format:", "HEAD")
        assert set(changed.stdout.split()) == {
            f"tickets/{tid}.md",
            f"tickets/{source_id}.md",
            TOPIC_REL,
        }


class TestNewTopicRegistryCommitted:
    def test_e1_new_topic_registry_line_in_same_commit(self, topic_repo):
        from ticket_system.commands.create import execute

        repo = topic_repo
        before = _commit_count(repo)
        assert execute(_make_args(new_topic="全新主題")) == 0

        assert _commit_count(repo) == before + 1
        assert _porcelain(repo, REGISTRY_REL) == "", "registry 行不應殘留工作區"
        assert _porcelain(repo, TOPIC_REL) == ""
        committed = _run_git(repo, "show", f"HEAD:{REGISTRY_REL}").stdout
        assert committed == "既有主題\n全新主題\n"

    def test_e2_existing_topic_does_not_commit_registry(self, topic_repo):
        from ticket_system.commands.create import execute

        assert execute(_make_args(topic="既有主題")) == 0
        changed = _run_git(topic_repo, "show", "--name-only", "--pretty=format:", "HEAD")
        assert REGISTRY_REL not in changed.stdout.split()

    def test_others_uncommitted_registry_lines_not_absorbed(self, topic_repo):
        from ticket_system.commands.create import execute

        repo = topic_repo
        with (repo / REGISTRY_REL).open("a", encoding="utf-8") as f:
            f.write("他人未提交主題\n")
        assert execute(_make_args(new_topic="全新主題")) == 0

        committed = _run_git(repo, "show", f"HEAD:{REGISTRY_REL}").stdout
        assert "全新主題" in committed and "他人未提交主題" not in committed
        assert "他人未提交主題" in (repo / REGISTRY_REL).read_text(encoding="utf-8")


class TestParentChildrenBackfillCommitted:
    def test_e1_parent_children_in_same_commit(self, topic_repo, monkeypatch):
        from ticket_system.commands.create import execute

        repo = topic_repo
        tickets_dir = repo / "tickets"
        parent_id = "0.0.0-W1-999"
        _write_source_ticket_for_bundle(tickets_dir, parent_id)
        _install_context_bundle_path_mocks(monkeypatch, tickets_dir)
        monkeypatch.setattr(
            "ticket_system.lib.ticket_builder.get_ticket_path",
            lambda v, tid: tickets_dir / f"{tid}.md",
        )
        _run_git(repo, "add", f"tickets/{parent_id}.md")
        _run_git(repo, "commit", "-m", "seed parent ticket")

        assert execute(_make_args(parent=parent_id, topic="既有主題")) == 0

        child_id = _new_ticket_id(tickets_dir, exclude=(parent_id,))
        assert _porcelain(repo, f"tickets/{parent_id}.md") == "", "母票回填不應殘留"
        assert child_id in _run_git(repo, "show", f"HEAD:tickets/{parent_id}.md").stdout
        changed = _run_git(repo, "show", "--name-only", "--pretty=format:", "HEAD")
        assert set(changed.stdout.split()) == {
            f"tickets/{child_id}.md",
            f"tickets/{parent_id}.md",
            TOPIC_REL,
        }
