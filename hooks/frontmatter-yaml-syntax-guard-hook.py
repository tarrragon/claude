#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""frontmatter-yaml-syntax-guard — PostToolUse Hook（YAML frontmatter 源頭驗證）

背景（源於 PyYAML 遷移後的 Phase 4 多視角審查發現）：
`.md` 檔案開頭的 YAML frontmatter 解析是全有全無——單一未跳脫的冒號（如
`why: 根因是 X: Y`）或 flow-style 誤觸字元（如 `{...}`）即使整份 frontmatter
靜默回傳空字典。既有呼叫端（parse_ticket_frontmatter 等）一律
`if not frontmatter: return None`，「解析失敗」與「本來就沒有 frontmatter」
在下游無法分辨，錯誤因此在編輯當下不可見，只能等 runtime 讀不到欄位時才
暴露（且往往被誤判為別的問題）。

本 hook 在 Edit/Write 完成後（PostToolUse）立即讀回檔案並嘗試解析 frontmatter，
語法錯誤時把訊息連同可定位的行號回報給編輯者，把失敗從「runtime 靜默」
移到「編輯當下可見」，屬源頭阻斷層；hook-logs 事後偵測層互補但不重疊
（見對應 ticket Context Bundle 的雙層防護定位說明）。

觸發範圍（Solution 決策，非票面預設路徑限定）：
不限定路徑（不用允許清單），只要求 (1) 檔案副檔名為 .md、(2) 內容以獨占
一行的 `---` 開頭（frontmatter 起始邊界既有慣例）。純內容判定使檢查天然
自我限縮——不含 frontmatter 的 .md 檔案完全不觸發，不需要為每個消費
frontmatter 的角色（ticket / agent 定義 / error-pattern / agent 範本）
各自維護一份路徑允許清單，也不會遺漏未來新增的 frontmatter 消費者。

阻擋策略（Solution 決策）：
語法錯誤 → exit 2（阻擋），因為結構化 frontmatter 是本專案多處消費端
（ticket 狀態機、agent 定義載入、error-pattern 索引）共同依賴的契約，
壞掉的 frontmatter 幾乎必然是缺陷而非刻意設計，僅警告不足以驅動修正
（opinionated-default-design：預設行為應引導正確做法，不能只靠文件
提醒）。逃生閥：檔案任意位置（不需在 frontmatter 區塊內，因為區塊本身
可能就是壞的）加入 `<!-- yaml-frontmatter-exempt: <理由> -->` 後，本次
異常降級為 stderr 警告，不阻擋——語法與 reference-stability-rule8-guard
的行內 marker 逃生閥同構（同一設計慣例的延伸套用）。

行號換算（實作陷阱）：
pyyaml 的 `YAMLError.problem_mark.line` 為 0-indexed，且相對於「已去除
頭尾空白（.strip()）後」的 frontmatter 區塊文字，非檔案原始行號。本檔
`check_frontmatter_yaml()` 以 `raw_block` 相對 `stripped_block` 的前導
空白長度換算出 `stripped_block` 在原始檔案中的起始行號（base_line），
再加上 `problem_mark.line` 得到檔案真實行號，訊息中明示「檔案第 N 行」。

Hook Type: PostToolUse (Edit, Write, MultiEdit)

Exit Codes:
    0 - 無 frontmatter / frontmatter 合法 / 有逃生閥 marker（降級警告）/
        輸入或檔案讀取異常（fail-open，見 hook 自身失敗處理）
    2 - 偵測到 frontmatter 起始邊界但解析失敗（語法錯誤 / 結束邊界缺失 /
        頂層結構非 dict），且無逃生閥 marker
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from lib import setup_hook_logging, run_hook_safely, read_json_from_stdin
except ImportError as e:
    # hook 自身失敗雙通道（quality-baseline 規則 4）：import 失敗時尚無
    # logger 可用，僅能靠 stderr 讓用戶可見；fail-open（exit 0）避免因
    # 本 hook 壞掉而連帶擋住所有 Edit/Write。
    print(f"[Hook Import Error] {Path(__file__).name}: {e}", file=sys.stderr)
    sys.exit(0)

