#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
AskUserQuestion Charset Guard Hook - PreToolUse Hook

功能：掃描 AskUserQuestion 工具呼叫的 JSON payload，偵測簡體字與非必要 emoji。
命中時阻擋執行（exit 2）並在 stderr 列出違規位置與字元，讓 PM 修正後重新產生。

Hook 類型：PreToolUse
匹配工具：AskUserQuestion
退出碼：0 = 放行，2 = 阻擋（stderr 回饋給 Claude）

背景：
- W12-002 ANA 調查確認污染源（Hook stdout emoji + language-constraints 範例 emoji）
- 根本解法需清洗所有污染源，但周期長
- 本 Hook 是立即止血方案：偵測並攔截污染的 AUQ payload 送達用戶前

遵循：
- language-constraints.md 規則 1（繁體）+ 規則 3（禁 emoji）
- PC-072 AUQ payload 字元集污染檢查清單
"""

import json
import sys

from hook_utils import setup_hook_logging, run_hook_safely, read_json_from_stdin
from hook_utils.hook_io import emit_hook_output

HOOK_NAME = "askuserquestion-charset-guard"

# 常見 zh-CN 字元清單（繁體不會出現，命中即確認污染）
# 來源：PC-072 檢查清單 + 姊妹簡體字
# 每字須通過繁簡不共用驗證（PC-074）+ 非繁中異體字（PC-084）
# W14-007 移除：U+4F53（繁中異體字，PC-084 §候選字驗證範例禁入）
SIMPLIFIED_CHARS = frozenset(
    "独违决关为与实发这应该简认识运动说话听读写买卖进见闻"
    "间问时来国让组长会义书产众们电门经济纪价东华"
    "补没务觉个灵响"
    "隶遗"  # W13-003: 2026-04-17 session 再現補強（隸/遺 位本應繁體）
)

# 日文新字體專屬漢字清單（繁中不收此字形，命中即確認污染）
# 來源：PC-084 §候選字驗證範例「日專 → 可入」列；W14-007 首版
# 禁入字（PC-084 明文記錄，僅註解保留以防後人誤加）：
#   - 鑑 U+9451（繁日共用；繁中「鑑別 / 借鑑 / 鑑於」正統字）
#   - 体 U+4F53、誉 U+8A89、豊 U+8C4A、拝 U+62DD（繁中異體字，保守不入）
# 加字流程：先查教育部異體字字典 / 漢典確認繁中不收此字形，再入清單
JAPANESE_ONLY = frozenset(
    "\u8aad"  # 読 U+8AAD  繁中用「讀」U+8B80
    "\u8a33"  # 訳 U+8A33  繁中用「譯」U+8B6F
    "\u99c5"  # 駅 U+99C5  繁中用「驛」U+9A5B
    "\u4e21"  # 両 U+4E21  繁中用「兩」U+5169（W14-013 實證污染字）
    "\u767a"  # 発 U+767A  繁中用「發」U+767C
    "\u56f3"  # 図 U+56F3  繁中用「圖」U+5716
    "\u5e83"  # 広 U+5E83  繁中用「廣」U+5EE3
    "\u5b9f"  # 実 U+5B9F  繁中用「實」U+5BE6
    "\u6c17"  # 気 U+6C17  繁中用「氣」U+6C23
    "\u697d"  # 楽 U+697D  繁中用「樂」U+6A02
    "\u89b3"  # 観 U+89B3  繁中用「觀」U+89C0
    "\u691c"  # 検 U+691C  繁中用「檢」U+6AA2
    "\u6a29"  # 権 U+6A29  繁中用「權」U+6B0A
    "\u58f2"  # 売 U+58F2  繁中用「賣」U+8CE3
    "\u95a2"  # 関 U+95A2  繁中用「關」U+95DC
    "\u9244"  # 鉄 U+9244  繁中用「鐵」U+9435
    "\u8ee2"  # 転 U+8EE2  繁中用「轉」U+8F49
)

# Emoji unicode 範圍（命中即違規）
EMOJI_RANGES = (
    (0x2600, 0x27BF),    # Miscellaneous Symbols (⚡ ✅ ❌ ⚠️ ★ ☆)
    (0x1F300, 0x1F5FF),  # Miscellaneous Symbols and Pictographs (🎯 🔴 🟢 📝)
    (0x1F600, 0x1F64F),  # Emoticons
    (0x1F680, 0x1F6FF),  # Transport and Map
    (0x1F900, 0x1F9FF),  # Supplemental Symbols and Pictographs
    (0x1FA00, 0x1FAFF),  # Symbols and Pictographs Extended-A
)

BLOCK_MESSAGE_TEMPLATE = """錯誤：AskUserQuestion payload 含字元集污染（PC-072）

違規清單（{count} 處）：
{violations}

為什麼阻止：
  AUQ payload 會渲染給用戶，含簡體字、日文漢字或 emoji 違反 language-constraints 規則 1/3。
  常見污染源：Hook stdout emoji 累積污染 PM token pool（見 W12-002 調查結論）。
  新增日文漢字類別（W14-007 / PC-084）：PM token pool 偶爾混入日文新字體近鄰字（如「読」U+8AAD 近鄰繁中「讀」U+8B80）。

