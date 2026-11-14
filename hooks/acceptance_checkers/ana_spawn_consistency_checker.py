"""
ANA Spawn Consistency Checker - ANA Solution spawn 規劃 vs 實際 ticket 數量一致性檢查

對應一次 ANA 分析結論與其 IMP 落地：
ANA complete 前比對 Solution 章節 spawn 規劃表格（IMP/DOC/ANA + P0-P3）
與 frontmatter spawned_tickets + children 數量。

檢查邏輯：
  1. 僅對 type=ANA／DOC ticket 觸發
  2. 解析 ## Solution 章節
  3. 三策略偵測 spawn 規劃數 N_raw（取 max）：
     - row-per-spawn：`| (IMP|DOC|ANA) | ... | P[0-3] |`
     - heading-based：H3 同行含 Spawn + IMP/DOC/ANA
     - type-annotated：spawn 區段內表格 cell 為 IMP/DOC/ANA（容忍註記、無 P0-P3）
  4. 逐項扣抵豁免宣告：N = max(0, N_raw - 豁免宣告行數)
  5. 計算落地數 = spawned_tickets + children + 已判定的 Spawn Request
     （不足 N 時再補回指本票的票，見下方 2026-11-12 修訂第 3 點）
  6. 分級偵測：
     - N == 0 → 通過（無規劃、或規劃已全數宣告豁免）
     - N > 0 且 落地數 < N → 阻擋 complete（含落地數 0）
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

2026-09-07 新增來源票對照表排除（實測發現）：

`_count_spawn_planning_rows` 掃描整個 Solution 無區段範圍限定，framework-issue
收束流程要求把「已處置的來源票對照表」（票 ID、型別、標題、處置、落點）寫入
Solution 供稽核，該表天然帶型別欄，加上優先級欄後與 row-per-spawn 判準同形，
誤判為 spawn 規劃並擋 complete（實測需補 16 列逐項豁免宣告才能通過）。改為在
`_extract_solution_section` 階段先以 `_strip_excluded_tables` 移除命中排除
判準（表頭含「處置」／「close 理由」欄，或表格前一行含「來源票對照」）的
表格，三項計數策略統一在剩餘文字上運作，不需逐列豁免宣告。

2026-11-12 三處修訂（依同期存量量測：兩個 repo 已完成的 ANA 中，部分落地
的樣本全是重複計數，真實部分漏建為 0）：

1. **規劃數只算規劃區段**。同一 Solution 並存「Spawn 規劃」與「Spawn 落地確認」
   兩張表時，type-annotated 策略把兩張表的列都計入，規劃數翻倍（#70）。
   有規劃區段時，落地區段（標題含「落地確認」「逐項落地」，或含「落地」而不含
   「規劃」）不計入規劃數；只有落地區段時（單表寫法）照舊計數。豁免宣告仍掃
   整個 Solution，落地區段內的逐項豁免照常扣抵。

2. **部分落地改為阻擋**。原第 3 級 `0 < 落地 < 規劃` 只警告；去重後存量樣本
   無真實部分漏建，因此升為阻擋，與 quality-baseline 規則 5「缺漏阻擋
   complete」一致。

3. **涵蓋 DOC，落地證據納入反向血緣**。DOC 套用同一檢查。落地數不足時，
   由呼叫端提供的查詢補上回指本票的票：`source_ticket`／`discovered_during`／
   `parent_id` 指向本票，或 `previous_ids` 含本票子號（子票被 migrate 到其他版本
   後，`parent_id` 與父票 `children` 皆被清除，只剩 `previous_ids` 保留血緣）。
   查詢失敗時不加嚴：只維持修訂前的行為（ANA 落地為 0 阻擋），其餘降為警告，
   並寫 stderr 與日誌。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Callable, Optional

from acceptance_checkers.spawn_request_checker import iter_spawn_request_entries

# 套用本檢查的票型（2026-11-12 由 ANA 擴及 DOC）
_CHECKED_TYPES: tuple[str, ...] = ("ANA", "DOC")

# 落地區段標題判準：含強訊號詞，或含「落地」而不含「規劃」
# 範例（落地）：`### Spawn 落地確認`、`### 用戶裁定與 Spawn 落地確認`、
#              `### Spawn 落地`、`### Spawn 規劃的逐項落地`
# 範例（規劃）：`### Spawn 規劃（裁決後落地）`、`### Spawn 規劃（等用戶裁定）`
_LANDING_HEADING_STRONG: tuple[str, ...] = ("落地確認", "逐項落地")
_LANDING_WORD = "落地"
_PLANNING_WORD = "規劃"


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

# 行級豁免標記：表格行含這些字樣時該行不計入 spawn 規劃數
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
# 涵蓋 key-value 表格格式 spawn 規劃的案例（row-per-spawn 正則漏判）
# 範例命中：`### Spawned IMP 規劃` / `### Spawn 規劃 (DOC)` / `### Spawned DOC/ANA 清單`
# 範例不命中：`### 根因分析` / `### Implementation Plan`（無 Spawn 關鍵字）
_SPAWN_HEADING_PATTERN = re.compile(
    r"^###\s+.*?\bSpawn(?:ed)?\b.*?\b(?:IMP|DOC|ANA)\b.*$",
    re.MULTILINE | re.IGNORECASE,
)

# spawn 區段標題：H3 含 Spawn 關鍵字（不要求同行含 IMP/DOC/ANA）
# 涵蓋 type 標註在表格內的案例（`### Spawn 落地確認`，type 在表格內而非標題行）
_SPAWN_SECTION_HEADING_PATTERN = re.compile(
    r"^###\s+.*?\bSpawn(?:ed)?\b.*$",
    re.IGNORECASE,
)

# 中文「Spawn」常見譯名標題（無英文 Spawn 字樣，仍屬 spawn 規劃區段）
# 涵蓋「Spawn 落地確認」等已含英文者由上方 pattern 命中；此處補純中文表述。
_SPAWN_SECTION_HEADING_ZH = ("落地確認", "spawn 規劃", "spawn規劃", "派生", "衍生 ticket")

# type-annotated spawn 行：表格行中某 cell 為 IMP/DOC/ANA（容忍註記如 `IMP（child）`）
# 範例命中：`| create UX 修復 | IMP（child） | 本 ticket spawn |`
#          `| 裸 cd 排除過寬 | IMP | 已 spawn 後續票 |`
# 僅在「spawn 區段」內計數，避免一般說明表格（含 IMP/DOC 字樣）誤判。
_TYPE_ANNOTATED_CELL_PATTERN = re.compile(
    r"\|\s*(?:IMP|DOC|ANA)(?:\s*[（(][^|]*?[)）])?\s*\|"
)

# 來源票對照表排除判準：framework-issue 收束流程要求把「已處置的來源票」
# 清單（票 ID、型別、標題、處置、落點）寫入 Solution 供稽核，這類表格天然
# 帶型別欄（IMP/DOC/ANA），加上優先級欄（P0-P3）後即與 row-per-spawn／
# type-annotated 判準在正則層面同形，但列的是已處置的舊票而非待建的新票。
# 兩項判準符合任一即整張表格排除：
#   1. 表頭列含「處置」或「close 理由」欄
#   2. 表格前一個非空行（標題或說明文字）含「來源票對照」
_EXCLUDED_TABLE_HEADER_MARKERS: tuple[str, ...] = ("處置", "close 理由", "close理由")
_EXCLUDED_TABLE_CONTEXT_MARKERS: tuple[str, ...] = ("來源票對照",)


def _is_table_separator_row(line: str) -> bool:
    """判斷是否為表格分隔列（如 `|---|---|`，僅含 `|`、`-`、`:`、空白）。"""
    stripped = line.strip()
    return bool(stripped) and stripped.startswith("|") and set(stripped) <= set("|-: ")


def _strip_excluded_tables(section: str) -> str:
    """移除來源票對照類表格的所有行，避免與真正的 spawn 規劃表格同形誤判。

    命中排除判準（表頭含「處置」／「close 理由」欄，或表格前一非空行含
    「來源票對照」）的表格，其表頭列、分隔列、所有資料列整段從計數輸入
    移除；不影響表格前後的標題與說明文字，也不影響其他表格的計數。
    """
    lines = section.split("\n")
    result: list[str] = []
    last_non_blank = ""
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()
        is_table_header = (
            stripped.startswith("|")
            and i + 1 < n
            and _is_table_separator_row(lines[i + 1])
        )
        if is_table_header:
            header_excluded = any(
                marker in stripped for marker in _EXCLUDED_TABLE_HEADER_MARKERS
            )
            context_excluded = any(
                marker in last_non_blank for marker in _EXCLUDED_TABLE_CONTEXT_MARKERS
            )
            if header_excluded or context_excluded:
                i += 2  # 跳過表頭列與分隔列
                while i < n and lines[i].strip().startswith("|"):
                    i += 1
                continue
        result.append(line)
        if stripped:
            last_non_blank = stripped
        i += 1
    return "\n".join(result)


def _extract_solution_section(content: str) -> str | None:
    """擷取 ## Solution 區段（到下一個 ## 或檔尾為止）。"""
    pattern = r"^## Solution\s*\n(.*?)(?=^## |\Z)"
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
    if not match:
        return None
    section = match.group(1)
    # 移除 HTML 註解（模板 placeholder）
    section = re.sub(r"<!--.*?-->", "", section, flags=re.DOTALL)
    # 移除來源票對照類表格（不影響其他計數邏輯）
    section = _strip_excluded_tables(section)
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

    用於補強 row-per-spawn 漏判場景：此類案例使用 key-value 格式表格
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


