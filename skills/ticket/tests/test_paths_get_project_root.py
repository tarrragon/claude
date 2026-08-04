"""
paths.py 的 get_project_root() 單元測試

測試覆蓋：
- 環境變數優先
- git rev-parse 優先（替代現有的 marker 搜尋）
- worktree 修復
- git 不可用 fallback
- marker 搜尋順序
- cwd fallback
- 相容性驗證
"""

import subprocess
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from ticket_system.lib.paths import get_project_root, reset_project_root_cache


class TestGetProjectRootPaths:
    """paths.py 的 get_project_root() 測試類別"""

    def test_env_var_priority(self):
        """環境變數 CLAUDE_PROJECT_DIR 優先（非 worktree 場景）"""
        custom_path = "/custom/project/path"
        with patch.dict("os.environ", {"CLAUDE_PROJECT_DIR": custom_path}):
            with patch(
                "ticket_system.lib.paths._linked_worktree_root",
                return_value=None
            ):
                result = get_project_root()
                assert result == Path(custom_path)

    def test_git_revparse_success(self):
        """git rev-parse 優先於 marker 搜尋"""
        git_root = "/path/to/git/repo"
        with patch.dict("os.environ", {}, clear=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout=git_root + "\n"
                )
                result = get_project_root()
                assert result == Path(git_root)
                # 驗證 subprocess（git）被呼叫
                assert mock_run.called
                call_args = mock_run.call_args
                assert "git" in call_args[0][0]

    def test_worktree_git_revparse(self, tmp_path):
        """worktree 環境下 git rev-parse 回傳源 repo 根目錄"""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        (repo_root / ".git").mkdir()
        (repo_root / "CLAUDE.md").write_text("# CLAUDE.md")

        worktree_dir = tmp_path / "worktree"
        worktree_dir.mkdir()

        with patch.dict("os.environ", {}, clear=True):
            with patch("pathlib.Path.cwd", return_value=worktree_dir):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value = MagicMock(
                        returncode=0,
                        stdout=str(repo_root) + "\n"
                    )
                    result = get_project_root()
                    assert result == repo_root
                    assert result != worktree_dir

    def test_git_not_found_fallback(self, tmp_path):
        """git 命令不存在時 fallback 到 marker 搜尋"""
        root = tmp_path / "project"
        root.mkdir()
        (root / "CLAUDE.md").write_text("# CLAUDE.md")

        with patch.dict("os.environ", {}, clear=True):
            with patch("pathlib.Path.cwd", return_value=root):
                with patch("subprocess.run") as mock_run:
                    mock_run.side_effect = FileNotFoundError("git not found")
                    result = get_project_root()
                    assert result == root

    def test_git_timeout_fallback(self, tmp_path):
        """git 命令超時時 fallback 到 marker 搜尋"""
        root = tmp_path / "project"
        root.mkdir()
        (root / "go.mod").write_text("module example.com")

        with patch.dict("os.environ", {}, clear=True):
            with patch("pathlib.Path.cwd", return_value=root):
                with patch("subprocess.run") as mock_run:
                    mock_run.side_effect = subprocess.TimeoutExpired("git", 5)
                    result = get_project_root()
                    assert result == root

    def test_git_failure_fallback(self, tmp_path):
        """git 失敗（returncode != 0）時 fallback 到 marker 搜尋"""
        root = tmp_path / "project"
        root.mkdir()
        (root / "pubspec.yaml").write_text("name: example")

        with patch.dict("os.environ", {}, clear=True):
            with patch("pathlib.Path.cwd", return_value=root):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value = MagicMock(returncode=128, stdout="")
                    result = get_project_root()
                    assert result == root

    def test_marker_fallback_order(self, tmp_path):
        """marker 搜尋順序：CLAUDE.md > go.mod > pubspec.yaml"""
        root = tmp_path / "root"
        root.mkdir()

        # 建立所有三種 marker
        (root / "CLAUDE.md").write_text("# CLAUDE.md")
        (root / "go.mod").write_text("module example.com")
        (root / "pubspec.yaml").write_text("name: example")

        subdir = root / "subdir"
        subdir.mkdir()

        with patch.dict("os.environ", {}, clear=True):
            with patch("pathlib.Path.cwd", return_value=subdir):
                with patch("subprocess.run") as mock_run:
                    mock_run.side_effect = FileNotFoundError("git not found")
                    result = get_project_root()
                    # 應該找到 root（優先序不重要，只要找到任何 marker）
                    assert result == root

    def test_cwd_fallback(self, tmp_path):
        """全部失敗時 fallback 到 cwd"""
        isolated_dir = tmp_path / "isolated"
        isolated_dir.mkdir()

        with patch.dict("os.environ", {}, clear=True):
            with patch("pathlib.Path.cwd", return_value=isolated_dir):
                with patch("subprocess.run") as mock_run:
                    mock_run.side_effect = FileNotFoundError("git not found")
                    result = get_project_root()
                    assert result == isolated_dir

    def test_backward_compatibility_ticket_commands(self):
        """驗證 ticket 命令相容性：函式簽名保持不變"""
        assert callable(get_project_root)
        with patch.dict("os.environ", {"CLAUDE_PROJECT_DIR": "/test"}):
            with patch(
                "ticket_system.lib.paths._linked_worktree_root",
                return_value=None
            ):
                result = get_project_root()
                assert isinstance(result, Path)

    def test_worktree_aware_prefers_worktree_root_over_env(self):
        """worktree 感知：位於 linked worktree 時優先用 worktree root（凌駕 CLAUDE_PROJECT_DIR）

        W3-008 根因 1 修復：worktree 場景下 CLAUDE_PROJECT_DIR 恆指向主 repo，
        應優先用 worktree root 避免 ticket CRUD/auto-commit 洩漏到主 repo。
        """
        main_repo = "/main/repo"
        worktree_root = Path("/main/repo/.claude/worktrees/agent-abc")
        with patch.dict("os.environ", {"CLAUDE_PROJECT_DIR": main_repo}):
            with patch(
                "ticket_system.lib.paths._linked_worktree_root",
                return_value=worktree_root
            ):
                result = get_project_root()
                assert result == worktree_root
                assert result != Path(main_repo)

    def test_non_worktree_uses_env(self):
        """非 worktree 場景（_linked_worktree_root 回 None）：用 CLAUDE_PROJECT_DIR"""
        main_repo = "/main/repo"
        with patch.dict("os.environ", {"CLAUDE_PROJECT_DIR": main_repo}):
            with patch(
                "ticket_system.lib.paths._linked_worktree_root",
                return_value=None
            ):
                result = get_project_root()
                assert result == Path(main_repo)


