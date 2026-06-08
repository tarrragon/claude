"""
ANA Spawn Consistency Checker - ANA Solution spawn 規劃 vs 實際 ticket 數量一致性檢查

對應 Ticket 0.18.0-W17-167 (ANA) → 0.18.0-W17-168 (IMP)：
ANA complete 前比對 Solution 章節 spawn 規劃表格（IMP/DOC/ANA + P0-P3）
與 frontmatter spawned_tickets + children 數量。

檢查邏輯：
  1. 僅對 type=ANA ticket 觸發
  2. 解析 ## Solution 章節
  3. 若含豁免標記（「無需建 ticket」「不 spawn」）→ 跳過
  4. 正則匹配 spawn 表格行 `| (IMP|DOC|ANA) | ... | P[0-3] |` → 計算 N
  5. 計算 S+C（spawned_tickets + children 數量）
  6. 分級偵測：
     - N == 0 → 通過（無規劃即無檢查需求）
     - N > 0 且 S+C == 0 → 阻擋 complete
     - N > 0 且 S+C < N → 警告（不阻擋）
     - N > 0 且 S+C >= N → 通過

Why: acceptance 勾選「產出 spawned 清單」只檢文字產出，不檢 ticket 實際建立。
此檢查在 complete 時攔截「寫了規劃但沒建 ticket」的斷裂（W17-162 / W17-167 / W11-003.6 案例）。

Consequence: 不加此檢查，ANA Solution 的 spawn 規劃會靜默遺忘。

Action: ANA complete 前 hook 強制比對；豁免機制讓合法不 spawn 的 ANA 通過。
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple


# 豁免標記：Solution 含這些字樣時跳過檢查
_EXEMPTION_MARKERS: List[str] = [
    "無需建 ticket",
    "無需建ticket",
    "不 spawn",
    "不spawn",
    "no spawn needed",
]

# spawn 表格行正則：匹配 `| IMP |` / `| DOC |` / `| ANA |`，且同行含 P0-P3
# 範例：`| 1 | IMP | P1 | 標題 | 範圍 | 代理人 |`
_SPAWN_ROW_PATTERN = re.compile(
    r"^\s*\|.*?\|\s*(IMP|DOC|ANA)\s*\|.*?\bP[0-3]\b.*\|",
    re.MULTILINE,
)

# heading-based spawn 偵測：H3 標題同時含 Spawn 關鍵字與 IMP/DOC/ANA 任一
# 涵蓋 W17-176 案例（key-value 表格格式 spawn 規劃，row-per-spawn 正則漏判）
# 範例命中：`### Spawned IMP 規劃` / `### Spawn 規劃 (DOC)` / `### Spawned DOC/ANA 清單`
# 範例不命中：`### 根因分析` / `### Implementation Plan`（無 Spawn 關鍵字）
_SPAWN_HEADING_PATTERN = re.compile(
    r"^###\s+.*?\bSpawn(?:ed)?\b.*?\b(?:IMP|DOC|ANA)\b.*$",
    re.MULTILINE | re.IGNORECASE,
)


def _extract_solution_section(content: str) -> Optional[str]:
    """擷取 ## Solution 區段（到下一個 ## 或檔尾為止）。"""
    pattern = r"^## Solution\s*\n(.*?)(?=^## |\Z)"
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
    if not match:
        return None
    section = match.group(1)
    # 移除 HTML 註解（模板 placeholder）
    section = re.sub(r"<!--.*?-->", "", section, flags=re.DOTALL)
    return section


def _has_exemption_marker(section: str) -> bool:
    """檢查 Solution 是否含豁免標記。"""
    lowered = section.lower()
    for marker in _EXEMPTION_MARKERS:
        if marker.lower() in lowered:
            return True
    return False


def _count_spawn_planning_rows(section: str) -> int:
    """計算 Solution 內 spawn 規劃表格行數（IMP/DOC/ANA + P0-P3）。"""
    matches = _SPAWN_ROW_PATTERN.findall(section)
    return len(matches)


def _count_spawn_heading_rows(section: str) -> int:
    """計算 Solution 內 H3 標題含 Spawn + IMP/DOC/ANA 的數量（heading-based 偵測）。

    用於補強 row-per-spawn 漏判場景：W17-176 案例使用 key-value 格式表格
    描述單一 spawn 規劃（無同行 type+priority），row-per-spawn 正則 N=0
    但語義上確實為 1 項 spawn 規劃。

    每個命中的 H3 視為 1 項 spawn 規劃。
    """
    matches = _SPAWN_HEADING_PATTERN.findall(section)
    return len(matches)


