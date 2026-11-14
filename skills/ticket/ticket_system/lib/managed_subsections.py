"""CLI 自動寫入的 H3 子節定義（單一來源，不依賴 filelock）。

ticket create／dispatch 會在 `## Problem Analysis` 下寫入 H3 子節，這些內容不是
執行者寫的分析。三方共用同一份清單：
- `track_dispatch`：dispatch 寫入與 `append-log --replace` 保留
- `track_acceptance`：`append-log --replace` 覆寫前切出自動產生內容
- hooks（如 analysis-before-edit-checkpoint）：判定分析章節是否已填前先移除

放在 lib 而非 commands：commands 模組在匯入時即依賴 filelock，hook 的執行環境
只保證 pyyaml，從這裡匯入才不會讓 hook 在載入時失敗。
"""

import re
from typing import Optional

# 派發日誌：dispatch 逐次追加的暫態內容（commit 歸屬、臨時能力調整等）
DISPATCH_LOG_SECTION = "派發日誌"

# Commit 規範：dispatch 每次冪等覆寫的固定 staging 制式句
COMMIT_SECTION_HEADING = "Commit 規範"

# dispatch 管理的 H3 子節（append-log --replace 取代 Problem Analysis 時保留）
CLI_MANAGED_H3_HEADINGS = (DISPATCH_LOG_SECTION, COMMIT_SECTION_HEADING)

# ticket create 寫入的 H3 子節（與 CLI_MANAGED_H3_HEADINGS 同語意，產生者為 create）
CREATE_GENERATED_H3_HEADINGS = ("查重紀錄",)


def find_h3_subsection(section_content: str, heading: str) -> Optional[tuple]:
    """在 H2 section 內容中定位單一 H3 子節 `### {heading}`，回傳
    `(start, content_start, end, text)`；未找到回傳 None。

    邊界為下一個「## 」或「### 」（不分層級）。`section_locator.find_section(...,
    levels=(3,))` 只認下一個 H2，多個手足 H3 並存時前一個子節會吞掉後面的手足，
    故不共用該函式。
    """
    header_match = re.search(rf"^###\s+{re.escape(heading)}\s*$", section_content, re.MULTILINE)
    if not header_match:
        return None
    start = header_match.start()
    content_start = header_match.end()
    if content_start < len(section_content) and section_content[content_start] == "\n":
        content_start += 1
    boundary_match = re.search(r"\n#{2,3} ", section_content[content_start:])
    end = content_start + boundary_match.start() if boundary_match else len(section_content)
    return start, content_start, end, section_content[start:end]
