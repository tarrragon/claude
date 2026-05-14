"""
ticket track td-status 命令（W10-083 / PC-094 防護建議 3）

掃描指定 ticket 的 TD（Technical Debt）清單，比對 ticket body 與 git commit
訊息中的 TD 引用，將每個 TD 編號分類為「已處理 / 無需處理 / 仍待處理」三狀態，
協助 PM 在 Phase 3a/3b/4 演進中即時校準 TD 清單。

設計約束：
- version-aware（透過 ticket_id 解析版本，或 --version 明確指定）
- 註冊於 track.py _create_command_handlers() 字典
- 復用 ticket_loader.load_ticket 取得 ticket body
- 校準訊號：ticket body 中「已處理 / 已修正 / 已完成 / 已關閉 / 無需」鄰近
  TD 編號，或 git commit 訊息含 TD 編號
- 設計取捨：AC 4「Phase 演進中提示校準缺失」採呼叫時即提示模式（不接 hook），
  保持單一職責；hook 整合屬獨立追蹤項。

相關 Pattern: PC-094 TD 清單即時校準缺失
"""

from __future__ import annotations

import argparse
import re
import subprocess
from typing import Dict, List, Optional, Set, Tuple

from ticket_system.lib.ticket_loader import load_ticket


# TD 編號 regex：行內 / 表格 / 散文皆可命中
# 使用負向 lookahead 避免誤命中 "TDD"
_TD_PATTERN = re.compile(r"\bTD(\d+)\b(?!D)", re.IGNORECASE)

# 已處理訊號詞（中文）：在 TD 編號附近（同行）出現即視為已處理候選
_DONE_KEYWORDS = (
    "已處理",
    "已修正",
    "已完成",
    "已關閉",
    "已落地",
    "已實作",
    "已 fix",
    "已 close",
)

# 「無需處理」訊號詞
_SKIP_KEYWORDS = (
    "無需處理",
    "無需",
    "不需處理",
    "不需要處理",
    "豁免",
    "N/A",
)

# 狀態常數
STATUS_DONE = "done"
STATUS_SKIPPED = "skipped"
STATUS_PENDING = "pending"

_STATUS_LABEL = {
    STATUS_DONE: "已處理",
    STATUS_SKIPPED: "無需處理",
    STATUS_PENDING: "仍待處理",
}


# ---------------------------------------------------------------------------
# 內部工具
# ---------------------------------------------------------------------------

def _extract_td_numbers(body: str) -> List[str]:
    """從 ticket body 抽取所有 TD 編號（去重、保留首次出現順序）。"""
    seen: Set[str] = set()
    ordered: List[str] = []
    for match in _TD_PATTERN.finditer(body or ""):
        num = match.group(1)
        if num in seen:
            continue
        seen.add(num)
        ordered.append(num)
    return ordered


def _classify_td_in_body(td_num: str, body: str) -> Optional[str]:
    """逐行掃描 body，回傳該 TD 編號在 body 中的狀態。

    若有任何行同時含 TD 編號 + skip 關鍵字 → skipped
    若有任何行同時含 TD 編號 + done 關鍵字 → done
    皆無 → None（待 commit 訊息或其他訊號補充）
    """
    if not body:
        return None
    pattern = re.compile(rf"\bTD{td_num}\b(?!D)", re.IGNORECASE)
    found_done = False
    for line in body.splitlines():
        if not pattern.search(line):
            continue
        # skip 訊號優先（語意更明確）
        if any(kw in line for kw in _SKIP_KEYWORDS):
            return STATUS_SKIPPED
        if any(kw in line for kw in _DONE_KEYWORDS):
            found_done = True
    return STATUS_DONE if found_done else None


