#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Canonical Schema 清單一致性檢查 Hook

觸發時機: SessionStart
模式: 提醒為主（不阻擋操作），一致時靜默

動機（0.0.1-W1-006，承接 0.0.1-W1-004 成因分析）：`v2.12.0` 於建立端
`CANONICAL_BODY_SECTIONS` 新增 `Spawn Requests` 成員，但 3 份驗證端
`_SCHEMA_SECTION_NAMES` 清單與 2 份文件的章節清單未同步更新，5 處下游
定義同時失準並潛伏 15 天未被察覺（PC-BAL-001）。既有 hook 有版本一致性
檢查（spec-version-consistency-check-hook.py），獨缺 canonical 清單對
下游清單的比對。本 hook 補上此檢查，以建立端 `CANONICAL_BODY_SECTIONS`
為唯一基準（PC-BAL-001 判定順序），比對以下 5 處下游清單：

1. `hooks/acceptance_checkers/custom_h2_checker.py` `_SCHEMA_SECTION_NAMES`
2. `hooks/acceptance_checkers/execution_log_checker.py` `_SCHEMA_SECTION_NAMES`
3. `skills/ticket/ticket_system/lib/ticket_validator.py` `_SCHEMA_SECTION_NAMES`
4. `pm-rules/ticket-body-schema.md`（Schema 對照表第一欄 + 補列項）
5. `references/agent-definition-standard-details.md`（Schema 章節清單行）

不比對 `ticket_builder.py` 的 `SCHEMA_H2_SECTIONS`：該常數是
`CANONICAL_BODY_SECTIONS` 的直接參照別名（`= CANONICAL_BODY_SECTIONS`），
語言層級保證恆等，比對它只會恆為一致的雜訊。

已知既有落差（本 hook 的設計目的即讓其可見，非本 hook 待修復範圍）：
- 3 份驗證端清單目前不含 `Spawn Requests`（方案 A：驗證端直接 import
  建立端常數，屬上游框架依賴方向決策，已於 0.0.1-W1-006 明確排除）。

檢查邏輯（純文字 regex 擷取，不 import 目標模組，避免觸發套件初始化副作用，
與 spec-version-consistency-check-hook.py 一致的設計選擇）:
1. 從 constants.py 擷取 CANONICAL_BODY_SECTIONS 作為基準集合
2. 從 3 份驗證端 .py 檔擷取 _SCHEMA_SECTION_NAMES 列表
3. 從 2 份文件擷取章節清單（ticket-body-schema.md 取 Schema 對照表第一欄
   + 補列小節；agent-definition-standard-details.md 取行內 backtick 清單）
