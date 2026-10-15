#!/usr/bin/env python3
"""spec validate 的 domain 覆蓋閘門：spec 的每個 FR 是否都被 domain map 的 FR->bundle 覆蓋表歸屬。

背景：一次架構檢討發現 domain 規劃缺口——spec 定義 FR、UC 定義場景，但無 domain
bundle 邊界；且 spec FR 是否全數映射到某 bundle 缺工具強制（曾靠人工四視角審查才
抓出漏覆蓋的 FR）。本檢核作為 /spec validate Layer 1 的擴充規則，機械掃描：
  1. spec 對應的 domain map 是否存在
  2. spec 每個 FR 是否出現在 domain map 的 FR 覆蓋（含標為 presentation/data 的非 domain FR）

domain map 定位鏈：--domain-map 明示（唯一來源，不聯集）-> spec 同目錄 domain-map.md
與 docs/spec/*/domain-map.md 中 frontmatter source_specs 含本 SPEC id 者（同目錄為聯集
成員之一，並聯集 docs/system-layer.md；逐檔解析後於集合層合併）-> docs/domain-map.md。

另含可選檢核「事件流標定」（`--check-event-flow-labeling`）：spec 的 FR 段落若命中
事件流訊號詞（清單見 EVENT_FLOW_SIGNAL_WORDS，與 /spec validate Layer 2 維度 5「資源
競爭」共用同一份訊號詞，見 SKILL.md 維度 5 掃描說明），該 FR 須能在 domain map 的
「通道與協調圖」節（以標題文字定位，不依編號——章節編號在各專案可能已被既有內容
佔用）之「到達類別與級別實例」子表中找到對應的 FR 引用，缺者列為提醒，非阻擋。
"""

import argparse
import re
import sys
import unicodedata
from pathlib import Path
from typing import NamedTuple

import check_api_surface

# FR 標題容許 H3 以上任一層級（### / #### …）——真實 spec 常用 #### FR-XX:，
# 只認 H3 會使 extract_spec_frs 回空集、gate 靜默假通過（Round 2-C 實證）。
# 冒號接受半形與全形（SPEC-006/007 用全形，曾因只認半形而抽出 0 個、假通過）。
FR_HEADER_RE = re.compile(r"^#{3,}\s+(FR-\d+)[:：]", re.MULTILINE)

# 事件流訊號詞：與 /spec validate Layer 2 維度 5「資源競爭」共用單一常數，避免
# Layer 1 機械檢核與 Layer 2 語意維度各自維護清單而漂移（SKILL.md 維度 5 掃描說明）。
EVENT_FLOW_SIGNAL_WORDS = (
    "事件", "通知", "提示", "背景", "排程", "佇列", "推送", "webhook", "isolate",
)

# domain map 章節標題比對：以標題文字定位，不依編號（章節編號在既有專案可能已
# 被其他內容佔用，如本專案 docs/domain-map.md 的「## 2.5」已用於他途）。
CHANNEL_SECTION_TITLE_RE = re.compile(r"^(#{1,6})\s*.*通道與協調圖.*$", re.MULTILINE)
ARRIVAL_LEVEL_TABLE_TITLE_RE = re.compile(r"^(#{1,6})\s*.*到達類別與級別.*$", re.MULTILINE)
# 展開 FR token：FR-NN、逗號續列 FR-01,02,03、範圍 FR-13~17 / FR-13-17
FR_TOKEN_RE = re.compile(r"FR-(\d+)((?:\s*[~\-,]\s*\d+)*)")


def _expand_fr_token(head_num, tail):
    """展開單一 FR token 為 int 集合。head_num=起始號，tail=續列/範圍字串。"""
    nums = {int(head_num)}
    prev = int(head_num)
    for op, digits in re.findall(r"([~\-,])\s*(\d+)", tail):
        n = int(digits)
        if op == ",":
            nums.add(n)
            prev = n
        else:  # ~ 或 - 視為範圍
            for v in range(min(prev, n), max(prev, n) + 1):
                nums.add(v)
            prev = n
    return nums


def extract_fr_ids(text):
    """從文字抽出所有 FR 編號（int 集合），處理逗號續列與範圍。"""
    ids = set()
    for head, tail in FR_TOKEN_RE.findall(text):
        ids |= _expand_fr_token(head, tail)
    return ids


FENCE_OPEN_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")


def _fence_open(line):
    """開圍欄行回傳 (圍欄字元, 長度)；反引號開行的標示含反引號者（行內寫法）不是圍欄。"""
    m = FENCE_OPEN_RE.match(line)
    if not m or (m.group(1)[0] == "`" and "`" in m.group(2)):
        return None
    return m.group(1)[0], len(m.group(1))


def _fence_closes(line, fence):
    """閉合行：同字元、長度不小於開行、其後無其他文字。"""
    m = re.match(r"^ {0,3}(`+|~+)[ \t]*$", line)
    return bool(m) and m.group(1)[0] == fence[0] and len(m.group(1)) >= fence[1]


def mask_fenced_blocks(text):
    """圍欄程式碼區塊內的行（含圍欄行）換成空行，保留行號。

    回傳 (遮罩後文字, 未閉合圍欄的開行行號或 None)。
    """
    out, fence, opened_at = [], None, None
    for no, line in enumerate(text.splitlines(), 1):
        if fence is None:
            fence = _fence_open(line)
            opened_at = no if fence else None
            out.append("" if fence else line)
        else:
            if _fence_closes(line, fence):
                fence = None
            out.append("")
    return "\n".join(out), (opened_at if fence else None)


def _mask_fenced_blocks(text):
    return mask_fenced_blocks(text)[0]


