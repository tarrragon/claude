#!/usr/bin/env python3
"""spec validate 的 domain 覆蓋閘門：spec 的每個 FR 是否都被 domain map 的 FR->bundle 覆蓋表歸屬。

背景：一次架構檢討發現 domain 規劃缺口——spec 定義 FR、UC 定義場景，但無 domain
bundle 邊界；且 spec FR 是否全數映射到某 bundle 缺工具強制（曾靠人工四視角審查才
抓出漏覆蓋的 FR）。本檢核作為 /spec validate Layer 1 的擴充規則，機械掃描：
  1. spec 對應的 domain map 是否存在
  2. spec 每個 FR 是否出現在 domain map 的 FR 覆蓋（含標為 presentation/data 的非 domain FR）

domain map 定位：預設找 spec 同目錄的 domain-map.md，退化找 docs/domain-map.md。

另含可選檢核「事件流標定」（`--check-event-flow-labeling`）：spec 的 FR 段落若命中
事件流訊號詞（清單見 EVENT_FLOW_SIGNAL_WORDS，與 /spec validate Layer 2 維度 5「資源
競爭」共用同一份訊號詞，見 SKILL.md 維度 5 掃描說明），該 FR 須能在 domain map 的
「通道與協調圖」節（以標題文字定位，不依編號——章節編號在各專案可能已被既有內容
佔用）之「到達類別與級別實例」子表中找到對應的 FR 引用，缺者列為提醒，非阻擋。
"""

import argparse
import re
import sys
from pathlib import Path

import check_api_surface

# FR 標題容許 H3 以上任一層級（### / #### …）——真實 spec 常用 #### FR-XX:，
# 只認 H3 會使 extract_spec_frs 回空集、gate 靜默假通過（Round 2-C 實證）。
FR_HEADER_RE = re.compile(r"^#{3,}\s+(FR-\d+):", re.MULTILINE)

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


def extract_spec_frs(spec_text):
    """從 spec 的 `### FR-XX:` 標題抽出定義的 FR 編號（int 集合）。"""
    return {int(m.group(1).split("-")[1]) for m in FR_HEADER_RE.finditer(spec_text)}


def check_domain_coverage(spec_text, domain_map_text):
    """回傳 spec 定義但 domain map 未覆蓋的 FR 編號（排序 list）。"""
    spec_frs = extract_spec_frs(spec_text)
    covered = extract_fr_ids(domain_map_text)
    return sorted(spec_frs - covered)


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
    signaled = extract_event_signaled_frs(spec_text, signal_words)
    if not signaled:
        return []
    arrival_table = extract_arrival_level_table(extract_channel_section(domain_map_text))
    labeled = extract_fr_ids(arrival_table) if arrival_table else set()
    return sorted(signaled - labeled)


def locate_domain_map(spec_path, explicit):
    """定位 domain map：優先 explicit，其次 spec 同目錄，最後 docs/domain-map.md。"""
    if explicit:
        p = Path(explicit)
        return p if p.exists() else None
    same_dir = spec_path.parent / "domain-map.md"
    if same_dir.exists():
        return same_dir
    fallback = Path("docs/domain-map.md")
    return fallback if fallback.exists() else None


def _report_domain_coverage(spec_text, domain_map_path):
    """列印 FR->bundle 覆蓋檢核結果，回傳 exit code。"""
    uncovered = check_domain_coverage(spec_text, domain_map_path.read_text(encoding="utf-8"))
    if not uncovered:
        print(f"domain 覆蓋檢核通過：spec 全部 FR 皆在 {domain_map_path} 有 bundle 歸屬")
        return 0

    print(f"domain 覆蓋檢核發現 {len(uncovered)} 個 FR 未在 domain map 覆蓋：")
    for fr in uncovered:
        print(f"  FR-{fr:02d}")
    print(f"（domain map：{domain_map_path}）請於 domain map §7 FR->bundle 覆蓋表補上歸屬。")
    return 1


def _report_event_flow_labeling(spec_text, domain_map_path):
    """列印事件流標定檢核結果，回傳 exit code。性質為啟發式提醒，非阻擋。"""
    missing = check_event_flow_labeling(spec_text, domain_map_path.read_text(encoding="utf-8"))
    if not missing:
        print("事件流標定檢核通過：命中事件流訊號詞的 FR 皆在通道與協調圖節有到達類別與級別標定")
        return 0

    print(f"事件流標定檢核發現 {len(missing)} 個 FR 命中事件流訊號詞但未見通道標定（提醒，非阻擋）：")
    for fr in missing:
        print(f"  FR-{fr:02d}")
    print(f"（domain map：{domain_map_path}）請於「通道與協調圖」節之「到達類別與級別實例」子表補上標定。")
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
    spec_text = spec_path.read_text(encoding="utf-8")

    domain_map_path = locate_domain_map(spec_path, args.domain_map)
    if domain_map_path is None:
        print(
            "domain 覆蓋檢核：找不到 domain map（spec 同目錄 domain-map.md 或 "
            "docs/domain-map.md）。依 version-bootstrap Step 2.5，規劃波應先產出 domain map。"
        )
        return 1

    rc = _report_domain_coverage(spec_text, domain_map_path)
    if args.check_event_flow_labeling:
        rc = _report_event_flow_labeling(spec_text, domain_map_path) or rc
    return rc


if __name__ == "__main__":
    sys.exit(main())
