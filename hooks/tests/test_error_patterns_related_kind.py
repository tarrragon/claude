"""error-pattern related 欄位 kind 標記與雙向性檢查測試。

背景：related 同時承載引註（單向合法）與姊妹關係（應雙向），舊檢查以 created
相差 7 天近似同批次，誤判 20～30 個百分點。結構化條目以 `kind` 明示語意：
- sibling：不論日期，對方未回指即報單向
- citation：單向合法，不報
- unknown／舊格式（純 ID）：沿用 7 天窗口

驗證範圍：
- parse_related_entries 解析 block list 結構化條目與舊格式混寫
- parse_related_field 對結構化條目仍回傳 ID 集合（舊呼叫端相容）
- check_related_bidirectional：sibling 正向對照（跨窗口仍報）、citation 正向對照
  （窗口內也不報）、unknown 與舊格式行為不變
- 不合法的 kind 值視為 unknown
"""

import importlib.util
import sys
from datetime import date
from pathlib import Path

_HOOKS_DIR = Path(__file__).parent.parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

_spec = importlib.util.spec_from_file_location(
    "error_patterns_index_consistency_check_hook_kind",
    _HOOKS_DIR / "error-patterns-index-consistency-check-hook.py",
)
_hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_hook)

_MIXED = (
    "id: PC-001\n"
    "related:\n"
    "  - id: PC-002\n"
    "    kind: sibling\n"
    "  - id: PC-003\n"
    "    kind: citation\n"
    "  - PC-004\n"
    "  - id: PC-005\n"
    "    kind: bogus\n"
    "created: 2026-08-18\n"
)


def test_parse_entries_structured_and_legacy():
    assert _hook.parse_related_entries(_MIXED) == {
        "PC-002": "sibling",
        "PC-003": "citation",
        "PC-004": "unknown",
        "PC-005": "unknown",
    }


def test_parse_entries_inline_legacy_is_unknown():
    text = "id: PC-001\nrelated: [PC-002, PC-BAL-003]\n"
    assert _hook.parse_related_entries(text) == {"PC-002": "unknown", "PC-BAL-003": "unknown"}


def test_parse_field_still_returns_id_set():
    assert _hook.parse_related_field(_MIXED) == {"PC-002", "PC-003", "PC-004", "PC-005"}


def _map(entries):
    """entries: {id: (related_ids, created)} → related_map 三元組。"""
    return {k: (set(v[0]), v[1], f"process-compliance/{k}.md") for k, v in entries.items()}


_FAR_A = date(2026, 1, 1)
_FAR_B = date(2026, 6, 1)  # 超出 7 天窗口
_NEAR = date(2026, 1, 3)  # 窗口內


def test_sibling_one_way_reported_even_outside_window():
    related_map = _map({"PC-001": (["PC-002"], _FAR_A), "PC-002": ([], _FAR_B)})
    kinds = {"PC-001": {"PC-002": "sibling"}}
    assert _hook.check_related_bidirectional(related_map, kinds) == [
        ("PC-001", "PC-002", "process-compliance/PC-001.md")
    ]


def test_sibling_one_way_reported_when_created_missing():
    related_map = _map({"PC-001": (["PC-002"], None), "PC-002": ([], None)})
    kinds = {"PC-001": {"PC-002": "sibling"}}
    assert len(_hook.check_related_bidirectional(related_map, kinds)) == 1


def test_sibling_bidirectional_not_reported():
    related_map = _map({"PC-001": (["PC-002"], _FAR_A), "PC-002": (["PC-001"], _FAR_B)})
    kinds = {"PC-001": {"PC-002": "sibling"}, "PC-002": {"PC-001": "citation"}}
    assert _hook.check_related_bidirectional(related_map, kinds) == []


def test_citation_one_way_not_reported_inside_window():
    """正向對照：同一組在窗口內、無 kind 時會報；標為 citation 後不報。"""
    related_map = _map({"PC-001": (["PC-002"], _FAR_A), "PC-002": ([], _NEAR)})
    assert len(_hook.check_related_bidirectional(related_map)) == 1
    kinds = {"PC-001": {"PC-002": "citation"}}
    assert _hook.check_related_bidirectional(related_map, kinds) == []


def test_unknown_keeps_window_behavior():
    related_map = _map({"PC-001": (["PC-002"], _FAR_A), "PC-002": ([], _FAR_B)})
    kinds = {"PC-001": {"PC-002": "unknown"}}
    assert _hook.check_related_bidirectional(related_map, kinds) == []
    near = _map({"PC-001": (["PC-002"], _FAR_A), "PC-002": ([], _NEAR)})
    assert len(_hook.check_related_bidirectional(near, kinds)) == 1


def test_collect_fills_kinds_out(tmp_path):
    cat = tmp_path / "error-patterns" / "process-compliance"
    cat.mkdir(parents=True)
    (cat / "PC-001-a.md").write_text(f"---\n{_MIXED}---\n\n# 標題\n", encoding="utf-8")
    kinds_out = {}
    related_map = _hook.collect_related_map(tmp_path / "error-patterns", kinds_out=kinds_out)
    assert related_map["PC-001"][0] == {"PC-002", "PC-003", "PC-004", "PC-005"}
    assert kinds_out["PC-001"]["PC-002"] == "sibling"
    assert kinds_out["PC-001"]["PC-003"] == "citation"