4. 逐一與基準集合比對差集，不一致時輸出警告並列出具體缺漏/多餘項
"""

import re
import sys
from pathlib import Path
from typing import List, NamedTuple, Optional, Set

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
from lib import setup_hook_logging, run_hook_safely, get_project_root

HOOK_NAME = "canonical-schema-consistency-check-hook"

CONSTANTS_PY = "skills/ticket/ticket_system/constants.py"

# 比對目標：(顯示名稱, 相對路徑, 擷取方式)
VALIDATOR_TARGETS = [
    ("custom_h2_checker.py", "hooks/acceptance_checkers/custom_h2_checker.py"),
    ("execution_log_checker.py", "hooks/acceptance_checkers/execution_log_checker.py"),
    ("ticket_validator.py", "skills/ticket/ticket_system/lib/ticket_validator.py"),
]

TICKET_BODY_SCHEMA_MD = "pm-rules/ticket-body-schema.md"
AGENT_DEFINITION_STANDARD_MD = "references/agent-definition-standard-details.md"

CANONICAL_PATTERN = re.compile(
    r"CANONICAL_BODY_SECTIONS\s*:\s*tuple\s*=\s*\((.*?)\)", re.DOTALL
)
SCHEMA_SECTION_NAMES_PATTERN = re.compile(
    r"_SCHEMA_SECTION_NAMES\s*(?::\s*List\[str\])?\s*=\s*\[(.*?)\]", re.DOTALL
)
QUOTED_ITEM_PATTERN = re.compile(r'"([^"]+)"')

# agent-definition-standard-details.md：`**Schema 章節清單**（來源 ...）：` 後的
# backtick 清單，以 ` / ` 分隔
BACKTICK_LIST_LINE_PATTERN = re.compile(r"\*\*Schema 章節清單\*\*[^\n]*：(.+)$", re.MULTILINE)
BACKTICK_ITEM_PATTERN = re.compile(r"`([^`]+)`")


class DriftResult(NamedTuple):
    """單一下游清單相對 canonical 基準的漂移結果"""

    label: str
    missing: List[str]
    extra: List[str]


def _clean_annotation(name: str) -> str:
    """去除章節名稱的括號附註（如「重現實驗結果（三子節）」→「重現實驗結果」）"""
    return re.sub(r"[（(].*?[）)]", "", name).strip()


def extract_canonical_sections(content: str) -> Optional[List[str]]:
    """從 constants.py 擷取 CANONICAL_BODY_SECTIONS 元組內容（保留順序）"""
    match = CANONICAL_PATTERN.search(content)
    if not match:
        return None
    return QUOTED_ITEM_PATTERN.findall(match.group(1))


def extract_schema_section_names(content: str) -> Optional[List[str]]:
    """從驗證端 .py 檔擷取 _SCHEMA_SECTION_NAMES 列表內容（保留順序）"""
    match = SCHEMA_SECTION_NAMES_PATTERN.search(content)
    if not match:
        return None
    return QUOTED_ITEM_PATTERN.findall(match.group(1))


def extract_ticket_body_schema_sections(content: str) -> Optional[List[str]]:
    """從 ticket-body-schema.md 擷取「## Schema 對照表」下第一張表格的第一欄章節名清單

    僅擷取緊接標題後的第一張表格（Section/ANA/IMP/DOC 對照表），不含後續的
    「狀態定義」等其他表格（該區段內尚有第二張表格，若不限制邊界會誤把
    「必填/選填/免填」等狀態值當成章節名）。
    """
    heading = "## Schema 對照表"
    start = content.find(heading)
    if start == -1:
        return None
    section = content[start + len(heading):]

    names: List[str] = []
    in_table = False
    for line in section.splitlines():
        stripped = line.strip()
        is_table_row = stripped.startswith("|") and stripped.endswith("|")
        if not is_table_row:
            if in_table:
                break  # 第一張表格已結束
            continue
        in_table = True
        cell = stripped.strip("|").split("|", 1)[0].strip()
        if cell in ("Section", "") or set(cell) <= {"-", ":"}:
            continue
        names.append(_clean_annotation(cell))

    return names or None


def extract_agent_definition_sections(content: str) -> Optional[List[str]]:
    """從 agent-definition-standard-details.md 擷取「Schema 章節清單」行的 backtick 清單"""
    match = BACKTICK_LIST_LINE_PATTERN.search(content)
    if not match:
        return None
    return [_clean_annotation(item) for item in BACKTICK_ITEM_PATTERN.findall(match.group(1))]


def _diff(label: str, canonical: Set[str], actual: List[str]) -> Optional[DriftResult]:
    """比對單一下游清單與 canonical 基準集合，回傳差異（無差異回傳 None）"""
    actual_set = set(actual)
    missing = sorted(canonical - actual_set)
    extra = sorted(actual_set - canonical)
    if not missing and not extra:
        return None
    return DriftResult(label=label, missing=missing, extra=extra)


def scan_schema_drifts(project_root: Path) -> List[DriftResult]:
    """掃描所有下游清單，回傳與 canonical 基準不一致的項目"""
    constants_path = project_root / ".claude" / CONSTANTS_PY
    try:
        constants_content = constants_path.read_text(encoding="utf-8")
    except OSError:
        return []

    canonical_list = extract_canonical_sections(constants_content)
    if not canonical_list:
        return []
    canonical_set = set(canonical_list)

    drifts: List[DriftResult] = []

    for label, rel_path in VALIDATOR_TARGETS:
        try:
            content = (project_root / ".claude" / rel_path).read_text(encoding="utf-8")
        except OSError:
            continue
        actual = extract_schema_section_names(content)
        if actual is None:
            continue
        drift = _diff(label, canonical_set, actual)
        if drift:
            drifts.append(drift)

    doc_extractors = [
        (TICKET_BODY_SCHEMA_MD, extract_ticket_body_schema_sections),
        (AGENT_DEFINITION_STANDARD_MD, extract_agent_definition_sections),
    ]
    for rel_path, extractor in doc_extractors:
        try:
            content = (project_root / ".claude" / rel_path).read_text(encoding="utf-8")
        except OSError:
            continue
        actual = extractor(content)
        if actual is None:
            continue
        drift = _diff(rel_path, canonical_set, actual)
        if drift:
            drifts.append(drift)

    return drifts


def format_drift_warning(drifts: List[DriftResult]) -> str:
    """將漂移結果格式化為警告訊息"""
    lines = [
        "[Canonical Schema Drift] 下游清單與 CANONICAL_BODY_SECTIONS（建立端）不一致："
    ]
    for drift in drifts:
        parts = []
        if drift.missing:
            parts.append(f"缺漏={drift.missing}")
        if drift.extra:
            parts.append(f"多餘={drift.extra}")
        lines.append(f"  - {drift.label}: {'; '.join(parts)}")
    lines.append(
        "  判定順序：以 constants.py 的 CANONICAL_BODY_SECTIONS 為準（PC-BAL-001），"
        "下游清單過期時應同步而非視為 canonical 有誤。"
    )
    return "\n".join(lines)


def main() -> int:
    """主函數"""
    logger = setup_hook_logging(HOOK_NAME)
    project_root = get_project_root()

    drifts = scan_schema_drifts(project_root)

    if not drifts:
        logger.info("Canonical schema 清單一致性檢查完成，無漂移")
        return 0

    warning = format_drift_warning(drifts)
    print(warning, file=sys.stderr)
    logger.warning(warning)
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
