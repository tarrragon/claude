"""Tests for sync-claude-pull.py full overlay 路徑對 should_exclude 的一致性
（0.2.1-W3-148）。

問題：三方合併路徑 `apply_upstream_delta` 已呼叫 `should_exclude` 過濾
`PUSH_ONLY_EXCLUDE_PATTERNS`（如 `project-integration/`，各 skill 的專案
落地層，per-project 案例/Hook 對齊/CLI 接線，設計上不跨專案同步——
0.2.1-W3-158 已查明雙向排除是設計意圖，非缺陷）。但 full overlay 路徑的
`cleanup_stale_files` 與 `sync_directory` 不呼叫 `should_exclude`，使
per-project 目錄在 full overlay 時被當 stale 刪除或被上游內容覆蓋。
screen_clock 的 `references/project-integration/` 7 檔即於 full overlay
被 `cleanup_stale_files` 刪除（0.2.1-W3-145 實證）。

修復：在兩個函式各自的走訪迴圈加入 `should_exclude` 早退——per-project
目錄整個跳過（不遞迴、不判定 stale、不覆蓋），與三方合併路徑行為對齊。

Not in scope（不改）：
- `should_exclude` 本身簽章（不加 `direction` 參數，雙向排除是正確設計）
- `sync_exclude_manifest.py`
- 三方合併路徑 `apply_upstream_delta`（行為完全不變，本測試檔不重複覆蓋）
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-pull.py"
_spec = importlib.util.spec_from_file_location(
    "sync_claude_pull_project_integration", _SCRIPT
)
assert _spec and _spec.loader
sync_mod = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_pull_project_integration"] = sync_mod
_spec.loader.exec_module(sync_mod)  # type: ignore[union-attr]


def _init_git_repo(root: Path) -> None:
    subprocess.run(["git", "init"], cwd=root, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=root, capture_output=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=root, capture_output=True)


def _git_add_commit(root: Path, *rel_paths: str) -> None:
    subprocess.run(["git", "add", *rel_paths], cwd=root, capture_output=True)
    subprocess.run(["git", "commit", "-m", "fixture"], cwd=root, capture_output=True)


def _make_claude(root: Path) -> Path:
    claude = root / ".claude"
    claude.mkdir()
    return claude


def _write(base: Path, rel: str, content: str = "x\n") -> Path:
    p = base / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


# ============================================================================
# cleanup_stale_files：project-integration 不被刪除
# ============================================================================


class TestCleanupStaleFilesProtectsProjectIntegration:
    def test_project_integration_files_not_deleted_when_absent_upstream(self, tmp_path):
        """screen_clock 情境重現：本地 project-integration 多檔，遠端無此目錄。"""
        root = tmp_path
        _init_git_repo(root)
        claude = _make_claude(root)
        files = [
            _write(
                claude,
                f"skills/wrap-decision/references/project-integration/file{i}.md",
            )
            for i in range(3)
        ]
        for f in files:
            _git_add_commit(
                root, str(f.relative_to(root)).replace("\\", "/")
            )

        remote_files: set = set()  # 遠端完全無此目錄（screen_clock 情境）
        removed, preserved = sync_mod.cleanup_stale_files(
            claude, remote_files, preserve=set(), project_root=root
        )

        for f in files:
            assert f.exists(), f"{f} 不應被刪除（project-integration 應完全跳過）"
        assert not any("project-integration" in r for r in removed)
        assert not any("project-integration" in p for p in preserved), (
            "不應移至 .sync-conflicts（應完全跳過，維持原路徑）"
        )

    def test_project_integration_untracked_files_also_protected(self, tmp_path):
        """未 git add 的 project-integration 檔（尚未 commit）同樣不受影響。"""
        root = tmp_path
        _init_git_repo(root)
        claude = _make_claude(root)
        f = _write(claude, "skills/x/references/project-integration/draft.md")
        # 不 git add → untracked，若走一般邏輯會被判定為真 stale 刪除

        remote_files: set = set()
        removed, preserved = sync_mod.cleanup_stale_files(
            claude, remote_files, preserve=set(), project_root=root
        )

        assert f.exists()
        assert not any("draft.md" in r for r in removed)
        assert not any("draft.md" in p for p in preserved)

    def test_project_integration_directory_itself_not_removed_as_empty(self, tmp_path):
        """project-integration/ 目錄本身（即使清空後看似空目錄）不被遞迴進入清理。"""
        root = tmp_path
        _init_git_repo(root)
        claude = _make_claude(root)
        pi_dir = claude / "skills" / "x" / "references" / "project-integration"
        pi_dir.mkdir(parents=True)
        (pi_dir / "keep.md").write_text("x", encoding="utf-8")

        remote_files: set = set()
        sync_mod.cleanup_stale_files(claude, remote_files, preserve=set(), project_root=root)

        assert pi_dir.exists()
        assert (pi_dir / "keep.md").exists()


class TestCleanupStaleFilesStillCleansRealStaleFiles:
    """acceptance 3：不可因過度過濾而讓真 stale 檔殘留（W3-132/133/139 不可回退）。"""

    def test_untracked_non_excluded_stale_file_still_deleted(self, tmp_path):
        root = tmp_path
        _init_git_repo(root)
        claude = _make_claude(root)
        stale = _write(claude, "runtime/temp.txt", "runtime garbage")
        # 不 git add → untracked，非 should_exclude 範圍

        remote_files: set = set()
        removed, preserved = sync_mod.cleanup_stale_files(
            claude, remote_files, preserve=set(), project_root=root
        )

        assert not stale.exists(), "真 stale 檔仍應被刪除（不可回退 W3-132/133/139）"
        assert any("temp.txt" in r for r in removed)
        assert not any("temp.txt" in p for p in preserved)

    def test_tracked_non_excluded_stale_file_still_moved_to_conflicts(self, tmp_path):
        """git 追蹤但非 should_exclude 範圍的本地獨有檔仍走既有 conflict 路徑（迴歸）。"""
        root = tmp_path
        _init_git_repo(root)
        claude = _make_claude(root)
        evolved = _write(claude, "error-patterns/PC-999-local.md", "local evolution")
        _git_add_commit(root, ".claude/error-patterns/PC-999-local.md")

        remote_files: set = set()
        removed, preserved = sync_mod.cleanup_stale_files(
            claude, remote_files, preserve=set(), project_root=root
        )

        assert not evolved.exists()
        assert any("PC-999-local.md" in p for p in preserved)
        assert not any("PC-999-local.md" in r for r in removed)

    def test_project_integration_and_real_stale_coexist(self, tmp_path):
        """混合情境：project-integration 保留，同批次的真 stale 檔仍清除。"""
        root = tmp_path
        _init_git_repo(root)
        claude = _make_claude(root)
        pi_file = _write(claude, "skills/x/references/project-integration/case.md")
        _git_add_commit(root, str(pi_file.relative_to(root)).replace("\\", "/"))
        stale = _write(claude, "runtime/junk.txt")

        remote_files: set = set()
        removed, preserved = sync_mod.cleanup_stale_files(
            claude, remote_files, preserve=set(), project_root=root
        )

        assert pi_file.exists(), "project-integration 應保留"
        assert not stale.exists(), "真 stale 檔仍應清除"
        assert any("junk.txt" in r for r in removed)


# ============================================================================
# sync_directory：project-integration 不被上游內容覆蓋
# ============================================================================


class TestSyncDirectoryProtectsProjectIntegration:
    def test_project_integration_not_overwritten_by_upstream_same_name_file(self, tmp_path):
        """canonical 若恰好也有同名 project-integration/ 內容，local 落地層不應被覆蓋。"""
        root = tmp_path
        claude = _make_claude(root)
        local_content = "screen_clock local content\n"
        local_file = _write(
            claude,
            "skills/x/references/project-integration/case.md",
            local_content,
        )

        upstream = tmp_path / "upstream"
        _write(upstream, "skills/x/references/project-integration/case.md", "canonical content\n")

        sync_mod.sync_directory(upstream, claude, preserve=set(), project_root=root)

        assert local_file.read_text(encoding="utf-8") == local_content, (
            "project-integration 內容不應被上游同名檔覆蓋"
        )

    def test_project_integration_upstream_only_file_not_copied_down(self, tmp_path):
        """upstream 若有 local 沒有的 project-integration 檔，也不應複製下來
        （per-project 層屬各專案自建，不應由 canonical 灌入）。"""
        root = tmp_path
        claude = _make_claude(root)

        upstream = tmp_path / "upstream"
        _write(upstream, "skills/x/references/project-integration/upstream_only.md")

        sync_mod.sync_directory(upstream, claude, preserve=set(), project_root=root)

        assert not (
            claude / "skills/x/references/project-integration/upstream_only.md"
        ).exists()

    def test_new_directory_tree_copytree_shortcut_still_filters_nested_excluded(self, tmp_path):
        """回歸 copytree 捷徑 bug：新目錄樹（本地完全不存在，觸發 shutil.copytree
        整批複製捷徑而非逐項迴圈）內巢狀混合正常檔與 project-integration 檔時，
        正常檔仍整批複製，project-integration 仍被過濾（不進入本地）。

        修復前：shutil.ignore_patterns 只按裸名稱比對 SKIP_DURING_SYNC，
        不會逐層呼叫 should_exclude，導致新樹整批複製時 project-integration/
        被一併帶入（此測試在改用 _make_should_exclude_ignore 前會失敗）。
        """
        root = tmp_path
        claude = _make_claude(root)  # 本地完全空的 .claude/，觸發 copytree 捷徑

        upstream = tmp_path / "upstream"
        _write(upstream, "skills/newskill/references/normal.md", "normal content\n")
        _write(
            upstream,
            "skills/newskill/references/project-integration/case.md",
            "should not appear locally\n",
        )
        _write(upstream, "skills/newskill/hooks/handler.py", "# hook\n")

        sync_mod.sync_directory(upstream, claude, preserve=set(), project_root=root)

        normal = claude / "skills/newskill/references/normal.md"
        hook = claude / "skills/newskill/hooks/handler.py"
        excluded = claude / "skills/newskill/references/project-integration/case.md"

        assert normal.exists() and normal.read_text(encoding="utf-8") == "normal content\n"
        assert hook.exists()
        assert not excluded.exists(), "project-integration 不應隨新目錄樹整批複製捷徑帶入"


class TestSyncDirectoryStillSyncsNormalFiles:
    """acceptance 3 對應：非 project-integration 的正常檔仍正確同步（迴歸）。"""

    def test_normal_file_still_synced_from_upstream(self, tmp_path):
        root = tmp_path
        claude = _make_claude(root)

        upstream = tmp_path / "upstream"
        _write(upstream, "rules/core/quality.md", "new upstream content\n")

        count = sync_mod.sync_directory(upstream, claude, preserve=set(), project_root=root)

        synced = claude / "rules/core/quality.md"
        assert synced.exists()
        assert synced.read_text(encoding="utf-8") == "new upstream content\n"
        assert count == 1

    def test_normal_file_overwritten_when_content_differs(self, tmp_path):
        root = tmp_path
        claude = _make_claude(root)
        existing = _write(claude, "rules/core/quality.md", "old content\n")

        upstream = tmp_path / "upstream"
        _write(upstream, "rules/core/quality.md", "updated content\n")

        sync_mod.sync_directory(upstream, claude, preserve=set(), project_root=root)

        assert existing.read_text(encoding="utf-8") == "updated content\n"


# ============================================================================
# 整合：full overlay（sync_directory + cleanup_stale_files 依序執行）
# ============================================================================


class TestFullOverlayIntegration:
    def test_screen_clock_scenario_end_to_end(self, tmp_path):
        """screen_clock 情境端到端重現：本地 project-integration 多檔，
        遠端該目錄少於本地（或不存在），完整 full overlay 兩步驟後本地檔全數保留，
        且真 stale 檔仍被清除。
        """
        root = tmp_path
        _init_git_repo(root)
        claude = _make_claude(root)

        # 本地 project-integration：7 檔（模擬 screen_clock 實測規模）
        pi_files = [
            _write(
                claude,
                f"skills/wrap-decision/references/project-integration/pm-rules-map-{i}.md",
            )
            for i in range(7)
        ]
        for f in pi_files:
            _git_add_commit(root, str(f.relative_to(root)).replace("\\", "/"))

        # 真 stale 檔：遠端已無，本地未追蹤
        stale = _write(claude, "obsolete/old_rule.md")

        # 正常檔：遠端有更新內容
        normal = _write(claude, "rules/core/normal.md", "old\n")
        _git_add_commit(root, str(normal.relative_to(root)).replace("\\", "/"))

        upstream = tmp_path / "upstream"
        _write(upstream, "rules/core/normal.md", "new\n")
        # upstream 完全無 project-integration/（screen_clock 實測情境）

        remote_files = sync_mod.collect_remote_files(upstream)

        # full overlay 步驟 1：sync_directory（複製/覆蓋）
        sync_mod.sync_directory(upstream, claude, preserve=set(), project_root=root)
        # full overlay 步驟 2：cleanup_stale_files（清理過時檔）
        removed, preserved = sync_mod.cleanup_stale_files(
            claude, remote_files, preserve=set(), project_root=root
        )

        for f in pi_files:
            assert f.exists(), f"{f} 應在 full overlay 後仍存在"
        assert not stale.exists(), "真 stale 檔應被清除"
        assert normal.read_text(encoding="utf-8") == "new\n", "正常檔仍應同步更新"
        assert not any("project-integration" in r for r in removed)
        assert not any("project-integration" in p for p in preserved)