def _code_span_end(text, i):
    """text[i] 為反引號時，回傳同行內與之等長的收尾反引號串之後的位置；無收尾回傳 None。"""
    n = 1
    while text[i + n:i + n + 1] == "`":
        n += 1
    eol = text.find("\n", i)
    eol = len(text) if eol < 0 else eol
    close = re.compile(r"(?<!`)`{%d}(?!`)" % n).search(text, i + n, eol)
    return close.end() if close else None


def _mask_html_comments(text):
    """HTML 註解（可跨行）的非換行字元換成 NUL，保留行號。

    行內程式碼（同行的反引號片段）內的 `<!--`、`-->` 不作為註解邊界；未閉合的 <!-- 不遮
    （保守，不掩蓋內容）。用 NUL 而非空白：`<!-- x --> ## FR-01` 遮成空白後會變成縮排標題而被誤認。
    """
    out, i = [], 0
    while i < len(text):
        if text[i] == "`":
            end = _code_span_end(text, i)
            end = end if end else i + 1
            out.append(text[i:end])
            i = end
        elif text.startswith("<!--", i):
            close = text.find("-->", i + 4)
            if close < 0:
                out.append(text[i:])
                break
            out.append(re.sub(r"[^\n]", "\x00", text[i:close + 3]))
            i = close + 3
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def _scan_text(text):
    """抽取與形似判定共用的掃描文字：先遮圍欄、再遮註解，行號不變。"""
    return _mask_html_comments(_mask_fenced_blocks(text))


def extract_spec_frs(spec_text):
    """從 spec 的 `### FR-XX:` 標題抽出定義的 FR 編號（int 集合）；略過圍欄程式碼區塊與註解。"""
    masked = _scan_text(spec_text)
    return {int(m.group(1).split("-")[1]) for m in FR_HEADER_RE.finditer(masked)}


# 形似 FR 定義的行（抽取端漏抓提醒與宣告矛盾比對共用單一判定，規則只在此處改）。
# 行文字先做 NFKC 正規化（全形字母、數字、連字號、方括號併入半形）。
_FR_LEAD = r"[*_\[\u3010\u300c`]*"  # 粗體、強調、方括號、反引號包裹
_FR_NUMBERING = r"(?:(?:\d+(?:\.\d+)*\.?|需求)[ \t]*)?"  # 「3.1 」「需求 」編號前綴
_FR_CORE = _FR_LEAD + _FR_NUMBERING + r"FR[-\u2010-\u2015\u2212]?[ \t]*(\d+)"  # 須含編號：「FR：不適用」不命中
FR_LIKE_ATX_RE = re.compile(r"^ {0,3}#{1,6}[ \t]+" + _FR_CORE, re.IGNORECASE)
FR_LIKE_STRONG_RE = re.compile(r"^ {0,3}(?:\*\*|__)" + _FR_CORE, re.IGNORECASE)
FR_LIKE_SETEXT_TEXT_RE = re.compile(r"^ {0,3}" + _FR_CORE, re.IGNORECASE)
SETEXT_UNDERLINE_RE = re.compile(r"^ {0,3}(?:=+|-+)[ \t]*$")


def _frontmatter_line_count(text):
    block = FRONTMATTER_BLOCK_RE.match(text)
    return text[: block.end()].count("\n") + 1 if block else 0


def _fr_like_number(line, next_line):
    """該行形似 FR 定義時回傳 FR 編號（int），否則 None。"""
    norm = unicodedata.normalize("NFKC", line)
    m = FR_LIKE_ATX_RE.match(norm) or FR_LIKE_STRONG_RE.match(norm)
    if not m and SETEXT_UNDERLINE_RE.match(unicodedata.normalize("NFKC", next_line)):
        m = FR_LIKE_SETEXT_TEXT_RE.match(norm)
    return int(m.group(1)) if m else None


def fr_like_lines(spec_text):
    """回傳 [(行號, 行文字, FR 編號)]：形似 FR 定義的行。略過圍欄、註解與 frontmatter。

    形式：ATX 標題、行首粗體、setext 標題；標題內可帶編號前綴、粗體、方括號、反引號、全形字母。
    不含清單項與表格列（那是對 FR 的引用，不是定義）；NFR、帶 SPEC 前綴的引用、
    無編號的 FR 字樣不命中。
    """
    masked = _scan_text(spec_text).splitlines()
    originals = spec_text.splitlines()
    skip = _frontmatter_line_count(spec_text)
    found = []
    for i, line in enumerate(masked):
        if i < skip:
            continue
        number = _fr_like_number(line, masked[i + 1] if i + 1 < len(masked) else "")
        if number is not None:
            found.append((i + 1, originals[i].strip(), number))
    return found


def find_unextracted_fr_lines(spec_text):
    """回傳 [(行號, 行文字)]：形似 FR 定義、但其編號不在抽出集合內的行。"""
    extracted = extract_spec_frs(spec_text)
    return [(no, line) for no, line, number in fr_like_lines(spec_text) if number not in extracted]


def find_skipped_fr_lines(spec_text):
    """回傳 [(行號, 行文字)]：被圍欄或註解遮掉、但原文形似 FR 定義或符合抽取樣式的行（略過 frontmatter）。

    遮蔽規則的通用保險：遮蔽後仍形似者（行內註解不影響該行）不列。
    """
    originals = spec_text.splitlines()
    masked = _scan_text(spec_text).splitlines()
    masked += [""] * (len(originals) - len(masked))
    skip = _frontmatter_line_count(spec_text)

    def looks_like_fr(lines, i):
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        return FR_HEADER_RE.match(lines[i]) or _fr_like_number(lines[i], nxt) is not None

    return [(i + 1, originals[i].strip()) for i in range(skip, len(originals))
            if masked[i] != originals[i] and looks_like_fr(originals, i) and not looks_like_fr(masked, i)]


SPEC_ID_RE = re.compile(r"SPEC-\d+")
FRONTMATTER_BLOCK_RE = re.compile(r"\A---\s*\n(.*?)^---\s*$", re.MULTILINE | re.DOTALL)
FRONTMATTER_ID_LINE_RE = re.compile(r"^id:\s*[\"']?([^\s\"']+)", re.MULTILINE)
HEADING_RE = re.compile(r"^(#{1,6})\s")


