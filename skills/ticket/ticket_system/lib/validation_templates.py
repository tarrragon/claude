"""validation_templates — AC 驗證模板規則庫（W5-001 Phase 3b-A）。

提供 5 個初期模板（npm_test_pass / coverage_threshold / lint_pass /
flaky_fixed / skipped_evaluated），依 §4 表格規格硬編碼為模組級有序 tuple。

公開 API：
- ``match_template(ac_text)``: 大小寫無關子字串匹配，第一註冊者勝出，
  無匹配回 ``None``。
- ``list_templates()``: 回傳模組級不可變 tuple，外部無法修改規則庫。

設計決策（來源 W5-001 Phase 1 §5 決策 3）：
- 規則庫硬編碼於 Python 模組級常數，不走 YAML 熱載入。
- 所有資料類別使用 ``@dataclass(frozen=True)`` 保障不可變性。
- ``patterns`` 字串全部小寫；匹配時輸入 ``ac_text.lower()`` 後做 ``in`` 比對。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


# ---------------------------------------------------------------------------
# 資料結構（§2 資料結構定義）
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Template:
    """驗證模板規格。

    對應 W5-001 Phase 1 §2 與 §4 表格欄位。patterns 為小寫關鍵字片段，
    命中任一子字串即視為匹配。
    """

    name: str
    patterns: tuple[str, ...]
    command: str | None
    timeout_sec: int
    parse_strategy: Literal["tail_lines", "exit_code", "coverage_number", "manual"]
    unverifiable_reason: str | None


@dataclass(frozen=True)
class ValidationCommand:
    """match_template 的回傳值：模板匹配後組裝的可執行驗證指令。

    ``is_verifiable`` 為 derive 欄位（``command is not None``），
    呼叫端可直接以布林分流，不需檢查 ``command`` 是否為 None。
    """

    template_name: str
    command: str | None
    timeout_sec: int
    parse_strategy: Literal["tail_lines", "exit_code", "coverage_number", "manual"]
    is_verifiable: bool
    unverifiable_reason: str | None


# ---------------------------------------------------------------------------
# 模板註冊表（§4 表格；順序嚴格為第一註冊者勝出的依據）
# ---------------------------------------------------------------------------


_TEMPLATES: tuple[Template, ...] = (
    Template(
        name="npm_test_pass",
        patterns=(
            "npm test",
            "測試全部通過",
            "測試通過率 100",
            "0 個失敗",
            "0 failed",
        ),
        command="npm test 2>&1 | tail -5",
        timeout_sec=300,
        parse_strategy="tail_lines",
        unverifiable_reason=None,
    ),
    Template(
        name="coverage_threshold",
        patterns=(
            "覆蓋率",
            "coverage",
        ),
        command="npm run test:coverage 2>&1 | tail -20",
        timeout_sec=300,
        parse_strategy="coverage_number",
        unverifiable_reason=None,
    ),
    Template(
        name="lint_pass",
        patterns=(
            "lint 通過",
            "無 lint 錯誤",
            "eslint",
        ),
        command="npm run lint",
        timeout_sec=60,
        parse_strategy="exit_code",
        unverifiable_reason=None,
    ),
    Template(
        name="flaky_fixed",
        patterns=(
            "flaky",
            "間歇性失敗",
        ),
        command=None,
        timeout_sec=0,
        parse_strategy="manual",
        unverifiable_reason="flaky 判定需人工審查連續多次執行結果",
    ),
    Template(
        name="skipped_evaluated",
        patterns=(
            "skipped 測試已評估",
            "skipped 已評估",
            "skip 已審查",
        ),
        command=None,
        timeout_sec=0,
        parse_strategy="manual",
        unverifiable_reason="skipped 理由需人工判斷是否可接受",
    ),
)


# ---------------------------------------------------------------------------
# 公開 API
# ---------------------------------------------------------------------------


def match_template(ac_text: str) -> ValidationCommand | None:
    """依 AC 文字匹配驗證模板。

    匹配規則：
    - 空字串或僅含空白 → ``None``。
    - 其餘情況：``ac_text.lower()`` 後，以有序遍歷 ``_TEMPLATES``，
      任一 pattern 子字串命中即回傳該模板對應的 ``ValidationCommand``。
    - 多模板同時命中時，第一註冊者勝出（決定性保證）。
    - 完全無匹配回 ``None``（呼叫端可藉此區分「無匹配」與「匹配但不可驗證」）。

    Args:
        ac_text: AC 驗收條件文字（單一條目）。大小寫無關。

    Returns:
        ValidationCommand | None: 匹配成功時回傳組裝後的驗證指令物件；
            若輸入為空字串／空白，或無任何模板匹配，回傳 ``None``。
            匹配到不可驗證模板時回傳 ``ValidationCommand`` 且其 ``command`` 為 ``None``、
            ``is_verifiable`` 為 ``False``。

    Raises:
        無（純查詢函式，不拋出例外）。
    """

    if not ac_text.strip():
        return None

    normalized = ac_text.lower()
    for template in _TEMPLATES:
        for pattern in template.patterns:
            if pattern in normalized:
                return ValidationCommand(
                    template_name=template.name,
                    command=template.command,
                    timeout_sec=template.timeout_sec,
                    parse_strategy=template.parse_strategy,
                    is_verifiable=template.command is not None,
                    unverifiable_reason=template.unverifiable_reason,
                )
    return None


def list_templates() -> tuple[Template, ...]:
    """回傳目前註冊的模板清單。

    回傳模組級常數 ``_TEMPLATES`` tuple 本身，不另做拷貝。
    tuple 與 Template（frozen dataclass）均不可變，呼叫端無法透過
    回傳值污染內部規則庫。

    Returns:
        tuple[Template, ...]: 模組級不可變 tuple，元素依註冊順序排列。
            呼叫端不可對此 tuple 做 append/clear/修改元素等操作
            （tuple 本身不支援，Template 為 frozen dataclass）。

    Raises:
        無（純查詢函式，不拋出例外）。
    """

    return _TEMPLATES
