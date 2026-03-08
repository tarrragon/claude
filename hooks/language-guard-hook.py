#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///

"""
Language Guard Hook - 偵測輸出語言切換

功能：
- UserPromptSubmit 事件觸發，讀取 transcript JSONL 取得前一輪回應
- 掃描回應中的韓文（Unicode AC00-D7AF）和日文假名（3040-30FF）字元
- 偵測到非繁體中文/英文字元時，輸出警告到 stderr

使用方式：
    UserPromptSubmit Hook 自動觸發

環境變數：
    HOOK_DEBUG: 啟用詳細日誌（true/false）
"""

import sys
import json
from pathlib import Path
from typing import Optional

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

# 警告訊息前綴
WARNING_PREFIX = "[LANG GUARD]"

# Hook 名稱
HOOK_NAME = "language-guard-hook"


# ============================================================================
# 輔助函式
# ============================================================================

def contains_korean(text: str) -> bool:
    """檢查文字是否包含韓文字元"""
    for char in text:
        code = ord(char)
        if KOREAN_RANGE_START <= code <= KOREAN_RANGE_END:
            return True
    return False


def contains_japanese_kana(text: str) -> bool:
    """檢查文字是否包含日文假名（平假名或片假名）"""
    for char in text:
        code = ord(char)
        hiragana = HIRAGANA_RANGE_START <= code <= HIRAGANA_RANGE_END
        katakana = KATAKANA_RANGE_START <= code <= KATAKANA_RANGE_END
        if hiragana or katakana:
            return True
    return False


def contains_non_expected_language(text: str) -> bool:
    """檢查文字是否包含非預期語言（韓文或日文）"""
    return contains_korean(text) or contains_japanese_kana(text)


def extract_previous_assistant_message(hook_input: dict, logger) -> Optional[str]:
    """
    從 Hook 輸入中提取前一輪 assistant 回應

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
        logger.warning(f"提取 transcript 失敗: {e}")
        return None


# ============================================================================
# 主程式入口
# ============================================================================

def main() -> int:
    """主程式入口"""
    logger = setup_hook_logging(HOOK_NAME)

    try:
        # 讀取 stdin 輸入
        hook_input = read_json_from_stdin(logger)

        # 若無輸入，直接返回成功
        if hook_input is None:
            logger.debug("無 Hook 輸入（empty stdin），靜默通過")
            return 0

        logger.debug(f"接收到 Hook 輸入")

        # 提取前一輪 assistant 回應
        previous_message = extract_previous_assistant_message(hook_input, logger)

        # 若無前一輪回應，靜默略過（不報錯）
        if previous_message is None:
            logger.debug("無前一輪 assistant 回應，靜默通過")
            return 0

        # 檢查是否包含非預期語言
        if contains_non_expected_language(previous_message):
            # 偵測到非預期語言，輸出警告到 stderr
            warning_message = (
                f"\n{WARNING_PREFIX} 警告：前一輪輸出檢測到非繁體中文/英文字元\n"
                f"{WARNING_PREFIX} 這可能表示 AI 的語言一致性出現偏差\n"
                f"{WARNING_PREFIX} 請檢查上方的回應內容，確認語言是否正確\n"
            )
            sys.stderr.write(warning_message)
            logger.warning("偵測到韓文或日文字元在 assistant 回應中")

        return 0

    except Exception as e:
        logger.error(f"Hook 執行錯誤: {e}")
        # 例外時靜默通過，不阻止用戶繼續
        return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
