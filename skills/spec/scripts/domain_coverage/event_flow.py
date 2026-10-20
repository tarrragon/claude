"""事件流標記檢查：FR 段落命中事件流訊號詞者，須在 domain map 通道表有到達類別與級別標定。"""

import re

import check_api_surface

from .fr_extract import extract_fr_ids

# 事件流訊號詞：與 /spec validate Layer 2 維度 5「資源競爭」共用單一常數，避免
# Layer 1 機械檢核與 Layer 2 語意維度各自維護清單而漂移（SKILL.md 維度 5 掃描說明）。
EVENT_FLOW_SIGNAL_WORDS = (
    "事件", "通知", "提示", "背景", "排程", "佇列", "推送", "webhook", "isolate",
)

# domain map 章節標題比對：以標題文字定位，不依編號（章節編號在既有專案可能已
# 被其他內容佔用，如本專案 docs/domain-map.md 的「## 2.5」已用於他途）。
CHANNEL_SECTION_TITLE_RE = re.compile(r"^(#{1,6})\s*.*通道與協調圖.*$", re.MULTILINE)
ARRIVAL_LEVEL_TABLE_TITLE_RE = re.compile(r"^(#{1,6})\s*.*到達類別與級別.*$", re.MULTILINE)


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
