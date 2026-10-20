"""domain map 定位：source_specs 解析、定位鏈、層級 SPEC 判定與各類診斷訊息。

路徑常數皆為相對於 cwd 的相對路徑（測試以 chdir 隔離）。
"""

import re
import sys
from pathlib import Path

from .fr_extract import FRONTMATTER_BLOCK_RE, SPEC_ID_RE, extract_spec_id

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