def extract_spec_id(spec_text, spec_path=None):
    """spec 識別：先取 frontmatter id，缺時取檔名的 SPEC-NNN 前綴，都沒有回 None。

    只接受 SPEC-NNN 形式：domain map 的歸屬鍵由 SPEC_ID_RE 抽出，其他形式的 id
    （如 SPEC-UI-001）在 map 端永遠對不上，回 None。覆蓋比對遇 None 走相容模式並警告
    （不把該 spec 的全部 FR 報成未覆蓋）；定位 domain map 與層級模式遇 None 則報 id 無法辨識。
    frontmatter 只看收尾 --- 之前的區塊。
    """
    block = FRONTMATTER_BLOCK_RE.match(spec_text)
    fm = FRONTMATTER_ID_LINE_RE.search(block.group(1)) if block else None
    if fm:
        candidate = fm.group(1).upper()
        return candidate if SPEC_ID_RE.fullmatch(candidate) else None
    if spec_path is not None:
        name = SPEC_ID_RE.match(Path(spec_path).name)
        if name:
            return name.group(0).upper()
    return None


def _line_fr_owners(line, heading_spec):
    """回傳該行每個 FR token 的（所屬 spec 或 None, FR 編號集合）。

    歸屬順序：同一行在 token 之前最近的 SPEC-NNN；否則沿用祖先標題的 spec。
    """
    for m in FR_TOKEN_RE.finditer(line):
        before = SPEC_ID_RE.findall(line[: m.start()])
        owner = before[-1].upper() if before else heading_spec
        yield owner, _expand_fr_token(m.group(1), m.group(2))


def extract_fr_attribution(domain_map_text):
    """回傳 ({spec_id: FR 編號集合}, 未歸屬 FR 編號集合)。"""
    attributed, unattributed = {}, set()
    stack = []  # [(標題階層, 該標題的 spec 或 None)]
    for line in domain_map_text.splitlines():
        heading = HEADING_RE.match(line)
        if heading:
            level = len(heading.group(1))
            while stack and stack[-1][0] >= level:
                stack.pop()
            found = SPEC_ID_RE.search(line)
            stack.append((level, found.group(0).upper() if found else None))
        heading_spec = next((sp for _, sp in reversed(stack) if sp), None)
        for owner, nums in _line_fr_owners(line, heading_spec):
            if owner:
                attributed.setdefault(owner, set()).update(nums)
            else:
                unattributed |= nums
    return attributed, unattributed


class _ParsedMap(NamedTuple):
    """一份 map 的歸屬解析結果；每份 map 只解析一次，覆蓋判定與尾行說明共用。"""
    name: str
    text: str
    attributed: dict
    unattributed: set

    @property
    def is_default_assigned(self):
        """整份無任何 SPEC 歸屬、有未歸屬 FR、且非系統層：其 FR 一律計給受檢 SPEC（相容語意）。

        系統層是定位鏈無條件附加的，不是因與受檢 SPEC 有關而被選入，不適用預設計給。
        """
        return not self.attributed and bool(self.unattributed) and Path(self.name).name != SYSTEM_LAYER_PATH.name


def _parse_maps(named_texts):
    """逐檔解析歸屬（標題堆疊不跨檔），回傳 [_ParsedMap]。"""
    return [_ParsedMap(name, text, *extract_fr_attribution(text)) for name, text in named_texts]


def _merged_attribution(parsed_maps, spec_id):
    """於集合層合併各檔歸屬，回傳 {spec_id: FR 集合}。

    整份無歸屬的檔（系統層除外）其 FR 計給受檢 SPEC；檔案內有部分歸屬時，有歸屬者依歸屬，未歸屬者不計入。
    """
    merged = {}
    for m in parsed_maps:
        attributed = m.attributed
        if m.is_default_assigned and spec_id:
            sys.stderr.write(f"domain 覆蓋檢核：{m.name} 無任何 SPEC 歸屬，其 FR 依預設計給受檢 SPEC\n")
            attributed = {spec_id: m.unattributed}
        for owner, nums in attributed.items():
            merged.setdefault(owner, set()).update(nums)
    return merged


def _uncovered_frs(spec_text, parsed_maps, spec_path=None):
    """回傳 spec 定義但各 map 聯集未覆蓋的 FR 編號（排序 list）。

    比對鍵為（spec 識別, FR 編號）。spec 識別取不到、或各檔合併後無任何歸屬時，
    走相容模式（不分 spec 的舊比對）並於 stderr 說明。
    """
    spec_frs = extract_spec_frs(spec_text)
    spec_id = extract_spec_id(spec_text, spec_path)
    attributed = _merged_attribution(parsed_maps, spec_id)
    if spec_id is None:
        sys.stderr.write("WARNING: 取不到 spec 識別（frontmatter id / 檔名 SPEC-NNN），走相容模式（不分 spec 比對）\n")
    elif not attributed:
        # 到此表示非系統層的 map 皆無任何 FR 編號（有則已預設計給），只有系統層可能帶未歸屬的 FR
        sys.stderr.write("domain 覆蓋檢核：domain map 無任何 FR 歸屬到 SPEC-NNN（非系統層的 map 無任何 FR 編號），"
                         "走相容模式（不分 spec 比對，系統層出現的 FR 一律視為覆蓋）\n")
    else:
        return sorted(spec_frs - attributed.get(spec_id, set()))
    return sorted(spec_frs - extract_fr_ids("\n".join(m.text for m in parsed_maps)))


def check_domain_coverage_union(spec_text, named_texts, spec_path=None):
    """多份 map（(檔名, 內容) 清單）的覆蓋判定，聯集發生在集合層；單份 map 傳單元素清單。"""
    return _uncovered_frs(spec_text, _parse_maps(named_texts), spec_path)


