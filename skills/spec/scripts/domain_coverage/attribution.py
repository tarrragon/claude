"""FR 歸屬與覆蓋計算：解析 domain map 的 FR->SPEC 歸屬、計算未覆蓋 FR、組補法說明。"""

import re
import sys
from pathlib import Path
from typing import NamedTuple

from .fr_extract import FR_TOKEN_RE, SPEC_ID_BODY, SPEC_ID_BOUNDARY, SPEC_ID_RE, _expand_fr_token, extract_fr_ids, extract_spec_frs, extract_spec_id
from .map_locate import SYSTEM_LAYER_PATH, _parse_source_specs

HEADING_RE = re.compile(r"^(#{1,6})\s")
SECTION7_RE = re.compile(r"^#{2}\s+7[.\s]", re.MULTILINE)
SECTION7_SPEC_HEADING_RE = re.compile(rf"^###\s+{SPEC_ID_BODY}{SPEC_ID_BOUNDARY}", re.MULTILINE)
# 措辭與 doc 端 validate.py 的 LEGACY_SECTION7_HINT 一致（{name} 取代 {doc_id}）
LEGACY_SECTION7_HINT = (
    "提示: {name} 的 §7 沒有任何 SPEC 子標題，視為舊結構（範本 2.4.0 以前），略過 source_specs 比對。"
    "遷移：把 §7 單表拆成每個 spec 一組 '### SPEC-xxx' 子標題，FR 列依各 spec 原文歸屬（見 CHANGELOG 2.89.0）"
)


def section7_state(text):
    """三態：'absent'（無 §7）／'no_spec_heading'（有 §7 但無 SPEC 子標題）／'has_spec_heading'。"""
    start = SECTION7_RE.search(text)
    if start is None:
        return "absent"
    rest = text[start.end():]
    end = re.search(r"^#{2}\s", rest, re.MULTILINE)
    section = rest[: end.start()] if end else rest
    return "has_spec_heading" if SECTION7_SPEC_HEADING_RE.search(section) else "no_spec_heading"


def _line_fr_owners(line, heading_spec):
    """回傳該行每個 FR token 的（所屬 spec 或 None, FR 編號集合）。

    歸屬順序：同一行在 token 之前最近的 SPEC-NNN；否則沿用祖先標題的 spec。
    """
    for m in FR_TOKEN_RE.finditer(line):
        before = [f.group(0) for f in SPEC_ID_RE.finditer(line[: m.start()])]
        owner = before[-1].upper().rstrip("-") if before else heading_spec
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
            stack.append((level, found.group(0).upper().rstrip("-") if found else None))
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


class AttributionError(Exception):
    """歸屬無從判定（多值 source_specs 又無明示歸屬）；呼叫端印訊息並以 exit code 1 結束。"""


def _default_owner(m, spec_id):
    """整份無歸屬的檔，其 FR 的歸屬 SPEC。

    source_specs 單值：計給該 SPEC；多值：無從判定，拋 AttributionError；
    整段缺席、為 []、格式無法解析：計給受檢 SPEC（相容語意，不變）。
    """
    declared = _parse_source_specs(m.text)
    if declared and len(declared) == 1:
        return next(iter(declared))
    if declared:
        raise AttributionError(
            f"domain 覆蓋檢核失敗：{m.name} 的 source_specs 列入多個 SPEC（{', '.join(sorted(declared))}），"
            "但檔內沒有任何 SPEC 歸屬，無從判定其 FR 屬於哪一個。"
            "請在 FR 所在的章節標題含 SPEC id，或在同一行、該 FR 之前寫出 SPEC id。")
    return spec_id


def _merged_attribution(parsed_maps, spec_id):
    """於集合層合併各檔歸屬，回傳 {spec_id: FR 集合}。

    整份無歸屬的檔（系統層除外）其 FR 依 source_specs 單值歸屬（見 _default_owner）；
    檔案內有部分歸屬時，有歸屬者依歸屬，未歸屬者不計入。
    """
    merged = {}
    for m in parsed_maps:
        attributed = m.attributed
        if m.is_default_assigned and spec_id:
            owner = _default_owner(m, spec_id)
            target = "受檢 SPEC" if owner == spec_id else f"{owner}（source_specs 單值）"
            sys.stderr.write(f"domain 覆蓋檢核：{m.name} 無任何 SPEC 歸屬，其 FR 依預設計給{target}\n")
            if section7_state(m.text) == "no_spec_heading":
                sys.stderr.write(LEGACY_SECTION7_HINT.format(name=m.name) + "\n")
            attributed = {owner: m.unattributed}
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
        legacy = [m.name for m in parsed_maps if section7_state(m.text) == "no_spec_heading"]
        for name in legacy:
            sys.stderr.write(LEGACY_SECTION7_HINT.format(name=name) + "\n")
        # 到此表示非系統層的 map 皆無任何 FR 編號（有則已預設計給），只有系統層可能帶未歸屬的 FR
        sys.stderr.write("domain 覆蓋檢核：domain map 無任何 FR 歸屬到 SPEC-NNN（非系統層的 map 無任何 FR 編號），"
                         "走相容模式（不分 spec 比對，系統層出現的 FR 一律視為覆蓋）\n")
    else:
        return sorted(spec_frs - attributed.get(spec_id, set()))
    return sorted(spec_frs - extract_fr_ids("\n".join(m.text for m in parsed_maps)))


def check_domain_coverage_union(spec_text, named_texts, spec_path=None):
    """多份 map（(檔名, 內容) 清單）的覆蓋判定，聯集發生在集合層；單份 map 傳單元素清單。"""
    return _uncovered_frs(spec_text, _parse_maps(named_texts), spec_path)


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
