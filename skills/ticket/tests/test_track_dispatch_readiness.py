"""測試 ticket track dispatch-readiness 命令（0.18.0-W17-053 + 0.2.1-W3-249）。

涵蓋三項核心閾值 + 第四項一致性檢查 + 第五項路徑存在性檢查 + 第六項路徑
涵蓋性檢查 + exit code 矩陣：
- 閾值 1（功能職責數 / acceptance 近似）：≤2 pass / 3-4 warn / >4 fail
- 閾值 2（修改檔案數 where.files）：≤5 pass / 6-10 warn / >10 fail
- 閾值 3（Context Bundle tokens 近似）：≤3000 pass / 3001-5000 warn / >5000 fail
- 檢查 4（acceptance 測試類關鍵詞 vs where.files 測試路徑一致性）：
  無關鍵詞 pass / 命中但無測試路徑 warn（不含 fail）/ 命中且有測試路徑 pass
- 檢查 5（where.files 路徑存在性）：路徑全存在 pass / 不存在且 acceptance 無
  新建語意 warn（不含 fail）/ 不存在但 acceptance 含新建語意 pass
- 檢查 6（acceptance 提及路徑 vs where.files 涵蓋性）：未提及路徑 pass /
  提及且被涵蓋 pass / 提及但未涵蓋 fail（強制，唯一產生 fail 的啟發式檢查）
- ticket 不存在 / IO 錯誤 → exit 2
- 任一 fail → exit 2；任一 warn 無 fail → exit 1；全 pass → exit 0
"""

from __future__ import annotations

import argparse
import io
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from typing import Optional
from unittest.mock import patch