def extract_event_signaled_frs(spec_text, signal_words=EVENT_FLOW_SIGNAL_WORDS):
    """回傳 spec 中，FR 段落內文命中任一事件流訊號詞的 FR 編號集合（int）。

    段落切分沿用 check_api_surface.split_fr_sections（H3 `### FR-XX:` 標題），
    避免與既有 API surface 檢核各自維護一份切段邏輯。
    """
    signaled = set()
    for fr_id, section in check_api_surface.split_fr_sections(spec_text):
        lowered = section.lower()
        if any(word.lower() in lowered for word in signal_words):
            signaled.add(int(fr_id.split("-")[1]))
    return signaled


def _extract_section_by_title(text, title_re):
    """依標題文字定位一個章節（不依編號），回傳從該標題到下一個同級或更高階標題前的內容。

    找不到標題時回傳 None。「同級或更高階」判定以 `#` 數決定，使巢狀子節（較深階
    標題）不會被誤判為章節邊界。
    """
    match = title_re.search(text)
    if not match:
        return None
    level = len(match.group(1))
    start = match.start()
    next_heading_re = re.compile(r"^#{1," + str(level) + r"}\s+", re.MULTILINE)
    next_match = next_heading_re.search(text, match.end())
    end = next_match.start() if next_match else len(text)
    return text[start:end]


def extract_channel_section(domain_map_text):
    """定位 domain map 的『通道與協調圖』節（標題文字比對，不依編號）。"""
    return _extract_section_by_title(domain_map_text, CHANNEL_SECTION_TITLE_RE)


def extract_arrival_level_table(channel_section_text):
    """在『通道與協調圖』節內，定位含到達類別與級別欄的『到達類別與級別實例』子節。"""
    if channel_section_text is None:
        return None
    return _extract_section_by_title(channel_section_text, ARRIVAL_LEVEL_TABLE_TITLE_RE)


def check_event_flow_labeling(spec_text, domain_map_text, signal_words=EVENT_FLOW_SIGNAL_WORDS):
    """回傳命中事件流訊號詞、但 domain map 通道表未見對應標定的 FR 編號（排序 list）。

    未命中任何訊號詞的 spec 回傳空 list（維度 5 同形的條件式觸發：無事件流訊號時不檢核）。
    """
    return check_event_flow_labeling_union(spec_text, [domain_map_text], signal_words)


def check_event_flow_labeling_union(spec_text, map_texts, signal_words=EVENT_FLOW_SIGNAL_WORDS):
    """多份 map 版：逐檔取通道章節與到達級別子表，聯集已標定的 FR 後再比對。"""
    signaled = extract_event_signaled_frs(spec_text, signal_words)
    if not signaled:
        return []
    labeled = set()
    for text in map_texts:
        table = extract_arrival_level_table(extract_channel_section(text))
        if table:
            labeled |= extract_fr_ids(table)
    return sorted(signaled - labeled)


DOMAIN_MAP_GLOB_DIR = Path("docs/spec")
SYSTEM_LAYER_PATH = Path("docs/system-layer.md")
LEGACY_DOMAIN_MAP_PATH = Path("docs/domain-map.md")
SOURCE_SPECS_KEY_RE = re.compile(r"^source_specs:[ \t]*(.*?)[ \t]*$")
BLOCK_ITEM_RE = re.compile(r"^[ \t]*-[ \t]*(.*?)[ \t]*$")
TRAILING_COMMENT_RE = re.compile(r"(?:^|[ \t]+)#.*$")

# 定位失敗的成因（locate_domain_maps_with_reason 的第二個回傳值；有定位到 map 時為 None）
REASON_EXPLICIT_MISSING = "explicit_missing"
REASON_NO_MAP = "no_map"
REASON_ID_UNRECOGNIZED = "id_unrecognized"
REASON_SOURCE_SPECS_UNPARSEABLE = "source_specs_unparseable"
REASON_NOT_LISTED = "not_listed"


def _parse_source_specs(map_text):
    """回傳 frontmatter source_specs 的 SPEC id 集合；未宣告該鍵為空集合，格式無法解析為 None。

    可解析：行內清單 `[a, b]`、區塊清單（鍵後逐行 `- a`）。
    """
    block = FRONTMATTER_BLOCK_RE.match(map_text)
    if not block:
        return set()
    lines = block.group(1).splitlines()
    for i, line in enumerate(lines):
        key = SOURCE_SPECS_KEY_RE.match(line)
        if not key:
            continue
        value = TRAILING_COMMENT_RE.sub("", key.group(1)).strip()
        rest = [TRAILING_COMMENT_RE.sub("", ln).strip() for ln in lines[i + 1:]]
        rest = [ln for ln in rest if ln]  # 空行與純註解行不截斷清單
        if not value and rest and rest[0].startswith("["):
            value = rest[0]  # flow 清單寫在鍵的下一行
        if value.startswith("[") and value.endswith("]"):
            return set(SPEC_ID_RE.findall(value.upper()))
        if value:
            return None
        items = []
        for following in lines[i + 1:]:
            if not TRAILING_COMMENT_RE.sub("", following).strip():
                continue
            item = BLOCK_ITEM_RE.match(following)
            if not item:
                break
            items.append(TRAILING_COMMENT_RE.sub("", item.group(1)))
        return set(SPEC_ID_RE.findall(" ".join(items).upper())) if items else None
    return set()


def _list_domain_maps():
    """列舉 docs/spec/*/domain-map.md（依路徑排序，結果穩定）。"""
    return sorted(DOMAIN_MAP_GLOB_DIR.glob("*/domain-map.md"))


