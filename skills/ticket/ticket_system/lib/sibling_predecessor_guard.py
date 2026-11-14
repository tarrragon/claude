"""兄弟前驅數檢查（ARCH-017 結構規則的寫入點執行）。

規則：同一父票下，一張票的 blockedBy 至多含一個兄弟票。依賴同一層兩個以上
的兄弟，代表依賴結構被壓平；應升格聚合父或改成父子深度（ARCH-017）。

本模組在 CLI 寫入 blockedBy 或 parent_id 前，以寫入後的值判定。寫入點持有
確切狀態，比 hook 從命令文字推測可靠。hook 在 claim／complete 的同名檢查保留
為後備，涵蓋手改票檔與規則上線前建立的既有票。

失敗語意：fail-open。載入票檔時發生例外，寫 stderr 後放行；後備檢查仍在。
"""

from __future__ import annotations

import sys
from typing import Callable, Dict, Iterable, List, Optional

from ticket_system.constants import TERMINAL_STATUSES

ARCH_017_PATH = ".claude/error-patterns/architecture/ARCH-017-sibling-hidden-dependency.md"

LoadFn = Callable[[str], Optional[Dict]]


def _sibling_predecessors(blocked_by: Iterable[str], sibling_ids: set, self_id: str) -> List[str]:
    return [b for b in blocked_by if b in sibling_ids and b != self_id]


def _is_violation(preds: List[str], load_fn: LoadFn) -> bool:
    """兄弟前驅達 2 個且並非全為終態。全為終態時結構已不影響排程，與 hook 條件 1 一致。"""
    if len(preds) < 2:
        return False
    statuses = [(load_fn(p) or {}).get("status") for p in preds]
    return not all(s in TERMINAL_STATUSES for s in statuses)


def find_violations(
    target_id: str,
    target_blocked_by: List[str],
    parent_id: Optional[str],
    load_fn: LoadFn,
) -> List[tuple]:
    """回傳寫入後違規的 (票號, 兄弟前驅清單)。

    檢查對象：目標票本身，以及同父下 blockedBy 含目標票的兄弟票
    （set-parent／add-child 把目標票移入新父時，這些兄弟的前驅數可能增加）。
    """
    if not parent_id:
        return []
    parent = load_fn(parent_id)
    if not parent:
        return []
    sibling_ids = set(parent.get("children") or []) | {target_id}

    violations = []
    target_preds = _sibling_predecessors(target_blocked_by or [], sibling_ids, target_id)
    if _is_violation(target_preds, load_fn):
        violations.append((target_id, target_preds))

    for sid in sorted(sibling_ids - {target_id}):
        sibling = load_fn(sid) or {}
        blocked_by = sibling.get("blockedBy") or []
        if target_id not in blocked_by:
            continue
        preds = _sibling_predecessors(blocked_by, sibling_ids, sid)
        if _is_violation(preds, load_fn):
            violations.append((sid, preds))
    return violations


def format_violation_hint(parent_id: str, violations: List[tuple], unchanged_note: str) -> str:
    lines = [
        f"{tid} 會同時依賴 {len(preds)} 個兄弟票（父票 {parent_id}）：{', '.join(preds)}"
        for tid, preds in violations
    ]
    lines.append(
        "兄弟票至多一個前驅兄弟；被多張票依賴的那張應升格為聚合父，"
        "或把依賴者改成它的子票。同檔排序屬派發排程，不寫 blockedBy。"
    )
    lines.append(f"參考：{ARCH_017_PATH}；{unchanged_note}")
    return "\n".join(lines)


def check_sibling_predecessors(
    target_id: str,
    target_blocked_by: List[str],
    parent_id: Optional[str],
    load_fn: LoadFn,
    unchanged_note: str,
) -> Optional[str]:
    """寫入點入口：違規回傳錯誤提示文字，通過或檢查失敗回傳 None。"""
    try:
        violations = find_violations(target_id, target_blocked_by, parent_id, load_fn)
    except Exception as exc:  # fail-open：後備檢查在 claim／complete
        sys.stderr.write(
            f"[sibling-predecessor-guard] 兄弟前驅檢查失敗（{exc!r}），略過本次檢查；"
            "claim／complete 時仍會由 sibling-blockedby-validator 檢查\n"
        )
        return None
    if not violations:
        return None
    return format_violation_hint(parent_id, violations, unchanged_note)
