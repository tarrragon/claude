"""
Test create 子命令

涵蓋正常建立、各種錯誤情況、dry-run 模式等
"""

import pytest
import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

# 動態新增 scripts 目錄到 Python 路徑
scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))

from worktree_manager import cmd_create, derive_worktree_path


class TestCreateCommand:
    """create 子命令測試"""

    def test_create_invalid_ticket_id(self, capsys):
        """場景 5.1：Ticket ID 格式無效"""
        result = cmd_create("my-feature")
        assert result == 1

        captured = capsys.readouterr()
        assert "無效的 Ticket ID 格式" in captured.out
        assert "my-feature" in captured.out

    def test_create_dry_run_valid_ticket(self, capsys):
        """場景 4.3：dry-run 模式"""
        result = cmd_create("0.1.1-W9-002.1", dry_run=True)
        assert result == 0

        captured = capsys.readouterr()
        assert "Dry Run" in captured.out
        assert "git worktree add" in captured.out
        assert "feat/0.1.1-W9-002.1" in captured.out

    @patch('worktree_manager.check_branch_exists')
    def test_create_branch_already_exists(self, mock_check_branch, capsys):
        """場景 5.2：分支已存在"""
        # 第一次檢查 base 分支（main），第二次檢查 feat 分支
        mock_check_branch.side_effect = [True, True]

        result = cmd_create("0.1.1-W9-002.1")
        assert result == 1

        captured = capsys.readouterr()
        assert "分支已存在" in captured.out

    @patch('worktree_manager.check_branch_exists')
    @patch('worktree_manager.os.path.exists')
    def test_create_worktree_path_exists(self, mock_path_exists, mock_check_branch, capsys):
        """場景 5.3：worktree 路徑已存在"""
        # 第一次檢查 base 分支（存在），第二次檢查 feat 分支（不存在）
        mock_check_branch.side_effect = [True, False]
        mock_path_exists.return_value = True

        result = cmd_create("0.1.1-W9-002.1")
        assert result == 1

        captured = capsys.readouterr()
        assert "目錄已存在" in captured.out

    @patch('worktree_manager.check_branch_exists')
    def test_create_base_branch_not_exists(self, mock_check_branch, capsys):
        """場景 5.4：base 分支不存在"""
        # 模擬 base 分支不存在
        mock_check_branch.side_effect = lambda b: False if b == "develop" else True

        result = cmd_create("0.1.1-W9-002.1", base="develop")
        assert result == 1

        captured = capsys.readouterr()
        assert "基礎分支不存在" in captured.out
        assert "develop" in captured.out

    @patch('worktree_manager.check_branch_exists')
    def test_create_with_custom_base_dry_run(self, mock_check_branch, capsys):
        """場景 4.2：指定 base 分支 + dry-run"""
        # dry-run 模式下不需要檢查分支，但為了測試完整性，模擬分支存在
        mock_check_branch.return_value = True

        result = cmd_create("0.1.1-W9-002.1", base="develop", dry_run=True)
        assert result == 0

        captured = capsys.readouterr()
        assert "develop" in captured.out

    @patch('worktree_manager.run_git_command')
    @patch('worktree_manager.check_branch_exists')
    @patch('worktree_manager.os.path.exists')
    def test_create_success_valid_ticket(self, mock_path_exists, mock_check_branch, mock_run_git, capsys):
        """場景 5.5：成功建立 worktree（#5 修復：補充成功路徑測試）"""
        # 模擬檢查：base 分支存在，feat 分支不存在
        mock_check_branch.side_effect = [True, False]
        # 模擬路徑不存在
        mock_path_exists.return_value = False
        # 模擬 git worktree add 成功
        mock_run_git.return_value = (True, "正在建立 worktree")

        result = cmd_create("0.1.1-W9-002.1")
        assert result == 0

        captured = capsys.readouterr()
        assert "建立成功" in captured.out
        assert "0.1.1-W9-002.1" in captured.out
        assert "feat/0.1.1-W9-002.1" in captured.out

    @patch('worktree_manager.run_git_command')
    @patch('worktree_manager.check_branch_exists')
    @patch('worktree_manager.os.path.exists')
    def test_create_success_with_custom_base(self, mock_path_exists, mock_check_branch, mock_run_git, capsys):
        """場景 5.6：成功建立 worktree（自訂 base 分支）

        base != main 時 _merge_main_baseline 會額外檢查 main 是否存在
        （0.2.1-W3-554.3），故 check_branch_exists 第 3 次呼叫（main 存在）。
        """
        # 模擬檢查：develop 分支存在，feat 分支不存在，main 存在
        mock_check_branch.side_effect = [True, False, True]
        # 模擬路徑不存在
        mock_path_exists.return_value = False
        # 模擬 git worktree add 成功
        mock_run_git.return_value = (True, "")

        result = cmd_create("0.1.1-W9-002.1", base="develop")
        assert result == 0

        captured = capsys.readouterr()
        assert "建立成功" in captured.out
        assert "develop" in captured.out


