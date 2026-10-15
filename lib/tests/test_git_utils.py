#!/usr/bin/env python3
"""
git_utils 模組單元測試
"""

import os
import signal
import subprocess
import threading
from contextlib import nullcontext
import time
import unittest
import pytest
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

# 添加 lib 目錄到路徑
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.git_utils import (
    get_current_branch,
    get_project_root,
    get_uncommitted_files,
    _get_uncommitted_status_lines,
    get_worktree_list,
    is_allowed_branch,
    is_protected_branch,
    run_git_command,
    run_with_graceful_timeout,
    TERMINATE_GRACE_SECONDS,
    find_target_repo,
    FileStatus,
    BRANCH_PREFIX_LEN,
    WORKTREE_PREFIX_LEN,
)


class TestRunGitCommand(unittest.TestCase):
    """測試 run_git_command 函式"""

    @patch('subprocess.run')
    def test_successful_command(self, mock_run):
        """測試成功執行 git 命令"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="main\n",
            stderr=""
        )
        success, output = run_git_command(["branch", "--show-current"])
        self.assertTrue(success)
        self.assertEqual(output, "main")

    @patch('subprocess.run')
    def test_failed_command(self, mock_run):
        """測試失敗的 git 命令"""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="fatal: not a git repository"
        )
        success, output = run_git_command(["status"])
        self.assertFalse(success)
        self.assertIn("not a git repository", output)

    @patch('subprocess.run')
    def test_timeout(self, mock_run):
        """測試命令超時"""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="git", timeout=10)
        success, output = run_git_command(["status"])
        self.assertFalse(success)
        self.assertIn("timed out", output)


class TestBranchFunctions(unittest.TestCase):
    """測試分支相關函式"""

    @patch('lib.git_utils.run_git_command')
    def test_get_current_branch_success(self, mock_run):
        """測試成功獲取當前分支"""
        mock_run.return_value = (True, "feat/new-feature")
        branch = get_current_branch()
        self.assertEqual(branch, "feat/new-feature")

    @patch('lib.git_utils.run_git_command')
    def test_get_current_branch_failure(self, mock_run):
        """測試獲取分支失敗"""
        mock_run.return_value = (False, "error")
        branch = get_current_branch()
        self.assertIsNone(branch)

    def test_is_protected_branch(self):
        """測試保護分支檢測"""
        self.assertTrue(is_protected_branch("main"))
        self.assertTrue(is_protected_branch("master"))
        self.assertTrue(is_protected_branch("develop"))
        self.assertTrue(is_protected_branch("release/v1.0"))
        self.assertFalse(is_protected_branch("feat/new-feature"))
        self.assertFalse(is_protected_branch("fix/bug-fix"))

    def test_is_allowed_branch(self):
        """測試允許編輯的分支檢測"""
        self.assertTrue(is_allowed_branch("feat/new-feature"))
        self.assertTrue(is_allowed_branch("fix/bug-fix"))
        self.assertTrue(is_allowed_branch("chore/update-deps"))
        self.assertTrue(is_allowed_branch("refactor/cleanup"))
        self.assertFalse(is_allowed_branch("main"))
        self.assertFalse(is_allowed_branch("random-branch"))


class TestWorktreeFunctions(unittest.TestCase):
    """測試 worktree 相關函式"""

    @patch('lib.git_utils.run_git_command')
    def test_get_worktree_list(self, mock_run):
        """測試獲取 worktree 列表"""
        mock_run.return_value = (True, """worktree /path/to/repo
branch refs/heads/main

worktree /path/to/feature
branch refs/heads/feat/new-feature
""")
        worktrees = get_worktree_list()
        self.assertEqual(len(worktrees), 2)
        self.assertEqual(worktrees[0]["path"], "/path/to/repo")
        self.assertEqual(worktrees[0]["branch"], "main")
        self.assertEqual(worktrees[1]["path"], "/path/to/feature")
        self.assertEqual(worktrees[1]["branch"], "feat/new-feature")

    @patch('lib.git_utils.run_git_command')
    def test_get_worktree_list_failure(self, mock_run):
        """測試獲取 worktree 列表失敗"""
        mock_run.return_value = (False, "error")
        worktrees = get_worktree_list()
        self.assertEqual(worktrees, [])

    @patch('lib.git_utils.run_git_command')
    def test_get_worktree_list_forwards_cwd(self, mock_run):
        """0.2.1-W3-286：cwd 參數轉發給 run_git_command（支援指定 worktree 路徑查詢）"""
        mock_run.return_value = (True, "")
        get_worktree_list(cwd="/some/worktree")
        mock_run.assert_called_once_with(
            ["worktree", "list", "--porcelain"], cwd="/some/worktree"
        )

    @patch('lib.git_utils.run_git_command')
    def test_get_worktree_list_exclude_main(self, mock_run):
        """0.2.1-W3-286：exclude_main=True 時排除 main/master，保留其他分支與 detached"""
        mock_run.return_value = (True, """worktree /path/to/repo
