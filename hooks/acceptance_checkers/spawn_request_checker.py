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
from dataclasses import dataclass
from typing import List, Optional, Tuple


# Spawn Request 條目起始行：`- **SR-N** (timestamp)`
_SR_ENTRY_PATTERN = re.compile(r"^\s*-\s*\*\*(SR-\d+)\*\*", re.MULTILINE)

# status 欄位（嚴格）：值為 `pending`/`processed`/`dismissed` 三者之一，
# 可選緊接（無空白）全形括號附註（`resolve-spawn-request` CLI 實際寫入
# 格式，如 `processed（已建 <ticket-id>）`，見
# `ticket_system/commands/track_acceptance.py`
# `_build_spawn_request_status_value`）。建立端為權威來源（tool-output-
# trust-rules 規則 6），此正則對齊其產出格式，非反向要求 CLI 改輸出。
#
# 附註格式以外的裝飾（半形括號、箭頭、日期等自由文字，如
# `processed (date) -> other-id`）刻意不匹配、維持 unparseable
# fail-closed——這類格式代表非本 CLI 產生的手改內容，語意不明確，仍應
# 由 PM 人工核實而非靜默放行。
_STATUS_FIELD_PATTERN = re.compile(
    r"^\s*-\s*status\s*:\s*(pending|processed|dismissed)(?:（(.*)）)?\s*$",
    re.MULTILINE | re.IGNORECASE,
)

# status 欄位（寬鬆）：偵測 `- status:` 行是否存在（不限值格式）
_STATUS_LINE_LOOSE_PATTERN = re.compile(r"^\s*-\s*status\s*:\s*(.+)$", re.MULTILINE | re.IGNORECASE)

_VALID_STATUSES = ("pending", "processed", "dismissed")


@dataclass
class _StatusParseResult:
    kind: str  # "parsed" | "unparseable" | "missing"
    value: Optional[str] = None
    raw_line: Optional[str] = None
    note: str = ""


@dataclass(frozen=True)
class SpawnRequestEntry:
    """單一 Spawn Request 條目的解析結果（公開型別，供其他 checker 共用）。

    `note` 取自 status 值後方全形括號內的附註（`resolve-spawn-request` CLI
    在 `--reason` / `--spawned-ticket` 有值時寫入），無附註時為空字串。
    """

    label: str
    status: Optional[str]  # pending / processed / dismissed；無法解析或缺欄位時為 None
    note: str
    parse_kind: str  # "parsed" | "unparseable" | "missing"

    @property
    def is_resolved(self) -> bool:
        """是否為已判定終態。

        `processed` 代表已建票（CLI 於 `--spawned-ticket` 有值時同步回填
        `spawned_tickets`）；`dismissed` 代表評估後不建，須附理由才算判定完成
        ——無理由的 dismissed 與 pending 一樣缺少可稽核依據，不視為終態。
        """
        if self.parse_kind != "parsed":
            return False
        if self.status == "processed":
            return True
        return self.status == "dismissed" and bool(self.note.strip())


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


def _parse_status(entry: str) -> _StatusParseResult:
    strict = _STATUS_FIELD_PATTERN.search(entry)
    if strict:
        value = strict.group(1).strip().strip("\"'`").lower()
        note = (strict.group(2) or "").strip()
        return _StatusParseResult(kind="parsed", value=value, note=note)

    loose = _STATUS_LINE_LOOSE_PATTERN.search(entry)
    if loose:
        return _StatusParseResult(kind="unparseable", raw_line=loose.group(0).strip())

    return _StatusParseResult(kind="missing")


def _parse_sr_label(entry: str) -> str:
    match = _SR_ENTRY_PATTERN.search(entry)
    return match.group(1) if match else "SR-?"


