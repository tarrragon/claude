"""測試 ticket track dispatch-readiness 命令（0.18.0-W17-053 + 0.2.1-W3-249）。

涵蓋三項核心閾值 + 第四項一致性檢查 + exit code 矩陣：
- 閾值 1（功能職責數 / acceptance 近似）：≤2 pass / 3-4 warn / >4 fail
- 閾值 2（修改檔案數 where.files）：≤5 pass / 6-10 warn / >10 fail
- 閾值 3（Context Bundle tokens 近似）：≤3000 pass / 3001-5000 warn / >5000 fail
- 檢查 4（acceptance 測試類關鍵詞 vs where.files 測試路徑一致性）：
  無關鍵詞 pass / 命中但無測試路徑 warn（不含 fail）/ 命中且有測試路徑 pass
- ticket 不存在 / IO 錯誤 → exit 2
- 任一 fail → exit 2；任一 warn 無 fail → exit 1；全 pass → exit 0
"""

from __future__ import annotations

import argparse
import io
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch

from ticket_system.commands.track_dispatch_readiness import (
    check_acceptance_writeset_consistency,
    check_context_bundle_tokens,
    check_file_count,
    check_responsibility_count,
    execute_dispatch_readiness,
)


# ---------------------------------------------------------------------------
# 純函式單元測試
# ---------------------------------------------------------------------------


class TestResponsibilityCount:
    def test_two_or_fewer_pass(self):
        status, n, _ = check_responsibility_count(["a", "b"])
        assert status == "pass"
        assert n == 2

    def test_three_to_four_warn(self):
        status, _, _ = check_responsibility_count(["a", "b", "c"])
        assert status == "warn"
        status2, _, _ = check_responsibility_count(["a", "b", "c", "d"])
        assert status2 == "warn"

    def test_more_than_four_fail(self):
        status, n, _ = check_responsibility_count(["a", "b", "c", "d", "e"])
        assert status == "fail"
        assert n == 5

    def test_none_treated_as_zero(self):
        status, n, _ = check_responsibility_count(None)
        assert status == "pass"
        assert n == 0


class TestFileCount:
    def test_five_or_fewer_pass(self):
        status, _, _ = check_file_count(["a", "b", "c", "d", "e"])
        assert status == "pass"

    def test_six_to_ten_warn(self):
        status, _, _ = check_file_count([f"f{i}" for i in range(6)])
        assert status == "warn"
        status2, _, _ = check_file_count([f"f{i}" for i in range(10)])
        assert status2 == "warn"

    def test_more_than_ten_fail(self):
        status, n, _ = check_file_count([f"f{i}" for i in range(11)])
        assert status == "fail"
        assert n == 11

    def test_empty_pass(self):
        status, n, _ = check_file_count([])
        assert status == "pass"
        assert n == 0

    def test_filters_empty_strings(self):
        status, n, _ = check_file_count(["a", "", "b"])
        assert status == "pass"
        assert n == 2


class TestContextBundleTokens:
    def test_missing_section_pass(self):
        status, est, _ = check_context_bundle_tokens("no section")
        assert status == "pass"
        assert est == 0

    def test_small_pass(self):
        body = "## Context Bundle\n\n" + ("x" * 200) + "\n\n## Next\n"
        status, est, _ = check_context_bundle_tokens(body)
        assert status == "pass"
        assert est < 3000

    def test_above_soft_warn(self):
        # > 3000 tokens ≈ > 12000 chars
        body = "## Context Bundle\n\n" + ("x" * 13000) + "\n\n## Next\n"
        status, est, _ = check_context_bundle_tokens(body)
        assert status == "warn"
        assert est > 3000 and est <= 5000

    def test_above_hard_fail(self):
        # > 5000 tokens ≈ > 20000 chars
        body = "## Context Bundle\n\n" + ("x" * 25000) + "\n\n## Next\n"
        status, est, _ = check_context_bundle_tokens(body)
        assert status == "fail"
        assert est > 5000


