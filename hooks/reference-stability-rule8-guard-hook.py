#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""reference-stability-rule8-guard — PreToolUse Hook

偵測 `.claude/` 框架檔案寫入內容中殘留的專案層級識別符（ticket ID），
落實 reference-stability 規則 8（框架文件禁止引用專案層級識別符）
的 hook 強制層。依「引用性質判準」（同檔規則 8 §引用性質判準）區分
依賴型（dependency_ref，同行含跳轉引導詞）與歷史錨點型（不報或僅
debug 記錄），僅對依賴型觸發 WARNING，降低對合法歷史標注的誤報。

觸發時機: PreToolUse Edit / Write / MultiEdit
掃描範圍: 目標檔案路徑位於 `.claude/` 下，且不在 `.claude/handoff/archive/`
          （該目錄為歷史紀錄，規則 8 明文豁免）
偵測樣式:
  - 版本化 ticket ID：`\\d+\\.\\d+\\.\\d+-W\\d+-\\d+`（如 9.9.9-W9-999）
  - 裸格式 ticket ID：`W\\d+-\\d+`（如 W9-999）
放行例外（不觸發 WARNING）:
  - 框架 error-pattern ID（PC-xxx / IMP-xxx / ARCH-xxx）與其檔名
  - 日期字串（YYYY-MM-DD）
  - Claude Code 版本號（CC 開頭 + 版本數字）
  - code fence（```...```）內的內容（格式示範，非實際引用）
引用性質判準（依 reference-stability-rules.md 移除測試操作化）:
  - 依賴型（dependency_ref）：ticket ID 前 15 字元鄰近視窗內含跳轉引導詞
    （詳見/參見/參閱/參考/依據/根據/來源是/相關文件）→ 觸發 WARNING
  - 歷史錨點型（historical_anchor）：其餘情形（含括號時點標注、
    frontmatter 欄位值、表格列舉、遠距離引導詞等裸引用，如
    「（W9-999 教訓）」「source_ticket: 9.9.9-W9-999」）→ 不觸發 WARNING，
    僅記錄 debug 日誌供觀察
  實測（0.2.1-W3-057，全框架 9771 處候選）：依賴型 136 處（1.39%），
  對齊 0.2.1-W3-056 基線（10638 處候選中 133 處，1.25%）；抽樣檢視
  皆為真依賴（如「根據 W1-017 重構」「設計依據（1.0.0-W1-056...）」）
行為: 依賴型命中 → WARNING（stderr + 日誌），exit 0（允許，不阻擋，
      待觀察一段時間後再評估是否升級為阻擋）
      歷史錨點型 / 未命中 / 非掃描範圍 / 輸入異常 → 靜默放行（歷史錨點型
      額外寫入 debug 日誌）

對應規則：.claude/references/reference-stability-rules.md 規則 8
及其「引用性質判準」章節（依賴型 vs 歷史錨點型）
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import List, Optional

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

# 專案 ticket ID 樣式
VERSIONED_TICKET_PATTERN = re.compile(r"\b\d+\.\d+\.\d+-W\d+-\d+\b")
BARE_TICKET_PATTERN = re.compile(r"\bW\d+-\d+\b")

# 放行例外樣式（框架內部識別符 / 外部平台版本 / 日期，規則 8 明文允許）
FRAMEWORK_ERROR_PATTERN_ID = re.compile(r"\b(?:PC|IMP|ARCH)-\d+\b")
DATE_PATTERN = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
CC_VERSION_PATTERN = re.compile(r"\bCC\s+\d+\.\d+(?:\.\d+)?\b")

# Code fence（```...```，含語言標記行）：格式示範內容不視為實際引用
CODE_FENCE_PATTERN = re.compile(r"```.*?```", re.DOTALL)

# 引用性質判準（reference-stability-rules.md 規則 8 §引用性質判準）
# 依賴型跳轉引導詞：同行與 ticket ID 並存 → 建立跳轉依賴
# 刻意不含裸「依」「見」單字（過度常見，如「依規」「意見」會誤增依賴型誤判）
JUMP_WORD_PATTERN = re.compile(r"詳見|參見|參閱|參考|依據|根據|來源是|相關文件")


def is_scanned_path(file_path: str) -> bool:
    """判斷檔案路徑是否落在規則 8 掃描範圍（.claude/ 下，排除 handoff/archive）。"""
    if not file_path:
        return False
    # 正規化：只取相對路徑中 .claude/ 起始的片段做比對，容忍絕對路徑前綴
    normalized = file_path.replace("\\", "/")
    idx = normalized.find(SCAN_PREFIX)
    if idx == -1:
        return False
    rel = normalized[idx:]
    if rel.startswith(EXEMPT_DIR_PREFIX):
        return False
    return True