def _count_spawn_planning(section: str) -> int:
    """整合雙策略：N = max(row-per-spawn 計數, heading-based 計數)。

    - row-per-spawn：每行一個 spawn（如 W17-162 / W17-167 多項規劃表）
    - heading-based：每個 H3 一個 spawn（如 W17-176 key-value 單項規劃表）

    取較大值避免漏判；兩策略適用不同表格樣式，不會在同一規劃中同時計數。
    """
    n_rows = _count_spawn_planning_rows(section)
    n_headings = _count_spawn_heading_rows(section)
    return max(n_rows, n_headings)


def _count_spawned_and_children(frontmatter: dict) -> int:
    """計算 frontmatter spawned_tickets + children 的有效數量。"""
    total = 0
    for field in ("spawned_tickets", "children"):
        raw = frontmatter.get(field, []) or []
        if isinstance(raw, list):
            total += len([item for item in raw if str(item).strip()])
        elif isinstance(raw, str):
            for line in raw.split("\n"):
                line = line.strip()
                if line.startswith("-"):
                    item = line[1:].strip()
                    if item:
                        total += 1
    return total


def check_ana_spawn_consistency(
    content: str, frontmatter: dict, logger
) -> Tuple[bool, Optional[str]]:
    """檢查 ANA Solution spawn 規劃 vs spawned_tickets + children 一致性。

    Args:
        content: ticket 完整內容（含 frontmatter + body）
        frontmatter: 已解析的 frontmatter dict
        logger: 日誌物件

    Returns:
        (should_block, message)
            - should_block=True：阻擋 complete（含完整阻擋訊息）
            - should_block=False + message：警告（不阻擋）
            - should_block=False + None：通過
    """
    ticket_type = (frontmatter.get("type") or "").strip().upper()
    if ticket_type != "ANA":
        logger.debug("非 ANA ticket（type=%s），跳過 spawn 一致性檢查", ticket_type)
        return False, None

    ticket_id = frontmatter.get("id", "未知")

    section = _extract_solution_section(content)
    if section is None or not section.strip():
        logger.debug("ANA %s Solution 區段缺失或為空，跳過 spawn 一致性檢查", ticket_id)
        return False, None

    if _has_exemption_marker(section):
        logger.info("ANA %s Solution 含豁免標記，跳過 spawn 一致性檢查", ticket_id)
        return False, None

    n_planned = _count_spawn_planning(section)
    if n_planned == 0:
        logger.debug("ANA %s Solution 無 spawn 規劃表格行", ticket_id)
        return False, None

    n_actual = _count_spawned_and_children(frontmatter)

    if n_actual == 0:
        msg = _format_block_message(ticket_id, n_planned)
        logger.error(
            "ANA %s Solution 規劃 %d 項 spawn，spawned_tickets+children 皆空 - 阻擋 complete",
            ticket_id,
            n_planned,
        )
        return True, msg

    if n_actual < n_planned:
        msg = _format_warning_message(ticket_id, n_planned, n_actual)
        logger.warning(
            "ANA %s Solution 規劃 %d 項 spawn，但實際只有 %d 項（spawned+children）",
            ticket_id,
            n_planned,
            n_actual,
        )
        return False, msg

    logger.info(
        "ANA %s spawn 一致性通過：規劃=%d，實際=%d", ticket_id, n_planned, n_actual
    )
    return False, None


# ----------------------------------------------------------------------------
# 訊息格式化
# ----------------------------------------------------------------------------


def _format_block_message(ticket_id: str, n_planned: int) -> str:
    return (
        f"[ERROR] Acceptance Gate: ANA Ticket Solution spawn 規劃未落地\n"
        f"\n"
        f"Ticket: {ticket_id}\n"
        f"Solution 規劃 spawn 數: {n_planned}\n"
        f"frontmatter spawned_tickets + children: 0\n"
        f"\n"
        f"修復方式（擇一）：\n"
        f"  1. 為每項規劃建 ticket：`ticket track create ...` 後填入 spawned_tickets 或使用 --parent\n"
        f"  2. 若不需 spawn，在 Solution 顯性標註豁免理由，例如：\n"
        f"     「無需建 ticket：[具體理由]」\n"
        f"\n"
        f"參考：quality-baseline.md 規則 5\n"
    )


def _format_warning_message(ticket_id: str, n_planned: int, n_actual: int) -> str:
    return (
        f"[WARNING] Acceptance Gate: ANA Ticket Solution spawn 規劃部分漏建\n"
        f"\n"
        f"Ticket: {ticket_id}\n"
        f"Solution 規劃 spawn 數: {n_planned}\n"
        f"frontmatter spawned_tickets + children: {n_actual}\n"
        f"\n"
        f"請確認是否有遺漏的 spawn ticket 未建立。\n"
        f"若部分項目決定不建，請在 Solution 補註「無需建 ticket：[理由]」並重新計算。\n"
    )
