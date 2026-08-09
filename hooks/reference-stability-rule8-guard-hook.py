#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""reference-stability-rule8-guard — PreToolUse Hook

偵測 `.claude/` 框架檔案寫入內容中新增的專案層級識別符（ticket ID），
落實 reference-stability 規則 8（框架文件禁止引用專案層級識別符）
「引用性質判準：全禁原則與五類分類」的 hook 強制層。

偵測策略（全禁 + 逐檔淨增量比對，0.2.1-W3-315）：
  ticket ID 在框架文件的任何出現，除落入第 4 類（被說明對象型，白名單
  路徑）或第 5 類（測試資料型，測試路徑）豁免，一律視為候選違規——
  不再依「跳轉引導詞」句型判斷依賴型 vs 歷史錨點型（該判準已被
  reference-stability-rules.md 規則 8 汰換，見同檔「與舊兩類判準的對應」）。

存量凍結機制（避免對既有大量存量違規產生噪音壓力，ARCH-016 失效模式）：
  本 hook 於 PreToolUse（編輯套用前）讀取目標檔案「編輯前」的磁碟內容作為
  該檔的即時基準（不需另存快照檔），套用本次 Edit/Write/MultiEdit 重建
  「編輯後」內容，比較兩者的 ticket ID 命中集合。只有編輯後集合中「編輯前
  不存在」的新增 ID 才觸發阻擋；既有於檔案內的舊 ID（存量）永久視為
  已凍結，不因後續無關編輯而重複觸發。此設計以逐檔即時差異取代靜態
  allowlist 快照，避免「整檔白名單」讓該檔案後續新增違規也被放行的漏洞
  （同一檔案的存量與新增用內容比對區分，而非用路徑層級的全有全無豁免）。

阻擋機制（0.2.1-W3-063，觀察期誤報率 0/10 後升級為 exit 2）：
  淨增量新增命中且非豁免路徑 → exit 2 阻擋（stdout 於 exit 2 時被
  runtime 丟棄，訊息一律寫 stderr，見 IMP-BAL-001）。行內 marker 逃生閥
  （見下）可豁免個別行的命中，供 self-test 測資與規則正文示範等合法
  場景繞過阻擋，不需整檔或整路徑豁免。

行內 marker 逃生閥：
  語法：`rule8-exempt: <category>:<reason>`（跨檔案類型通用語法，不綁
  HTML comment 或 Python 註解符號）。生效範圍為 marker 所在行及其下一行
  （逐行生效，非整檔放行）。合法 category 僅兩類：
    - testdata     — 守衛或工具自身 self-test 測資需真實 ID 形態
    - illustration — 規則/方法論正文示範 ID 形態，且不便置於 code fence
  category 不在清單內，或 reason 為空，視為格式錯誤，仍阻擋（exit 2）
  並在 stderr 分別指出錯誤項目，不與一般命中共用同一段訊息。

觸發時機: PreToolUse Edit / Write / MultiEdit
掃描範圍: 目標檔案路徑位於 `.claude/` 下，且不在 `.claude/handoff/archive/`
          （該目錄為歷史紀錄，規則 8 明文豁免）
偵測樣式:
  - 版本化 ticket ID：`\\d+\\.\\d+\\.\\d+-W\\d+-\\d+`（如 9.9.9-W9-999）
  - 裸格式 ticket ID：`W\\d+-\\d+`（如 W9-999）
放行例外（不視為 ticket ID 候選）:
  - 框架 error-pattern ID（PC-xxx / IMP-xxx / ARCH-xxx）與其檔名
  - 日期字串（YYYY-MM-DD）
  - Claude Code 版本號（CC 開頭 + 版本數字）
  - code fence（```...```）內的內容（格式示範，非實際引用）
機械可判定豁免（reference-stability-rules.md 規則 8 §引用性質判準）:
  - 第 4 類（被說明對象型）：路徑落在 WHITELIST_PATHS（成員上限 3，
    目前僅 .claude/references/ticket-id-conventions.md）
  - 第 5 類（測試資料型）：路徑含 /tests/ 目錄區段，或檔名符合
    test_*.py / *_test.py
