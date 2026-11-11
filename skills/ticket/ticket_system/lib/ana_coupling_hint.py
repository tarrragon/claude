"""指向 ANA 時的耦合後果提示。

ANA 掛著非終態 children 時不能 complete；被 blockedBy 的 ANA 不 complete，
依賴它的票就一直等。建票或設定依賴當下把這條後果說出來，寫 stdout
（受眾含模型，stderr 對模型不可見），不改 exit code（提示不是拒絕，
避免與 PC-091 衝突）。
"""
from __future__ import annotations

import sys
from typing import Any, Dict, Iterable, List

from ticket_system.constants import TERMINAL_STATUSES
from ticket_system.lib import version as version_mod
from ticket_system.lib.field_validators import resolve_reference_version
from ticket_system.lib.ticket_loader import list_tickets, load_ticket

ANA_TYPE = "ANA"


def _is_open(ticket: Dict[str, Any]) -> bool:
    return ticket.get("status") not in TERMINAL_STATUSES


def _blocked_by_ids(ticket: Dict[str, Any]) -> List[str]:
    return list(ticket.get("blockedBy") or ticket.get("blocked_by") or [])


def _load_ana(version: str, ticket_id: str) -> Dict[str, Any] | None:
    ticket = load_ticket(resolve_reference_version(version, ticket_id), ticket_id)
    if ticket and ticket.get("type") == ANA_TYPE:
        return ticket
    return None


def _open_dependents(version: str, ana_id: str, exclude_id: str) -> List[str]:
    """非終態且 blockedBy 含 ana_id 的票 ID（不含 exclude_id）。"""
    ana_version = resolve_reference_version(version, ana_id)
    return [
        t["id"]
        for t in list_tickets(ana_version)
        if t.get("id") != exclude_id
        and _is_open(t)
        and ana_id in _blocked_by_ids(t)
    ]


def _open_children(version: str, ana: Dict[str, Any], exclude_id: str) -> List[str]:
    """ANA 非終態的 children ID（不含 exclude_id）。"""
    open_ids = []
    for child_id in ana.get("children") or []:
        if child_id == exclude_id:
            continue
        child = load_ticket(resolve_reference_version(version, child_id), child_id)
        if child and _is_open(child):
            open_ids.append(child_id)
    return open_ids


def _emit(message: str) -> None:
    sys.stdout.write(f"[HINT] {message}\n")


def hint_parent_is_ana(version: str, parent_id: str, new_id: str) -> None:
    """--parent 指向 ANA 且已有票 blockedBy 該 ANA 時提示。"""
    if not _load_ana(version, parent_id):
        return
    dependents = _open_dependents(version, parent_id, exclude_id=new_id)
    if not dependents:
        return
    _emit(
        f"ANA 將保持開啟到本票 {new_id} 終態；以下 {len(dependents)} 張 "
        f"blockedBy 本 ANA {parent_id} 的票會一起等待：{', '.join(dependents)}"
    )


def hint_blocked_by_ana(
    version: str, blocked_ids: Iterable[str], waiter_id: str
) -> None:
    """blockedBy 指向有非終態 children 的 ANA 時提示。"""
    for ana_id in blocked_ids:
        ana = _load_ana(version, ana_id)
        if not ana:
            continue
        children = _open_children(version, ana, exclude_id=waiter_id)
        if not children:
            continue
        _emit(
            f"ANA 將保持開啟：{ana_id} 尚有 {len(children)} 張非終態 children"
            f"（{', '.join(children)}），本票 {waiter_id} 會等到它們全部終態"
            f"後 ANA 才能 complete"
        )


def hint_frozen_version_ana_parent(
    version: str, parent_id: str, new_id: str, scope_blocker: str | None
) -> None:
    """--parent 指向 ANA、父票版本 scope 已凍結、未帶 --scope-blocker 時提示。

    不阻擋：凍結版本內的合法拆票同樣用 --parent。子票版本繼承父票版本，
    ANA 結論要求的落地若屬後續版本，應改用 --version + --source-ticket。
    """
    if scope_blocker or not _load_ana(version, parent_id):
        return
    parent_version = resolve_reference_version(version, parent_id)
    if not version_mod.is_version_scope_frozen(parent_version):
        return
    _emit(
        f"ANA {parent_id} 所在版本 {parent_version} 已 scope: frozen，--parent "
        f"建的子票 {new_id} 版本繼承父票，會落在凍結版本內。若本票是依〈兩期〉"
        f"排入後續版本的落地，請改用：ticket create --version <目標版本> "
        f"--source-ticket {parent_id}（目標版本未登記先登記）；屬本版範圍的"
        f"拆票維持 --parent 並加 --scope-blocker <理由>"
    )
