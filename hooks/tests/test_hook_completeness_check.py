"""
Test: hook-completeness-check._format_permission_report（0.2.1-W3-499 AC2）

驗證「權限」區塊回報語意修正：本次 chmod 修復的檔案數不再併入主計數
「已確認可執行」，改獨立成另一行。修正前的假訊號：
`f"權限: {ok_count + len(fixed_files)} 個已確認可執行"` 會讓本次才修復的
檔案讀起來像本 session 已就緒。

0.2.1-W3-514 追加約束：獨立那一行原寫「下個 session 起生效」，該敘述等同
斷言「runtime 於 session 啟動時一次快照 hook 命令集」這個尚未驗證的假設
（區分實驗見 0.2.1-W3-510）。現改為只陳述已修復數量、不對生效時點作斷言，
並以 test_no_line_asserts_effective_timing 釘住此約束。

Source: ticket 0.2.1-W3-499、0.2.1-W3-514
"""

import importlib.util
import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
HOOK_PATH = HOOKS_DIR / "hook-completeness-check.py"


def _load_hook_module():
    spec = importlib.util.spec_from_file_location(
        "hook_completeness_check_permission_report_under_test", HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)
    if str(HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(HOOKS_DIR))
    spec.loader.exec_module(module)
    return module


hook_mod = _load_hook_module()


class TestFormatPermissionReport:
    def test_no_fixed_files_single_line_main_count_only(self):
        lines = hook_mod._format_permission_report(ok_count=104, fixed_files=[])
        assert lines == ["權限: 104 個已確認可執行"]

    def test_fixed_files_not_merged_into_main_count(self):
        """本次修復的檔案不併入主計數，主計數只含 ok_count。"""
        lines = hook_mod._format_permission_report(
            ok_count=103, fixed_files=["workspace-wipe-guard-hook.py"]
        )
        assert lines[0] == "權限: 103 個已確認可執行"

    def test_fixed_files_reported_as_separate_line(self):
        lines = hook_mod._format_permission_report(
            ok_count=103, fixed_files=["workspace-wipe-guard-hook.py"]
        )
        assert len(lines) == 2
        assert lines[1] == "權限: 本次修復 1 個（本 session 內是否生效未經驗證）"

    def test_multiple_fixed_files_count_correct(self):
        lines = hook_mod._format_permission_report(
            ok_count=100, fixed_files=["a.py", "b.py", "c.py"]
        )
        assert lines[1] == "權限: 本次修復 3 個（本 session 內是否生效未經驗證）"

    def test_no_line_claims_fixed_files_are_confirmed_executable(self):
        """回歸防護：任何一行都不得把 fixed_files 計入「已確認可執行」語意。"""
        lines = hook_mod._format_permission_report(
            ok_count=50, fixed_files=["x.py", "y.py"]
        )
        combined = "\n".join(lines)
        assert "52 個已確認可執行" not in combined

    def test_no_line_asserts_effective_timing(self):
        """回歸防護：不得斷言修復何時生效——該時點取決於 runtime 解析 hook
        命令集的時機（session 啟動一次快照 vs 每次呼叫解析），尚無實驗區分。
        """
        lines = hook_mod._format_permission_report(
            ok_count=50, fixed_files=["x.py", "y.py"]
        )
        combined = "\n".join(lines)
        for claim in ("下個 session 起生效", "本 session 生效", "立即生效"):
            assert claim not in combined
