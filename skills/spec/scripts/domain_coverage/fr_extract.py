"""FR 擷取與遮罩：FR token 展開、圍欄/行內程式碼/HTML 註解遮罩、FR 標題抽取、frontmatter 讀取。

本模組是套件最底層，不依賴套件內其他模組。
"""

import re
import unicodedata
from pathlib import Path

# FR 標題容許 H3 以上任一層級（### / #### …）——真實 spec 常用 #### FR-XX:，
# 只認 H3 會使 extract_spec_frs 回空集、gate 靜默假通過（Round 2-C 實證）。
# 冒號接受半形與全形（SPEC-006/007 用全形，曾因只認半形而抽出 0 個、假通過）。
FR_HEADER_RE = re.compile(r"^#{3,}\s+(FR-\d+)[:：]", re.MULTILINE)

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
_FR_LEAD = r"[*_\[【「`]*"  # 粗體、強調、方括號、反引號包裹
_FR_NUMBERING = r"(?:(?:\d+(?:\.\d+)*\.?|需求)[ \t]*)?"  # 「3.1 」「需求 」編號前綴
_FR_CORE = _FR_LEAD + _FR_NUMBERING + r"FR[-‐-―−]?[ \t]*(\d+)"  # 須含編號：「FR：不適用」不命中
FR_LIKE_ATX_RE = re.compile(r"^ {0,3}#{1,6}[ \t]+" + _FR_CORE, re.IGNORECASE)
FR_LIKE_STRONG_RE = re.compile(r"^ {0,3}(?:\*\*|__)" + _FR_CORE, re.IGNORECASE)
FR_LIKE_SETEXT_TEXT_RE = re.compile(r"^ {0,3}" + _FR_CORE, re.IGNORECASE)
SETEXT_UNDERLINE_RE = re.compile(r"^ {0,3}(?:=+|-+)[ \t]*$")

SPEC_ID_RE = re.compile(r"SPEC-\d+")
FRONTMATTER_BLOCK_RE = re.compile(r"\A---\s*\n(.*?)^---\s*$", re.MULTILINE | re.DOTALL)
FRONTMATTER_ID_LINE_RE = re.compile(r"^id:\s*[\"']?([^\s\"']+)", re.MULTILINE)


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
