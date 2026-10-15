"""完成類命令的票面狀態驗證器（供 is_bash_success 的 state_verifier 使用）。

命令結束碼被遮蔽、stdout 又被吸走時，成功與否只能由票面推得：命令中的每張票
status 為 completed，且 completed_at 距現在不超過 COMPLETED_AT_WINDOW_SECONDS。

讀票失敗（找不到票、無法解析命令中的票號、completed_at 缺漏或無法解析）時拋
VerifierUnavailable，lib 的分層判定會退回標記判定；不得把讀不到當成功。
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

from .hook_base import get_shared_state_root
from .hook_ticket import find_ticket_file, parse_ticket_date, parse_ticket_frontmatter
from .ticket_command_parse import find_complete_invocations
from .ticket_id_pattern import SEARCH_WITH_SUFFIX_RE

# 時間窗：hook 在命令結束後立即觸發，complete 寫入 completed_at 到 hook 讀票只隔
# CLI 收尾（auto-commit、worktree 同步）的數秒；取 120 秒涵蓋慢速收尾，同時遠小於
# 「隔一段時間重新 complete 已完成的舊票」的間隔，使舊票的 completed_at 落在窗外。
COMPLETED_AT_WINDOW_SECONDS = 120

# 容忍 hook 與 CLI 之間的時鐘讀數落差（completed_at 略晚於 hook 的 now）
_CLOCK_SKEW_SECONDS = 5


class VerifierUnavailable(Exception):
    """票面無法讀取或命令無法解析出票號；呼叫端（lib）退回標記判定。"""


def extract_complete_ticket_ids(command: str) -> List[str]:
    """取出命令中所有完成類呼叫的票號（支援逗號分隔）；無法解析回空清單。"""
    invocations = find_complete_invocations(command)
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


def _is_recently_completed(
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
    if str(frontmatter.get("status", "")).strip() != "completed":
        return False
    completed_at = parse_ticket_date(frontmatter.get("completed_at"), logger)
    if completed_at is None:
        raise VerifierUnavailable("completed_at 缺漏或無法解析: {}".format(ticket_id))
    reference = now.astimezone(completed_at.tzinfo) if completed_at.tzinfo else now
    age = (reference - completed_at).total_seconds()
    return -_CLOCK_SKEW_SECONDS <= age <= COMPLETED_AT_WINDOW_SECONDS


def is_complete_transition_success(
    tool_response,
    success_markers,
    command: str,
    verifier: Callable[[], bool],
) -> bool:
    """完成類 hook 的成功判定：確認「這次發生了完成轉換」，不論命令是否被遮蔽。

    未遮蔽且收到 PostToolUse 只代表命令成功；對已完成的票重新 complete，CLI 仍輸出
    「已完成於 ...」且結束碼為 0，但沒有狀態轉換（重複計數）。因此先跑驗證器：
    True（completed_at 在時間窗內）才成功，False 即失敗；驗證器拋 VerifierUnavailable
    （或任何例外）時才退回 is_bash_success 的分層判定。interrupted / exit_code 前置檢查
    仍由 is_bash_success 負責。
    採 hook 端呼叫（不改 lib 的 is_bash_success），維持 286.1 的預設行為不變。
    """
    from .bash_tool_response import is_bash_success

    try:
        verdict = bool(verifier())
    except Exception:  # 讀票失敗不等於命令失敗：退回分層判定
        return is_bash_success(
            tool_response, success_markers, command=command, state_verifier=verifier)
    if not verdict:
        return False
    return is_bash_success(
        tool_response, success_markers, command=command, state_verifier=lambda: True)


def make_completed_verifier(
    command: str,
    logger: Optional[logging.Logger] = None,
    now: Optional[Callable[[], datetime]] = None,
    project_root: Optional[Path] = None,
) -> Callable[[], bool]:
    """建立 state_verifier：命令中每張票都在時間窗內剛完成才回 True。

    project_root 預設為 get_shared_state_root()（linked worktree 內讀主倉庫的票）。
    now 供測試注入時鐘；預設 datetime.now()（completed_at 為本機時區的 naive 時間）。
    """

    def verify() -> bool:
        ids = extract_complete_ticket_ids(command)
        if not ids:
            raise VerifierUnavailable("命令中無可辨識的票號")
        root = project_root if project_root is not None else get_shared_state_root()
        current = now() if now is not None else datetime.now()
        return all(_is_recently_completed(i, root, current, logger) for i in ids)

    return verify
