"""Memory 目錄 layout 結構知識 SSOT（0.2.1-W3-196，Phase 4 第二輪修正）

兩個 hook 各自實作了 memory 目錄的認定，已漂移出實質缺陷（slug 推錯、
legacy 位置覆蓋不對稱（框架審查發現）：

- memory-write-guard-hook.py（PreToolUse deny）用正則直接判定「這個路徑是
  不是 memory 位置」——判定式，輸入路徑，回傳布林
- memory-dir-audit-hook.py（SessionStart/Stop 稽核）用 layout 表列舉「本
  專案的 memory 目錄在哪些位置」——列舉式，無輸入，回傳目錄清單

兩者要回答的問題不同，不可合併成單一函式（那會製造一個既要接受輸入又要能
無輸入列舉的介面）。本模組只收斂兩者共用的部分：**結構知識**——
`~/.claude/projects/<slug>/memory` 與 `~/auto-memory/<name>` 這兩種 layout
的存在，以及各自的識別符語意（前者是完整路徑的另一種編碼、後者是純專案
名稱）。判定邏輯與列舉邏輯仍各自留在對應 hook 內。

單一事實原則（Phase 4 第一輪審查發現：`path_segments` 與 `regex_fragment`
原本並排手寫兩份，無機制保證一致，是 ARCH-BAL-012 在同一個 dict 內的精準
復發）：**`path_segments` 是唯一事實**，regex fragment 由
`derive_regex_fragment()` 從中推導，不手寫第二份。識別符取法
（`get_layout_identifier()`）同理由 `path_segments` 中 `*` 的位置推導，不
在消費端另寫 `basename(dirname(x))` 之類的硬編碼。

呼叫端不得自行重新推導這份 layout 定義（ARCH-BAL-012：抽取後不得留下任何
一方仍自行推導結構知識）——包含「這個 layout 少一段是什麼樣子」這類衍生
查詢，也應呼叫 `get_layout_parent_glob_pattern()` 取得，不應在消費端重新
`os.path.join(home, ".claude", "projects", "*")`。

提供 API：
- MEMORY_LAYOUTS：兩種 layout 的結構定義（唯讀 tuple）。消費端一律
  `for layout in MEMORY_LAYOUTS` 走訪，不得只 import 具名常數後自行重排
  一張表——後者會在新增第三種 layout 時造成兩個消費端覆蓋範圍不對稱
  （0.2.1-W3-194 修過的同型缺陷）
- get_memory_dir_regex_fragments() -> List[str]：guard 判定式用，回傳兩種
  layout 推導出的 regex fragment（不含 home 前綴，未 anchor）
- get_anchored_memory_dir_pattern(home) -> str：guard 判定式用，回傳已
  anchor 至 home、已 `re.escape` 的完整 pattern 字串（呼叫端只需
  `re.compile(..., re.IGNORECASE)`）。錨定至 home 是結構知識的一部分
  （legacy/current 兩種 layout 都只在使用者 home 目錄下才成立），不應由
  guard 自行組裝
- get_layout_glob_pattern(layout, home) -> str：audit 列舉式用，依呼叫端
  當前的 home（可能被測試 monkeypatch）組出指定 layout 的 glob pattern
- get_layout_parent_glob_pattern(layout, home) -> str：audit 用於「比 layout
  本身更外層一段的存在性檢查」（例如檢查 `~/.claude/projects/` 這個 CC
  專案目錄機制本身是否存在，而非該 layout 對應的 memory 子目錄）
- get_layout_identifier(layout, matched_path) -> str：audit 列舉式用，依
  layout 的 `path_segments` 中 `*` 的位置，從命中路徑推導識別符

home 目錄刻意不在本模組內快取為模組級常數：本模組不持有環境狀態，home
一律由呼叫端傳入，模組本身對「現在的 home 是什麼」沒有意見。這不只是為了
遷就測試 monkeypatch——若本模組自行快取 home，就等於本模組對執行環境做出
了假設，這個假設本身就是它要消滅的那種「呼叫端自行推導」在模組內部重演。
"""

from __future__ import annotations

import os
import re
from typing import Dict, List, Tuple

# 現行位置：識別符（slug）是完整路徑的另一種編碼，比對鍵屬 "full_path"。
CURRENT_LAYOUT: Dict[str, object] = {
    "kind": "current",
    "path_segments": (".claude", "projects", "*", "memory"),
    "identifier_kind": "full_path",
}

