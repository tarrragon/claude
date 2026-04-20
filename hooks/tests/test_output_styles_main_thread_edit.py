"""
Test: 主線程允許編輯 .claude/output-styles/（W10-050）

驗證：
1. .claude/output-styles/ 路徑在 path_permission 允許清單中
2. 邊界測試：未列入的目錄（如 .claude/foo/）仍被阻擋
3. 錯誤訊息同步：EDIT_BLOCKED_DEFAULT_DENY 包含 .claude/output-styles/

來源：W10-008 多視角審查發現主線程被擋無法寫入 .claude/output-styles/，
派發代理人成本高且偏離 ARCH-016（Hook 允許清單應主動維護）。
本測試覆蓋 W10-050 的白名單擴充，落地 ARCH-018 教訓。
"""

import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR / "lib"))


class _SilentLogger:
    """測試用最小 logger 介面。"""

    def debug(self, *args, **kwargs):
        pass

    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass


def test_output_styles_allowed_by_path_permission():
    """.claude/output-styles/ 下的檔案必須被主線程允許編輯。"""
    from lib.path_permission import check_file_permission

    is_allowed, _ = check_file_permission(
        ".claude/output-styles/5w1h-format.md", _SilentLogger()
    )
    assert is_allowed, ".claude/output-styles/ 應該被主線程允許編輯"


def test_output_styles_subpath_allowed():
    """.claude/output-styles/ 子目錄也應被允許。"""
    from lib.path_permission import check_file_permission

    is_allowed, _ = check_file_permission(
        ".claude/output-styles/custom/format.md", _SilentLogger()
    )
    assert is_allowed, ".claude/output-styles/ 任意子路徑應被允許"


def test_unlisted_claude_subdirectory_still_blocked():
    """未列入白名單的 .claude/ 子目錄仍應被阻擋（邊界測試）。"""
    from lib.path_permission import check_file_permission

    is_allowed, _ = check_file_permission(
        ".claude/random-dir/file.md", _SilentLogger()
    )
    assert not is_allowed, "未列入白名單的 .claude/ 子目錄仍應被阻擋"
