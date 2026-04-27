#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///

"""
Language Guard Hook - 偵測前一輪 assistant 回應的語言/格式違規

功能：
- UserPromptSubmit 事件觸發，讀取 transcript JSONL 取得前一輪回應
- 三類偵測（皆為警告非阻擋；exit 0）：
  1. 非預期語言：韓文（U+AC00-D7AF）、日文假名（U+3040-30FF）
  2. Emoji codepoint：U+1F300-U+1FAFF / U+2600-U+27BF 等主要範圍
  3. 隱含表達 6 句型（document-writing-style v1.2.0 反模式表）
- 觸發後寫入 stderr + 日誌（規則 4：失敗必須可見）

設計原則（W17-068 / W17-066 ginger P1 + linux L-C1）：
- L1 同步阻擋層由 askuserquestion-charset-guard-hook.py 處理（exit 2 阻擋）
- 本 hook 為 L1 警告層，避免 false positive 阻擋合法引用
- 隱含表達為語意問題，需 basil 兜底；hook 僅標記疑似位置

使用方式：
    UserPromptSubmit Hook 自動觸發

環境變數：
    HOOK_DEBUG: 啟用詳細日誌（true/false）
"""

import sys
import re
from pathlib import Path
from typing import Optional, List, Tuple

# 加入 hook_utils 路徑（相同目錄）
sys.path.insert(0, str(Path(__file__).parent))

from hook_utils import setup_hook_logging, run_hook_safely, read_json_from_stdin


# ============================================================================
# 常數定義
# ============================================================================

# Unicode 範圍：韓文（Hangul Syllables）
KOREAN_RANGE_START = 0xAC00
KOREAN_RANGE_END = 0xD7AF

# Unicode 範圍：日文平假名（Hiragana）
HIRAGANA_RANGE_START = 0x3040
HIRAGANA_RANGE_END = 0x309F

# Unicode 範圍：日文片假名（Katakana）
KATAKANA_RANGE_START = 0x30A0
KATAKANA_RANGE_END = 0x30FF

# Emoji unicode 範圍（W17-068 新增；命中即警告）
# 範圍對齊 askuserquestion-charset-guard-hook.py EMOJI_RANGES，保持一致性
EMOJI_RANGES = (
    (0x2600, 0x27BF),    # Miscellaneous Symbols
    (0x1F300, 0x1F5FF),  # Miscellaneous Symbols and Pictographs
    (0x1F600, 0x1F64F),  # Emoticons
    (0x1F680, 0x1F6FF),  # Transport and Map
    (0x1F900, 0x1F9FF),  # Supplemental Symbols and Pictographs
    (0x1FA00, 0x1FAFF),  # Symbols and Pictographs Extended-A
)

# 隱含表達 6 句型（W17-068 新增；對應 document-writing-style v1.2.0 反模式表）
# 來源：.claude/rules/core/document-writing-style.md L115-L120
# 設計原則：警告非阻擋（語意需 basil 兜底，避免阻擋合法引用 / 規範描述本身）
# 每組（pattern, hint）→ pattern 為偵測字串、hint 為修正方向
IMPLICIT_EXPRESSION_PATTERNS: Tuple[Tuple[str, str], ...] = (
    ("希望讀者理解", "把責任推給讀者；改為明示：『此原則依據 X，違反會導致 Y』"),
    ("按理應", "假設共識；改為明示條件：『當 X 條件成立時，應做 Y』"),
    ("自然而然", "假設共識；改為明示條件：『當 X 條件成立時，應做 Y』"),
    ("通常來說", "條件模糊；改為明示邊界：『除了 X/Y 情境外，應做 Z』"),
    ("一般情況下", "條件模糊；改為明示邊界：『除了 X/Y 情境外，應做 Z』"),
    ("假設讀者會注意到", "把規則寄託於讀者自律；改為明示強制點：『Hook A 在時機 B 強制檢查』"),
    ("理想情況下", "未指明落差處理；改為明示落差：『理想 X；現實 Y；先做 Z 達到 W』"),
)