from ticket_system.commands.track_dispatch_readiness import (
    check_acceptance_path_coverage,
    check_acceptance_writeset_consistency,
    check_context_bundle_tokens,
    check_file_count,
    check_responsibility_count,
    check_where_paths_existence,
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

    def test_glob_mention_covered_by_full_path_pass(self):
        """0.2.1-W3-1147：acceptance 提及 glob 形式路徑（星號斷開字面 token，
        第六項檢查的字元類無法涵蓋），where.files 內有檔案可被該樣式 fnmatch
        涵蓋 → pass（以真實票面案例的路徑措辭為輸入，非人造字串）。"""
        acceptance = ["lib/l10n/generated/app_localizations*.dart 三份生成檔皆需同步更新版號"]
        where_files = [
            "lib/l10n/generated/app_localizations.dart",
            "lib/l10n/generated/app_localizations_en.dart",
            "lib/l10n/generated/app_localizations_zh.dart",
        ]
        status, items, _ = check_acceptance_writeset_consistency(acceptance, where_files)
        assert status == "pass"
        assert items == []

    def test_glob_mention_uncovered_warns(self):
        """反例：where.files 內無檔案可被該 glob 樣式涵蓋 → warn，且矛盾條目
        列出、訊息點名文件 ID 形態不在本檢查範圍。"""
        acceptance = ["lib/l10n/generated/app_localizations*.dart 三份生成檔皆需同步更新版號"]
        where_files = ["lib/l10n/generated/other_widget.dart"]
        status, items, msg = check_acceptance_writeset_consistency(acceptance, where_files)
        assert status == "warn"
        assert len(items) == 1
        assert "app_localizations*.dart" in items[0]
        assert "glob 路徑提及" in msg
        assert "SPEC-002" in msg and "PROP-003" in msg

    def test_glob_mention_bare_filename_covered_by_full_path_pass(self):
        """0.2.1-W3-1147 AC1：acceptance 寫裸檔名 glob、where.files 寫完整
        路徑，兩側正規化至同一粒度後不得產生 false positive。"""
        acceptance = ["app_localizations*.dart 三份生成檔皆需同步更新版號"]
        where_files = ["lib/l10n/generated/app_localizations_en.dart"]
        status, items, _ = check_acceptance_writeset_consistency(acceptance, where_files)
        assert status == "pass"
        assert items == []

    def test_glob_mention_and_keyword_both_matched_combined_in_message(self):
        """關鍵詞與 glob 兩種訊號同時命中時，兩者矛盾條目皆列出且訊息分別
        計數，不互相覆蓋。"""
        acceptance = [
            "新增測試涵蓋 app_localizations*.dart 的產出範圍",
        ]
        where_files = ["lib/l10n/generated/other_widget.dart"]  # 無測試路徑，glob 未涵蓋
        status, items, msg = check_acceptance_writeset_consistency(acceptance, where_files)
        assert status == "warn"
        assert len(items) == 1  # 同一條 acceptance 文字，兩訊號命中同一項不重複列
        assert "測試類關鍵詞" in msg and "glob 路徑提及" in msg

    def test_literal_uncovered_path_not_flagged_by_check4(self):
        """分工邊界：不含 `*` 的字面路徑提及一律歸第六項檢查（fail），本檢查
        （檢查 4）刻意不重複判定，避免同一 acceptance 條目被兩項檢查以不同
        severity 判定（見模組 docstring「與第六項檢查的分工」）。"""
        acceptance = ["核對 lib/l10n/generated/app_localizations.dart 內容是否正確"]
        where_files = ["lib/l10n/generated/other_widget.dart"]  # 未涵蓋，但屬檢查 6 範圍
        status, items, _ = check_acceptance_writeset_consistency(acceptance, where_files)
        assert status == "pass"
        assert items == []


class TestWherePathsExistence:
    """where.files 路徑存在性檢查（純函式，project_root 直接注入）。"""

    def test_all_exist_pass(self, tmp_path):
        (tmp_path / "a.py").write_text("", encoding="utf-8")
        status, missing, _ = check_where_paths_existence(["a.py"], ["實作"], tmp_path)
        assert status == "pass"
        assert missing == []

    def test_missing_without_creation_keyword_warns(self, tmp_path):
        status, missing, msg = check_where_paths_existence(
            ["not-there.py"], ["修正既有邏輯"], tmp_path
        )
        assert status == "warn"
        assert missing == ["not-there.py"]
        assert "啟發式" in msg

    def test_missing_with_creation_keyword_pass(self, tmp_path):
        status, missing, _ = check_where_paths_existence(
            ["not-there.py"], ["新增測試檔涵蓋此情境"], tmp_path
        )
        assert status == "pass"
        assert missing == []

    def test_empty_files_pass(self, tmp_path):
        status, missing, _ = check_where_paths_existence([], ["a"], tmp_path)
        assert status == "pass"
        assert missing == []


class TestAcceptancePathCoverage:
    """0.2.1-W3-1221：acceptance 提及的檔案路徑須落在 where.files 內，否則 fail。"""

    def test_no_path_mentioned_pass(self):
        status, uncovered, _ = check_acceptance_path_coverage(
            ["實作查重邏輯", "回歸驗證既有行為不變"], ["a.py"]
        )
        assert status == "pass"
        assert uncovered == []

    def test_mentioned_basename_covered_by_full_path_pass(self):
        status, uncovered, _ = check_acceptance_path_coverage(
            ["核對 SKILL.md 並直接修文件"],
            [".claude/skills/framework-issue/SKILL.md"],
        )
        assert status == "pass"
        assert uncovered == []

    def test_mentioned_basename_uncovered_fail(self):
        """0.2.1-W3-1217.3 實例：acceptance 要求核對 SKILL.md，但 where.files
        只列了另兩個檔案——此為本檢查應攔下的宣告不一致。"""
        status, uncovered, msg = check_acceptance_path_coverage(
            ["核對 SKILL.md 並直接修文件"],
            [
                ".claude/skills/framework-issue/scripts/section_comment.py",
                ".claude/skills/framework-issue/tests/test_section_comment.py",
            ],
        )
        assert status == "fail"
        assert uncovered == ["SKILL.md"]
        assert "where.files" in msg

    def test_mentioned_full_path_covered_pass(self):
        status, uncovered, _ = check_acceptance_path_coverage(
            ["確認 .claude/skills/ticket/SKILL.md 內容與實作一致"],
            [".claude/skills/ticket/SKILL.md"],
        )
        assert status == "pass"
        assert uncovered == []

    def test_mentioned_full_path_uncovered_fail(self):
        status, uncovered, _ = check_acceptance_path_coverage(
            ["確認 .claude/skills/ticket/SKILL.md 內容與實作一致"],
            [".claude/skills/ticket/ticket_system/commands/track_dispatch_readiness.py"],
        )
        assert status == "fail"
        assert uncovered == [".claude/skills/ticket/SKILL.md"]

    def test_phase_notation_not_treated_as_path(self):
        """「3a/3b」等 Phase 標號不具已知副檔名，不應誤判為路徑。"""
        status, uncovered, _ = check_acceptance_path_coverage(
            ["TDD Phase 3a/3b 皆需通過"], ["a.py"]
        )
        assert status == "pass"
        assert uncovered == []

    def test_ticket_id_not_treated_as_path(self):
        status, uncovered, _ = check_acceptance_path_coverage(
            ["承接 0.2.1-W3-1217.3 的驗收結論"], ["a.py"]
        )
        assert status == "pass"
        assert uncovered == []

    def test_where_files_intent_marker_stripped_before_match(self):
        status, uncovered, _ = check_acceptance_path_coverage(
            ["核對 SKILL.md 並直接修文件"],
            [".claude/skills/framework-issue/SKILL.md::read"],
        )
        assert status == "pass"
        assert uncovered == []

    def test_empty_acceptance_pass(self):
        status, uncovered, _ = check_acceptance_path_coverage(None, [])
        assert status == "pass"
        assert uncovered == []


# ---------------------------------------------------------------------------
# CLI 整合測試（mock load_ticket + get_project_root）
# ---------------------------------------------------------------------------


def _args(ticket_id: str = "0.18.0-W17-053") -> argparse.Namespace:
    return argparse.Namespace(
        operation="dispatch-readiness",
        ticket_id=ticket_id,
        version=None,
    )


def _seed_where_files(root: Path, ticket_dict: dict) -> None:
    """在 root 下建立 ticket_dict['where']['files'] 列出的每個檔案。

    檢查 5 新增後，既有測試用的假路徑（a.py / f0.py 等）若不預先建立會被
    判定為不存在而觸發非預期的 warn，故整合測試統一以 tmp_path 作為
    project_root 並預先建檔，維持既有三項閾值 + 檢查 4 的測試意圖不變。
    """
    for token in (ticket_dict.get("where", {}) or {}).get("files", []) or []:
        path = token.split("::", 1)[0]
        if not path:
            continue
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("", encoding="utf-8")


def _run(
    ticket_dict: Optional[dict], tmp_path: Path, *, seed: bool = True
) -> tuple[int, str, str]:
    if ticket_dict is not None and seed:
        _seed_where_files(tmp_path, ticket_dict)
    out, err = io.StringIO(), io.StringIO()
    with patch(
        "ticket_system.lib.dispatch_common.load_ticket",
        return_value=ticket_dict,
    ), patch(
        "ticket_system.commands.track_dispatch_readiness.get_project_root",
        return_value=tmp_path,
    ), redirect_stdout(out), redirect_stderr(err):
        rc = execute_dispatch_readiness(_args(), "0.18.0")
    return rc, out.getvalue(), err.getvalue()


class TestExecuteDispatchReadiness:
    def test_ticket_not_found_returns_2(self, tmp_path):
        rc, _out, err = _run(None, tmp_path)
        assert rc == 2
        assert "不存在" in err

    def test_yaml_error_returns_2(self, tmp_path):
        rc, _out, err = _run({"_yaml_error": "bad yaml"}, tmp_path)
        assert rc == 2
        assert "YAML" in err

    def test_all_pass_returns_0(self, tmp_path):
        ticket = {
            "_body": "## Context Bundle\n\n短內容\n",
            "acceptance": ["a", "b"],
            "where": {"files": ["a.py", "b.py"]},
        }
        rc, out, _err = _run(ticket, tmp_path)
        assert rc == 0
        assert "全數通過" in out

    def test_warn_acceptance_returns_1(self, tmp_path):
        ticket = {
            "_body": "",
            "acceptance": ["a", "b", "c"],
            "where": {"files": []},
        }
        rc, out, _err = _run(ticket, tmp_path)
        assert rc == 1
        assert "軟性警告" in out

    def test_warn_files_returns_1(self, tmp_path):
        ticket = {
            "_body": "",
            "acceptance": ["a"],
            "where": {"files": [f"f{i}.py" for i in range(7)]},
        }
        rc, _out, _err = _run(ticket, tmp_path)
        assert rc == 1

    def test_fail_acceptance_returns_2(self, tmp_path):
        ticket = {
            "_body": "",
            "acceptance": ["a", "b", "c", "d", "e"],
            "where": {"files": []},
        }
        rc, out, _err = _run(ticket, tmp_path)
        assert rc == 2
        assert "拆 ticket" in out or "拆分" in out

    def test_fail_files_returns_2(self, tmp_path):
        ticket = {
            "_body": "",
            "acceptance": ["a"],
            "where": {"files": [f"f{i}.py" for i in range(12)]},
        }
        rc, _out, _err = _run(ticket, tmp_path)
        assert rc == 2

    def test_fail_cb_tokens_returns_2(self, tmp_path):
        ticket = {
            "_body": "## Context Bundle\n\n" + ("x" * 25000) + "\n",
            "acceptance": ["a"],
            "where": {"files": []},
        }
        rc, _out, _err = _run(ticket, tmp_path)
        assert rc == 2

    def test_fail_overrides_warn(self, tmp_path):
        # 一項 warn + 一項 fail → exit 2
        ticket = {
            "_body": "",
            "acceptance": ["a", "b", "c"],  # warn
            "where": {"files": [f"f{i}.py" for i in range(12)]},  # fail
        }
        rc, _out, _err = _run(ticket, tmp_path)
        assert rc == 2

    def test_check4_contradiction_warns_with_item_listed(self, tmp_path):
        """0.2.1-W3-249：檢查 4 命中矛盾時 exit 1，且矛盾條目印出於 stdout。"""
        ticket = {
            "_body": "",
            "acceptance": ["非 shim 套件的既有判定行為不變（回歸驗證）"],
            "where": {"files": ["check.py"]},
        }
        rc, out, _err = _run(ticket, tmp_path)
        assert rc == 1
        assert "回歸驗證" in out
        assert "啟發式" in out

    def test_check4_pass_does_not_affect_existing_three_thresholds(self, tmp_path):
        """AC3：既有三項閾值全 pass 且無測試關鍵詞矛盾時仍 exit 0（三項閾值行為不變）。"""
        ticket = {
            "_body": "## Context Bundle\n\n短內容\n",
            "acceptance": ["a", "b"],
            "where": {"files": ["a.py", "b.py"]},
        }
        rc, out, _err = _run(ticket, tmp_path)
        assert rc == 0
        assert "全數通過" in out

    def test_check5_missing_path_without_creation_keyword_warns(self, tmp_path):
        """檢查 5：路徑不存在且 acceptance 無新建語意 → warn，exit 1。"""
        ticket = {
            "_body": "",
            "acceptance": ["修正既有排序邏輯"],
            "where": {"files": ["not-there.py"]},
        }
        rc, out, _err = _run(ticket, tmp_path, seed=False)
        assert rc == 1
        assert "not-there.py" in out
        assert "路徑存在性" in out

    def test_check5_missing_path_with_creation_keyword_pass(self, tmp_path):
        """檢查 5：路徑不存在但 acceptance 含新建語意 → pass，不影響 exit code。"""
        ticket = {
            "_body": "## Context Bundle\n\n短內容\n",
            "acceptance": ["新增設定檔案供此情境使用"],
            "where": {"files": ["not-there.py"]},
        }
        rc, out, _err = _run(ticket, tmp_path, seed=False)
        assert rc == 0
        assert "全數通過" in out

    def test_check5_all_exist_does_not_affect_pass(self, tmp_path):
        """檢查 5：路徑全存在時不影響既有 pass 結論。"""
        ticket = {
            "_body": "## Context Bundle\n\n短內容\n",
            "acceptance": ["a", "b"],
            "where": {"files": ["a.py", "b.py"]},
        }
        rc, out, _err = _run(ticket, tmp_path)
        assert rc == 0
        assert "全數通過" in out

    def test_check6_mentioned_path_uncovered_fails(self, tmp_path):
        """0.2.1-W3-1221：acceptance 提及 SKILL.md 但 where.files 未涵蓋 → fail，exit 2。"""
        ticket = {
            "_body": "",
            "acceptance": ["核對 SKILL.md 並直接修文件"],
            "where": {"files": ["section_comment.py"]},
        }
        rc, out, _err = _run(ticket, tmp_path)
        assert rc == 2
        assert "SKILL.md" in out
        assert "where.files" in out

    def test_check6_mentioned_path_covered_passes(self, tmp_path):
        """反例：acceptance 提及的路徑已在 where.files 內 → 不影響 pass 結論。"""
        ticket = {
            "_body": "## Context Bundle\n\n短內容\n",
            "acceptance": ["核對 SKILL.md 並直接修文件"],
            "where": {"files": ["SKILL.md"]},
        }
        rc, out, _err = _run(ticket, tmp_path)
        assert rc == 0
        assert "全數通過" in out

    def test_check4_glob_mention_uncovered_warns(self, tmp_path):
        """0.2.1-W3-1147：檢查 4 涵蓋 glob 形式路徑提及，未涵蓋時 exit 1，
        且訊息點名文件 ID 形態不在本檢查範圍（AC2）。"""
        ticket = {
            "_body": "",
            "acceptance": [
                "lib/l10n/generated/app_localizations*.dart 三份生成檔皆需同步更新版號"
            ],
            "where": {"files": ["lib/l10n/generated/other_widget.dart"]},
        }
        rc, out, _err = _run(ticket, tmp_path)
        assert rc == 1
        assert "app_localizations*.dart" in out
        assert "SPEC-002" in out and "PROP-003" in out

    def test_check4_glob_mention_covered_does_not_affect_pass(self, tmp_path):
        """反例：glob 樣式已被 where.files 涵蓋 → 不影響 pass 結論。"""
        ticket = {
            "_body": "## Context Bundle\n\n短內容\n",
            "acceptance": [
                "lib/l10n/generated/app_localizations*.dart 三份生成檔皆需同步更新版號"
            ],
            "where": {
                "files": [
                    "lib/l10n/generated/app_localizations.dart",
                    "lib/l10n/generated/app_localizations_en.dart",
                    "lib/l10n/generated/app_localizations_zh.dart",
                ]
            },
        }
        rc, out, _err = _run(ticket, tmp_path)
        assert rc == 0
        assert "全數通過" in out