branch refs/heads/main

worktree /path/to/feature
branch refs/heads/feat/new-feature

worktree /path/to/detached
detached
""")
        worktrees = get_worktree_list(exclude_main=True)
        paths = [wt["path"] for wt in worktrees]
        self.assertNotIn("/path/to/repo", paths)
        self.assertIn("/path/to/feature", paths)
        # detached 項目（無 branch 值）不受 exclude_main 影響，仍保留
        self.assertIn("/path/to/detached", paths)

    @patch('lib.git_utils.run_git_command')
    def test_get_worktree_list_exclude_main_false_keeps_all(self, mock_run):
        """exclude_main=False（預設）時維持原本行為，main 仍在清單中"""
        mock_run.return_value = (True, """worktree /path/to/repo
branch refs/heads/main
""")
        worktrees = get_worktree_list()
        self.assertEqual(len(worktrees), 1)
        self.assertEqual(worktrees[0]["branch"], "main")


class TestConstants(unittest.TestCase):
    """測試常數定義"""

    def test_worktree_prefix_length(self):
        """測試 worktree 前綴長度"""
        self.assertEqual(WORKTREE_PREFIX_LEN, len("worktree "))

    def test_branch_prefix_length(self):
        """測試 branch 前綴長度"""
        self.assertEqual(BRANCH_PREFIX_LEN, len("branch "))


class TestFileStatus(unittest.TestCase):
    """測試 FileStatus dataclass"""

    def test_file_status_creation(self):
        """測試 FileStatus 建立"""
        file = FileStatus(status=" M", file_path="file.txt")
        self.assertEqual(file.status, " M")
        self.assertEqual(file.file_path, "file.txt")

    def test_is_modified(self):
        """測試是否為修改狀態"""
        file = FileStatus(status=" M", file_path="file.txt")
        self.assertTrue(file.is_modified)
        self.assertFalse(file.is_added)
        self.assertFalse(file.is_untracked)

    def test_is_added(self):
        """測試是否為新增狀態"""
        file = FileStatus(status="A ", file_path="new.py")
        self.assertFalse(file.is_modified)
        self.assertTrue(file.is_added)
        self.assertFalse(file.is_untracked)

    def test_is_untracked(self):
        """測試是否為未追蹤"""
        file = FileStatus(status="??", file_path="untracked.txt")
        self.assertFalse(file.is_modified)
        self.assertFalse(file.is_added)
        self.assertTrue(file.is_untracked)

    def test_is_staged(self):
        """測試是否有 staged 變更"""
        staged = FileStatus(status="M ", file_path="file.txt")
        unstaged = FileStatus(status=" M", file_path="file.txt")
        untracked = FileStatus(status="??", file_path="file.txt")
        
        self.assertTrue(staged.is_staged)
        self.assertFalse(unstaged.is_staged)
        self.assertFalse(untracked.is_staged)

    def test_file_status_str(self):
        """測試 FileStatus 字串表示"""
        file = FileStatus(status=" M", file_path="file.txt")
        self.assertEqual(str(file), " M file.txt")


class TestUncommittedStatusLines(unittest.TestCase):
    """測試 get_uncommitted_status_lines 和相關函式"""

    @patch('lib.git_utils.run_git_command')
    def test_has_uncommitted_changes(self, mock_run):
        """測試有未提交變更時回傳非空列表"""
        mock_run.return_value = (True, " M file1.txt\0?? file2.txt\0A  file3.py\0")
        status_lines = _get_uncommitted_status_lines()
        self.assertEqual(len(status_lines), 3)
        self.assertIn(" M file1.txt", status_lines)
        self.assertIn("?? file2.txt", status_lines)
        self.assertIn("A  file3.py", status_lines)

    @patch('lib.git_utils.run_git_command')
    def test_no_uncommitted_changes(self, mock_run):
        """測試無未提交變更時回傳空列表"""
        mock_run.return_value = (True, "")
        status_lines = _get_uncommitted_status_lines()
        self.assertEqual(status_lines, [])

    @patch('lib.git_utils.run_git_command')
    def test_git_command_failure(self, mock_run):
        """測試 git 命令失敗時回傳空列表"""
        mock_run.return_value = (False, "fatal: not a git repository")
        status_lines = _get_uncommitted_status_lines()
        self.assertEqual(status_lines, [])

    @patch('lib.git_utils.run_git_command')
    def test_porcelain_format_preserved(self, mock_run):
        """測試 porcelain 格式狀態行被保留

        注意：本測試 mock 層級為 run_git_command 本身，不涵蓋
        run_git_command 內部對 subprocess.run 結果做 strip 的路徑，
        故無法捕捉 IMP-BAL-007 / 0.2.1-W3-284 缺陷（整體 strip 剝除
        首行前導空白）。該缺陷的回歸測試見
        TestRunGitCommandSubprocessLevel（mock 點下移至 subprocess.run）。
        """
        mock_run.return_value = (
            True, " M modified.txt\0?? untracked.txt\0 D deleted.txt\0"
        )
        status_lines = _get_uncommitted_status_lines()
        # 驗證格式完整性（含狀態和空格）
        self.assertTrue(any(line.startswith(" M") for line in status_lines))
        self.assertTrue(any(line.startswith("??") for line in status_lines))
        self.assertTrue(any(line.startswith(" D") for line in status_lines))


class TestRunGitCommandSubprocessLevel(unittest.TestCase):
    """mock 點下移至 subprocess.run，覆蓋 run_git_command 內部 strip 路徑

    IMP-BAL-007 / 0.2.1-W3-284 迴歸測試：舊測試 mock run_git_command
    本身，無法觸及其內部對 result.stdout 做 strip 的那一行。這裡改
    mock subprocess.run，讓 run_git_command 的真實實作（含 strip 邏輯）
    進入受測範圍。
    """

    @patch('subprocess.run')
    def test_porcelain_leading_space_preserved(self, mock_run):
        """porcelain 首行前導空白（worktree-modified 狀態）不應被剝除"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=" M aaa.txt\n?? zzz-untracked.txt\n",
            stderr="",
        )
        success, output = run_git_command(["status", "--porcelain"])
        self.assertTrue(success)
        # 首行前導空白必須保留，否則 " M aaa.txt" 會被誤剝成 "M aaa.txt"
        self.assertEqual(output.split("\n")[0], " M aaa.txt")

    @patch('subprocess.run')
    def test_uncommitted_files_first_line_parsed_correctly(self, mock_run):
        """get_uncommitted_files 對首行 worktree-modified 檔案的解析須正確

        對應 ticket 實驗重現：整體 strip 使首行 status 由 " M" 誤判為 "M "
        （is_staged 由 False 誤翻為 True），file_path 掉首字元。
        """
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=" M aaa.txt\0?? zzz-untracked.txt\0",
            stderr="",
        )
        files = get_uncommitted_files()
        self.assertEqual(len(files), 2)
        first = files[0]
        self.assertEqual(first.status, " M")
        self.assertEqual(first.file_path, "aaa.txt")
        self.assertFalse(first.is_staged)


