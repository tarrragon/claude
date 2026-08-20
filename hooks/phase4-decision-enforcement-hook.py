#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
Phase 4 Decision Enforcement Hook - PC-093 YAGNI 累積防護

功能：Phase 4 階段強制決斷閘門。掃描 ticket md 中的延後話術（「Phase X 再決定」
「之後再說」「保留以防萬一」等），命中 MUST-block 等級時阻擋，要求 PM 做出
「執行 / 移除 / 豁免」三選一決策。

Hook 類型：
- PostToolUse (Bash): 主觸發，匹配 `ticket track phase <id> phase4`
- PreToolUse (Bash): 輔助觸發，匹配 `ticket track complete <id>`（殘留二次掃描）

分級：
- MUST-block（M1-M3）：Exit 2，stderr 阻擋
- WARN（W1-W3）：Exit 0，stdout 警告
- INFO（I1-I2）：Exit 0，stdout 提醒

豁免語法：
  <!-- PC-093-exempt: <category>:<reason> -->
  於命中 phrase 同行或前 1 行內生效。
  category: tdd-transition | baseline-gated | ticket-tracked | user-override | rule-quote | history
  reason: ≥10 字元；baseline-gated 需含數字；ticket-tracked / history 需含 ticket id；
          rule-quote 需含 .claude/rules/ 或 .claude/pm-rules/ 路徑

