"""Phase 2 RED — ticket create ID 掃描改用 main ref（0.19.0-W1-037 / B3 方案）。

來源 Ticket: 0.19.0-W1-037（IMP）
依據 ANA: 0.19.0-W1-035（worktree stale base 分叉連鎖問題，症狀 3）

問題背景
--------
`ticket create` 分配新 ID 時，序號掃描完全基於 cwd 本地檔案系統，
worktree 從 stale base 分叉時掃不到 main 上已存在的新 ticket，造成 ID 碰撞。

B3 方案
-------
`get_next_seq` / `_scan_child_files_max_seq` 改為「本地工作樹 glob ∪
`git ls-tree -r <ref>` 路徑列舉」取聯集。新增輔助函式
`list_ticket_files_from_main(version, ref)`：先試 main、失敗試 master、
皆失敗回 None；timeout / 非 git 環境亦回 None。聯集 + 失敗 fallback
確保非 git / 無 main 環境降級為現行純本地掃描行為。

測試策略
--------
Sociable Unit Test：採真實 tmp git repo 重現 stale base（mock 無法真實
重現 worktree base 漂移）；subprocess timeout 情境用 mock。
被測函式本身、Path glob、seq 解析邏輯不 mock。

RED 階段預期
-----------
本檔測試將因 `list_ticket_files_from_main` 尚未實作、`get_next_seq` /
`_scan_child_files_max_seq` 尚未改造為聯集邏輯而失敗，符合 TDD Red。
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from ticket_system.lib import ticket_builder
from ticket_system.lib.ticket_builder import get_next_seq, get_next_child_seq

# 新輔助函式：B3 方案新增，RED 階段尚未實作 → ImportError 屬預期
try:
    from ticket_system.lib.ticket_builder import list_ticket_files_from_main
except ImportError:  # pragma: no cover - RED 階段預期路徑
    list_ticket_files_from_main = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_git(cwd: Path, *args: str) -> None:
    """在指定目錄執行 git 命令（測試環境設置用，失敗即拋出）。"""
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )


def _tickets_dir(root: Path, version: str = "0.19.0") -> Path:
    """回傳三層階層 tickets 目錄路徑（對齊 get_tickets_dir 規則）。"""
    parts = version.split(".")
    major = f"v{parts[0]}"
    minor = f"v{parts[0]}.{parts[1]}"
    return root / "docs" / "work-logs" / major / minor / f"v{version}" / "tickets"


def _write_ticket(tickets_dir: Path, ticket_id: str) -> Path:
    """寫入最小化 ticket .md 檔（掃描只看檔名，內容僅需可解析）。"""
    tickets_dir.mkdir(parents=True, exist_ok=True)
    path = tickets_dir / f"{ticket_id}.md"
    path.write_text(
        f"---\nid: {ticket_id}\ntitle: Test {ticket_id}\n"
        f"type: IMP\nstatus: pending\n---\n\n# Body\n",
        encoding="utf-8",
    )
    return path


def _init_git_repo(root: Path, default_branch: str = "main") -> None:
    """在 root 初始化 git repo 並設定預設分支名。"""
    root.mkdir(parents=True, exist_ok=True)
    _run_git(root, "init", "-q")
    _run_git(root, "checkout", "-q", "-b", default_branch)
    _run_git(root, "config", "user.email", "test@example.com")
    _run_git(root, "config", "user.name", "Test")
    # 初始空 commit，確保分支存在
    (root / "README.md").write_text("init\n", encoding="utf-8")
    _run_git(root, "add", "README.md")
    _run_git(root, "commit", "-q", "-m", "init")


def _commit_tickets(root: Path, version: str, ticket_ids: list[str]) -> None:
    """將指定 ticket 檔寫入並 commit 到當前分支。"""
    tickets_dir = _tickets_dir(root, version)
    for tid in ticket_ids:
        _write_ticket(tickets_dir, tid)
    _run_git(root, "add", "-A")
    _run_git(root, "commit", "-q", "-m", f"add tickets {ticket_ids}")


def _patch_project_root(monkeypatch, root: Path) -> None:
    """將 ticket_builder 與 paths 的 get_project_root 指向 root。"""
    monkeypatch.setattr(
        ticket_builder, "get_project_root", lambda: root, raising=False
    )
    try:
        import ticket_system.lib.paths as paths_mod

        monkeypatch.setattr(
            paths_mod, "get_project_root", lambda: root, raising=False
        )
    except ImportError:  # pragma: no cover
        pass


# ---------------------------------------------------------------------------
# AC1：main 存在時，get_next_seq = max(本地 seq, main ref seq) + 1
# ---------------------------------------------------------------------------


class TestMainRefUnion:
    """AC1：get_next_seq 回傳本地與 main ref 的聯集 max + 1。"""

    def test_seq_is_union_of_local_and_main(self, tmp_path, monkeypatch):
        """
        Given: main 已 commit W1-005；本地工作樹另有未涵蓋於 main 的 W1-003
        前置驗證: tmp 為有效 git repo、main ref 存在、W1-005 已 commit
        When: get_next_seq("0.19.0", 1)
        Then: 回傳 6（max(main=5, local=3) + 1）
        """
        root = tmp_path / "repo"
        _init_git_repo(root, "main")
        _commit_tickets(root, "0.19.0", ["0.19.0-W1-005"])

        # 前置驗證：main ref 存在
        head = subprocess.run(
            ["git", "rev-parse", "--verify", "main"],
            cwd=root, capture_output=True, text=True,
        )
        assert head.returncode == 0, "前置條件失敗：main ref 不存在"

        # 本地工作樹額外加入未 commit 的較小 seq 檔
        _write_ticket(_tickets_dir(root), "0.19.0-W1-003")

        _patch_project_root(monkeypatch, root)
        assert get_next_seq("0.19.0", 1) == 6

    def test_main_only_when_no_local(self, tmp_path, monkeypatch):
        """
        Given: main 有 W1-008；本地工作樹該 wave 無任何檔
        When: get_next_seq("0.19.0", 1)
        Then: 回傳 9（僅 main ref 結果）
        """
        root = tmp_path / "repo"
        _init_git_repo(root, "main")
        _commit_tickets(root, "0.19.0", ["0.19.0-W1-008"])

        # 模擬 stale 工作樹：移除工作樹中的 ticket 檔（main ref 仍保有）
        (_tickets_dir(root) / "0.19.0-W1-008.md").unlink()

        _patch_project_root(monkeypatch, root)
        assert get_next_seq("0.19.0", 1) == 9


# ---------------------------------------------------------------------------
# AC2：main 不存在 / 非 git 環境 → fallback 純本地掃描（含 master fallback）
# ---------------------------------------------------------------------------


class TestMainRefAbsent:
    """AC2：main 不存在或非 git 時 fallback 本地掃描，不阻斷 create。"""

    def test_fallback_to_local_when_main_missing(self, tmp_path, monkeypatch):
        """
        Given: git repo 預設分支為 develop（無 main、無 master），本地有 W1-002
        When: get_next_seq("0.19.0", 1)
        Then: 回傳 3（純本地掃描），不拋例外
        """
        root = tmp_path / "repo"
        _init_git_repo(root, "develop")
        _commit_tickets(root, "0.19.0", ["0.19.0-W1-002"])

        # 前置驗證：main 不存在
        r = subprocess.run(
            ["git", "rev-parse", "--verify", "main"],
            cwd=root, capture_output=True, text=True,
        )
        assert r.returncode != 0, "前置條件失敗：main 不該存在"

        _patch_project_root(monkeypatch, root)
        assert get_next_seq("0.19.0", 1) == 3

    def test_fallback_to_master_when_main_missing(self, tmp_path, monkeypatch):
        """
        Given: git repo 預設分支為 master 並 commit W1-007，無 main ref
        When: get_next_seq("0.19.0", 1)
        Then: 嘗試 main 失敗後改試 master，回傳 8（PM 決策：main→master 依序）
        """
        root = tmp_path / "repo"
        _init_git_repo(root, "master")
        _commit_tickets(root, "0.19.0", ["0.19.0-W1-007"])

        # 前置驗證：master 存在、main 不存在
        assert subprocess.run(
            ["git", "rev-parse", "--verify", "master"],
            cwd=root, capture_output=True, text=True,
        ).returncode == 0
        assert subprocess.run(
            ["git", "rev-parse", "--verify", "main"],
            cwd=root, capture_output=True, text=True,
        ).returncode != 0

        # 模擬 stale 工作樹：移除工作樹檔，迫使結果只能來自 master ref
        (_tickets_dir(root) / "0.19.0-W1-007.md").unlink()

        _patch_project_root(monkeypatch, root)
        assert get_next_seq("0.19.0", 1) == 8

    def test_fallback_to_local_when_not_git_repo(self, tmp_path, monkeypatch):
        """
        Given: 非 git 目錄（無 .git），本地有 W1-004
        When: get_next_seq("0.19.0", 1)
        Then: 回傳 5（純本地掃描），不拋例外
        """
        root = tmp_path / "plain"
        tickets_dir = _tickets_dir(root)
        _write_ticket(tickets_dir, "0.19.0-W1-004")

        # 前置驗證：非 git repo
        assert not (root / ".git").exists()

        _patch_project_root(monkeypatch, root)
        assert get_next_seq("0.19.0", 1) == 5


# ---------------------------------------------------------------------------
# AC3：detached HEAD 下 main ref 仍可解析
# ---------------------------------------------------------------------------


class TestDetachedHead:
    """AC3：detached HEAD 不影響 main ref 名查找。"""

    def test_main_ref_resolved_in_detached_head(self, tmp_path, monkeypatch):
        """
        Given: git repo 處 detached HEAD，main 仍存在並有 W1-006
        前置驗證: HEAD 為 detached、main ref 仍存在
        When: get_next_seq("0.19.0", 1)
        Then: 回傳 7（git ls-tree 以 ref 名查找，與 HEAD 狀態無關）
        """
        root = tmp_path / "repo"
        _init_git_repo(root, "main")
        _commit_tickets(root, "0.19.0", ["0.19.0-W1-006"])

        # 進入 detached HEAD
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root, capture_output=True, text=True,
        ).stdout.strip()
        _run_git(root, "checkout", "-q", sha)

        # 前置驗證：HEAD detached、main 仍存在
        symref = subprocess.run(
            ["git", "symbolic-ref", "-q", "HEAD"],
            cwd=root, capture_output=True, text=True,
        )
        assert symref.returncode != 0, "前置條件失敗：HEAD 應為 detached"
        assert subprocess.run(
            ["git", "rev-parse", "--verify", "main"],
            cwd=root, capture_output=True, text=True,
        ).returncode == 0

        _patch_project_root(monkeypatch, root)
        assert get_next_seq("0.19.0", 1) == 7


# ---------------------------------------------------------------------------
# AC4：未 commit 的本地新 ticket 仍被本地 glob 涵蓋（聯集不遺漏）
# ---------------------------------------------------------------------------


class TestUncommittedLocal:
    """AC4：聯集涵蓋未 commit 的本地檔，不遺漏。"""

    def test_uncommitted_local_ticket_included(self, tmp_path, monkeypatch):
        """
        Given: main 有 W1-002（已 commit）；本地新建 W1-009 尚未 commit
        When: get_next_seq("0.19.0", 1)
        Then: 回傳 10（聯集 = max(main=2, local=9) + 1，涵蓋未 commit 檔）
        """
        root = tmp_path / "repo"
        _init_git_repo(root, "main")
        _commit_tickets(root, "0.19.0", ["0.19.0-W1-002"])

        # 本地新建較大 seq 檔，刻意不 commit
        _write_ticket(_tickets_dir(root), "0.19.0-W1-009")
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root, capture_output=True, text=True,
        ).stdout
        assert "0.19.0-W1-009.md" in status, "前置條件失敗：W1-009 應為未 commit"

        _patch_project_root(monkeypatch, root)
        assert get_next_seq("0.19.0", 1) == 10


# ---------------------------------------------------------------------------
# AC5：stale base worktree 重現 — create 分配 ID 不與 main 既有 ticket 碰撞
# ---------------------------------------------------------------------------


class TestStaleBaseReproduction:
    """AC5：W1-035 stale base 連鎖問題重現，B3 修復後不再碰撞。"""

    def test_no_id_collision_in_stale_base_worktree(self, tmp_path, monkeypatch):
        """
        Given: main 含 W1-031/W1-032/W1-033（後續 commit 加入），
               worktree 工作樹為 stale base（只見到 W1-031，缺 W1-032/W1-033）
        前置驗證: main ref 含三檔；stale 工作樹只有 W1-031
        When: 在 stale 工作樹呼叫 get_next_seq("0.19.0", 1)
        Then: 回傳 34（涵蓋 main 上 W1-033，不碰撞既有 ID）
        """
        root = tmp_path / "repo"
        _init_git_repo(root, "main")
        # 第一個 commit（stale base 將停在此）
        _commit_tickets(root, "0.19.0", ["0.19.0-W1-031"])
        # 後續 commit 加入新 ticket（stale 工作樹不會看到）
        _commit_tickets(root, "0.19.0", ["0.19.0-W1-032", "0.19.0-W1-033"])

        # 模擬 stale 工作樹：移除 W1-032/W1-033 的工作樹檔
        # （main ref 仍保有，但 stale 工作樹掃不到）
        tickets_dir = _tickets_dir(root)
        (tickets_dir / "0.19.0-W1-032.md").unlink()
        (tickets_dir / "0.19.0-W1-033.md").unlink()

        # 前置驗證：工作樹只剩 W1-031
        local_files = sorted(p.name for p in tickets_dir.glob("*-W1-*.md"))
        assert local_files == ["0.19.0-W1-031.md"], (
            f"前置條件失敗：stale 工作樹應只有 W1-031，實際 {local_files}"
        )
        # 前置驗證：main ref 含全部三檔
        ls_tree = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", "main"],
            cwd=root, capture_output=True, text=True,
        ).stdout
        assert "0.19.0-W1-033.md" in ls_tree, "前置條件失敗：main 應含 W1-033"

        _patch_project_root(monkeypatch, root)
        # 純本地掃描會回傳 32（碰撞 W1-032）；B3 聯集應回傳 34
        assert get_next_seq("0.19.0", 1) == 34


# ---------------------------------------------------------------------------
# AC6：git ls-tree 逾時觸發 fallback，create 不被卡住
# ---------------------------------------------------------------------------


class TestLsTreeTimeout:
    """AC6：git ls-tree 逾時時 fallback 本地掃描。"""

    def test_fallback_when_ls_tree_timeout(self, tmp_path, monkeypatch):
        """
        Given: git ls-tree 逾時（mock subprocess.run 拋 TimeoutExpired）；
               本地有 W1-005
        When: get_next_seq("0.19.0", 1)
        Then: 回傳 6（逾時後 fallback 純本地掃描），不卡住、不拋例外
        """
        root = tmp_path / "repo"
        _init_git_repo(root, "main")
        _commit_tickets(root, "0.19.0", ["0.19.0-W1-005"])

        _patch_project_root(monkeypatch, root)

        # mock subprocess.run 逾時。
        # GREEN 實作須以 `import subprocess` 後呼叫 `subprocess.run`，
        # 故 patch 全域 subprocess.run 即可覆蓋（無論在哪個模組呼叫）。
        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd=["git"], timeout=5),
        ):
            result = get_next_seq("0.19.0", 1)

        assert result == 6


# ---------------------------------------------------------------------------
# AC7：子 ticket 序號同樣涵蓋 main ref 上的子 ticket 檔
# ---------------------------------------------------------------------------


class TestChildSeqMainRef:
    """AC7：get_next_child_seq 聯集涵蓋 main ref 上的子 ticket。"""

    def test_child_seq_union_with_main(self, tmp_path, monkeypatch):
        """
        Given: main 有父 W1-001 + 子 ticket W1-001.3；
               本地工作樹另有未涵蓋的 W1-001.1
        前置驗證: main ref 含 W1-001.3.md
        When: get_next_child_seq("0.19.0-W1-001")
        Then: 回傳 4（max(main 子 seq=3, local 子 seq=1) + 1）
        """
        root = tmp_path / "repo"
        _init_git_repo(root, "main")
        _commit_tickets(
            root, "0.19.0",
            ["0.19.0-W1-001", "0.19.0-W1-001.3"],
        )

        ls_tree = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", "main"],
            cwd=root, capture_output=True, text=True,
        ).stdout
        assert "0.19.0-W1-001.3.md" in ls_tree, "前置條件失敗：main 應含子 ticket"

        # 本地額外加入較小子 seq 檔
        _write_ticket(_tickets_dir(root), "0.19.0-W1-001.1")

        _patch_project_root(monkeypatch, root)
        assert get_next_child_seq("0.19.0-W1-001") == 4

    def test_child_seq_main_only(self, tmp_path, monkeypatch):
        """
        Given: main 有父 W1-001 + 子 ticket W1-001.2；
               本地工作樹無任何子檔（stale）
        When: get_next_child_seq("0.19.0-W1-001")
        Then: 回傳 3（僅 main ref 子 seq=2 + 1）
        """
        root = tmp_path / "repo"
        _init_git_repo(root, "main")
        _commit_tickets(
            root, "0.19.0",
            ["0.19.0-W1-001", "0.19.0-W1-001.2"],
        )

        # 模擬 stale 工作樹：移除子 ticket 工作樹檔
        (_tickets_dir(root) / "0.19.0-W1-001.2.md").unlink()

        _patch_project_root(monkeypatch, root)
        assert get_next_child_seq("0.19.0-W1-001") == 3


# ---------------------------------------------------------------------------
# 新輔助函式契約：list_ticket_files_from_main
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    list_ticket_files_from_main is None,
    reason="RED 階段：list_ticket_files_from_main 尚未實作",
)
class TestListTicketFilesFromMain:
    """新輔助函式契約：成功回 basename 清單，失敗回 None。"""

    def test_returns_basenames_on_success(self, tmp_path, monkeypatch):
        """
        Given: main 有 W1-001、W1-002 兩個 ticket 檔
        When: list_ticket_files_from_main("0.19.0")
        Then: 回傳含兩檔 basename 的清單
        """
        root = tmp_path / "repo"
        _init_git_repo(root, "main")
        _commit_tickets(root, "0.19.0", ["0.19.0-W1-001", "0.19.0-W1-002"])

        _patch_project_root(monkeypatch, root)
        result = list_ticket_files_from_main("0.19.0")

        assert result is not None
        basenames = {Path(p).name for p in result}
        assert "0.19.0-W1-001.md" in basenames
        assert "0.19.0-W1-002.md" in basenames

    def test_returns_none_on_failure(self, tmp_path, monkeypatch):
        """
        Given: 非 git 目錄（main 與 master 皆不可解析）
        When: list_ticket_files_from_main("0.19.0")
        Then: 回傳 None（不拋例外）
        """
        root = tmp_path / "plain"
        _tickets_dir(root).mkdir(parents=True, exist_ok=True)
        assert not (root / ".git").exists()

        _patch_project_root(monkeypatch, root)
        assert list_ticket_files_from_main("0.19.0") is None
