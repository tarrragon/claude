#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
AUQ Option Pattern Detector Hook - PM 回覆含選項 pattern 時提醒使用 AskUserQuestion

補齊 PC-064 多層防護的最後一層（Hook 層）。既有 askuserquestion-reminder-hook 只處
理 Task 工具派發含多 Ticket ID 的場景；本 Hook 偵測 PM 對話中途列選項（A./B./C.、
1./2./3.）或二元問句結尾等待用戶回應的場景。

Hook 類型: UserPromptSubmit
行為: Warning-only，只注入 additionalContext 提醒，不阻擋（exit 0）

規格: .claude/plans/hooks/auq-option-pattern-detector-spec.md
測試設計: .claude/plans/hooks/auq-option-pattern-detector-test-design.md
"""

import json
import re
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))

try:
    from hook_utils import setup_hook_logging, is_subagent_environment, read_json_from_stdin, run_hook_safely, get_effort_level
    from lib.hook_messages import AUQOptionPatternMessages
    from lib.transcript_tail_reader import read_last_assistant_text as _shared_read_last_assistant_text
except ImportError as e:
    print(f"[Hook Import Error] {Path(__file__).name}: {e}", file=sys.stderr)
    sys.exit(0)


# --- 正則與關鍵字 ---

# 行首選項標記（allow 前置空白 ≤ 2）
# A./B./C./D./E. 或 1./2./3./4./5.
OPTION_MARKER_RE = re.compile(
    r"^[ ]{0,2}(?:[A-Ea-e]\.|[1-5]\.)[ \t]+\S",
    re.MULTILINE,
)

# Fenced code block（```…```）
FENCED_CODE_RE = re.compile(r"```.*?```", re.DOTALL)
# Inline code (`…`)
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")

# 半形/全形問號常數（規格 3.2/3.3 共用）
QUESTION_MARKS = ("?", "？")

# 選項語境問句關鍵字（3.2 條件 B）
# 注意：「要不要」「需要做」與 BINARY_QUESTION_KEYWORDS 重疊為刻意保留——
# OPTION 路徑需搭配選項標記（A./B./C.）才命中，BINARY 路徑需搭配問號才命中，
# 兩條路徑語意分離且豁免邏輯獨立，重疊不會產生雙重判定。
OPTION_QUESTION_KEYWORDS = (
    "要選哪個",
    "哪個比較好",
    "請選擇",
    "要不要",
    "需要做",
    "應該",
    "先做",
    "還是",
)

# 二元問句關鍵字（3.3）
# 不含「嗎？」「嗎?」：問號條件已由 is_binary_question 透過 QUESTION_MARKS 獨立檢查，
# 在關鍵字清單再列「嗎？」會造成雙重判定（同一個問號被檢查兩次）。
BINARY_QUESTION_KEYWORDS = (
    "要繼續",
    "確認執行",
    "要不要",
    "是否繼續",
    "是否執行",
    "需要做",
    "要進",
    "要 commit",
    "嗎",
)

# 豁免關鍵字
E1_CITATION_KEYWORDS = (
    "引用",
    "參考",
    "根據",
    "如下列所述",
    "詳見該文件",
    "askuserquestion-rules",
    "18 個場景",
    "規則表",
)

E2_HISTORY_KEYWORDS = (
    "先前",
    "已完成",
    "過去",
    "當初",
    "之前 commit",
    "歷史",
    "最後選了",
)
E2_HISTORY_TICKET_RE = re.compile(r"W\d+-\d+")

# §3.4-bis Markdown 表格選項偵測（W17-174.2 Solution §1）
# 資料列：行首 | 後至少一個非 | 字元，再接 |
TABLE_DATA_ROW_RE = re.compile(r"^\|[^|\n]+\|", re.MULTILINE)
# 分隔列：只含 -、:、~、空白
TABLE_SEPARATOR_RE = re.compile(r"^\|[\s:~\-|]+\|\s*$", re.MULTILINE)

# 表格標題列含選項關鍵字才視為「選項表」（E6 反向判定）
TABLE_OPTION_HEADER_KEYWORDS = (
    "選項",
    "方案",
    "策略",
    "Option",
    "option",
    "推薦",
    "Recommended",
    "建議",
    "候選",
)


def strip_code_blocks(text: str) -> str:
    """移除 fenced code block 與 inline code。"""
    text = FENCED_CODE_RE.sub("", text)
    text = INLINE_CODE_RE.sub("", text)
    return text


def has_option_markers(text: str) -> bool:
    """判斷是否連續 3+ 個行首選項標記。"""
    return len(OPTION_MARKER_RE.findall(text)) >= 3


def has_question_ending(text: str, window: int = 400) -> bool:
    """判斷結尾 window 字內是否含選項問句關鍵字或問號。

    單次 tail 掃描合併三條件：
    1. tail（window 字）含 OPTION_QUESTION_KEYWORDS 任一
    2. tail 最後 50 字含半形或全形問號
    3. tail 最後一行以半形或全形問號結尾
    """
    tail = text[-window:] if len(text) > window else text
    if any(kw in tail for kw in OPTION_QUESTION_KEYWORDS):
        return True
    if any(mark in tail[-50:] for mark in QUESTION_MARKS):
        return True
    last_line = tail.rstrip().split("\n")[-1].rstrip()
    return last_line.endswith(QUESTION_MARKS)


def is_binary_question(text: str) -> bool:
    """判斷結尾 200 字是否為二元問句（含關鍵字 + 半形或全形問號）。"""
    tail = text[-200:] if len(text) > 200 else text
    has_kw = any(kw in tail for kw in BINARY_QUESTION_KEYWORDS)
    has_q = any(mark in tail for mark in QUESTION_MARKS)
    return has_kw and has_q


def is_exempt_citation(text: str) -> bool:
    """E1：引用既有文件豁免。"""
    return any(kw in text for kw in E1_CITATION_KEYWORDS)


def is_exempt_history(text: str) -> bool:
    """E2：歷史回顧豁免（過去時態 + W 編號）。"""
    has_kw = any(kw in text for kw in E2_HISTORY_KEYWORDS)
    has_ticket = bool(E2_HISTORY_TICKET_RE.search(text))
    return has_kw and has_ticket


def has_table_options(text: str) -> bool:
    """§3.4-bis：判斷是否為 Markdown 表格選項列（W17-174.2 Solution §1）。

    必須同時滿足：
    (A) 至少 3 個資料列（資料列總數 - 分隔列數 - 標題列數 >= 3）
    (B) 結尾出現選項問句語境（複用 has_question_ending）

    其中 header_count = min(1, separator_count)（有分隔列才扣 1 行作為標題）。
    """
    total_pipes = len(TABLE_DATA_ROW_RE.findall(text))
    separator = len(TABLE_SEPARATOR_RE.findall(text))
    header = 1 if separator >= 1 else 0
    data_rows = total_pipes - separator - header
    return data_rows >= 3 and has_question_ending(text)


def _extract_first_table_header(text: str) -> str:
    """取出文字中第一個 Markdown 表格的標題列（行首 |...| 第一行）。"""
    match = TABLE_DATA_ROW_RE.search(text)
    if not match:
        return ""
    line_start = text.rfind("\n", 0, match.start()) + 1
    line_end = text.find("\n", match.start())
    if line_end == -1:
        line_end = len(text)
    return text[line_start:line_end]


def is_exempt_pure_data_table(text: str) -> bool:
    """E6：純資料表格豁免（W17-174.2 Solution §2）。

    若表格標題列不含任何選項關鍵字（選項/方案/策略/Option/推薦 等），
    視為純資料表（測試結果、效能指標等），不應觸發提醒。
    """
    header_line = _extract_first_table_header(text)
    if not header_line:
        return False
    return not any(kw in header_line for kw in TABLE_OPTION_HEADER_KEYWORDS)


def is_exempt_rule_writing(text: str) -> bool:
    """E4：規則文件寫作場景豁免（含 .claude/*.md 路徑佔比 > 10%）。"""
    # 找所有 .claude/...md 路徑字串
    paths = re.findall(r"\.claude/[\w\-/]+\.md", text)
    if not paths:
        return False
    path_chars = sum(len(p) for p in paths)
    ratio = path_chars / max(len(text), 1)
    return ratio > 0.10 or len(paths) >= 3


def detect_and_build_output(
    input_data: dict,
    transcript_text: Optional[str],
) -> dict:
    """核心偵測邏輯 - 純函式便於測試。

    Args:
        input_data: Hook stdin 解析後的 dict
        transcript_text: 最後一則 assistant 訊息文字（None 表示讀取失敗）

    Returns:
        hookSpecificOutput JSON dict（含或不含 additionalContext）
    """
    base_output = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
        }
    }

    # E5: subagent 環境直接跳過
    if is_subagent_environment(input_data):
        return base_output

    if not transcript_text:
        return base_output

    # Code block 預處理
    cleaned = strip_code_blocks(transcript_text)

    # 偵測三路徑（W17-174.2 Solution §1：新增 §3.4-bis 表格路徑）
    hit_option_path = has_option_markers(cleaned) and has_question_ending(cleaned)
    hit_binary_path = is_binary_question(cleaned)
    hit_table_path = has_table_options(cleaned)

    if not (hit_option_path or hit_binary_path or hit_table_path):
        return base_output

    # 豁免順序：E4（規則寫作）> E1（引用）> E2（歷史）> E6（純資料表，僅表格路徑適用）
    if is_exempt_rule_writing(cleaned):
        return base_output
    if is_exempt_citation(cleaned):
        return base_output
    if is_exempt_history(cleaned):
        return base_output
    # E6 僅在「只有」表格路徑命中時適用；若同時命中 option/binary 路徑，仍走原有偵測
    if hit_table_path and not (hit_option_path or hit_binary_path) and is_exempt_pure_data_table(cleaned):
        return base_output

    # 命中且未豁免 - 注入提醒
    base_output["hookSpecificOutput"]["additionalContext"] = AUQOptionPatternMessages.REMINDER
    return base_output


def read_last_assistant_text(transcript_path: Optional[str], logger) -> Optional[str]:
    """從 JSONL transcript 讀取最後一則 assistant 訊息文字。

    委派至 lib.transcript_tail_reader 共用工具，使用 offset 快取避免每次全檔
    掃描（W11-004.11）。保留本函式名稱以維持既有 import 相容性。
    """
    return _shared_read_last_assistant_text(transcript_path, logger)


def main() -> int:
    """Hook 主入口。"""
    logger = setup_hook_logging("auq-option-pattern-detector")
    logger.info("AUQ Option Pattern Detector Hook 啟動")

    input_data = read_json_from_stdin(logger)
    if input_data is None:
        # 空輸入或解析失敗 - 放行並輸出基礎 JSON
        print(json.dumps(
            {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit"}},
            ensure_ascii=False,
        ))
        return 0

    # Effort 感知（v2.1.133+，W14-037）：
    # PC-064 防護不可削弱 — AUQ 選項 pattern 偵測為事實判斷，
    # 必擋邏輯與 effort 無關。此處僅記錄 effort 供後續觀測。
    effort = get_effort_level(input_data)
    logger.info("effort=%s，AUQ pattern 偵測無條件執行（PC-064）", effort)

    transcript_path = input_data.get("transcript_path")
    transcript_text = read_last_assistant_text(transcript_path, logger)

    output = detect_and_build_output(input_data, transcript_text)

    if "additionalContext" in output["hookSpecificOutput"]:
        logger.info("偵測到 AUQ 選項 pattern，注入提醒")
    else:
        logger.debug("未命中或已豁免，放行")

    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "auq-option-pattern-detector"))
