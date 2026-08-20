#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
Worktree Commit-Before-Dispatch Hook - PreToolUse (Agent)

功能：派發 worktree agent 前，檢查主 repo 上是否有未 commit 的 tracked 變更。
未 commit 的變更可能在 worktree 操作後因 stash/checkout 丟失（PC-019）。

PC-019 髒污判定由 DENY 降為 WARN。派發事件本身不執行任何破壞性動作，
危險動作端（stash/checkout/reset 等）已由 workspace-wipe-guard-hook.py
無條件 DENY 覆蓋，本 hook 的 DENY 因此成為冗餘；仍保留 stderr 提醒以維持
可觀測性。

Hook 類型：PreToolUse
匹配工具：Agent
退出碼：0 = 放行（含 PC-019 髒污 WARN），2 = 阻擋（僅 origin/main 落後超門檻）
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from lib import (
    setup_hook_logging,
    run_hook_safely,
    read_json_from_stdin,
    emit_hook_output,
    get_project_root,
)
from lib.ticket_id_pattern import extract_ticket_id_anchored


# W4-008：origin/main 落後 local main 達此門檻視為高風險，改走 deny（非僅警告）
LAG_DENY_THRESHOLD = 10

WARN_MESSAGE = """[PC-019 提醒] 主 repo 上有未 commit 的 tracked 變更

未 commit 的檔案：
{files}

建議：派發前先 commit 主 repo 上的變更，避免 worktree 操作
（stash/checkout 等）造成遺失風險
  git add <files> && git commit -m "chore: pre-dispatch commit"

詳見: .claude/pm-rules/worktree-operations.md（階段 1：派發前）"""

# W3-007 方案 A：origin/main 落後 local main 警告訊息（非阻擋，走 additionalContext）
ORIGIN_BEHIND_WARNING = """[W3-007 警告] origin/main 落後 local main {count} 個 commit

CC runtime 的 worktree 隔離以 origin/main（remote-tracking ref）為 base，
而非 local main HEAD。origin/main 落後時，worktree 會建在 stale 基底上，
缺少最新本地 commit（W2-013 實證需 agent 手動 recovery）。

建議：派發前先 push local main
  git push origin main

詳見: .claude/pm-rules/parallel-dispatch.md（worktree base 與 push-first 紀律）"""

# W4-008：origin/main 落後達 LAG_DENY_THRESHOLD 以上，改為阻擋派發（stderr，非 JSON）
ORIGIN_BEHIND_DENY_MESSAGE = """[W4-008 防護] origin/main 落後 local main {count} 個 commit，超過門檻 {threshold}，禁止派發 worktree agent

CC runtime 的 worktree 隔離以 origin/main（remote-tracking ref）為 base，
而非 local main HEAD。落後過多時 worktree 會建在嚴重過時的基底上，
代理人可能重建已存在檔案並產生無法直接合併的產出（0.2.0-W4-006 事故實證）。

修復方式：
  git push origin main

詳見: .claude/pm-rules/parallel-dispatch.md（worktree base 與 push-first 紀律）"""

# 目標票 md 在 origin/main 與 local main 之間有差異，阻擋派發（commit 數
# 門檻是落後量的代理指標，本檢查才是實際前提——目標票內容是否在 worktree
# base 內）
TICKET_UNSYNCED_DENY_MESSAGE = """[目標票同步防護] 目標票 {ticket_id} 的 md（{path}）尚未同步至 origin/main，禁止派發 worktree agent

CC runtime 的 worktree 隔離以 origin/main（remote-tracking ref）為 base，
worktree 代理人讀到的目標票內容會落後於 local main 上剛寫入的版本（例如
claim 後以 append-log 寫入的 Context Bundle 章節），代理人可能漏做該內容
所含的收尾要求且全程零錯誤訊號。

修復方式：
  git push origin main

詳見: .claude/pm-rules/parallel-dispatch.md（worktree base 與 push-first 紀律）"""