def _scan_listing_maps(spec_id):
    """回傳 (source_specs 含 spec_id 的 map 清單, source_specs 格式無法解析的 map 清單)。"""
    listing, unparseable = [], []
    for m in _list_domain_maps():
        declared = _parse_source_specs(m.read_text(encoding="utf-8"))
        if declared is None:
            unparseable.append(m)
        elif spec_id in declared:
            listing.append(m)
    return listing, unparseable


def _diagnose_missing(spec_id, unparseable):
    """找不到任何 map 時的成因，依序判定。"""
    if not _list_domain_maps():
        return REASON_NO_MAP
    if spec_id is None:
        return REASON_ID_UNRECOGNIZED
    if unparseable:
        return REASON_SOURCE_SPECS_UNPARSEABLE
    return REASON_NOT_LISTED


def locate_domain_maps_with_reason(spec_path, explicit, spec_id=None):
    """定位 domain map 清單（可多份，覆蓋判定取聯集），並回報找不到時的成因。

    回傳 (paths, reason, unparseable)：找到時 reason 為 None；找不到時 paths 為空 list、reason 為
    REASON_* 之一；unparseable 為 source_specs 格式無法解析的 map 清單（供訊息列名）。
    解析鏈：explicit -> spec 同目錄（為聯集成員之一，不短路）+ docs/spec/*/domain-map.md 中 source_specs 含本 SPEC
    者（並聯集 docs/system-layer.md）-> docs/domain-map.md。
    """
    if explicit:
        p = Path(explicit)
        return ([p], None, []) if p.exists() else ([], REASON_EXPLICIT_MISSING, [])
    same_dir = spec_path.parent / "domain-map.md"
    if spec_id is None and Path(spec_path).exists():
        spec_id = extract_spec_id(Path(spec_path).read_text(encoding="utf-8"), spec_path)
    found = [same_dir] if same_dir.exists() else []
    listing, unparseable = _scan_listing_maps(spec_id)
    seen = {p.resolve() for p in found}
    for m in listing:
        if m.resolve() not in seen:
            found.append(m)
            seen.add(m.resolve())
    if found:
        return found + ([SYSTEM_LAYER_PATH] if SYSTEM_LAYER_PATH.exists() else []), None, unparseable
    if LEGACY_DOMAIN_MAP_PATH.exists():
        return [LEGACY_DOMAIN_MAP_PATH], None, unparseable
    return [], _diagnose_missing(spec_id, unparseable), unparseable


def locate_domain_maps(spec_path, explicit, spec_id=None):
    """locate_domain_maps_with_reason 的僅路徑版；找不到回空 list。"""
    return locate_domain_maps_with_reason(spec_path, explicit, spec_id)[0]


ID_UNRECOGNIZED_CAUSE = "domain 覆蓋檢核：spec id 無法辨識（frontmatter id 與檔名皆取不到 SPEC-NNN 形式）"


def describe_layer_id_unrecognized():
    """層級路徑的 id 無法辨識訊息：成因子句與非層級共用，下一步不同（層級模式不走相容比對，不建議 --domain-map）。"""
    return f"{ID_UNRECOGNIZED_CAUSE}，無法比對系統層的 SPEC 歸屬。請修正 spec 的 id 為 SPEC-NNN 形式。"


def describe_missing_map(reason, explicit=None, unparseable=()):
    """依定位函式回報的成因輸出訊息。"""
    if reason == REASON_EXPLICIT_MISSING:
        return f"domain 覆蓋檢核：--domain-map 指定的檔案不存在：{explicit}"
    if reason == REASON_ID_UNRECOGNIZED:
        return (
            f"{ID_UNRECOGNIZED_CAUSE}，"
            "無法比對 domain map 的 source_specs。請修正 spec 的 id 為 SPEC-NNN 形式，或以 --domain-map 指定。"
        )
    if reason == REASON_SOURCE_SPECS_UNPARSEABLE:
        names = ", ".join(p.as_posix() for p in unparseable)
        return (
            f"domain 覆蓋檢核：下列 domain map 的 source_specs 格式無法解析：{names}。"
            "接受行內清單 `[SPEC-001, SPEC-002]` 或逐行 `- SPEC-001` 的區塊清單；"
            "請改成可解析的寫法，或以 --domain-map 指定。"
        )
    if reason == REASON_NOT_LISTED:
        return (
            "domain 覆蓋檢核：有 domain map（docs/spec/*/domain-map.md），但無一份的 "
            "source_specs 列入本 SPEC。請於對應 domain map frontmatter 的 source_specs 補上本 SPEC id，"
            "或以 --domain-map 指定。"
        )
    return (
        "domain 覆蓋檢核：找不到任何 domain map（spec 同目錄 domain-map.md、"
        "docs/spec/*/domain-map.md 或 docs/domain-map.md）。"
        "依 version-bootstrap Step 2.5，規劃波應先產出 domain map。"
    )


DOMAIN_FIELD_RE = re.compile(r"^domain:[ \t]*(.*?)[ \t]*$", re.MULTILINE)
DOMAIN_NOT_SINGLE_NAME_RE = re.compile(r"[\[\],\s\"'#]")
YAML_NULL_LITERALS = frozenset({"", "~", "null"})


def _unquote_domain(raw):
    """先配對引號再剝尾端註解：引號配對成功取其內容；未配對的引號與值內井號原樣保留（交給格式檢查）。"""
    if raw[:1] in ("\"", "'") and raw.find(raw[0], 1) > 0:
        end = raw.find(raw[0], 1)
        if not raw[end + 1:].strip() or raw[end + 1:].lstrip().startswith("#"):
            return raw[1:end]
    return TRAILING_COMMENT_RE.sub("", raw).strip()


def _frontmatter_domain(text):
    """回傳 frontmatter 的 domain 欄值；未填、波浪號、null 或無 frontmatter 回 None。

    值為該行去掉尾端註解與成對引號後的字面，不驗證格式（見 domain_format_error）。
    """
    block = FRONTMATTER_BLOCK_RE.match(text)
    found = DOMAIN_FIELD_RE.search(block.group(1)) if block else None
    if not found:
        return None
    value = _unquote_domain(found.group(1))
    return None if value.lower() in YAML_NULL_LITERALS else value


