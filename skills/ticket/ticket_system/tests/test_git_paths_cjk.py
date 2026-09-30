"""E2：git 路徑清單讀取對 CJK 檔名的處理（tarrragon/claude#111）。

git 預設 core.quotepath=true 會把非 ASCII 路徑加引號並八進位跳脫。本檔在真實
tmp git repo 以 CJK 檔名 fixture 驗證各讀取點取得原始路徑；ASCII 對照維持綠。
"""

import subprocess
from pathlib import Path

import pytest

from ticket_system.commands import track_commit
from ticket_system.lib import git_ops, ticket_builder

_CJK_REL = "docs/work-logs/v1/tickets/票面-測試.md"
_ASCII_REL = "docs/work-logs/v1/tickets/ascii-test.md"


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True,
        encoding="utf-8", check=True,
    )
    return result.stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    _git(tmp_path, "config", "core.quotepath", "true")
    # 目錄內先有已追蹤檔，避免 status 把全未追蹤目錄折疊成單一目錄項
    seed = tmp_path / "docs/work-logs/v1/tickets/seed.md"
    seed.parent.mkdir(parents=True)
    seed.write_text("seed\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "seed")
    return tmp_path


def _write(repo: Path, rel: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("content\n", encoding="utf-8")


def _shared_index_paths(repo: Path) -> set:
    out = _git(repo, "ls-files", "-z")
    return {p for p in out.split("\0") if p}


class TestCommitFilesIsolatedCjk:
    @pytest.mark.parametrize("rel", [_CJK_REL, _ASCII_REL])
    def test_commit_succeeds_and_shared_index_keeps_file(self, repo, rel):
        _write(repo, rel)
        result = git_ops.commit_files_isolated([rel], "msg", cwd=str(repo))
        assert result["status"] == "committed", result["error"]
        assert rel in _shared_index_paths(repo)
        assert rel in _git(repo, "ls-tree", "-r", "--name-only", "-z", "HEAD").split("\0")


class TestExpandDirectoryCjk:
    @pytest.mark.parametrize("rel", [_CJK_REL, _ASCII_REL])
    def test_directory_expansion_returns_raw_path(self, repo, rel):
        _write(repo, rel)
        got = track_commit._expand_directory_to_changed_files(
            "docs/work-logs/v1/tickets", str(repo)
        )
        assert got == [rel]


class TestListTicketFilesFromMainCjk:
    @pytest.mark.parametrize("rel", [_CJK_REL, _ASCII_REL])
    def test_ls_tree_returns_raw_path(self, repo, rel, monkeypatch):
        _write(repo, rel)
        _git(repo, "add", rel)
        _git(repo, "commit", "-q", "-m", "add")
        tickets_dir = repo / "docs/work-logs/v1/tickets"
        monkeypatch.setattr(ticket_builder, "get_ticket_state_root", lambda: repo)
        monkeypatch.setattr(ticket_builder, "get_tickets_dir", lambda v: tickets_dir)
        got = ticket_builder.list_ticket_files_from_main("1")
        assert sorted(got) == sorted([rel, "docs/work-logs/v1/tickets/seed.md"])
