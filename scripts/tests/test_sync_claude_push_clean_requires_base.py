"""Tests for sync-claude-push.py --clean without reachable base（0.2.1-W3-155）。

問題：clean_stale_files 的三方保護 `if base_files and rel_posix not in
base_files` 依賴 `_list_base_files` 的回傳值非空才生效；`_list_base_files`
的空集合同時代表「base 確實無檔案」與「base 不可達」，base 不可達時保護
整條失效，所有「canonical 有而本地無」的檔案會被無差別刪除
（0.2.1-W3-130 實測：blog 無 sync-state 時會刪除 1991 個 canonical 檔案）。

修復：呼叫端（push 主流程）自行以 `_is_base_sha_reachable` 獨立判定 base
可達性（不依賴 `_list_base_files` 的空集合語意，也不改動其既有契約），
無法達時且帶 --clean 直接中止（fail-closed），與 0.2.1-W3-156 建立的
「不確定時 fail-closed」判準一致。

三情境（acceptance）：
  1. 無 base 帶 --clean → 中止（`_clean_requires_abort` 回 True）
  2. 無 base 不帶 --clean → 放行（`_clean_requires_abort` 回 False，既有行為不變）
  3. 有 base（可達）帶 --clean → 放行（`_clean_requires_abort` 回 False，不誤擋）
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-push.py"
_spec = importlib.util.spec_from_file_location("sync_claude_push", _SCRIPT)
assert _spec and _spec.loader
sync_mod = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_push"] = sync_mod
_spec.loader.exec_module(sync_mod)  # type: ignore[union-attr]


def _run(args: list[str], cwd: Path) -> None:
    subprocess.run(args, cwd=str(cwd), check=True, capture_output=True)


def _init_repo_with_commit(root: Path) -> str:
    """建立一個真實 git repo 並回傳其 HEAD commit SHA（模擬遠端 clone temp_dir）。"""
    _run(["git", "init", "-q"], root)
    _run(["git", "config", "user.email", "t@example.com"], root)
    _run(["git", "config", "user.name", "Test"], root)
    (root / "VERSION").write_text("1.0.0\n", encoding="utf-8")
    _run(["git", "add", "-A"], root)
    _run(["git", "commit", "-q", "-m", "init"], root)
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(root), check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def _write(base: Path, rel: str, content: str = "x\n") -> None:
    p = base / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


# ============================================================================
# _is_base_sha_reachable
# ============================================================================


class TestIsBaseShaReachable:
    def test_reachable_sha_true(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        sha = _init_repo_with_commit(repo)
        assert sync_mod._is_base_sha_reachable(repo, sha) is True

    def test_unreachable_sha_false(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_repo_with_commit(repo)
        fake_sha = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
        assert sync_mod._is_base_sha_reachable(repo, fake_sha) is False

    def test_none_sha_false(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_repo_with_commit(repo)
        assert sync_mod._is_base_sha_reachable(repo, None) is False

    def test_empty_sha_false(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_repo_with_commit(repo)
        assert sync_mod._is_base_sha_reachable(repo, "") is False


# ============================================================================
# _estimate_clean_deletion_scale
# ============================================================================


class TestEstimateCleanDeletionScale:
    def test_counts_files_in_each_tree(self, tmp_path):
        temp_dir = tmp_path / "remote"
        staging = tmp_path / "staging"
        temp_dir.mkdir()
        staging.mkdir()
        for name in ("a.md", "b.md", "c.md"):
            _write(temp_dir, name)
        _write(staging, "a.md")

        canonical_count, local_count = sync_mod._estimate_clean_deletion_scale(temp_dir, staging)
        assert canonical_count == 3
        assert local_count == 1

    def test_empty_trees_zero(self, tmp_path):
        temp_dir = tmp_path / "remote"
        staging = tmp_path / "staging"
        temp_dir.mkdir()
        staging.mkdir()

        assert sync_mod._estimate_clean_deletion_scale(temp_dir, staging) == (0, 0)

    def test_nested_directories_counted(self, tmp_path):
        temp_dir = tmp_path / "remote"
        staging = tmp_path / "staging"
        temp_dir.mkdir()
        staging.mkdir()
        _write(temp_dir, "a/b/c.md")
        _write(temp_dir, "a/d.md")

        canonical_count, _ = sync_mod._estimate_clean_deletion_scale(temp_dir, staging)
        assert canonical_count == 2


# ============================================================================
# _clean_requires_abort：純判斷，三情境
# ============================================================================


class TestCleanRequiresAbort:
    def test_scenario1_no_base_with_clean_aborts(self, tmp_path):
        """情境 1：無 base 帶 --clean → 中止。"""
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_repo_with_commit(repo)

        assert sync_mod._clean_requires_abort(True, None, repo) is True

    def test_scenario1_unreachable_base_with_clean_aborts(self, tmp_path):
        """情境 1 變體：base_sha 存在但在 temp_dir 找不到（如遠端已 rebase）→ 中止。"""
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_repo_with_commit(repo)

        fake_sha = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
        assert sync_mod._clean_requires_abort(True, fake_sha, repo) is True

    def test_scenario2_no_base_without_clean_proceeds(self, tmp_path):
        """情境 2：無 base 不帶 --clean → 放行（既有行為不變，acceptance 3）。"""
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_repo_with_commit(repo)

        assert sync_mod._clean_requires_abort(False, None, repo) is False

    def test_scenario3_reachable_base_with_clean_proceeds(self, tmp_path):
        """情境 3：有 base（可達）帶 --clean → 放行（不誤擋，acceptance 3）。"""
        repo = tmp_path / "repo"
        repo.mkdir()
        sha = _init_repo_with_commit(repo)

        assert sync_mod._clean_requires_abort(True, sha, repo) is False

    def test_reachable_base_without_clean_also_proceeds(self, tmp_path):
        """clean_mode=False 恆為 False，與 base 可達性無關（不影響既有未帶 --clean 流程）。"""
        repo = tmp_path / "repo"
        repo.mkdir()
        sha = _init_repo_with_commit(repo)

        assert sync_mod._clean_requires_abort(False, sha, repo) is False


# ============================================================================
# _abort_clean_without_base_protection：中止動作與訊息內容
# ============================================================================


class TestAbortCleanWithoutBaseProtection:
    def test_exits_with_code_1(self, tmp_path, capsys):
        temp_dir = tmp_path / "remote"
        staging = tmp_path / "staging"
        temp_dir.mkdir()
        staging.mkdir()
        for i in range(5):
            _write(temp_dir, f"file{i}.md")
        _write(staging, "file0.md")

        with pytest.raises(SystemExit) as exc_info:
            sync_mod._abort_clean_without_base_protection(temp_dir, staging, None)
        assert exc_info.value.code == 1

    def test_message_contains_deletion_scale_estimate(self, tmp_path, capsys):
        """acceptance 1：中止訊息輸出刪除規模預估（canonical 檔數減本地檔數）。"""
        temp_dir = tmp_path / "remote"
        staging = tmp_path / "staging"
        temp_dir.mkdir()
        staging.mkdir()
        for i in range(10):
            _write(temp_dir, f"file{i}.md")
        for i in range(3):
            _write(staging, f"file{i}.md")

        with pytest.raises(SystemExit):
            sync_mod._abort_clean_without_base_protection(temp_dir, staging, None)

        out = capsys.readouterr().out
        assert "canonical 檔案數: 10" in out
        assert "本地檔案數: 3" in out
        assert "預估刪除規模: 7" in out

    def test_message_explains_why_unsafe(self, tmp_path, capsys):
        """acceptance 2：訊息說明三方保護失效的原因，非只說被拒。"""
        temp_dir = tmp_path / "remote"
        staging = tmp_path / "staging"
        temp_dir.mkdir()
        staging.mkdir()

        with pytest.raises(SystemExit):
            sync_mod._abort_clean_without_base_protection(temp_dir, staging, None)

        out = capsys.readouterr().out
        assert "三方比對" in out
        assert "失效" in out

    def test_message_gives_next_step(self, tmp_path, capsys):
        """acceptance 2：訊息給出可行的下一步（先跑不帶 --clean 的 push 建立 base）。"""
        temp_dir = tmp_path / "remote"
        staging = tmp_path / "staging"
        temp_dir.mkdir()
        staging.mkdir()

        with pytest.raises(SystemExit):
            sync_mod._abort_clean_without_base_protection(temp_dir, staging, None)

        out = capsys.readouterr().out
        assert "下一步" in out
        assert "--clean" in out

    def test_message_distinguishes_no_sync_state_vs_unreachable_sha(self, tmp_path, capsys):
        """base_sha=None（無 sync-state）與 base_sha=不可達字串，訊息應分別說明。"""
        temp_dir = tmp_path / "remote"
        staging = tmp_path / "staging"
        temp_dir.mkdir()
        staging.mkdir()

        with pytest.raises(SystemExit):
            sync_mod._abort_clean_without_base_protection(temp_dir, staging, None)
        out_no_state = capsys.readouterr().out
        assert ".sync-state.json" in out_no_state

        with pytest.raises(SystemExit):
            sync_mod._abort_clean_without_base_protection(
                temp_dir, staging, "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
            )
        out_unreachable = capsys.readouterr().out
        assert "deadbeef" in out_unreachable