import yaml  # noqa: E402


# ============================================================================
# 常數
# ============================================================================

EXIT_ALLOW = 0
EXIT_BLOCK = 2

HOOK_NAME = "frontmatter-yaml-syntax-guard"

# frontmatter 邊界：--- 須獨占一行（允許行尾空白），錨定於行首。與
# lib/hook_ticket.py 的 _FRONTMATTER_BOUNDARY_RE 同構（該正則是修復
# 「欄位值內連續三個減號被誤判為邊界」後的版本）。本檔獨立維護同構定義
# 而非 import 該私有符號（前綴底線非公開契約，避免耦合 lib 內部實作）。
_FRONTMATTER_BOUNDARY_RE = re.compile(r"^---[ \t]*(?:\r\n|\n|\Z)", re.MULTILINE)

# 逃生閥 marker：可置於檔案任意位置（不需在 frontmatter 區塊內）。
_EXEMPT_MARKER_RE = re.compile(r"<!--\s*yaml-frontmatter-exempt:\s*(.+?)\s*-->")

_ERROR_KIND_MISSING_FENCE = "missing_closing_fence"
_ERROR_KIND_SYNTAX = "yaml_syntax_error"
_ERROR_KIND_NON_DICT = "non_dict_toplevel"


class FrontmatterError:
    """單次 frontmatter 檢查失敗的結構化結果。"""

    def __init__(self, kind: str, message: str, line: "Optional[int]" = None):
        self.kind = kind
        self.message = message
        self.line = line


# ============================================================================
# 核心檢查邏輯
# ============================================================================

def check_frontmatter_yaml(content: str) -> "Optional[FrontmatterError]":
    """檢查檔案開頭的 YAML frontmatter 是否可解析。

    Args:
        content: 檔案完整內容

    Returns:
        None：檔案未以獨占一行的 --- 開頭（非 frontmatter 檔案，不適用本
              檢查）、或 frontmatter 為空區塊、或成功解析為 dict
        FrontmatterError：偵測到 frontmatter 起始邊界但結構異常
    """
    start_match = _FRONTMATTER_BOUNDARY_RE.match(content)
    if start_match is None:
        return None

    end_match = _FRONTMATTER_BOUNDARY_RE.search(content, start_match.end())
    if end_match is None:
        return FrontmatterError(
            kind=_ERROR_KIND_MISSING_FENCE,
            message="找到起始 --- 但找不到獨占一行的結束 ---，frontmatter 區塊未封閉",
        )

    raw_block = content[start_match.end():end_match.start()]
    stripped_block = raw_block.strip()
    if not stripped_block:
        return None

    # 行號換算：stripped_block 在原始 content 中的起始行號（1-indexed）。
    leading_ws_len = len(raw_block) - len(raw_block.lstrip())
    block_start_offset = start_match.end() + leading_ws_len
    base_line = content[:block_start_offset].count("\n") + 1

    try:
        result = yaml.safe_load(stripped_block)
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        line = base_line + mark.line if mark is not None else None
        detail = str(e).replace("\n", " ")
        return FrontmatterError(kind=_ERROR_KIND_SYNTAX, message=detail, line=line)

    if not isinstance(result, dict):
        return FrontmatterError(
            kind=_ERROR_KIND_NON_DICT,
            message="frontmatter 頂層結構非 dict（實際型別: {}）".format(
                type(result).__name__
            ),
        )

    return None


def find_exempt_reason(content: str) -> "Optional[str]":
    """在完整檔案內容中尋找逃生閥 marker，回傳其理由文字（找不到回傳 None）。

    刻意掃描整份檔案而非僅 frontmatter 區塊：frontmatter 本身若已損壞，
    marker 不應被要求放在壞掉的區塊內部。
    """
    match = _EXEMPT_MARKER_RE.search(content)
    return match.group(1) if match else None


