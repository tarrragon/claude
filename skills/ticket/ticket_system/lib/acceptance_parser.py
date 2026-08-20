"""acceptance 條目的 CLI 輸入解析。

`--acceptance` 接受兩種寫法——多次指定旗標，或以分隔符在單一值內串接多條。
本模組負責把這兩種形式正規化為條目列表，並在偵測到疑似誤用時產出警告
（而非拒絕）：分隔符出現在條目內文時可用反斜線跳脫保留字面，未跳脫而被拆條
會發出警告供確認；使用者把編號列表整段貼入單一條目時同樣發出警告，
因為那通常是想要多條而非一條。

自 commands/create.py 抽出（0.2.1-W3-834 分群結論第 B 群）：本群為純字串處理、
無副作用、有 17 項專屬測試覆蓋跳脫邊界，是該次分群中風險最低的一群。
抽出後 track_acceptance 的 `set-acceptance --add` 亦可重用同一份解析，
避免同格式在兩處各實作一次。
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

from ticket_system.lib.command_lifecycle_messages import CreateMessages, format_msg
from ticket_system.lib.messages import format_warning


ACCEPTANCE_SEP = "|"

# 編號列表行形態：可選前導空白 + 數字 + 分隔符（. 、 或 )），如「1. 」「2、」「3)」
ACCEPTANCE_NUMBERED_LINE = re.compile(r"^\s*\d+[.、)]")


def detect_numbered_list_collapse(item: str) -> Optional[str]:
    """偵測單一 --acceptance 值是否內含 >= 2 行編號列表（將被摺疊為單一條目）。

    多行編號列表（如「1. 條件一\\n2. 條件二」）以換行分隔，不受 `|` 拆條邏輯
    處理，會被靜默摺疊成一條驗收條件，使逐項驗收語意失效。本函式僅偵測並
    提示，不改變拆分語意（多行單條目仍合法保留，是否拆條由使用者決定）。

    Args:
        item: 單一 --acceptance 原始值（可能含換行）

    Returns:
        命中時回傳格式化警告字串；未命中回傳 None
    """
    numbered_lines = [
        line.strip() for line in item.split("\n") if ACCEPTANCE_NUMBERED_LINE.match(line)
    ]
    if len(numbered_lines) < 2:
        return None
    preview = "\n".join(f"             {line}" for line in numbered_lines)
    return format_warning(
        CreateMessages.ACCEPTANCE_NUMBERED_LIST_COLLAPSE_WARNING,
        count=len(numbered_lines),
        preview=preview,
    )


def parse_acceptance_items(raw_items: List[str]) -> tuple:
    """解析 --acceptance 多值，支援分隔符拆條 + 反斜線跳脫 + 拆條警告 + 編號列表摺疊警告。

    分隔符 `|` 用於在單一 --acceptance 值內表達多條驗收條件。但當內文本身
    需要使用該字元（如描述 shell pipe），無條件 split 會靜默拆條（W3-089）。

    處理規則：
    - `\\|`（反斜線 + 分隔符）視為跳脫，還原為字面 `|`，不拆條。
    - 未跳脫的 `|` 才作為分隔符拆條。
    - 單一 --acceptance 值經未跳脫分隔符拆出 > 1 段時，回傳警告供呼叫端提示，
      讓使用者確認是否為預期行為（與 PC-079 同家族：CLI 參數含工具特殊字元）。
    - 單一 --acceptance 值含 >= 2 行編號列表形態（如「1. 」「2、」）時，回傳警告
      提示該值會被摺疊為單一驗收條件，不會依編號自動拆條（拆分語意零變更，
      僅偵測與提示；正確用法改多次 --acceptance 或以 | 分隔）。

    Args:
        raw_items: argparse 收集的 --acceptance 值列表（可能多次指定）

    Returns:
        (acceptance, warnings) tuple：
        - acceptance: 解析後的驗收條件列表（已去空白、去空項）
        - warnings: 警告訊息列表（每個被拆條或摺疊偵測的原始值各一條）
    """
    acceptance: List[str] = []
    warnings: List[str] = []
    for item in raw_items:
        numbered_list_warning = detect_numbered_list_collapse(item)
        if numbered_list_warning:
            warnings.append(numbered_list_warning)
        segments = split_unescaped(item, ACCEPTANCE_SEP)
        cleaned = [s.strip() for s in segments]
        cleaned = [s for s in cleaned if s]
        if len(cleaned) > 1:
            preview = "\n".join(f"             {i + 1}. {s}" for i, s in enumerate(cleaned))
            warnings.append(
                format_warning(
                    CreateMessages.ACCEPTANCE_PIPE_SPLIT_WARNING,
                    count=len(cleaned),
                    preview=preview,
                )
            )
        acceptance.extend(cleaned)
    return acceptance, warnings


def split_unescaped(text: str, sep: str) -> List[str]:
    """以 sep 拆分 text，但反斜線跳脫的 sep 還原為字面字元不拆。

    逐字元掃描：`\\sep` → 字面 sep；單獨 `\\` 後接其他字元 → 保留原樣；
    未跳脫 sep → 切段。避免 str.split 無法區分跳脫的限制。
    """
    segments: List[str] = []
    buffer: List[str] = []
    i = 0
    length = len(text)
    while i < length:
        char = text[i]
        if char == "\\" and i + 1 < length and text[i + 1] == sep:
            buffer.append(sep)
            i += 2
            continue
        if char == sep:
            segments.append("".join(buffer))
            buffer = []
            i += 1
            continue
        buffer.append(char)
        i += 1
    segments.append("".join(buffer))
    return segments