def domain_format_error(spec_text):
    """domain 欄不是單一名稱（含方括號、逗號或空白）時回傳錯誤訊息，否則 None。不立命名樣式。"""
    domain = _frontmatter_domain(spec_text)
    if domain and DOMAIN_NOT_SINGLE_NAME_RE.search(domain):
        return (f"domain 覆蓋檢核失敗：SPEC frontmatter 的 domain 欄讀到 {domain!r}，"
                "該欄須為單一 domain 名稱（不可為清單、含空白、引號殘留或井號）。")
    return None


LEGACY_DOMAIN_FIELD_RE = re.compile(r"^domain:[ \t]*[\"']?([^\s\"'#]+)", re.MULTILINE)


def _map_frontmatter_domain(text):
    """domain map 端的 domain 欄讀取，刻意維持本輸入健全性補強之前的舊讀法（取第一個非空白、引號、井號字元序列）。

    與 SPEC 端的 _frontmatter_domain 不同：SPEC 端已補強（波浪號視同未填、引號與井號殘留報格式錯誤），
    但那些處置若直接套到 map 端，會使已宣告集合改變（單邊引號的名稱變成含引號字串、唯一的 map 寫波浪號時
    集合變空），讓層級判定的結果翻轉。map 端的正式處置（格式檢查與波浪號）待後續另行決定，在此之前保持不變。
    """
    block = FRONTMATTER_BLOCK_RE.match(text)
    found = LEGACY_DOMAIN_FIELD_RE.search(block.group(1)) if block else None
    if not found or found.group(1).lower() == "null":
        return None
    return found.group(1)


def _declared_domains():
    """各 docs/spec/*/domain-map.md 宣告的 domain 集合；無任何 map 時為空集合。"""
    found = (_map_frontmatter_domain(m.read_text(encoding="utf-8")) for m in _list_domain_maps())
    return {d for d in found if d}


def is_layer_spec(spec_text):
    """SPEC 的 domain 欄非任何已宣告 DomainBundle 的 domain，即為層級 SPEC（以系統層判定）。

    domain 欄未填、或專案無任何已宣告 domain（單 domain 專案）時不適用。
    """
    domain = _frontmatter_domain(spec_text)
    declared = _declared_domains()
    return bool(domain and declared and domain not in declared)


def layer_banner(spec_text, unparseable=()):
    """走系統層時印出判定依據：SPEC 的 domain 欄值與已宣告 domain 集合（供人眼比對錯字）。

    unparseable 非空時，有 map 以無法解析的寫法可能列了本 SPEC，橫幅不宣稱「無任何 map 列入」。
    """
    declared = ", ".join(sorted(_declared_domains()))
    claim = "無可解析的 map 列入本 SPEC（另有 map 的 source_specs 格式無法解析，見 stderr）" if unparseable else "無任何 map 列入本 SPEC"
    return (
        f"domain 覆蓋檢核：{claim}，其 domain 欄 {_frontmatter_domain(spec_text)!r} "
        f"不在已宣告 domain 集合 [{declared}]，視為層級 SPEC，以系統層判定"
    )


def warn_unparseable_maps(unparseable):
    """列出 source_specs 格式無法解析的 map 檔名（stderr 提醒，不改 exit code）。

    這些 map 未納入本次判定，且讀不出是否列了本 SPEC，故一律列出。
    """
    for p in unparseable:
        sys.stderr.write(
            f"WARNING: domain map 的 source_specs 格式無法解析，未納入本次判定，其歸屬可能含本 SPEC：{p.as_posix()}\n")


def _unlisted_unparseable(unparseable, selected_paths, reason, layer_mode):
    """須於 stderr 列名的 map：無法解析且未被選入判定者（以解析後路徑比對）。

    定位失敗且成因為 source_specs 無法解析時，stdout 訊息已列名（層級模式除外，其 stdout 不列），不重複。
    """
    if not selected_paths and not layer_mode and reason == REASON_SOURCE_SPECS_UNPARSEABLE:
        return []
    selected = {p.resolve() for p in selected_paths}
    return [p for p in unparseable if p.resolve() not in selected]


def describe_missing_system_layer():
    return (
        "domain 覆蓋檢核：本 SPEC 的 domain 欄不是任何已宣告的 domain（層級 SPEC），"
        f"以系統層 {SYSTEM_LAYER_PATH} 判定，但該檔不存在。"
    )


def _read_maps(paths):
    """逐檔讀取，回傳 [(檔名, 內容)]；不串接，供集合層聯集。"""
    return [(str(p), p.read_text(encoding="utf-8")) for p in paths]


DECLARATION_KEY = "has_functional_requirements"
DECLARATION_LINE_RE = re.compile(rf"^{DECLARATION_KEY}:[ \t]*(.*?)[ \t]*$")
TOP_KEY_LINE_RE = re.compile(r"^[^\s#][^:]*:[ \t]*(.*)$")
EXPECTED_HEADING_HINT = (
    "預期標題樣式：`### FR-NN: 標題` 或 `### FR-NN：標題`（H3 以上，半形或全形冒號）；"
    f"若本 SPEC 確實無 FR，請於 frontmatter 宣告 `{DECLARATION_KEY}: false`。"
)


def _unclosed_quote(text, quote):
    """於引號 quote 內掃描 text，回傳掃完後仍未閉合的引號字元；已閉合回 None。"""
    i = 0
    while i < len(text):
        ch = text[i]
        if quote == '"' and ch == "\\":
            i += 2
            continue
        if ch == quote:
            if quote == "'" and text[i + 1:i + 2] == "'":  # '' 是單引號的跳脫
                i += 2
                continue
            return None
        i += 1
    return quote


