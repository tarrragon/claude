"""
Test: hook-completeness-check._format_permission_report（0.2.1-W3-499 AC2）

驗證「權限」區塊回報語意修正：本次 chmod 修復的檔案數不再併入主計數
「已確認可執行」，改獨立成另一行。修正前的假訊號：
`f"權限: {ok_count + len(fixed_files)} 個已確認可執行"` 會讓本次才修復的
檔案讀起來像本 session 已就緒。

0.2.1-W3-514 追加約束：獨立那一行原寫「下個 session 起生效」，該敘述等同
斷言「runtime 於 session 啟動時一次快照 hook 命令集」這個當時尚未驗證的假設。
現改為只陳述已修復數量、不對生效時點作斷言，並以
test_no_line_asserts_effective_timing 釘住此約束。

0.2.1-W3-704 更新約束的依據（非放寬約束）：0.2.1-W3-510 已完成該區分實驗，
結論為**版本相依**——08-13 側資料支持快照模型，08-18 兩輪 session_id 直接
歸因實驗支持即時生效，兩組各自自洽且互相矛盾。故約束從「因未知而不斷言」
升級為「因已知會翻轉而不斷言」：斷言任一時點都會在模型翻轉時變成假訊息。
test_no_line_asserts_effective_timing 的斷言清單維持不變，含「立即生效」
——即使 08-18 實測即時生效，也不得寫死。

0.2.1-W3-687 對齊輸出層措辭：獨立行原寫「本 session 內是否生效未經驗證」，
其中「未經驗證」在實驗完成後為假訊息，會讓讀者以為尚無人查過而重跑實驗或
多做一次無謂重啟。改為「本次補上可執行位 N 個（生效時點不作斷言）」——只
陳述已完成的動作，時點維度整個不進入輸出。約束方向與 0.2.1-W3-514 一致
（仍不斷言時點），變的是不再宣稱該問題無人回答。新增
test_no_line_claims_timing_unverified 釘住此約束。

Source: ticket 0.2.1-W3-499、0.2.1-W3-514、0.2.1-W3-704、0.2.1-W3-687
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
        assert lines[1] == "權限: 本次補上可執行位 1 個（生效時點不作斷言）"

    def test_multiple_fixed_files_count_correct(self):
        lines = hook_mod._format_permission_report(
            ok_count=100, fixed_files=["a.py", "b.py", "c.py"]
        )
        assert lines[1] == "權限: 本次補上可執行位 3 個（生效時點不作斷言）"

    def test_no_line_claims_fixed_files_are_confirmed_executable(self):
        """回歸防護：任何一行都不得把 fixed_files 計入「已確認可執行」語意。"""
        lines = hook_mod._format_permission_report(
            ok_count=50, fixed_files=["x.py", "y.py"]
        )
        combined = "\n".join(lines)
        assert "52 個已確認可執行" not in combined

    def test_no_line_asserts_effective_timing(self):
        """回歸防護：不得斷言修復何時生效。

        理由已由「尚無實驗區分」更新為「實驗結論為版本相依」（0.2.1-W3-704）：
        runtime 解析 hook 命令集的時機在 08-13 側觀測支持快照模型、08-18 兩輪
        實驗支持即時生效。既然模型會隨 runtime 版本翻轉，寫死任一時點都會在
        翻轉後成為假訊息，故「立即生效」同樣列入禁止清單——它在 08-18 為真，
        但正確性不該建立在會翻轉的維度上。
        """
        lines = hook_mod._format_permission_report(
            ok_count=50, fixed_files=["x.py", "y.py"]
        )
        combined = "\n".join(lines)
        for claim in ("下個 session 起生效", "本 session 生效", "立即生效"):
            assert claim not in combined

    def test_no_line_claims_timing_unverified(self):
        """回歸防護：不得宣稱生效時點「未經驗證」。

        與 test_no_line_asserts_effective_timing 是同一約束的兩側——該測試
        禁止斷言某個時點，本測試禁止宣稱無人查過。區分實益：實驗已完成，
        結論為版本相依；寫「未經驗證」會讓讀者誤以為此問題尚待回答，而據此
        重跑實驗或多做一次無謂重啟。合格寫法是只陳述已完成的動作。
        """
        lines = hook_mod._format_permission_report(
            ok_count=50, fixed_files=["x.py", "y.py"]
        )
        combined = "\n".join(lines)
        for claim in ("未經驗證", "尚未驗證", "無實驗"):
            assert claim not in combined
