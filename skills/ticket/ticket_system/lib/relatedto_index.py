"""
relatedTo 反向索引模組

裁決一：relatedTo 儲存單向，消費端做 1-hop symmetric union。但 union 的
where 子句對單票查詢若無索引即等於全庫反查（千級票量規模下不可行）。

本模組在讀取路徑建立 relatedTo 的反向索引（被引用方 -> 引用方），讓單票查詢的
symmetric union 為 O(1) 查表，而非對整個版本目錄做 O(N) 掃描。

閉包深度依裁決一限 1-hop：僅 forward（該票自身 relatedTo）∪ backward（反向索引
查表），不對 union 結果再次展開查詢（禁遞移）。

輕量抽取：僅解析 frontmatter 的 relatedTo 欄位，不呼叫 parser.load_ticket()
（避免整份 body 解析與其他欄位驗證的額外成本）。
"""

from __future__ import annotations

import re
from typing import Dict, List, Set

import yaml

from .paths import get_tickets_dir

# 與 parser.parse_frontmatter 相同的邊界比對規則：獨占一行的 ---。
_FRONTMATTER_BOUNDARY_RE = re.compile(r"^---\s*$", re.MULTILINE)

# process-scoped 快取（比照 parser._ticket_cache 慣例）：key 為 version，
# value 為該 version 的反向索引 dict。同一 process 內重複查詢不重掃檔案系統。
_reverse_index_cache: Dict[str, Dict[str, List[str]]] = {}


def reset_reverse_index_cache() -> None:
    """清空反向索引快取（測試隔離用，比照 paths.reset_project_root_cache）。"""
    _reverse_index_cache.clear()


def _extract_related_to_only(content: str) -> List[str]:
    """輕量抽取單一 ticket md 內容的 relatedTo 清單，不解析 body 或其他欄位。

    解析失敗（YAML 錯誤、無 frontmatter）時回傳空列表而非拋例外——本模組
    僅供反向索引使用，個別票的格式錯誤不應中斷整個索引建立。
    """
    if not content.startswith("---"):
        return []
    start = _FRONTMATTER_BOUNDARY_RE.match(content)
    if start is None:
        return []
    end = _FRONTMATTER_BOUNDARY_RE.search(content, start.end())
    if end is None:
        return []
    try:
        frontmatter = yaml.safe_load(content[start.end():end.start()])
    except yaml.YAMLError:
        return []
    if not isinstance(frontmatter, dict):
        return []
    raw = frontmatter.get("relatedTo")
    if isinstance(raw, str):
        return [raw] if raw.strip() else []
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, str) and item.strip()]
    return []


def build_reverse_index(version: str) -> Dict[str, List[str]]:
    """掃描 version 的 tickets 目錄，建立 relatedTo 反向索引。

    結果依 process-scoped 快取，同一 version 重複呼叫不重掃檔案系統。

    Args:
        version: 版本號（如 "0.31.0"）

    Returns:
        dict[被引用票id] -> list[引用該票的票id]（依檔名字母序去重）。
        tickets 目錄不存在時回傳空 dict。
    """
    if version in _reverse_index_cache:
        return _reverse_index_cache[version]

    tickets_dir = get_tickets_dir(version)
    reverse: Dict[str, List[str]] = {}
    if tickets_dir.exists():
        for path in sorted(tickets_dir.glob("*.md")):
            ticket_id = path.stem
            try:
                content = path.read_text(encoding="utf-8")
            except OSError:
                continue
            for target_id in _extract_related_to_only(content):
                bucket = reverse.setdefault(target_id, [])
                if ticket_id not in bucket:
                    bucket.append(ticket_id)

    _reverse_index_cache[version] = reverse
    return reverse


def get_symmetric_related_to(
    version: str, ticket_id: str, forward: List[str]
) -> List[str]:
    """1-hop symmetric union：forward（該票自身 relatedTo）∪ backward（反向索引查表）。

    禁遞移：backward 僅取反向索引的直接查表結果，不對 union 後的結果再次展開。

    Args:
        version: 版本號
        ticket_id: 查詢票 id
        forward: 該票自身 frontmatter 的 relatedTo 清單（呼叫端傳入，避免本模組
            重複解析 target ticket 全文）

    Returns:
        去重、排除自我引用後的 relatedTo id 清單，保留 forward 優先於 backward 的順序。
    """
    reverse_index = build_reverse_index(version)
    backward = reverse_index.get(ticket_id, [])

    seen: Set[str] = set()
    result: List[str] = []
    for related_id in list(forward) + list(backward):
        if related_id == ticket_id or related_id in seen:
            continue
        seen.add(related_id)
        result.append(related_id)
    return result


__all__ = [
    "build_reverse_index",
    "get_symmetric_related_to",
    "reset_reverse_index_cache",
]