def _declaration_occurrences(frontmatter):
    """回傳 [(檔內行號, 值)]：頂層的宣告鍵行；引號多行字串續行內的行不算。"""
    found, quote = [], None
    for no, line in enumerate(frontmatter.splitlines(), 2):  # frontmatter 內容自檔案第 2 行起
        if quote:
            quote = _unclosed_quote(line, quote)
            continue
        declared = DECLARATION_LINE_RE.match(line)
        if declared:
            found.append((no, declared.group(1)))
        top = TOP_KEY_LINE_RE.match(line)
        if top and top.group(1)[:1] in ('"', "'"):
            quote = _unclosed_quote(top.group(1)[1:], top.group(1)[0])
    return found


def read_fr_declaration(spec_text):
    """回傳 frontmatter 的 has_functional_requirements：True/False；未填回 True；非布林或重複宣告拋 ValueError。"""
    block = FRONTMATTER_BLOCK_RE.match(spec_text)
    found = _declaration_occurrences(block.group(1)) if block else []
    if not found:
        return True
    if len(found) > 1:
        rows = "、".join(str(no) for no, _ in found)
        raise ValueError(f"{DECLARATION_KEY} 在 frontmatter 重複宣告（第 {rows} 行），無法判定以何者為準")
    raw = re.sub(r"\s+#.*$", "", found[0][1])
    if raw in ("true", "false"):
        return raw == "true"
    raise ValueError(
        f"{DECLARATION_KEY} 須為布林（合法寫法：true、false，小寫），實得 {raw!r}"
        "（未填視同 true；非布林不當作 false）")


def judge_fr_declaration(spec_text):
    """於 domain map 定位之前判定。回傳 exit code（已結束）或 None（續行覆蓋比對）。"""
    try:
        declared = read_fr_declaration(spec_text)
    except ValueError as exc:
        print(f"domain 覆蓋檢核失敗：{exc}")
        return 1
    for no, line in find_skipped_fr_lines(spec_text):
        sys.stderr.write(f"WARNING: 第 {no} 行形似 FR 定義但位於被略過的區段（圍欄程式碼區塊或 HTML 註解）內，不納入比對：{line}\n")
    extracted = extract_spec_frs(spec_text)
    if declared is False:
        loose = fr_like_lines(spec_text)
        if extracted or loose:
            print(f"domain 覆蓋檢核失敗：宣告 {DECLARATION_KEY}: false，但內容存在 FR 標題行（宣告與內容矛盾）：")
            for no, line, _ in loose:
                print(f"  第 {no} 行：{line}")
            return 1
        print(f"本 SPEC 宣告無 FR（{DECLARATION_KEY}: false），未執行覆蓋比對")
        return 0
    if not extracted:
        print("domain 覆蓋檢核失敗：未宣告無 FR，但未抽到任何 FR 標題（未執行覆蓋比對）。")
        print(EXPECTED_HEADING_HINT)
        return 1
    for no, line in find_unextracted_fr_lines(spec_text):
        sys.stderr.write(f"WARNING: 第 {no} 行形似 FR 定義但未被抽出（不納入比對）：{line}\n")
    return None


def check_layer_coverage(spec_text, system_text, spec_path=None):
    """層級模式：只以該 SPEC 在系統層的歸屬比對，不走相容後備；呼叫端須先確認 SPEC 識別可取得。"""
    spec_frs = extract_spec_frs(spec_text)
    spec_id = extract_spec_id(spec_text, spec_path)
    attributed, _ = extract_fr_attribution(system_text)
    return sorted(spec_frs - attributed.get(spec_id, set()))


def describe_attribution_remedy(where, spec_id):
    """未覆蓋尾行的補法：歸屬的比對鍵是 SPEC 識別，檔內已有任何 SPEC 歸屬時，只列出 FR 而不帶 SPEC 識別不會使檢核轉為通過。"""
    if spec_id is None:
        return f"請{where}補上這些 FR。"
    return f"請{where}補上這些 FR 的歸屬：FR 所在的章節標題含 {spec_id}，或在同一行、該 FR 之前寫出 {spec_id}。"


def describe_default_assigned(parsed_maps, spec_id):
    """整份無歸屬而走預設計給的檔（系統層除外）的補充說明；無此類檔回空字串。

    這類檔寫入任一 SPEC id 即轉為部分歸屬，檔內其餘未歸屬的 FR 不再計入，故須整檔一併歸屬。
    """
    if spec_id is None:
        return ""
    names = [m.name for m in parsed_maps if m.is_default_assigned]
    if not names:
        return ""
    return (f"其中 {', '.join(names)} 目前無任何 SPEC 歸屬，直接列出這些 FR 即可；"
            f"若於該檔寫入任一 SPEC id，檔內其餘 FR 須一併歸屬到 {spec_id}。")


def warn_unattributed_uncovered(parsed_maps, uncovered):
    """部分歸屬的檔內，未覆蓋的 FR 若落在其未歸屬集合，於 stderr 列該檔名與 FR（不改 exit code）。

    整份無歸屬的檔其 FR 已計給受檢 SPEC（另有訊息），不在此列；一個 FR 同時出現在多份檔時各檔各列一次。
    """
    for m in parsed_maps:
        dropped = sorted(m.unattributed & set(uncovered)) if m.attributed else []
        if dropped:
            frs = ", ".join(f"FR-{n:02d}" for n in dropped)
            sys.stderr.write(f"WARNING: {m.name} 為部分歸屬的檔，下列未覆蓋的 FR 在其中未歸屬到任何 SPEC，故不計入：{frs}\n")