def _is_landing_heading(line: str) -> bool:
    """判斷 H3 標題是否為落地區段（落地確認表），而非規劃區段。"""
    if not line.startswith("### "):
        return False
    if any(token in line for token in _LANDING_HEADING_STRONG):
        return True
    # 弱判準限 spawn 標題下，避免「### 落地建議」等一般段落被整段剔除
    return (
        _LANDING_WORD in line
        and _PLANNING_WORD not in line
        and _is_spawn_section_heading(line)
    )


def _is_planning_heading(line: str) -> bool:
    """判斷 H3 標題是否為 spawn 規劃區段（spawn 區段且非落地區段）。"""
    return (
        line.startswith("### ")
        and _is_spawn_section_heading(line)
        and not _is_landing_heading(line)
    )


def _strip_landing_sections(section: str) -> str:
    """有規劃區段時移除落地區段，避免規劃表與落地確認表的列重複計入規劃數。

    只有落地區段時（單表寫法：一張表同時列規劃項與落地票）原樣回傳，
    否則該寫法的規劃數會變成 0、整張票不受檢。
    """
    lines = section.split("\n")
    if not any(_is_planning_heading(line) for line in lines):
        return section
    kept: list[str] = []
    skipping = False
    for line in lines:
        if line.startswith("### "):
            skipping = _is_landing_heading(line)
        if not skipping:
            kept.append(line)
    return "\n".join(kept)


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

    - row-per-spawn：每行一個 spawn 且同行含 P0-P3（如多項規劃表）
    - heading-based：每個 H3 同行含 Spawn + IMP/DOC/ANA（如 key-value 單項規劃表）
    - type-annotated：spawn 區段內表格行某 cell 為 IMP/DOC/ANA（容忍註記、無 P0-P3）

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
    named_ids, judged_without_id = _collect_named_ids(frontmatter, content)
    return len(named_ids), judged_without_id


