"""Tests for sync-claude-pull.py full-overlay git-delete awareness.

full overlay 復活前對 local-absent 上游檔查本地 git 史：若最後一次涉及該檔的
git 事件為刪除（D，未 re-add），視為「刻意刪除」，full overlay 跳過複製（不復活）；
否則照舊複製。preview 顯示 will_skip_resurrection（消除復活靜默）。

背景：commit e791a64d 的 sync-pull 從上游 claude.git full overlay 把 W10-049 已刪的
16 個 .claude/ root 孤兒全部復活。.sync-state.json 為 local-only（gitignored），
fresh clone 缺 base SHA → 首次 sync 走 full-overlay → 復活上游孤兒。M2 用本地 git 史
（隨 repo clone 而存在）作刪除 SSOT，survives fresh clone。
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

# sync-claude-pull.py 含連字符且 shebang 為 uv script，須以 importlib 載入
_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-pull.py"
_spec = importlib.util.spec_from_file_location("sync_claude_pull_overlay_git_delete", _SCRIPT)
assert _spec and _spec.loader
sync_mod = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_pull_overlay_git_delete"] = sync_mod
_spec.loader.exec_module(sync_mod)  # type: ignore[union-attr]


def _init_git_repo(root: Path) -> None:
    """在 root 初始化 git repo 並設定最小 identity。"""
    subprocess.run(["git", "init"], cwd=root, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=root, capture_output=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=root, capture_output=True)


def _git_add_commit(root: Path, *rel_paths: str) -> None:
    """git add + commit 指定相對路徑。"""
    subprocess.run(["git", "add", *rel_paths], cwd=root, capture_output=True)
    subprocess.run(["git", "commit", "-m", "fixture"], cwd=root, capture_output=True)


def _git_rm_commit(root: Path, *rel_paths: str) -> None:
    """git rm + commit 指定相對路徑（產生刪除事件）。"""
    subprocess.run(["git", "rm", *rel_paths], cwd=root, capture_output=True)
    subprocess.run(["git", "commit", "-m", "remove"], cwd=root, capture_output=True)


def _make_claude(root: Path) -> Path:
    """建立 root/.claude 並回傳。"""
    claude = root / ".claude"
    claude.mkdir()
    return claude


def _make_upstream(root: Path, claude_rel: str, content: str = "upstream") -> Path:
    """建立模擬上游 clone 目錄並在其下放一個 .claude 相對路徑檔。"""
    upstream = root / "fake_upstream"
    target = upstream / claude_rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return upstream


# ---------------------------------------------------------------------------
# _is_intentionally_deleted 判定函式（三情境）
# ---------------------------------------------------------------------------

def test_clean_delete_detected_as_intentional(tmp_path: Path) -> None:
    """clean-delete：曾 commit、後 git rm commit、磁碟 absent → 判定刻意刪除。"""
    root = tmp_path
    _init_git_repo(root)
    claude = _make_claude(root)
    orphan = claude / "orphan.md"
    orphan.write_text("legacy", encoding="utf-8")
    _git_add_commit(root, ".claude/orphan.md")
    _git_rm_commit(root, ".claude/orphan.md")

    assert not orphan.exists(), "fixture: 檔應已從磁碟移除"
    assert sync_mod._is_intentionally_deleted(".claude/orphan.md", root) is True


def test_delete_then_readd_not_intentional(tmp_path: Path) -> None:
    """delete-then-readd：刪後又 re-add commit、磁碟 present → 不判定刻意刪除。"""
    root = tmp_path
    _init_git_repo(root)
    claude = _make_claude(root)
    revived = claude / "revived.md"
    revived.write_text("v1", encoding="utf-8")
    _git_add_commit(root, ".claude/revived.md")
    _git_rm_commit(root, ".claude/revived.md")
    # re-add（git rm 可能移除空的 .claude 目錄，重建之）
    claude.mkdir(exist_ok=True)
    revived.write_text("v2", encoding="utf-8")
    _git_add_commit(root, ".claude/revived.md")

    assert revived.exists(), "fixture: re-add 後檔應在磁碟"
    assert sync_mod._is_intentionally_deleted(".claude/revived.md", root) is False


def test_never_existed_not_intentional(tmp_path: Path) -> None:
    """never-existed-locally：本地 git 史從無此檔、磁碟 absent → 不判定刻意刪除（真新檔）。"""
    root = tmp_path
    _init_git_repo(root)
    claude = _make_claude(root)
    keeper = claude / "keeper.md"
    keeper.write_text("keep", encoding="utf-8")
    _git_add_commit(root, ".claude/keeper.md")

    # newfile.md 從未在本地 git 史出現，磁碟亦無
    assert not (claude / "newfile.md").exists()
    assert sync_mod._is_intentionally_deleted(".claude/newfile.md", root) is False


# ---------------------------------------------------------------------------
# sync_directory 整合：full overlay 跳過復活
# ---------------------------------------------------------------------------

def test_overlay_skips_clean_deleted_resurrection(tmp_path: Path) -> None:
    """full overlay：clean-delete 檔（上游有、本地刻意刪除）不復活複製。"""
    root = tmp_path
    _init_git_repo(root)
    claude = _make_claude(root)
    orphan = claude / "orphan.md"
    orphan.write_text("legacy", encoding="utf-8")
    _git_add_commit(root, ".claude/orphan.md")
    _git_rm_commit(root, ".claude/orphan.md")

    upstream = _make_upstream(root, "orphan.md", "upstream-orphan")

    count = sync_mod.sync_directory(upstream, claude, project_root=root)

    assert not (claude / "orphan.md").exists(), "刻意刪除檔不應被 overlay 復活"
    assert count == 0, "無檔案被複製"


def test_overlay_copies_never_existed_newfile(tmp_path: Path) -> None:
    """full overlay：never-existed 上游新檔正常複製（不誤跳過）。"""
    root = tmp_path
    _init_git_repo(root)
    claude = _make_claude(root)
    keeper = claude / "keeper.md"
    keeper.write_text("keep", encoding="utf-8")
    _git_add_commit(root, ".claude/keeper.md")

    upstream = _make_upstream(root, "newfile.md", "brand-new")

    count = sync_mod.sync_directory(upstream, claude, project_root=root)

    assert (claude / "newfile.md").exists(), "真新檔應正常複製"
    assert (claude / "newfile.md").read_text(encoding="utf-8") == "brand-new"
    assert count == 1


def test_overlay_overwrites_existing_local(tmp_path: Path) -> None:
    """full overlay：本地存在檔（含 delete-then-readd）正常覆蓋，不受 git-delete 判定影響。"""
    root = tmp_path
    _init_git_repo(root)
    claude = _make_claude(root)
    present = claude / "present.md"
    present.write_text("local", encoding="utf-8")
    _git_add_commit(root, ".claude/present.md")

    upstream = _make_upstream(root, "present.md", "upstream-new")

    count = sync_mod.sync_directory(upstream, claude, project_root=root)

    assert (claude / "present.md").read_text(encoding="utf-8") == "upstream-new", "本地存在檔正常覆蓋"
    assert count == 1


# ---------------------------------------------------------------------------
# preview 補強：will_skip_resurrection
# ---------------------------------------------------------------------------

def test_preview_lists_will_skip_resurrection(tmp_path: Path) -> None:
    """preview 顯示將跳過復活的清單（消除復活靜默）。"""
    root = tmp_path
    _init_git_repo(root)
    claude = _make_claude(root)
    orphan = claude / "orphan.md"
    orphan.write_text("legacy", encoding="utf-8")
    _git_add_commit(root, ".claude/orphan.md")
    _git_rm_commit(root, ".claude/orphan.md")

    upstream = _make_upstream(root, "orphan.md", "upstream-orphan")
    # 另放一個 never-existed 新檔，確認不列入 skip
    newf = upstream / "newfile.md"
    newf.write_text("new", encoding="utf-8")

    result = sync_mod.preview_overlay_changes(
        upstream, claude, remote_files=set(), preserve=set(), project_root=root
    )
    # 回傳新增第三元素 will_skip_resurrection
    assert len(result) == 3, "preview 應回傳 (will_overwrite, will_delete, will_skip_resurrection)"
    will_skip = result[2]
    assert "orphan.md" in will_skip, "clean-delete 檔應列入 will_skip_resurrection"
    assert "newfile.md" not in will_skip, "never-existed 新檔不應列入 skip"