def _report_domain_coverage(spec_text, domain_map_paths, spec_path=None, layer_mode=False):
    """列印 FR->bundle 覆蓋檢核結果，回傳 exit code。"""
    domain_map_path = ", ".join(str(p) for p in domain_map_paths)
    named_texts = _read_maps(domain_map_paths)
    if layer_mode:
        uncovered = check_layer_coverage(spec_text, named_texts[0][1], spec_path)
    else:
        parsed_maps = _parse_maps(named_texts)
        uncovered = _uncovered_frs(spec_text, parsed_maps, spec_path)
    if not uncovered:
        print(f"domain 覆蓋檢核通過：spec 全部 FR 皆在 {domain_map_path} 有 bundle 歸屬")
        return 0

    if layer_mode:
        print(f"domain 覆蓋檢核發現 {len(uncovered)} 個 FR 未在系統層覆蓋：")
    else:
        print(f"domain 覆蓋檢核發現 {len(uncovered)} 個 FR 未在 domain map 覆蓋：")
    for fr in uncovered:
        print(f"  FR-{fr:02d}")
    spec_id = extract_spec_id(spec_text, spec_path)
    if layer_mode:
        print(f"（系統層：{domain_map_path}）層級 SPEC 以系統層判定，{describe_attribution_remedy('於系統層', spec_id)}")
        return 1
    warn_unattributed_uncovered(parsed_maps, uncovered)
    tail = describe_attribution_remedy('於 domain map ', spec_id) + describe_default_assigned(parsed_maps, spec_id)
    print(f"（domain map：{domain_map_path}）{tail}")
    return 1


def _report_event_flow_labeling(spec_text, domain_map_paths, layer_mode=False):
    """列印事件流標定檢核結果，回傳 exit code。性質為啟發式提醒，非阻擋。"""
    domain_map_path = ", ".join(str(p) for p in domain_map_paths)
    missing = check_event_flow_labeling_union(
        spec_text, [t for _, t in _read_maps(domain_map_paths)])
    if not missing:
        print("事件流標定檢核通過：命中事件流訊號詞的 FR 皆在通道與協調圖節有到達類別與級別標定")
        return 0

    print(f"事件流標定檢核發現 {len(missing)} 個 FR 命中事件流訊號詞但未見通道標定（提醒，非阻擋）：")
    for fr in missing:
        print(f"  FR-{fr:02d}")
    label = "系統層" if layer_mode else "domain map"
    print(f"（{label}：{domain_map_path}）請於「通道與協調圖」節之「到達類別與級別實例」子表補上標定。")
    return 1


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="spec check-domain-coverage",
        description="檢查 spec 的每個 FR 是否被 domain map 的 FR->bundle 覆蓋表歸屬",
    )
    parser.add_argument("spec_path", help="Spec 文件路徑")
    parser.add_argument("--domain-map", help="domain map 路徑（省略則自動定位）")
    parser.add_argument(
        "--check-event-flow-labeling",
        action="store_true",
        help="額外執行事件流標定檢核（可選，啟發式提醒，非阻擋）",
    )
    args = parser.parse_args(argv)

    spec_path = Path(args.spec_path)
    for label, path in (("spec 路徑", spec_path), ("--domain-map", Path(args.domain_map) if args.domain_map else None)):
        if path is not None and path.is_dir():
            print(f"domain 覆蓋檢核：{label} 是目錄，需為檔案：{path}")
            return 1
    spec_text = spec_path.read_text(encoding="utf-8")

    unclosed = mask_fenced_blocks(spec_text)[1]
    if unclosed is not None:
        print(f"domain 覆蓋檢核失敗：第 {unclosed} 行開啟的圍欄程式碼區塊未閉合，其後內容未被檢視（未執行覆蓋比對）")
        return 1

    early = judge_fr_declaration(spec_text)
    if early is not None:
        return early

    if args.domain_map == "":
        print("domain 覆蓋檢核：--domain-map 指定的檔案不存在：''（空字串不視為未帶旗標）")
        return 1
    domain_map_paths, reason, unparseable = locate_domain_maps_with_reason(
        spec_path, args.domain_map, extract_spec_id(spec_text, spec_path))
    layer_mode = not domain_map_paths and args.domain_map is None and is_layer_spec(spec_text)
    warn_unparseable_maps(_unlisted_unparseable(unparseable, domain_map_paths, reason, layer_mode))
    # 層級判定只在原定位鏈找不到任何 map、且 domain 欄非已宣告 domain 時成立；
    # 有 map 時照原鏈，無 map 但 domain 欄為已宣告 domain 是漏登記，維持紅
    if not domain_map_paths and args.domain_map is None:
        # domain 欄只在此處被消費（進入層級判定），格式檢查限於此路徑
        format_error = domain_format_error(spec_text)
        if format_error:
            print(format_error)
            return 1
    if layer_mode:
        print(layer_banner(spec_text, unparseable))
        if SYSTEM_LAYER_PATH.is_dir():
            print(f"domain 覆蓋檢核：系統層 {SYSTEM_LAYER_PATH} 是目錄，需為檔案。")
            return 1
        if not SYSTEM_LAYER_PATH.exists():
            print(describe_missing_system_layer())
            return 1
        if extract_spec_id(spec_text, spec_path) is None:
            print(describe_layer_id_unrecognized())
            return 1
        domain_map_paths = [SYSTEM_LAYER_PATH]
    if SYSTEM_LAYER_PATH in domain_map_paths and SYSTEM_LAYER_PATH.is_dir():
        print(f"domain 覆蓋檢核：系統層 {SYSTEM_LAYER_PATH} 是目錄，需為檔案。")
        return 1
    if not domain_map_paths:
        print(describe_missing_map(reason, args.domain_map, unparseable))
        return 1

    rc = _report_domain_coverage(spec_text, domain_map_paths, spec_path, layer_mode)
    if args.check_event_flow_labeling:
        rc = _report_event_flow_labeling(spec_text, domain_map_paths, layer_mode) or rc
    return rc


if __name__ == "__main__":
    sys.exit(main())