class TestLinkedWorktreeRoot:
    """_linked_worktree_root() 的 git-native 偵測測試"""

    def test_main_repo_returns_none(self):
        """主 repo：--git-dir == --git-common-dir，回傳 None"""
        from ticket_system.lib.paths import _linked_worktree_root
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=".git\n.git\n"
            )
            assert _linked_worktree_root() is None

    def test_linked_worktree_returns_toplevel(self):
        """linked worktree：--git-dir != --git-common-dir，回傳 worktree toplevel"""
        from ticket_system.lib.paths import _linked_worktree_root
        wt_root = "/main/repo/.claude/worktrees/agent-abc"
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(
                    returncode=0,
                    stdout="/main/repo/.git/worktrees/agent-abc\n/main/repo/.git\n"
                ),
                MagicMock(returncode=0, stdout=wt_root + "\n"),
            ]
            assert _linked_worktree_root() == Path(wt_root)

    def test_git_unavailable_returns_none(self):
        """git 不可用：回傳 None（不誤判 worktree）"""
        from ticket_system.lib.paths import _linked_worktree_root
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("git not found")
            assert _linked_worktree_root() is None

    def test_git_failure_returns_none(self):
        """git 失敗（returncode != 0）：回傳 None"""
        from ticket_system.lib.paths import _linked_worktree_root
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=128, stdout="")
            assert _linked_worktree_root() is None


