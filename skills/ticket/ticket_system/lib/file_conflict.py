"""where.files 交集判定共用實作（multi-PM 協調層 Phase 2/3）。

抽取自 `commands/track_conflicts.py`（AC-3：`ticket track conflicts` 與
`ticket track runqueue --groups` 共用同一交集判定實作，禁止複製貼上）。

Phase 2 盲測實證：宣告 where.files 吻合度僅 3/10，七成 completed 票的實際
commit 超出宣告範圍，主導缺漏是「宣告實作檔、漏宣告伴生測試檔與關聯模組」。
純宣告值交集判定的錯誤方向是 false negative（宣告互斥、實際相撞），因此
本模組內建 impl→test 擴張啟發式：對每個宣告的實作檔路徑，額外推導其可能
的伴生測試檔路徑一併納入交集判定，擴大偵測面。

判定規則：
  1. 兩兩比對 where.files（原始宣告 + 啟發式衍生）——呼叫端負責篩選要
     比對的 ticket 子集（conflicts 篩 pending/in_progress，groups 篩
     blockedBy=[] pending，語意不同，本模組不內建任何狀態篩選）
  2. 路徑交集用路徑段 tuple 前綴比對（精確相符或互為上層目錄），禁用
     string startswith（避免 "lib/foo" 誤命中 "lib/foobar.dart"）；
     Phase 4 五視角審查效能組實測 `PurePosixPath` 建構為熱路徑瓶頸
     （139 票 1.28s、cProfile 318,400 次呼叫佔 16.8s），改手動 tuple
     切分 + `lru_cache` 快取（見 `_path_parts`），139 票優化後 <300ms。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# where.files 讀取
# ---------------------------------------------------------------------------


def where_files(ticket: Dict[str, Any]) -> List[str]:
    """從 ticket dict 取 where.files，相容舊逗號分隔字串格式。"""
    where = ticket.get("where") or {}
    files = where.get("files") if isinstance(where, dict) else None
    if isinstance(files, str):
        return [f.strip() for f in files.split(",") if f.strip()]
    if isinstance(files, list):
        return [str(f) for f in files]
    return []


# ---------------------------------------------------------------------------
# 路徑判定
# ---------------------------------------------------------------------------


@lru_cache(maxsize=4096)
def _path_parts(path: str) -> Tuple[str, ...]:
    """將路徑切為段 tuple 並快取（同一路徑字串在批次交集判定中會被
    `files_intersect` 重複比對數十次，快取消除重複 split，Phase 4 效能組
    量測的主要優化來源）。"""
    return tuple(p for p in path.rstrip("/").split("/") if p)


def files_intersect(path_a: str, path_b: str) -> bool:
    """路徑段 tuple 前綴比對：精確相符，或其中一者為另一者的上層目錄前綴。

    非 string startswith——"lib/foo" 與 "lib/foobar.dart" 字串前綴相符但路徑
    段不同層級，不應誤判為交集（`_path_parts` 切段後逐段比較，非字元級
    比對，天然避免此誤判）。

    兩路徑取較短者的段數 n，比較兩者前 n 段是否逐段相等——等價於「pa 是
    pb 的上層目錄前綴，或 pb 是 pa 的上層目錄前綴，或兩者相等」（原
    `PurePosixPath.parents` 判定的語意，改用 tuple slice 比較取代物件
    建構與 `.parents` 走訪）。任一路徑為空段（如空字串輸入）時僅在兩者
    皆空才視為交集，避免空 tuple 前綴恆真的邊界錯誤。
    """
    parts_a = _path_parts(path_a)
    parts_b = _path_parts(path_b)
    if not parts_a or not parts_b:
        return parts_a == parts_b
    n = min(len(parts_a), len(parts_b))
    return parts_a[:n] == parts_b[:n]


def find_nearest_tests_dir(file_path: str, project_root: Path) -> Optional[PurePosixPath]:
    """向上尋找最近的實際存在之 `tests/` 兄弟目錄（掃描真實檔案系統）。

    本專案 `tests/` 目錄一律為套件根目錄的兄弟層（如 `ticket_system/tests/`
    對應 `ticket_system/commands/`、`ticket_system/lib/` 等子目錄下的模組；
    `hooks/tests/` 對應 `hooks/` 下直接放置的檔案），並非緊鄰檔案自身目錄下
    的子目錄。

    逐層往上檢查每個祖先目錄是否有 `tests` 兄弟目錄實際存在，找到最近
    （最深）的一個即回傳；專案內找不到任何符合的 `tests/` 兄弟目錄時回傳
    None（不猜測）。
    """
    p = PurePosixPath(file_path.rstrip("/"))
    current = p.parent
    while True:
        candidate = current / "tests"
        if (project_root / candidate).is_dir():
            return candidate
        if not current.parts:
            return None
        current = current.parent


def derive_test_candidates(path: str, project_root: Optional[Path] = None) -> List[str]:
    """impl->test 擴張啟發式：由實作檔路徑推導可能的伴生測試檔路徑。

    僅覆蓋本專案已知兩種慣例，不窮舉所有語言慣例：
      - Dart：`lib/...` -> `test/..._test.dart`
      - Python：`.../X.py`（非 test_*.py / conftest.py）-> 實際存在的最近
        `tests/` 兄弟目錄下 `test_X.py`（見 `find_nearest_tests_dir`）

    未命中任何慣例、或 Python 分支找不到真實存在的 `tests/` 目錄時回傳
    空清單（不衍生候選，維持原宣告值）。`project_root` 為 None 時 Python
    分支無法驗證真實目錄結構，同樣不猜測（寧缺勿錯）。
    """
    p = PurePosixPath(path.rstrip("/"))
    candidates: List[str] = []

    if p.suffix == ".dart" and p.parts and p.parts[0] == "lib":
        rest_parts = p.parts[1:]
        if rest_parts:
            stem = PurePosixPath(rest_parts[-1]).stem
            candidate = PurePosixPath("test", *rest_parts[:-1], f"{stem}_test.dart")
            candidates.append(str(candidate))

    if p.suffix == ".py" and not p.stem.startswith("test_") and p.stem != "conftest":
        if project_root is not None:
            tests_dir = find_nearest_tests_dir(path, project_root)
            if tests_dir is not None:
                candidates.append(str(tests_dir / f"test_{p.stem}.py"))

    return candidates


def expand_files(declared: List[str], project_root: Optional[Path] = None) -> List[str]:
    """回傳宣告清單 + 啟發式衍生候選的去重聯集（保序）。"""
    expanded: List[str] = list(declared)
    for f in declared:
        expanded.extend(derive_test_candidates(f, project_root))
    seen: Set[str] = set()
    result: List[str] = []
    for f in expanded:
        if f not in seen:
            seen.add(f)
            result.append(f)
    return result


# ---------------------------------------------------------------------------
# 兩兩交集判定
# ---------------------------------------------------------------------------


def compute_pairwise_conflicts(
    tickets: List[Dict[str, Any]], project_root: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """兩兩比對 tickets 的 where.files（含擴張啟發式），回傳衝突對清單。

    呼叫端負責篩選要比對的 ticket 子集（本函式不內建任何狀態篩選，供
    conflicts 與 groups 兩種不同語意的呼叫端共用）；無宣告 where.files 的
    ticket 略過（不參與任何交集判定，等同孤立節點）；無 id（缺失或空字串）
    的 ticket 亦略過——與 `compute_parallel_groups` 的節點篩選
    （`if t.get("id")`）保持一致，避免同一批 ticket 在兩個共用同一份
    `compute_pairwise_conflicts` 輸出的呼叫端出現不同的納入結果（先前本
    函式以 `t.get("id") or ""` 容忍空 id，`compute_parallel_groups` 卻濾除
    ——空 id 邊界的兩函式納入邏輯不一致）。

    `project_root` 供 impl->test 啟發式驗證真實 `tests/` 目錄結構（見
    `derive_test_candidates`）；為 None 時該啟發式停用，僅比對原始宣告值。

    Returns:
        依 (ticket_a, ticket_b) 排序的衝突清單，每筆含 ticket_a / ticket_b /
        matched_files / heuristic_only（純宣告值互相命中則 False，僅啟發式
        衍生候選命中則 True）。
    """
    entries: List[Tuple[str, List[str], List[str]]] = []
    for t in tickets:
        tid = t.get("id")
        if not tid:
            continue
        declared = where_files(t)
        if not declared:
            continue
        entries.append((tid, declared, expand_files(declared, project_root)))

    conflicts: List[Dict[str, Any]] = []
    for i in range(len(entries)):
        for j in range(i + 1, len(entries)):
            id_a, declared_a, expanded_a = entries[i]
            id_b, declared_b, expanded_b = entries[j]
            matched_pairs: List[Tuple[str, str]] = []
            heuristic_only = True
            for fa in expanded_a:
                for fb in expanded_b:
                    if files_intersect(fa, fb):
                        matched_pairs.append((fa, fb))
                        if fa in declared_a and fb in declared_b:
                            heuristic_only = False
            if matched_pairs:
                matched_display = sorted({
                    fa if fa == fb else f"{fa} ~ {fb}" for fa, fb in matched_pairs
                })
                conflicts.append({
                    "ticket_a": id_a,
                    "ticket_b": id_b,
                    "matched_files": matched_display,
                    "heuristic_only": heuristic_only,
                })
    conflicts.sort(key=lambda c: (c["ticket_a"], c["ticket_b"]))
    return conflicts


# ---------------------------------------------------------------------------
# 共用衝突圖核心（節點 + 已判定衝突配對 -> 連通分量切分）
#
# 收斂自 runqueue --groups（本模組）與 track_parallel_check.py（union-find
# + 弱衝突深度啟發式）兩份並行分組演算法：兩端解同一圖論問題（衝突圖建構
# + 連通分量），但衝突判準刻意不同（impl->test 擴張 vs 弱衝突深度啟發式），
# 收斂只發生在圖層——本函式不解讀 `conflict_pairs` 的來源語意，兩端各自
# 決定「什麼算衝突」再把結果餵進來。
# ---------------------------------------------------------------------------


def group_by_conflict(
    ids: List[str], conflict_pairs: Iterable[Tuple[str, str]]
) -> Tuple[List[str], List[List[str]]]:
    """給定節點清單與已判定的衝突配對，切分孤立節點與連通分量。

    Args:
        ids: 節點（ticket id）清單，決定孤立節點的輸出順序（保留輸入序，
            供呼叫端自行決定後續排序策略——如依 priority 或字母序，本函式
            不代為排序）。
        conflict_pairs: `(id_a, id_b)` tuple 的可疊代序列，代表已判定的
            衝突配對（判準完全由呼叫端決定，可為 `compute_pairwise_conflicts`
            的 impl->test 擴張結果，也可為任何其他 predicate 的輸出）。

    Returns:
        (isolated, components) —— `isolated` 為無衝突邊節點，保留 `ids`
        輸入順序；`components` 為 size >= 2 的連通分量清單，每個分量內部
        依 id 字串排序，分量之間依各自最小成員排序（確定性輸出——兩份
        既有呼叫端皆依賴此排序行為，收斂時原樣保留）。
    """
    adjacency: Dict[str, Set[str]] = {i: set() for i in ids}
    for a, b in conflict_pairs:
        if a in adjacency and b in adjacency:
            adjacency[a].add(b)
            adjacency[b].add(a)

    visited: Set[str] = set()
    isolated: List[str] = []
    components: List[List[str]] = []

    # 度數 0 節點不需獨立分支：DFS 從無鄰居節點出發時 `stack` 僅含自身一次
    # 迭代，`component` 結果必為單一元素，與原本 `if not adjacency[node]`
    # 提前分支的輸出完全一致（收斂消除重複程式碼，同一結果改用單一路徑
    # 產生，degree=0 節點事後依長度分類為 isolated）。
    for node in ids:
        if node in visited:
            continue

        component: List[str] = []
        stack = [node]
        visited.add(node)
        while stack:
            current = stack.pop()
            component.append(current)
            for neighbor in adjacency[current]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    stack.append(neighbor)

        if len(component) == 1:
            isolated.append(component[0])
        else:
            component.sort()
            components.append(component)

    components.sort(key=lambda group: group[0] if group else "")
    return isolated, components


# ---------------------------------------------------------------------------
# 並行群組切分（runqueue --groups，multi-PM 協調層 Phase 3）
# ---------------------------------------------------------------------------


@dataclass
class GroupsResult:
    """`compute_parallel_groups` 回傳結構。

    Attributes:
        parallel_group: 無衝突邊的票 id 清單（保留呼叫端傳入順序，供呼叫端
            自行依 priority 等準則預排序——本函式不重排，維持單一職責）。
        sequential_groups: 各連通分量（含衝突邊）的票 id 清單，組內成員依
            id 字串排序（顯示穩定性），組間彼此無交集、可並行執行；組內
            則須序列執行。
        conflict_pairs: `compute_pairwise_conflicts` 的原始輸出，供呼叫端
            標示衝突對（父票設計要點 5：「輸出...衝突組內標示衝突對」）。
    """

    parallel_group: List[str] = field(default_factory=list)
    sequential_groups: List[List[str]] = field(default_factory=list)
    conflict_pairs: List[Dict[str, Any]] = field(default_factory=list)


def compute_parallel_groups(
    tickets: List[Dict[str, Any]], project_root: Optional[Path] = None
) -> GroupsResult:
    """依 where.files 交集切分可並行群組（父票設計要點 5）。

    建無向衝突圖（節點 = tickets 的 id，邊 = `compute_pairwise_conflicts`
    命中的兩兩交集）；連通分量（size >= 2，即含至少一條邊）即序列組——
    組內成員經由交集邊傳遞關聯，即使組內兩票本身無直接交集，仍因傳遞性
    必須序列化（例：A-B 交集、B-C 交集，A-C 縱使無交集也不可能與 B 同時
    進行）。孤立節點（度數為 0，與任何其他票皆無交集）歸入單一
    `parallel_group`，彼此兩兩必無交集，符合 AC-1「群組內兩兩 where.files
    無交集」。

    呼叫端負責篩選輸入 tickets 子集（同 `compute_pairwise_conflicts`，本
    函式不內建狀態篩選）與所需的 priority 排序（parallel_group 保留輸入
    順序）。圖建構與連通分量切分委派 `group_by_conflict`（與
    `track_parallel_check.py` 共用同一核心）。
    """
    conflict_pairs = compute_pairwise_conflicts(tickets, project_root)
    ticket_ids: List[str] = [t.get("id") for t in tickets if t.get("id")]
    pair_tuples = [(p["ticket_a"], p["ticket_b"]) for p in conflict_pairs]

    parallel_group, sequential_groups = group_by_conflict(ticket_ids, pair_tuples)

    return GroupsResult(
        parallel_group=parallel_group,
        sequential_groups=sequential_groups,
        conflict_pairs=conflict_pairs,
    )


def render_groups(result: GroupsResult) -> str:
    """渲染 `compute_parallel_groups` 結果為固定值文字（沿用 runqueue 現有
    text 輸出風格：無 emoji、章節分隔線）。供 `runqueue --groups` 直接
    輸出使用（CLI 接線見對應 spawn request）。
    """
    lines: List[str] = ["=== Parallel Groups ==="]

    lines.append(f"可並行群組（{len(result.parallel_group)} 票，兩兩無交集）：")
    if result.parallel_group:
        for tid in result.parallel_group:
            lines.append(f"  - {tid}")
    else:
        lines.append("  （無）")

    lines.append("")
    lines.append(f"序列群組（{len(result.sequential_groups)} 組，組內須依序執行）：")
    if result.sequential_groups:
        for idx, group in enumerate(result.sequential_groups, start=1):
            lines.append(f"  群組 {idx}: {', '.join(group)}")
    else:
        lines.append("  （無）")

    lines.append("")
    lines.append(f"衝突對（{len(result.conflict_pairs)} 組）：")
    if result.conflict_pairs:
        for pair in result.conflict_pairs:
            tag = " [heuristic]" if pair["heuristic_only"] else ""
            files_repr = ", ".join(pair["matched_files"])
            lines.append(f"  {pair['ticket_a']} <-> {pair['ticket_b']}{tag}: {files_repr}")
    else:
        lines.append("  （無）")

    return "\n".join(lines)


if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()
