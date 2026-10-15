#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///

"""
Parallel Claim Audit Hook (PostToolUse:Bash) — 非阻擋 observability

功能:
  偵測 `ticket track claim <id>` 命令成功完成後，記錄當時同 wave in_progress
  快照到 .claude/hook-logs/parallel-claim-audit.log，作為 PC-078 / PC-141 並行
  claim 衝突的事後歸因依據。

設計原則:
  - 純 observability：一律 exit 0，任何失敗只 log，絕不影響 claim 操作
  - 零 race condition：只讀取既有 ticket 檔案 frontmatter 建快照，不寫 ticket，
    不執行 ticket CLI（避免與並行 claim 競爭）
  - 失敗雙通道可觀測（quality-baseline 規則 4）：例外寫 logger.info + stderr

觸發時機: PostToolUse (Bash: ticket track claim)
覆蓋限制: 只見被管線或分號遮蔽的失敗（整體結束碼為 0）；未遮蔽的非零結束碼走
  PostToolUseFailure，本 hook 不在該群組，不會收到（含結束碼 75）。

輸出:
  audit log（JSONL）：{ ticket_id, wave, timestamp, same_wave_in_progress: [...] }
  異常時：stderr + logger（不阻擋，exit 0）
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
from typing import Optional
from lib.bash_tool_response import is_bash_success
from lib.ticket_claim_verifier import make_claim_verifier
from lib import (
    setup_hook_logging,
    run_hook_safely,
    read_json_from_stdin,
    get_project_root,
    find_ticket_files,
    parse_ticket_frontmatter,
    extract_version_from_ticket_id,
    extract_wave_from_ticket_id,
)

# 匹配 `ticket track claim <id>`（容許前後管線、選項）
_CLAIM_RE = re.compile(r"\bticket\s+track\s+claim\s+(\S+)")

_AUDIT_LOG_RELPATH = Path(".claude") / "hook-logs" / "parallel-claim-audit.log"


def parse_claim_command(command: str):
    """從 Bash 命令解析 `ticket track claim <id>`，回傳 ticket_id 或 None。"""
    if not command:
        return None
    match = _CLAIM_RE.search(command)
    if not match:
        return None
    candidate = match.group(1)
    # 排除以 - 開頭的選項誤判（如 claim --help）
    if candidate.startswith("-"):
        return None
    return candidate


# claim 成功回音（messages.py TICKET_CLAIMED）
CLAIM_SUCCESS_MARKERS = ("[OK] 已接手",)
# format_write_command_commit_failure 的固定片語；其 stderr 原因文字可能含 "failed"
AUTO_COMMIT_WARNING_MARK = "已寫入 working tree 但 auto-commit 失敗"


def _claim_transition_verdict(tool_result, command: str, logger) -> Optional[bool]:
    """以票面確認「這次發生了認領轉換」，不論命令是否被遮蔽。

    未遮蔽且收到 PostToolUse 只代表命令成功：對已認領的票再次 claim，CLI 仍輸出
    「已被接手」警告且結束碼為 0，started_at 保持舊值（落在時間窗外）。
    回傳 True／False 為驗證器的明確判定；None 表示票面讀不到，呼叫端退回標記判定。
    """
    try:
        verdict = bool(make_claim_verifier(command, logger)())
    except Exception:  # 讀票失敗不等於命令失敗：退回標記判定
        return None
    if not verdict:
        return False
    # 驗證器為真時仍交由 is_bash_success 做 exit_code 前置檢查（驗證器恆真，不重複判定）
    return is_bash_success(
        tool_result, CLAIM_SUCCESS_MARKERS, command=command, state_verifier=lambda: True
    )


def is_claim_successful(tool_result, command: Optional[str] = None, logger=None) -> bool:
    """判斷 claim 是否成功。

    給定 command 時先以票面驗證器確認認領轉換（見 _claim_transition_verdict）；
    驗證器不可用時退回下列標記判定。
    失敗訊號（任一出現於 stdout/stderr 即視為失敗）：
    - 'already claimed' / 'not found' / 'Error' / 'failed' / 'blocked'
    其餘視為成功（observability 寧可多記，不影響 claim）。
    """
    if not isinstance(tool_result, dict):
        return True
    # 結束碼 75（claim 已寫入、僅 auto-commit 失敗）屬非零，PostToolUse 只在結束碼為 0 時
    # 觸發，故此處不會收到 75，原 75 分支已移除；以下 WARNING 片語後備保留。
    if tool_result.get("interrupted") is True:
        return False
    if command:
        verdict = _claim_transition_verdict(tool_result, command, logger)
        if verdict is not None:
            return verdict
    if is_bash_success(tool_result, CLAIM_SUCCESS_MARKERS):
        return True
    if AUTO_COMMIT_WARNING_MARK in str(tool_result.get("stderr", "")):
        return True
    combined = "{}\n{}".format(
        tool_result.get("stdout", ""), tool_result.get("stderr", "")
    ).lower()
    failure_markers = (
        "already claimed",
        "not found",
        "error",
        "failed",
        "blocked",
        "traceback",
    )
    return not any(marker in combined for marker in failure_markers)


def build_same_wave_snapshot(ticket_id: str, project_root: Path, logger):
    """掃描同 version 同 wave 的 in_progress ticket 快照。

    回傳: (wave, [ {id, started_at, who} ...])
    僅讀取 ticket 檔案 frontmatter，不執行 CLI、不寫檔（零 race condition）。
    被 claim 的 ticket 自身也納入快照（claim 後即為 in_progress）。
    """
    wave = extract_wave_from_ticket_id(ticket_id)
    version = extract_version_from_ticket_id(ticket_id)

    snapshot = []
    ticket_files = find_ticket_files(project_root, version=version, logger=logger)
    for ticket_file in ticket_files:
        frontmatter = parse_ticket_frontmatter(ticket_file, logger=logger)
        if not frontmatter:
            continue
        if frontmatter.get("status") != "in_progress":
            continue
        fid = frontmatter.get("id", ticket_file.stem)
        # wave 比對：以 ticket_id 推導的 wave 為準
        if wave is not None and extract_wave_from_ticket_id(str(fid)) != wave:
            continue
        who = frontmatter.get("who")
        current_owner = who.get("current") if isinstance(who, dict) else who
        snapshot.append(
            {
                "id": fid,
                "started_at": frontmatter.get("started_at"),
                "who": current_owner,
            }
        )
    return wave, snapshot


def write_audit_entry(entry: dict, project_root: Path, logger):
    """以 append JSONL 方式寫入 audit log。"""
    audit_path = project_root / _AUDIT_LOG_RELPATH
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    logger.info("已記錄 parallel claim audit: {}".format(entry.get("ticket_id")))


def main() -> int:
    logger = setup_hook_logging("parallel-claim-audit-hook")

    input_data = read_json_from_stdin(logger)
    if input_data is None:
        return 0

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input") or {}
    # 平台欄位為 tool_response；tool_result 僅為舊測試樁相容後備
    tool_result = input_data.get("tool_response")
    if tool_result is None:
        tool_result = input_data.get("tool_result", {})

    if tool_name != "Bash":
        return 0

    command = tool_input.get("command", "")
    ticket_id = parse_claim_command(command)
    if ticket_id is None:
        return 0  # 非 claim 命令，正常跳過

    if not is_claim_successful(tool_result, command, logger):
        logger.info("claim 命令未成功（{}），不記錄快照".format(ticket_id))
        return 0

    # 任一步驟失敗都不可影響 claim（純 observability），故包裹 try/except
    # 並依規則 4 雙通道（stderr + logger）輸出異常。
    try:
        project_root = get_project_root()
        wave, snapshot = build_same_wave_snapshot(ticket_id, project_root, logger)
        entry = {
            "ticket_id": ticket_id,
            "wave": wave,
            "timestamp": datetime.now().isoformat(),
            "same_wave_in_progress_count": len(snapshot),
            "same_wave_in_progress": snapshot,
        }
        write_audit_entry(entry, project_root, logger)
    except Exception as exc:  # noqa: BLE001 — observability 不可因任何失敗中斷 claim
        msg = "parallel-claim-audit-hook 記錄失敗（不影響 claim）: {}".format(exc)
        logger.info(msg)
        sys.stderr.write(msg + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "parallel-claim-audit-hook"))
