#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
Phase 4 Decision Enforcement Hook - PC-093 YAGNI 累積防護

功能：Phase 4 階段強制決斷閘門。掃描 ticket md 中的延後話術（「Phase X 再決定」
「之後再說」「保留以防萬一」等），命中 MUST-block 等級時阻擋，要求 PM 做出
「執行 / 移除 / 豁免」三選一決策。

Hook 類型：
- PostToolUse (Bash): 主觸發，匹配 `ticket track phase <id> phase4`
- PreToolUse (Bash): 輔助觸發，匹配 `ticket track complete <id>`（殘留二次掃描）

分級：
- MUST-block（M1-M3）：Exit 2，stderr 阻擋
- WARN（W1-W3）：Exit 0，stdout 警告
- INFO（I1-I2）：Exit 0，stdout 提醒

豁免語法：
  <!-- PC-093-exempt: <category>:<reason> -->
  於命中 phrase 同行或前 1 行內生效。
  category: tdd-transition | baseline-gated | ticket-tracked | user-override
  reason: ≥10 字元；baseline-gated 需含數字；ticket-tracked 需含 ticket id

Ticket: 0.18.0-W10-082
Pattern: PC-093
"""

import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

# 加入 hooks/ 到 sys.path 以便 import hook_utils package
sys.path.insert(0, str(Path(__file__).parent))

from hook_utils import (  # noqa: E402
    setup_hook_logging,
    run_hook_safely,
    read_json_from_stdin,
    extract_tool_input,
    find_ticket_file,
    emit_hook_output,
)


# ============================================================================
# 常數定義
# ============================================================================

EXEMPT_CATEGORIES = frozenset({
    "tdd-transition",
    "baseline-gated",
    "ticket-tracked",
    "user-override",
})

REASON_MIN_LEN = 10

# Ticket ID 通用格式：W{wave}-{seq} 或 {version}-W{wave}-{seq}
TICKET_ID_PATTERN = re.compile(r"\bW\d+-\d+")

# 觸發命令偵測
MAIN_GATE_CMD = re.compile(r"ticket\s+track\s+phase\s+(\S+)\s+phase4\b")
RESIDUAL_GATE_CMD = re.compile(r"ticket\s+track\s+complete\s+(\S+)")

# 豁免 marker 解析（大小寫敏感，EX-N7）
EXEMPT_MARKER = re.compile(
    r"<!--\s*PC-093-exempt\s*:\s*([^:]+?)\s*:\s*(.+?)\s*-->"
)

# 豁免 marker 剔除（掃描 phrase 前移除，避免 marker 內含 phrase 誤判）
EXEMPT_MARKER_STRIP = re.compile(r"<!--\s*PC-093-exempt[^>]*-->")

# 豁免 proximity（marker 同行或前 1 行生效）
EXEMPT_PROXIMITY_LINES = 1

# 檔級豁免（PC-099 meta-ticket 自我引用）：
#   此 hook 的識別名稱。當 ticket frontmatter 包含
#     hook_self_reference: phase4-decision-enforcement
#   或 list 形式含此值時，整檔豁免偵測（hook 自身設計/測試/實作 ticket）。
SELF_REFERENCE_HOOK_ID = "phase4-decision-enforcement"


# ============================================================================
# 資料結構
# ============================================================================

@dataclass
class PhraseRule:
    id: str          # M1|M2|M3|W1|W2|W3|I1|I2
    level: str       # BLOCK|WARN|INFO
    pattern: re.Pattern
    rationale: str


@dataclass
class Hit:
    line_no: int
    rule_id: str
    level: str
    text: str


@dataclass
class ExemptMarker:
    category: str
    reason: str


@dataclass
class ExemptRef:
    line_no: int
    marker: Optional[ExemptMarker]
    valid: bool
    err: Optional[str] = None


# ============================================================================
# F1: Regex 表構建
# ============================================================================

def build_regex_table() -> List[PhraseRule]:
    """構建 3 級 regex 表（8 條：M×3 / W×3 / I×2）。

    依 Phase 1 §1 設計。IGNORECASE + MULTILINE。
    """
    flags = re.IGNORECASE | re.MULTILINE
    return [
        # M1: Phase X 再決定（遞迴推給未來 phase）
        PhraseRule(
            id="M1",
            level="BLOCK",
            pattern=re.compile(
                r"Phase\s*[0-9]+[^\n]{0,30}?(?:再|在)?(?:決定|決斷|判斷|評估)",
                flags,
            ),
            rationale="遞迴推給未來 phase，PC-093 核心反模式",
        ),
        # M2: 之後/以後 再決定（無時間錨點）
        PhraseRule(
            id="M2",
            level="BLOCK",
            pattern=re.compile(
                r"(?:之後|以後|日後|未來)\s*(?:再|才)?(?:決定|決斷|說|考慮|處理)",
                flags,
            ),
            rationale="無時間錨點＝永久延後",
        ),
        # M3: 保留以防萬一（「不用」偽裝為「保留」）
        PhraseRule(
            id="M3",
            level="BLOCK",
            pattern=re.compile(
                r"保留[^\n]{0,20}?(?:以防萬一|以備不時之需|彈性|擴展性|擴充性)",
                flags,
            ),
            rationale="將「不用」偽裝為「保留」（根因 D）",
        ),
        # W1: 視 X 結果再決定（帶條件延後）
        PhraseRule(
            id="W1",
            level="WARN",
            pattern=re.compile(
                r"視\s*.{1,30}?\s*(?:結果|情況|狀況|需求)\s*(?:再|而)?\s*(?:決定|判斷|評估)",
                flags,
            ),
            rationale="帶條件的延後，條件明確可豁免",
        ),
        # W2: 未來/以後 可能需要（預留樂觀話術）
        PhraseRule(
            id="W2",
            level="WARN",
            pattern=re.compile(
                r"(?:未來|以後)\s*(?:可能|或許|也許)\s*(?:需要|會用|要用)",
                flags,
            ),
            rationale="根因 B「預留樂觀」話術",
        ),
        # W3: 先保留再說（決策疲勞）
        PhraseRule(
            id="W3",
            level="WARN",
            pattern=re.compile(
                r"先(?:保留|留著|不動)\s*(?:再說|吧)?",
                flags,
            ),
            rationale="根因 C「決策疲勞」口語",
        ),
        # I1: TBD/TODO/FIXME 延後標記
        PhraseRule(
            id="I1",
            level="INFO",
            pattern=re.compile(
                r"(?:TBD|TODO|FIXME)\s*[:：]?\s*(?:Phase\s*[0-9]+|之後|未來)",
                flags,
            ),
            rationale="標記式延後，若有後續 ticket 可豁免",
        ),
        # I2: 擴展彈性/擴充介面（PC-093 偽裝詞）
        PhraseRule(
            id="I2",
            level="INFO",
            pattern=re.compile(
                r"(?:擴展|擴充)\s*(?:彈性|空間|介面)",
                flags,
            ),
            rationale="PC-093 偽裝詞前綴",
        ),
    ]


# ============================================================================
# F2: 逐行掃描 phrase
# ============================================================================

def scan_lines_for_phrases(
    lines: List[str],
    table: List[PhraseRule],
) -> List[Hit]:
    """逐行掃描命中。

    - 掃前移除 EXEMPT_MARKER_STRIP 避 marker 內含 phrase 誤判。
    - 同行可多規則命中，不去重；豁免狀態由 F7 處理。
    """
    hits: List[Hit] = []
    for idx, raw in enumerate(lines, start=1):
        stripped = EXEMPT_MARKER_STRIP.sub("", raw)
        for rule in table:
            for match in rule.pattern.finditer(stripped):
                hits.append(
                    Hit(
                        line_no=idx,
                        rule_id=rule.id,
                        level=rule.level,
                        text=match.group(),
                    )
                )
    return hits


# ============================================================================
# F3 + F4: 豁免解析 + 驗證
# ============================================================================

def parse_exempt_marker(text: str) -> Optional[ExemptMarker]:
    """解析 <!-- PC-093-exempt: cat:reason --> 格式。

    大小寫敏感（EX-N7）；空格寬鬆（EX-N6）；純文字非 HTML comment 不匹配（EX-N8）。
    """
    m = EXEMPT_MARKER.search(text)
    if not m:
        return None
    return ExemptMarker(category=m.group(1).strip(), reason=m.group(2).strip())


def validate_exempt_fields(marker: ExemptMarker) -> Tuple[bool, Optional[str]]:
    """驗證 category 白名單 + reason 規則。

    Returns (is_valid, err_code)。
    """
    if marker.category not in EXEMPT_CATEGORIES:
        return (False, "category-whitelist")
    if len(marker.reason) < REASON_MIN_LEN:
        return (False, "reason-too-short")
    if marker.category == "baseline-gated" and not re.search(r"\d", marker.reason):
        return (False, "baseline-need-number")
    if marker.category == "ticket-tracked" and not TICKET_ID_PATTERN.search(marker.reason):
        return (False, "ticket-tracked-need-id")
    return (True, None)


# ============================================================================
# F5: 掃全文蒐集 exempt markers
# ============================================================================

def collect_exempt_markers(lines: List[str]) -> List[ExemptRef]:
    """掃全文蒐集 marker 位置 + 解析結果。"""
    refs: List[ExemptRef] = []
    for idx, raw in enumerate(lines, start=1):
        marker = parse_exempt_marker(raw)
        if marker is None:
            # 若行內含 PC-093-exempt 文字但格式不符（EX-N5/EX-N8）
            if "PC-093-exempt" in raw and "<!--" in raw:
                refs.append(
                    ExemptRef(line_no=idx, marker=None, valid=False, err="format-error")
                )
            continue
        valid, err = validate_exempt_fields(marker)
        refs.append(
            ExemptRef(line_no=idx, marker=marker, valid=valid, err=err)
        )
    return refs


# ============================================================================
# F6: 豁免距離匹配
# ============================================================================

def is_hit_exempted(hit: Hit, markers: List[ExemptRef]) -> bool:
    """判斷 hit 是否被有效豁免 marker 覆蓋。

    規則（Phase 1 §3.2）：marker 在 phrase 同行或前 1 行內生效。
    - 同行 (DIST-1)：生效
    - 前 1 行 (DIST-2)：生效
    - 前 2 行 (DIST-3)：不生效
    - 後行 (DIST-4)：不生效
    """
    for ref in markers:
        if not ref.valid:
            continue
        if ref.line_no == hit.line_no:
            return True
        if ref.line_no == hit.line_no - EXEMPT_PROXIMITY_LINES:
            return True
    return False


# ============================================================================
# F7: 四分類（blocked / warned / info / exempted）
# ============================================================================

def partition_hits(
    hits: List[Hit],
    markers: List[ExemptRef],
) -> Tuple[List[Hit], List[Hit], List[Hit], List[Hit]]:
    """依 level 與豁免狀態四分類。

    Returns (blocked, warned, info, exempted)。
    """
    blocked: List[Hit] = []
    warned: List[Hit] = []
    info: List[Hit] = []
    exempted: List[Hit] = []

    for hit in hits:
        if is_hit_exempted(hit, markers):
            exempted.append(hit)
            continue
        if hit.level == "BLOCK":
            blocked.append(hit)
        elif hit.level == "WARN":
            warned.append(hit)
        elif hit.level == "INFO":
            info.append(hit)
    return blocked, warned, info, exempted


# ============================================================================
# F7.5: 檔級豁免偵測（PC-099 meta-ticket self-reference）
# ============================================================================

def detect_hook_self_reference(content: str) -> bool:
    """偵測 ticket frontmatter 是否宣告 self-reference 豁免。

    格式（任一匹配）：
        hook_self_reference: phase4-decision-enforcement
        hook_self_reference:
          - phase4-decision-enforcement
          - other-hook

    僅解析首個 YAML frontmatter 區塊（--- ... ---）。不引入 PyYAML 相依。

    Returns True 表示整檔豁免。
    """
    if not content.startswith("---"):
        return False
    # 取 frontmatter 區塊（--- ... ---）
    end = content.find("\n---", 3)
    if end < 0:
        return False
    fm = content[3:end]
    # 單行形式：hook_self_reference: phase4-decision-enforcement
    single = re.search(
        r"^\s*hook_self_reference\s*:\s*(\S.*?)\s*$",
        fm,
        re.MULTILINE,
    )
    if single:
        value = single.group(1).strip()
        if value == SELF_REFERENCE_HOOK_ID or value == '"{}"'.format(SELF_REFERENCE_HOOK_ID) \
                or value == "'{}'".format(SELF_REFERENCE_HOOK_ID):
            return True
    # List 形式：hook_self_reference:\n  - phase4-decision-enforcement
    list_match = re.search(
        r"^\s*hook_self_reference\s*:\s*\n((?:\s*-\s*\S.*\n?)+)",
        fm,
        re.MULTILINE,
    )
    if list_match:
        items = re.findall(r"-\s*(\S+)", list_match.group(1))
        if SELF_REFERENCE_HOOK_ID in items:
            return True
    return False


# ============================================================================
# F8: 從命令萃取 ticket_id 及模式
# ============================================================================

def extract_ticket_id_from_command(command: str) -> Tuple[Optional[str], Optional[str]]:
    """從 bash 命令萃取 (ticket_id, mode)。

    mode: 'main_gate' | 'residual_gate' | None
    """
    if not command:
        return (None, None)
    m = MAIN_GATE_CMD.search(command)
    if m:
        return (m.group(1), "main_gate")
    m = RESIDUAL_GATE_CMD.search(command)
    if m:
        return (m.group(1), "residual_gate")
    return (None, None)


# ============================================================================
# F9: ticket id → md 路徑
# ============================================================================

def resolve_ticket_md_path(ticket_id: str, logger) -> Optional[Path]:
    """解析 ticket id 到 md 檔路徑（複用 hook_utils.find_ticket_file）。"""
    try:
        return find_ticket_file(ticket_id, logger=logger)
    except Exception as exc:
        logger.info("resolve_ticket_md_path 失敗: {}".format(exc))
        return None


# ============================================================================
# F10: Block 訊息組裝
# ============================================================================

def format_block_message(
    ticket_id: str,
    blocked: List[Hit],
    exempted: List[Hit],
) -> str:
    """組 §4.1 stderr block 訊息 + AUQ 骨架。"""
    lines = []
    lines.append("[PC-093 Phase 4 強制決斷] 偵測到延後話術，禁止遞迴延後")
    lines.append("")
    lines.append("Ticket: {}".format(ticket_id))
    lines.append("命中:")
    for hit in blocked:
        lines.append("  line {} [{}]: 「{}」".format(hit.line_no, hit.rule_id, hit.text))
    lines.append("")
    lines.append("根因: PC-093 YAGNI 累積反模式")
    lines.append("  詳見: .claude/error-patterns/process-compliance/PC-093-yagni-deferred-decision-accumulation.md")
    lines.append("")
    lines.append("要求對每項做出二選一:")
    lines.append("  1. 執行 — 立即實作，附 use case + AC")
    lines.append("  2. 移除 — 刪除預留 + dead code，記錄理由")
    lines.append("  3. 豁免 — 符合合法延後條件，加 <!-- PC-093-exempt: cat:reason --> 標記")
    lines.append("")
    lines.append("修復後重新 ticket track phase {} phase4。".format(ticket_id))
    lines.append("")
    lines.append("AUQ 選項骨架:")
    lines.append("  - label: 執行          description: Phase 4 立即實作 + 加 AC")
    lines.append("  - label: 移除          description: 刪除預留 + dead code")
    lines.append("  - label: 豁免（附條件） description: 加 PC-093-exempt 標記")
    if exempted:
        lines.append("")
        lines.append("[PC-093 當前豁免清單]")
        for hit in exempted:
            lines.append("  line {} [{}]: 「{}」".format(hit.line_no, hit.rule_id, hit.text))
    return "\n".join(lines)


# ============================================================================
# F11: Warn/Info 訊息組裝
# ============================================================================

def format_warn_info_message(
    warned: List[Hit],
    info: List[Hit],
    exempted_refs: List[ExemptRef],
) -> str:
    """組 §4.2 stdout 警告 + 豁免審計訊息。"""
    lines = []
    if warned:
        lines.append("[PC-093 警告] 模糊延後話術（不阻塞，Phase 4 前建議釐清）")
        for hit in warned:
            lines.append("  line {} [{}]: 「{}」".format(hit.line_no, hit.rule_id, hit.text))
    if info:
        if warned:
            lines.append("")
        lines.append("[PC-093 提醒] 延後標記（若有後續 ticket 可豁免）")
        for hit in info:
            lines.append("  line {} [{}]: 「{}」".format(hit.line_no, hit.rule_id, hit.text))

    # 豁免審計（AC8）
    valid_exempts = [r for r in exempted_refs if r.valid and r.marker]
    invalid_exempts = [r for r in exempted_refs if not r.valid]
    if valid_exempts or invalid_exempts:
        if lines:
            lines.append("")
        lines.append("[PC-093 豁免清單] 當前豁免：")
        for ref in valid_exempts:
            lines.append("  line {}: {} — {}".format(
                ref.line_no, ref.marker.category, ref.marker.reason
            ))
        for ref in invalid_exempts:
            err_msg = ref.err or "format-error"
            lines.append("  line {}: [INVALID: {}]".format(ref.line_no, err_msg))
        if valid_exempts:
            lines.append("")
            lines.append("Phase 4 結束前必須清償（改執行或移除），剩餘豁免於 complete 時 WARN。")
    return "\n".join(lines)


# ============================================================================
# Main
# ============================================================================

def main() -> int:
    """Hook 主流程。"""
    logger = setup_hook_logging("phase4-decision-enforcement")

    input_data = read_json_from_stdin(logger)
    if input_data is None:
        return 0

    event_name = input_data.get("hook_event_name") or input_data.get("hookEventName") or ""
    tool_input = extract_tool_input(input_data)
    command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""

    if not command:
        logger.debug("no command in tool_input, skip")
        return 0

    ticket_id, mode = extract_ticket_id_from_command(command)
    if mode is None:
        logger.debug("command not matching main/residual gate: {}".format(command[:80]))
        return 0

    # Event 與 mode 對應檢查（INT-6/INT-10）
    if mode == "main_gate" and event_name not in ("PostToolUse", ""):
        logger.debug("main_gate 但 event 非 PostToolUse: {}".format(event_name))
        return 0
    if mode == "residual_gate" and event_name not in ("PreToolUse", ""):
        logger.debug("residual_gate 但 event 非 PreToolUse: {}".format(event_name))
        return 0

    if not ticket_id:
        logger.debug("no ticket_id extracted")
        return 0

    md_path = resolve_ticket_md_path(ticket_id, logger)
    if md_path is None or not md_path.exists():
        logger.info("ticket md not found: {}".format(ticket_id))
        return 0

    try:
        content = md_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as exc:
        logger.info("read ticket md failed: {}".format(exc))
        return 0

    # PC-099: 檔級豁免（meta-ticket self-reference）
    if detect_hook_self_reference(content):
        logger.info(
            "ticket {} declared hook_self_reference, skip scan (PC-099)".format(ticket_id)
        )
        return 0

    lines = content.split("\n")
    table = build_regex_table()
    hits = scan_lines_for_phrases(lines, table)
    markers = collect_exempt_markers(lines)
    blocked, warned, info, exempted_hits = partition_hits(hits, markers)

    logger.info(
        "scan result: ticket={} mode={} blocked={} warned={} info={} exempted={}".format(
            ticket_id, mode, len(blocked), len(warned), len(info), len(exempted_hits)
        )
    )

    if blocked:
        msg = format_block_message(ticket_id, blocked, exempted_hits)
        sys.stderr.write(msg + "\n")
        sys.stderr.flush()
        return 2

    # WARN/INFO/exempt audit → stdout (hook JSON)
    if warned or info or markers:
        msg = format_warn_info_message(warned, info, markers)
        if msg:
            emit_hook_output(event_name or "PostToolUse", additional_context=msg)
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "phase4-decision-enforcement"))
