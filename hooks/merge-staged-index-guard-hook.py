#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
Merge Staged Index Guard Hook - PreToolUse(Bash)

功能: 主工作區的 index 有 staged 變更（index != HEAD）時，擋下需建 merge commit 的
      `git merge`；可快轉（HEAD 為目標 ref 的祖先且無 --no-ff）的 merge 放行。

Hook Event: PreToolUse
Matcher: Bash
Decision: DENY（exit 2，stderr 訊息）| allow（無輸出，exit 0）

============================================================
為何擋
============================================================
index != HEAD 時，需建 merge commit 的 ort merge 必然失敗（merge_start 檢查
index 是否等於 HEAD）；失敗路徑以 read-tree --reset -u 把
index 與工作區重設為「merge 開始時的 HEAD」。他方在這段期間 commit 時，
重設目標是過期 tree，檔案與 index 雙雙退回舊值（實例：版本檔
2.66.0 -> 2.65.0）。擋下這類 merge 不損失任何能成功的合併。
快轉走 checkout_fast_forward（兩樹 unpack），staged 變更在不相干檔案上時會成功，
即使失敗也無 read-tree 回舊 HEAD 的收尾路徑，故放行。

============================================================
生成路徑盤點
============================================================
| 路徑 | 本守衛涵蓋 |
| Bash 直下 git merge（主工作區） | 是 |
| git -C <主 repo> merge | 是 |
| 目標位於 .claude/worktrees/* 或為 linked worktree | 否，放行（獨立 index） |
| 可快轉的 merge（HEAD 是 ref 祖先且無 --no-ff） | 否，放行 |
| ref 無法解析 / 多 ref（octopus） / --no-ff | 是，照 staged 判定 |
| git merge --abort / --continue / --quit | 否，放行（收拾中斷合併，擋下會卡住 repo） |
| CLI 內部 subprocess merge | 否（PreToolUse 看不到字面命令，已知邊界） |

失敗語意: 守衛自身例外、逾時、diff 非零 returncode 皆 fail-open（維持 fail_closed=False：
放行後 merge 可復原，且 hook 自身故障不得使全域卡死），一律寫 stderr 與日誌（quality-baseline 規則 4）。
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib import setup_hook_logging, run_hook_safely, read_json_from_stdin
from lib.git_command_parse import find_git_invocations

# 收拾中斷合併的路徑，必須放行
_RECOVERY_FLAGS = {"--abort", "--continue", "--quit"}

# git 子程序逾時秒數；全套件負載下偏緊，測試可 monkeypatch 放寬
_GIT_TIMEOUT_SECONDS = 10


def _run_git(target: str, args: List[str]) -> "subprocess.CompletedProcess":
    return subprocess.run(
        ["git", "-C", target, *args],
        capture_output=True, text=True, timeout=_GIT_TIMEOUT_SECONDS,
    )


def _staged_files(target: str, logger) -> List[str]:
    """回傳 index 相對 HEAD 的變更檔清單。

    非零 returncode 時維持 fail-open（回空清單），但寫日誌與 stderr 留下可見訊號。
    """
    result = _run_git(target, ["diff", "--cached", "--name-only"])
    if result.returncode != 0:
        detail = (result.stderr or "").strip()
        logger.warning(
            "diff --cached 回傳 %d，無法判定 index，fail-open 放行: %s",
            result.returncode, detail,
        )
        sys.stderr.write(
            f"[merge-staged-index-guard] diff --cached 回傳 {result.returncode}，"
            f"無法判定 index 狀態，已放行: {detail}\n"
        )
        return []
    return [line for line in result.stdout.splitlines() if line]


def _is_worktree(target: str) -> bool:
    """目標位於 .claude/worktrees/* 內，或為 linked worktree（git-dir != common-dir）。"""
    parts = Path(target).resolve().parts
    for i in range(len(parts) - 1):
        if parts[i] == ".claude" and parts[i + 1] == "worktrees":
            return True
    gd = _run_git(target, ["rev-parse", "--git-dir"])
    cd = _run_git(target, ["rev-parse", "--git-common-dir"])
    if gd.returncode != 0 or cd.returncode != 0:
        return False
    base = Path(target)
    return (base / gd.stdout.strip()).resolve() != (base / cd.stdout.strip()).resolve()


def _is_fast_forward(target: str, args: List[str]) -> bool:
    """單一 ref、無 --no-ff，且 HEAD 為該 ref 的祖先才算可快轉；其餘保守回 False。"""
    if "--no-ff" in args:
        return False
    refs = [a for a in args if not a.startswith("-")]
    if len(refs) != 1:
        return False
    result = _run_git(target, ["merge-base", "--is-ancestor", "HEAD", refs[0]])
    return result.returncode == 0


def _resolve_target(cwd: str, dash_c: Optional[str]) -> str:
    if not dash_c:
        return cwd
    return str(Path(cwd) / dash_c)  # 絕對 -C 路徑會覆蓋 cwd


def _build_deny_message(command: str, staged: List[str]) -> str:
    shown = "\n".join(f"  {f}" for f in staged[:15])
    if len(staged) > 15:
        shown += f"\n  ...（另 {len(staged) - 15} 筆）"
    return (
        "[git merge 被阻擋：目標 repo 的 index 有 staged 變更]\n\n"
        f"被攔截的命令：{command}\n\n"
        "理由：index != HEAD 時，需建 merge commit 的 merge 必然失敗，而失敗路徑會以 read-tree 把 "
        "index 與工作區重設為 merge 開始時的 HEAD。若他方在這段期間 commit，"
        "重設目標是過期 tree，檔案與 index 雙雙退回舊值。\n\n"
        f"目前 staged 檔：\n{shown}\n\n"
        "處置二選一：\n"
        "  1. 這些 staged 檔屬他方：等持有方提交完成後再 merge。\n"
        "  2. 確認屬自己：先 `git restore --staged <檔案>`（或提交）後再 merge。\n"
        "（`git merge --abort` / `--continue` 不受本守衛限制。）\n"
    )


def main() -> int:
    logger = setup_hook_logging("merge-staged-index-guard")
    try:
        input_data = read_json_from_stdin(logger)
        if not input_data or input_data.get("tool_name") != "Bash":
            return 0
        command = (input_data.get("tool_input") or {}).get("command", "") or ""
        if not command:
            return 0

        invocations = find_git_invocations(command, {"merge"})
        if not invocations:
            return 0  # None（無法解析）或無 merge 呼叫

        cwd = input_data.get("cwd") or os.getcwd()
        for inv in invocations:
            if any(a in _RECOVERY_FLAGS for a in inv.args):
                logger.debug("merge 收拾旗標，放行")
                continue
            target = _resolve_target(cwd, inv.dash_c_path)
            if _is_worktree(target):
                logger.debug("目標為 worktree，放行: %s", target)
                continue
            staged = _staged_files(target, logger)
            if not staged:
                logger.debug("index 乾淨，放行: %s", target)
                continue
            if _is_fast_forward(target, inv.args):
                logger.debug("可快轉 merge，放行: %s", target)
                continue
            logger.warning("git merge 被阻擋（staged=%d）: %s", len(staged), command)
            print(_build_deny_message(" ".join(inv.statement), staged), file=sys.stderr)
            return 2
        return 0
    except Exception as exc:  # fail-open：守衛自身故障不得阻擋合併
        logger.error("守衛自身例外，fail-open 放行: %s", exc, exc_info=True)
        sys.stderr.write(f"[merge-staged-index-guard] 自身例外，已放行: {exc}\n")
        return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "merge-staged-index-guard"))