def _extract_frontmatter_text(text: str) -> Optional[str]:
    """取出票檔開頭 `---` 與下一個 `---` 之間的 frontmatter 原文。"""
    if not text.startswith("---"):
        return None
    # 結尾須為整行 `---`，避免以 `----` 開頭的內容行提早截斷
    match = re.search(r"\n---[ \t]*(?:\n|$)", text[3:])
    if match is None:
        return None
    return text[3:3 + match.start()]


def _frontmatter_scalar(frontmatter_text: str, key: str) -> Optional[str]:
    """以行比對讀取 frontmatter 的純量欄位（不經 YAML 解析，掃描成本低）。"""
    match = re.search(
        rf"^{re.escape(key)}:\s*['\"]?([^'\"\n]*?)['\"]?\s*$",
        frontmatter_text,
        re.MULTILINE,
    )
    if not match:
        return None
    value = match.group(1).strip()
    return value or None


def _previous_ids(frontmatter_text: str) -> list[str]:
    """讀取 frontmatter `previous_ids:` 區塊下的列表項。"""
    items: list[str] = []
    in_block = False
    for line in frontmatter_text.split("\n"):
        if line.startswith("previous_ids:"):
            in_block = True
            continue
        if not in_block:
            continue
        stripped = line.strip()
        if stripped.startswith("- "):
            items.append(stripped[2:].strip().strip("'\""))
        elif stripped and not line.startswith(" "):
            break
    return items


def _is_child_id_of(candidate: str, ticket_id: str) -> bool:
    """candidate 是否為 ticket_id 的直接子號（如 `<id>.3`）。"""
    prefix = ticket_id + "."
    return candidate.startswith(prefix) and candidate[len(prefix):].isdigit()


