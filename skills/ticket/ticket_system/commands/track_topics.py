"""ticket track topics / topic 命令。

背景：用戶裁示——多 session 的目的是處理多個任務群組而非同一群組內的
任務，每個群組須有明確的任務鏈 map 而非單純列表。既有 `tree`/`chain`/
`deps` 皆為單票視角須先知根 ID，無指令可列舉主題。主題歸屬資料已由
`lib/topic_assignments.py`（ticket_id -> topic 映射）與
`lib/topic_registry.py`（主題名去重清單）交付，本模組是純讀取的視圖層，
不新增任何隔離層，亦不寫入任何來源檔（ticket md / assignment log /
topics-registry.txt 皆不被開啟為寫入目標）。

兩個命令：
    topics
        列出全部主題：票數、status 分佈、組內最高 priority、in_progress
        佔用票的 lease 狀態、未歸屬（無主題標記）票數。
    topic <name>
        單一主題的任務鏈 map：以 `blockedBy` 為邊建 DAG，樹狀縮排呈現，
        每節點附 status / priority / blockedBy。

設計點（Solution 記錄理由）：

    邊定義 —— 同主題票之間 blockedBy 指向主題外的票如何呈現：
        票面 blockedBy 語意上可能指向不屬同一主題的票（任務鏈本就可能
        跨主題協作，非設計缺陷）。若直接捨棄外部邊，會讓讀者誤以為某票
        無任何前置依賴；若展開外部票的完整子樹，則單一主題視圖會擴散
        成跨主題大圖，違背「主題視圖」的範圍邊界。折衷：外部 blockedBy
        僅以節點自身屬性列出（不展開為子節點），並在 tree 縮排結構之外
        另立「外部依賴」章節統整列出，讓讀者知道有跨主題依賴存在但不
        混淆本主題內部的鏈結構。tree 結構本身只由「主題內部」blockedBy
        邊構成。

    未歸屬票的呈現位置 —— 獨立列或摘要計數：
        採摘要計數（`unassigned_count`），不逐票展開為獨立列。理由：
        `topics` 命令的定位是「主題總覽」，逐票列出未歸屬票會與
        `ticket track list --status pending` 等既有全票視圖重複；讀者
        需要未歸屬票細節時，既有指令已可查（`list`/`runqueue` 等），
        本命令僅需讓讀者知道「有多少票尚未分類」以評估回填缺口大小。
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ticket_system.constants import STATUS_IN_PROGRESS
from ticket_system.lib import lease
from ticket_system.lib.priority_utils import highest_priority as _highest_priority
from ticket_system.lib.ticket_loader import list_tickets
from ticket_system.lib.topic_assignments import list_assignments
from ticket_system.lib.topic_registry import list_topics
from ticket_system.lib.version import get_active_versions

FORMAT_TABLE = "table"
FORMAT_JSON = "json"


# ---------------------------------------------------------------------------
# 資料蒐集（version-agnostic，與 track_conflicts._gather_tickets 同款）
# ---------------------------------------------------------------------------


def _gather_tickets(explicit_version: Optional[str]) -> List[Dict[str, Any]]:
    if explicit_version:
        versions = [explicit_version]
    else:
        versions = get_active_versions() or []
    aggregated: List[Dict[str, Any]] = []
    for version in versions:
        aggregated.extend(list_tickets(version) or [])
    return aggregated


# ---------------------------------------------------------------------------
# topics：主題摘要視圖
# ---------------------------------------------------------------------------


def build_topic_summary(
    tickets: List[Dict[str, Any]],
    assignments: Dict[str, str],
    topics: List[str],
    registry: Dict[str, Any],
    pm_registry: Any,
    now: datetime,
) -> Dict[str, Any]:
    """建立主題摘要（純函式，便於測試）。

    `topics` 取 `list_topics()` 與 assignments 值域的聯集——理論上
    `append_assignment` 會同步註冊主題至中央清單，兩者應恆一致；聯集是
    防禦性處理，避免中央清單因外部因素（手動編輯、回填中斷）落後於
    assignment log 時，仍已被指派的主題從摘要中消失。
    """
    topic_names = sorted(set(topics) | set(assignments.values()))
    tickets_by_topic: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    unassigned_count = 0
    for ticket in tickets:
        topic = assignments.get(ticket.get("id", ""))
        if topic is None:
            unassigned_count += 1
            continue
        tickets_by_topic[topic].append(ticket)

    rows: List[Dict[str, Any]] = []
    for topic in topic_names:
        topic_tickets = tickets_by_topic.get(topic, [])
        status_counts = dict(Counter(t.get("status") for t in topic_tickets))
        in_progress_rows = [
            {
                "ticket_id": t.get("id"),
                "lease_state": lease.determine_lease_state(
                    registry, t.get("id"), pm_registry, now
                ),
            }
            for t in topic_tickets
            if t.get("status") == STATUS_IN_PROGRESS
        ]
        rows.append(
            {
                "topic": topic,
                "ticket_count": len(topic_tickets),
                "status_counts": status_counts,
                "highest_priority": _highest_priority(topic_tickets),
                "in_progress": in_progress_rows,
            }
        )

    return {"topics": rows, "unassigned_count": unassigned_count}


def _render_topics_table(summary: Dict[str, Any]) -> str:
    lines: List[str] = ["=== Topics ==="]
    rows = summary.get("topics") or []
    if not rows:
        lines.append("（無已標記主題）")
    for row in rows:
        status_repr = ", ".join(
            f"{status}={count}" for status, count in sorted(row["status_counts"].items())
        ) or "-"
        priority_repr = row["highest_priority"] or "-"
        lines.append(
            f"  {row['topic']}：{row['ticket_count']} 票 "
            f"[{status_repr}] 最高優先級={priority_repr}"
        )
        for ip in row["in_progress"]:
            lines.append(f"    in_progress: {ip['ticket_id']} (lease={ip['lease_state']})")
    lines.append(f"未歸屬票數: {summary.get('unassigned_count', 0)}")
    return "\n".join(lines)


def execute_topics(args: argparse.Namespace) -> int:
    """執行 `ticket track topics`（純讀取，不寫任何 ticket 檔或歸屬來源檔）。"""
    fmt = getattr(args, "format", FORMAT_TABLE) or FORMAT_TABLE
    explicit_version = getattr(args, "version", None)

    tickets = _gather_tickets(explicit_version)
    assignments = list_assignments()
    topics = list_topics()
    registry, pm_registry = lease.load_registry_snapshot()
    now = getattr(args, "_now", None) or datetime.now(timezone.utc)

    summary = build_topic_summary(tickets, assignments, topics, registry, pm_registry, now)

    if fmt == FORMAT_JSON:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(_render_topics_table(summary))
    return 0


# ---------------------------------------------------------------------------
# topic <name>：單一主題任務鏈 map
# ---------------------------------------------------------------------------


def build_topic_chain(
    topic_name: str,
    tickets: List[Dict[str, Any]],
    assignments: Dict[str, str],
) -> Dict[str, Any]:
    """建立單一主題的任務鏈 map（純函式，便於測試）。

    邊定義：僅同主題票之間的 `blockedBy` 構成 tree 結構；跨主題的
    `blockedBy` 目標另存 `external_blockers`（node -> 外部 ticket_id 清單），
    不展開為子節點（理由見模組 docstring「邊定義」段）。

    Returns:
        {
            "topic": str,
            "nodes": {ticket_id: {"status", "priority", "blockedBy"}},
            "roots": [ticket_id, ...],           # 無主題內部前置依賴的票
            "children": {ticket_id: [child_id, ...]},
            "external_blockers": {ticket_id: [外部 ticket_id, ...]},
        }
    """
    topic_tickets = [t for t in tickets if assignments.get(t.get("id", "")) == topic_name]
    id_set = {t.get("id") for t in topic_tickets}
    nodes: Dict[str, Dict[str, Any]] = {}
    children: Dict[str, List[str]] = defaultdict(list)
    external_blockers: Dict[str, List[str]] = {}
    roots: List[str] = []

    for t in topic_tickets:
        tid = t.get("id")
        blocked_by = list(t.get("blockedBy") or [])
        nodes[tid] = {
            "status": t.get("status"),
            "priority": t.get("priority"),
            "blockedBy": blocked_by,
        }
        in_topic = [b for b in blocked_by if b in id_set]
        ext = [b for b in blocked_by if b not in id_set]
        if ext:
            external_blockers[tid] = ext
        if not in_topic:
            roots.append(tid)
        for blocker in in_topic:
            children[blocker].append(tid)

    return {
        "topic": topic_name,
        "nodes": nodes,
        "roots": sorted(roots),
        "children": {k: sorted(v) for k, v in children.items()},
        "external_blockers": external_blockers,
    }


def _render_chain_node(
    tid: str,
    chain: Dict[str, Any],
    depth: int,
    lines: List[str],
    ancestors: frozenset,
) -> None:
    node = chain["nodes"][tid]
    indent = "  " * depth
    blocked_by_repr = ", ".join(node["blockedBy"]) if node["blockedBy"] else "-"
    lines.append(
        f"{indent}- {tid} [status={node['status']} priority={node['priority'] or '-'} "
        f"blockedBy={blocked_by_repr}]"
    )
    if tid in ancestors:
        # 循環防護：blockedBy 資料若含環，停止繼續展開該分支，不無限遞迴。
        lines.append(f"{indent}  (偵測到循環依賴，停止展開)")
        return
    for child in chain["children"].get(tid, []):
        _render_chain_node(child, chain, depth + 1, lines, ancestors | {tid})


def _render_chain_table(chain: Dict[str, Any]) -> str:
    lines: List[str] = [f"=== Topic: {chain['topic']} ==="]
    if not chain["nodes"]:
        lines.append("（無票屬於此主題）")
        return "\n".join(lines)
    for root in chain["roots"]:
        _render_chain_node(root, chain, 0, lines, frozenset())
    if chain["external_blockers"]:
        lines.append("外部依賴:")
        for tid, ext_ids in sorted(chain["external_blockers"].items()):
            lines.append(f"  {tid} <- {', '.join(ext_ids)}")
    return "\n".join(lines)


def execute_topic(args: argparse.Namespace) -> int:
    """執行 `ticket track topic <name>`（純讀取，不寫任何 ticket 檔或歸屬來源檔）。"""
    fmt = getattr(args, "format", FORMAT_TABLE) or FORMAT_TABLE
    explicit_version = getattr(args, "version", None)
    topic_name = args.topic

    tickets = _gather_tickets(explicit_version)
    assignments = list_assignments()
    chain = build_topic_chain(topic_name, tickets, assignments)

    if fmt == FORMAT_JSON:
        print(json.dumps(chain, ensure_ascii=False, indent=2))
    else:
        print(_render_chain_table(chain))
    return 0 if chain["nodes"] else 1


# ---------------------------------------------------------------------------
# 註冊
# ---------------------------------------------------------------------------


def register_topics(subparsers: argparse._SubParsersAction) -> None:
    """註冊 `topics` 與 `topic` 兩個唯讀子命令 parser。

    dispatch 由 track.py 的 `_create_version_agnostic_handlers()` dict 統一
    處理（同 `conflicts`/`sessions` 等既有 version-agnostic 命令慣例），
    本函式僅建立 parser 與參數，不用 `set_defaults(func=...)`（該模式在
    本檔案未被其他命令採用）。
    """
    p_topics = subparsers.add_parser(
        "topics",
        help="列出全部主題（票數、status 分佈、最高 priority、in_progress lease 狀態、未歸屬票數）",
    )
    p_topics.add_argument("--version", default=None, help="指定版本（覆蓋自動偵測 active 版本）")
    p_topics.add_argument(
        "--format",
        choices=[FORMAT_TABLE, FORMAT_JSON],
        default=FORMAT_TABLE,
        help=f"輸出格式（預設 {FORMAT_TABLE}）",
    )

    p_topic = subparsers.add_parser(
        "topic",
        help="檢視單一主題的任務鏈 map（以 blockedBy 為邊，樹狀縮排呈現 status/priority/blockedBy）",
    )
    p_topic.add_argument("topic", help="主題名（與 topic_registry 中儲存的原始形式相符）")
    p_topic.add_argument("--version", default=None, help="指定版本（覆蓋自動偵測 active 版本）")
    p_topic.add_argument(
        "--format",
        choices=[FORMAT_TABLE, FORMAT_JSON],
        default=FORMAT_TABLE,
        help=f"輸出格式（預設 {FORMAT_TABLE}）",
    )


if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit

    print_not_executable_and_exit()
