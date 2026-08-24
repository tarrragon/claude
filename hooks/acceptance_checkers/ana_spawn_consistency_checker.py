"""
ANA Spawn Consistency Checker - ANA Solution spawn 規劃 vs 實際 ticket 數量一致性檢查

對應 Ticket 0.18.0-W17-167 (ANA) → 0.18.0-W17-168 (IMP)：
ANA complete 前比對 Solution 章節 spawn 規劃表格（IMP/DOC/ANA + P0-P3）
與 frontmatter spawned_tickets + children 數量。

檢查邏輯：
  1. 僅對 type=ANA ticket 觸發
  2. 解析 ## Solution 章節
  3. 三策略偵測 spawn 規劃數 N_raw（取 max）：
     - row-per-spawn：`| (IMP|DOC|ANA) | ... | P[0-3] |`
     - heading-based：H3 同行含 Spawn + IMP/DOC/ANA
     - type-annotated：spawn 區段內表格 cell 為 IMP/DOC/ANA（容忍註記、無 P0-P3）
  4. 逐項扣抵豁免宣告：N = max(0, N_raw - 豁免宣告行數)
  5. 計算落地數 = spawned_tickets + children + 已判定的 Spawn Request
  6. 分級偵測：
     - N == 0 → 通過（無規劃、或規劃已全數宣告豁免）
     - N > 0 且 落地數 == 0 → 阻擋 complete
     - N > 0 且 落地數 < N → 警告（不阻擋）
     - N > 0 且 落地數 >= N → 通過

Why: acceptance 勾選「產出 spawned 清單」只檢文字產出，不檢 ticket 實際建立。
此檢查在 complete 時攔截「寫了規劃但沒建 ticket」的斷裂。

Consequence: 不加此檢查，ANA Solution 的 spawn 規劃會靜默遺忘。

Action: ANA complete 前 hook 強制比對；豁免宣告讓合法無須落地的規劃項通過。

2026-08-23 修訂兩處判定範圍（依同日 ANA 的實測結論）：

1. **落地證據納入已判定的 Spawn Request**。框架文件（`agent-dispatch-template.md`
   「建票血緣回填義務」、`AGENT_PRELOAD.md` 規則 2.6）明列 `add-spawn-request`
   為兩條合法建票通道之一，原實作只認 `spawned_tickets` / `children`，使走該
   通道的 ANA 無論登記多少筆 SR 都被硬擋。已判定僅指終態——`processed`
   （CLI 於 `--spawned-ticket` 有值時同步回填 frontmatter）與附理由的
   `dismissed`；`pending` 刻意不計入，它正是無 trigger 延後決策本身。

2. **豁免宣告改為逐項扣抵**。原實作對整個 Solution 章節掃描豁免字串，命中即
   跳過全部計數——2 項規劃、0 項落地的票補一行豁免說明即放行（實測）。改為
   每則宣告扣抵一項後，豁免成本與規劃項數成正比，宣告一項只放行一項。
"""

from __future__ import annotations

import re

from acceptance_checkers.spawn_request_checker import iter_spawn_request_entries


# 已判定 SR 附註中記載 ticket ID 的前綴與分隔符，對齊 resolve-spawn-request
# CLI 的寫入格式（`已建 A、B` / `已建 A、B，理由`）
_SPAWNED_NOTE_PREFIX = "已建 "
_ID_SEPARATOR = "、"
_NOTE_REASON_SEPARATOR = "，"

# 豁免宣告標記：Solution 內含這些字樣的每一行，扣抵一項 spawn 規劃
_EXEMPTION_MARKERS: list[str] = [
    "無需建 ticket",
    "無需建ticket",
    "無需 spawn",
    "無需spawn",
    "不 spawn",
    "不spawn",
    "不需 spawn",
    "不需spawn",
    "no spawn needed",
    "no spawn required",
]

