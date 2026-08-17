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
  - string_detect:     user-facing 字串「內容層級」偵測 regex 清單（任一命中即
                        視為命中；比對對象是引擎 token 化後去除引號的字面內容，
                        非含引號的整行，見 presence-detection-hook.py）
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
    # 含 CJK 或含空白的多字英文字串字面（單字 token 不視為 user-facing）。
    #
    # 字面內容層級 predicate（不含引號、無 backreference）：引擎先以固定的
    # quote-token 化 regex 依序（非重疊）枚舉字面，再對每個字面的內容套用
    # 以下 pattern（presence-detection-hook.py 的 _content_detect_matches）。
    # 舊版直接對「含引號整行」套 lookahead regex，會讓不含目標內容的字面被
    # 跳過後，其結束引號與下一個字面的起始引號重新配對，把兩字面之間的文字
    # 誤判為字面內容——修正後兩者的職責分離：token 化（quote 語法，語言通用）
    # 留在引擎；「怎樣的內容算 user-facing」（CJK / 多字英文句）才是語言專屬
    # 規則，留在 profile。
    string_detect=_compile([
        r"[一-鿿]",
        r"^[A-Za-z][^\n]*\s+\S",
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
# 僅示範 user-facing 字串（含 CJK）與魔術數字兩類，並排除 log / 註解等開發者
# 面脈絡。本 profile 為 stub，意在證明「新語言只需新增 profile、引擎不動」，
# 落地正式偵測規則時可再擴充 pattern。
#
# docstring 涵蓋範圍（引擎逐行掃描無跨行狀態，line-level 規則能力上限）：
#   - 涵蓋：單行完整三引號 docstring（如 `    """說明"""`）——string_exclude
#     對「行首（容前導空白）緊接 `"""` / `'''`」的行豁免。行首錨定是刻意
#     設計，不可放寬為「任一位置含三引號」，理由見下一項。
#   - 天生安全（非本清單排除，是 token 化偵測的副作用）：多行 docstring 的
#     起始/結束行（僅含未配對的三引號標記）與純文字中間行（不含任何引號
#     字元）——引擎只對「引號配對內的內容」做 CJK 判斷，這兩種行本就不會
#     產生可判斷的字面 token。
#   - 正確偵測、非豁免範圍：三引號賦值給變數的 user-facing 長文案（如
#     `msg = """請輸入帳號"""`，Python 撰寫多行提示文字的常見形態）。若
#     docstring 排除改用「任一位置含三引號」的寬鬆樣式，這類賦值行的三引號
#     也會誤觸豁免，造成偽陰性——行首錨定利用「賦值行的三引號前有 `msg = `
#     等內容」精確排除此類誤豁免，故仍會被 string_detect 判定為 CJK 字面。
#   - 已知涵蓋範圍限制：多行 docstring 的中間行若本身含成對引號（如說明文字
#     引用了 "某字串"），仍會被誤判為獨立字串字面——line-level 規則無法得知
#     該行實際位於 docstring 內部。此限制的行為快照見
#     test_python_profile_multiline_docstring_middle_line_with_quotes_known_limitation。
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
        r"/\.claude/lib/",
        r"/\.claude/scripts/",
        r"^\.claude/hooks/",
        r"^\.claude/skills/",
        r"^\.claude/config/",
        r"^\.claude/lib/",
        r"^\.claude/scripts/",
    ]),
    override_markers=[
        "presence-exempt",
        "i18n-exempt",
        "magic-exempt",
    ],
    # 含 CJK 的字串字面（Python user-facing 文案通常為中文文案）。
    # 字面內容層級 predicate，與 _DART.string_detect 同機制，見該處說明。
    string_detect=_compile([
        r"[一-鿿]",
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
        # 三引號 docstring 標記：行首錨定（容前導空白後緊接三引號）才豁免。
        # 不可用「任一位置含三引號」（此為修正前的初版寫法），會連帶豁免
        # `msg = """請輸入帳號"""` 這類三引號賦值給變數的 user-facing 長文案
        # （Python 撰寫多行提示文字的常見形態），造成偽陰性——行首錨定收斂
        # 後，賦值行的三引號前有 `msg = ` 等內容，不會命中此樣式。
        r'^\s*"""',  # 雙引號形式
        r"^\s*'''",  # 單引號形式
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