class TestAcceptanceWritesetConsistency:
    """0.2.1-W3-249：acceptance 測試類關鍵詞 vs where.files 測試路徑一致性。"""

    def test_no_test_keyword_pass(self):
        status, items, _ = check_acceptance_writeset_consistency(
            ["兩個實測反例皆不再繞過", "引號配對不再因跳脫序列而錯位"],
            ["a.py"],
        )
        assert status == "pass"
        assert items == []

    def test_keyword_with_test_path_pass(self):
        status, items, _ = check_acceptance_writeset_consistency(
            ["新增測試涵蓋識別成功與不誤觸發兩側"],
            [".claude/hooks/post-test-hook.py", ".claude/hooks/tests/test_post_test_hook.py"],
        )
        assert status == "pass"
        assert items == []

    def test_empty_acceptance_pass(self):
        status, items, _ = check_acceptance_writeset_consistency(None, [])
        assert status == "pass"
        assert items == []

    def test_regression_w3_234_shim_regression_no_test_path_warns(self):
        """0.2.1-W3-234 實例：acceptance 含「回歸驗證」但 where.files 僅
        `check.py`，無測試路徑——測試缺口後續另需補票（0.2.1-W3-248）。"""
        acceptance = [
            "_check_single_package() 引用 package_manager.SHIM_CLIS，check.py 內無獨立 shim 清單",
            "三個 shim CLI（ticket / doc / worktree）在 check 輸出中不再標記 OUTDATED 或 MISSING",
            "check 輸出不再對 shim CLI 建議 uv tool install --force --reinstall",
            "非 shim 套件的既有判定行為不變（回歸驗證）",
        ]
        where_files = [
            ".claude/skills/project-init/project_init/commands/check.py",
        ]
        status, items, msg = check_acceptance_writeset_consistency(acceptance, where_files)
        assert status == "warn"
        assert len(items) == 1
        assert "回歸驗證" in items[0]
        assert "false positive" in msg

    def test_regression_w3_233_two_scenarios_coverage_no_test_path_warns(self):
        """0.2.1-W3-233 實例：acceptance 明文要求「兩情形皆有測試覆蓋」但
        寫入集僅含 hook + lib 兩檔，無測試路徑——執行者後來自行納入測試檔
        （test_parallel_suggestion_hook.py）並透明記錄，本檢查應能命中此矛盾。"""
        acceptance = [
            "extract_ticket_info 回傳含 wave 欄位，既有呼叫端不受影響",
            "訊息輸出含真實 pending 數，且與 ticket track list --wave N --status pending 結果一致（實測記錄兩者輸出）",
            "pending 為零與非零兩情形皆有測試覆蓋",
            "hooks 全量測試套件通過，無新增失敗",
        ]
        where_files = [
            ".claude/hooks/parallel-suggestion-hook.py",
            ".claude/lib/ask_user_question_reminders.py",
        ]
        status, items, msg = check_acceptance_writeset_consistency(acceptance, where_files)
        assert status == "warn"
        # 「測試覆蓋」與「全量測試套件」兩條皆含測試類關鍵詞
        assert len(items) == 2
        assert any("測試覆蓋" in item for item in items)
        assert "false positive" in msg

    def test_regression_w3_233_resolved_once_test_path_added(self):
        """同一實例：若寫入集事後補上測試路徑（W3-249 修復後的正確派發方式），
        檢查應轉為 pass，證明本檢查可用來驗證矛盾已解除。"""
        acceptance = ["pending 為零與非零兩情形皆有測試覆蓋"]
        where_files = [
            ".claude/hooks/parallel-suggestion-hook.py",
            ".claude/hooks/tests/test_parallel_suggestion_hook.py",
        ]
        status, items, _ = check_acceptance_writeset_consistency(acceptance, where_files)
        assert status == "pass"
        assert items == []


# ---------------------------------------------------------------------------
# CLI 整合測試（mock load_ticket）
# ---------------------------------------------------------------------------