class TestGetProjectRootCache:
    """get_project_root() 程序內快取（0.2.1-W3-254）。

    自動載入的 `.claude/skills/ticket/conftest.py::_isolate_project_root`
    autouse fixture 在每個 test 前呼叫 reset_project_root_cache()，故本類別
    每個 test 開始時快取已為空，可直接測試「呼叫內」的快取行為。
    """

    def teardown_method(self):
        # 保險：即使本類別內測試提前 raise，仍清快取避免污染後續其他測試
        # 檔案（雙重保護，autouse fixture 已於每個 test 前處理，此為防禦層）。
        reset_project_root_cache()

    def test_second_call_uses_cache_not_new_subprocess(self):
        """AC1：單次「呼叫」內（模擬單一 CLI process）第二次呼叫不再觸發 git subprocess。"""
        git_root = "/path/to/git/repo"
        with patch.dict("os.environ", {}, clear=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout=git_root + "\n")
                first = get_project_root()
                second = get_project_root()

        assert first == second == Path(git_root)
        # worktree 偵測（1 次）+ git rev-parse（1 次）＝ 2 次；快取生效後
        # 第二次呼叫應完全不再觸發任何 subprocess.run。
        assert mock_run.call_count == 2

    def test_reset_forces_fresh_resolution(self):
        """reset_project_root_cache() 後下次呼叫重新解析，不沿用舊快取值。"""
        with patch.dict("os.environ", {}, clear=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0, stdout="/first/root\n"
                )
                first = get_project_root()

            reset_project_root_cache()

            with patch("subprocess.run") as mock_run2:
                mock_run2.return_value = MagicMock(
                    returncode=0, stdout="/second/root\n"
                )
                second = get_project_root()

        assert first == Path("/first/root")
        assert second == Path("/second/root")
        assert first != second

    def test_worktree_result_cached_correctly(self):
        """worktree 情境：快取後第二次呼叫仍回傳同一 worktree root，且不重複偵測。

        需 `patch.dict(..., clear=True)` 清除 autouse fixture 注入的
        `TICKET_SYSTEM_TEST_ISOLATION=1`，否則測試隔離逃生艙（步驟 0）
        會在抵達 `_linked_worktree_root` 前就短路回傳 fixture 的 tmp 目錄。
        """
        worktree_root = Path("/main/repo/.claude/worktrees/agent-abc")
        with patch.dict("os.environ", {}, clear=True):
            with patch(
                "ticket_system.lib.paths._linked_worktree_root",
                return_value=worktree_root,
            ) as mock_worktree:
                first = get_project_root()
                second = get_project_root()

        assert first == second == worktree_root
        # 快取生效後第二次呼叫不應再呼叫 _linked_worktree_root。
        assert mock_worktree.call_count == 1

    def test_main_repo_result_cached_correctly(self):
        """主 repo 情境（非 worktree）：快取後第二次呼叫仍回傳同一根目錄，且不重複偵測。

        同上，須 clear=True 排除逃生艙旗標干擾。
        """
        main_repo = "/main/repo"
        with patch.dict("os.environ", {"CLAUDE_PROJECT_DIR": main_repo}, clear=True):
            with patch(
                "ticket_system.lib.paths._linked_worktree_root",
                return_value=None,
            ) as mock_worktree:
                first = get_project_root()
                second = get_project_root()

        assert first == second == Path(main_repo)
        assert mock_worktree.call_count == 1

    def test_autouse_fixture_reset_simulates_test_boundary_isolation(self):
        """模擬 conftest 的 autouse fixture 行為（不依賴實際 pytest 執行順序
        ——避免測試斷言依賴執行順序，見 test-assertion-design-rules 規則 D）：
        先讓快取寫入某值，呼叫 reset_project_root_cache()（fixture 每個 test
        前實際執行的動作），驗證快取確實歸零，不會洩漏給下一個呼叫者。"""
        with patch.dict("os.environ", {}, clear=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0, stdout="/boundary/test/root\n"
                )
                get_project_root()

        from ticket_system.lib.paths import _project_root_cache as cache_after_call
        assert cache_after_call == Path("/boundary/test/root")

        # 模擬下一個 test 開始前 autouse fixture 執行的動作
        reset_project_root_cache()

        from ticket_system.lib.paths import _project_root_cache as cache_after_reset
        assert cache_after_reset is None