# 警告訊息前綴
WARNING_PREFIX = "[LANG GUARD]"

# Hook 名稱
HOOK_NAME = "language-guard-hook"


# ============================================================================
# 偵測函式
# ============================================================================

def contains_korean(text: str) -> bool:
    """檢查文字是否包含韓文字元。"""
    for char in text:
        code = ord(char)
        if KOREAN_RANGE_START <= code <= KOREAN_RANGE_END:
            return True
    return False


def contains_japanese_kana(text: str) -> bool:
    """檢查文字是否包含日文假名（平假名或片假名）。"""
    for char in text:
        code = ord(char)
        hiragana = HIRAGANA_RANGE_START <= code <= HIRAGANA_RANGE_END
        katakana = KATAKANA_RANGE_START <= code <= KATAKANA_RANGE_END
        if hiragana or katakana:
            return True
    return False


def contains_non_expected_language(text: str) -> bool:
    """檢查文字是否包含非預期語言（韓文或日文假名）。"""
    return contains_korean(text) or contains_japanese_kana(text)


def find_emoji_chars(text: str) -> List[Tuple[str, int]]:
    """
    掃描文字中的 emoji 字元（W17-068 新增）。

    Returns:
        [(char, codepoint), ...] — 命中的 emoji 字元清單；空 list = 無命中
    """
    hits: List[Tuple[str, int]] = []
    seen_codes = set()  # 去重避免同一 emoji 重複報告
    for char in text:
        code = ord(char)
        if code in seen_codes:
            continue
        for range_start, range_end in EMOJI_RANGES:
            if range_start <= code <= range_end:
                hits.append((char, code))
                seen_codes.add(code)
                break
    return hits


def find_implicit_expressions(text: str) -> List[Tuple[str, str]]:
    """
    掃描文字中的隱含表達 6 句型（W17-068 新增）。

    Returns:
        [(pattern, hint), ...] — 命中的句型 + 修正方向；空 list = 無命中
    """
    hits: List[Tuple[str, str]] = []
    for pattern, hint in IMPLICIT_EXPRESSION_PATTERNS:
        if pattern in text:
            hits.append((pattern, hint))
    return hits


# ============================================================================
# Transcript 解析
# ============================================================================

def extract_previous_assistant_message(hook_input: dict, logger) -> Optional[str]:
    """
    從 Hook 輸入中提取前一輪 assistant 回應。

    Hook 輸入結構：
    {
        "transcript": [
            {"role": "user", "content": "..."},
            {"role": "assistant", "content": "..."},
            ...
        ]
    }

    Returns:
        前一輪 assistant 回應的 content，或 None（若無 transcript 或無 assistant 回應）
    """
    try:
        transcript = hook_input.get("transcript")
        if not isinstance(transcript, list) or not transcript:
            logger.debug("無 transcript 或 transcript 為空")
            return None

        # 從後往前掃描，找最後一個 assistant 訊息
        for item in reversed(transcript):
            if isinstance(item, dict) and item.get("role") == "assistant":
                content = item.get("content")
                if isinstance(content, str):
                    logger.debug(f"找到前一輪 assistant 回應，長度 {len(content)}")
                    return content

        logger.debug("Transcript 中未找到 assistant 回應")
        return None

    except Exception as e:
        logger.info(f"提取 transcript 失敗（已預期的非標準輸入）: {e}")
        return None


# ============================================================================
# 警告訊息建構
# ============================================================================

def build_language_warning() -> str:
    """非預期語言警告訊息。"""
    return (
        f"\n{WARNING_PREFIX} 警告：前一輪輸出檢測到非繁體中文/英文字元（韓文 / 日文假名）\n"
        f"{WARNING_PREFIX} 這可能表示 AI 的語言一致性出現偏差\n"
        f"{WARNING_PREFIX} 請檢查上方的回應內容，確認語言是否正確\n"
    )


