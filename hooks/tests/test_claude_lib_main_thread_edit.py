"""
Test: 主線程允許編輯 .claude/lib/ 下的 .py

驗證：
1. .claude/lib/ 的 .py（含子套件）與 .md 皆被 path_permission 放行
2. 正向對照（E2）：.claude/ 以外的產品碼路徑（lib/、test/、*.dart、*.go）仍被拒絕
3. 拒絕訊息的「.claude/ 允許子目錄」清單列出 lib，說明文字不再宣稱 .py 被阻擋

來源：pm-role 寫明 .claude/** 為主線程可寫路徑；同檔放行 .claude/hooks/、
.claude/skills/ 的 .py，唯獨擋 .claude/lib/*.py，且查無擋的理由。
"""

import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent))


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


@pytest.mark.parametrize(
    "path",
    [
        ".claude/lib/x.py",
        ".claude/lib/path_permission.py",
        ".claude/lib/ticket_quality/detectors.py",
        ".claude/lib/README.md",
    ],
)
def test_claude_lib_files_allowed(path):
    """.claude/lib/ 下的 .py 與 .md 皆允許主線程編輯。"""
    from lib.path_permission import check_file_permission

    is_allowed, reason = check_file_permission(path, _SilentLogger())
    assert is_allowed, f"{path} 應被允許，實際拒絕：{reason}"


@pytest.mark.parametrize(
    "path",
    ["lib/a.py", "test/a_test.py", "src/a.dart", "x.go", ".claude/libx/a.py"],
)
def test_product_code_paths_still_blocked(path):
    """正向對照：.claude/lib/ 以外的產品碼路徑與相鄰目錄名仍被拒絕。"""
    from lib.path_permission import check_file_permission

    is_allowed, _ = check_file_permission(path, _SilentLogger())
    assert not is_allowed, f"{path} 應仍被拒絕"


def test_denial_message_lists_lib_subdirectory():
    """拒絕訊息的允許子目錄清單列出 lib，且不再宣稱 .py 由 BLOCKED 阻擋。"""
    from lib.path_permission import get_allowed_claude_subdirectory_lines

    lib_lines = [
        line for line in get_allowed_claude_subdirectory_lines()
        if line.strip().startswith("- .claude/lib/")
    ]
    assert len(lib_lines) == 1
    assert "BLOCKED" not in lib_lines[0]