行為: 命中新增 ticket ID 且非豁免路徑、且未被有效 marker 涵蓋
      → exit 2 阻擋（stderr 含命中清單、規則出處、marker 語法範例）
      marker 存在但格式錯誤（未知 category / 理由為空）
      → exit 2 阻擋（stderr 另段說明格式錯誤，不與一般命中訊息合併）
      無新增命中 / 全屬既有存量 / 非掃描範圍 / 豁免路徑 / 輸入異常 /
      新增命中全數被有效 marker 涵蓋
      → 靜默放行（既有存量命中額外寫入 debug 日誌供觀察）

對應規則：.claude/references/reference-stability-rules.md 規則 8
及其「引用性質判準：全禁原則與五類分類」章節
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from lib import setup_hook_logging, run_hook_safely, read_json_from_stdin
except ImportError as e:
    print(f"[Hook Import Error] {Path(__file__).name}: {e}", file=sys.stderr)
    sys.exit(0)


EXIT_ALLOW = 0
EXIT_BLOCK = 2

# 掃描範圍：位於 .claude/ 下，排除 handoff/archive（歷史紀錄豁免）
SCAN_PREFIX = ".claude/"
EXEMPT_DIR_PREFIX = ".claude/handoff/archive/"

# 第 4 類白名單（被說明對象型）。成員上限 3（reference-stability-rules.md
# §第 4 類白名單明文規定）；超過 3 個須改用可陳述的通用條件取代逐檔列舉。
WHITELIST_PATHS = frozenset(
    {
        ".claude/references/ticket-id-conventions.md",
    }
)

# 第 5 類豁免（測試資料型）路徑樣式
TEST_DIR_SEGMENT = "/tests/"
TEST_FILENAME_PATTERN = re.compile(r"^(test_.+\.py|.+_test\.py)$")

# 專案 ticket ID 樣式
VERSIONED_TICKET_PATTERN = re.compile(r"\b\d+\.\d+\.\d+-W\d+-\d+\b")
BARE_TICKET_PATTERN = re.compile(r"\bW\d+-\d+\b")

# 放行例外樣式（框架內部識別符 / 外部平台版本 / 日期，規則 8 明文允許）
FRAMEWORK_ERROR_PATTERN_ID = re.compile(r"\b(?:PC|IMP|ARCH)-\d+\b")
DATE_PATTERN = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
CC_VERSION_PATTERN = re.compile(r"\bCC\s+\d+\.\d+(?:\.\d+)?\b")

# Code fence（```...```，含語言標記行）：格式示範內容不視為實際引用
CODE_FENCE_PATTERN = re.compile(r"```.*?```", re.DOTALL)

# 行內 marker 逃生閥：`rule8-exempt: <category>:<reason>`
MARKER_PATTERN = re.compile(r"rule8-exempt:\s*([A-Za-z_]+):(.*)")
VALID_MARKER_CATEGORIES = frozenset({"testdata", "illustration"})


def normalize_relpath(file_path: str) -> Optional[str]:
    """取出檔案路徑中 .claude/ 起始的相對片段；不在 .claude/ 下回傳 None。"""
    if not file_path:
        return None
    normalized = file_path.replace("\\", "/")
    idx = normalized.find(SCAN_PREFIX)
    if idx == -1:
        return None
    return normalized[idx:]


def is_scanned_path(file_path: str) -> bool:
    """判斷檔案路徑是否落在規則 8 掃描範圍（.claude/ 下，排除 handoff/archive）。"""
    rel = normalize_relpath(file_path)
    if rel is None:
        return False
    if rel.startswith(EXEMPT_DIR_PREFIX):
        return False
    return True


def is_class4_whitelisted(file_path: str) -> bool:
    """第 4 類（被說明對象型）豁免：路徑落在 WHITELIST_PATHS。"""
    rel = normalize_relpath(file_path)
    return rel in WHITELIST_PATHS if rel is not None else False


def is_class5_test_path(file_path: str) -> bool:
    """第 5 類（測試資料型）豁免：路徑含 /tests/ 或檔名符合 test_*.py / *_test.py。"""
    rel = normalize_relpath(file_path)
    if rel is None:
        return False
    if TEST_DIR_SEGMENT in rel:
        return True
    return bool(TEST_FILENAME_PATTERN.match(Path(rel).name))


def is_exempt_path(file_path: str) -> bool:
    """第 4 / 5 類機械可判定豁免的合併判斷。"""
    return is_class4_whitelisted(file_path) or is_class5_test_path(file_path)


