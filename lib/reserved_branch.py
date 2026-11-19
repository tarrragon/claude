"""保留分支判定。

合併提醒類 hook 共用：分支 `feat/<票號>` 對應的票為 pending（未認領）時，
視為刻意保留的跨版本分支，提醒改列資訊而非強制合併。

判準：只有經 previous_ids（遷移前舊 ID）命中、且現行票 status 為 pending
才算保留。直接命中票檔者一律強制（不論 status：`ticket track release` 會把
做到一半的票設回 pending，直接列保留會讓未合併進度失去提醒）。查無票、
解析失敗、查票例外同樣視為非保留（fail-safe：判不出就照舊強制提醒）。
"""

import logging
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .hook_ticket import find_ticket_file, find_ticket_files, parse_ticket_frontmatter

_BRANCH_TICKET_RE = re.compile(r"^feat/(\d+\.\d+\.\d+-W\d+-\d+(?:\.\d+)*)$")
_RESERVED_STATUS = "pending"


def _find_by_previous_id(
    ticket_id: str, project_root: Optional[Path], logger: logging.Logger
) -> Optional[dict]:
    """掃描票檔，找 previous_ids 含 ticket_id 的票 frontmatter。"""
    root = project_root
    if root is None:
        from .hook_base import get_shared_state_root
        root = get_shared_state_root()
    for path in find_ticket_files(root, logger=logger):
        frontmatter = parse_ticket_frontmatter(path, logger)
        if ticket_id in (frontmatter.get("previous_ids") or []):
            return frontmatter
    return None


def find_reservation(
    branch: str, project_root: Optional[Path], logger: logging.Logger
) -> Optional[str]:
    """分支為保留中回傳其對應的現行票號，否則回傳 None。

    查票例外時寫 stderr 與日誌（規則 4），並回傳 None（退回強制提醒）。
    """
    matched = _BRANCH_TICKET_RE.match(branch)
    if not matched:
        return None
    ticket_id = matched.group(1)
    try:
        if find_ticket_file(ticket_id, project_root, logger) is not None:
            return None  # 直接命中票檔：不論 status 一律強制（release 回 pending 的進行中票）
        frontmatter = _find_by_previous_id(ticket_id, project_root, logger)
        if not frontmatter or frontmatter.get("status") != _RESERVED_STATUS:
            return None
        return str(frontmatter.get("id") or ticket_id)
    except Exception as exc:  # 查票失敗不得使提醒失效；已寫雙通道後退回現行行為
        message = "保留分支查票失敗，退回強制提醒: branch={} {}: {}".format(
            branch, type(exc).__name__, exc
        )
        logger.warning(message)
        sys.stderr.write("[reserved_branch] {}\n".format(message))
        return None


def split_reserved(
    branches: List[str], project_root: Optional[Path], logger: logging.Logger
) -> Tuple[List[str], Dict[str, str]]:
    """把分支清單切成 (須處理的分支, {保留分支: 保留給的票號})。"""
    active: List[str] = []
    reserved: Dict[str, str] = {}
    for branch in branches:
        ticket_id = find_reservation(branch, project_root, logger)
        if ticket_id:
            reserved[branch] = ticket_id
        else:
            active.append(branch)
    return active, reserved


def format_reserved_lines(reserved: Dict[str, str]) -> List[str]:
    """保留分支的資訊行（無強制字樣、無合併建議）。"""
    return [
        "  [保留中] {} 保留給票 {}（票為 pending），無需合併".format(branch, ticket_id)
        for branch, ticket_id in reserved.items()
    ]