class TestCreateMergesMainBaseline:
    """0.2.1-W3-554.3：worktree create 完成後確定性 merge main（issue #77 決議 A）"""

    @patch('worktree_manager.run_git_command')
    @patch('worktree_manager.check_branch_exists')
    @patch('worktree_manager.os.path.exists')
    def test_create_merges_main_after_success(
        self, mock_path_exists, mock_check_branch, mock_run_git, capsys
    ):
        """create 成功後自動執行 git merge main，並輸出同步成功訊息。"""
        mock_check_branch.side_effect = [True, False]  # base(main) 存在, feat 分支不存在
        mock_path_exists.return_value = False

        merge_calls = []

        def _fake_run_git(args, cwd=None, timeout=10):
            if args[:2] == ["worktree", "add"]:
                return (True, "")
            if args[:2] == ["merge", "main"]:
                merge_calls.append((args, cwd))
                return (True, "Updating abc123..def456\nFast-forward")
            return (True, "")

        mock_run_git.side_effect = _fake_run_git

        result = cmd_create("0.1.1-W9-002.1")

        assert result == 0
        assert len(merge_calls) == 1
        args, cwd = merge_calls[0]
        assert "--no-edit" in args
        assert cwd == derive_worktree_path("0.1.1-W9-002.1")  # 於新 worktree 目錄下執行
        captured = capsys.readouterr()
        assert "已合併 main" in captured.out

    @patch('worktree_manager.run_git_command')
    @patch('worktree_manager.check_branch_exists')
    @patch('worktree_manager.os.path.exists')
    def test_create_merge_main_up_to_date_no_conflict_message(
        self, mock_path_exists, mock_check_branch, mock_run_git, capsys
    ):
        """main 無新變更時（no-op fast-forward）不視為衝突，輸出「已是最新」訊息。"""
        mock_check_branch.side_effect = [True, False]
        mock_path_exists.return_value = False

        def _fake_run_git(args, cwd=None, timeout=10):
            if args[:2] == ["worktree", "add"]:
                return (True, "")
            if args[:2] == ["merge", "main"]:
                return (True, "Already up to date.")
            return (True, "")

        mock_run_git.side_effect = _fake_run_git

        result = cmd_create("0.1.1-W9-002.1")

        assert result == 0
        captured = capsys.readouterr()
        assert "無新變更" in captured.out
        assert "阻擋" not in captured.out

    @patch('worktree_manager.run_git_command')
    @patch('worktree_manager.check_branch_exists')
    @patch('worktree_manager.os.path.exists')
    def test_create_stops_on_main_merge_conflict(
        self, mock_path_exists, mock_check_branch, mock_run_git, capsys
    ):
        """merge main 衝突時明確停下：exit code 1，輸出後果與下一步，不自動解。"""
        mock_check_branch.side_effect = [True, False]
        mock_path_exists.return_value = False

        def _fake_run_git(args, cwd=None, timeout=10):
            if args[:2] == ["worktree", "add"]:
                return (True, "")
            if args[:2] == ["merge", "main"]:
                return (
                    False,
                    "CONFLICT (content): Merge conflict in foo.py\n"
                    "Automatic merge failed; fix conflicts and then commit the result.",
                )
            return (True, "")

        mock_run_git.side_effect = _fake_run_git

        result = cmd_create("0.1.1-W9-002.1")

        assert result == 1
        captured = capsys.readouterr()
        assert "[阻擋]" in captured.out
        assert "衝突" in captured.out
        assert "git status" in captured.out
        assert "git merge --abort" in captured.out
        # 不自動解：輸出中不應出現任何自動執行 abort/commit 的宣稱
        assert "已自動" not in captured.out

    @patch('worktree_manager.run_git_command')
    @patch('worktree_manager.check_branch_exists')
    @patch('worktree_manager.os.path.exists')
    def test_create_main_merge_conflict_skips_blocked_by_merge(
        self, mock_path_exists, mock_check_branch, mock_run_git, capsys
    ):
        """main 合併衝突後不疊加 blockedBy 合併（避免在已衝突的 working tree 上繼續操作）。"""
        mock_check_branch.side_effect = [True, False]
        mock_path_exists.return_value = False

        def _fake_run_git(args, cwd=None, timeout=10):
            if args[:2] == ["worktree", "add"]:
                return (True, "")
            if args[:2] == ["merge", "main"]:
                return (False, "CONFLICT (content): Merge conflict in foo.py")
            return (True, "")

        mock_run_git.side_effect = _fake_run_git

        result = cmd_create("0.1.1-W9-002.1")

        assert result == 1
        captured = capsys.readouterr()
        assert "blockedBy" not in captured.out
        assert "依賴分支" not in captured.out


