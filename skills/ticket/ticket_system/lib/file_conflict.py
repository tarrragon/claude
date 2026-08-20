"""where.files 交集判定共用實作（multi-PM 協調層 Phase 2/3）。

抽取自 `commands/track_conflicts.py`（AC-3：`ticket track conflicts` 與
`ticket track runqueue --groups` 共用同一交集判定實作，禁止複製貼上）。

Phase 2 盲測實證：宣告 where.files 吻合度僅 3/10，七成 completed 票的實際
commit 超出宣告範圍，主導缺漏是「宣告實作檔、漏宣告伴生測試檔與關聯模組」。
純宣告值交集判定的錯誤方向是 false negative（宣告互斥、實際相撞），因此
本模組內建 impl→test 擴張啟發式：對每個宣告的實作檔路徑，額外推導其可能
的伴生測試檔路徑一併納入交集判定，擴大偵測面。

判定規則：
  1. 兩兩比對 where.files 中意圖為「寫入」的路徑集合（原始宣告 + 啟發式
     衍生；read 集合不參與衝突判定，僅供 `read_files()` 另行查詢影響面）
     ——呼叫端負責篩選要比對的 ticket 子集（conflicts 篩 pending/
     in_progress，groups 篩 blockedBy=[] pending，語意不同，本模組不內建
     任何狀態篩選）
  2. 路徑交集用路徑段 tuple 前綴比對（精確相符或互為上層目錄），禁用
     string startswith（避免 "lib/foo" 誤命中 "lib/foobar.dart"）；
     Phase 4 五視角審查效能組實測 `PurePosixPath` 建構為熱路徑瓶頸
     （139 票 1.28s、cProfile 318,400 次呼叫佔 16.8s），改手動 tuple
     切分 + `lru_cache` 快取（見 `_path_parts`），139 票優化後 <300ms。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# where.files 讀寫意圖解析
# ---------------------------------------------------------------------------

# 標記只在字串「結尾」被辨識，且不可被反斜線跳脫（`(?<!\\)`）——字串中段
# 出現同形字元（如路徑段本身含 "::read"）不觸發切分，滿足「路徑本身含
# 分隔符字元時解析正確」的要求。
_INTENT_MARKER_RE = re.compile(r"(?<!\\)::(read|write)$")

# 跳脫還原：路徑本身需要字面上以 "::read" / "::write" 結尾時，票面寫
# `\::read`（反斜線 + 分隔符），上面的 `_INTENT_MARKER_RE` 因負向零寬斷言
# 而不會將其誤判為標記；此處於未命中標記分支還原跳脫，去掉反斜線後保留
# 字面路徑，同時不覆寫意圖（維持 type 推導的預設值）。
_ESCAPED_MARKER_RE = re.compile(r"\\(::(?:read|write))$")


def _raw_where_files(ticket: Dict[str, Any]) -> List[str]:
    """取 where.files 原始字串清單（未剝除意圖標記），相容舊逗號分隔字串格式。"""
    where = ticket.get("where") or {}
    files = where.get("files") if isinstance(where, dict) else None
    if isinstance(files, str):
        return [f.strip() for f in files.split(",") if f.strip()]
    if isinstance(files, list):
        return [str(f) for f in files]
    return []


def parse_file_intent(raw: str) -> Tuple[str, Optional[str]]:
    """解析單一 where.files 原始字串，回傳 (純路徑, 覆寫意圖)。

    覆寫意圖僅在字串結尾出現未跳脫的 `::read` / `::write` 時回傳對應值；
    否則回傳 None，交由呼叫端套用 type 推導的預設方向。無法辨識為合法
    標記的後綴（如 `::readonly`）一律視為路徑的一部分（fail-safe：寧可
    當成路徑，不可當成標記而丟失路徑片段）。
    """
    match = _INTENT_MARKER_RE.search(raw)
    if match:
        return raw[: match.start()], match.group(1)
    return _ESCAPED_MARKER_RE.sub(r"\1", raw), None


def _default_intent(ticket: Dict[str, Any]) -> str:
    """由 ticket type 推導預設讀寫意圖：ANA 為 read，其餘（含 IMP / DOC /
    ADJ 及無 type 者）為 write。

    無 type 者刻意保守判為 write（而非 read）：判為 write 只會多攔一次
    （false positive，並行安全判定多一次不必要的序列化），判為 read 會
    漏放一次真實衝突（false negative，兩票同時寫入同一檔案未被攔下）。
    兩個方向的錯誤代價不對稱——後者可能導致寫入衝突或資料遺失，前者僅
    犧牲一點並行效率，故無 type 與非 ANA 型別一律預設 write，不可「優化」
    成 read。
    """
    return "read" if ticket.get("type") == "ANA" else "write"


def _file_intents(ticket: Dict[str, Any]) -> List[Tuple[str, str]]:
    """回傳 [(純路徑, 最終意圖)]，意圖 = 逐檔標記覆寫，否則 type 預設。"""
    default = _default_intent(ticket)
    result: List[Tuple[str, str]] = []
    for raw in _raw_where_files(ticket):
        path, override = parse_file_intent(raw)
        result.append((path, override or default))
    return result


# ---------------------------------------------------------------------------
# where.files 讀取
# ---------------------------------------------------------------------------


def where_files(ticket: Dict[str, Any]) -> List[str]:
    """從 ticket dict 取 where.files 純路徑清單，相容舊逗號分隔字串格式。

    剝離逐檔意圖標記（若有）後回傳，對無標記的票逐字不變——既有取全部
    路徑的呼叫端（`lib/lease.py`、`commands/track_conflicts.py` 等）語意
    不變，標記僅對 `write_files` / `read_files` 兩個新查詢介面可見。
    """
    return [path for path, _ in _file_intents(ticket)]


def write_files(ticket: Dict[str, Any]) -> List[str]:
    """取 where.files 中意圖為寫入的純路徑清單（type 預設為 write 或逐檔標記覆寫為 write）。"""
    return [path for path, intent in _file_intents(ticket) if intent == "write"]


def read_files(ticket: Dict[str, Any]) -> List[str]:
    """取 where.files 中意圖為唯讀的純路徑清單（type 為 ANA 或逐檔標記覆寫為 read）。"""
    return [path for path, intent in _file_intents(ticket) if intent == "read"]


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
    conflicts 與 groups 兩種不同語意的呼叫端共用）；無宣告 write 檔案（`ANA`
    型全唯讀宣告，或逐檔標記全覆寫為 read）的 ticket 略過（不參與任何交集
    判定，等同孤立節點）；無 id（缺失或空字串）的 ticket 亦略過——與
    `compute_parallel_groups` 的節點篩選（`if t.get("id")`）保持一致，避免
    同一批 ticket 在兩個共用同一份 `compute_pairwise_conflicts` 輸出的呼叫端
    出現不同的納入結果（先前本函式以 `t.get("id") or ""` 容忍空 id，
    `compute_parallel_groups` 卻濾除——空 id 邊界的兩函式納入邏輯不一致）。

    比對核心改為雙方 write 集合的交集（僅比對意圖為寫入的路徑，read 集合
    不參與衝突判定），ANA 票的唯讀宣告不再觸發假陽性警告——read 集合仍可
    經 `read_files()` 另行查詢供影響面分析，不受本函式影響。

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
        declared = write_files(t)
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
        parallel_group: 可同時進行的票 id 清單（保留呼叫端傳入順序，供
            呼叫端自行依 priority 等準則預排序——本函式不重排，維持單一
            職責）。集合內任兩票皆無衝突邊，為全域貪婪獨立集走訪選中的
            節點（含孤立節點，度數 0 必定入選）。
        not_selected: 貪婪獨立集走訪後未選入 `parallel_group` 的票 id 清單
            （本輪判定為與已選票有直接衝突，非「彼此之間皆須序列執行」
            ——未選入的票兩兩之間可能仍無衝突邊，只是與本批已選票衝突而
            落選）。攤平為單一清單並依 id 字串排序（確定性輸出，不再以
            連通分量分組呈現——分量邊界編碼的是傳遞閉包，與本函式「僅
            直接衝突節點互斥」的立論相悖，見同批收斂說明）。
        conflict_pairs: `compute_pairwise_conflicts` 的原始輸出，供呼叫端
            標示衝突對（父票設計要點 5：「輸出...衝突組內標示衝突對」）。
    """

    parallel_group: List[str] = field(default_factory=list)
    not_selected: List[str] = field(default_factory=list)
    conflict_pairs: List[Dict[str, Any]] = field(default_factory=list)


