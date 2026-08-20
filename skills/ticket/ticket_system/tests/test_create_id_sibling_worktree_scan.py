"""跨 worktree 並行 create 序號碰撞修復（配號鎖目錄級 + 掃描範圍不含 sibling worktree）。

問題背景
--------
`create_id_allocation_lock`（IMP-072 方案 A）的鎖檔落在 `tickets_dir` 內，
該目錄在 git worktree 環境下為各 worktree 獨立副本（每個 worktree 有自己
的 docs/work-logs 副本）。兩個 worktree 各自對自己的 tickets_dir 取鎖，
互不阻擋；`get_next_seq` 的掃描來源（本地 glob ∪ main/master ref）也看不
到「已在 sibling worktree 本地建立、尚未 merge 進 main」的 ticket 檔，
導致兩個 worktree 各自算出同一個「下一個可用序號」，配出同一 ID。

實測驗證（先於本測試手動重現，見 ticket Context Bundle）：在兩個以
`git worktree add` 建立的獨立 worktree 中，分別呼叫 get_next_seq 於同一
version/wave，即使兩次呼叫完全序列（無真正並行），只要其中一方尚未把
建立的 ticket 檔 merge 進 main，另一方仍會算出相同序號——問題不只是
「臨界區未序列化」，掃描範圍本身也需要涵蓋所有 sibling worktree。

修復設計（指導本測試斷言）
--------------------------
1. lib/ticket_builder.py 新增 list_ticket_files_from_sibling_worktrees()：
   列舉 `git worktree list --porcelain` 回報的所有 worktree 路徑（排除
   自身），各自 glob 其 tickets_dir，與本地 glob / main ref 三方取聯集。
2. get_next_seq / _scan_child_files_max_seq 併入此第三來源。
3. lib/file_lock.py 的 create_id_allocation_lock 改將鎖檔落在
   git-common-dir（所有 linked worktree 共用同一份），非 git 環境降級為
   原本 tickets_dir 內部落鎖。

測試策略
--------
Sociable Unit Test：以真實 `git worktree add` 建立實體 sibling worktree
（mock 無法真實重現跨 worktree 檔案系統可見性差異）。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from ticket_system.lib import ticket_builder
from ticket_system.lib.file_lock import CREATE_LOCK_FILENAME, _resolve_shared_lock_path
from ticket_system.lib.ticket_builder import get_next_child_seq, get_next_seq

try:
    from ticket_system.lib.ticket_builder import (
        list_ticket_files_from_sibling_worktrees,
    )
except ImportError:  # pragma: no cover - RED 階段預期路徑
    list_ticket_files_from_sibling_worktrees = None


# ---------------------------------------------------------------------------
# Helpers（沿用 test_create_id_scan_main_ref.py 慣例，本檔額外加 worktree 支援）
# ---------------------------------------------------------------------------


def _run_git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    )


def _tickets_dir(root: Path, version: str = "0.19.0") -> Path:
    parts = version.split(".")
    major = f"v{parts[0]}"
    minor = f"v{parts[0]}.{parts[1]}"
    return root / "docs" / "work-logs" / major / minor / f"v{version}" / "tickets"


def _write_ticket(tickets_dir: Path, ticket_id: str) -> Path:
    tickets_dir.mkdir(parents=True, exist_ok=True)
    path = tickets_dir / f"{ticket_id}.md"
    path.write_text(
        f"---\nid: {ticket_id}\ntitle: Test {ticket_id}\n"
        f"type: IMP\nstatus: pending\n---\n\n# Body\n",
        encoding="utf-8",
    )
    return path


def _init_git_repo(root: Path, default_branch: str = "main") -> None:
    root.mkdir(parents=True, exist_ok=True)
    _run_git(root, "init", "-q")
    _run_git(root, "checkout", "-q", "-b", default_branch)
    _run_git(root, "config", "user.email", "test@example.com")
    _run_git(root, "config", "user.name", "Test")
    (root / "README.md").write_text("init\n", encoding="utf-8")
    _run_git(root, "add", "README.md")
    _run_git(root, "commit", "-q", "-m", "init")


def _add_worktree(main_root: Path, wt_root: Path, branch: str) -> None:
    """在 main_root 上建立一個新的 linked worktree，簽出獨立分支 branch。"""
    _run_git(main_root, "worktree", "add", "-q", "-b", branch, str(wt_root), "HEAD")


def _patch_project_root(monkeypatch, root: Path) -> None:
    """將 ticket_builder / paths / file_lock 的 get_project_root 指向 root。

    三處各自透過 `from ... import get_project_root` 綁定了獨立的模組級
    名稱（Python import 語意），monkeypatch 必須逐一覆蓋，否則遺漏的模組
    仍會呼叫真實 get_project_root()（在測試環境下已被 conftest 的
    autouse fixture 導向另一個隔離 tmp 目錄，而非本測試建立的 root）。
    """
    monkeypatch.setattr(ticket_builder, "get_project_root", lambda: root, raising=False)
    import ticket_system.lib.file_lock as file_lock_mod
    import ticket_system.lib.paths as paths_mod

    monkeypatch.setattr(paths_mod, "get_project_root", lambda: root, raising=False)
    monkeypatch.setattr(file_lock_mod, "get_project_root", lambda: root, raising=False)


# ---------------------------------------------------------------------------
# AC1：list_ticket_files_from_sibling_worktrees 列舉其他 worktree 的 ticket 檔
# ---------------------------------------------------------------------------


class TestSiblingWorktreeScan:
    def test_lists_files_from_sibling_worktree(self, tmp_path, monkeypatch):
        """
        Given: main worktree 與一個 linked worktree（各自本地建立不同 ticket）
        When: 從 main worktree 呼叫 list_ticket_files_from_sibling_worktrees
        Then: 回傳清單含 sibling worktree 本地建立的 ticket 檔絕對路徑
        """
        main_root = tmp_path / "main"
        wt_root = tmp_path / "wt"
        _init_git_repo(main_root, "main")
        _add_worktree(main_root, wt_root, "feat-a")

        _write_ticket(_tickets_dir(wt_root), "0.19.0-W1-001")

        _patch_project_root(monkeypatch, main_root)
        files = list_ticket_files_from_sibling_worktrees("0.19.0")

        assert files is not None
        assert any(Path(f).name == "0.19.0-W1-001.md" for f in files), files

    def test_returns_empty_list_when_no_sibling_worktree(self, tmp_path, monkeypatch):
        """
        Given: 只有主 repo，沒有任何 linked worktree
        When: list_ticket_files_from_sibling_worktrees
        Then: 回傳空 list（非 None——git worktree list 成功執行只是沒有 sibling）
        """
        root = tmp_path / "repo"
        _init_git_repo(root, "main")

        _patch_project_root(monkeypatch, root)
        files = list_ticket_files_from_sibling_worktrees("0.19.0")

        assert files == []

    def test_degrades_to_none_when_not_git_repo(self, tmp_path, monkeypatch):
        """
        Given: 非 git 目錄
        When: list_ticket_files_from_sibling_worktrees
        Then: 回傳 None（降級，caller 不計入聯集，不阻斷 create）
        """
        root = tmp_path / "plain"
        root.mkdir()

        _patch_project_root(monkeypatch, root)
        assert list_ticket_files_from_sibling_worktrees("0.19.0") is None


# ---------------------------------------------------------------------------
# AC2：get_next_seq 併入 sibling worktree 掃描後不再跨 worktree 撞號
# ---------------------------------------------------------------------------


class TestNoCollisionAcrossWorktrees:
    def test_next_seq_sees_sibling_local_ticket(self, tmp_path, monkeypatch):
        """
        Given: sibling worktree 本地建立 W3-001（尚未 merge 進 main）
        When: 從主 worktree 呼叫 get_next_seq（不知道 sibling 存在前會回傳 1）
        Then: 回傳 2（涵蓋 sibling 本地檔，不再與 sibling 之後的 create 撞號）

        本測試直接重現 ticket Context Bundle 記錄的實測結果：修復前，
        主 worktree 呼叫 get_next_seq 對 sibling 已建立但未 merge 的 ticket
        完全無感知，回傳與 sibling 自己算出的值相同的序號。
        """
        main_root = tmp_path / "main"
        wt_root = tmp_path / "wt"
        _init_git_repo(main_root, "main")
        _add_worktree(main_root, wt_root, "feat-a")

        # sibling worktree 本地建立 001 並 commit 到自己的分支（不 merge 進 main）
        _write_ticket(_tickets_dir(wt_root, "0.2.1"), "0.2.1-W3-001")
        _run_git(wt_root, "add", "docs/work-logs/v0/v0.2/v0.2.1/tickets/0.2.1-W3-001.md")
        _run_git(wt_root, "commit", "-q", "-m", "create 001 in feat-a")

        _patch_project_root(monkeypatch, main_root)
        assert get_next_seq("0.2.1", 3) == 2

    def test_baseline_without_fix_would_collide(self, tmp_path, monkeypatch):
        """
        Given: 同上情境，但停用 sibling worktree 掃描（monkeypatch 回傳 None，
               模擬修復前行為）
        When: 從主 worktree 呼叫 get_next_seq
        Then: 回傳 1（與 sibling 自己算出的值相同 → 撞號重現，佐證本修復
              確實改變了行為，而非巧合通過）
        """
        main_root = tmp_path / "main"
        wt_root = tmp_path / "wt"
        _init_git_repo(main_root, "main")
        _add_worktree(main_root, wt_root, "feat-a")

        _write_ticket(_tickets_dir(wt_root, "0.2.1"), "0.2.1-W3-001")
        _run_git(wt_root, "add", "docs/work-logs/v0/v0.2/v0.2.1/tickets/0.2.1-W3-001.md")
        _run_git(wt_root, "commit", "-q", "-m", "create 001 in feat-a")

        _patch_project_root(monkeypatch, main_root)
        monkeypatch.setattr(
            ticket_builder, "list_ticket_files_from_sibling_worktrees", lambda v: None
        )
        assert get_next_seq("0.2.1", 3) == 1


# ---------------------------------------------------------------------------
# AC3：create lock 鎖檔位置改為跨 worktree 共用（git-common-dir）
# ---------------------------------------------------------------------------


class TestSharedLockPath:
    def test_lock_path_identical_across_worktrees(self, tmp_path, monkeypatch):
        """
        Given: main worktree 與 sibling worktree（同一 repo）
        When: 分別以各自的 get_project_root() 視角解析 create lock 路徑
        Then: 兩者解析出完全相同的絕對路徑（結構性保證跨 worktree 互斥：
              filelock 對同一路徑的互斥語意已由既有並行 create 測試覆蓋，
              此處只需證明路徑收斂到同一點）
        """
        main_root = tmp_path / "main"
        wt_root = tmp_path / "wt"
        _init_git_repo(main_root, "main")
        _add_worktree(main_root, wt_root, "feat-a")

        _patch_project_root(monkeypatch, main_root)
        from ticket_system.lib.paths import get_tickets_dir_under_root

        main_tickets_dir = get_tickets_dir_under_root(main_root, "0.2.1")
        path_from_main = _resolve_shared_lock_path(main_tickets_dir)

        _patch_project_root(monkeypatch, wt_root)
        wt_tickets_dir = get_tickets_dir_under_root(wt_root, "0.2.1")
        path_from_wt = _resolve_shared_lock_path(wt_tickets_dir)

        assert path_from_main == path_from_wt, (
            f"跨 worktree 解析出不同鎖檔路徑，無法達成互斥：\n"
            f"  main: {path_from_main}\n"
            f"  wt:   {path_from_wt}"
        )
        # 落在共用的 git-common-dir 下（非各自 worktree 內部）
        common_dir = _run_git(main_root, "rev-parse", "--git-common-dir").stdout.strip()
        assert str((main_root / common_dir).resolve()) in str(path_from_main)

    def test_falls_back_to_local_when_not_git_repo(self, tmp_path, monkeypatch):
        """
        Given: 非 git 目錄
        When: _resolve_shared_lock_path
        Then: 退回 tickets_dir 內部落鎖（修復前行為，既有測試
              test_lock_file_created_at_expected_path 依賴此路徑不回歸）
        """
        root = tmp_path / "plain"
        tickets_dir = root / "tickets"
        tickets_dir.mkdir(parents=True)

        _patch_project_root(monkeypatch, root)
        assert _resolve_shared_lock_path(tickets_dir) == tickets_dir / CREATE_LOCK_FILENAME


# ---------------------------------------------------------------------------
# AC4：子任務序號（get_next_child_seq）同樣涵蓋 sibling worktree
# ---------------------------------------------------------------------------


class TestChildSeqSiblingWorktree:
    def test_child_seq_sees_sibling_local_child_ticket(self, tmp_path, monkeypatch):
        """
        Given: 父票只存在於主 worktree（無 children 欄位）；sibling worktree
               本地建立子票 0.2.1-W3-001.1（尚未 merge 進 main）
        When: 從主 worktree 呼叫 get_next_child_seq("0.2.1-W3-001")
        Then: 回傳 2（涵蓋 sibling 本地子票，不與 sibling 之後的 create 撞號）
        """
        main_root = tmp_path / "main"
        wt_root = tmp_path / "wt"
        _init_git_repo(main_root, "main")
        _add_worktree(main_root, wt_root, "feat-a")

        # 主 worktree 本地有父票（無 children 欄位）
        parent_tickets_dir = _tickets_dir(main_root, "0.2.1")
        parent_tickets_dir.mkdir(parents=True, exist_ok=True)
        (parent_tickets_dir / "0.2.1-W3-001.md").write_text(
            "---\nid: 0.2.1-W3-001\ntitle: Parent\ntype: IMP\nstatus: pending\n"
            "children: []\n---\n\n# Body\n",
            encoding="utf-8",
        )

        # sibling worktree 本地建立子票並 commit 到自己的分支（不 merge 進 main）
        _write_ticket(_tickets_dir(wt_root, "0.2.1"), "0.2.1-W3-001.1")
        _run_git(wt_root, "add", "docs/work-logs/v0/v0.2/v0.2.1/tickets/0.2.1-W3-001.1.md")
        _run_git(wt_root, "commit", "-q", "-m", "create child 001.1 in feat-a")

        _patch_project_root(monkeypatch, main_root)
        assert get_next_child_seq("0.2.1-W3-001") == 2


# ---------------------------------------------------------------------------
# AC4：目標檔案已存在時，create 拒絕覆寫（落盤前最後一道防線）
# ---------------------------------------------------------------------------


class TestRefusesOverwriteOnCollision:
    def test_build_and_save_ticket_refuses_existing_path(self, tmp_path, monkeypatch):
        """
        Given: 目標 ticket 路徑已存在既有檔案（模擬 get_next_seq 計算出撞號候選值
               的殘跡——sibling worktree 掃描降級或極短時間窗下仍可能發生）
        When: _build_and_save_ticket 嘗試在同一路徑落盤
        Then: 拋出 FileExistsError，不靜默覆寫既有內容
        """
        from ticket_system.commands.create import _build_and_save_ticket

        root = tmp_path / "repo"
        _patch_project_root(monkeypatch, root)

        tickets_dir = _tickets_dir(root, "0.31.0")
        _write_ticket(tickets_dir, "0.31.0-W5-001")
        original_content = (tickets_dir / "0.31.0-W5-001.md").read_text(encoding="utf-8")

        config = {
            "ticket_id": "0.31.0-W5-001",
            "version": "0.31.0",
            "wave": 5,
            "title": "撞號候選（不應落盤）",
            "ticket_type": "IMP",
            "priority": "P1",
            "who": "thyme-python-developer",
            "what": "撞號候選（不應落盤）",
            "when": "測試",
            "where_layer": "Application",
            "why": "測試",
            "how_task_type": "Implementation",
            "how_strategy": "測試",
        }

        with pytest.raises(FileExistsError):
            _build_and_save_ticket("0.31.0", "0.31.0-W5-001", config)

        # 既有內容未被覆寫
        assert (tickets_dir / "0.31.0-W5-001.md").read_text(encoding="utf-8") == original_content