# ============================================================================
# 訊息組裝
# ============================================================================

def build_block_message(file_path: str, err: FrontmatterError) -> str:
    """組合阻擋訊息（exit 2 時寫入 stderr）。"""
    lines = [
        f"[BLOCKED][{HOOK_NAME}] YAML frontmatter 解析失敗（exit 2）：{file_path}",
    ]
    if err.kind == _ERROR_KIND_SYNTAX:
        loc = f"檔案第 {err.line} 行" if err.line is not None else "位置不明"
        lines.append(f"錯誤（{loc}）：{err.message}")
        lines.append(
            "常見成因：欄位值含未跳脫冒號（如 `why: 根因是 X: Y`）或 flow-style "
            "字元（`{` `}` `[` `]`）落在未加引號的純量值中。"
            "修法：整段值加引號 `\"...\"`，或改用 `>` / `|` block scalar。"
        )
    else:
        lines.append(f"錯誤：{err.message}")
    lines.append(
        "背景：PyYAML 為全有全無解析——單一語法錯誤會使整份 frontmatter 靜默"
        "回傳空字典，下游讀取端（status / acceptance / who 等欄位）因此全部"
        "讀不到值，且無法與「本來就沒有 frontmatter」區分。"
    )
    lines.append(
        "逃生閥：若此檔案的內容有意呈現非合法 YAML（如格式示範），"
        "在檔案任意位置加入 `<!-- yaml-frontmatter-exempt: <理由> -->` 後重試，"
        "本次異常將降級為警告不阻擋。"
    )
    return "\n".join(lines) + "\n"


def build_exempt_warning_message(file_path: str, err: FrontmatterError, reason: str) -> str:
    """組合逃生閥豁免時的 stderr 警告訊息（不阻擋，但仍可見）。"""
    return (
        f"[{HOOK_NAME}] WARNING（逃生閥豁免，未阻擋）：{file_path} "
        f"frontmatter 異常（{err.kind}），因 yaml-frontmatter-exempt marker "
        f"放行。理由：{reason}\n"
    )


# ============================================================================
# 主入口
# ============================================================================

def main() -> int:
    logger = setup_hook_logging(HOOK_NAME)
    logger.info(f"{HOOK_NAME} Hook 啟動")

    input_data = read_json_from_stdin(logger)
    if input_data is None:
        logger.info("stdin 無 JSON 輸入，跳過（可能為未提供 payload 的事件）")
        return EXIT_ALLOW

    tool_name = input_data.get("tool_name", "")
    if tool_name not in ("Edit", "Write", "MultiEdit"):
        logger.debug(f"工具 {tool_name} 不在本 hook 檢查範圍，跳過")
        return EXIT_ALLOW

    tool_input = input_data.get("tool_input") or {}
    file_path = tool_input.get("file_path", "")
    if not file_path or not file_path.endswith(".md"):
        logger.debug(f"非 .md 檔案，跳過: {file_path}")
        return EXIT_ALLOW

    try:
        content = Path(file_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        logger.info(f"讀取檔案失敗，跳過: {file_path} ({e})")
        return EXIT_ALLOW

    err = check_frontmatter_yaml(content)
    if err is None:
        logger.debug(f"frontmatter 合法或不適用: {file_path}")
        return EXIT_ALLOW

    exempt_reason = find_exempt_reason(content)
    if exempt_reason:
        logger.info(
            f"偵測到 frontmatter 異常但有逃生閥 marker，降級為警告不阻擋: "
            f"file={file_path} kind={err.kind} line={err.line} reason={exempt_reason}"
        )
        sys.stderr.write(build_exempt_warning_message(file_path, err, exempt_reason))
        return EXIT_ALLOW

    sys.stderr.write(build_block_message(file_path, err))
    logger.warning(
        f"阻擋：frontmatter YAML 解析失敗 file={file_path} kind={err.kind} "
        f"line={err.line} detail={err.message}"
    )
    return EXIT_BLOCK


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
