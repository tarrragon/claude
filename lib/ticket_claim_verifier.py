"""claim 命令的票面狀態驗證器（與 ticket_completed_verifier 同一做法）。

claim 的 CLI 回音在「已認領的票再次 claim」時仍結束碼為 0（輸出「已被接手」警告），
故未遮蔽的 PostToolUse 只代表命令成功，不代表發生了認領轉換。判定「這次發生了
認領」的依據：命令中每張票 status 為 in_progress，且 started_at 距現在不超過時間窗
（重複認領時 started_at 保持舊值，落在窗外）。

讀票失敗（找不到票、無法解析命令中的票號、started_at 缺漏或無法解析）時拋
VerifierUnavailable，呼叫端退回原判定；不得把讀不到當成功。
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

from .hook_base import get_shared_state_root
from .hook_ticket import find_ticket_file, parse_ticket_date, parse_ticket_frontmatter
from .ticket_command_parse import find_ticket_track_invocations
from .ticket_completed_verifier import (
    COMPLETED_AT_WINDOW_SECONDS,
    VerifierUnavailable,
    _CLOCK_SKEW_SECONDS,
)
from .ticket_id_pattern import SEARCH_WITH_SUFFIX_RE

CLAIM_VERBS = ("claim",)

# 時間窗沿用完成類驗證器：hook 在命令結束後立即觸發，started_at 寫入到讀票只隔 CLI 收尾
CLAIMED_AT_WINDOW_SECONDS = COMPLETED_AT_WINDOW_SECONDS


def extract_claim_ticket_ids(command: str) -> List[str]:
    """取出命令中所有 claim 呼叫的票號；無法解析回空清單。"""
    invocations = find_ticket_track_invocations(command, CLAIM_VERBS)
    if not invocations:
        return []
    ids: List[str] = []
    for _verb, args in invocations:
        for token in args:
            for piece in token.split(","):
                match = SEARCH_WITH_SUFFIX_RE.fullmatch(piece)
                if match:
                    ids.append(match.group(1))
    return ids


def _is_recently_claimed(
    ticket_id: str,
    project_root: Path,
    now: datetime,
    logger: Optional[logging.Logger],
) -> bool:
    ticket_file = find_ticket_file(ticket_id, project_root, logger)
    if ticket_file is None:
        raise VerifierUnavailable("找不到票面: {}".format(ticket_id))
    frontmatter = parse_ticket_frontmatter(ticket_file, logger)
    if not frontmatter:
        raise VerifierUnavailable("票面無法解析: {}".format(ticket_id))
    if str(frontmatter.get("status", "")).strip() != "in_progress":
        return False
    started_at = parse_ticket_date(frontmatter.get("started_at"), logger)
    if started_at is None:
        raise VerifierUnavailable("started_at 缺漏或無法解析: {}".format(ticket_id))
    reference = now.astimezone(started_at.tzinfo) if started_at.tzinfo else now
    age = (reference - started_at).total_seconds()
    return -_CLOCK_SKEW_SECONDS <= age <= CLAIMED_AT_WINDOW_SECONDS


def make_claim_verifier(
    command: str,
    logger: Optional[logging.Logger] = None,
    now: Optional[Callable[[], datetime]] = None,
    project_root: Optional[Path] = None,
) -> Callable[[], bool]:
    """建立 state_verifier：命令中每張票都在時間窗內剛被認領才回 True。"""

    def verify() -> bool:
        ids = extract_claim_ticket_ids(command)
        if not ids:
            raise VerifierUnavailable("命令中無可辨識的票號")
        root = project_root if project_root is not None else get_shared_state_root()
        current = now() if now is not None else datetime.now()
        return all(_is_recently_claimed(i, root, current, logger) for i in ids)

    return verify