_REVERSE_POINTER_FIELDS: tuple[str, ...] = ("source_ticket", "discovered_during", "parent_id")


def collect_reverse_lineage_ids(project_root: Path, ticket_id: str) -> set[str]:
    """掃描 `docs/work-logs/**/tickets/*.md`，回傳回指 ticket_id 的票 ID 集合。

    回指條件（任一）：`source_ticket`／`discovered_during`／`parent_id` 等於
    ticket_id；票 ID 本身是 ticket_id 的子號；`previous_ids` 含 ticket_id 的子號
    （子票被 migrate 到其他版本後僅剩此處保留血緣）。

    單檔讀取失敗時略過該檔繼續掃描；掃描結束若有略過的檔，拋出
    `ReverseLineageScanIncomplete`（帶已找到的 ID），由呼叫端決定失敗語意，
    避免一張壞檔使全部血緣遺失。
    """
    found: set[str] = set()
    errors: list[str] = []
    work_logs = project_root / "docs" / "work-logs"
    if not work_logs.is_dir():
        return found
    for path in work_logs.rglob("tickets/*.md"):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            errors.append(f"{path}: {exc}")
            continue
        if ticket_id not in text:
            continue
        fm_text = _extract_frontmatter_text(text)
        if fm_text is None:
            continue
        own_id = _frontmatter_scalar(fm_text, "id")
        if not own_id or own_id == ticket_id:
            continue
        points_back = any(
            _frontmatter_scalar(fm_text, field) == ticket_id
            for field in _REVERSE_POINTER_FIELDS
        )
        if (
            points_back
            or _is_child_id_of(own_id, ticket_id)
            or any(_is_child_id_of(old, ticket_id) for old in _previous_ids(fm_text))
        ):
            found.add(own_id)
    if errors:
        raise ReverseLineageScanIncomplete(found, errors)
    return found


class ReverseLineageScanIncomplete(Exception):
    """反向血緣掃描有檔案讀取失敗；`found` 為其餘檔案已找到的回指票。"""

    def __init__(self, found: set[str], errors: list[str]):
        super().__init__(f"{len(errors)} 個票檔讀取失敗，首例：{errors[0]}")
        self.found = found
        self.errors = errors


def _collect_named_ids(frontmatter: dict, content: str) -> tuple[set[str], int]:
    """回傳（spawned_tickets + children + 已判定 SR 的具名 ID 集合, 無 ID 已判定數）。"""
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
    return named_ids, judged_without_id