def _extract_target_ticket_id(prompt: str) -> Optional[str]:
    """從派發 prompt 首行提取目標 Ticket ID；抽取實作複用既有 SSOT，非票務
    派發或無標籤命中時回傳 None（呼叫端一律視為不阻擋）。
    """
    if not prompt or not prompt.strip():
        return None
    first_line = prompt.strip().splitlines()[0]
    return extract_ticket_id_anchored(first_line)


def _locate_ticket_md(ticket_id: str, project_root: Path, logger) -> Optional[Path]:
    """在 docs/work-logs 下定位目標票 md；定位不到（含目錄不存在、命中數不為
    1）一律回傳 None，呼叫端視為不阻擋但記錄可觀測性日誌。
    """
    tickets_root = project_root / "docs" / "work-logs"
    if not tickets_root.exists():
        logger.info("docs/work-logs 不存在，跳過目標票同步檢查: %s", ticket_id)
        return None
    try:
        matches = list(tickets_root.rglob(f"{ticket_id}.md"))
    except OSError as exc:
        logger.warning("定位目標票 md 失敗（%s）：%s", ticket_id, exc)
        return None
    if len(matches) != 1:
        logger.info(
            "目標票 md 定位失敗（%s 命中 %d 個），跳過同步檢查",
            ticket_id, len(matches),
        )
        return None
    return matches[0]


def _check_target_ticket_synced(md_path: Path, project_root: Path, logger) -> bool:
    """回傳 True 表示已同步或無法判斷（fail-open）；False 表示 origin/main
    與 local main 之間該檔有差異，呼叫端應阻擋派發。
    """
    try:
        rel_path = md_path.relative_to(project_root)
    except ValueError:
        logger.warning("目標票 md 不在 project_root 之下，跳過同步檢查: %s", md_path)
        return True

    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "origin/main..main", "--", str(rel_path)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=10, cwd=project_root,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        logger.warning("目標票同步檢查 git 命令失敗，放行: %s", exc)
        return True

    if result.returncode != 0:
        logger.warning(
            "目標票同步檢查 git diff 非零退出，放行: %s",
            result.stderr.strip()[:200],
        )
        return True

    if result.stdout.strip():
        logger.warning("目標票 md 未同步至 origin/main: %s", rel_path)
        return False

    return True