class TestUncommittedFiles(unittest.TestCase):
    """測試 get_uncommitted_files 高階 API"""

    @patch('lib.git_utils.run_git_command')
    def test_get_uncommitted_files_with_changes(self, mock_run):
        """測試有未提交變更時回傳 FileStatus 列表"""
        mock_run.return_value = (True, " M file1.txt\0?? file2.txt\0A  file3.py\0")
        files = get_uncommitted_files()
        
        self.assertEqual(len(files), 3)
        
        # 驗證第一個檔案（修改）
        self.assertEqual(files[0].status, " M")
        self.assertEqual(files[0].file_path, "file1.txt")
        self.assertTrue(files[0].is_modified)
        self.assertFalse(files[0].is_untracked)
        
        # 驗證第二個檔案（未追蹤）
        self.assertEqual(files[1].status, "??")
        self.assertEqual(files[1].file_path, "file2.txt")
        self.assertTrue(files[1].is_untracked)
        
        # 驗證第三個檔案（新增）
        self.assertEqual(files[2].status, "A ")
        self.assertEqual(files[2].file_path, "file3.py")
        self.assertTrue(files[2].is_added)

    @patch('lib.git_utils.run_git_command')
    def test_get_uncommitted_files_empty(self, mock_run):
        """測試無未提交變更時回傳空列表"""
        mock_run.return_value = (True, "")
        files = get_uncommitted_files()
        self.assertEqual(files, [])

    @patch('lib.git_utils.run_git_command')
    def test_get_uncommitted_files_forwards_cwd(self, mock_run):
        """0.2.1-W3-286：cwd 參數轉發，支援指定 worktree 路徑查詢（取代各
        hook 各自 `git -C <path> status --porcelain` 的重複實作）"""
        mock_run.return_value = (True, "")
        get_uncommitted_files(cwd="/some/worktree")
        mock_run.assert_called_once_with(
            ["status", "--porcelain", "-z"], cwd="/some/worktree"
        )

    @patch('lib.git_utils.run_git_command')
    def test_get_uncommitted_files_failure(self, mock_run):
        """測試 git 命令失敗時回傳空列表"""
        mock_run.return_value = (False, "fatal: not a git repository")
        files = get_uncommitted_files()
        self.assertEqual(files, [])

    @patch('lib.git_utils.run_git_command')
    def test_get_uncommitted_files_parse_multiple_files(self, mock_run):
        """測試正確解析多個變更檔案"""
        mock_run.return_value = (
            True,
            "M  modified_staged.txt\0 M unstaged_modified.txt\0"
            "?? new_untracked.txt\0A  added_staged.py\0 D deleted_unstaged.py\0",
        )
        files = get_uncommitted_files()
        
        self.assertEqual(len(files), 5)
        
        # 驗證每個檔案的狀態
        statuses = [f.status for f in files]
        file_paths = [f.file_path for f in files]
        
        self.assertIn("M ", statuses)
        self.assertIn(" M", statuses)
        self.assertIn("??", statuses)
        self.assertIn("A ", statuses)
        self.assertIn(" D", statuses)
        
        self.assertIn("modified_staged.txt", file_paths)
        self.assertIn("unstaged_modified.txt", file_paths)
        self.assertIn("new_untracked.txt", file_paths)
        self.assertIn("added_staged.py", file_paths)
        self.assertIn("deleted_unstaged.py", file_paths)


