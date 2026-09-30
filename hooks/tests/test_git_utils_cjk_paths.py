#!/usr/bin/env python3
"""CJK 檔名下共用 git 讀取層須回傳原始 UTF-8 路徑（core.quotepath=false / -z）。"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.git_utils import get_uncommitted_files, run_git_command
from lib.hook_io import run_git
from lib.skill_case_guard import check_git_tree_skill_md_case


def _git(repo: str, *args: str) -> None:
    subprocess.run(
        ["git", "-C", repo, "-c", "user.email=t@t", "-c", "user.name=t", *args],
        check=True, capture_output=True,
    )


class TestCjkPaths(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = self._tmp.name
        _git(self.repo, "init", "-q")
        (Path(self.repo) / "舊檔名.md").write_text("x", encoding="utf-8")
        (Path(self.repo) / "plain.md").write_text("x", encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "init")

    def tearDown(self):
        self._tmp.cleanup()

    def test_untracked_cjk_path_is_raw_utf8(self):
        (Path(self.repo) / "新增文件.md").write_text("y", encoding="utf-8")
        paths = [f.file_path for f in get_uncommitted_files(cwd=self.repo)]
        self.assertIn("新增文件.md", paths)

    def test_ascii_path_still_works(self):
        (Path(self.repo) / "plain.md").write_text("changed", encoding="utf-8")
        files = get_uncommitted_files(cwd=self.repo)
        self.assertEqual([f.file_path for f in files], ["plain.md"])

    def test_rename_keeps_old_arrow_new_format(self):
        _git(self.repo, "mv", "舊檔名.md", "新檔名.md")
        paths = [f.file_path for f in get_uncommitted_files(cwd=self.repo)]
        self.assertEqual(paths, ["舊檔名.md -> 新檔名.md"])

    def test_run_git_command_unquoted(self):
        ok, out = run_git_command(["ls-files"], cwd=self.repo)
        self.assertTrue(ok)
        self.assertIn("舊檔名.md", out.splitlines())

    def test_hook_io_run_git_unquoted(self):
        out = run_git(["git", "ls-files"], cwd=self.repo)
        self.assertIn("舊檔名.md", (out or "").splitlines())

    def test_hook_io_run_git_non_git_argv_untouched(self):
        out = run_git(["echo", "a"], cwd=self.repo)
        self.assertEqual(out, "a")

    def test_skill_case_guard_cjk_skill_dir(self):
        d = Path(self.repo) / "skills" / "中文技能"
        d.mkdir(parents=True)
        (d / "skill.md").write_text("x", encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "s")
        warnings = check_git_tree_skill_md_case(Path(self.repo))
        self.assertEqual(len(warnings), 1)
        self.assertIn("中文技能", warnings[0])


if __name__ == "__main__":
    unittest.main()
