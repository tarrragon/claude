#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
整合測試：YAML 折行延續行修復 x hook_protection_acceptance checker 的交互。

背景：hook_protection_acceptance checker 對 acceptance 前三項必含關鍵詞的
判定（`_join_acceptance_text` + `_missing_categories`）依賴
`frontmatter.get("acceptance")` 的完整文字內容。當 acceptance 單一項目文字
夠長觸發 pyyaml 折行（width=80 預設）時，若解析器（`_parse_yaml_lines`）未
正確併回折行延續行，關鍵詞落在延續行（折行後第二行起）的部分會被靜默捨棄，
導致 checker 誤判「缺該項」（false negative on completeness）——即使撰寫者
已在 acceptance 中完整寫明前三項語意。

第四項「產生路徑盤點結果」自 0.2.1-W3-533 起改為命中 `how.strategy`（非
acceptance），本檔的 `_build_ticket_content` 額外附上一個可正確被
`_parse_yaml_lines` 重組的 how.strategy 盤點表（避免使用巢狀欄位不支援的
`|-`/`>-` 區塊標記、避免 3 個以上連續 `-` 觸發 frontmatter 結尾誤判——皆為
本測試過程中實測發現的既有解析器限制，改用單一 `-` 分隔列規避），確保本檔
「should_block is False」的斷言反映的是折行修復本身，不因第四項而意外阻擋。

本測試走「原始 YAML 文字 → parse_ticket_frontmatter → 完整解析結果 →
check_hook_protection_acceptance」的端到端路徑（而非直接建構 frontmatter
dict 餵給 checker，那樣會繞過本次要驗證的解析器層）。
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

_hooks_dir = Path(__file__).parent.parent
if str(_hooks_dir) not in sys.path:
    sys.path.insert(0, str(_hooks_dir))

from lib import parse_ticket_frontmatter  # noqa: E402
from acceptance_checkers.hook_protection_acceptance_checker import (  # noqa: E402
    check_hook_protection_acceptance,
)


@pytest.fixture
def logger():
    log = logging.getLogger("test-hook-protection-yaml-folding")
    log.addHandler(logging.NullHandler())
    log.setLevel(logging.CRITICAL)
    return log


def _wrap(frontmatter_body: str) -> str:
    return "---\n" + frontmatter_body + "\n---\n\n# Body\n"


# 手工構造折行位置：acceptance 前三項語意（含關鍵詞「liveness」「失敗語意」）
# 刻意分散於折行前後，「liveness」與「失敗語意」落在延續行（第二行起），
# 模擬 pyyaml 對長 acceptance 項目折行後的真實輸出格式（延續行縮排 = dash
# 縮排 + 2，不以 "- " 開頭）。內文殘留的「產生路徑盤點：2 條，覆蓋 2 條」字樣
# 屬歷史遺留（第四項改命中 how.strategy 前的舊格式），對 checker 判定已無
# 作用，僅驗證解析器仍正確重組完整文字（見
# test_parser_reassembles_full_item_across_fold）。
_LONG_ACCEPTANCE_ITEM_LINE_1 = (
    "[x] 既有 session 生效策略：本次修改屬既有已載入 hook 的原始碼變更，本 session 內對後續呼叫立即生效"
)
_LONG_ACCEPTANCE_ITEM_LINE_2 = (
    "  liveness 驗證方式為比對 hook-logs 輸出，失敗語意為 fail-open，"
    "產生路徑盤點：2 條，覆蓋 2 條"
)
_FULL_ITEM_TEXT = (
    _LONG_ACCEPTANCE_ITEM_LINE_1 + " " + _LONG_ACCEPTANCE_ITEM_LINE_2.strip()
)


