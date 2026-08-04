#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Bare Commit Guard Hook - PreToolUse Hook

功能: 並行派發期間偵測裸 git commit（無 -- pathspec / --amend / -a），
      DENY 阻擋跨 ticket 汙染共用 git index；非並行期僅 WARN 提醒。

Hook Event: PreToolUse
Matcher: Bash
Decision: DENY（exit 2，stderr 訊息）| WARN（exit 0，stderr 訊息）| allow（無輸出）

============================================================
背景（0.2.1-W3-276 ANA 裁決，完整回測數據見 ticket Solution）
============================================================
path-limited commit 文字條款（parallel-dispatch / dispatch-template 逐字範例）
四次失效後的機制層防線。8/1-8/4 570 筆 commit 回測：91 筆手動 commit 中
5 筆（agent commit 的 8.6%）為裸 commit 掃入他人 staged 檔案的跨 ticket 汙染，
5 筆事故全部發生在並行派發期間；非並行期裸 commit（PM 單線 bookkeeping）
27.3% 為刻意多 ticket 操作，無害。

三設計題裁決：
1. 觸發條件：並行條件觸發（.claude/dispatch-active.json 有活躍派發才啟用）。
   一律啟用會打斷 PM 33 筆合法裸 commit 中的多數（誤擋成本過高）。
2. 處置等級：並行期 DENY（exit 2）+ 非並行期 WARN（exit 0 + stderr）。
   WARN 對 AI agent 無約束力已四次實證，並行期改 DENY 才有效防護；
   非並行期維持 WARN 不打斷 PM 但仍提供提醒。
3. 豁免通道：三種自然豁免（-- pathspec / --amend / -a｜--all），不設顯式
   marker（marker 有同樣的記憶依賴問題）。

============================================================
探針結論（0.2.1-W3-277 前提驗證）
============================================================
1. dispatch-active.json 時效性：本 session（0.2.1-W3 wave）並行派發下，
   dispatches 陣列在無活躍派發時穩定為 []，未觀察到超時清理（housekeeping
   `cleanup_expired` 90+ 筆日誌中僅 2 筆命中，且皆非本 wave）的異常累積。
   次要觀察：SubagentStop 精準清理（clear_dispatch_by_id）在本 session 樣本
   中命中率偏低，改由 FIFO fallback 或更早的清理路徑處理——此為既有
   dispatch_tracker 機制的已知行為（非本票新增），效果是條目「提早消失」
   而非「殘留過久」，方向上不會導致非並行期被誤 DENY（本票風險項），
   僅可能在極端時序下低估真並行度而降級為 WARN（安全方向，符合 ANA
   本已接受的 ~20% 精確率設計）。
2. CLI auto-commit 不可見性：PreToolUse Bash hook 僅檢視 Bash 工具收到的
   **字面命令字串**（tool_input.command），不追蹤該命令執行時內部產生的
   子行程呼叫。`ticket track complete <id>` 等 CLI 命令字面文字不含
   "git commit"，其內部以 Python subprocess 呼叫 git commit 對本 hook
   結構性不可見（與 bash-git-protected-branch-guard-hook.py 等既有同類
   hook 的偵測模型一致）。本 session 執行歷程本身即為實證：多次
   `ticket track append-log` / `ticket track complete` 呼叫觸發了真實
   auto-commit（git log 可見對應 commit），但從未觸發任何以命令字面文字
   比對為基礎的 Bash git guard。

============================================================
範疇邊界（刻意不做，非遺漏）
============================================================
- 僅偵測 cwd 隱含形式的 `git commit`（含 `git -C <path> commit`），不解析
  子 shell `cd` 形式的目標 repo（與本 hook 的目的無關——本 hook 檢查的是
  「是否夾帶他人 staged 檔案」，非跨 repo 保護分支，無需解析目標 repo）。
- staged 檔案清單一律讀取專案根目錄（get_project_root()）的 git index，
  不解析 `-C <path>` 指向的其他 repo（回測樣本 91 筆手動 commit 皆為
  cwd 隱含形式，此範疇涵蓋實際發現的事故模式）。
- `-a`/`--all` 豁免偵測為全命令字串層級的 token 掃描，非嚴格綁定 commit
  呼叫本身的參數位置。已知殘留：commit message 內容恰好含獨立 ` -a `
  子字串時可能被誤判為豁免（如 `git commit -m "fix -a bug"`）。方向安全
  （誤判方向是「該擋的沒擋」而非「不該擋的被擋」），符合 ANA 對此類邊界
  情境的容忍設計，未進一步處理。
