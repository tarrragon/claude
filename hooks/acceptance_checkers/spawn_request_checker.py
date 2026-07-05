"""
Spawn Request Checker - Spawn Requests 章節處理狀態檢查

對應 Ticket 1.5.0-W5-024（1.5.0-W5-022 ANA 結論）：
agent 執行中透過 `ticket track add-spawn-request` 產生的 Spawn Requests 條目，
若在 ticket complete 前仍為 `status: pending`，代表 PM 尚未評估是否要建立對應
ticket（`processed`）或評估後決定不需要（`dismissed`）。

Why: Spawn Request 條目有確定性 schema（what/why/priority/type/status），
complete 前遺漏處理會讓建議靜默遺忘，違反 quality-baseline.md 規則 5
（所有發現必須追蹤）。

Consequence: 不加此檢查，PM 可能在未檢視 Spawn Requests 的情況下 complete
ticket，導致 agent 回報的後續建議未被評估即消失。

Action: complete 時掃描 Spawn Requests 章節，任何 `status: pending` 條目
產生 WARNING（不硬擋，PM 可 --force 或後續處理）。

條目格式（由 `add-spawn-request` CLI 生成，見
`.claude/skills/ticket/ticket_system/commands/track_acceptance.py`）：

    - **SR-N** (timestamp)
      - what: ...
      - why: ...
      - suggested_type: ...
      - suggested_priority: ...
      - related_files: ...
      - context: ...
      - status: pending

status 有效值：pending（未處理）、processed（已建 ticket）、dismissed（已評估不需要）。
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple


# Spawn Request 條目起始行：`- **SR-N** (timestamp)`
_SR_ENTRY_PATTERN = re.compile(r"^\s*-\s*\*\*(SR-\d+)\*\*", re.MULTILINE)

# status 欄位：`  - status: pending`
_STATUS_FIELD_PATTERN = re.compile(r"^\s*-\s*status\s*:\s*(\S+)\s*$", re.MULTILINE | re.IGNORECASE)

_VALID_STATUSES = ("pending", "processed", "dismissed")


def _extract_spawn_requests_section(content: str) -> Optional[str]:
    """擷取 ## Spawn Requests 區段內容（到下一個 ## 或檔尾為止）。"""
    pattern = r"^## Spawn Requests\s*\n(.*?)(?=^## |\Z)"
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
    if not match:
        return None
    section = match.group(1)
    # 移除 HTML 註解（模板佔位符）
    section = re.sub(r"<!--.*?-->", "", section, flags=re.DOTALL)
    return section


def _split_entries(section: str) -> List[str]:
    """依 SR-N 起始行切分區段為各條目的內文區塊。"""
    starts = list(_SR_ENTRY_PATTERN.finditer(section))
    if not starts:
        return []
    entries: List[str] = []
    for i, m in enumerate(starts):
        start = m.start()
        end = starts[i + 1].start() if i + 1 < len(starts) else len(section)
        entries.append(section[start:end])
    return entries


def _parse_status(entry: str) -> Optional[str]:
    match = _STATUS_FIELD_PATTERN.search(entry)
    if not match:
        return None
    return match.group(1).strip().strip("\"'`").lower()


def _parse_sr_label(entry: str) -> str:
    match = _SR_ENTRY_PATTERN.search(entry)
    return match.group(1) if match else "SR-?"


def check_spawn_requests(
    content: str, frontmatter: dict, logger
) -> Tuple[bool, Optional[str]]:
    """檢查 Ticket 的 Spawn Requests 章節是否有未處理（pending）條目。

    Args:
        content: Ticket 檔案完整內容
        frontmatter: 已解析的 frontmatter dict
        logger: 日誌物件

    Returns:
        (should_warn, warning_message)
            - should_warn=False：通過（無 Spawn Requests 章節或全數已處理）
            - should_warn=True：應輸出 WARNING（不阻擋 complete）
    """
    ticket_id = frontmatter.get("id", "未知")

    section = _extract_spawn_requests_section(content)
    if section is None or not section.strip():
        logger.debug("Ticket %s 無 Spawn Requests 章節，跳過檢查", ticket_id)
        return False, None

    entries = _split_entries(section)
    if not entries:
        logger.debug("Ticket %s Spawn Requests 章節無條目，跳過檢查", ticket_id)
        return False, None

    pending_labels: List[str] = []
    for entry in entries:
        status = _parse_status(entry)
        label = _parse_sr_label(entry)
        if status is None:
            # 缺少 status 欄位視為未處理，避免格式異常條目被靜默略過
            pending_labels.append(label)
            continue
        if status not in _VALID_STATUSES:
            logger.info(
                "Ticket %s %s status 值非預期: %s（視為未處理）", ticket_id, label, status
            )
            pending_labels.append(label)
            continue
        if status == "pending":
            pending_labels.append(label)

    if not pending_labels:
        logger.info("Ticket %s Spawn Requests 全數已處理", ticket_id)
        return False, None

    msg = _format_warning_message(ticket_id, pending_labels)
    logger.warning(
        "Ticket %s 有 %d 個未處理的 Spawn Request: %s",
        ticket_id,
        len(pending_labels),
        ", ".join(pending_labels),
    )
    return True, msg


def _format_warning_message(ticket_id: str, pending_labels: List[str]) -> str:
    return (
        f"[WARNING] Acceptance Gate: Spawn Requests 尚有未處理條目\n"
        f"\n"
        f"Ticket: {ticket_id}\n"
        f"未處理條目: {', '.join(pending_labels)}\n"
        f"\n"
        f"請評估每個 Spawn Request 是否需要建立對應 ticket：\n"
        f"  - 需要 -> 建立 ticket 後將該條目 status 改為 processed\n"
        f"  - 不需要 -> 將該條目 status 改為 dismissed 並附理由\n"
        f"\n"
        f"參考：quality-baseline.md 規則 5（所有發現必須追蹤）\n"
    )