def _collect_commit_td_refs(ticket_id: str) -> Set[str]:
    """搜尋 git log，找出 commit 訊息中與本 ticket 相關且含 TD 編號的引用。

    策略：搜尋訊息含 ticket_id 的 commits，從訊息中抽取 TD 編號。
    若 git 失敗或無 commits，回空 set。
    """
    try:
        result = subprocess.run(
            [
                "git",
                "log",
                "--all",
                "--format=%B%n--END--",
                f"--grep={ticket_id}",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return set()
    if result.returncode != 0:
        return set()
    refs: Set[str] = set()
    for match in _TD_PATTERN.finditer(result.stdout or ""):
        refs.add(match.group(1))
    return refs


def classify_tds(
    td_numbers: List[str], body: str, commit_refs: Set[str]
) -> List[Tuple[str, str]]:
    """組合 body / commit 訊號得到每個 TD 編號的最終狀態。

    優先序：
    1. body 中明確標註「無需處理」→ skipped
    2. body 中明確標註「已處理」→ done
    3. commit 訊息引用該 TD 編號 → done
    4. 皆無 → pending
    """
    result: List[Tuple[str, str]] = []
    for num in td_numbers:
        body_status = _classify_td_in_body(num, body)
        if body_status == STATUS_SKIPPED:
            result.append((num, STATUS_SKIPPED))
        elif body_status == STATUS_DONE:
            result.append((num, STATUS_DONE))
        elif num in commit_refs:
            result.append((num, STATUS_DONE))
        else:
            result.append((num, STATUS_PENDING))
    return result


# ---------------------------------------------------------------------------
# 渲染
# ---------------------------------------------------------------------------

def _render(
    ticket_id: str,
    classified: List[Tuple[str, str]],
    commit_refs: Set[str],
) -> str:
    lines: List[str] = []
    lines.append("─" * 60)
    lines.append(f"TD 狀態校準  ticket={ticket_id}")
    lines.append("─" * 60)

    if not classified:
        lines.append("（ticket body 中未發現 TD 編號）")
        return "\n".join(lines)

    # 分組顯示
    groups: Dict[str, List[str]] = {
        STATUS_DONE: [],
        STATUS_SKIPPED: [],
        STATUS_PENDING: [],
    }
    for num, status in classified:
        groups[status].append(num)

    for status in (STATUS_DONE, STATUS_SKIPPED, STATUS_PENDING):
        nums = groups[status]
        label = _STATUS_LABEL[status]
        if nums:
            joined = ", ".join(f"TD{n}" for n in nums)
            lines.append(f"  [{label}] ({len(nums)}) {joined}")
        else:
            lines.append(f"  [{label}] (0)")

    # AC 4 校準提示：列出 pending TD 提醒 PM 在 Phase 演進中更新 body 或 commit
    pending = groups[STATUS_PENDING]
    if pending:
        lines.append("")
        lines.append(
            f"  提示：仍有 {len(pending)} 個 TD 未見處理訊號（PC-094 校準缺失），"
            "Phase 演進完成後請於 body 標註「已處理 / 已修正 / 無需處理」"
            "或在 commit 訊息引用 TD 編號"
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def execute_td_status(args: argparse.Namespace, version: str) -> int:
    """執行 track td-status 命令。"""
    ticket_id = args.ticket_id
    ticket = load_ticket(version, ticket_id)
    if ticket is None:
        print(f"[ERROR] 找不到 Ticket: {ticket_id} (version={version})")
        return 1

    body = ticket.get("_body") or ""
    td_numbers = _extract_td_numbers(body)
    commit_refs = _collect_commit_td_refs(ticket_id)
    classified = classify_tds(td_numbers, body, commit_refs)
    print(_render(ticket_id, classified, commit_refs))
    return 0


def register_td_status(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    """註冊 td-status 子命令 parser。"""
    p = subparsers.add_parser(
        "td-status",
        help=(
            "校準 TD 清單（PC-094）：掃描 ticket body 與 commit 訊息，"
            "將 TD 編號分類為 已處理 / 無需處理 / 仍待處理"
        ),
    )
    p.add_argument(
        "ticket_id",
        help="目標 Ticket ID（如 0.18.0-W10-017.8）",
    )
    p.add_argument(
        "--version",
        default=None,
        help="指定版本（覆蓋自動偵測）",
    )
    return p


if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()