def _strip_exempt_spans(text: str) -> str:
    """將放行例外樣式（框架 ID / 日期 / CC 版本）從文字中挖除，避免誤判為專案 ticket ID。

    挖除而非僅檢查是否存在，可避免例外樣式與 ticket 樣式在同一段落中
    因位置相鄰而互相干擾判定。
    """
    text = FRAMEWORK_ERROR_PATTERN_ID.sub(" ", text)
    text = DATE_PATTERN.sub(" ", text)
    text = CC_VERSION_PATTERN.sub(" ", text)
    return text


def _blank_match_preserving_newlines(match: "re.Match[str]") -> str:
    """把命中片段的非換行字元換成空白、換行字元原樣保留（子函式供 re.sub 呼叫）。"""
    return "".join("\n" if ch == "\n" else " " for ch in match.group(0))


def _strip_code_fences_preserve_lines(text: str) -> str:
    """挖除 code fence（```...```）內容，但保留原始換行位置與行號對應。

    與逐字元替換為單一空白（會使多行 fence 併為一行、行號位移）不同，
    本函式僅將 fence 命中片段內的非換行字元換成空白，換行字元原樣保留。
    效果：fence 起訖標記所在行的行號不變，且 fence 結束標記 ``` 之後
    「同一行殘留的文字」不在命中片段內，不受影響——這是 fence 標記與
    內容同行時的唯一判定依據（曾因整段挖除與逐行行區間排除各自實作而
    邊界不一致，導致命中在其中一份實作被排除、另一份未排除而漏擋）。
    """
    return CODE_FENCE_PATTERN.sub(_blank_match_preserving_newlines, text)


def find_ticket_id_hits_with_lines(text: str) -> List[Tuple[str, int]]:
    """逐行找出專案 ticket ID 候選，回傳 (ticket_id, line_index) list（0-based，不去重）。

    單一事實來源：pattern 掃描與 code fence 排除的唯一實作，
    find_ticket_id_hits 為其去重保序投影。

    marker 逃生閥判定需要逐行結果（生效範圍以行為單位，需知道每筆命中
    落在哪一行才能判斷該行或上一行是否有有效 marker）；fence 排除改用
    _strip_code_fences_preserve_lines 的逐字元挖除（保留行號對應），
    不再有第二套獨立的行區間排除邏輯與其分歧。
    """
    if not text:
        return []
    cleaned = _strip_code_fences_preserve_lines(text)
    hits: List[Tuple[str, int]] = []
    for idx, line in enumerate(cleaned.split("\n")):
        cleaned_line = _strip_exempt_spans(line)
        for pattern in (VERSIONED_TICKET_PATTERN, BARE_TICKET_PATTERN):
            for match in pattern.finditer(cleaned_line):
                hits.append((match.group(0), idx))
    return hits


def find_ticket_id_hits(text: str) -> List[str]:
    """在文字中找出專案 ticket ID 候選（已排除放行例外與 code fence），去重保序。

    改為 find_ticket_id_hits_with_lines 的去重保序投影，不再自行做整段
    pattern 掃描與 fence 挖除。兩函式對 fence 邊界的判定因此共用同一份
    實作，結構上不可能再漂移（先前發現的「fence 結束標記與內容同行」
    漏擋即源自兩份獨立實作邊界不一致）。

    全禁原則下本函式即為完整偵測器，不再區分依賴型 / 歷史錨點型——
    是否觸發阻擋改由呼叫端以「編輯前後淨增量」與「行內 marker」判斷
    （見 main / filter_marker_exempt）。
    """
    if not text:
        return []
    hits: List[str] = []
    seen = set()
    for value, _line_idx in find_ticket_id_hits_with_lines(text):
        if value not in seen:
            seen.add(value)
            hits.append(value)
    return hits