def iter_spawn_request_entries(content: str) -> List[SpawnRequestEntry]:
    """解析 Ticket 內容的 Spawn Requests 章節，回傳各條目的狀態。

    本函式是 Spawn Request 狀態解析的唯一入口，供本模組與
    `ana_spawn_consistency_checker` 共用——status 行的合法格式、fail-closed
    判讀（無法解析或缺欄位一律不視為已判定）皆定義於此，避免兩處各自維護
    正則而漂移。

    無 Spawn Requests 章節、章節為空、或章節內無 `SR-N` 條目時回傳空列表。
    """
    section = _extract_spawn_requests_section(content)
    if section is None or not section.strip():
        return []

    entries: List[SpawnRequestEntry] = []
    for entry_text in _split_entries(section):
        result = _parse_status(entry_text)
        status = result.value if result.kind == "parsed" else None
        if status is not None and status not in _VALID_STATUSES:
            # 值非預期時降級為 unparseable，與 check_spawn_requests 的判讀一致
            entries.append(
                SpawnRequestEntry(
                    label=_parse_sr_label(entry_text),
                    status=None,
                    note="",
                    parse_kind="unparseable",
                )
            )
            continue
        entries.append(
            SpawnRequestEntry(
                label=_parse_sr_label(entry_text),
                status=status,
                note=result.note,
                parse_kind=result.kind,
            )
        )
    return entries


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
    unparseable_entries: List[Tuple[str, str]] = []
    missing_labels: List[str] = []

    for entry in entries:
        result = _parse_status(entry)
        label = _parse_sr_label(entry)

        if result.kind == "parsed":
            if result.value not in _VALID_STATUSES:
                logger.info(
                    "Ticket %s %s status 值非預期: %s（視為未處理）",
                    ticket_id, label, result.value,
                )
                unparseable_entries.append((label, f"  - status: {result.value}"))
            elif result.value == "pending":
                pending_labels.append(label)
        elif result.kind == "unparseable":
            logger.info(
                "Ticket %s %s status 行無法解析: %s", ticket_id, label, result.raw_line
            )
            unparseable_entries.append((label, result.raw_line or ""))
        elif result.kind == "missing":
            missing_labels.append(label)

    all_unprocessed = (
        pending_labels
        + [e[0] for e in unparseable_entries]
        + missing_labels
    )
    if not all_unprocessed:
        logger.info("Ticket %s Spawn Requests 全數已處理", ticket_id)
        return False, None

    msg = _format_warning_message(
        ticket_id, pending_labels, unparseable_entries, missing_labels
    )
    logger.warning(
        "Ticket %s 有 %d 個未處理的 Spawn Request: %s",
        ticket_id,
        len(all_unprocessed),
        ", ".join(all_unprocessed),
    )
    return True, msg


def _format_warning_message(
    ticket_id: str,
    pending_labels: List[str],
    unparseable_entries: List[Tuple[str, str]],
    missing_labels: List[str],
) -> str:
    lines = [
        "[WARNING] Acceptance Gate: Spawn Requests 尚有未處理條目",
        "",
        f"Ticket: {ticket_id}",
    ]

    if pending_labels:
        lines.append("")
        lines.append(f"  status: pending（未處理）: {', '.join(pending_labels)}")

    if unparseable_entries:
        lines.append("")
        lines.append("  status 行無法解析（fail-closed 視為未處理）:")
        for label, raw_line in unparseable_entries:
            lines.append(f"    {label}: 實際內容 `{raw_line}`")
        lines.append("    期望格式: `  - status: pending|processed|dismissed`")

    if missing_labels:
        lines.append("")
        lines.append(
            f"  status 欄位缺失（fail-closed 視為未處理）: {', '.join(missing_labels)}"
        )

    lines.extend([
        "",
        "請評估每個 Spawn Request 是否需要建立對應 ticket：",
        "  - 需要 -> 建立 ticket 後將該條目 status 改為 processed",
        "  - 不需要 -> 將該條目 status 改為 dismissed 並附理由",
        "",
        "參考：quality-baseline.md 規則 5（所有發現必須追蹤）",
    ])

    return "\n".join(lines) + "\n"