def _args(ticket_id: str = "0.18.0-W17-053") -> argparse.Namespace:
    return argparse.Namespace(
        operation="dispatch-readiness",
        ticket_id=ticket_id,
        version=None,
    )


def _run(ticket_dict) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with patch(
        "ticket_system.lib.dispatch_common.load_ticket",
        return_value=ticket_dict,
    ), redirect_stdout(out), redirect_stderr(err):
        rc = execute_dispatch_readiness(_args(), "0.18.0")
    return rc, out.getvalue(), err.getvalue()


class TestExecuteDispatchReadiness:
    def test_ticket_not_found_returns_2(self):
        rc, _out, err = _run(None)
        assert rc == 2
        assert "不存在" in err

    def test_yaml_error_returns_2(self):
        rc, _out, err = _run({"_yaml_error": "bad yaml"})
        assert rc == 2
        assert "YAML" in err

    def test_all_pass_returns_0(self):
        ticket = {
            "_body": "## Context Bundle\n\n短內容\n",
            "acceptance": ["a", "b"],
            "where": {"files": ["a.py", "b.py"]},
        }
        rc, out, _err = _run(ticket)
        assert rc == 0
        assert "全數通過" in out

    def test_warn_acceptance_returns_1(self):
        ticket = {
            "_body": "",
            "acceptance": ["a", "b", "c"],
            "where": {"files": []},
        }
        rc, out, _err = _run(ticket)
        assert rc == 1
        assert "軟性警告" in out

    def test_warn_files_returns_1(self):
        ticket = {
            "_body": "",
            "acceptance": ["a"],
            "where": {"files": [f"f{i}.py" for i in range(7)]},
        }
        rc, _out, _err = _run(ticket)
        assert rc == 1

    def test_fail_acceptance_returns_2(self):
        ticket = {
            "_body": "",
            "acceptance": ["a", "b", "c", "d", "e"],
            "where": {"files": []},
        }
        rc, out, _err = _run(ticket)
        assert rc == 2
        assert "拆 ticket" in out or "拆分" in out

    def test_fail_files_returns_2(self):
        ticket = {
            "_body": "",
            "acceptance": ["a"],
            "where": {"files": [f"f{i}.py" for i in range(12)]},
        }
        rc, _out, _err = _run(ticket)
        assert rc == 2

    def test_fail_cb_tokens_returns_2(self):
        ticket = {
            "_body": "## Context Bundle\n\n" + ("x" * 25000) + "\n",
            "acceptance": ["a"],
            "where": {"files": []},
        }
        rc, _out, _err = _run(ticket)
        assert rc == 2

    def test_fail_overrides_warn(self):
        # 一項 warn + 一項 fail → exit 2
        ticket = {
            "_body": "",
            "acceptance": ["a", "b", "c"],  # warn
            "where": {"files": [f"f{i}.py" for i in range(12)]},  # fail
        }
        rc, _out, _err = _run(ticket)
        assert rc == 2

    def test_check4_contradiction_warns_with_item_listed(self):
        """0.2.1-W3-249：檢查 4 命中矛盾時 exit 1，且矛盾條目印出於 stdout。"""
        ticket = {
            "_body": "",
            "acceptance": ["非 shim 套件的既有判定行為不變（回歸驗證）"],
            "where": {"files": ["check.py"]},
        }
        rc, out, _err = _run(ticket)
        assert rc == 1
        assert "回歸驗證" in out
        assert "啟發式" in out

    def test_check4_pass_does_not_affect_existing_three_thresholds(self):
        """AC3：既有三項閾值全 pass 且無測試關鍵詞矛盾時仍 exit 0（三項閾值行為不變）。"""
        ticket = {
            "_body": "## Context Bundle\n\n短內容\n",
            "acceptance": ["a", "b"],
            "where": {"files": ["a.py", "b.py"]},
        }
        rc, out, _err = _run(ticket)
        assert rc == 0
        assert "全數通過" in out
