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

W17-068 增補（PC-085 字形混淆防護）：
- 新增 PC-085 相鄰 codepoint 對照表（CONFUSABLE_PAIRS），記錄繁/簡/日新字體
  在同義對應字 codepoint 高度相鄰的清單
- 啟動時 self-check：驗證 SIMPLIFIED_CHARS / JAPANESE_ONLY 與對照表一致性，
  防止清單設計者寫 \\uXXXX 時誤打鄰近 codepoint（PC-085 §防護措施 Lint 輔助）
- self-check 失敗時 logger.error + stderr 警告（規則 4：失敗必須可見）

遵循：
- language-constraints.md 規則 1（繁體）+ 規則 3（禁 emoji）
- PC-072 AUQ payload 字元集污染檢查清單
- PC-085 CJK codepoint 相鄰字形混淆防護
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

# ============================================================================
# PC-085：CJK 相鄰 codepoint 字形混淆防護（W17-068）
# ============================================================================
# 對照表記錄繁體 / 簡體 / 日文新字體三胞胎中 codepoint 高度相鄰的清單。
# 用途：啟動 self-check 驗證 SIMPLIFIED_CHARS / JAPANESE_ONLY 設計一致性，
# 防止清單作者在寫 \uXXXX 時誤打鄰近字（如想加「遗 U+9057」誤打「遺 U+907A」）。
#
# 格式：(traditional_cp, simplified_cp, japanese_new_cp_or_None, gloss)
#   - traditional_cp: 繁體字 codepoint（必填）
#   - simplified_cp:  簡體字 codepoint（無對應簡化時填 None）
#   - japanese_new_cp: 日文新字體 codepoint（無對應新字體時填 None；繁日共用時 = traditional_cp）
#   - gloss: 字形說明（人類可讀，輔助維護者辨識）
#
# 來源：PC-085 §症狀首發案例表 + PC-074 / PC-084 配對表
# 設計原則（PC-085）：每個 codepoint 寫成 \uXXXX 形式 + 同行註解附字形（肉眼可辨）
CONFUSABLE_PAIRS = (
    (0x907A, 0x9057, 0x907A, "遺 / 遗 / 遺（日同繁）"),
    (0x8B80, 0x8BFB, 0x8AAD, "讀 / 读 / 読"),
    (0x9451, None,   0x9451, "鑑 / —— / 鑑（繁日共用，PC-084 禁入）"),
    (0x96B8, 0x96B6, 0x96B8, "隸 / 隶 / 隸（日同繁）"),
    (0x7368, 0x72EC, 0x7368, "獨 / 独 / 獨"),
    (0x9055, 0x8FDD, 0x9055, "違 / 违 / 違"),
    (0x6C7A, 0x51B3, 0x6C7A, "決 / 决 / 決"),
    (0x95DC, 0x5173, 0x95A2, "關 / 关 / 関"),
    (0x70BA, 0x4E3A, 0x70BA, "為 / 为 / 為"),
    (0x8207, 0x4E0E, 0x8207, "與 / 与 / 與"),
    (0x767C, 0x53D1, 0x767A, "發 / 发 / 発"),
    (0x5716, 0x56FE, 0x56F3, "圖 / 图 / 図"),
    (0x5169, 0x4E24, 0x4E21, "兩 / 两 / 両"),
    (0x8B6F, 0x8BD1, 0x8A33, "譯 / 译 / 訳"),
    (0x9A5B, 0x9A7F, 0x99C5, "驛 / 驿 / 駅"),
    (0x5BE6, 0x5B9E, 0x5B9F, "實 / 实 / 実"),
    (0x6C23, 0x6C14, 0x6C17, "氣 / 气 / 気"),
    (0x6A02, 0x4E50, 0x697D, "樂 / 乐 / 楽"),
    (0x89C0, 0x89C2, 0x89B3, "觀 / 观 / 観"),
    (0x6AA2, 0x68C0, 0x691C, "檢 / 检 / 検"),
    (0x6B0A, 0x6743, 0x6A29, "權 / 权 / 権"),
    (0x8CE3, 0x5356, 0x58F2, "賣 / 卖 / 売"),
    (0x9435, 0x94C1, 0x9244, "鐵 / 铁 / 鉄"),
    (0x8F49, 0x8F6C, 0x8EE2, "轉 / 转 / 転"),
    (0x5EE3, 0x5E7F, 0x5E83, "廣 / 广 / 広"),
)


