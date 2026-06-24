"""
Test: main-thread-edit-restriction-hook 跨專案放行邏輯（Ticket: 0.18.0-W17-148）

驗證：
1. 主線程編輯本專案內檔案：仍套用 path_permission（既有行為）
2. 主線程編輯外部 repo 檔案：跨專案 skip path_permission，直接放行
3. find_target_repo 找不到 .git 時：fallback 至 path_permission（保守）

來源：0.18.0-W17-147 ANA → 0.18.0-W17-148 IMP
"""

import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# 測試目錄在 .claude/hooks/tests/，target hook 在 .claude/hooks/
HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent))
sys.path.insert(0, str(HOOKS_DIR.parent))


def _load_hook_module():
    """以 importlib 載入連字號命名的 hook 模組"""
    hook_file = HOOKS_DIR / "main-thread-edit-restriction-hook.py"
    spec = importlib.util.spec_from_file_location("main_thread_edit_restriction_hook", hook_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestCrossRepoBypass(unittest.TestCase):
    """跨專案放行行為驗證"""

    def _run_main_with_input(self, hook_module, input_data):
        """以 stdin 注入 JSON 並呼叫 hook.main()，回傳 exit code"""
        stdin_buf = io.StringIO(json.dumps(input_data))
        with patch("sys.stdin", stdin_buf):
            return hook_module.main()

    def test_cross_repo_bypasses_path_permission(self):
        """跨專案編輯：即使檔名不在白名單也應放行"""
        hook = _load_hook_module()

        with tempfile.TemporaryDirectory() as tmp:
            other_repo = Path(tmp) / "other_project"
            (other_repo / "content").mkdir(parents=True)
            (other_repo / ".git").mkdir()
            target = other_repo / "content" / "skill.md"
            target.write_text("")

            input_data = {
                "tool_name": "Edit",
                "tool_input": {"file_path": str(target)},
            }

            # 假設當前 cwd 在本專案；hook 應偵測 target_repo != current_root → 放行
            with patch.object(hook, "is_subagent_environment", return_value=False):
                # 強制讓 get_current_branch 回傳 main（非 feat/*），避免分支豁免提前放行
                with patch.object(hook, "get_current_branch", return_value="main"):
                    with patch.object(hook, "is_allowed_branch", return_value=False):
                        exit_code = self._run_main_with_input(hook, input_data)

            self.assertEqual(exit_code, 0, "跨專案編輯應放行（exit 0）")

    def test_same_repo_still_applies_path_permission(self):
        """本專案內編輯：仍套用 path_permission（黑名單檔案應被擋）"""
        hook = _load_hook_module()

        # 取本專案 root
        from lib.git_utils import get_project_root as _gpr
        project_root = _gpr()

        # 選一個本專案內、應被 path_permission 擋的路徑（例如 src/ 下任意檔）
        # 由於本 repo 為 Chrome Extension，src/ 為產品程式碼受保護
        target = str(Path(project_root) / "src" / "background" / "service-worker.js")

        input_data = {
            "tool_name": "Edit",
            "tool_input": {"file_path": target},
        }

        with patch.object(hook, "is_subagent_environment", return_value=False):
            with patch.object(hook, "get_current_branch", return_value="main"):
                with patch.object(hook, "is_allowed_branch", return_value=False):
                    exit_code = self._run_main_with_input(hook, input_data)

        # 本專案內 src/ 應被 path_permission 阻擋（exit 2）
        # 注意：此測試假設 src/ 不在白名單；若 path_permission 規則改變需同步調整
        self.assertEqual(exit_code, 2, "本專案內 src/ 檔案應被 path_permission 擋")

    def test_relative_path_does_not_trigger_cross_repo_logic(self):
        """相對路徑（不以 / 開頭）：跳過 find_target_repo 走原邏輯"""
        hook = _load_hook_module()

        input_data = {
            "tool_name": "Edit",
            "tool_input": {"file_path": ".gitignore"},
        }

        with patch.object(hook, "is_subagent_environment", return_value=False):
            with patch.object(hook, "get_current_branch", return_value="main"):
                with patch.object(hook, "is_allowed_branch", return_value=False):
                    exit_code = self._run_main_with_input(hook, input_data)

        # .gitignore 在白名單，應放行
        self.assertEqual(exit_code, 0, ".gitignore 為相對路徑且在白名單，應放行")


if __name__ == "__main__":
    unittest.main()
