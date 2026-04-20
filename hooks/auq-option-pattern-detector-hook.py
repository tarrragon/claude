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
    from hook_utils import setup_hook_logging, is_subagent_environment, read_json_from_stdin, run_hook_safely
    from lib.hook_messages import AUQOptionPatternMessages
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

# 選項語境問句關鍵字（3.2 條件 B）
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
BINARY_QUESTION_KEYWORDS = (
    "要繼續",
    "確認執行",
    "要不要",
    "是否繼續",
    "是否執行",
    "需要做",
    "要進",
    "要 commit",
    "嗎？",
    "嗎?",
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


def strip_code_blocks(text: str) -> str:
    """移除 fenced code block 與 inline code。"""
    text = FENCED_CODE_RE.sub("", text)
    text = INLINE_CODE_RE.sub("", text)
    return text


def has_option_markers(text: str) -> bool:
    """判斷是否連續 3+ 個行首選項標記。"""
    return len(OPTION_MARKER_RE.findall(text)) >= 3


def has_question_ending(text: str, window: int = 400) -> bool:
    """判斷結尾 window 字內是否含選項問句關鍵字或問號。"""
    tail = text[-window:] if len(text) > window else text
    for kw in OPTION_QUESTION_KEYWORDS:
        if kw in tail:
            return True
    # 最後 50 字含 ? / ?
    last_50 = text[-50:]
    if "?" in last_50 or "?" in last_50:
        return True
    # 最後一行以問號結尾
    last_line = text.rstrip().split("\n")[-1].rstrip()
    if last_line.endswith("?") or last_line.endswith("?"):
        return True
    return False


def is_binary_question(text: str) -> bool:
    """判斷結尾 200 字是否為二元問句（含關鍵字 + 半形或全形問號）。"""
    tail = text[-200:] if len(text) > 200 else text
    has_kw = any(kw in tail for kw in BINARY_QUESTION_KEYWORDS)
    has_q = ("?" in tail) or ("\uff1f" in tail)
    return has_kw and has_q


def is_exempt_citation(text: str) -> bool:
    """E1：引用既有文件豁免。"""
    return any(kw in text for kw in E1_CITATION_KEYWORDS)


def is_exempt_history(text: str) -> bool:
    """E2：歷史回顧豁免（過去時態 + W 編號）。"""
    has_kw = any(kw in text for kw in E2_HISTORY_KEYWORDS)
    has_ticket = bool(E2_HISTORY_TICKET_RE.search(text))
    return has_kw and has_ticket


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

    # 偵測雙路徑
    hit_option_path = has_option_markers(cleaned) and has_question_ending(cleaned)
    hit_binary_path = is_binary_question(cleaned)

    if not (hit_option_path or hit_binary_path):
        return base_output

    # 豁免順序：E4（規則寫作）> E1（引用）> E2（歷史）
    if is_exempt_rule_writing(cleaned):
        return base_output
    if is_exempt_citation(cleaned):
        return base_output
    if is_exempt_history(cleaned):
        return base_output

    # 命中且未豁免 - 注入提醒
    base_output["hookSpecificOutput"]["additionalContext"] = AUQOptionPatternMessages.REMINDER
    return base_output


def read_last_assistant_text(transcript_path: Optional[str], logger) -> Optional[str]:
    """從 JSONL transcript 讀取最後一則 assistant 訊息文字。

    支援兩種 content 格式：
    - stringified: {"message": {"role": "assistant", "content": "..."}}
    - blocks: {"message": {"role": "assistant", "content": [{"type":"text","text":"..."}]}}

    失敗時回傳 None（不 raise），呼叫端會以放行處理。
    """
    if not transcript_path:
        logger.info("transcript_path 為空，跳過")
        return None

    path = Path(transcript_path)
    if not path.exists():
        logger.info("transcript 檔案不存在: %s", transcript_path)
        return None

    try:
        last_assistant_text: Optional[str] = None
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    # 跳過單行損壞，繼續讀
                    continue
                msg = obj.get("message") or {}
                if not isinstance(msg, dict):
                    continue
                role = msg.get("role") or obj.get("type")
                if role != "assistant":
                    continue
                content = msg.get("content")
                if isinstance(content, str):
                    last_assistant_text = content
                elif isinstance(content, list):
                    parts = []
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            parts.append(block.get("text", ""))
                    if parts:
                        last_assistant_text = "\n".join(parts)
        return last_assistant_text
    except OSError as e:
        logger.info("transcript 讀取失敗: %s", e)
        return None


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