def _check_origin_behind(logger) -> int:
    """純計算 origin/main 落後 local main 的 commit 數，不做任何輸出（W4-009）。

    輸出決策（deny / emit additionalContext）全部移至 main()。PC-019 髒污
    判定已改為 exit 0（不再丟棄 stdout JSON），此函式維持純計算職責僅為
    保持與 origin/main 落後量 deny 分支（`behind_count >= LAG_DENY_THRESHOLD`
    時 exit 2）的既有結構一致。

    Args:
        logger: hook logger，供記錄檢查失敗原因（可觀測性規則 4）

    Returns:
        int: 落後的 commit 數。0 表示同步或無法判斷（git 失敗 / 無 remote /
             無法解析），呼叫端一律視為「無需警告」。
    """
    try:
        # 計算 origin/main..main 的 commit 數（local main 領先 origin/main 的量）
        result = subprocess.run(
            ["git", "rev-list", "--count", "origin/main..main"],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=10
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        # git 不可用 / 超時：無法判斷，記錄後略過（不阻擋派發）
        logger.warning("origin/main 落後檢查失敗：%s", exc)
        return 0

    if result.returncode != 0:
        # origin/main ref 不存在（未 push 過 / 無 remote）等情況，略過
        logger.info("origin/main 落後檢查略過（git rev-list 非零退出）")
        return 0

    count_str = result.stdout.strip()
    if not count_str.isdigit():
        logger.info("origin/main 落後檢查略過（無法解析 commit 數）")
        return 0

    behind_count = int(count_str)
    if behind_count == 0:
        logger.info("origin/main 與 local main 同步，無需警告")
    return behind_count


def main() -> int:
    """Hook 主邏輯。"""
    logger = setup_hook_logging("worktree-commit-before-dispatch")

    try:
        input_data = read_json_from_stdin(logger)
    except (json.JSONDecodeError, EOFError):
        logger.warning("無法解析 stdin JSON")
        return 0  # 解析失敗不阻擋

    if not input_data:
        return 0

    tool_input = input_data.get("tool_input", {})
    isolation = tool_input.get("isolation", "")

    # 只檢查 worktree 隔離的派發
    if isolation != "worktree":
        logger.debug("非 worktree 隔離，跳過檢查")
        return 0

    logger.info("偵測到 worktree 派發，檢查未 commit 變更")

    # 目標票 md 同步檢查：抽不到 ticket ID 或定位不到檔案時不阻擋（維持既有
    # 行為，避免對非票務派發誤擋），僅由上述兩函式記錄可觀測性日誌
    ticket_id = _extract_target_ticket_id(tool_input.get("prompt", ""))
    if ticket_id:
        project_root = get_project_root()
        md_path = _locate_ticket_md(ticket_id, project_root, logger)
        if md_path is not None and not _check_target_ticket_synced(
            md_path, project_root, logger
        ):
            rel_path = md_path.relative_to(project_root)
            message = TICKET_UNSYNCED_DENY_MESSAGE.format(
                ticket_id=ticket_id, path=rel_path
            )
            print(message, file=sys.stderr)
            logger.warning(
                "阻擋 worktree 派發：目標票 %s md 未同步至 origin/main", ticket_id
            )
            return 2

    # W4-008：origin/main 落後量先計算（純計算，不輸出）
    behind_count = _check_origin_behind(logger)

    # lag >= LAG_DENY_THRESHOLD：直接阻擋（stderr，不 emit JSON），與 PC-019 無關
    if behind_count >= LAG_DENY_THRESHOLD:
        message = ORIGIN_BEHIND_DENY_MESSAGE.format(
            count=behind_count, threshold=LAG_DENY_THRESHOLD
        )
        print(message, file=sys.stderr)
        logger.warning(
            "阻擋 worktree 派發：origin/main 落後 %d 個 commit（>= 門檻 %d）",
            behind_count, LAG_DENY_THRESHOLD,
        )
        return 2

    # 0 < lag < 閾值：emit additionalContext 警告。原 W4-009 修復要求延後 emit
    # 至確認不會走 PC-019 block（exit 2）之後才發出，避免 stdout JSON 被丟棄；
    # 本 hook 髒污路徑已改為 exit 0（見下方），全路徑不再有 exit 2 丟棄 JSON 的
    # 風險，故移至此處單點發出，不需依 changed_files 是否為空分道處理。
    if behind_count > 0:
        emit_hook_output(
            "PreToolUse",
            additional_context=ORIGIN_BEHIND_WARNING.format(count=behind_count),
            audience="pm_only",
            input_data=input_data,
        )
        logger.warning(
            "origin/main 落後 local main %d 個 commit（additionalContext 已發出）",
            behind_count,
        )

    # 檢查 tracked 檔案是否有未 commit 的變更
    try:
        unstaged = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10
        )
        staged = subprocess.run(
            ["git", "diff", "--staged", "--name-only"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        logger.warning("git 命令執行失敗")
        return 0  # git 失敗不阻擋

    changed_files = set()
    if unstaged.stdout.strip():
        changed_files.update(unstaged.stdout.strip().split("\n"))
    if staged.stdout.strip():
        changed_files.update(staged.stdout.strip().split("\n"))

    if not changed_files:
        logger.info("無未 commit 變更，放行")
        return 0

    # PC-019 WARN：主 repo 有未 commit tracked 變更，提醒但不阻擋派發。
    # 危險動作端已由 workspace-wipe-guard-hook.py 無條件 DENY 覆蓋，本 hook
    # 只保留 stderr 提醒維持可觀測性。
    files_list = "\n".join(f"  - {f}" for f in sorted(changed_files))
    message = WARN_MESSAGE.format(files=files_list)
    print(message, file=sys.stderr)
    logger.warning("提醒：主 repo 有 %d 個未 commit 檔案（不阻擋派發）", len(changed_files))
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "worktree-commit-before-dispatch"))