def extract_written_texts(tool_name: str, tool_input: dict) -> List[str]:
    """依工具類型取出「新寫入內容」字串列表（不含未變動的舊內容）。"""
    if tool_name == "Write":
        content = tool_input.get("content")
        return [content] if isinstance(content, str) else []

    if tool_name == "Edit":
        new_string = tool_input.get("new_string")
        return [new_string] if isinstance(new_string, str) else []

    if tool_name == "MultiEdit":
        edits = tool_input.get("edits")
        if not isinstance(edits, list):
            return []
        texts = []
        for edit in edits:
            if isinstance(edit, dict):
                new_string = edit.get("new_string")
                if isinstance(new_string, str):
                    texts.append(new_string)
        return texts

    return []


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
    """在文字中找出專案 ticket ID 命中（已排除放行例外與 code fence），去重保序。"""
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


# 跳轉引導詞與 ticket ID 之間的最大容許字元距離（同行內）。
# Why：長段落中引導詞與 ticket ID 可能相距甚遠且語意無關（如「...的判斷依據。
# 需事後補 domain map（實證：W2-014 於實作前補建）」——「依據」是段落前段
# 泛用名詞，與段落末的 ticket ID 引用無關）。窄化為鄰近視窗才能捕捉「引導詞
# 直接導向該 ticket ID」的真實依賴語意，避免長段落遠距離詞彙誤觸發。
JUMP_WORD_PROXIMITY_WINDOW = 15


def classify_hit_nature(line: str, match_start: int) -> str:
    """對單一 ticket ID 命中分類：dependency_ref / historical_anchor。

    判準來源：.claude/references/reference-stability-rules.md 規則 8
    §引用性質判準（移除測試操作化）。

    - ticket ID 起始位置前 JUMP_WORD_PROXIMITY_WINDOW 字元內含跳轉引導詞
      （詳見/參見/參閱/參考/依據/根據/來源是/相關文件）→ dependency_ref
      （建立跳轉依賴，禁止）
    - 其餘（含括號時點標注、frontmatter 欄位值、表格列舉、遠距離引導詞等
      裸引用）→ historical_anchor（不建立跳轉依賴，允許）

    Why 預設落在 historical_anchor 而非保守回報依賴型：
    0.2.1-W3-056 對全框架 10638 處候選的實測顯示僅 133 處（1.3%）具
    dependency_ref 形態；若對「無鄰近引導詞裸引用」預設回報依賴型，實測
    命中率會暴衝至數千處，與既有基線嚴重不符——多數裸引用是 frontmatter
    `source_ticket` 欄、表格列舉範例等既有判準下合法的用法，非真正跳轉
    依賴。故僅在鄰近視窗內存在明確跳轉引導詞才判定為依賴型。
    """
    window_start = max(0, match_start - JUMP_WORD_PROXIMITY_WINDOW)
    window = line[window_start:match_start]
    if JUMP_WORD_PATTERN.search(window):
        return "dependency_ref"
    return "historical_anchor"


def find_dependency_ref_hits(text: str) -> List[str]:
    """在文字中找出屬「依賴型」的專案 ticket ID 命中（逐 hit 鄰近視窗分類），去重保序。

    歷史錨點型命中不計入回傳，僅供呼叫端額外記錄 debug 日誌。
    """
    if not text:
        return []
    cleaned = _strip_exempt_spans(_strip_code_fences(text))

    hits: List[str] = []
    seen = set()
    for line in cleaned.splitlines():
        for pattern in (VERSIONED_TICKET_PATTERN, BARE_TICKET_PATTERN):
            for match in pattern.finditer(line):
                value = match.group(0)
                if value in seen:
                    continue
                if classify_hit_nature(line, match.start()) != "dependency_ref":
                    continue
                seen.add(value)
                hits.append(value)
    return hits


def build_warning_message(file_path: str, hits: List[str]) -> str:
    """組合 WARNING 訊息：命中清單 + 規則出處 + 抽象化建議。"""
    hits_display = "、".join(hits)
    return (
        f"[WARNING][reference-stability-rule8] 偵測到 .claude/ 框架檔案寫入內容"
        f"疑似含專案層級依賴型引用（dependency_ref）：{file_path}\n"
        f"命中：{hits_display}\n"
        f"依據：.claude/references/reference-stability-rules.md 規則 8"
        f"（框架文件禁止引用專案層級識別符，跨專案 sync 後會變成死連結）。\n"
        f"建議：改用抽象原則描述（如「防範 Hook error 干擾代理人判斷」），"
        f"或改引用框架內部識別符（PC-xxx / IMP-xxx / ARCH-xxx / 檔案路徑）。\n"
        f"若此引用僅為時點標注（歷史錨點型，如「（W9-999 教訓）」），"
        f"可忽略本提示；若為跳轉依賴（詳見/參考等），請依上述建議修正。\n"
        f"本提示僅 WARNING，不阻擋本次操作。"
    )