# legacy 位置：識別符是純專案名稱，比對鍵屬 "project_name"。
LEGACY_LAYOUT: Dict[str, object] = {
    "kind": "legacy",
    "path_segments": ("auto-memory", "*"),
    "identifier_kind": "project_name",
}

MEMORY_LAYOUTS: Tuple[Dict[str, object], ...] = (LEGACY_LAYOUT, CURRENT_LAYOUT)


def derive_regex_fragment(path_segments: Tuple[str, ...]) -> str:  # i18n-exempt
    """由 path_segments 推導 regex fragment（唯一事實 -> 衍生值）。

    規則：`*` 轉 `[^/]+`，其餘 segment 逐字 `re.escape`，segment 間以 `/`
    相接，頭尾各補一個 `/` 分隔符——與兩條既有 layout 手寫的 fragment
    完全等價，此函式取代手寫，使 path_segments 成為唯一事實。
    """
    escaped_segments = [
        "[^/]+" if segment == "*" else re.escape(segment)
        for segment in path_segments
    ]
    return "/" + "/".join(escaped_segments) + "/"


def get_layout_regex_fragment(layout: Dict[str, object]) -> str:  # i18n-exempt
    """回傳指定 layout 的 regex fragment（由 path_segments 推導）。"""
    return derive_regex_fragment(layout["path_segments"])


def get_memory_dir_regex_fragments() -> List[str]:  # i18n-exempt
    """回傳兩種 layout 的 regex fragment 清單（guard 判定式用，未 anchor）。"""
    return [get_layout_regex_fragment(layout) for layout in MEMORY_LAYOUTS]


def get_anchored_memory_dir_pattern(home: str) -> str:  # i18n-exempt
    """回傳已 anchor 至 home、已 escape 的完整 regex pattern 字串。

    Args:
        home: 呼叫端當前的 home 目錄

    Returns:
        可直接餵給 `re.compile(pattern, re.IGNORECASE)` 的 pattern 字串
        （本函式不加 IGNORECASE flag，由呼叫端決定）。
    """
    fragments = get_memory_dir_regex_fragments()
    return re.escape(home) + r"(?:" + "|".join(fragments) + r")"


def get_layout_glob_pattern(layout: Dict[str, object], home: str) -> str:  # i18n-exempt
    """依呼叫端當前的 home 目錄，組出指定 layout 的 glob pattern（audit 列舉式用）。

    Args:
        layout: MEMORY_LAYOUTS 中的一個元素
        home: 呼叫端當前的 home 目錄（可能被測試 monkeypatch）

    Returns:
        glob pattern 字串，例如 "<home>/.claude/projects/*/memory"
    """
    segments = layout["path_segments"]
    return os.path.join(home, *segments)


def get_layout_parent_glob_pattern(layout: Dict[str, object], home: str) -> str:  # i18n-exempt
    """回傳指定 layout 去掉最後一段的 glob pattern。

    用途：檢查「比該 layout 對應的 memory 子目錄更外層一段是否存在」，
    例如 CURRENT_LAYOUT 去掉 "memory" 只留 `<home>/.claude/projects/*`，
    用於判斷 CC 的專案目錄機制本身是否已建立（而非該專案的 memory
    子目錄本身是否存在，兩者是不同粒度的存在性檢查）。

    Args:
        layout: MEMORY_LAYOUTS 中的一個元素
        home: 呼叫端當前的 home 目錄

    Returns:
        glob pattern 字串
    """
    segments = layout["path_segments"][:-1]
    return os.path.join(home, *segments)


def get_layout_identifier(layout: Dict[str, object], matched_path: str) -> str:  # i18n-exempt
    """依 layout 的 path_segments 中 `*` 的位置，從命中路徑推導識別符。

    `*` 若是最後一段（如 legacy 的 `auto-memory/*`），識別符就是
    `os.path.basename(matched_path)`；`*` 後面若還有 N 段（如 current 的
    `.claude/projects/*/memory`，`*` 後面還有 1 段 `memory`），須先
    `os.path.dirname()` 上溯 N 層再取 basename。這條規則取代消費端原本
    手寫的 `basename(x)` / `basename(dirname(x))`，識別符位在路徑第幾段
    是純結構資訊，由 path_segments 推導而非另外硬編碼。

    Args:
        layout: MEMORY_LAYOUTS 中的一個元素
        matched_path: glob 命中的實際路徑

    Returns:
        識別符字串（尚未正規化）
    """
    segments = layout["path_segments"]
    star_index = segments.index("*")
    levels_after_star = len(segments) - star_index - 1
    path = matched_path
    for _ in range(levels_after_star):
        path = os.path.dirname(path)
    return os.path.basename(path)