"""

import json
import re
import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib import setup_hook_logging, run_hook_safely, read_json_from_stdin
from lib.dispatch_tracker import get_active_dispatches
from lib.git_utils import get_project_root, run_git_command


# 便宜前置判斷 + 主偵測：cwd 隱含形式與 `-C <path>` 形式的 git commit
_GIT_COMMIT_RE = re.compile(r"\bgit\s+(?:-C\s+\S+\s+)?commit\b")

# 三種自然豁免（0.2.1-W3-276 裁決，不設顯式 marker）
_PATHSPEC_RE = re.compile(r"(?:^|\s)--(?:\s|$)")
_AMEND_RE = re.compile(r"(?:^|\s)--amend\b")
_ALL_FLAG_RE = re.compile(r"(?:^|\s)(?:--all|-[a-zA-Z]*a[a-zA-Z]*)(?:\s|$)")


def _contains_git_commit(command: str) -> bool:
    """偵測命令是否含 `git commit`（cwd 隱含或 `-C <path>` 形式）。"""
    if not command:
        return False
    return bool(_GIT_COMMIT_RE.search(command))


def _has_natural_exemption(command: str) -> bool:
    """三種自然豁免任一命中即豁免：-- pathspec / --amend / -a｜--all。"""
    return bool(
        _PATHSPEC_RE.search(command)
        or _AMEND_RE.search(command)
        or _ALL_FLAG_RE.search(command)
    )


def _get_active_dispatch_count(project_root: Path) -> int:
    """取得目前活躍派發數，讀取失敗時保守回傳 0（fail-open，降級為 WARN）。"""
    try:
        return len(get_active_dispatches(project_root))
    except Exception:
        return 0


def _get_staged_files(project_root: Path) -> List[str]:
    """取得目前 staged 檔案清單，讀取失敗時回傳空清單。"""
    success, output = run_git_command(
        ["diff", "--cached", "--name-only"], cwd=str(project_root)
    )
    if not success or not output:
        return []
    return [line.strip() for line in output.splitlines() if line.strip()]


def _build_deny_message(staged_files: List[str], dispatch_count: int) -> str:
    """組出 DENY 訊息：含當前 staged 清單 + path-limited 逐字範例（可直接複製）。"""
    if staged_files:
        staged_block = "\n".join(f"  - {f}" for f in staged_files)
        example_files = " ".join(staged_files[:3])
        example_cmd = f'  git commit -m "你的訊息" -- {example_files}'
    else:
        staged_block = "  （無法讀取，可能不在 git repo 或無 staged 變更）"
        example_cmd = '  git commit -m "你的訊息" -- <你 ticket 相關的檔案>'

    return (
        "[並行派發期間裸 commit 被阻擋]\n\n"
        f"理由：目前有 {dispatch_count} 個實作代理人正在派發中"
        "（.claude/dispatch-active.json 有活躍記錄），裸 git commit"
        "（無 -- pathspec / --amend / -a）會把共用 git index 中其他人的"
        "staged 檔案一併提交，造成跨 ticket 汙染"
        "（0.2.1-W3-276 回測：91 筆手動 commit 中 agent commit 的 8.6% "
        "為此類事故）。\n\n"
        "當前 staged 檔案：\n"
        f"{staged_block}\n\n"
        "請改用 path-limited commit，只挑出你 ticket 相關的檔案接在 -- 後面，"
        "例如：\n"
        f"{example_cmd}\n\n"
        "確需一次提交全部 staged 內容（刻意行為）時，改用：\n"
        '  git commit -a -m "你的訊息"     # 提交所有 tracked 變更\n'
        "  git commit --amend             # 修訂上一筆 commit\n"
    )


def _build_warn_message() -> str:
    """組出非並行期的 WARN 提醒訊息（exit 0，不阻擋）。"""
    return (
        "[提醒] 偵測到裸 git commit（無 -- pathspec / --amend / -a）。"
        "目前無並行派發活躍記錄，本次放行；建議養成 path-limited 習慣，"
        "以防未來並行期誤觸跨 ticket 汙染：\n"
        '  git commit -m "你的訊息" -- <你的檔案>\n'
    )


def main() -> int:
    """Hook 主邏輯：並行期 DENY 裸 commit，非並行期 WARN。"""
    logger = setup_hook_logging("bare-commit-guard")

    try:
        input_data = read_json_from_stdin(logger)
    except (json.JSONDecodeError, EOFError):
        logger.warning("無法解析 stdin JSON，放行")
        return 0

    if not input_data:
        return 0

    tool_name = input_data.get("tool_name", "")
    if tool_name != "Bash":
        return 0

    tool_input = input_data.get("tool_input") or {}
    command = tool_input.get("command", "") or ""

    if not _contains_git_commit(command):
        logger.debug("命令不含 git commit，放行")
        return 0

    if _has_natural_exemption(command):
        logger.debug("命令含自然豁免（-- / --amend / -a｜--all），放行")
        return 0

    project_root = get_project_root()
    dispatch_count = _get_active_dispatch_count(project_root)

    if dispatch_count > 0:
        staged_files = _get_staged_files(project_root)
        logger.warning(
            "並行期裸 commit 被阻擋（活躍派發數=%d，staged 檔案數=%d）",
            dispatch_count, len(staged_files),
        )
        print(_build_deny_message(staged_files, dispatch_count), file=sys.stderr)
        return 2

    logger.info("非並行期裸 commit，WARN 放行")
    print(_build_warn_message(), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "bare-commit-guard"))