class TestCreateSyncsMacosXcconfig:
    """0.2.1-W3-1069：worktree create 補齊 gitignored 的 macOS xcconfig 建置檔案

    macos/Flutter/Flutter-Debug.xcconfig、Flutter-Release.xcconfig 被 .gitignore
    的 /macos/ 規則排除，git worktree add 建立的新 worktree 不會帶有這兩個檔案，
    導致 flutter build macos / flutter test -d macos 找不到 include 檔而失敗。
    兩檔內容為固定的 Flutter 樣板（僅 #include 相對路徑，無機器相依內容），
    故用固定內容寫入取代「從主 checkout 複製」，避免帶入非標準本機修改。
    """

    @patch('worktree_manager.run_git_command')
    @patch('worktree_manager.check_branch_exists')
    @patch('worktree_manager.derive_worktree_path')
    def test_create_writes_missing_xcconfig_when_macos_platform_present(
        self, mock_derive_path, mock_check_branch, mock_run_git, tmp_path, capsys
    ):
        """macos/ 平台目錄存在（git worktree add 帶出 tracked 檔案）時，
        缺失的 xcconfig 應被自動補齊。"""
        worktree_path = str(tmp_path / "wt")
        mock_derive_path.return_value = worktree_path
        mock_check_branch.side_effect = [True, False]

        def _fake_run_git(args, cwd=None, timeout=10):
            if args[:2] == ["worktree", "add"]:
                os.makedirs(os.path.join(worktree_path, "macos", "Flutter"), exist_ok=True)
                return (True, "")
            return (True, "")

        mock_run_git.side_effect = _fake_run_git

        result = cmd_create("0.1.1-W9-002.1")

        assert result == 0
        debug_path = os.path.join(worktree_path, "macos", "Flutter", "Flutter-Debug.xcconfig")
        release_path = os.path.join(worktree_path, "macos", "Flutter", "Flutter-Release.xcconfig")
        assert os.path.exists(debug_path)
        assert os.path.exists(release_path)
        with open(debug_path, encoding="utf-8") as f:
            assert "ephemeral/Flutter-Generated.xcconfig" in f.read()
        captured = capsys.readouterr()
        assert "xcconfig" in captured.out.lower()

    @patch('worktree_manager.run_git_command')
    @patch('worktree_manager.check_branch_exists')
    @patch('worktree_manager.derive_worktree_path')
    def test_create_skips_xcconfig_sync_when_no_macos_platform(
        self, mock_derive_path, mock_check_branch, mock_run_git, tmp_path
    ):
        """worktree 沒有 macos/ 平台目錄時（非本專案或無 macOS target），不應建立任何檔案。"""
        worktree_path = str(tmp_path / "wt")
        mock_derive_path.return_value = worktree_path
        mock_check_branch.side_effect = [True, False]

        def _fake_run_git(args, cwd=None, timeout=10):
            if args[:2] == ["worktree", "add"]:
                os.makedirs(worktree_path, exist_ok=True)
                return (True, "")
            return (True, "")

        mock_run_git.side_effect = _fake_run_git

        result = cmd_create("0.1.1-W9-002.1")

        assert result == 0
        assert not os.path.exists(os.path.join(worktree_path, "macos"))

    @patch('worktree_manager.run_git_command')
    @patch('worktree_manager.check_branch_exists')
    @patch('worktree_manager.derive_worktree_path')
    def test_create_does_not_overwrite_existing_xcconfig(
        self, mock_derive_path, mock_check_branch, mock_run_git, tmp_path
    ):
        """xcconfig 已存在（如使用者已手動補過）時不覆寫，避免蓋掉本機自訂內容。"""
        worktree_path = str(tmp_path / "wt")
        mock_derive_path.return_value = worktree_path
        mock_check_branch.side_effect = [True, False]

        def _fake_run_git(args, cwd=None, timeout=10):
            if args[:2] == ["worktree", "add"]:
                flutter_dir = os.path.join(worktree_path, "macos", "Flutter")
                os.makedirs(flutter_dir, exist_ok=True)
                debug_path = os.path.join(flutter_dir, "Flutter-Debug.xcconfig")
                with open(debug_path, "w", encoding="utf-8") as f:
                    f.write("# 自訂內容，不應被覆寫\n")
                return (True, "")
            return (True, "")

        mock_run_git.side_effect = _fake_run_git

        result = cmd_create("0.1.1-W9-002.1")

        assert result == 0
        debug_path = os.path.join(worktree_path, "macos", "Flutter", "Flutter-Debug.xcconfig")
        with open(debug_path, encoding="utf-8") as f:
            assert "自訂內容" in f.read()
