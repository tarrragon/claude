"""ticket track parallel-check 命令（0.18.0-W17-203.1）。

偵測目標 ticket 的 children（或同 parent 兄弟）pending 集合中，
依 ``where.files`` 路徑前綴判斷哪些可平行派發、哪些互相衝突，
輔助 PM 套用 ``.claude/pm-rules/askuserquestion-rules.md`` 規則 7。

輸出三章節：
- 可平行派發（檔案互斥的單身節點）
- 衝突任務（union-find 連通分量，每組僅能單一派發）
- 單獨派發（無 sibling 可比對者）

額外 PC-137 警告：可平行集合中 >= 3 個 ticket 觸及 ``.claude/`` 時建議拆批至 <= 2。

退出碼：
- 0：分析成功（不論是否有衝突）
- 1：目標 ticket 不存在 / 無 children
- 2：IO / 格式錯誤
"""

from __future__ import annotations

import argparse
import sys
from pathlib import PurePosixPath
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from ticket_system.lib.id_parser import extract_id_components
from ticket_system.lib.ticket_loader import list_tickets

# 共同祖先深度閾值：>= 3 段路徑視為同目錄弱衝突
# 例：.claude/skills/ticket/ 為 3 段，視為同模組
_SHARED_ANCESTOR_DEPTH = 3

# PC-137 並行 .claude/ Edit 上限
_PC137_PARALLEL_LIMIT = 2


# ---------------------------------------------------------------------------
# 資料模型
# ---------------------------------------------------------------------------

def _extract_files(ticket: Dict[str, Any]) -> List[str]:
    """從 ticket dict 取出 where.files 清單，容錯不同來源。"""
    where = ticket.get("where") or {}
    files = where.get("files") if isinstance(where, dict) else None
    if not isinstance(files, list):
        return []
    return [str(f) for f in files if isinstance(f, (str, PurePosixPath))]


def _normalize_path(raw: str) -> PurePosixPath:
    """以 PurePosixPath 標準化路徑，避免 string startswith 誤判（規則層要求）。"""
    return PurePosixPath(raw.strip().strip("/"))


def _path_conflict(a: PurePosixPath, b: PurePosixPath) -> bool:
    """單一路徑對的衝突判定。

    - 完全相等 → 強衝突
    - 一方為另一方祖先 → 強衝突（如 dir/ vs dir/file）
    - 最深共同祖先深度 >= ``_SHARED_ANCESTOR_DEPTH`` → 弱衝突
    """
    if a == b:
        return True
    try:
        a.relative_to(b)
        return True
    except ValueError:
        pass
    try:
        b.relative_to(a)
        return True
    except ValueError:
        pass

    a_parts = a.parts
    b_parts = b.parts
    common = 0
    for x, y in zip(a_parts, b_parts):
        if x != y:
            break
        common += 1
    return common >= _SHARED_ANCESTOR_DEPTH


def _tickets_conflict(files_a: Sequence[str], files_b: Sequence[str]) -> Optional[str]:
    """回傳第一個觸發衝突的描述，None 表示互斥。"""
    for fa in files_a:
        pa = _normalize_path(fa)
        for fb in files_b:
            pb = _normalize_path(fb)
            if _path_conflict(pa, pb):
                return f"{fa} <-> {fb}"
    return None


# ---------------------------------------------------------------------------
# Union-Find
# ---------------------------------------------------------------------------

class _UnionFind:
    def __init__(self, ids: Iterable[str]) -> None:
        self._parent: Dict[str, str] = {i: i for i in ids}

    def find(self, x: str) -> str:
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]
            x = self._parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self._parent[ra] = rb

    def groups(self) -> Dict[str, List[str]]:
        out: Dict[str, List[str]] = {}
        for k in self._parent:
            root = self.find(k)
            out.setdefault(root, []).append(k)
        return out


# ---------------------------------------------------------------------------
# 主分析邏輯
# ---------------------------------------------------------------------------

def _collect_candidates(
    target_id: str,
    tickets: Sequence[Dict[str, Any]],
) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    """找到 target 與其子任務（或同 parent 兄弟）的 pending 集合。"""
    by_id: Dict[str, Dict[str, Any]] = {
        t["id"]: t for t in tickets if isinstance(t.get("id"), str)
    }
    target = by_id.get(target_id)
    if target is None:
        return None, []

    child_ids = [c for c in (target.get("children") or []) if isinstance(c, str)]
    candidates: List[Dict[str, Any]] = []
    if child_ids:
        candidates = [by_id[c] for c in child_ids if c in by_id]
    else:
        parent_id = target.get("parent_id")
        if parent_id:
            candidates = [
                t for t in tickets
                if t.get("parent_id") == parent_id and t.get("id") != target_id
            ]

    pending = [t for t in candidates if t.get("status") == "pending"]
    return target, pending