class TestFindTargetRepo(unittest.TestCase):
    """測試 find_target_repo：依檔案路徑往上找 .git 標記"""

    def test_returns_none_for_empty_path(self):
        self.assertIsNone(find_target_repo(""))

    def test_finds_repo_with_git_directory(self):
        """一般 repo（.git 為目錄）：應找到 repo 根"""
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo_a"
            (repo / ".git").mkdir(parents=True)
            (repo / "src").mkdir()
            target_file = repo / "src" / "x.py"
            target_file.write_text("")

            result = find_target_repo(str(target_file))
            self.assertEqual(Path(result).resolve(), repo.resolve())

    def test_finds_repo_with_git_file_worktree(self):
        """worktree（.git 為檔案）：應找到 worktree 根"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            wt = Path(tmp) / "worktree_a"
            (wt / "sub").mkdir(parents=True)
            # worktree 的 .git 是檔案
            (wt / ".git").write_text("gitdir: /some/path\n")
            target_file = wt / "sub" / "y.py"
            target_file.write_text("")

            result = find_target_repo(str(target_file))
            self.assertEqual(Path(result).resolve(), wt.resolve())

    def test_returns_none_for_non_git_path(self):
        """非 git 環境：應回傳 None"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            target_file = Path(tmp) / "x.py"
            target_file.write_text("")
            # /tmp 上層通常無 .git，但保險起見只驗證不為 tmp 本身
            result = find_target_repo(str(target_file))
            # 結果可能為 None，或為某個祖先 repo（CI 環境難保證）
            # 至少必須不是 tmp 自身（因 tmp 無 .git）
            if result is not None:
                self.assertNotEqual(Path(result).resolve(), Path(tmp).resolve())

    def test_distinguishes_two_separate_repos(self):
        """兩個獨立 repo：分別找到正確的根"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            repo_a = Path(tmp) / "repo_a"
            repo_b = Path(tmp) / "repo_b"
            (repo_a / ".git").mkdir(parents=True)
            (repo_b / ".git").mkdir(parents=True)
            file_a = repo_a / "a.py"
            file_b = repo_b / "b.py"
            file_a.write_text("")
            file_b.write_text("")

            self.assertEqual(Path(find_target_repo(str(file_a))).resolve(), repo_a.resolve())
            self.assertEqual(Path(find_target_repo(str(file_b))).resolve(), repo_b.resolve())


# ---------- run_with_graceful_timeout 契約測試（0.5.0-W1-164.6.2） ----------
# 案例移植自 skills/worktree/tests/test_graceful_timeout_contract.py，固定 lib 版
# 與 worktree-auto-commit-hook / ticket git_ops 兩份私有複本的行為一致。
# 耗時上界採寬鬆門檻（孫程序 sleep 30、斷言 15 秒內返回），避免機器負載造成誤判。

_SLOW_SECONDS = 30
_BOUND_SECONDS = 15


def _pid_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


@pytest.fixture
def pid_log(tmp_path):
    """測試內啟動的程序把 PID 追加到此檔；結束時逐一終止並以 PID 確認已不存在。"""
    path = tmp_path / "pids.log"
    path.touch()
    yield path
    pids = [int(t) for t in path.read_text().split()]
    for pid in pids:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and any(_pid_alive(p) for p in pids):
        time.sleep(0.05)
    survivors = [p for p in pids if _pid_alive(p)]
    assert not survivors, f"測試結束後仍殘留程序：{survivors}"


@pytest.fixture
def slow_filter_repo(tmp_path, monkeypatch, pid_log):
    """含慢 clean filter 的暫存 repo；git add 期間持有 index.lock。"""
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    repo = tmp_path / "repo"
    repo.mkdir()
    for cmd in (
        ["git", "init", "-q"],
        [
            "git", "config", "filter.slow.clean",
            f"echo $$ >> '{pid_log}'; sleep {_SLOW_SECONDS} & echo $! >> '{pid_log}'; wait; cat",
        ],
    ):
        subprocess.run(cmd, cwd=repo, check=True)
    (repo / ".gitattributes").write_text("*.dat filter=slow\n")
    (repo / "payload.dat").write_text("x\n")
    return repo


def _lock(repo):
    return repo / ".git" / "index.lock"


def _wait_for_lock(repo):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if _lock(repo).exists():
            return True
        time.sleep(0.05)
    return False


# 子程序裝好處理器後才寫就緒標記；高負載下啟動慢於逾時時標記缺席，測試 skip 而非假紅或假綠
_RECORD_SIGTERM = (
    "import signal, sys, time\n"
    "out, ready = sys.argv[1], sys.argv[2]\n"
    "def on_term(signum, frame):\n"
    "    open(out, 'w').write('SIGTERM')\n"
    "    sys.exit(0)\n"
    "signal.signal(signal.SIGTERM, on_term)\n"
    "open(ready, 'w').write('1')\n"
    "time.sleep(60)\n"
)

_IGNORE_SIGTERM = (
    "import signal, sys, time\n"
    "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
    "open(sys.argv[1], 'w').write('1')\n"
    "time.sleep(60)\n"
)


class TestRunWithGracefulTimeout:
    def test_grace_constant_is_five_seconds(self):
        assert TERMINATE_GRACE_SECONDS == 5

    def test_timeout_sends_sigterm_first(self, tmp_path):
        record = tmp_path / "signal.txt"
        ready = tmp_path / "ready.txt"
        with pytest.raises(subprocess.TimeoutExpired):
            run_with_graceful_timeout(
                [sys.executable, "-c", _RECORD_SIGTERM, str(record), str(ready)], 3, text=True
            )
        if not ready.exists():
            pytest.skip("子程序在逾時前未裝好 SIGTERM 處理器（環境負載過高）")
        assert record.exists() and record.read_text() == "SIGTERM"

    def test_ignoring_sigterm_is_killed_after_grace(self, tmp_path):
        ready = tmp_path / "ready.txt"
        start = time.monotonic()
        with pytest.raises(subprocess.TimeoutExpired):
            run_with_graceful_timeout(
                [sys.executable, "-c", _IGNORE_SIGTERM, str(ready)], 1, grace=1, text=True
            )
        if not ready.exists():
            pytest.skip("子程序在逾時前未進入忽略 SIGTERM 狀態，未走到 kill 路徑（環境負載過高）")
        assert time.monotonic() - start < _BOUND_SECONDS

    def test_grandchild_holding_pipe_does_not_extend_wait(self, pid_log):
        script = (
            f"sleep {_SLOW_SECONDS} & echo $! >> '{pid_log}'; "
            f"sleep {_SLOW_SECONDS * 2} & echo $! >> '{pid_log}'; wait"
        )
        start = time.monotonic()
        with pytest.raises(subprocess.TimeoutExpired):
            run_with_graceful_timeout(
                ["sh", "-c", script], 1, grace=1, text=True, start_new_session=True
            )
        assert time.monotonic() - start < _BOUND_SECONDS

    def test_ignoring_sigterm_with_grandchild_has_bounded_wait(self, pid_log):
        script = (
            f"trap '' TERM; echo $$ >> '{pid_log}'; "
            f"sleep {_SLOW_SECONDS} & echo $! >> '{pid_log}'; "
            f"sleep {_SLOW_SECONDS * 2} & echo $! >> '{pid_log}'; wait"
        )
        start = time.monotonic()
        with pytest.raises(subprocess.TimeoutExpired):
            run_with_graceful_timeout(
                ["sh", "-c", script], 1, grace=1, text=True, start_new_session=True
            )
        assert time.monotonic() - start < _BOUND_SECONDS

    def test_input_is_passed_to_stdin(self):
        result = run_with_graceful_timeout(["cat"], 10, input="hello", text=True)
        assert (result.returncode, result.stdout) == (0, "hello")

    def test_completed_process_fields(self):
        result = run_with_graceful_timeout(
            ["sh", "-c", "echo out; echo err >&2; exit 3"], 10, text=True
        )
        assert (result.returncode, result.stdout, result.stderr) == (3, "out\n", "err\n")

    def test_timeout_none_waits_for_completion(self):
        result = run_with_graceful_timeout(["echo", "ok"], None, text=True)
        assert result.stdout == "ok\n"


class TestProcessGroupTermination:
    def test_timeout_kills_grandchild_in_group(self, pid_log):
        script = f"sleep {_SLOW_SECONDS} & echo $! >> '{pid_log}'; wait"
        with pytest.raises(subprocess.TimeoutExpired):
            run_with_graceful_timeout(["sh", "-c", script], 1, grace=1, text=True)
        pids = [int(x) for x in pid_log.read_text().split()]
        assert pids
        time.sleep(0.3)
        for pid in pids:
            with pytest.raises(ProcessLookupError):
                os.kill(pid, 0)

    def test_normal_completion_sends_no_signal(self):
        with patch("lib.git_utils.os.killpg") as killpg:
            result = run_with_graceful_timeout(["echo", "ok"], 10, text=True)
        assert result.stdout == "ok\n"
        killpg.assert_not_called()

    def test_missing_group_logs_warning(self, capsys):
        real_killpg = os.killpg

        def fake(pid, sig):
            real_killpg(pid, signal.SIGKILL)  # 實際收尾，再模擬群組已不存在
            raise ProcessLookupError

        with patch("lib.git_utils.os.killpg", side_effect=fake):
            with pytest.raises(subprocess.TimeoutExpired):
                run_with_graceful_timeout(["sleep", "30"], 1, grace=1, text=True)
        assert "already gone" in capsys.readouterr().err

    def test_killpg_oserror_logs_warning(self, capsys):
        real_killpg = os.killpg

        def fake(pid, sig):
            real_killpg(pid, signal.SIGKILL)
            raise PermissionError("denied")

        with patch("lib.git_utils.os.killpg", side_effect=fake):
            with pytest.raises(subprocess.TimeoutExpired):
                run_with_graceful_timeout(["sleep", "31"], 1, grace=1, text=True)
        assert "failed: denied" in capsys.readouterr().err


class TestSigtermForwarding:
    """hook 自身收到 SIGTERM 時須轉送給 start_new_session 的子群組。"""

    _TRAP = "trap 'echo got >> \"{log}\"; exit 0' TERM; sleep 2 & wait"

    def _run_with_self_term(self, log, forwarding=True):
        received = []
        previous = signal.signal(signal.SIGTERM, lambda s, f: received.append(s))
        timer = threading.Timer(0.6, os.kill, (os.getpid(), signal.SIGTERM))
        args = ["sh", "-c", self._TRAP.format(log=log)]
        try:
            timer.start()
            if forwarding:
                run_with_graceful_timeout(args, 10, text=True)
            else:
                with patch("lib.git_utils._forward_sigterm_to_group", lambda p: nullcontext()):
                    run_with_graceful_timeout(args, 10, text=True)
        finally:
            timer.cancel()
            signal.signal(signal.SIGTERM, previous)
        time.sleep(0.3)
        return received

    def test_child_group_receives_term_and_previous_handler_called(self, tmp_path):
        log = tmp_path / "term.log"
        received = self._run_with_self_term(log)
        assert log.exists() and "got" in log.read_text()
        assert received == [signal.SIGTERM]

    def test_without_forwarding_child_misses_term(self, tmp_path):
        """正向對照：移除轉送時子群組收不到 TERM，上一測試的斷言即轉紅。"""
        log = tmp_path / "term.log"
        self._run_with_self_term(log, forwarding=False)
        assert not log.exists()

    def test_handler_restored_after_run(self):
        before = signal.getsignal(signal.SIGTERM)
        run_with_graceful_timeout(["echo", "ok"], 10, text=True)
        assert signal.getsignal(signal.SIGTERM) == before

    def test_previous_handler_none_skips_forwarding_without_error(self, capsys):
        with patch("lib.git_utils.signal.getsignal", return_value=None):
            result = run_with_graceful_timeout(["echo", "ok"], 10, text=True)
        assert result.returncode == 0 and result.stdout.strip() == "ok"
        assert "previous handler not installed" in capsys.readouterr().err

    def test_previous_handler_sig_dfl_still_installs_forwarding(self, capsys):
        with patch("lib.git_utils.signal.getsignal", return_value=signal.SIG_DFL):
            run_with_graceful_timeout(["echo", "ok"], 10, text=True)
        assert "previous handler not installed" not in capsys.readouterr().err

    def test_non_main_thread_does_not_raise(self, capsys):
        errors = []

        def work():
            try:
                run_with_graceful_timeout(["echo", "ok"], 10, text=True)
            except Exception as e:  # 收集後於主執行緒斷言
                errors.append(e)

        t = threading.Thread(target=work)
        t.start()
        t.join()
        assert errors == []
        assert "not in main thread" in capsys.readouterr().err


class TestIndexLockEffect:
    """效果層：逾時終止後 index.lock 是否殘留。SIGKILL 對照證明 fixture 有鑑別力。"""

    def test_sigterm_via_lib_clears_index_lock(self, slow_filter_repo):
        lock_seen = threading.Event()
        stop = threading.Event()

        def watch():
            while not stop.is_set():
                if _lock(slow_filter_repo).exists():
                    lock_seen.set()
                    return
                time.sleep(0.02)

        watcher = threading.Thread(target=watch, daemon=True)
        watcher.start()
        start = time.monotonic()
        try:
            with pytest.raises(subprocess.TimeoutExpired):
                run_with_graceful_timeout(
                    ["git", "add", "payload.dat"], 3,
                    cwd=slow_filter_repo, text=True, start_new_session=True,
                )
        finally:
            stop.set()
            watcher.join()
        if not lock_seen.is_set():
            pytest.skip("逾時前 git 未取得 index.lock（機器負載高），無法鑑別清鎖行為")
        assert time.monotonic() - start < _BOUND_SECONDS
        assert not _lock(slow_filter_repo).exists()

    def test_direct_sigkill_leaves_index_lock(self, slow_filter_repo):
        """對照：直接 SIGKILL 同一呼叫，鎖檔殘留。"""
        proc = subprocess.Popen(
            ["git", "add", "payload.dat"], cwd=slow_filter_repo,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        try:
            if not _wait_for_lock(slow_filter_repo):
                pytest.skip("git 未取得 index.lock（機器負載高），無法建立對照")
            proc.kill()
            proc.wait()
            assert _lock(slow_filter_repo).exists()
        finally:
            proc.wait()


if __name__ == "__main__":
    unittest.main()
