#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""reference-stability-rule8-guard — PreToolUse Hook

偵測 `.claude/` 框架檔案寫入內容中殘留的專案層級識別符（ticket ID），
落實 reference-stability 規則 8（框架文件禁止引用專案層級識別符）
的 hook 強制層。目前僅 WARNING（不硬擋），供觀察誤報率後續評估是否升級。

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
行為: 命中且非例外 → WARNING（stderr + 日誌），exit 0（允許，不阻擋）
      未命中 / 非掃描範圍 / 輸入異常 → 靜默放行

對應規則：.claude/references/reference-stability-rules.md 規則 8
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


def find_ticket_id_hits(text: str) -> List[str]:
    """在文字中找出專案 ticket ID 命中（已排除放行例外），去重保序。"""
    if not text:
        return []
    cleaned = _strip_exempt_spans(text)

    hits: List[str] = []
    seen = set()
    for pattern in (VERSIONED_TICKET_PATTERN, BARE_TICKET_PATTERN):
        for match in pattern.finditer(cleaned):
            value = match.group(0)
            if value not in seen:
                seen.add(value)
                hits.append(value)
    return hits


def build_warning_message(file_path: str, hits: List[str]) -> str:
    """組合 WARNING 訊息：命中清單 + 規則出處 + 抽象化建議。"""
    hits_display = "、".join(hits)
    return (
        f"[WARNING][reference-stability-rule8] 偵測到 .claude/ 框架檔案寫入內容"
        f"疑似含專案層級識別符：{file_path}\n"
        f"命中：{hits_display}\n"
        f"依據：.claude/references/reference-stability-rules.md 規則 8"
        f"（框架文件禁止引用專案層級識別符，跨專案 sync 後會變成死連結）。\n"
        f"建議：改用抽象原則描述（如「防範 Hook error 干擾代理人判斷」），"
        f"或改引用框架內部識別符（PC-xxx / IMP-xxx / ARCH-xxx / 檔案路徑）。\n"
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
    for text in texts:
        for hit in find_ticket_id_hits(text):
            if hit not in seen:
                seen.add(hit)
                all_hits.append(hit)

    if not all_hits:
        logger.debug(f"未偵測到專案 ticket ID：{file_path}")
        return EXIT_ALLOW

    message = build_warning_message(file_path, all_hits)
    sys.stderr.write(message + "\n")
    logger.warning(
        f"偵測到專案 ticket ID：file={file_path} tool={tool_name} hits={all_hits}"
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

        if failures:
            print("\n".join(failures))
            sys.exit(1)
        print("[self-test] 全部通過")
        sys.exit(0)

    sys.exit(run_hook_safely(main, "reference-stability-rule8-guard"))