# 有效的產生路徑盤點表（供 how.strategy 使用）。改用 `|` 字面區塊純量標記
# （0.2.1-W3-665.2 遷移 yaml.safe_load 後）：plain scalar 折行語意下「換行 →
# 空白」，若不加區塊標記，多行表格會被摺成單行導致 checker 的
# `parse_path_inventory_table` 找不到表頭列與分隔列的行界（本測試過程中
# 實測發現）。`|` 標記明確保留每個換行，與真實 ticket CLI（`yaml.dump`
# 寫入、`yaml.safe_load` 讀回）對多段落內容的行為一致。
_HOW_STRATEGY_INVENTORY_TABLE = (
    "  strategy: |\n"
    "    策略說明。\n"
    "    | 產生路徑 | 是否覆蓋 |\n"
    "    |-|-|\n"
    "    | 經工具正常寫入 | 是 |\n"
)


def _build_ticket_content(where_files) -> str:
    where_files_lines = "\n".join(f"  - {f}" for f in where_files)
    return _wrap(
        "id: 0.0.0-W1-999\n"
        "type: IMP\n"
        "where:\n"
        "  files:\n"
        f"{where_files_lines}\n"
        "how:\n"
        "  task_type: Implementation\n"
        f"{_HOW_STRATEGY_INVENTORY_TABLE}"
        "acceptance:\n"
        f"- '{_LONG_ACCEPTANCE_ITEM_LINE_1}\n"
        f"{_LONG_ACCEPTANCE_ITEM_LINE_2}'"
    )


class TestFoldedAcceptanceItemReachesHookProtectionChecker:
    def test_parser_reassembles_full_item_across_fold(self, logger):
        """0.2.1-W3-518 修復本身：解析結果不再於折行處截斷。"""
        content = _build_ticket_content([".claude/hooks/some-new-guard-hook.py"])
        frontmatter = parse_ticket_frontmatter(content)

        acceptance = frontmatter.get("acceptance")
        assert acceptance == [_FULL_ITEM_TEXT]
        assert "liveness" in acceptance[0]
        assert "失敗語意" in acceptance[0]
        assert "產生路徑盤點" in acceptance[0]

    def test_hook_protection_checker_sees_all_three_categories_after_fold(self, logger):
        """YAML 折行延續行修復 x hook_protection_acceptance checker 交互：
        checker 透過完整解析後的 acceptance 正確判定前三項皆已提及，不再因
        折行截斷誤判缺項（false negative）；第四項另由 how.strategy 的有效
        盤點表滿足（見 `_HOW_STRATEGY_INVENTORY_TABLE`），確保本測試斷言的
        `should_block is False` 反映的是折行修復本身。"""
        content = _build_ticket_content([".claude/hooks/some-new-guard-hook.py"])
        frontmatter = parse_ticket_frontmatter(content)

        should_block, msg = check_hook_protection_acceptance(frontmatter, logger)

        assert should_block is False, (
            f"acceptance 已完整提及前三項語意（含折行延續行的 liveness / 失敗語意），"
            f"how.strategy 亦含有效盤點表，checker 不應誤判缺項並阻擋。實際訊息: {msg}"
        )
        assert msg is None

    def test_regression_guard_manually_truncated_acceptance_still_blocks(self, logger):
        """對照組：若 acceptance 真的只有折行前第一行（模擬修復前的錯誤解析結果）
        且未提供 how 欄位，checker 應正確判定缺 liveness / 失敗語意 / 產生路徑
        盤點結果三項並阻擋——證明 checker 本身邏輯未變，差異只在解析器是否
        正確餵給它完整文字。"""
        frontmatter = {
            "id": "0.0.0-W1-999",
            "type": "IMP",
            "where": {"files": [".claude/hooks/some-new-guard-hook.py"]},
            "acceptance": [_LONG_ACCEPTANCE_ITEM_LINE_1],
        }

        should_block, msg = check_hook_protection_acceptance(frontmatter, logger)

        assert should_block is True
        assert "liveness" in msg
        assert "失敗語意" in msg
        assert "產生路徑盤點結果" in msg