def _greedy_independent_set(
    ordered_nodes: List[str], adjacency: Dict[str, Set[str]]
) -> List[str]:
    """在 `adjacency` 描述的衝突圖上，依 `ordered_nodes` 順序貪婪走訪選取
    極大獨立集：逐一檢視節點，若尚未被先前選中節點的鄰居排除即選入，並
    立即排除其所有鄰居。呼叫端負責決定 `ordered_nodes` 的順序（如依
    priority 排序），選取結果天然反映該順序的優先權。
    """
    selected: List[str] = []
    excluded: Set[str] = set()
    for node in ordered_nodes:
        if node in excluded:
            continue
        selected.append(node)
        excluded.update(adjacency.get(node, ()))
    return selected


def compute_parallel_groups(
    tickets: List[Dict[str, Any]], project_root: Optional[Path] = None
) -> GroupsResult:
    """依 where.files 交集切分可並行群組（父票設計要點 5；貪婪極大獨立集
    取代連通分量作為可並行判定）。

    建無向衝突圖（節點 = tickets 的 id，邊 = `compute_pairwise_conflicts`
    命中的兩兩交集），對全體節點依 `tickets` 輸入序（供呼叫端依 priority
    等準則預排序）做單次全域貪婪獨立集走訪：選中節點併入 `parallel_group`，
    落選節點併入 `not_selected`——僅直接衝突的節點對互斥，落選只代表與
    已選票有直接衝突邊，不代表落選票彼此之間也須序列（見 `GroupsResult`
    docstring）。孤立節點（度數為 0）必定入選（`excluded` 集合恆不含
    它們），故不需先切連通分量再逐分量走訪：貪婪的排除只沿邊傳播，
    邊不跨連通分量，逐分量走訪與單次全域走訪在任何輸入下同構（含選取
    順序），分量切分對 `parallel_group` / `not_selected` 是可證明的
    no-op（PM 5000 次隨機圖實測零不一致）。

    呼叫端負責篩選輸入 tickets 子集（同 `compute_pairwise_conflicts`，本
    函式不內建狀態篩選）與所需的 priority 排序（`parallel_group` 保留輸入
    順序，不重排）。`group_by_conflict` 的連通分量切分不再用於本函式，
    但簽章與行為原樣保留供 `track_parallel_check.py` 獨立使用。
    """
    conflict_pairs = compute_pairwise_conflicts(tickets, project_root)
    ticket_ids: List[str] = [t.get("id") for t in tickets if t.get("id")]
    pair_tuples = [(p["ticket_a"], p["ticket_b"]) for p in conflict_pairs]

    adjacency: Dict[str, Set[str]] = {i: set() for i in ticket_ids}
    for a, b in pair_tuples:
        if a in adjacency and b in adjacency:
            adjacency[a].add(b)
            adjacency[b].add(a)

    parallel_group = _greedy_independent_set(ticket_ids, adjacency)
    selected_ids: Set[str] = set(parallel_group)
    not_selected = sorted(i for i in ticket_ids if i not in selected_ids)

    return GroupsResult(
        parallel_group=parallel_group,
        not_selected=not_selected,
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
    lines.append(f"本輪未選入可並行集合（{len(result.not_selected)} 票）：")
    if result.not_selected:
        for tid in result.not_selected:
            lines.append(f"  - {tid}")
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
