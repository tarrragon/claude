"""lib/write_scope 公開函式測試（0.5.0-W1-390）。"""
import subprocess
from unittest.mock import patch

from ticket_system.lib import write_scope


def _git_init(path):
    path.mkdir(exist_ok=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)


class TestToRepoRelative:
    def test_relative_and_absolute_normalize_same(self, tmp_path):
        root = str(tmp_path)
        assert write_scope.to_repo_relative("a/b.py", root, root) == "a/b.py"
        assert write_scope.to_repo_relative(f"{root}/a/b.py", root, root) == "a/b.py"


class TestOutOfScopeFiles:
    def test_directory_declaration_covers_children(self, tmp_path):
        root = str(tmp_path)
        assert write_scope.out_of_scope_files(["d/x.py"], {"d"}, root, root) == []
        assert write_scope.out_of_scope_files(["e/x.py"], {"d"}, root, root) == ["e/x.py"]


class TestUnsafePaths:
    def test_symlink_file_flagged(self, tmp_path):
        (tmp_path / "r.txt").write_text("x")
        (tmp_path / "l.txt").symlink_to(tmp_path / "r.txt")
        root = str(tmp_path)
        assert write_scope.unsafe_paths(["l.txt"], root, root) == ["l.txt"]

    def test_symlink_dir_escaping_repo_flagged(self, tmp_path):
        repo, out = tmp_path / "repo", tmp_path / "out"
        repo.mkdir()
        out.mkdir()
        (out / "f").write_text("x")
        (repo / "s").symlink_to(out, target_is_directory=True)
        root = str(repo)
        assert write_scope.unsafe_paths(["s/f"], root, root) == ["s/f"]

    def test_regular_and_missing_files_pass(self, tmp_path):
        (tmp_path / "ok.txt").write_text("x")
        root = str(tmp_path)
        assert write_scope.unsafe_paths(["ok.txt", "gone.txt"], root, root) == []


class TestResolveRepoRoot:
    def test_no_worktree_returns_main_root(self):
        assert write_scope.resolve_repo_root(None, "/main") == "/main"

    def test_own_worktree_accepted(self, tmp_path):
        _git_init(tmp_path)
        result = write_scope.resolve_repo_root(str(tmp_path), str(tmp_path))
        assert result is not None

    def test_linked_worktree_accepted(self, tmp_path):
        main, linked = tmp_path / "main", tmp_path / "linked"
        _git_init(main)
        subprocess.run(
            ["git", "-C", str(main), "-c", "user.name=t", "-c", "user.email=t@e.x",
             "commit", "-q", "--allow-empty", "-m", "init"], check=True)
        subprocess.run(
            ["git", "-C", str(main), "worktree", "add", "-q", "-b", "wt", str(linked)],
            check=True)
        assert write_scope.resolve_repo_root(str(linked), str(main)) is not None

    def test_symlinked_path_forms_accepted(self, tmp_path):
        """E1：symlink 路徑與實體路徑混用於 --worktree／main_root，皆放行。"""
        real = tmp_path / "real"
        _git_init(real)
        alias = tmp_path / "alias"
        alias.symlink_to(real, target_is_directory=True)
        assert write_scope.resolve_repo_root(str(alias), str(real)) is not None
        assert write_scope.resolve_repo_root(str(real), str(alias)) is not None

    def test_foreign_repo_rejected(self, tmp_path):
        _git_init(tmp_path / "m")
        _git_init(tmp_path / "f")
        assert write_scope.resolve_repo_root(
            str(tmp_path / "f"), str(tmp_path / "m")
        ) is None

    def test_worktree_list_failure_rejected(self, tmp_path):
        _git_init(tmp_path)
        failed = subprocess.CompletedProcess([], 128, "", "boom")
        real_run = subprocess.run

        def fake_run(cmd, *a, **kw):
            return failed if "worktree" in cmd else real_run(cmd, *a, **kw)

        with patch.object(subprocess, "run", side_effect=fake_run):
            assert write_scope.resolve_repo_root(str(tmp_path), str(tmp_path)) is None