def check_ana_spawn_consistency(
    content: str,
    frontmatter: dict,
    logger,
    reverse_lineage_lookup: Optional[Callable[[str], set[str]]] = None,
) -> tuple[bool, str | None]:
    """檢查 ANA／DOC Solution spawn 規劃 vs 落地證據一致性。

    Args:
        content: ticket 完整內容（含 frontmatter + body）
        frontmatter: 已解析的 frontmatter dict
        logger: 日誌物件
        reverse_lineage_lookup: 以 ticket ID 查回指本票的票 ID 集合；只在
            frontmatter 與 SR 證據不足規劃數時呼叫。None 表示不查反向血緣。

    Returns:
        (should_block, message)
            - should_block=True：阻擋 complete（含完整阻擋訊息）
            - should_block=False + message：警告（反向血緣查詢失敗時的降級）
            - should_block=False + None：通過
    """
    ticket_type = (frontmatter.get("type") or "").strip().upper()
    if ticket_type not in _CHECKED_TYPES:
        logger.debug("非 ANA／DOC ticket（type=%s），跳過 spawn 一致性檢查", ticket_type)
        return False, None

    ticket_id = frontmatter.get("id", "未知")

    section = _extract_solution_section(content)
    if section is None or not section.strip():
        logger.debug("%s %s Solution 區段缺失或為空，跳過 spawn 一致性檢查", ticket_type, ticket_id)
        return False, None

    n_raw = _count_spawn_planning(_strip_landing_sections(section))
    n_exempted = _count_exemption_declarations(section)
    n_planned = max(0, n_raw - n_exempted)
    if n_planned == 0:
        logger.debug(
            "%s %s spawn 規劃 %d 項、豁免宣告 %d 則，無待落地項目",
            ticket_type,
            ticket_id,
            n_raw,
            n_exempted,
        )
        return False, None

    named_ids, n_judged_without_id = _collect_named_ids(frontmatter, content)
    n_reverse = 0
    lookup_failed = False
    if reverse_lineage_lookup is not None and len(named_ids) + n_judged_without_id < n_planned:
        try:
            reverse_ids = reverse_lineage_lookup(str(ticket_id))
        except ReverseLineageScanIncomplete as exc:
            # 部分檔案讀取失敗：已找到的照算；仍不足時才走 lookup_failed 降級
            n_reverse = len(exc.found - named_ids)
            named_ids |= exc.found
            if len(named_ids) + n_judged_without_id < n_planned:
                lookup_failed = True
            logger.error("%s %s 反向血緣掃描不完整: %s", ticket_type, ticket_id, exc)
            sys.stderr.write(
                f"[ana_spawn_consistency] {ticket_id} 反向血緣掃描不完整: {exc}\n"
            )
        except Exception as exc:  # noqa: BLE001 - 失敗語意見下方 lookup_failed 分支
            lookup_failed = True
            logger.error("%s %s 反向血緣查詢失敗，不加嚴: %s", ticket_type, ticket_id, exc)
            sys.stderr.write(
                f"[ana_spawn_consistency] {ticket_id} 反向血緣查詢失敗，部分落地降為警告: {exc}\n"
            )
        else:
            n_reverse = len(reverse_ids - named_ids)
            named_ids |= reverse_ids
    n_named = len(named_ids)
    n_actual = n_named + n_judged_without_id

    if n_actual >= n_planned:
        logger.info(
            "%s %s spawn 一致性通過：規劃=%d，落地=%d（具名 ticket 去重後=%d，其中反向血緣=%d，無 ID 已判定=%d）",
            ticket_type,
            ticket_id,
            n_planned,
            n_actual,
            n_named,
            n_reverse,
            n_judged_without_id,
        )
        return False, None

    # 查詢失敗時只保留修訂前的阻擋（ANA 落地為 0），其餘降為警告
    keeps_legacy_block = ticket_type == "ANA" and n_actual == 0
    if lookup_failed and not keeps_legacy_block:
        logger.warning(
            "%s %s 規劃 %d 項、落地 %d 項，反向血緣查詢失敗，降為警告",
            ticket_type,
            ticket_id,
            n_planned,
            n_actual,
        )
        return False, _format_lookup_failed_warning(ticket_id, ticket_type, n_planned, n_actual)

    logger.error(
        "%s %s Solution 規劃 %d 項 spawn，落地 %d 項（具名 ticket 去重後=%d，其中反向血緣=%d，"
        "無 ID 已判定=%d），未落地 %d 項 - 阻擋 complete",
        ticket_type,
        ticket_id,
        n_planned,
        n_actual,
        n_named,
        n_reverse,
        n_judged_without_id,
        n_planned - n_actual,
    )
    return True, _format_block_message(
        ticket_id, ticket_type, n_planned, n_named, n_judged_without_id
    )


# ----------------------------------------------------------------------------
# 訊息格式化
# ----------------------------------------------------------------------------


def _format_block_message(
    ticket_id: str,
    ticket_type: str,
    n_planned: int,
    n_named: int,
    n_judged_without_id: int,
) -> str:
    n_actual = n_named + n_judged_without_id
    return (
        f"[ERROR] Acceptance Gate: {ticket_type} Ticket Solution spawn 規劃未落地\n"
        f"\n"
        f"Ticket: {ticket_id}\n"
        f"待落地 spawn 規劃數: {n_planned}（已扣除豁免宣告；落地確認區段不計入規劃數）\n"
        f"落地證據: {n_actual}"
        f"（具名 ticket 去重後 = {n_named}，含 spawned_tickets、children、"
        f"回指本票的票；無 ticket ID 的已判定項 = {n_judged_without_id}）\n"
        f"未落地: {n_planned - n_actual} 項\n"
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


def _format_lookup_failed_warning(
    ticket_id: str, ticket_type: str, n_planned: int, n_actual: int
) -> str:
    return (
        f"[WARNING] Acceptance Gate: {ticket_type} Ticket spawn 落地數不足，"
        f"但反向血緣查詢失敗，本次不阻擋\n"
        f"\n"
        f"Ticket: {ticket_id}\n"
        f"待落地 spawn 規劃數: {n_planned}；frontmatter 與 Spawn Request 落地證據: {n_actual}\n"
        f"回指本票的票（source_ticket／discovered_during／parent_id／previous_ids）未能掃描，"
        f"錯誤見 stderr 與 hook 日誌。\n"
        f"請確認是否有遺漏的 spawn ticket 未建立。\n"
    )
