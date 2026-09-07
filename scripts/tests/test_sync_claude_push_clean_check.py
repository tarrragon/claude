"""Tests for sync-claude-push.py clean-check (缺陷 T 根因修復，0.19.1-W1-030).

缺陷 T：push step 2 的乾淨檢查若把未進 .gitignore 的 local-only untracked 檔
（如 .zhtw-mcp-skip / .sync-conflicts）也視為「未提交變更」而 abort，使 push
無法進行。

M1 根因解：clean-check 改用 git status --porcelain 取工作區狀態，再以
sync_exclude_manifest.should_exclude 過濾掉 local-only / 憑證後判定。
過濾後仍有變更 → 真的需要先 commit（abort）；過濾後乾淨 → 放行。

回歸保證：
  - untracked local-only 檔（should_exclude 命中）不再造成 abort
  - 真正未 commit 的 tracked 程式碼變更仍被攔截
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-push.py"
_spec = importlib.util.spec_from_file_location("sync_claude_push", _SCRIPT)
assert _spec and _spec.loader
sync_mod = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_push"] = sync_mod
_spec.loader.exec_module(sync_mod)  # type: ignore[union-attr]


def _run(args: list[str], cwd: Path) -> None:
    subprocess.run(args, cwd=str(cwd), check=True, capture_output=True)


def _init_repo(root: Path) -> None:
    _run(["git", "init", "-q"], root)
    _run(["git", "config", "user.email", "t@example.com"], root)
    _run(["git", "config", "user.name", "Test"], root)
    claude = root / ".claude"
    claude.mkdir()
    (claude / "CLAUDE.md").write_text("base\n", encoding="utf-8")
    _run(["git", "add", "-A"], root)
    _run(["git", "commit", "-q", "-m", "init"], root)


def test_clean_check_passes_with_untracked_local_only(tmp_path):
    """untracked local-only 檔（.zhtw-mcp-skip）不應使 clean-check 失敗（缺陷 T 根因）。"""
    _init_repo(tmp_path)
    # 新增一個 should_exclude 命中的 untracked 檔
    (tmp_path / ".claude" / ".zhtw-mcp-skip").write_text("", encoding="utf-8")
    (tmp_path / ".claude" / "settings.local.json").write_text("{}", encoding="utf-8")

    assert sync_mod.ensure_committed(tmp_path) is True


def test_clean_check_fails_with_uncommitted_tracked_change(tmp_path):
    """真正未 commit 的 tracked 程式碼變更仍應使 clean-check 失敗。"""
    _init_repo(tmp_path)
    # 修改既有 tracked 檔但不 commit
    (tmp_path / ".claude" / "CLAUDE.md").write_text("modified\n", encoding="utf-8")

    assert sync_mod.ensure_committed(tmp_path) is False


def test_clean_check_fails_with_untracked_real_file(tmp_path):
    """非 local-only 的 untracked 檔（真正的新框架檔）仍應使 clean-check 失敗。"""
    _init_repo(tmp_path)
    (tmp_path / ".claude" / "new_rule.md").write_text("content\n", encoding="utf-8")

    assert sync_mod.ensure_committed(tmp_path) is False


def test_clean_check_passes_when_fully_committed(tmp_path):
    """全數 commit 時 clean-check 通過。"""
    _init_repo(tmp_path)
    assert sync_mod.ensure_committed(tmp_path) is True


# ============================================================================
# classify_orphan_candidate / 孤兒偵測三格分類（0.1.0-W3-044）
#
# 情境：canonical 有、推送方 tracked 樹（staging）無的路徑，可能是三種成因
# 之一——(1) 推送方確實刪除過（true_orphan，可 --clean）、(2) 推送方從未
# 擁有過，屬他方貢獻（other_contribution，不可清）、(3) 本地磁碟存在但未被
# git 追蹤，如被 .gitignore 排除（untracked_local，不可清）。三者在單純比對
# tracked 樹的視角下完全同形，須分別以磁碟存在性 + git 歷史查詢區分。
# ============================================================================


def _add_file_commit_then_delete(root: Path, rel: str) -> None:
    """在 root 這個 git repo 內新增一個檔案、commit，再刪除並 commit，
    製造出「git 歷史確實有過刪除記錄」的真孤兒情境。"""
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x\n", encoding="utf-8")
    _run(["git", "add", "-A"], root)
    _run(["git", "commit", "-q", "-m", "add"], root)
    path.unlink()
    _run(["git", "add", "-A"], root)
    _run(["git", "commit", "-q", "-m", "delete"], root)


def test_classify_orphan_true_when_local_history_has_deletion(tmp_path):
    """acceptance 2：本專案 git 歷史確有刪除記錄的路徑，分類為 true_orphan。"""
    _init_repo(tmp_path)
    rel = ".claude/skills/example/removed.md"
    _add_file_commit_then_delete(tmp_path, rel)

    classification = sync_mod.classify_orphan_candidate(
        Path("skills/example/removed.md"), tmp_path / ".claude", tmp_path,
    )

    assert classification == sync_mod._ORPHAN_TRUE


def test_classify_orphan_other_contribution_when_never_owned(tmp_path):
    """acceptance 1：本專案 git 歷史從未擁有過的路徑（磁碟也無），分類為
    other_contribution，不列為孤兒。"""
    _init_repo(tmp_path)

    classification = sync_mod.classify_orphan_candidate(
        Path("scripts/uv.lock"), tmp_path / ".claude", tmp_path,
    )

    assert classification == sync_mod._ORPHAN_OTHER_CONTRIBUTION


def test_classify_orphan_untracked_local_when_present_on_disk(tmp_path):
    """acceptance 4：磁碟上存在但未被 git 追蹤的路徑（如被 .gitignore 排除），
    分類為 untracked_local，判別排在歷史查詢之前（即使歷史查詢會回零，
    仍應歸類為 untracked_local 而非 other_contribution）。"""
    _init_repo(tmp_path)
    claude_dir = tmp_path / ".claude"
    untracked = claude_dir / "scripts" / "uv.lock"
    untracked.parent.mkdir(parents=True, exist_ok=True)
    untracked.write_text("locked\n", encoding="utf-8")
    # 刻意不 git add：磁碟存在但未追蹤

    classification = sync_mod.classify_orphan_candidate(
        Path("scripts/uv.lock"), claude_dir, tmp_path,
    )

    assert classification == sync_mod._ORPHAN_UNTRACKED_LOCAL


def test_classify_orphan_degrades_to_true_orphan_without_context(tmp_path):
    """claude_dir / project_root 皆為 None 時降級為舊行為（一律 true_orphan），
    維持既有無此二參數呼叫端的行為。"""
    classification = sync_mod.classify_orphan_candidate(
        Path("anything.md"), None, None,
    )

    assert classification == sync_mod._ORPHAN_TRUE


# ---------- clean_stale_files / detect_uncleaned_deletions 整合三格分類 ----------


def _make_remote_and_staging(tmp_path: Path) -> tuple[Path, Path]:
    temp_dir = tmp_path / "remote_clone"
    staging = tmp_path / "staging"
    temp_dir.mkdir()
    staging.mkdir()
    return temp_dir, staging


def test_clean_stale_files_skips_other_contribution(tmp_path):
    """acceptance 1：--clean 模式下，他方貢獻（本地歷史從未擁有）不被刪除。"""
    project_root = tmp_path / "project"
    project_root.mkdir()
    claude_dir = project_root / ".claude"
    _init_repo(project_root)
    temp_dir, staging = _make_remote_and_staging(tmp_path)
    # canonical 有 uv.lock，staging（本地 tracked 樹）與磁碟皆無
    (temp_dir / "scripts").mkdir(parents=True)
    (temp_dir / "scripts" / "uv.lock").write_text("locked\n", encoding="utf-8")

    deleted = sync_mod.clean_stale_files(
        temp_dir, staging, claude_dir=claude_dir, project_root=project_root,
    )

    assert deleted == 0
    assert (temp_dir / "scripts" / "uv.lock").exists()


def test_clean_stale_files_still_deletes_true_orphan(tmp_path):
    """acceptance 2：--clean 模式下，本專案確有刪除記錄的路徑仍正常刪除。"""
    project_root = tmp_path / "project"
    project_root.mkdir()
    claude_dir = project_root / ".claude"
    _init_repo(project_root)
    _add_file_commit_then_delete(project_root, ".claude/hooks/removed.py")
    temp_dir, staging = _make_remote_and_staging(tmp_path)
    (temp_dir / "hooks").mkdir(parents=True)
    (temp_dir / "hooks" / "removed.py").write_text("x\n", encoding="utf-8")

    deleted = sync_mod.clean_stale_files(
        temp_dir, staging, claude_dir=claude_dir, project_root=project_root,
    )

    # deleted 含檔案本身與刪除後淨空的 hooks/ 目錄（既有行為，非本票變更範圍）
    assert deleted == 2
    assert not (temp_dir / "hooks" / "removed.py").exists()


def test_clean_stale_files_skips_untracked_local(tmp_path):
    """acceptance 4：磁碟存在但未追蹤的路徑不被刪除（第三格）。"""
    project_root = tmp_path / "project"
    project_root.mkdir()
    claude_dir = project_root / ".claude"
    _init_repo(project_root)
    untracked = claude_dir / "scripts" / "uv.lock"
    untracked.parent.mkdir(parents=True, exist_ok=True)
    untracked.write_text("locked\n", encoding="utf-8")
    temp_dir, staging = _make_remote_and_staging(tmp_path)
    (temp_dir / "scripts").mkdir(parents=True)
    (temp_dir / "scripts" / "uv.lock").write_text("locked\n", encoding="utf-8")

    deleted = sync_mod.clean_stale_files(
        temp_dir, staging, claude_dir=claude_dir, project_root=project_root,
    )

    assert deleted == 0
    assert (temp_dir / "scripts" / "uv.lock").exists()


def test_clean_stale_files_without_context_preserves_legacy_behavior(tmp_path):
    """負向錨點：不傳 claude_dir / project_root 時維持舊行為（一律視為 true_orphan
    並刪除），確認既有呼叫端（未升級的測試）行為不變。"""
    temp_dir, staging = _make_remote_and_staging(tmp_path)
    (temp_dir / "stale.md").write_text("x\n", encoding="utf-8")

    deleted = sync_mod.clean_stale_files(temp_dir, staging)

    assert deleted == 1
    assert not (temp_dir / "stale.md").exists()


def test_detect_uncleaned_deletions_excludes_other_contribution(tmp_path):
    """acceptance 1：soft 警告清單不含他方貢獻（本地歷史從未擁有）的路徑。"""
    project_root = tmp_path / "project"
    project_root.mkdir()
    claude_dir = project_root / ".claude"
    _init_repo(project_root)
    temp_dir, staging = _make_remote_and_staging(tmp_path)
    (temp_dir / "scripts").mkdir(parents=True)
    (temp_dir / "scripts" / "uv.lock").write_text("locked\n", encoding="utf-8")

    orphans = sync_mod.detect_uncleaned_deletions(
        temp_dir, staging, claude_dir=claude_dir, project_root=project_root,
    )

    assert orphans == []


def test_detect_uncleaned_deletions_includes_true_orphan(tmp_path):
    """acceptance 2：soft 警告清單仍含本專案確有刪除記錄的真孤兒。"""
    project_root = tmp_path / "project"
    project_root.mkdir()
    claude_dir = project_root / ".claude"
    _init_repo(project_root)
    _add_file_commit_then_delete(project_root, ".claude/hooks/removed.py")
    temp_dir, staging = _make_remote_and_staging(tmp_path)
    (temp_dir / "hooks").mkdir(parents=True)
    (temp_dir / "hooks" / "removed.py").write_text("x\n", encoding="utf-8")

    orphans = sync_mod.detect_uncleaned_deletions(
        temp_dir, staging, claude_dir=claude_dir, project_root=project_root,
    )

    assert orphans == ["hooks/removed.py"]


def test_detect_uncleaned_deletions_excludes_untracked_local(tmp_path):
    """acceptance 4：soft 警告清單不含磁碟存在但未追蹤的路徑（第三格）。"""
    project_root = tmp_path / "project"
    project_root.mkdir()
    claude_dir = project_root / ".claude"
    _init_repo(project_root)
    untracked = claude_dir / "scripts" / "uv.lock"
    untracked.parent.mkdir(parents=True, exist_ok=True)
    untracked.write_text("locked\n", encoding="utf-8")
    temp_dir, staging = _make_remote_and_staging(tmp_path)
    (temp_dir / "scripts").mkdir(parents=True)
    (temp_dir / "scripts" / "uv.lock").write_text("locked\n", encoding="utf-8")

    orphans = sync_mod.detect_uncleaned_deletions(
        temp_dir, staging, claude_dir=claude_dir, project_root=project_root,
    )

    assert orphans == []
