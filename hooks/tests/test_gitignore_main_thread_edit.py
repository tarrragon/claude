"""
Test: 主線程允許編輯 .gitignore（Ticket: 0.18.0-W10-033）

驗證：
1. `.gitignore` 在主線程允許清單中（path_permission.check_file_permission 返回 allow）
2. `.gitignore` 在保護分支豁免路徑中（branch-verify-hook.is_path_exempt 返回 True）
3. 其他 root 檔案（如 package.json）仍被阻擋（邊界測試）

來源：本 session 實戰發現 Hook 對 .gitignore 過嚴（W10-032 需編輯 .gitignore 補 scheduled_tasks.lock 被攔截）。
"""

import logging
import sys
from pathlib import Path

# 測試目錄在 .claude/hooks/tests/，target 在 .claude/hooks/ 和 .claude/hooks/lib/
HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR / "lib"))


class _SilentLogger:
    """測試用最小 logger 介面，避免實際輸出。"""

    def debug(self, *args, **kwargs):
        pass

    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass


def test_gitignore_allowed_by_path_permission():
    """.gitignore 必須在 path_permission 允許清單中。"""
    from lib.path_permission import check_file_permission

    is_allowed, _ = check_file_permission(".gitignore", _SilentLogger())
    assert is_allowed, ".gitignore 應該被主線程允許編輯"


def test_package_json_still_blocked_by_path_permission():
    """package.json 等 root 檔案仍需被阻擋（邊界測試，防止過度放行）。"""
    from lib.path_permission import check_file_permission

    is_allowed, _ = check_file_permission("package.json", _SilentLogger())
    assert not is_allowed, "package.json 不應該被主線程編輯（邊界測試）"


def test_random_root_file_still_blocked():
    """.gitignore 放行不能影響其他 root 檔案。"""
    from lib.path_permission import check_file_permission

    for path in ["random.txt", "secrets.env", "tsconfig.json"]:
        is_allowed, _ = check_file_permission(path, _SilentLogger())
        assert not is_allowed, f"{path} 不應該被主線程編輯（邊界測試）"


def test_gitignore_exempt_by_branch_verify():
    """.gitignore 必須在 branch-verify 保護分支豁免清單中。"""
    # branch-verify-hook.py 以連字號命名無法直接 import，用 importlib
    import importlib.util

    hook_file = HOOKS_DIR / "branch-verify-hook.py"
    spec = importlib.util.spec_from_file_location("branch_verify_hook", hook_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    project_root = str(Path.cwd())

    # 相對路徑形式
    assert module.is_exempt_path_on_protected_branch(".gitignore", cwd=project_root), \
        ".gitignore 應該在保護分支豁免清單中（相對路徑）"


def test_package_json_not_exempt_by_branch_verify():
    """package.json 等 root 檔案在保護分支不應被豁免。"""
    import importlib.util

    hook_file = HOOKS_DIR / "branch-verify-hook.py"
    spec = importlib.util.spec_from_file_location("branch_verify_hook", hook_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    project_root = str(Path.cwd())

    assert not module.is_exempt_path_on_protected_branch("package.json", cwd=project_root), \
        "package.json 不應在保護分支豁免清單（邊界測試）"


def test_error_message_mentions_gitignore():
    """錯誤訊息的允許路徑清單應該包含 .gitignore（同步更新）。"""
    from lib.hook_messages import GateMessages

    message = GateMessages.EDIT_BLOCKED_DEFAULT_DENY
    assert ".gitignore" in message, \
        "EDIT_BLOCKED_DEFAULT_DENY 錯誤訊息應列出 .gitignore 為允許路徑"
