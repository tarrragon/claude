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
  不存在」的新增 ID 才觸發 WARNING；既有於檔案內的舊 ID（存量）永久視為
  已凍結，不因後續無關編輯而重複觸發。此設計以逐檔即時差異取代靜態
  allowlist 快照，避免「整檔白名單」讓該檔案後續新增違規也被放行的漏洞
  （同一檔案的存量與新增用內容比對區分，而非用路徑層級的全有全無豁免）。

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
行為: 命中新增 ticket ID 且非豁免路徑 → WARNING（stderr + 日誌），
      exit 0（允許，不阻擋；改寫品質判定仍需人工，見規則 8「硬性強制
      的範圍」章節）
      無新增命中 / 全屬既有存量 / 非掃描範圍 / 豁免路徑 / 輸入異常
      → 靜默放行（既有存量命中額外寫入 debug 日誌供觀察）

對應規則：.claude/references/reference-stability-rules.md 規則 8
及其「引用性質判準：全禁原則與五類分類」章節
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from lib import setup_hook_logging, run_hook_safely, read_json_from_stdin
except ImportError as e:
    print(f"[Hook Import Error] {Path(__file__).name}: {e}", file=sys.stderr)
    sys.exit(0)


EXIT_ALLOW = 0

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


def _strip_code_fences(text: str) -> str:
    """挖除 code fence（```...```）區塊，格式示範內容不視為實際引用。"""
    return CODE_FENCE_PATTERN.sub(" ", text)


def find_ticket_id_hits(text: str) -> List[str]:
    """在文字中找出專案 ticket ID 候選（已排除放行例外與 code fence），去重保序。

    全禁原則下本函式即為完整偵測器，不再區分依賴型 / 歷史錨點型——
    是否觸發告警改由呼叫端以「編輯前後淨增量」判斷（見 main）。
    """
    if not text:
        return []
    cleaned = _strip_exempt_spans(_strip_code_fences(text))

    hits: List[str] = []
    seen = set()
    for pattern in (VERSIONED_TICKET_PATTERN, BARE_TICKET_PATTERN):
        for match in pattern.finditer(cleaned):
            value = match.group(0)
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


def build_warning_message(file_path: str, new_hits: List[str]) -> str:
    """組合 WARNING 訊息：新增命中清單 + 規則出處 + 處置建議。"""
    hits_display = "、".join(new_hits)
    return (
        f"[WARNING][reference-stability-rule8] 偵測到 .claude/ 框架檔案新增內容"
        f"含專案層級 ticket ID 引用：{file_path}\n"
        f"新增命中：{hits_display}\n"
        f"依據：.claude/references/reference-stability-rules.md 規則 8"
        f"「引用性質判準：全禁原則與五類分類」（框架文件禁止引用專案層級識別符，"
        f"跨專案 sync 後會變成死連結；既有於檔案內的存量引用不重複觸發本警告）。\n"
        f"處置：依五類分類移除該 ticket ID——論證依據型改自足 WHY 或先寫方法論"
        f"再引用；時點標注型改標日期；案例敘事主詞型改描述性標籤。若此路徑本應屬"
        f"第 4 類（被說明對象型）或第 5 類（測試資料型），請確認路徑落在白名單"
        f"（.claude/references/ticket-id-conventions.md）或測試路徑（/tests/、"
        f"test_*.py、*_test.py）。\n"
        f"本提示僅 WARNING，不阻擋本次操作。"
    )


def main() -> int:
    """主入口：讀取 stdin → 篩選掃描範圍與豁免 → 重建編輯前後內容 → 淨增量比對 → WARNING（不阻擋）。"""
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
                f"僅命中既有（凍結）ticket ID，不觸發告警："
                f"file={file_path} tool={tool_name} hits={sorted(set(existing_hits))}"
            )
        else:
            logger.debug(f"未偵測到 ticket ID 命中：{file_path}")
        return EXIT_ALLOW

    message = build_warning_message(file_path, new_hits)
    sys.stderr.write(message + "\n")
    logger.warning(
        f"偵測到新增專案 ticket ID 引用：file={file_path} tool={tool_name} new_hits={new_hits}"
    )
    return EXIT_ALLOW


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--self-test":
        import tempfile

        failures: List[str] = []

        # 正例：應偵測到 ticket ID 候選（find_ticket_id_hits 為全量偵測，
        # 不再區分依賴型 / 歷史錨點型）
        positive_cases = [
            "版本化格式：本 hook 修復 9.9.9-W9-999 遺漏的問題。",
            "裸格式：詳見 W9-999 的分析結論。",
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
                "既有內容第一行\n舊引用（0.2.1-W3-100 教訓）\n既有內容第三行\n",
                encoding="utf-8",
            )

            # 案例 A：Edit 僅重排既有內容，未新增任何 ticket ID → 不應告警
            pre_a, post_a = reconstruct_pre_post_text(
                "Edit",
                {
                    "file_path": str(existing_file),
                    "old_string": "既有內容第三行",
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
                    "content": "全新檔案，直接 # from 0.2.1-W3-308 無跳轉詞",
                },
                str(new_file),
            )
            new_hits_c = diff_new_hits(pre_c, post_c)
            if "0.2.1-W3-308" not in new_hits_c:
                failures.append(f"[FAIL] 新檔案含 ticket ID 應被偵測，實際 {new_hits_c}")
            else:
                print("[PASS] 新檔案（無存量基準）正確偵測新增 ticket ID")

        if failures:
            print("\n".join(failures))
            sys.exit(1)
        print("[self-test] 全部通過")
        sys.exit(0)

    sys.exit(run_hook_safely(main, "reference-stability-rule8-guard"))