# 行級豁免標記：表格行含這些字樣時該行不計入 spawn 規劃數（0.3.4-W2-003）
_ROW_EXEMPTION_MARKERS: list[str] = [
    "無需建 ticket",
    "無需建ticket",
    "併入",
    "merged into",
    "合併實作",
    "不建 ticket",
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

# spawn 區段標題：H3 含 Spawn 關鍵字（不要求同行含 IMP/DOC/ANA）
# 涵蓋 W1-024 案例（`### Spawn 落地確認`，type 在表格內而非標題行）
_SPAWN_SECTION_HEADING_PATTERN = re.compile(
    r"^###\s+.*?\bSpawn(?:ed)?\b.*$",
    re.IGNORECASE,
)

# 中文「Spawn」常見譯名標題（無英文 Spawn 字樣，仍屬 spawn 規劃區段）
# 涵蓋「Spawn 落地確認」等已含英文者由上方 pattern 命中；此處補純中文表述。
_SPAWN_SECTION_HEADING_ZH = ("落地確認", "spawn 規劃", "spawn規劃", "派生", "衍生 ticket")

# type-annotated spawn 行：表格行中某 cell 為 IMP/DOC/ANA（容忍註記如 `IMP（child）`）
# 範例命中：`| create UX 修復 | IMP（child） | 本 ticket spawn |`
#          `| 裸 cd 排除過寬 | IMP | 已 spawn W1-026 |`
# 僅在「spawn 區段」內計數，避免一般說明表格（含 IMP/DOC 字樣）誤判。
_TYPE_ANNOTATED_CELL_PATTERN = re.compile(
    r"\|\s*(?:IMP|DOC|ANA)(?:\s*[（(][^|]*?[)）])?\s*\|"
)


def _extract_solution_section(content: str) -> str | None:
    """擷取 ## Solution 區段（到下一個 ## 或檔尾為止）。"""
    pattern = r"^## Solution\s*\n(.*?)(?=^## |\Z)"
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
    if not match:
        return None
    section = match.group(1)
    # 移除 HTML 註解（模板 placeholder）
    section = re.sub(r"<!--.*?-->", "", section, flags=re.DOTALL)
    return section


def _count_exemption_declarations(section: str) -> int:
    """計算 Solution 內的豁免宣告行數（表格行除外，那些走行級扣抵）。

    每一行至多計為一則宣告，用於逐項扣抵 spawn 規劃數。表格行不在此計數：
    表格行的豁免由 `_is_exempted_row` 在計數階段直接排除，兩處重複計入會
    使單一項目被扣抵兩次。

    Why: 原實作只判斷「整段是否含豁免字串」，命中即跳過全部計數，使一行
    說明就能關閉整張票的檢查。改為計數後，宣告數少於規劃數時剩餘項目仍
    受檢，豁免成本與規劃項數成正比。
    """
    count = 0
    for line in section.split("\n"):
        stripped = line.strip()
        if stripped.startswith("|"):
            continue
        lowered = stripped.lower()
        if any(marker.lower() in lowered for marker in _EXEMPTION_MARKERS):
            count += 1
    return count


def _is_exempted_row(line: str) -> bool:
    """判斷表格行是否含行級豁免標記（「無需建 ticket」「併入」等）。"""
    lowered = line.lower()
    return any(marker.lower() in lowered for marker in _ROW_EXEMPTION_MARKERS)


def _count_spawn_planning_rows(section: str) -> int:
    """計算 Solution 內 spawn 規劃表格行數（IMP/DOC/ANA + P0-P3），排除行級豁免行。"""
    count = 0
    for line in section.split("\n"):
        if _SPAWN_ROW_PATTERN.match(line.strip()) and not _is_exempted_row(line):
            count += 1
    return count


def _count_spawn_heading_rows(section: str) -> int:
    """計算 Solution 內 H3 標題含 Spawn + IMP/DOC/ANA 的數量（heading-based 偵測）。

    用於補強 row-per-spawn 漏判場景：W17-176 案例使用 key-value 格式表格
    描述單一 spawn 規劃（無同行 type+priority），row-per-spawn 正則 N=0
    但語義上確實為 1 項 spawn 規劃。

    每個命中的 H3 視為 1 項 spawn 規劃。
    """
    matches = _SPAWN_HEADING_PATTERN.findall(section)
    return len(matches)


def _is_spawn_section_heading(line: str) -> bool:
    """判斷 H3 標題行是否屬 spawn 規劃區段（英文 Spawn 或中文譯名）。"""
    if _SPAWN_SECTION_HEADING_PATTERN.match(line):
        return True
    lowered = line.lower()
    return any(token.lower() in lowered for token in _SPAWN_SECTION_HEADING_ZH)


def _iter_spawn_section_bodies(section: str) -> list[str]:
    """擷取所有 spawn 區段的內文（從 spawn H3 標題到下一個 ### 或檔尾）。

    用於將 type-annotated 行偵測限縮在 spawn 語境，避免一般說明表格
    （如風險評估表含 IMP/DOC 字樣）被誤判為 spawn 規劃。
    """
    bodies: list[str] = []
    lines = section.split("\n")
    current: list[str] | None = None
    for line in lines:
        if line.startswith("### "):
            if current is not None:
                bodies.append("\n".join(current))
            current = [] if _is_spawn_section_heading(line) else None
        elif current is not None:
            current.append(line)
    if current is not None:
        bodies.append("\n".join(current))
    return bodies


def _count_type_annotated_rows(section: str) -> int:
    """計算 spawn 區段內 type-annotated 表格行數（容忍 type 欄附註與無 P0-P3 欄）。

    僅在 spawn 區段（H3 含 Spawn 關鍵字或中文譯名）內計數，
    並排除表頭分隔行（`|---|---|`）與表頭標題行（cell 為「形態」「Type」等非 type 值）。
    """
    count = 0
    for body in _iter_spawn_section_bodies(section):
        for line in body.split("\n"):
            stripped = line.strip()
            if not stripped.startswith("|"):
                continue
            if set(stripped) <= set("|-: "):  # 表頭分隔行
                continue
            if _TYPE_ANNOTATED_CELL_PATTERN.search(line) and not _is_exempted_row(line):
                count += 1
    return count


def _count_spawn_planning(section: str) -> int:
    """整合三策略：N = max(row-per-spawn, heading-based, type-annotated 計數)。

    - row-per-spawn：每行一個 spawn 且同行含 P0-P3（如 W17-162 / W17-167 多項規劃表）
    - heading-based：每個 H3 同行含 Spawn + IMP/DOC/ANA（如 W17-176 key-value 單項規劃表）
    - type-annotated：spawn 區段內表格行某 cell 為 IMP/DOC/ANA（容忍註記、無 P0-P3，如 W1-024）

    取較大值避免漏判；三策略適用不同表格樣式，不會在同一規劃中重複放大計數。
    """
    n_rows = _count_spawn_planning_rows(section)
    n_headings = _count_spawn_heading_rows(section)
    n_type_annotated = _count_type_annotated_rows(section)
    return max(n_rows, n_headings, n_type_annotated)


def _extract_ticket_ids_from_note(note: str) -> list[str]:
    """從已判定 SR 的附註取出其記載的 ticket ID。

    對齊建立端格式：`resolve-spawn-request --status processed --spawned-ticket`
    寫入 `已建 A、B`，附 `--reason` 時為 `已建 A、B，理由`（見
    `ticket_system/commands/track_acceptance.py`
    `_build_spawn_request_status_value`）。非此格式者回傳空列表。
    """
    stripped = note.strip()
    if not stripped.startswith(_SPAWNED_NOTE_PREFIX):
        return []
    body = stripped[len(_SPAWNED_NOTE_PREFIX):]
    body = body.split(_NOTE_REASON_SEPARATOR, 1)[0]
    return [token.strip() for token in body.split(_ID_SEPARATOR) if token.strip()]


def _collect_landing_evidence(frontmatter: dict, content: str) -> tuple[int, int]:
    """彙整落地證據，回傳（具名 ticket ID 去重後的數量, 無 ID 的已判定數）。

    Why 用集合而非直接相加：`resolve-spawn-request --status processed
    --spawned-ticket <id>` 會同步回填 `spawned_tickets`，同一筆落地因此同時
    出現在 frontmatter 與 SR 附註兩處。直接相加會把它計兩次，使「規劃 4 項、
    實際落地 2 項」這種本該警告的狀態靜默通過——正是本檢查要攔截的壞狀態。

    無 ID 的已判定條目（附理由的 `dismissed`、未帶 ticket 的 `processed`）
    與具名 ID 不會重疊，另行計數。附註為非建立端格式而無法解析 ID 時退回
    無 ID 計數，方向偏保守：可能少計而偏向阻擋，不會造成誤放。
    """
    named_ids: set[str] = set()
    for field in ("spawned_tickets", "children"):
        raw = frontmatter.get(field, []) or []
        if isinstance(raw, list):
            named_ids.update(str(item).strip() for item in raw if str(item).strip())
        elif isinstance(raw, str):
            for line in raw.split("\n"):
                line = line.strip()
                if line.startswith("-"):
                    item = line[1:].strip()
                    if item:
                        named_ids.add(item)

    judged_without_id = 0
    for entry in iter_spawn_request_entries(content):
        if not entry.is_resolved:
            continue
        entry_ids = _extract_ticket_ids_from_note(entry.note)
        if entry_ids:
            named_ids.update(entry_ids)
        else:
            judged_without_id += 1

    return len(named_ids), judged_without_id


def check_ana_spawn_consistency(
    content: str, frontmatter: dict, logger
) -> tuple[bool,str | None]:
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

    n_raw = _count_spawn_planning(section)
    n_exempted = _count_exemption_declarations(section)
    n_planned = max(0, n_raw - n_exempted)
    if n_planned == 0:
        logger.debug(
            "ANA %s spawn 規劃 %d 項、豁免宣告 %d 則，無待落地項目",
            ticket_id,
            n_raw,
            n_exempted,
        )
        return False, None

    n_named, n_judged_without_id = _collect_landing_evidence(frontmatter, content)
    n_actual = n_named + n_judged_without_id

    if n_actual == 0:
        msg = _format_block_message(ticket_id, n_planned)
        logger.error(
            "ANA %s Solution 規劃 %d 項 spawn，落地證據為 0 - 阻擋 complete",
            ticket_id,
            n_planned,
        )
        return True, msg

    if n_actual < n_planned:
        msg = _format_warning_message(
            ticket_id, n_planned, n_named, n_judged_without_id
        )
        logger.warning(
            "ANA %s Solution 規劃 %d 項 spawn，但落地只有 %d 項"
            "（具名 ticket 去重後=%d，無 ID 已判定=%d）",
            ticket_id,
            n_planned,
            n_actual,
            n_named,
            n_judged_without_id,
        )
        return False, msg

    logger.info(
        "ANA %s spawn 一致性通過：規劃=%d，落地=%d（具名 ticket 去重後=%d，無 ID 已判定=%d）",
        ticket_id,
        n_planned,
        n_actual,
        n_named,
        n_judged_without_id,
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
        f"待落地 spawn 規劃數: {n_planned}（已扣除豁免宣告）\n"
        f"落地證據: spawned_tickets + children + 已判定 Spawn Request = 0\n"
        f"\n"
        f"修復方式（擇一）：\n"
        f"  1. 直接建票：`ticket create --source-ticket {ticket_id} --action <動詞> "
        f"--target <對象> --type <IMP|ADJ|ANA|DOC> --why <依據>`\n"
        f"     （CLI 建立當下即回填 source_ticket / spawned_tickets 雙向欄位；\n"
        f"      子任務形態改用 `--parent {ticket_id}`）\n"
        f"  2. 成票與否需 PM 裁決：先 `ticket track add-spawn-request {ticket_id} "
        f"--what ... --why ... --type ... --priority ...`，\n"
        f"     再以 `ticket track resolve-spawn-request {ticket_id} SR-N "
        f"--status processed --spawned-ticket <ticket-id>`\n"
        f"     或 `--status dismissed --reason <理由>` 標為終態。"
        f"停在 pending 不計入落地證據。\n"
        f"  3. 該項評估後無須落地：在 Solution 逐項顯性標註豁免理由\n"
        f"     （每則宣告扣抵一項，宣告數需與待落地項數相符）\n"
        f"\n"
        f"參考：quality-baseline.md 規則 5\n"
    )


def _format_warning_message(
    ticket_id: str, n_planned: int, n_named: int, n_judged_without_id: int
) -> str:
    n_actual = n_named + n_judged_without_id
    return (
        f"[WARNING] Acceptance Gate: ANA Ticket Solution spawn 規劃部分漏建\n"
        f"\n"
        f"Ticket: {ticket_id}\n"
        f"待落地 spawn 規劃數: {n_planned}（已扣除豁免宣告）\n"
        f"落地證據: {n_actual}"
        f"（具名 ticket 去重後 = {n_named}，無 ticket ID 的已判定項 = {n_judged_without_id}）\n"
        f"\n"
        f"請確認是否有遺漏的 spawn ticket 未建立。\n"
        f"若部分項目評估後無須落地，請在 Solution 逐項補註豁免理由（每則扣抵一項）。\n"
        f"停在 pending 的 Spawn Request 不計入落地證據，需先 resolve 為 "
        f"processed 或附理由的 dismissed。\n"
    )
