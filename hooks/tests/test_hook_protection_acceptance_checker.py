"""
Hook Protection Acceptance Checker Tests

驗證防護類 hook ticket 的必含項目：前三項（本 session 實地觸發確認／
liveness／失敗語意）命中對象為 acceptance；第四項（產生路徑盤點結果）命中
對象為 how.strategy（缺則 Solution）的盤點表正本，行為三分（absent 阻擋 /
ok 輸出計數 / failed fail-open）。

第一項的 label 於 2026-08-18 由「既有 session 生效策略」改名（PC-BAL-033
v2.0.0 機制收窄，需驗的是本 session 實地觸發而非 session 世代）。本檔對該
label 的斷言必須跟著改名——其中兩處為 `not in missing_section` 形式，若只改
產品碼不改測試，它們會在標籤不再存在時恆真通過，從有效斷言退化為空斷言，
且不會紅燈提醒。偵測關鍵詞清單刻意未動（見 checker 內註解），故 fixture 的
acceptance 原措辭無須改寫。

覆蓋情境（前三項，substring 關鍵詞機制，命中對象不變）：
  (a) type=IMP + where.files 觸及 .claude/hooks/ + 前三項皆缺 → block，
      訊息列出三項（第四項因預設 fixture 含有效表格而不列入）
  (b) type=IMP + where.files 觸及 .claude/hooks/ + 前三項皆有 + 有效表格
      → 通過
  (c) 只缺一項（前三項之一） → block，訊息只列該項
  (d) 合格填法「本 wave 該防護不生效，改以人工紀律承擔」→ 視為已提及第一項
  (e) type 非 IMP（ANA/DOC/ADJ）→ 跳過，即使 where.files 觸及 hooks 目錄
  (f) where.files 不觸及 hooks 目錄（一般 IMP 票）→ 跳過
  (g) where.files 觸及 .claude/skills/<skill>/hooks/（非頂層 .claude/hooks/）
      → 仍觸發
  (h) 路徑前綴混淆防護：.claude/hooks-backup/ 不應被字串 startswith 誤判為
      .claude/hooks/ 的子路徑（PurePosixPath 邊界正確性）
  (i) touches_hook_protection_scope 單元測試（路徑判定邊界）

覆蓋情境（第四項「產生路徑盤點結果」，命中對象改為 how.strategy／Solution）：
  (j) how.strategy 與 Solution 皆缺席（表格完全缺席）→ block，訊息指出正本
      應寫於 how.strategy 並附格式範例
  (j2) how.strategy 非空但不含表格（Solution 有效表格）→ block，訊息須點明
      「非空即不 fallback」讀取優先序，並附 set-how --strategy 寫入指引
  (k) how.strategy 含有效表格 → 不阻擋，logger.info 輸出「盤點 N 條、覆蓋 M
      條、未覆蓋 K 條」三個實際數字
  (l) how.strategy 表格格式不符預期（缺覆蓋欄／儲存格非「是/否」）→
      fail-open：不阻擋、不拋例外，logger.warning 記錄且略過計數輸出
  (m) how.strategy 為空、Solution 章節有效表格（fallback）→ 不阻擋且輸出計數
  (n) 迴歸案例：acceptance 不含任何盤點數字宣告，但 how.strategy 有有效表格
      → 仍通過（0.2.1-W3-533 拿掉 acceptance 副本宣告要求）
  (o) parse_path_inventory_table / _extract_solution_section 單元測試
      （表格偵測與解析邊界）

覆蓋情境（各項通過提示，吸收自攔截點分工節補強）：
  (p) 四項皆通過時，logger.info 附帶指向 ticket-body-schema 攔截點分工節的
      提示；提示不改變 should_block 回傳值（仍為 False，msg 仍為 None）
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

_hooks_dir = Path(__file__).parent.parent
if str(_hooks_dir) not in sys.path:
    sys.path.insert(0, str(_hooks_dir))

from acceptance_checkers.hook_protection_acceptance_checker import (  # noqa: E402
    check_hook_protection_acceptance,
    touches_hook_protection_scope,
    parse_path_inventory_table,
    _extract_solution_section,
)


@pytest.fixture
def logger():
    log = logging.getLogger("test-hook-protection-acceptance")
    log.addHandler(logging.NullHandler())
    log.setLevel(logging.CRITICAL)
    return log


# 有效的產生路徑盤點表（格式見 ticket-body-schema.md「防護類 hook ticket
# 額外 acceptance」節）。供「僅測前三項邏輯」的既有情境沿用，確保這些情境
# 仍是「整體通過」而非因第四項而意外阻擋。3 條路徑、1 條覆蓋、2 條未覆蓋。
_VALID_INVENTORY_TABLE = (
    "| 產生路徑 | 是否覆蓋 | 未覆蓋原因 |\n"
    "|---------|---------|-----------|\n"
    "| 經工具正常寫入 | 是 | — |\n"
    "| 先寫註冊後建檔（順序調換） | 否 | 檢查時目標尚不存在，走 fail-open |\n"
    "| 經 VCS 合併寫入 | 否 | 未經該工具路徑 |\n"
)


def _fm(ticket_type: str, where_files, acceptance, how_strategy: str = _VALID_INVENTORY_TABLE) -> dict:
    return {
        "id": "0.2.1-W99-999",
        "type": ticket_type,
        "where": {"files": where_files},
        "acceptance": acceptance,
        "how": {"task_type": "Implementation", "strategy": how_strategy},
    }


# ---------------------------------------------------------------------------
# (a) 前三項皆缺 → block，訊息列出三項（第四項因 fixture 預設有效表格而不列入）
# ---------------------------------------------------------------------------


def test_all_three_missing_blocks_and_lists_all(logger):
    fm = _fm(
        "IMP",
        [".claude/hooks/new-guard-hook.py"],
        ["[ ] 新增守衛偵測 X"],
    )
    should_block, msg = check_hook_protection_acceptance(fm, logger)
    assert should_block is True
    assert "本 session 實地觸發確認" in msg
    assert "liveness" in msg
    assert "失敗語意" in msg
    assert "產生路徑盤點結果" not in msg.split("合格填法範例")[0]


# ---------------------------------------------------------------------------
# (b) 前三項皆有 + 有效表格 → 通過
# ---------------------------------------------------------------------------


def test_all_present_passes(logger):
    fm = _fm(
        "IMP",
        [".claude/hooks/new-guard-hook.py"],
        [
            "[ ] 本 session 不生效，下個 session 才會被 runtime 載入",
            "[ ] 以 liveness 日誌比對確認 hook 已被觸發",
            "[ ] 異常時 fail-closed，回傳 exit 2",
        ],
    )
    should_block, msg = check_hook_protection_acceptance(fm, logger)
    assert should_block is False
    assert msg is None


# ---------------------------------------------------------------------------
# (c) 只缺一項（前三項之一） → block，訊息只列該項
# ---------------------------------------------------------------------------


def test_only_one_missing_blocks_and_lists_only_that_one(logger):
    fm = _fm(
        "IMP",
        [".claude/hooks/new-guard-hook.py"],
        [
            "[ ] 本 session 不生效，需重啟才生效",
            "[ ] 以 liveness 日誌比對確認 hook 已被觸發",
            # 缺失敗語意
        ],
    )
    should_block, msg = check_hook_protection_acceptance(fm, logger)
    assert should_block is True
    missing_section = msg.split("依規範必須補齊以下項目，缺少：")[1]
    missing_section = missing_section.split("合格填法範例")[0]
    assert "失敗語意" in missing_section
    assert "本 session 實地觸發確認" not in missing_section
    assert "liveness" not in missing_section
    assert "產生路徑盤點結果" not in missing_section


# ---------------------------------------------------------------------------
# (d) 合格填法：部署期政策用語視為已提及第一項
# ---------------------------------------------------------------------------


def test_deployment_policy_wording_counts_as_session_strategy(logger):
    """用戶裁示的合格填法：「本 wave 該防護不生效，改以人工紀律承擔」。"""
    fm = _fm(
        "IMP",
        [".claude/hooks/new-guard-hook.py"],
        [
            "[ ] 本 wave 該防護不生效，改以人工紀律承擔",
            "[ ] 以 liveness 日誌比對確認 hook 已被觸發",
            "[ ] 異常時 fail-open，僅記錄不阻擋",
        ],
    )
    should_block, msg = check_hook_protection_acceptance(fm, logger)
    assert should_block is False
    assert msg is None


# ---------------------------------------------------------------------------
# (e) 非 IMP type → 跳過
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ticket_type", ["ANA", "DOC", "ADJ"])
def test_non_imp_type_skips_even_when_touching_hooks(logger, ticket_type):
    fm = _fm(ticket_type, [".claude/hooks/new-guard-hook.py"], ["[ ] 隨便寫"], how_strategy="")
    should_block, msg = check_hook_protection_acceptance(fm, logger)
    assert should_block is False
    assert msg is None


# ---------------------------------------------------------------------------
# (f) where.files 不觸及 hooks 目錄 → 跳過
# ---------------------------------------------------------------------------


def test_imp_not_touching_hooks_directory_skips(logger):
    fm = _fm("IMP", ["lib/models/foo.dart", "test/foo_test.dart"], ["[ ] 隨便寫"], how_strategy="")
    should_block, msg = check_hook_protection_acceptance(fm, logger)
    assert should_block is False
    assert msg is None


# ---------------------------------------------------------------------------
# (g) skill hooks 目錄同樣觸發（W3-511 教訓）
# ---------------------------------------------------------------------------


def test_skill_hooks_directory_triggers_same_as_top_level(logger):
    fm = _fm(
        "IMP",
        [".claude/skills/myskill/hooks/guard.py"],
        ["[ ] 隨便寫"],
        how_strategy="",
    )
    should_block, msg = check_hook_protection_acceptance(fm, logger)
    assert should_block is True
    assert "本 session 實地觸發確認" in msg


def test_skill_root_without_hooks_subdir_does_not_trigger(logger):
    """skill 目錄本身（非 hooks/ 子目錄）不在觸發範圍。"""
    fm = _fm("IMP", [".claude/skills/myskill/SKILL.md"], ["[ ] 隨便寫"], how_strategy="")
    should_block, msg = check_hook_protection_acceptance(fm, logger)
    assert should_block is False


# ---------------------------------------------------------------------------
# (h) 路徑前綴混淆防護
# ---------------------------------------------------------------------------


def test_hooks_backup_directory_not_confused_with_hooks(logger):
    """`.claude/hooks-backup/` 不應被字串 startswith 誤判為 `.claude/hooks/`
    的子路徑（PurePosixPath 邊界正確性，非本 checker 觸發範圍）。
    """
    fm = _fm("IMP", [".claude/hooks-backup/old-guard.py"], ["[ ] 隨便寫"], how_strategy="")
    should_block, msg = check_hook_protection_acceptance(fm, logger)
    assert should_block is False


# ---------------------------------------------------------------------------
# (i) touches_hook_protection_scope 單元測試
# ---------------------------------------------------------------------------


class TestTouchesHookProtectionScope:
    def test_top_level_hooks_file(self):
        assert touches_hook_protection_scope(".claude/hooks/foo.py") is True

    def test_top_level_hooks_dir_itself(self):
        assert touches_hook_protection_scope(".claude/hooks") is True

    def test_top_level_hooks_nested_subdir(self):
        assert touches_hook_protection_scope(".claude/hooks/tests/test_foo.py") is True

    def test_skill_hooks_file(self):
        assert touches_hook_protection_scope(".claude/skills/ticket/hooks/x.py") is True

    def test_skill_hooks_nested_subdir(self):
        assert touches_hook_protection_scope(".claude/skills/ticket/hooks/sub/x.py") is True

    def test_hooks_backup_not_matched(self):
        assert touches_hook_protection_scope(".claude/hooks-backup/x.py") is False

    def test_unrelated_path_not_matched(self):
        assert touches_hook_protection_scope("lib/models/foo.dart") is False

    def test_skill_non_hooks_subdir_not_matched(self):
        assert touches_hook_protection_scope(".claude/skills/ticket/scripts/x.py") is False

    def test_empty_path_not_matched(self):
        assert touches_hook_protection_scope("") is False

    def test_leading_slash_and_dot_slash_normalized(self):
        assert touches_hook_protection_scope("./.claude/hooks/foo.py") is True
        assert touches_hook_protection_scope("/.claude/hooks/foo.py") is True


# ---------------------------------------------------------------------------
# (j) how.strategy 與 Solution 皆缺席 → block，訊息指出正本應寫於
#     how.strategy 並附格式範例
# ---------------------------------------------------------------------------


def test_inventory_table_absent_blocks_and_points_to_how_strategy(logger):
    fm = _fm(
        "IMP",
        [".claude/hooks/new-guard-hook.py"],
        [
            "[ ] 本 session 不生效，需重啟才生效",
            "[ ] 以 liveness 日誌比對確認 hook 已被觸發",
            "[ ] 異常時 fail-closed，回傳 exit 2",
        ],
        how_strategy="",
    )
    should_block, msg = check_hook_protection_acceptance(fm, logger, content="")
    assert should_block is True
    missing_section = msg.split("依規範必須補齊以下項目，缺少：")[1]
    missing_section = missing_section.split("合格填法範例")[0]
    assert "產生路徑盤點結果" in missing_section
    assert "本 session 實地觸發確認" not in missing_section
    assert "liveness" not in missing_section
    assert "失敗語意" not in missing_section
    # 訊息須指出正本位置（how.strategy）並附格式範例
    assert "how.strategy" in msg
    assert "產生路徑" in msg
    assert "是否覆蓋" in msg


# ---------------------------------------------------------------------------
# (j2) how.strategy 非空但不含表格、Solution 有效表格 → block，訊息須點明
#      「非空即不 fallback」的讀取優先序，並指引正確寫入位置（0.2.1-W3-581：
#      566 收尾實測，執行者把表寫進 Solution 反覆不過，根因是 how.strategy
#      已有其他策略文字擋住 fallback，原訊息未講明此優先序）
# ---------------------------------------------------------------------------


def test_how_strategy_non_empty_without_table_explains_no_fallback_priority(logger):
    fm = _fm(
        "IMP",
        [".claude/hooks/new-guard-hook.py"],
        [
            "[ ] 本 session 不生效，需重啟才生效",
            "[ ] 以 liveness 日誌比對確認 hook 已被觸發",
            "[ ] 異常時 fail-closed，回傳 exit 2",
        ],
        how_strategy="改用正規表達式解析新增的設定檔格式，避免逐行字串比對。",
    )
    content = "---\nid: X\n---\n\n## Solution\n\n" + _VALID_INVENTORY_TABLE + "\n## Test Results\n\n"
    should_block, msg = check_hook_protection_acceptance(fm, logger, content=content)

    assert should_block is True, (
        "how.strategy 非空（即使不含表格）不應 fallback 讀 Solution，"
        "即使 Solution 有有效表格仍須阻擋"
    )
    # 訊息須明講讀取優先序：非空即不 fallback，而非「沒表格才 fallback」
    assert "非空" in msg
    assert "不會讀 Solution" in msg
    # 訊息須指引正確寫入位置：既有策略文字須併入 how.strategy，附具體指令
    assert "set-how" in msg
    assert "--strategy" in msg


# ---------------------------------------------------------------------------
# (k) how.strategy 含有效表格 → 不阻擋，logger.info 輸出三個實際數字
# ---------------------------------------------------------------------------


def test_valid_inventory_table_passes_and_logs_counts(logger, caplog):
    fm = _fm(
        "IMP",
        [".claude/hooks/new-guard-hook.py"],
        [
            "[ ] 本 session 不生效，需重啟才生效",
            "[ ] 以 liveness 日誌比對確認 hook 已被觸發",
            "[ ] 異常時 fail-closed，回傳 exit 2",
        ],
    )
    with caplog.at_level(logging.INFO, logger="test-hook-protection-acceptance"):
        should_block, msg = check_hook_protection_acceptance(fm, logger)

    assert should_block is False
    assert msg is None
    info_records = [r.message for r in caplog.records if r.levelno == logging.INFO]
    assert any(
        "盤點 3 條" in text and "覆蓋 1 條" in text and "未覆蓋 2 條" in text
        for text in info_records
    )


# ---------------------------------------------------------------------------
# (l) how.strategy 表格格式不符預期 → fail-open：不阻擋、記錄 warning、略過
#     計數輸出
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "malformed_table",
    [
        # 缺「是否覆蓋」欄（表頭只有兩欄）
        "| 產生路徑 | 說明 |\n|---|---|\n| 經工具正常寫入 | 沒問題 |\n",
        # 儲存格值非「是/否」
        "| 產生路徑 | 是否覆蓋 | 未覆蓋原因 |\n|---|---|---|\n| 經工具正常寫入 | 部分 | 未知 |\n",
        # 表頭與分隔列存在但無任何資料列
        "| 產生路徑 | 是否覆蓋 | 未覆蓋原因 |\n|---|---|---|\n",
    ],
)
def test_malformed_inventory_table_fails_open(logger, caplog, malformed_table):
    fm = _fm(
        "IMP",
        [".claude/hooks/new-guard-hook.py"],
        [
            "[ ] 本 session 不生效，需重啟才生效",
            "[ ] 以 liveness 日誌比對確認 hook 已被觸發",
            "[ ] 異常時 fail-closed，回傳 exit 2",
        ],
        how_strategy=malformed_table,
    )
    with caplog.at_level(logging.WARNING, logger="test-hook-protection-acceptance"):
        should_block, msg = check_hook_protection_acceptance(fm, logger)

    # fail-open：不阻擋、不拋例外（未拋例外已由測試未 raise 隱性驗證）
    assert should_block is False
    assert msg is None
    warning_records = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert any("格式不符預期" in text for text in warning_records)
    info_records = [r.message for r in caplog.records if r.levelno == logging.INFO]
    assert not any("盤點" in text and "條、覆蓋" in text for text in info_records)


# ---------------------------------------------------------------------------
# (m) how.strategy 為空、Solution 章節有效表格（fallback）→ 不阻擋且輸出計數
# ---------------------------------------------------------------------------


def test_solution_section_fallback_when_how_strategy_empty(logger, caplog):
    fm = _fm(
        "IMP",
        [".claude/hooks/new-guard-hook.py"],
        [
            "[ ] 本 session 不生效，需重啟才生效",
            "[ ] 以 liveness 日誌比對確認 hook 已被觸發",
            "[ ] 異常時 fail-closed，回傳 exit 2",
        ],
        how_strategy="",
    )
    content = (
        "---\nid: 0.2.1-W99-999\n---\n\n"
        "# Execution Log\n\n"
        "## Solution\n\n"
        + _VALID_INVENTORY_TABLE
        + "\n## Test Results\n\n（略）\n"
    )
    with caplog.at_level(logging.INFO, logger="test-hook-protection-acceptance"):
        should_block, msg = check_hook_protection_acceptance(fm, logger, content=content)

    assert should_block is False
    assert msg is None
    info_records = [r.message for r in caplog.records if r.levelno == logging.INFO]
    assert any("盤點 3 條" in text for text in info_records)


def test_how_strategy_present_takes_priority_over_solution(logger, caplog):
    """how.strategy 非空時優先採用，不查看 Solution（即使 Solution 也有表格，
    計數應以 how.strategy 內容為準）。"""
    how_strategy_table = (
        "| 產生路徑 | 是否覆蓋 | 未覆蓋原因 |\n"
        "|---|---|---|\n"
        "| 唯一路徑 | 是 | — |\n"
    )
    fm = _fm(
        "IMP",
        [".claude/hooks/new-guard-hook.py"],
        [
            "[ ] 本 session 不生效，需重啟才生效",
            "[ ] 以 liveness 日誌比對確認 hook 已被觸發",
            "[ ] 異常時 fail-closed，回傳 exit 2",
        ],
        how_strategy=how_strategy_table,
    )
    content = "---\nid: X\n---\n\n## Solution\n\n" + _VALID_INVENTORY_TABLE + "\n## Test Results\n\n"
    with caplog.at_level(logging.INFO, logger="test-hook-protection-acceptance"):
        should_block, msg = check_hook_protection_acceptance(fm, logger, content=content)

    assert should_block is False
    info_records = [r.message for r in caplog.records if r.levelno == logging.INFO]
    # how.strategy 僅 1 條路徑（is 覆蓋），不應是 Solution 的 3 條
    assert any("盤點 1 條" in text and "覆蓋 1 條" in text and "未覆蓋 0 條" in text for text in info_records)


# ---------------------------------------------------------------------------
# (n) 迴歸案例：acceptance 不含任何盤點數字宣告，但 how.strategy 有有效表格
#     → 仍通過（0.2.1-W3-533 拿掉 acceptance 副本宣告要求）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "acceptance_without_inventory_declaration",
    [
        ["[ ] 回歸測試覆蓋 effort low/high 與 complete/非 complete 四種組合"],
        ["[ ] whitelist 測試補 parametrize 覆蓋新增兩項，非僅改數字"],
        ["[ ] 測試覆蓋兩種模式"],
    ],
)
def test_acceptance_without_digit_declaration_still_passes_when_how_strategy_valid(
    logger, acceptance_without_inventory_declaration
):
    base_acceptance = [
        "[ ] 本 session 不生效，需重啟才生效",
        "[ ] 以 liveness 日誌比對確認 hook 已被觸發",
        "[ ] 異常時 fail-closed，回傳 exit 2",
    ] + acceptance_without_inventory_declaration
    fm = _fm("IMP", [".claude/hooks/new-guard-hook.py"], base_acceptance)
    should_block, msg = check_hook_protection_acceptance(fm, logger)
    assert should_block is False
    assert msg is None


# ---------------------------------------------------------------------------
# (o) parse_path_inventory_table / _extract_solution_section 單元測試
# ---------------------------------------------------------------------------


class TestParsePathInventoryTable:
    def test_valid_table_returns_ok_with_correct_counts(self):
        result = parse_path_inventory_table(_VALID_INVENTORY_TABLE)
        assert result.status == "ok"
        assert result.total == 3
        assert result.covered == 1
        assert result.uncovered == 2

    def test_empty_text_returns_absent(self):
        assert parse_path_inventory_table("").status == "absent"

    def test_whitespace_only_text_returns_absent(self):
        assert parse_path_inventory_table("   \n  \n").status == "absent"

    def test_prose_without_table_returns_absent(self):
        text = "產生路徑盤點：4 條（工具寫入／順序調換／VCS 合併／skill 私有目錄），覆蓋 2 條"
        assert parse_path_inventory_table(text).status == "absent"

    def test_table_without_coverage_column_returns_failed(self):
        text = "| 產生路徑 | 說明 |\n|---|---|\n| A | ok |\n"
        assert parse_path_inventory_table(text).status == "failed"

    def test_table_with_non_binary_cell_returns_failed(self):
        text = "| 產生路徑 | 是否覆蓋 |\n|---|---|\n| A | 部分 |\n"
        assert parse_path_inventory_table(text).status == "failed"

    def test_table_header_only_no_data_rows_returns_failed(self):
        text = "| 產生路徑 | 是否覆蓋 |\n|---|---|\n"
        assert parse_path_inventory_table(text).status == "failed"

    def test_table_with_prose_before_and_after(self):
        text = (
            "第一段策略說明，與盤點無關的文字。\n\n"
            + _VALID_INVENTORY_TABLE
            + "\n後續補充說明。"
        )
        result = parse_path_inventory_table(text)
        assert result.status == "ok"
        assert result.total == 3

    def test_single_dash_separator_still_recognized(self):
        text = "| 產生路徑 | 是否覆蓋 |\n|-|-|\n| A | 是 |\n"
        result = parse_path_inventory_table(text)
        assert result.status == "ok"
        assert result.total == 1
        assert result.covered == 1

    def test_row_shorter_than_coverage_index_returns_failed(self):
        text = "| 產生路徑 | 說明 | 是否覆蓋 |\n|---|---|---|\n| A |\n"
        assert parse_path_inventory_table(text).status == "failed"


class TestExtractSolutionSection:
    def test_extracts_content_between_solution_and_next_heading(self):
        content = "---\nid: X\n---\n\n## Problem Analysis\n\n背景\n\n## Solution\n\n實作內容\n\n## Test Results\n\n測試\n"
        assert _extract_solution_section(content) == "實作內容"

    def test_solution_at_end_of_file(self):
        content = "---\nid: X\n---\n\n## Solution\n\n最後一段\n"
        assert _extract_solution_section(content) == "最後一段"

    def test_no_solution_section_returns_empty(self):
        content = "---\nid: X\n---\n\n## Problem Analysis\n\n背景\n"
        assert _extract_solution_section(content) == ""

    def test_empty_content_returns_empty(self):
        assert _extract_solution_section("") == ""


# ---------------------------------------------------------------------------
# (p) 各項通過時附帶攔截點分工節提示，提示不改變 should_block 回傳值
# ---------------------------------------------------------------------------


def test_all_pass_logs_interception_point_hint(logger, caplog):
    fm = _fm(
        "IMP",
        [".claude/hooks/new-guard-hook.py"],
        [
            "[ ] 本 session 不生效，下個 session 才會被 runtime 載入",
            "[ ] 以 liveness 日誌比對確認 hook 已被觸發",
            "[ ] 異常時 fail-closed，回傳 exit 2",
        ],
    )
    with caplog.at_level(logging.INFO, logger="test-hook-protection-acceptance"):
        should_block, msg = check_hook_protection_acceptance(fm, logger)

    # 提示不改變 should_block / msg 回傳值
    assert should_block is False
    assert msg is None

    info_records = [r.message for r in caplog.records if r.levelno == logging.INFO]
    assert any("ticket-body-schema.md" in text for text in info_records)
    assert any("攔截點" in text for text in info_records)


def test_blocked_case_does_not_log_interception_point_hint(logger, caplog):
    """未通過（should_block=True）時不應附帶攔截點分工節提示——該提示只在
    必含項目齊備、防護面已就緒的正向路徑才有意義。"""
    fm = _fm(
        "IMP",
        [".claude/hooks/new-guard-hook.py"],
        ["[ ] 新增守衛偵測 X"],
        how_strategy="",
    )
    with caplog.at_level(logging.INFO, logger="test-hook-protection-acceptance"):
        should_block, msg = check_hook_protection_acceptance(fm, logger)

    assert should_block is True
    info_records = [r.message for r in caplog.records if r.levelno == logging.INFO]
    assert not any("攔截點" in text for text in info_records)