def build_emoji_warning(hits: List[Tuple[str, int]]) -> str:
    """Emoji 違規警告訊息（W17-068 新增）。"""
    char_list = ", ".join(f"'{ch}' (U+{cp:04X})" for ch, cp in hits[:10])
    suffix = f"（共 {len(hits)} 處）" if len(hits) > 10 else ""
    return (
        f"\n{WARNING_PREFIX} 警告：前一輪輸出含 emoji 字元{suffix}\n"
        f"{WARNING_PREFIX} 命中字元：{char_list}\n"
        f"{WARNING_PREFIX} 違反 .claude/rules/core/language-constraints.md 規則 3（禁止 emoji）\n"
        f"{WARNING_PREFIX} 修正方向：移除 emoji 或改用 ASCII 標記 [OK]/[WARN]/[FAIL]\n"
    )


def build_implicit_expression_warning(hits: List[Tuple[str, str]]) -> str:
    """隱含表達句型警告訊息（W17-068 新增；警告非阻擋）。"""
    lines = [f"\n{WARNING_PREFIX} 警告：前一輪輸出含隱含表達句型（共 {len(hits)} 處）"]
    for pattern, hint in hits:
        lines.append(f"{WARNING_PREFIX}   - 「{pattern}」→ {hint}")
    lines.append(
        f"{WARNING_PREFIX} 違反 .claude/rules/core/document-writing-style.md "
        f"v1.2.0 反模式表（語意需 basil 兜底，警告非阻擋）"
    )
    return "\n".join(lines) + "\n"


# ============================================================================
# 主程式入口
# ============================================================================

def main() -> int:
    """主程式入口。"""
    logger = setup_hook_logging(HOOK_NAME)

    try:
        # 讀取 stdin 輸入
        hook_input = read_json_from_stdin(logger)

        # 若無輸入，直接返回成功
        if hook_input is None:
            logger.debug("無 Hook 輸入（empty stdin），靜默通過")
            return 0

        logger.debug("接收到 Hook 輸入")

        # 提取前一輪 assistant 回應
        previous_message = extract_previous_assistant_message(hook_input, logger)

        # 若無前一輪回應，靜默略過（不報錯）
        if previous_message is None:
            logger.debug("無前一輪 assistant 回應，靜默通過")
            return 0

        # 偵測 1：非預期語言（韓文 / 日文假名）
        if contains_non_expected_language(previous_message):
            sys.stderr.write(build_language_warning())
            logger.warning("偵測到韓文或日文假名字元在 assistant 回應中")

        # 偵測 2：Emoji（W17-068 新增）
        emoji_hits = find_emoji_chars(previous_message)
        if emoji_hits:
            sys.stderr.write(build_emoji_warning(emoji_hits))
            logger.warning(
                "偵測到 %d 處 emoji 字元（前 5 個：%s）",
                len(emoji_hits),
                [(ch, f"U+{cp:04X}") for ch, cp in emoji_hits[:5]],
            )

        # 偵測 3：隱含表達 6 句型（W17-068 新增；警告非阻擋）
        implicit_hits = find_implicit_expressions(previous_message)
        if implicit_hits:
            sys.stderr.write(build_implicit_expression_warning(implicit_hits))
            logger.warning(
                "偵測到 %d 處隱含表達句型：%s",
                len(implicit_hits),
                [p for p, _ in implicit_hits],
            )

        return 0

    except Exception as e:
        # 規則 4：失敗必須可見（stderr + 日誌雙通道）
        # 已預期的非標準輸入走 logger.info 路徑（read_json_from_stdin 內處理）
        # 此處 catch 為未預期 crash，logger.error + stderr
        logger.error(f"Hook 執行錯誤: {e}")
        sys.stderr.write(f"{WARNING_PREFIX} Hook 內部錯誤（已記錄日誌）：{e}\n")
        # 例外時靜默通過，不阻止用戶繼續
        return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
