#!/usr/bin/env python3
"""
Presence-Detection Language Profiles（language-pluggable presence hook 的設定來源）

背景（1.2.0-W1-036）：presence-detection 的三類偵測（user-facing 字串 / 裸 Color /
魔術數字）偵測模式通用，但原 dart-presence hook 的實作把 .dart 專屬的 pattern 寫死，
裸推上游會洩漏 Flutter 假設給非 Flutter 消費端。本檔把「語言專屬規則」抽成 profile，
通用引擎依副檔名選 profile；無對應副檔名 profile 時引擎 no-op（exit 0），
使非 Flutter 專案 pull 後對其 .js/.py 等檔案完全不誤觸，profile 集合可安全上游散佈。

profile schema（PresenceProfile）：
  - extensions:        本 profile 適用的副檔名（如 (".dart",)）
  - skip_patterns:     檔路徑命中即整檔跳過（生成檔 / 測試 / 設施本體 sink）
  - override_markers:  命中行或前一行含任一即豁免
  - string_detect:     user-facing 字串偵測 regex 清單（任一命中即視為命中）
  - string_exclude:    字串脈絡排除 regex（log / assert / import / 註解等開發者面）
  - color_detect:      裸顏色字面偵測 regex
  - color_exclude:     已是 theme token 引用的豁免 regex
  - magic_detect:      魔術數字字面偵測 regex
  - magic_exclude:     已集中常數的豁免 regex

任一 *_detect 為空清單時，引擎跳過該類偵測（語言不適用該類即留空）。
新增語言：在 PROFILES 內新增一個 PresenceProfile 並登記其副檔名即可，引擎無須改動。
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Pattern, Tuple


@dataclass(frozen=True)
class PresenceProfile:
    """單一語言的 presence-detection 規則集。所有 regex 在建構時預編譯。"""

    name: str
    extensions: Tuple[str, ...]
    skip_patterns: List[Pattern] = field(default_factory=list)
    override_markers: List[str] = field(default_factory=list)
    string_detect: List[Pattern] = field(default_factory=list)
    string_exclude: List[Pattern] = field(default_factory=list)
    color_detect: List[Pattern] = field(default_factory=list)
    color_exclude: List[Pattern] = field(default_factory=list)
    magic_detect: List[Pattern] = field(default_factory=list)
    magic_exclude: List[Pattern] = field(default_factory=list)


def _compile(patterns: List[str], verbose: bool = False) -> List[Pattern]:
    flags = re.VERBOSE if verbose else 0
    return [re.compile(p, flags) for p in patterns]


# ---------------------------------------------------------------------------
# dart profile —— 與原 dart-presence-detection-hook 行為 1:1 保留（既有 34 測試須全綠）
# ---------------------------------------------------------------------------

_DART = PresenceProfile(
    name="dart",
    extensions=(".dart",),
    skip_patterns=_compile([
        r"\.g\.dart$",
        r"\.freezed\.dart$",
        r"\.mocks\.dart$",
        r"\.gr\.dart$",
        r"/test/",
        r"/integration_test/",
        r"_test\.dart$",
        r"/l10n/",
        r"/generated/",
        r"ui_config\.dart$",
        r"/design_system/",
        r"flat_design_config\.dart$",
        r"flat_design_config\.dart$",
        r"responsive_config\.dart$",
        r"theme\.dart$",
        r"app_colors\.dart$",
        r"ui_colors\.dart$",
        r"ui_spacing\.dart$",
        r"ui_constants\.dart$",
        # 013/014 ANA 選定的集中化 sink 檔；常數定義本體不應被誤攔
        r"app_spacing\.dart$",
        r"app_typography\.dart$",
        r"terminal_constants\.dart$",
    ]),
    override_markers=[
        "presence-exempt",
        "i18n-exempt",
        "color-exempt",
        "magic-exempt",
        "style-exempt",
    ],
    # 含 CJK 或含空白的多字英文字串字面（單字 token 不視為 user-facing）
    string_detect=_compile([
        r"""(['"])(?=[^'"]*[一-鿿])[^'"]*\1""",
        r"""(['"])([A-Za-z][^'"]*\s+[^'"]+)\1""",
    ]),
    string_exclude=_compile([
        r"""(
            ^\s*//                |
            ^\s*/?\*              |
            ^\s*import\s          |
            ^\s*export\s          |
            ^\s*part\s            |
            ^\s*@                 |
            \blog(ger)?\.\w+      |
            \bdebugPrint\b        |
            \bprint\b             |
            \bassert\b            |
            \bthrow\s+\w*Exception|
            \bArgumentError\b     |
            \btoString\s*\(       |
            \bAppLogger\b         |
            \bKey\s*\(            |
            \bByName\b
        )""",
    ], verbose=True),
    color_detect=_compile([
        r"""(?<![A-Za-z0-9_.])(
            Color\s*\(\s*0x[0-9A-Fa-f]{6,8}\s*\)  |
            Colors\.[a-zA-Z]+
        )""",
    ], verbose=True),
    color_exclude=_compile([
        r"\b(UIColors|AppColors|Theme\.of|colorScheme|ColorScheme)\b",
    ]),
    magic_detect=_compile([
        r"""(
            SizedBox\s*\(\s*(?:height|width)\s*:\s*\d+(?:\.\d+)?      |
            EdgeInsets\.(?:all|symmetric|only|fromLTRB)\s*\([^)]*\b\d+(?:\.\d+)?\b |
            \bfontSize\s*:\s*\d+(?:\.\d+)?                           |
            BorderRadius\.circular\s*\(\s*\d+(?:\.\d+)?\s*\)         |
            Duration\s*\(\s*\w+\s*:\s*\d+\s*\)
        )""",
    ], verbose=True),
    magic_exclude=_compile([
        r"\b(UISpacing|UIFontSizes|UIBorderRadius|UIDurations|AppDimens)\b",
    ]),
)


# ---------------------------------------------------------------------------
# python profile —— 第 2 個 profile，證明引擎可擴充（最小可用版）
# ---------------------------------------------------------------------------
#
# 設計取捨：Python 無顏色概念，故 color_detect 留空（引擎自動跳過該類）。
# 僅示範 user-facing 字串（含 CJK）與魔術數字兩類，並排除 log / 註解 / docstring 等
# 開發者面脈絡。本 profile 為 stub，意在證明「新語言只需新增 profile、引擎不動」，
# 落地正式偵測規則時可再擴充 pattern。
#
# 重要（1.2.0-W1-036 dogfooding 發現）：framework 自身的 .py（hooks / skills / config）
# 內含大量開發者面 CJK 字串字面（block 訊息組裝、log 文案），這些非 user-facing i18n
# 候選。若 stub profile 對其生效會在編輯框架 hook 時誤觸 deny（88+ 檔受影響），癱瘓
# 框架開發。故將框架 Python 來源目錄納入 skip_patterns——stub 仍由 unit test 直接驗證
# 偵測邏輯（證可擴充），但對 host 專案的框架 .py 不誤觸。落地正式 application 層 .py
# 偵測時，application 程式碼路徑不在此 skip 範圍內，仍會生效。
_PYTHON = PresenceProfile(
    name="python",
    extensions=(".py",),
    skip_patterns=_compile([
        r"/tests?/",
        r"_test\.py$",
        r"test_.*\.py$",
        r"/migrations/",
        r"conftest\.py$",
        # framework 自身 Python 來源（開發者面字串，非 application user-facing）
        r"/\.claude/hooks/",
        r"/\.claude/skills/",
        r"/\.claude/config/",
        r"^\.claude/hooks/",
        r"^\.claude/skills/",
        r"^\.claude/config/",
    ]),
    override_markers=[
        "presence-exempt",
        "i18n-exempt",
        "magic-exempt",
    ],
    # 含 CJK 的字串字面（Python user-facing 文案通常為中文文案）
    string_detect=_compile([
        r"""(['"])(?=[^'"]*[一-鿿])[^'"]*\1""",
    ]),
    string_exclude=_compile([
        r"""(
            ^\s*\#                |   # 行註解
            ^\s*import\s          |
            ^\s*from\s            |
            \blog(ger)?\.\w+      |
            \bprint\s*\(          |
            \bassert\b            |
            \braise\s+\w*Error    |
            \braise\s+\w*Exception
        )""",
    ], verbose=True),
    # Python 無原生顏色概念
    color_detect=[],
    color_exclude=[],
    # 魔術數字：sleep / timeout 等帶裸數字（stub 示範）
    magic_detect=_compile([
        r"""(
            \btime\.sleep\s*\(\s*\d+(?:\.\d+)?\s*\)  |
            \btimeout\s*=\s*\d+(?:\.\d+)?
        )""",
    ], verbose=True),
    magic_exclude=_compile([
        r"\b(TIMEOUT|SLEEP|DELAY|INTERVAL)_?\w*\b",  # 已具名常數
    ]),
)


# ---------------------------------------------------------------------------
# Profile registry —— 副檔名 → profile
# ---------------------------------------------------------------------------

PROFILES: Tuple[PresenceProfile, ...] = (_DART, _PYTHON)

_BY_EXTENSION: Dict[str, PresenceProfile] = {
    ext: profile for profile in PROFILES for ext in profile.extensions
}


def get_profile_for_path(file_path: str):
    """
    依副檔名選 profile。無對應副檔名 → 回傳 None（引擎據此 no-op）。

    這是安全上游的關鍵：非 Flutter 專案的 .js / .ts / .go 等檔案無對應 profile，
    引擎拿到 None 即 exit 0，不誤觸。
    """
    for ext, profile in _BY_EXTENSION.items():
        if file_path.endswith(ext):
            return profile
    return None