def _read_existing_file(file_path: str) -> str:
    """讀取檔案編輯前的磁碟內容；不存在或無法解碼時回傳空字串（視為新檔）。"""
    try:
        return Path(file_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def reconstruct_pre_post_text(
    tool_name: str, tool_input: dict, file_path: str
) -> Tuple[str, str]:
    """讀取編輯前檔案內容並套用本次工具呼叫，回傳 (pre_text, post_text)。

    設計目的：以「編輯前磁碟內容」作為該檔存量的即時基準，取代另存快照檔——
    檔案既有的 ticket ID 天然落在 pre_text 中而被視為存量凍結，僅 post_text
    相對 pre_text 新增的命中才是本次操作引入的違規。

    重建失敗時的保守退化：old_string 在 pre_text 中找不到（例如 pre_text
    讀取失敗，或呼叫端傳入的片段與磁碟內容不一致）時，退化為
    pre_text=""、post_text=新增片段本身，確保寧可多掃也不漏掃。
    """
    pre_text = _read_existing_file(file_path)

    if tool_name == "Write":
        content = tool_input.get("content")
        post_text = content if isinstance(content, str) else ""
        return pre_text, post_text

    if tool_name == "Edit":
        old_string = tool_input.get("old_string")
        new_string = tool_input.get("new_string")
        if not isinstance(old_string, str) or not isinstance(new_string, str):
            return pre_text, pre_text
        if old_string and old_string in pre_text:
            if tool_input.get("replace_all"):
                post_text = pre_text.replace(old_string, new_string)
            else:
                post_text = pre_text.replace(old_string, new_string, 1)
            return pre_text, post_text
        # old_string 不在 pre_text 中（罕見）：退化為保守模式
        return "", new_string

    if tool_name == "MultiEdit":
        edits = tool_input.get("edits")
        if not isinstance(edits, list):
            return pre_text, pre_text
        post_text = pre_text
        fallback_new_parts: List[str] = []
        reconstruction_failed = False
        for edit in edits:
            if not isinstance(edit, dict):
                continue
            old_string = edit.get("old_string")
            new_string = edit.get("new_string")
            if not isinstance(old_string, str) or not isinstance(new_string, str):
                continue
            fallback_new_parts.append(new_string)
            if old_string and old_string in post_text:
                if edit.get("replace_all"):
                    post_text = post_text.replace(old_string, new_string)
                else:
                    post_text = post_text.replace(old_string, new_string, 1)
            else:
                reconstruction_failed = True
        if reconstruction_failed:
            # 任一 edit 重建失敗：整體退化為保守模式，僅掃描新增片段集合
            return "", "\n".join(fallback_new_parts)
        return pre_text, post_text

    return pre_text, pre_text


def diff_new_hits(pre_text: str, post_text: str) -> List[str]:
    """回傳 post_text 相對 pre_text 淨增量的 ticket ID 命中（去重保序）。"""
    pre_hits = set(find_ticket_id_hits(pre_text))
    post_hits = find_ticket_id_hits(post_text)

    new_hits: List[str] = []
    seen = set()
    for hit in post_hits:
        if hit in pre_hits or hit in seen:
            continue
        seen.add(hit)
        new_hits.append(hit)
    return new_hits


def build_marker_syntax_hint() -> str:
    """組合 marker 逃生閥語法說明與兩個 category 的具體範例（訊息共用片段）。"""
    return (
        "逃生閥語法（同行或下一行皆可）：`rule8-exempt: <category>:<reason>`\n"
        "合法 category：\n"
        "  testdata    — 守衛或工具自身 self-test 測資需真實 ID 形態，例：\n"
        "                rule8-exempt: testdata:self-test 存量凍結案例需真實 ID 形態\n"
        "  illustration — 規則/方法論正文示範 ID 形態，且不便置於 code fence，例：\n"
        "                rule8-exempt: illustration:規則 8 主表展示裸格式與版本化格式差異\n"
    )


def build_block_message(file_path: str, blocked_hits: List[str]) -> str:
    """組合一般命中阻擋訊息：命中清單 + 規則出處 + 處置建議 + marker 語法。"""
    hits_display = "、".join(blocked_hits)
    return (
        f"[BLOCKED][reference-stability-rule8] 本次操作已被阻擋（exit 2）："
        f".claude/ 框架檔案新增內容含專案層級 ticket ID 引用：{file_path}\n"
        f"新增命中：{hits_display}\n"
        f"依據：.claude/references/reference-stability-rules.md 規則 8"
        f"「引用性質判準：全禁原則與五類分類」（框架文件禁止引用專案層級識別符，"
        f"跨專案 sync 後會變成死連結；既有於檔案內的存量引用不重複觸發本阻擋）。\n"
        f"處置：依五類分類移除該 ticket ID——論證依據型改自足 WHY 或先寫方法論"
        f"再引用；時點標注型改標日期；案例敘事主詞型改描述性標籤。若此路徑本應屬"
        f"第 4 類（被說明對象型）或第 5 類（測試資料型），請確認路徑落在白名單"
        f"（.claude/references/ticket-id-conventions.md）或測試路徑（/tests/、"
        f"test_*.py、*_test.py）。\n"
        f"{build_marker_syntax_hint()}"
        f"這是阻擋（exit 2），非提示——若確認此 ID 屬合法情境（測資 / 示範），"
        f"請在該行或上一行加上逃生閥 marker 後重試。"
    )


def build_marker_format_error_message(
    file_path: str, line_idx: int, category: str, reason: str
) -> str:
    """組合 marker 格式錯誤訊息（獨立段落，不與一般命中訊息合併）。"""
    line_no = line_idx + 1
    problems = []
    if category not in VALID_MARKER_CATEGORIES:
        problems.append(f"category「{category}」不在合法清單（testdata / illustration）")
    if not reason:
        problems.append("reason 為空（僅寫 category 視為無條件旁路，禁止）")
    problem_text = "；".join(problems) if problems else "格式不符"
    return (
        f"[BLOCKED][reference-stability-rule8] marker 格式錯誤，仍阻擋（exit 2）："
        f"{file_path} 第 {line_no} 行\n"
        f"問題：{problem_text}\n"
        f"{build_marker_syntax_hint()}"
    )


def _find_marker_lines(post_text: str) -> Dict[int, Tuple[bool, str, str]]:
    """逐行掃描 marker 語法，回傳 {行索引: (是否有效, category, reason)}。"""
    marker_info: Dict[int, Tuple[bool, str, str]] = {}
    for idx, line in enumerate(post_text.split("\n")):
        match = MARKER_PATTERN.search(line)
        if not match:
            continue
        category = match.group(1)
        reason = match.group(2).strip()
        is_valid = category in VALID_MARKER_CATEGORIES and bool(reason)
        marker_info[idx] = (is_valid, category, reason)
    return marker_info


def filter_marker_exempt(
    file_path: str, post_text: str, new_hits: List[str]
) -> Tuple[List[str], List[str]]:
    """依行內 marker 逃生閥篩選新增命中，回傳 (blocked_hits, format_error_messages)。

    marker 生效範圍為所在行與下一行（逐行生效，非整檔放行）。同一筆命中
    若所在行或上一行有有效 marker → 豁免；若有 marker 但格式錯誤（未知
    category 或理由為空）→ 該命中仍阻擋，且產生獨立的格式錯誤訊息。

    前提（呼叫端契約）：`new_hits` 必須是針對同一份 `post_text` 呼叫
    `find_ticket_id_hits` 得到結果的子集。此契約現由單一事實來源保證
    成立——find_ticket_id_hits 已改為 find_ticket_id_hits_with_lines 的
    去重投影（見該函式），故 `new_hits` 中的每個值必然能在
    `find_ticket_id_hits_with_lines(post_text)` 找到至少一筆對應的
    (value, line_idx)。曾經需要的「找不到對應行時 fail-closed 阻擋」
    保底分支（因兩函式各自獨立實作 fence 排除、邊界可能不一致）已隨此
    次重構結構性消除，不再需要，故移除。若未來任一呼叫端違反此契約
    （傳入非源自 find_ticket_id_hits(post_text) 的 new_hits），本函式會
    靜默忽略該值——這是新的風險面，留意 main() 為唯一生產路徑且已符合
    契約。
    """
    marker_info = _find_marker_lines(post_text)
    new_hits_set = set(new_hits)
    hits_with_lines = find_ticket_id_hits_with_lines(post_text)

    blocked: List[str] = []
    seen_blocked = set()
    format_error_messages: List[str] = []
    seen_error_lines: Set[int] = set()

    for value, line_idx in hits_with_lines:
        if value not in new_hits_set:
            continue

        exempted = False
        invalid_marker_line: Optional[int] = None
        for marker_line in (line_idx, line_idx - 1):
            if marker_line in marker_info:
                is_valid, _category, _reason = marker_info[marker_line]
                if is_valid:
                    exempted = True
                    break
                if invalid_marker_line is None:
                    invalid_marker_line = marker_line

        if exempted:
            continue

        if invalid_marker_line is not None:
            if invalid_marker_line not in seen_error_lines:
                seen_error_lines.add(invalid_marker_line)
                _is_valid, category, reason = marker_info[invalid_marker_line]
                format_error_messages.append(
                    build_marker_format_error_message(
                        file_path, invalid_marker_line, category, reason
                    )
                )
            continue

        if value not in seen_blocked:
            seen_blocked.add(value)
            blocked.append(value)

    return blocked, format_error_messages


def main() -> int:
    """主入口：讀取 stdin → 篩選掃描範圍與豁免 → 重建編輯前後內容 → 淨增量比對 → marker 篩選 → 阻擋。"""
    logger = setup_hook_logging("reference-stability-rule8-guard")

    input_data = read_json_from_stdin(logger)
    if not input_data:
        logger.debug("輸入為空或解析失敗，預設允許")
        return EXIT_ALLOW

    tool_name = input_data.get("tool_name", "")
    if tool_name not in ("Edit", "Write", "MultiEdit"):
        logger.debug(f"工具 {tool_name} 不在本 hook 檢查範圍，跳過")
        return EXIT_ALLOW

    tool_input = input_data.get("tool_input") or {}
    file_path = tool_input.get("file_path", "")

    if not is_scanned_path(file_path):
        logger.debug(f"路徑 {file_path} 不在規則 8 掃描範圍，跳過")
        return EXIT_ALLOW

    if is_class4_whitelisted(file_path):
        logger.debug(f"路徑 {file_path} 屬第 4 類白名單（被說明對象型），豁免")
        return EXIT_ALLOW

    if is_class5_test_path(file_path):
        logger.debug(f"路徑 {file_path} 屬第 5 類測試路徑（測試資料型），豁免")
        return EXIT_ALLOW

    pre_text, post_text = reconstruct_pre_post_text(tool_name, tool_input, file_path)
    new_hits = diff_new_hits(pre_text, post_text)

    if not new_hits:
        existing_hits = find_ticket_id_hits(post_text)
        if existing_hits:
            logger.debug(
                f"僅命中既有（凍結）ticket ID，不觸發阻擋："
                f"file={file_path} tool={tool_name} hits={sorted(set(existing_hits))}"
            )
        else:
            logger.debug(f"未偵測到 ticket ID 命中：{file_path}")
        return EXIT_ALLOW

    blocked_hits, format_error_messages = filter_marker_exempt(
        file_path, post_text, new_hits
    )

    if not blocked_hits and not format_error_messages:
        logger.debug(
            f"新增命中全數被有效 marker 豁免：file={file_path} hits={new_hits}"
        )
        return EXIT_ALLOW

    messages = []
    if blocked_hits:
        messages.append(build_block_message(file_path, blocked_hits))
    messages.extend(format_error_messages)
    sys.stderr.write("\n\n".join(messages) + "\n")
    logger.warning(
        f"阻擋新增專案 ticket ID 引用：file={file_path} tool={tool_name} "
        f"blocked={blocked_hits} format_error_lines={len(format_error_messages)}"
    )
    return EXIT_BLOCK


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--self-test":
        import tempfile

        failures: List[str] = []

        # 正例：應偵測到 ticket ID 候選（find_ticket_id_hits 為全量偵測，
        # 不再區分依賴型 / 歷史錨點型）
        positive_cases = [
            "版本化格式：本 hook 修復 9.9.9-W9-999 遺漏的問題。",
            "裸格式：詳見 W9-999 的分析結論。",
            # rule8-exempt: testdata:self-test 正例測資需真實 ID 形態
            "無跳轉詞裸引用（0.2.1-W3-308 形態）：  # from 0.2.1-W3-308",
        ]
        negative_cases = [
            "已知案例：PC-050、IMP-003、ARCH-002。",
            "此變更於 2026-07-08 完成。",
            "CC 2.1.97 新增 /agents 分頁能力。",
        ]

        for case in positive_cases:
            hits = find_ticket_id_hits(case)
            if not hits:
                failures.append(f"[FAIL] 正例未偵測到命中: {case!r}")
            else:
                print(f"[PASS] 正例偵測到 {hits}: {case!r}")

        for case in negative_cases:
            hits = find_ticket_id_hits(case)
            if hits:
                failures.append(f"[FAIL] 反例誤判命中 {hits}: {case!r}")
            else:
                print(f"[PASS] 反例未誤判: {case!r}")

        # 路徑範圍測試
        if not is_scanned_path(".claude/rules/core/pm-role.md"):
            failures.append("[FAIL] .claude/rules/ 應在掃描範圍")
        else:
            print("[PASS] .claude/rules/ 在掃描範圍")

        if is_scanned_path(".claude/handoff/archive/2026-01-01.md"):
            failures.append("[FAIL] .claude/handoff/archive/ 應豁免")
        else:
            print("[PASS] .claude/handoff/archive/ 已豁免")

        if is_scanned_path("docs/work-logs/v0.38/foo.md"):
            failures.append("[FAIL] docs/ 不應在掃描範圍")
        else:
            print("[PASS] docs/ 不在掃描範圍")

        # 第 4 / 5 類機械可判定豁免測試
        if not is_class4_whitelisted(".claude/references/ticket-id-conventions.md"):
            failures.append("[FAIL] ticket-id-conventions.md 應屬第 4 類白名單")
        else:
            print("[PASS] 第 4 類白名單判定正確")

        if not is_class5_test_path(".claude/hooks/tests/test_foo_hook.py"):
            failures.append("[FAIL] .claude/hooks/tests/ 應屬第 5 類測試路徑")
        else:
            print("[PASS] 第 5 類測試路徑判定正確（/tests/ 目錄）")

        if not is_class5_test_path(".claude/scripts/foo_test.py"):
            failures.append("[FAIL] *_test.py 檔名應屬第 5 類測試路徑")
        else:
            print("[PASS] 第 5 類測試路徑判定正確（*_test.py 檔名）")

        if is_exempt_path(".claude/rules/core/pm-role.md"):
            failures.append("[FAIL] 一般規則檔不應被誤判為豁免")
        else:
            print("[PASS] 一般規則檔未被誤判為豁免")

        # code fence 內容不應被視為實際引用
        fence_case = "說明如下：\n```\n詳見 W9-999 的分析結論\n```\n本行本身無引用。"
        fence_hits = find_ticket_id_hits(fence_case)
        if fence_hits:
            failures.append(f"[FAIL] code fence 內容誤判為引用 {fence_hits}: {fence_case!r}")
        else:
            print("[PASS] code fence 內容已正確排除")

        # 存量凍結機制：編輯前後淨增量比對（0.2.1-W3-315 acceptance 1/3）
        with tempfile.TemporaryDirectory() as tmpdir:
            existing_file = Path(tmpdir) / "existing.md"
            existing_file.write_text(
                # rule8-exempt: testdata:self-test 存量凍結案例需真實 ID 形態
                "既有內容第一行\n舊引用（0.2.1-W3-100 教訓）\n既有內容第三行\n",
                encoding="utf-8",
            )

            # 案例 A：Edit 僅重排既有內容，未新增任何 ticket ID → 不應告警
            pre_a, post_a = reconstruct_pre_post_text(
                "Edit",
                {
                    "file_path": str(existing_file),
                    "old_string": "既有內容第三行",
                    # rule8-exempt: testdata:self-test 存量凍結案例需真實 ID 形態
                    "new_string": "既有內容第三行（微調文字，仍含 0.2.1-W3-100）",
                },
                str(existing_file),
            )
            new_hits_a = diff_new_hits(pre_a, post_a)
            if new_hits_a:
                failures.append(f"[FAIL] 純重排既有 ticket ID 不應觸發新增命中: {new_hits_a}")
            else:
                print("[PASS] 存量凍結：重排既有 ticket ID 不觸發新增命中")

            # 案例 B：Edit 在已有存量違規的檔案中新增一個「不同」的 ticket ID
            # → 凍結範圍內新增命中仍應告警（acceptance 3 的關鍵情境）
            pre_b, post_b = reconstruct_pre_post_text(
                "Edit",
                {
                    "file_path": str(existing_file),
                    "old_string": "既有內容第一行",
                    "new_string": "既有內容第一行\n新增引用（0.2.1-W3-999 教訓）",
                },
                str(existing_file),
            )
            new_hits_b = diff_new_hits(pre_b, post_b)
            # 版本化與裸格式樣式各自獨立匹配（沿用既有 find_ticket_id_hits 行為，
            # 同一 ticket ID 會同時產生版本化與裸格式兩筆命中），故預期兩筆。
            # rule8-exempt: testdata:self-test 存量凍結案例需真實 ID 形態
            if set(new_hits_b) != {"0.2.1-W3-999", "W3-999"} or "0.2.1-W3-100" in new_hits_b:
                failures.append(
                    "[FAIL] 凍結範圍內新增命中應被偵測且不含既有 0.2.1-W3-100，"
                    f"預期 {{'0.2.1-W3-999', 'W3-999'}}，實際 {new_hits_b}"
                )
            else:
                print("[PASS] 凍結範圍內新增命中仍正確告警（不含既有 0.2.1-W3-100）")

            # 案例 C：Write 建立全新檔案含 ticket ID（無存量基準，pre_text 為空）
            new_file = Path(tmpdir) / "brand_new.md"
            pre_c, post_c = reconstruct_pre_post_text(
                "Write",
                {
                    "file_path": str(new_file),
                    # rule8-exempt: testdata:self-test 新檔案案例需真實 ID 形態
                    "content": "全新檔案，直接 # from 0.2.1-W3-308 無跳轉詞",
                },
                str(new_file),
            )
            new_hits_c = diff_new_hits(pre_c, post_c)
            # rule8-exempt: testdata:self-test 新檔案案例需真實 ID 形態
            if "0.2.1-W3-308" not in new_hits_c:
                failures.append(f"[FAIL] 新檔案含 ticket ID 應被偵測，實際 {new_hits_c}")
            else:
                print("[PASS] 新檔案（無存量基準）正確偵測新增 ticket ID")

        # marker 逃生閥：同行生效
        marker_same_line_text = (
            "既有內容\n"
            "新增引用 0.2.1-W3-777 rule8-exempt: testdata:self-test 同行案例\n"
        )
        blocked_same, errors_same = filter_marker_exempt(
            "dummy.md", marker_same_line_text, ["0.2.1-W3-777", "W3-777"]
        )
        if blocked_same or errors_same:
            failures.append(
                f"[FAIL] marker 同行應豁免，實際 blocked={blocked_same} "
                f"errors={len(errors_same)}"
            )
        else:
            print("[PASS] marker 逃生閥同行生效")

        # marker 逃生閥：下一行生效
        marker_next_line_text = (
            "rule8-exempt: illustration:self-test 下一行案例\n"
            "新增引用 0.2.1-W3-778\n"
        )
        blocked_next, errors_next = filter_marker_exempt(
            "dummy.md", marker_next_line_text, ["0.2.1-W3-778", "W3-778"]
        )
        if blocked_next or errors_next:
            failures.append(
                f"[FAIL] marker 下一行應豁免，實際 blocked={blocked_next} "
                f"errors={len(errors_next)}"
            )
        else:
            print("[PASS] marker 逃生閥下一行生效")

        # marker 格式錯誤：未知 category 仍阻擋
        marker_bad_category_text = "新增引用 0.2.1-W3-779 rule8-exempt: unknown:理由存在\n"
        blocked_bad_cat, errors_bad_cat = filter_marker_exempt(
            "dummy.md", marker_bad_category_text, ["0.2.1-W3-779", "W3-779"]
        )
        if not errors_bad_cat:
            failures.append("[FAIL] 未知 category 應產生格式錯誤並阻擋")
        else:
            print("[PASS] marker 未知 category 格式錯誤仍阻擋")

        # marker 格式錯誤：理由為空仍阻擋
        marker_empty_reason_text = "新增引用 0.2.1-W3-780 rule8-exempt: testdata:\n"
        blocked_empty, errors_empty = filter_marker_exempt(
            "dummy.md", marker_empty_reason_text, ["0.2.1-W3-780", "W3-780"]
        )
        if not errors_empty:
            failures.append("[FAIL] 空理由應產生格式錯誤並阻擋")
        else:
            print("[PASS] marker 空理由格式錯誤仍阻擋")

        if failures:
            print("\n".join(failures))
            sys.exit(1)
        print("[self-test] 全部通過")
        sys.exit(0)

    sys.exit(run_hook_safely(main, "reference-stability-rule8-guard"))