修復方式：
  1. 逐項替換簡體字為繁體（例：独→獨、违→違、决→決、为→為、与→與）
  2. 逐項替換日文漢字為繁體等價字（例：読→讀、訳→譯、駅→驛、両→兩、発→發、図→圖）
  3. 移除 emoji 或改用 ASCII 標記 [OK]/[WARN]/[FAIL]
  4. 重新提交 AskUserQuestion 工具呼叫

詳見: .claude/error-patterns/process-compliance/PC-072-askuserquestion-payload-charset-contamination.md
"""


def find_violations(text: str, field_path: str) -> list:
    """
    掃描字串偵測簡體字與 emoji。

    Args:
        text: 欲掃描的字串
        field_path: 欄位路徑（例：questions[0].label）用於錯誤訊息

    Returns:
        [(field_path, char, code_point, category), ...]
    """
    violations = []
    for idx, char in enumerate(text):
        code = ord(char)

        # 分支 A：簡體字偵測
        if char in SIMPLIFIED_CHARS:
            violations.append((field_path, char, code, "簡體字"))
            continue

        # 分支 B：Emoji 偵測
        matched_emoji = False
        for range_start, range_end in EMOJI_RANGES:
            if range_start <= code <= range_end:
                violations.append((field_path, char, code, "emoji"))
                matched_emoji = True
                break
        if matched_emoji:
            continue

        # 分支 C：日文漢字偵測（W14-007 / PC-084）
        if char in JAPANESE_ONLY:
            violations.append((field_path, char, code, "日文漢字"))
            continue

    return violations


def scan_payload(questions: list) -> list:
    """
    掃描 AskUserQuestion payload 的 questions 陣列。

    Returns:
        所有違規清單（空 list = 通過）
    """
    all_violations = []

    for q_idx, question in enumerate(questions):
        if not isinstance(question, dict):
            continue

        # 檢查 question 本身
        q_text = question.get("question", "")
        if q_text:
            all_violations.extend(
                find_violations(q_text, f"questions[{q_idx}].question")
            )

        # 檢查 header
        header = question.get("header", "")
        if header:
            all_violations.extend(
                find_violations(header, f"questions[{q_idx}].header")
            )

        # 檢查每個 option
        options = question.get("options", [])
        if isinstance(options, list):
            for o_idx, option in enumerate(options):
                if not isinstance(option, dict):
                    continue

                label = option.get("label", "")
                if label:
                    all_violations.extend(
                        find_violations(
                            label,
                            f"questions[{q_idx}].options[{o_idx}].label",
                        )
                    )

                description = option.get("description", "")
                if description:
                    all_violations.extend(
                        find_violations(
                            description,
                            f"questions[{q_idx}].options[{o_idx}].description",
                        )
                    )

    return all_violations


def format_violations(violations: list) -> str:
    """將違規清單格式化為 stderr 訊息。"""
    lines = []
    for field_path, char, code, category in violations:
        lines.append(f"  - {field_path}: '{char}' (U+{code:04X}) [{category}]")
    return "\n".join(lines)


def main() -> int:
    """Hook 主邏輯。"""
    logger = setup_hook_logging(HOOK_NAME)

    try:
        input_data = read_json_from_stdin(logger)
    except (json.JSONDecodeError, EOFError):
        logger.warning("無法解析 stdin JSON，放行")
        return 0

    if not input_data:
        return 0

    tool_name = input_data.get("tool_name", "")
    if tool_name != "AskUserQuestion":
        return 0

    # tool_input 可能以 JSON 字串或 dict 傳入
    raw_input = input_data.get("tool_input") or "{}"
    if isinstance(raw_input, str):
        try:
            tool_input = json.loads(raw_input)
        except json.JSONDecodeError:
            logger.warning("tool_input JSON 解析失敗，放行")
            return 0
    else:
        tool_input = raw_input

    questions = tool_input.get("questions", [])
    if not isinstance(questions, list) or not questions:
        return 0

    violations = scan_payload(questions)

    if not violations:
        logger.info("通過：AUQ payload 無簡體字與 emoji")
        return 0

    # 命中違規 → 阻擋（W13-006.2 方案 C：雙通道分離）
    # - stdout JSON: permissionDecisionReason 承載完整修復指引（給 Claude）
    # - stderr: 極簡摘要（給用戶 terminal，保留規則 4 可觀測性）
    # - exit 0: 讓 JSON 生效（exit 2 會忽略 JSON）
    full_message = BLOCK_MESSAGE_TEMPLATE.format(
        count=len(violations), violations=format_violations(violations)
    )

    # 極簡 stderr 摘要：錯誤標題 + 違規清單 + PC-072 連結（不含修復指引 1-4 步）
    stderr_summary = (
        f"錯誤：AUQ payload 含 {len(violations)} 處字元集污染（PC-072）\n"
        f"{format_violations(violations)}\n"
        f"（完整修復指引已傳遞給 AI；詳見 PC-072）\n"
    )
    sys.stderr.write(stderr_summary)

    emit_hook_output(
        "PreToolUse",
        permission_decision="deny",
        permission_decision_reason=full_message,
    )

    logger.warning("阻擋：AUQ payload 含 %d 處污染", len(violations))
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