def analyze_parallel(
    target_id: str,
    tickets: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    """純函式核心：回傳分組結果與 PC-137 警告。

    結構：
    {
        "target": <dict|None>,
        "pending": [<ticket>...],
        "conflict_groups": [[id1, id2, ...], ...],  # 各分量 >= 2
        "parallel": [<ticket>...],  # 連通分量大小為 1 的單身節點
        "alone": [],  # 預留：無 sibling 可比對的情境
        "pc137_warning": bool,
        "pc137_count": int,
        "conflict_reasons": {(a, b): "..."},
    }
    """
    target, pending = _collect_candidates(target_id, tickets)

    if target is None or not pending:
        return {
            "target": target,
            "pending": pending,
            "conflict_groups": [],
            "parallel": [],
            "pc137_warning": False,
            "pc137_count": 0,
            "conflict_reasons": {},
        }

    pending_by_id = {t["id"]: t for t in pending}
    files_map = {t["id"]: _extract_files(t) for t in pending}

    uf = _UnionFind(pending_by_id.keys())
    reasons: Dict[Tuple[str, str], str] = {}
    ids = list(pending_by_id.keys())
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = ids[i], ids[j]
            reason = _tickets_conflict(files_map[a], files_map[b])
            if reason:
                uf.union(a, b)
                reasons[(a, b)] = reason

    groups = uf.groups()
    conflict_groups: List[List[str]] = []
    parallel_ids: List[str] = []
    for members in groups.values():
        if len(members) >= 2:
            conflict_groups.append(sorted(members))
        else:
            parallel_ids.extend(members)

    conflict_groups.sort()
    parallel_ids.sort()
    parallel_tickets = [pending_by_id[i] for i in parallel_ids]

    # PC-137：可平行集合中 .claude/ 觸及計數
    pc137_count = sum(
        1 for tid in parallel_ids
        if any(
            _normalize_path(f).parts[:1] == (".claude",)
            for f in files_map[tid]
        )
    )
    pc137_warning = pc137_count >= 3

    return {
        "target": target,
        "pending": pending,
        "conflict_groups": conflict_groups,
        "parallel": parallel_tickets,
        "pc137_warning": pc137_warning,
        "pc137_count": pc137_count,
        "conflict_reasons": reasons,
    }


# ---------------------------------------------------------------------------
# 輸出格式化
# ---------------------------------------------------------------------------

def _format_files(files: Sequence[str]) -> str:
    return "[" + ", ".join(files) + "]" if files else "[]"


def _render(result: Dict[str, Any], target_id: str) -> str:
    lines: List[str] = []
    lines.append(f"=== parallel-check {target_id} ===")
    lines.append("")

    parallel = result["parallel"]
    lines.append(f"[可平行派發] {len(parallel)} ticket(s)（檔案互斥）")
    for t in parallel:
        files = _extract_files(t)
        lines.append(f"  - {t['id']}  files={_format_files(files)}")
    if not parallel:
        lines.append("  （無）")

    groups = result["conflict_groups"]
    lines.append("")
    lines.append(f"[衝突任務] {len(groups)} group(s)")
    reasons = result["conflict_reasons"]
    for idx, members in enumerate(groups, 1):
        # 找這個 group 內第一個有 reason 的描述
        sample_reason = ""
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                key = (members[i], members[j])
                if key in reasons:
                    sample_reason = reasons[key]
                    break
            if sample_reason:
                break
        suffix = f"（衝突路徑：{sample_reason}）" if sample_reason else ""
        lines.append(f"  Group #{idx}{suffix}:")
        for mid in members:
            lines.append(f"    - {mid}")
    if not groups:
        lines.append("  （無）")

    lines.append("")
    lines.append("[單獨派發] 0 ticket(s)")

    lines.append("")
    if result["pc137_warning"]:
        lines.append(
            f"[PC-137 警告] 可平行集合觸及 .claude/ 的 ticket 數 = "
            f"{result['pc137_count']}（>= 3），建議拆批至 <= {_PC137_PARALLEL_LIMIT}"
        )
    else:
        lines.append(
            f"[PC-137 警告] 無（.claude/ Edit 數 = {result['pc137_count']} < 3）"
        )

    lines.append("")
    lines.append("Hint: 派發前請對齊 .claude/pm-rules/askuserquestion-rules.md 規則 7")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def execute_parallel_check(args: argparse.Namespace) -> int:
    target_id = getattr(args, "ticket_id", None)
    if not target_id:
        sys.stderr.write("[FAIL] 缺少 ticket_id 參數\n")
        return 2

    components = extract_id_components(target_id)
    if components is None:
        sys.stderr.write(f"[FAIL] 無效的 ticket ID 格式: {target_id}\n")
        return 2

    version = components["version"]
    try:
        tickets = list_tickets(version) or []
    except Exception as e:  # pragma: no cover - 防禦性
        sys.stderr.write(f"[FAIL] 載入 ticket 失敗: {e}\n")
        return 2

    result = analyze_parallel(target_id, tickets)

    if result["target"] is None:
        sys.stderr.write(f"[FAIL] 找不到 ticket: {target_id}\n")
        return 1
    if not result["pending"]:
        sys.stderr.write(
            f"[FAIL] {target_id} 無 pending children 或兄弟可分析\n"
        )
        return 1

    print(_render(result, target_id))
    return 0


def register_parallel_check(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    """註冊 parallel-check 子命令。"""
    p = subparsers.add_parser(
        "parallel-check",
        help=(
            "分析目標 ticket 的 children/兄弟 pending 集合的檔案衝突，"
            "輸出可平行派發/衝突任務分組（對齊 askuserquestion-rules 規則 7）"
        ),
    )
    p.add_argument("ticket_id", help="目標 ticket ID（例如 0.18.0-W17-203）")
    return p
