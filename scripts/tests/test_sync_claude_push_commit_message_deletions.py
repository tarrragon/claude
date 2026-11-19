"""sync-claude-push：--clean 實際刪檔時，push commit 訊息 body 列出刪除路徑。

涵蓋：
  - 同一份 fixture（暫存區含刪除）帶與不帶 --clean，訊息不同（E1 對照）
  - 首行固定 v<版號>: <摘要>，帶 --clean 時 body 列出全部刪除路徑
  - 帶 --clean 但沒有刪除時，訊息與未帶 --clean 相同（只有首行）
  - 暫存區的修改與新增不列入刪除清單（正向對照：只有 D 計入）
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-push.py"
_spec = importlib.util.spec_from_file_location("sync_claude_push_commit_msg_deletions", _SCRIPT)
assert _spec and _spec.loader
sync_mod = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_push_commit_msg_deletions"] = sync_mod
_spec.loader.exec_module(sync_mod)  # type: ignore[union-attr]


def _git(args: list[str], cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True
    ).stdout.strip()


def _repo_with_staged_changes(path: Path) -> Path:
    """建 repo：初始 commit 含四檔，暫存區刪兩檔、改一檔、新增一檔。"""
    path.mkdir(parents=True)
    _git(["init", "-q", "-b", "main"], path)
    _git(["config", "user.email", "t@example.com"], path)
    _git(["config", "user.name", "t"], path)
    for rel in ("rules/a.md", "rules/b.md", "skills/x/SKILL.md", "keep.md"):
        f = path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(rel)
    _git(["add", "-A"], path)
    _git(["commit", "-q", "-m", "init"], path)

    (path / "rules/b.md").unlink()
    (path / "skills/x/SKILL.md").unlink()
    (path / "keep.md").write_text("modified")
    (path / "new.md").write_text("new")
    _git(["add", "-A"], path)
    return path


def test_clean_flag_changes_message_on_same_fixture(tmp_path):
    repo = _repo_with_staged_changes(tmp_path / "remote")

    with_clean = sync_mod.compose_push_commit_message(repo, "3.4.0", "摘要", True)
    without_clean = sync_mod.compose_push_commit_message(repo, "3.4.0", "摘要", False)

    assert with_clean != without_clean
    assert without_clean == "v3.4.0: 摘要"
    assert with_clean.splitlines()[0] == "v3.4.0: 摘要"


def test_clean_message_body_lists_all_deleted_paths(tmp_path):
    repo = _repo_with_staged_changes(tmp_path / "remote")

    msg = sync_mod.compose_push_commit_message(repo, "3.4.0", "摘要", True)
    first, blank, *body = msg.splitlines()

    assert first == "v3.4.0: 摘要"
    assert blank == ""
    assert "2" in body[0]
    assert body[1:] == ["- rules/b.md", "- skills/x/SKILL.md"]


def test_modified_and_added_files_not_listed_as_deletions(tmp_path):
    repo = _repo_with_staged_changes(tmp_path / "remote")

    deleted = sync_mod.list_staged_deletions(repo)

    assert deleted == ["rules/b.md", "skills/x/SKILL.md"]
    assert "keep.md" not in deleted
    assert "new.md" not in deleted


def test_clean_without_deletions_keeps_single_line(tmp_path):
    repo = tmp_path / "remote"
    repo.mkdir()
    _git(["init", "-q", "-b", "main"], repo)
    _git(["config", "user.email", "t@example.com"], repo)
    _git(["config", "user.name", "t"], repo)
    (repo / "a.md").write_text("a")
    _git(["add", "-A"], repo)
    _git(["commit", "-q", "-m", "init"], repo)
    (repo / "a.md").write_text("changed")
    _git(["add", "-A"], repo)

    msg = sync_mod.compose_push_commit_message(repo, "3.4.0", "摘要", True)

    assert msg == "v3.4.0: 摘要"


def test_build_message_without_deletions_is_first_line_only():
    assert sync_mod.build_push_commit_message("1.2.3", "s", []) == "v1.2.3: s"