def main() -> int:
    """主入口：讀取 stdin → 篩選掃描範圍 → 偵測 ticket ID → WARNING（不阻擋）。"""
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

    texts = extract_written_texts(tool_name, tool_input)
    if not texts:
        logger.debug(f"{tool_name} 無可掃描的新寫入內容：{file_path}")
        return EXIT_ALLOW

    all_hits: List[str] = []
    seen = set()
    all_anchor_hits: List[str] = []
    seen_anchor = set()
    for text in texts:
        for hit in find_dependency_ref_hits(text):
            if hit not in seen:
                seen.add(hit)
                all_hits.append(hit)
        # 全量命中（不分類）減去依賴型命中 = 歷史錨點型命中，供 debug 觀察
        for hit in find_ticket_id_hits(text):
            if hit not in seen and hit not in seen_anchor:
                seen_anchor.add(hit)
                all_anchor_hits.append(hit)

    if all_anchor_hits:
        logger.debug(
            f"偵測到歷史錨點型 ticket ID（不觸發 WARNING）："
            f"file={file_path} tool={tool_name} hits={all_anchor_hits}"
        )

    if not all_hits:
        logger.debug(f"未偵測到依賴型專案 ticket ID：{file_path}")
        return EXIT_ALLOW

    message = build_warning_message(file_path, all_hits)
    sys.stderr.write(message + "\n")
    logger.warning(
        f"偵測到依賴型專案 ticket ID：file={file_path} tool={tool_name} hits={all_hits}"
    )
    return EXIT_ALLOW


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--self-test":
        # 正例：應偵測到 ticket ID
        positive_cases = [
            "版本化格式：本 hook 修復 9.9.9-W9-999 遺漏的問題。",
            "裸格式：詳見 W9-999 的分析結論。",
        ]
        # 反例：不應誤報（框架 ID / 日期 / CC 版本）
        negative_cases = [
            "已知案例：PC-050、IMP-003、ARCH-002。",
            "此變更於 2026-07-08 完成。",
            "CC 2.1.97 新增 /agents 分頁能力。",
        ]

        failures = []
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

        # 引用性質判準測試：依賴型應觸發 WARNING，歷史錨點型不應
        dependency_cases = [
            "詳見 W15-005 WRAP 方案 F 的完整說明。",
            "參考 9.9.9-W9-999 的分析結論做決策。",
            "相關文件：W10-011（擴充註解規則）。",
        ]
        anchor_cases = [
            "此防護源於某次崩潰事件（W9-999 教訓）。",
            "Version: 1.5.1 — 規則 6「以價值優先」加入（W9-999）。",
            "本段落內容未經任何括號包裝，裸引用 W9-999。",
            "source_ticket: 0.2.1-W3-056",
            # 遠距離引導詞（超出鄰近視窗）不應觸發依賴型判定（W3-057 修正案例）
            "跳過本步驟後測試設計無清楚可依據。這段填充文字用來拉開距離讓引導詞"
            "遠離後方的識別符標注（實證：W9-999 於實作前補建）。",
        ]

        for case in dependency_cases:
            hits = find_dependency_ref_hits(case)
            if not hits:
                failures.append(f"[FAIL] 依賴型未被分類為 dependency_ref: {case!r}")
            else:
                print(f"[PASS] 依賴型正確分類 {hits}: {case!r}")

        for case in anchor_cases:
            hits = find_dependency_ref_hits(case)
            if hits:
                failures.append(f"[FAIL] 歷史錨點型誤判為 dependency_ref {hits}: {case!r}")
            else:
                print(f"[PASS] 歷史錨點型正確排除: {case!r}")

        # code fence 內容不應被視為實際引用
        fence_case = "說明如下：\n```\n詳見 W9-999 的分析結論\n```\n本行本身無引用。"
        fence_hits = find_dependency_ref_hits(fence_case)
        if fence_hits:
            failures.append(f"[FAIL] code fence 內容誤判為引用 {fence_hits}: {fence_case!r}")
        else:
            print("[PASS] code fence 內容已正確排除")

        if failures:
            print("\n".join(failures))
            sys.exit(1)
        print("[self-test] 全部通過")
        sys.exit(0)

    sys.exit(run_hook_safely(main, "reference-stability-rule8-guard"))