Ticket: 0.18.0-W10-082
Pattern: PC-093
"""

import re
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 加入 hooks/ 到 sys.path 以便 import hook_utils package
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib import (  # noqa: E402
    setup_hook_logging,
    run_hook_safely,
    read_json_from_stdin,
    get_effort_level,
    extract_tool_input,
    find_ticket_file,
    emit_hook_output,
)
from lib.git_command_parse import (  # noqa: E402
    strip_heredoc_bodies,
    normalize_newlines_to_separators,
)
from lib.ticket_id_pattern import BARE_START_BOUNDED_RE  # noqa: E402


# ============================================================================
# 常數定義
# ============================================================================

EXEMPT_CATEGORIES = frozenset({
    "tdd-transition",
    "baseline-gated",
    "ticket-tracked",
    "user-override",
    "rule-quote",
    "history",
})

REASON_MIN_LEN = 10

# Ticket ID 通用格式：W{wave}-{seq}（SSOT：lib.ticket_id_pattern.BARE_START_BOUNDED_RE）
TICKET_ID_PATTERN = BARE_START_BOUNDED_RE

# Rule-quote 類別：reason 必須含 .claude/rules/ 或 .claude/pm-rules/ 路徑
# 用途：PM 在 acceptance / Solution 引用規則名稱（如「禁止 Phase 5 再決定」）時豁免
RULE_PATH_PATTERN = re.compile(r"\.claude/(?:rules|pm-rules)/")

# 觸發命令偵測：語句內 token 需依序相鄰命中，見 extract_ticket_id_from_command
# （原為對整條命令字串的 regex.search，heredoc/引號 payload 內文含觸發字樣
# 會被誤判為真實呼叫，已改為 token 化後的相鄰比對，見「payload 誤判修正」段）
_STATEMENT_SEPARATORS = frozenset({"&&", "||", ";", "|", "(", ")"})

# 豁免 marker 解析（大小寫敏感，EX-N7）
EXEMPT_MARKER = re.compile(
    r"<!--\s*PC-093-exempt\s*:\s*([^:]+?)\s*:\s*(.+?)\s*-->"
)

# 豁免 marker 剔除（掃描 phrase 前移除，避免 marker 內含 phrase 誤判）
EXEMPT_MARKER_STRIP = re.compile(r"<!--\s*PC-093-exempt[^>]*-->")

# Context Bundle 自動抽取的 [ref] 行豁免（W10-127）：
# ticket-loader 抽取 source ticket 的 acceptance / rationale 時，會將每行加上
# `[ref]` 前綴標記。這些行是「引用其他 ticket 的內容」，不是本 ticket 的延後
# 決策。常見模式：
#   - [ref] [ ] Phase 4 評估結論明確（無需重構 / ...，禁止 Phase 5 再決定）
# 屬於 PC-142 case 4 漏網案例（W10-122 rule-quote 豁免未涵蓋 ref 行模式）。
# 行級豁免（trim 後以 `- [ref]` 或 `[ref]` 開頭）— 採方向 A：簡單精準。
REF_LINE_PATTERN = re.compile(r"^\s*-?\s*\[ref\]")

# W10-130: Schema placeholder template 區塊起點。
# Ticket body schema 採 `<!-- Schema[<type>/<section>]: <note> -->` 標記。
# 該區塊內的 `<!-- PC-093-exempt: cat:reason -->` 屬範例文字（template note 內
# 示意 marker 格式），非實際豁免宣告。應整段跳過 phrase 掃描與 marker 蒐集。
SCHEMA_PLACEHOLDER_START = re.compile(r"<!--\s*Schema\[[^\]]+\]\s*:")
# 區塊邊界：下個 H2（## ）或 `---` 水平分隔符（trim 後完全相符）。
SCHEMA_PLACEHOLDER_END_H2 = re.compile(r"^\s*##\s")
SCHEMA_PLACEHOLDER_END_HR = re.compile(r"^\s*---\s*$")

# W1-120: Context Bundle auto-extracted 區塊起點。
# ticket-loader 抽取 source ticket 的 what / why 寫入 `## Context Bundle` 時，
# 以 `<!-- auto-extracted: v1 | sources: ... -->` marker 標記為機器產生的結構化
# 元資料（逐字引用 source ticket why / what）。該區塊與 frontmatter 同類——非
# 人類撰寫的決策論述，其中的「Phase 4 評估」「Phase 5 再決定」等字面屬 source
# ticket history 引用，不應被誤判為本 ticket 延後決策（PC-142 case 5 同根因，
# W1-092 frontmatter 修復的延伸）。
# 錨定 marker 而非整個 section：人工撰寫的 Context Bundle（無 marker）仍應被攔截。
# 區塊終點複用 SCHEMA_PLACEHOLDER_END_H2 / SCHEMA_PLACEHOLDER_END_HR。
CONTEXT_BUNDLE_START = re.compile(r"<!--\s*auto-extracted\s*:")

# W11-018: Fenced code block 範例語境豁免
# Markdown fenced code block 內的延後話術與 PC-093-exempt marker 屬「範例展示」，
# 非實際延後決策或豁免宣告。整段跳過 phrase 掃描與 marker 蒐集。
# 規則：採 CommonMark 0.31 fenced code block 子集
# - 起始 fence: 行首 0-3 空格 indent + 3+ 連續 backtick 或 3+ 連續 tilde
# - 結束 fence: 同字元 + 長度 >= 起始 + 行內僅尾部空白
# - 未閉合 fence: 視為至檔尾（容錯）
# - 不支援 indented fence（indent >= 4 空格 / Tab=4）與 nested fence
FENCED_BLOCK_START_PATTERN = re.compile(
    r"^(?P<indent> {0,3})(?P<fence>`{3,}|~{3,})(?P<info>.*)$"
)
FENCED_BLOCK_CLOSE_PATTERN = re.compile(
    r"^(?P<indent> {0,3})(?P<fence>`{3,}|~{3,})\s*$"
)

# 「## Spawn Requests」區段內已 resolved 條目的結構化欄位豁免。
# 該區段全數由 add-spawn-request / resolve-spawn-request 兩個 CLI 指令
# 產生，非使用者於 Phase 4 當下自由撰寫的決策 prose；一旦條目已
# processed/dismissed，其中的階段字面是「建立當下的分析記錄」而非待辦，
# 與 frontmatter / Context Bundle 既有豁免同精神。pending 條目維持掃描
# （見 compute_resolved_spawn_request_lines docstring）。
SPAWN_REQUESTS_SECTION_START = re.compile(r"^##\s+Spawn Requests\s*$")
SPAWN_REQUEST_ENTRY_START = re.compile(r"^-\s+\*\*SR-\d+\*\*")
SPAWN_REQUEST_STATUS_LINE = re.compile(r"^\s*-\s*status:\s*(processed|dismissed|pending)\b")
RESOLVED_SPAWN_REQUEST_STATUSES = frozenset({"processed", "dismissed"})

# 豁免 proximity（marker 同行或前 1 行生效）
EXEMPT_PROXIMITY_LINES = 1

# 檔級豁免（PC-099 meta-ticket 自我引用）：
#   此 hook 的識別名稱。當 ticket frontmatter 包含
#     hook_self_reference: phase4-decision-enforcement
#   或 list 形式含此值時，整檔豁免偵測（hook 自身設計/測試/實作 ticket）。
SELF_REFERENCE_HOOK_ID = "phase4-decision-enforcement"

# Exempt marker 驗證失敗的人類可讀訊息對照表（W17-085 / quality-baseline 規則 4）
# 每項 = (humanized 描述, 修復範例/提示)；保留 err code 作 grep 訊號（向後相容）
ERR_MESSAGE_MAP: Dict[str, Tuple[str, str]] = {
    "format-error": (
        "Exempt marker 格式錯誤（需 <!-- PC-093-exempt: 類別:理由 -->）",
        "範例：<!-- PC-093-exempt: ticket-tracked:W17-085 hook 訊息改善 -->",
    ),
    "category-whitelist": (
        "Exempt category 不在白名單",
        "合法 category: " + ", ".join(sorted(EXEMPT_CATEGORIES)),
    ),
    "reason-too-short": (
        "Exempt reason 太短（< {} 字元）".format(REASON_MIN_LEN),
        "請補充足夠的延後理由說明（至少 {} 字元）".format(REASON_MIN_LEN),
    ),
    "baseline-need-number": (
        "baseline-gated 類別的 reason 必須含數字（量化基線）",
        "範例：<!-- PC-093-exempt: baseline-gated:測量結果 84ms，低於 100ms AC 故無需快取 -->",
    ),
    "ticket-tracked-need-id": (
        "ticket-tracked 類別的 reason 必須含 W{wave}-{seq} 格式 ticket ID",
        "範例：<!-- PC-093-exempt: ticket-tracked:W17-085 hook 訊息改善 -->",
    ),
    "rule-quote-need-path": (
        "rule-quote 類別的 reason 必須含規則檔案路徑（.claude/rules/ 或 .claude/pm-rules/）",
        "範例：<!-- PC-093-exempt: rule-quote:引用 .claude/rules/core/decision-trigger-binding.md 規則 1.5 -->",
    ),
    "history-need-anchor": (
        "history 類別的 reason 必須含 W{wave}-{seq} 格式 ticket ID 作歷史錨點",
        "範例：<!-- PC-093-exempt: history:本段引用 parent W11-004.7 多視角審查發現作動機脈絡 -->",
    ),
}


# ============================================================================
# 資料結構
# ============================================================================

@dataclass
class PhraseRule:
    id: str          # M1|M2|M3|W1|W2|W3|I1|I2
    level: str       # BLOCK|WARN|INFO
    pattern: re.Pattern
    rationale: str


@dataclass
class Hit:
    line_no: int
    rule_id: str
    level: str
    text: str


@dataclass
class ExemptMarker:
    category: str
    reason: str


@dataclass
class ExemptRef:
    line_no: int
    marker: Optional[ExemptMarker]
    valid: bool
    err: Optional[str] = None


# ============================================================================
# F1: Regex 表構建
# ============================================================================

def build_regex_table() -> List[PhraseRule]:
    """構建 3 級 regex 表（8 條：M×3 / W×3 / I×2）。

    依 Phase 1 §1 設計。IGNORECASE + MULTILINE。
    """
    flags = re.IGNORECASE | re.MULTILINE
    return [
        # M1: Phase X 再決定（遞迴推給未來 phase）
        # 「評估」單獨要求前接「再|在」才觸發（W2-017：「Phase 4 重構評估」是
        # 標準章節名非延後話術，但「Phase 5 再評估」仍需攔截）。
        #
        # 雙分支設計（修正單分支「收逗號」方案的回歸）：
        # 分支一（同子句，前綴可選）：「Phase N」與判定動詞之間排除逗號，
        #   兩者須落在同一子句，前綴「再/在」可有可無——涵蓋「Phase 5 視
        #   baseline 決定」這類語法直接相連、無需前綴即可判定為關於
        #   Phase N 決策的句型。
        # 分支二（可跨子句，前綴必須）：「Phase N」與判定動詞之間允許
        #   跨逗號，但判定動詞強制要求「再/在」前綴——涵蓋「Phase 4
        #   完成後，再決定是否重構」這類語意上仍屬同一延後單元、但用
        #   逗號分句的句型；前綴強制是關鍵，用以排除「於 Phase 4 審查
        #   初稿時建立，後因判斷應直接執行」這類過去完成式敘述（判定
        #   動詞前無「再/在」、描述的是另一件已完成的事）。
        # 兩分支為 OR 關係：僅有分支一（收窄跨子句比對）會連帶排除分支
        # 二該涵蓋的「跨逗號但有前綴」真延後話術（已實測發現的回歸）。
        # 反過來，單純移除逗號排除、把前綴改為全域強制，會使分支一涵蓋
        # 的「Phase 5 視 baseline 決定」漏攔（已實測驗證，見 ticket
        # Problem Analysis），故不採任一單分支設計。
        PhraseRule(
            id="M1",
            level="BLOCK",
            pattern=re.compile(
                r"Phase\s*[0-9]+(?:"
                r"[^\n，,]{0,30}?(?:(?:再|在)?(?:決定|決斷|判斷)|(?:再|在)評估)"
                r"|"
                r"[^\n]{0,30}?(?:再|在)(?:決定|決斷|判斷|評估)"
                r")",
                flags,
            ),
            rationale="遞迴推給未來 phase，PC-093 核心反模式",
        ),
        # M2: 之後/以後 再決定（無時間錨點）
        PhraseRule(
            id="M2",
            level="BLOCK",
            pattern=re.compile(
                r"(?:之後|以後|日後|未來)\s*(?:再|才)?(?:決定|決斷|說|考慮|處理)",
                flags,
            ),
            rationale="無時間錨點＝永久延後",
        ),
        # M3: 保留以防萬一（「不用」偽裝為「保留」）
        PhraseRule(
            id="M3",
            level="BLOCK",
            pattern=re.compile(
                r"保留[^\n]{0,20}?(?:以防萬一|以備不時之需|彈性|擴展性|擴充性)",
                flags,
            ),
            rationale="將「不用」偽裝為「保留」（根因 D）",
        ),
        # W1: 視 X 結果再決定（帶條件延後）
        PhraseRule(
            id="W1",
            level="WARN",
            pattern=re.compile(
                r"視\s*.{1,30}?\s*(?:結果|情況|狀況|需求)\s*(?:再|而)?\s*(?:決定|判斷|評估)",
                flags,
            ),
            rationale="帶條件的延後，條件明確可豁免",
        ),
        # W2: 未來/以後 可能需要（預留樂觀話術）
        PhraseRule(
            id="W2",
            level="WARN",
            pattern=re.compile(
                r"(?:未來|以後)\s*(?:可能|或許|也許)\s*(?:需要|會用|要用)",
                flags,
            ),
            rationale="根因 B「預留樂觀」話術",
        ),
        # W3: 先保留再說（決策疲勞）
        PhraseRule(
            id="W3",
            level="WARN",
            pattern=re.compile(
                r"先(?:保留|留著|不動)\s*(?:再說|吧)?",
                flags,
            ),
            rationale="根因 C「決策疲勞」口語",
        ),
        # I1: TBD/TODO/FIXME 延後標記
        PhraseRule(
            id="I1",
            level="INFO",
            pattern=re.compile(
                r"(?:TBD|TODO|FIXME)\s*[:：]?\s*(?:Phase\s*[0-9]+|之後|未來)",
                flags,
            ),
            rationale="標記式延後，若有後續 ticket 可豁免",
        ),
        # I2: 擴展彈性/擴充介面（PC-093 偽裝詞）
        PhraseRule(
            id="I2",
            level="INFO",
            pattern=re.compile(
                r"(?:擴展|擴充)\s*(?:彈性|空間|介面)",
                flags,
            ),
            rationale="PC-093 偽裝詞前綴",
        ),
    ]


# ============================================================================
# F2: 逐行掃描 phrase
# ============================================================================

def compute_frontmatter_lines(lines: List[str]) -> set:
    """W1-092: 計算 YAML frontmatter 區塊的 1-based 行號集合（含起訖 `---` 行）。

    Frontmatter 定義（採嚴格規則，PM WRAP P 防護）：
    - 必須由「檔案第一行」起始（trim 後完全等於 `---`）
    - 結束於下一個「行首僅有 `---` 三字元的行」（trim 後完全等於 `---`）
    - 起訖 fence 自身行屬 frontmatter 範圍
    - 未閉合（檔案無第二個 `---`）→ 視為無 frontmatter，回傳空集合（容錯）
    - 第一行非 `---` → 視為無 frontmatter，回傳空集合

    Why: ticket md frontmatter 為結構化元資料（YAML），其 why/title/strategy 等
    欄位可能含「Phase 4 評估」「Phase 5 再決定」等歷史引用字面，屬於 source
    ticket history 引用而非本 ticket 延後決策論述，與 W10-130 Schema placeholder
    + W11-018 fenced code block 同精神整段跳過。

    邊界匹配限「行首僅有 `---` 三字元」避免內文 `---` 水平分隔符誤判結束。
    """
    if not lines or lines[0].strip() != "---":
        return set()
    frontmatter_lines: set = {1}
    for idx in range(2, len(lines) + 1):
        frontmatter_lines.add(idx)
        if lines[idx - 1].strip() == "---":
            return frontmatter_lines
    # 未閉合：視為無 frontmatter（容錯，避免整檔被跳過）
    return set()


def compute_schema_placeholder_lines(lines: List[str]) -> set:
    """W10-130: 計算 Schema placeholder template 區塊的 1-based 行號集合。

    起點：含 `<!-- Schema[<type>/<section>]: ... -->` 的行（含該行）。
    終點：下個 H2（`## `）或 `---` 水平分隔符（不含該邊界行）。

    回傳：所有屬於 placeholder 區塊的行號集合。phrase 掃描與 marker 蒐集均跳過。
    """
    placeholder_lines: set = set()
    in_block = False
    for idx, raw in enumerate(lines, start=1):
        if in_block:
            if SCHEMA_PLACEHOLDER_END_H2.match(raw) or SCHEMA_PLACEHOLDER_END_HR.match(raw):
                in_block = False
                # 邊界行不屬 placeholder
                continue
            placeholder_lines.add(idx)
            # 同一行可能再次出現 Schema 標記（連續 placeholder），仍視為 in_block
            continue
        if SCHEMA_PLACEHOLDER_START.search(raw):
            in_block = True
            placeholder_lines.add(idx)
    return placeholder_lines


def compute_context_bundle_lines(lines: List[str]) -> set:
    """W1-120: 計算 Context Bundle auto-extracted 區塊的 1-based 行號集合。

    起點：含 `<!-- auto-extracted: ... -->` marker 的行（含該行）。
    終點：下個 H2（`## `）或 `---` 水平分隔符（不含該邊界行）。

    Why: `## Context Bundle` 區塊由 ticket-loader 自動抽取，逐字引用 source
    ticket 的 why / what，屬機器產生的結構化元資料（與 frontmatter 同類）。其中
    階段名稱字面屬 source ticket history 引用而非本 ticket 延後決策，與 W1-092
    frontmatter + W10-130 Schema placeholder + W11-018 fenced code block 同精神
    整段跳過。

    邊界：錨定 auto-extracted marker（非整個 section）。人工撰寫的 Context
    Bundle（無 marker）不跳過——人工延後論述仍應被攔截。

    注意：H3（`### `）不被誤判為終點——`^\\s*##\\s` 要求第三字元為空白，`### `
    第三字元為 `#`，天然不匹配。

    回傳：所有屬於 auto-extracted 區塊的行號集合。phrase 掃描與 marker 蒐集均跳過。
    """
    bundle_lines: set = set()
    in_block = False
    for idx, raw in enumerate(lines, start=1):
        if in_block:
            if SCHEMA_PLACEHOLDER_END_H2.match(raw) or SCHEMA_PLACEHOLDER_END_HR.match(raw):
                in_block = False
                # 邊界行不屬 bundle
                continue
            bundle_lines.add(idx)
            continue
        if CONTEXT_BUNDLE_START.search(raw):
            in_block = True
            bundle_lines.add(idx)
    return bundle_lines


def compute_fenced_block_lines(lines: List[str]) -> set:
    """W11-018: 計算 fenced code block 內的 1-based 行號集合（含 fence 自身行）。

    規則（CommonMark 0.31 子集）：
    - FENCE-1: 起始 fence = 行首 0-3 空格 + 3+ 連續 backtick 或 tilde
    - FENCE-2: 結束 fence = 同字元 + 長度 >= 起始 + 行內僅尾部空白
    - FENCE-3: info string（language hint）不影響邊界
    - FENCE-4: fence 起始與結束行自身屬區塊範圍
    - FENCE-5: 未閉合 fence 視為至檔尾（容錯）
    - FENCE-6: indent >= 4 空格不啟用（Tab 視為 4 空格）
    - FENCE-7: 不支援 nested fence；內層字元數 < 外層起始長度則視為內容

    單次線性掃描 O(n)；in_block 期間先 add 後判 close（保 FENCE-4）。
    """
    def _visual_indent(text: str) -> int:
        """Tab 視為 4 空格（EDGE-8 / CommonMark）。"""
        width = 0
        for ch in text:
            if ch == "\t":
                width += 4
            elif ch == " ":
                width += 1
            else:
                break
        return width

    fenced_lines: set = set()
    in_block = False
    open_char: Optional[str] = None
    open_len = 0

    for idx, raw in enumerate(lines, start=1):
        if not in_block:
            # 先檢查 leading Tab / 大量空白（visual indent >= 4 不視為 fence）
            # 取出 raw 開頭非空白前的部分，計算 visual width
            leading = raw[: len(raw) - len(raw.lstrip(" \t"))]
            if "\t" in leading and _visual_indent(leading) > 3:
                continue
            m = FENCED_BLOCK_START_PATTERN.match(raw)
            if not m:
                continue
            # FENCE-6: indent ≤ 3 才視為 fence（regex 已限制 ≤ 3 純空格；Tab 已上方排除）
            fence = m.group("fence")
            info = m.group("info") or ""
            # backtick fence 的 info string 不可含 backtick（CommonMark）
            if fence[0] == "`" and "`" in info:
                continue
            in_block = True
            open_char = fence[0]
            open_len = len(fence)
            fenced_lines.add(idx)
        else:
            # 已在區塊中：先加入再判 close（FENCE-4）
            fenced_lines.add(idx)
            cm = FENCED_BLOCK_CLOSE_PATTERN.match(raw)
            if cm:
                cfence = cm.group("fence")
                if cfence[0] == open_char and len(cfence) >= open_len:
                    in_block = False
                    open_char = None
                    open_len = 0
    # FENCE-5: 未閉合 fence — 因迴圈內 in_block 期間每行已 add，自然涵蓋至檔尾
    return fenced_lines


def compute_resolved_spawn_request_lines(lines: List[str]) -> set:
    """計算「## Spawn Requests」區段中，已 resolved（processed/dismissed）
    之 spawn request 條目的 1-based 行號集合。

    起訖規則同 Schema placeholder / Context Bundle：從 `## Spawn Requests`
    標題後一行起算，至下個 H2 或 `---` 為止。區段內以 `- **SR-N**` 起始
    行界定各條目邊界，逐條目掃描其 `- status:` 欄位；命中 processed 或
    dismissed 才把整條目（含 SR 標題行）納入回傳集合，pending 條目維持
    掃描——尚未處理的 spawn request 仍是待辦，PC-093 必須繼續攔截其中的
    延後話術，否則使用者可把延後話術寫進未 resolved 的 spawn request
    規避本 hook（防止開新漏洞優先於消除誤報）。

    Why：本區段全數由 add-spawn-request / resolve-spawn-request 兩個 CLI
    指令產生的結構化欄位（what/why/suggested_type/suggested_priority/
    related_files/context/status），不是使用者於 Phase 4 當下自由撰寫的
    決策 prose。resolve-spawn-request 執行完畢即代表該分析已有結論（要嘛
    確實建了對應 ticket，要嘛評估後不建），其中的階段字面（如「留待後續
    評估」）此時已是「建立當下的分析記錄」而非現在仍待決的事項，與
    frontmatter / Context Bundle auto-extracted 兩處既有豁免同一精神——
    結構化、機器可驗證來源的歷史記錄不應被當成使用者當下的延後決策。
    """
    section_lines: set = set()
    in_section = False
    for idx, raw in enumerate(lines, start=1):
        if in_section:
            if SCHEMA_PLACEHOLDER_END_H2.match(raw) or SCHEMA_PLACEHOLDER_END_HR.match(raw):
                break
            section_lines.add(idx)
            continue
        if SPAWN_REQUESTS_SECTION_START.match(raw.rstrip()):
            in_section = True

    if not section_lines:
        return set()

    ordered = sorted(section_lines)
    entry_starts = [i for i in ordered if SPAWN_REQUEST_ENTRY_START.match(lines[i - 1])]
    if not entry_starts:
        return set()

    resolved_lines: set = set()
    for pos, start in enumerate(entry_starts):
        end = entry_starts[pos + 1] - 1 if pos + 1 < len(entry_starts) else ordered[-1]
        entry_range = range(start, end + 1)
        status: Optional[str] = None
        for i in entry_range:
            m = SPAWN_REQUEST_STATUS_LINE.match(lines[i - 1])
            if m:
                status = m.group(1)
                break
        if status in RESOLVED_SPAWN_REQUEST_STATUSES:
            resolved_lines.update(entry_range)
    return resolved_lines


def scan_lines_for_phrases(
    lines: List[str],
    table: List[PhraseRule],
) -> List[Hit]:
    """逐行掃描命中。

    - 掃前移除 EXEMPT_MARKER_STRIP 避 marker 內含 phrase 誤判。
    - 同行可多規則命中，不去重；豁免狀態由 F7 處理。
    - W10-130: Schema placeholder template 區塊整段跳過。
    """
    fenced_lines = compute_fenced_block_lines(lines)
    placeholder_lines = compute_schema_placeholder_lines(lines)
    frontmatter_lines = compute_frontmatter_lines(lines)
    context_bundle_lines = compute_context_bundle_lines(lines)
    resolved_spawn_lines = compute_resolved_spawn_request_lines(lines)
    hits: List[Hit] = []
    for idx, raw in enumerate(lines, start=1):
        # W1-092: Frontmatter (YAML 區塊) 跳過 (source ticket history 引用等結構化元資料)
        if idx in frontmatter_lines:
            continue
        # W1-120: Context Bundle auto-extracted 區塊跳過（機器逐字引用 source ticket why/what）
        if idx in context_bundle_lines:
            continue
        # 已 resolved 的 Spawn Request 條目跳過（CLI 產出結構化欄位，非
        # 使用者當下延後決策，見 compute_resolved_spawn_request_lines）
        if idx in resolved_spawn_lines:
            continue
        # W11-018: Fenced code block 範例語境豁免（行級 short-circuit，最先檢查）
        if idx in fenced_lines:
            continue
        # W10-130: Schema placeholder template 區塊跳過（範例文字非實際內容）
        if idx in placeholder_lines:
            continue
        # W10-127: Context Bundle 自動抽取的 [ref] 行豁免（行級 short-circuit）。
        # 這些行屬 source ticket 引用，非本 ticket 延後決策。
        if REF_LINE_PATTERN.match(raw):
            continue
        stripped = EXEMPT_MARKER_STRIP.sub("", raw)
        for rule in table:
            for match in rule.pattern.finditer(stripped):
                hits.append(
                    Hit(
                        line_no=idx,
                        rule_id=rule.id,
                        level=rule.level,
                        text=match.group(),
                    )
                )
    return hits


# ============================================================================
# F3 + F4: 豁免解析 + 驗證
# ============================================================================

def parse_exempt_marker(text: str) -> Optional[ExemptMarker]:
    """解析 <!-- PC-093-exempt: cat:reason --> 格式。

    大小寫敏感（EX-N7）；空格寬鬆（EX-N6）；純文字非 HTML comment 不匹配（EX-N8）。
    """
    m = EXEMPT_MARKER.search(text)
    if not m:
        return None
    return ExemptMarker(category=m.group(1).strip(), reason=m.group(2).strip())


def validate_exempt_fields(marker: ExemptMarker) -> Tuple[bool, Optional[str]]:
    """驗證 category 白名單 + reason 規則。

    Returns (is_valid, err_code)。
    """
    if marker.category not in EXEMPT_CATEGORIES:
        return (False, "category-whitelist")
    if len(marker.reason) < REASON_MIN_LEN:
        return (False, "reason-too-short")
    if marker.category == "baseline-gated" and not re.search(r"\d", marker.reason):
        return (False, "baseline-need-number")
    if marker.category == "ticket-tracked" and not TICKET_ID_PATTERN.search(marker.reason):
        return (False, "ticket-tracked-need-id")
    if marker.category == "rule-quote" and not RULE_PATH_PATTERN.search(marker.reason):
        return (False, "rule-quote-need-path")
    # W11-023: history 類別 reason 必須含 ticket ID 作歷史錨點，
    # 避免「歷史脈絡」變成自由文字逃生閥。語意上 history 描述「引用已完成的
    # 歷史 / 動機脈絡」（如 parent ANA 審查發現），與 ticket-tracked（等待
    # 該 ticket 完成）語意不同。
    if marker.category == "history" and not TICKET_ID_PATTERN.search(marker.reason):
        return (False, "history-need-anchor")
    return (True, None)


# ============================================================================
# F5: 掃全文蒐集 exempt markers
# ============================================================================

def collect_exempt_markers(lines: List[str]) -> List[ExemptRef]:
    """掃全文蒐集 marker 位置 + 解析結果。

    W10-130: Schema placeholder template 區塊內的 marker 屬範例文字（如
    `<!-- PC-093-exempt: cat:reason -->`），整段跳過避免誤判為 INVALID。
    """
    fenced_lines = compute_fenced_block_lines(lines)
    placeholder_lines = compute_schema_placeholder_lines(lines)
    frontmatter_lines = compute_frontmatter_lines(lines)
    context_bundle_lines = compute_context_bundle_lines(lines)
    resolved_spawn_lines = compute_resolved_spawn_request_lines(lines)
    refs: List[ExemptRef] = []
    for idx, raw in enumerate(lines, start=1):
        # W1-092: Frontmatter 內 marker 不蒐集（結構化元資料非豁免宣告載體）
        if idx in frontmatter_lines:
            continue
        # W1-120: Context Bundle auto-extracted 區塊內 marker 不蒐集（機器引用非豁免宣告載體）
        if idx in context_bundle_lines:
            continue
        # 已 resolved 的 Spawn Request 條目內 marker 不蒐集（同上，非人工
        # 豁免宣告載體；該區塊此時亦不產生 hit，本就無需豁免）
        if idx in resolved_spawn_lines:
            continue
        # W11-018: Fenced code block 範例語境豁免（範例 marker 不蒐集）
        if idx in fenced_lines:
            continue
        if idx in placeholder_lines:
            continue
        marker = parse_exempt_marker(raw)
        if marker is None:
            # 若行內含 PC-093-exempt 文字但格式不符（EX-N5/EX-N8）
            if "PC-093-exempt" in raw and "<!--" in raw:
                refs.append(
                    ExemptRef(line_no=idx, marker=None, valid=False, err="format-error")
                )
            continue
        valid, err = validate_exempt_fields(marker)
        refs.append(
            ExemptRef(line_no=idx, marker=marker, valid=valid, err=err)
        )
    return refs


# ============================================================================
# F6: 豁免距離匹配
# ============================================================================

def is_hit_exempted(hit: Hit, markers: List[ExemptRef]) -> bool:
    """判斷 hit 是否被有效豁免 marker 覆蓋。

    規則（Phase 1 §3.2）：marker 在 phrase 同行或前 1 行內生效。
    - 同行 (DIST-1)：生效
    - 前 1 行 (DIST-2)：生效
    - 前 2 行 (DIST-3)：不生效
    - 後行 (DIST-4)：不生效
    """
    for ref in markers:
        if not ref.valid:
            continue
        if ref.line_no == hit.line_no:
            return True
        if ref.line_no == hit.line_no - EXEMPT_PROXIMITY_LINES:
            return True
    return False


# ============================================================================
# F7: 四分類（blocked / warned / info / exempted）
# ============================================================================

def partition_hits(
    hits: List[Hit],
    markers: List[ExemptRef],
) -> Tuple[List[Hit], List[Hit], List[Hit], List[Hit]]:
    """依 level 與豁免狀態四分類。

    Returns (blocked, warned, info, exempted)。
    """
    blocked: List[Hit] = []
    warned: List[Hit] = []
    info: List[Hit] = []
    exempted: List[Hit] = []

    for hit in hits:
        if is_hit_exempted(hit, markers):
            exempted.append(hit)
            continue
        if hit.level == "BLOCK":
            blocked.append(hit)
        elif hit.level == "WARN":
            warned.append(hit)
        elif hit.level == "INFO":
            info.append(hit)
    return blocked, warned, info, exempted


# ============================================================================
# F7.5: 檔級豁免偵測（PC-099 meta-ticket self-reference）
# ============================================================================

def detect_hook_self_reference(content: str) -> bool:
    """偵測 ticket frontmatter 是否宣告 self-reference 豁免。

    格式（任一匹配）：
        hook_self_reference: phase4-decision-enforcement
        hook_self_reference:
          - phase4-decision-enforcement
          - other-hook

    僅解析首個 YAML frontmatter 區塊（--- ... ---）。不引入 PyYAML 相依。

    Returns True 表示整檔豁免。
    """
    if not content.startswith("---"):
        return False
    # 取 frontmatter 區塊（--- ... ---）
    end = content.find("\n---", 3)
    if end < 0:
        return False
    fm = content[3:end]
    # 單行形式：hook_self_reference: phase4-decision-enforcement
    single = re.search(
        r"^\s*hook_self_reference\s*:\s*(\S.*?)\s*$",
        fm,
        re.MULTILINE,
    )
    if single:
        value = single.group(1).strip()
        if value == SELF_REFERENCE_HOOK_ID or value == '"{}"'.format(SELF_REFERENCE_HOOK_ID) \
                or value == "'{}'".format(SELF_REFERENCE_HOOK_ID):
            return True
    # List 形式：hook_self_reference:\n  - phase4-decision-enforcement
    list_match = re.search(
        r"^\s*hook_self_reference\s*:\s*\n((?:\s*-\s*\S.*\n?)+)",
        fm,
        re.MULTILINE,
    )
    if list_match:
        items = re.findall(r"-\s*(\S+)", list_match.group(1))
        if SELF_REFERENCE_HOOK_ID in items:
            return True
    return False


# ============================================================================
# F8: 從命令萃取 ticket_id 及模式（payload 誤判修正）
# ============================================================================
#
# 原實作對整條命令字串做 regex.search，heredoc 本體或引號參數內文若恰好
# 含「ticket track complete/phase」字樣即誤判為真實呼叫——與三個 Bash git
# 守衛（bare-commit-guard-hook.py 等）曾經歷的同型缺陷。修法改為 token 化
# 後比對相鄰獨立 token，而非字串子字串搜尋：被 shlex 判定為引號內容的
# payload 天生落在單一 token 內，不會被拆成 `ticket`/`track`/`complete`
# 四個相鄰獨立 token；heredoc 本體則先以 `strip_heredoc_bodies` 剝除
# （shlex 不理解 heredoc 語法，若不先剝除，本體內文仍會被拆成獨立 token
# 而誤判，見 ticket Problem Analysis 實測記錄）。
#
# 複用 `.claude/lib/git_command_parse.py` 的 `strip_heredoc_bodies` /
# `normalize_newlines_to_separators` 兩個既有公開函式（皆為通用命令字串
# 前處理，內部無 git 專屬邏輯）。不重用該模組的 `find_git_invocations`：
# 其「識別一次呼叫」邏輯硬編寫死比對字面 `"git"`、承載前綴包裹穿透與
# 全域選項消耗等 git 專屬知識，要讓它同時服務 `ticket` CLI 需要把 anchor
# word 參數化並拆分 git 專屬邏輯，變更幅度接近重新設計該共用函式的職責
# 邊界；本處只需要「ticket track complete/phase」4-5 個 token 的位置
# 比對，維持在本 hook 內實作，不構成與既有三個 Bash git 守衛同型的
# 「重複實作 payload 剝離」問題（真正容易重複、風險最高的 heredoc 剝離
# 已重用，未重寫）。

def _tokenize_statements(command: str) -> Optional[List[List[str]]]:
    """把命令字串剝除 heredoc 本體、換行正規化後，以 shlex 保留引號語意
    tokenize，並依 shell 運算子切分為獨立語句清單。

    回傳 None 表示無法安全 tokenize（未閉合引號等）。
    """
    stripped = strip_heredoc_bodies(command)
    normalized = normalize_newlines_to_separators(stripped)
    try:
        lexer = shlex.shlex(normalized, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return None

    statements: List[List[str]] = []
    current: List[str] = []
    for tok in tokens:
        if tok in _STATEMENT_SEPARATORS:
            if current:
                statements.append(current)
            current = []
        else:
            current.append(tok)
    if current:
        statements.append(current)
    return statements


def extract_ticket_id_from_command(command: str) -> Tuple[Optional[str], Optional[str]]:
    """從 bash 命令萃取 (ticket_id, mode)。

    mode: 'main_gate' | 'residual_gate' | None

    失敗語意：命令為空、無法安全 tokenize（未閉合引號等）、或無語句匹配
    任一命令形狀時，一律回傳 (None, None)——與原 regex.search 在對應
    情境下的行為一致（原本 regex 對這些輸入同樣找不到匹配而回傳 None），
    本次修正未改變此方向（見 acceptance 6）。
    """
    if not command:
        return (None, None)

    statements = _tokenize_statements(command)
    if statements is None:
        return (None, None)

    for statement in statements:
        if (
            len(statement) >= 5
            and statement[0] == "ticket"
            and statement[1] == "track"
            and statement[2] == "phase"
            and statement[4] == "phase4"
        ):
            return (statement[3], "main_gate")
        if (
            len(statement) >= 4
            and statement[0] == "ticket"
            and statement[1] == "track"
            and statement[2] == "complete"
        ):
            return (statement[3], "residual_gate")
    return (None, None)


# ============================================================================
# F9: ticket id → md 路徑
# ============================================================================

def resolve_ticket_md_path(ticket_id: str, logger) -> Optional[Path]:
    """解析 ticket id 到 md 檔路徑（複用 hook_utils.find_ticket_file）。"""
    try:
        return find_ticket_file(ticket_id, logger=logger)
    except Exception as exc:
        logger.info("resolve_ticket_md_path 失敗: {}".format(exc))
        return None


# ============================================================================
# F10: Block 訊息組裝
# ============================================================================

def format_block_message(
    ticket_id: str,
    blocked: List[Hit],
    exempted: List[Hit],
) -> str:
    """組 §4.1 stderr block 訊息 + AUQ 骨架。

    W10-108: 訊息開頭主動提示「優先嘗試 inline 標記」+ 列出白名單完整 category 清單
    （含適用情境），引導 agent 走 inline 路徑而非字串繞過（PC-093 同精神反模式）。
    """
    lines = []
    lines.append("[PC-093 強制決斷] 偵測到延後話術，禁止遞迴延後（Phase 4 決策閘門）")
    lines.append("")
    lines.append("若命中內容是引用或示範延後話術（例如說明規則、撰寫測試案例、")
    lines.append("記錄他人 ticket 的延後語），不是本 ticket 實際要延後的決策，")
    lines.append("最省事的路徑是把該段包進 markdown code fence（本 hook 已內建")
    lines.append("此豁免，整段跳過掃描，不需逐行補 marker）：")
    lines.append("  ~~~")
    lines.append("  範例句型：Phase 4 再決定是否保留 use_cache")
    lines.append("  ~~~")
    lines.append("上方範例刻意用 ~~~ 而非 ```：若你連本訊息全文一起用 ``` 包進")
    lines.append("ticket 引用，可避免與本訊息內建的 ~~~ 範例巢狀衝突（本 hook")
    lines.append("不支援巢狀 fence，兩者相同字元會使外層過早視為已收尾）。")
    lines.append("")
    lines.append("若命中內容是實質論述中不得不出現的延後語彙（真實決策本身），")
    lines.append("優先嘗試 inline 標記（不要改寫文字繞過偵測）:")
    lines.append("  在命中行同行或前 1 行加 <!-- PC-093-exempt: <category>:<reason> -->")
    lines.append("  若屬合法延後情境，這是最低成本的解法；改寫文字 = PC-093 同精神反模式。")
    lines.append("")
    lines.append("Ticket: {}".format(ticket_id))
    lines.append("命中:")
    for hit in blocked:
        lines.append("  line {} [{}]: 「{}」".format(hit.line_no, hit.rule_id, hit.text))
    lines.append("")
    lines.append("根因: PC-093 YAGNI 累積反模式")
    lines.append("  詳見: .claude/error-patterns/process-compliance/PC-093-yagni-deferred-decision-accumulation.md")
    lines.append("")
    lines.append("合法豁免 category 白名單（共 {} 項）:".format(len(EXEMPT_CATEGORIES)))
    lines.append("  - tdd-transition  — TDD phase 轉換的合法延後（Phase 1→2→3 規格性過渡）")
    lines.append("  - baseline-gated  — 量化基線觸發條件（reason 須含數字，如『baseline > 100ms 重啟』）")
    lines.append("  - ticket-tracked  — 引用既有 ticket ID（reason 須含 W{wave}-{seq}，如 source ticket 歷史引用）")
    lines.append("  - user-override   — 用戶明確授權的延後（一般說明 ≥ 10 字）")
    lines.append("  - rule-quote      — 引用 .claude/rules/ 或 .claude/pm-rules/ 規則名稱（reason 須含規則路徑）")
    lines.append("  - history         — 引用已完成歷史 / 動機脈絡（reason 須含 W{wave}-{seq} ticket ID 作錨點）")
    lines.append("  詳見 .claude/references/decision-trigger-binding-details.md「Hook 引用豁免機制」章節")
    lines.append("")
    lines.append("要求對每項做出三選一:")
    lines.append("  1. 執行 — 立即實作，附 use case + AC")
    lines.append("  2. 移除 — 刪除預留 + dead code，記錄理由")
    lines.append("  3. 豁免 — 符合上述白名單條件，加 <!-- PC-093-exempt: cat:reason --> 標記")
    lines.append("")
    lines.append("修復後重新 ticket track phase {} phase4。".format(ticket_id))
    lines.append("")
    lines.append("AUQ 選項骨架:")
    lines.append("  - label: 執行          description: Phase 4 立即實作 + 加 AC")
    lines.append("  - label: 移除          description: 刪除預留 + dead code")
    lines.append("  - label: 豁免（附條件） description: 加 PC-093-exempt 標記")
    if exempted:
        lines.append("")
        lines.append("[PC-093 當前豁免清單]")
        for hit in exempted:
            lines.append("  line {} [{}]: 「{}」".format(hit.line_no, hit.rule_id, hit.text))
    return "\n".join(lines)


# ============================================================================
# F11: Warn/Info 訊息組裝
# ============================================================================

def format_warn_info_message(
    warned: List[Hit],
    info: List[Hit],
    exempted_refs: List[ExemptRef],
) -> str:
    """組 §4.2 stdout 警告 + 豁免審計訊息。"""
    lines = []
    if warned:
        lines.append("[PC-093 警告] 模糊延後話術（不阻塞，Phase 4 前建議釐清）")
        for hit in warned:
            lines.append("  line {} [{}]: 「{}」".format(hit.line_no, hit.rule_id, hit.text))
    if info:
        if warned:
            lines.append("")
        lines.append("[PC-093 提醒] 延後標記（若有後續 ticket 可豁免）")
        for hit in info:
            lines.append("  line {} [{}]: 「{}」".format(hit.line_no, hit.rule_id, hit.text))

    # 豁免審計（AC8）
    valid_exempts = [r for r in exempted_refs if r.valid and r.marker]
    invalid_exempts = [r for r in exempted_refs if not r.valid]
    if valid_exempts or invalid_exempts:
        if lines:
            lines.append("")
        lines.append("[PC-093 豁免清單] 當前豁免：")
        for ref in valid_exempts:
            lines.append("  line {}: {} — {}".format(
                ref.line_no, ref.marker.category, ref.marker.reason
            ))
        for ref in invalid_exempts:
            err_code = ref.err or "format-error"
            title, hint = ERR_MESSAGE_MAP.get(
                err_code,
                ("Exempt marker 驗證失敗", "請檢查 marker 格式"),
            )
            lines.append("  line {}: [INVALID: {}] {}".format(ref.line_no, err_code, title))
            lines.append("    修復提示: {}".format(hint))
        if valid_exempts:
            lines.append("")
            lines.append("Phase 4 結束前必須清償（改執行或移除），剩餘豁免於 complete 時 WARN。")
    return "\n".join(lines)


# ============================================================================
# Main
# ============================================================================

def main() -> int:
    """Hook 主流程。"""
    logger = setup_hook_logging("phase4-decision-enforcement")

    input_data = read_json_from_stdin(logger)
    if input_data is None:
        return 0

    # Effort 感知（v2.1.133+，W14-034）：
    # PC-093 偵測屬「事實判斷」（quality-baseline 規則 2 強制），
    # 必擋邏輯與 effort 無關 — 不論 effort 為何，blocked 一律阻擋。
    # low effort 僅抑制 warn/info audit 輸出以省 tokens。
    effort = get_effort_level(input_data)
    logger.info("effort=%s，phase4-decision-enforcement 啟動（blocked 始終阻擋）", effort)

    event_name = input_data.get("hook_event_name") or input_data.get("hookEventName") or ""
    tool_input = extract_tool_input(input_data)
    command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""

    if not command:
        logger.debug("no command in tool_input, skip")
        return 0

    ticket_id, mode = extract_ticket_id_from_command(command)
    if mode is None:
        logger.debug("command not matching main/residual gate: {}".format(command[:80]))
        return 0

    # Event 與 mode 對應檢查（INT-6/INT-10）
    if mode == "main_gate" and event_name not in ("PostToolUse", ""):
        logger.debug("main_gate 但 event 非 PostToolUse: {}".format(event_name))
        return 0
    if mode == "residual_gate" and event_name not in ("PreToolUse", ""):
        logger.debug("residual_gate 但 event 非 PreToolUse: {}".format(event_name))
        return 0

    if not ticket_id:
        logger.debug("no ticket_id extracted")
        return 0

    md_path = resolve_ticket_md_path(ticket_id, logger)
    if md_path is None or not md_path.exists():
        logger.info("ticket md not found: {}".format(ticket_id))
        return 0

    try:
        content = md_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as exc:
        logger.info("read ticket md failed: {}".format(exc))
        return 0

    # PC-099: 檔級豁免（meta-ticket self-reference）
    if detect_hook_self_reference(content):
        logger.info(
            "ticket {} declared hook_self_reference, skip scan (PC-099)".format(ticket_id)
        )
        return 0

    lines = content.split("\n")
    table = build_regex_table()
    hits = scan_lines_for_phrases(lines, table)
    markers = collect_exempt_markers(lines)
    blocked, warned, info, exempted_hits = partition_hits(hits, markers)

    logger.info(
        "scan result: ticket={} mode={} blocked={} warned={} info={} exempted={}".format(
            ticket_id, mode, len(blocked), len(warned), len(info), len(exempted_hits)
        )
    )

    if blocked:
        msg = format_block_message(ticket_id, blocked, exempted_hits)
        sys.stderr.write(msg + "\n")
        sys.stderr.flush()
        logger.info("blocked=%d，effort=%s 仍強制阻擋（PC-093 規則 2）", len(blocked), effort)
        return 2

    # WARN/INFO/exempt audit → stdout (hook JSON)
    # low effort 抑制 warn/info audit 以省 tokens（blocked 已在上方處理）
    if effort == "low":
        if warned or info or markers:
            logger.info("effort=low，抑制 warn/info audit 輸出（warned=%d info=%d markers=%d）",
                        len(warned), len(info), len(markers))
        return 0

    if warned or info or markers:
        msg = format_warn_info_message(warned, info, markers)
        if msg:
            emit_hook_output(event_name or "PostToolUse", additional_context=msg)
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "phase4-decision-enforcement"))