def validate_confusable_pairs_consistency() -> dict:
    """
    啟動 self-check：驗證 SIMPLIFIED_CHARS / JAPANESE_ONLY 與 CONFUSABLE_PAIRS 一致性。

    回傳分兩級（PC-085 §防護措施 Lint 輔助）：
    - critical（誤入）：清單作者寫 \\uXXXX 時誤打鄰近 codepoint（PC-085 首發案例真實風險）
        - 規則 2: traditional_cp 不應出現在 SIMPLIFIED_CHARS（繁體誤入）
        - 規則 3: 日文新字體 cp 不應出現在 SIMPLIFIED_CHARS（PC-074 教訓）
        - 規則 4: 繁日共用字（trad_cp == jp_cp）不應出現在 JAPANESE_ONLY（PC-084 禁入）
    - info（漏網）：簡體字漏收，屬清單漸進擴充的預期狀態（PC-074：只收實際遇過字）
        - 規則 1: simplified_cp 未在 SIMPLIFIED_CHARS

    設計理由：
    - critical 級別寫 stderr（規則 4：失敗必須可見），代表清單設計筆誤需修正
    - info 級別僅 logger.info，不污染 stderr 雙通道契約（PC-074：清單漸進擴充）

    Returns:
        {
            "critical": [warning_message, ...],  # 設計筆誤，須立即修正
            "info":     [info_message, ...],     # 漏網提示，可選擴充
        }
    """
    critical: list = []
    info: list = []

    for trad_cp, simp_cp, jp_cp, gloss in CONFUSABLE_PAIRS:
        # 規則 1（info）：簡體應在 SIMPLIFIED_CHARS（除非 None）
        # 漏網屬清單漸進擴充的預期狀態，不寫 stderr
        if simp_cp is not None and chr(simp_cp) not in SIMPLIFIED_CHARS:
            info.append(
                f"PC-085 漏網提示：{gloss} 簡體 U+{simp_cp:04X} 未在 SIMPLIFIED_CHARS"
            )

        # 規則 2（critical）：繁體不應在 SIMPLIFIED_CHARS（PC-085 首發案例 codepoint 筆誤）
        if chr(trad_cp) in SIMPLIFIED_CHARS:
            critical.append(
                f"PC-085 誤入：{gloss} 繁體 U+{trad_cp:04X} 不應在 SIMPLIFIED_CHARS（疑似 codepoint 筆誤）"
            )

        # 規則 3（critical）：日文新字體不應在 SIMPLIFIED_CHARS（PC-074 教訓）
        # 但若 jp_cp == trad_cp（繁日共用），不檢查（屬正常情況）
        if jp_cp is not None and jp_cp != trad_cp and chr(jp_cp) in SIMPLIFIED_CHARS:
            critical.append(
                f"PC-074/085 誤入：{gloss} 日文新字體 U+{jp_cp:04X} 不應在 SIMPLIFIED_CHARS"
            )

        # 規則 4（critical）：JAPANESE_ONLY 中若有 traditional_cp（繁日共用），警告（PC-084 禁入）
        if jp_cp is not None and jp_cp == trad_cp and chr(jp_cp) in JAPANESE_ONLY:
            critical.append(
                f"PC-084/085 誤入：{gloss} 繁日共用字 U+{jp_cp:04X} 不應在 JAPANESE_ONLY（保守不入）"
            )

    return {"critical": critical, "info": info}


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

    # W17-068：啟動時 PC-085 self-check（驗證清單設計一致性）
    # 規則 4：失敗必須可見（stderr + 日誌雙通道）
    # critical（誤入）→ stderr + logger.error（清單設計筆誤需修正）
    # info（漏網）→ 僅 logger.info（清單漸進擴充屬預期）
    consistency_result = validate_confusable_pairs_consistency()
    critical_warnings = consistency_result["critical"]
    info_warnings = consistency_result["info"]

    if critical_warnings:
        logger.error(
            "PC-085 self-check 偵測 %d 處清單設計筆誤：%s",
            len(critical_warnings),
            critical_warnings,
        )
        sys.stderr.write(
            f"[charset-guard] PC-085 self-check 設計筆誤（{len(critical_warnings)} 處）：\n"
        )
        for w in critical_warnings:
            sys.stderr.write(f"  - {w}\n")
        # 不阻擋 hook 主邏輯，僅警示維護者；維護者應修正清單後重啟

    if info_warnings:
        logger.info(
            "PC-085 self-check 漏網提示 %d 處（清單漸進擴充屬預期）：%s",
            len(info_warnings),
            info_warnings,
        )

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
